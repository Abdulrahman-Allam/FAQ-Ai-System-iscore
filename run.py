import csv
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import torch.nn.functional as F
from pyarabic.araby import strip_tashkeel
from flask import Flask, request, jsonify
from flask_cors import CORS
from deep_translator import GoogleTranslator
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import os
import math

# Initialize translator
translator_ar = GoogleTranslator(source='en', target='ar')
translator_en = GoogleTranslator(source='ar', target='en')

# Database setup
DATABASE_URL = "postgresql://postgres.miqxqndvjliyelaceqip:FAQwhat?1234@aws-0-eu-north-1.pooler.supabase.com:5432/postgres"

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
        return conn
    except Exception as e:
        print(f"Database connection error: {e}")
        return None

def init_database():
    """Initialize the database with required tables (only if they don't exist)"""
    try:
        conn = get_db_connection()
        if not conn:
            print("Failed to connect to database")
            return
            
        cursor = conn.cursor()
        
        # Create questions table ONLY if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS questions (
                question_id BIGSERIAL PRIMARY KEY,
                question_text TEXT NOT NULL,
                answer_text TEXT,
                status VARCHAR(20) DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create feedback table ONLY if it doesn't exist
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS feedback (
                feed_id BIGSERIAL PRIMARY KEY,
                question_id BIGINT NOT NULL,
                is_good BOOLEAN NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (question_id) REFERENCES questions (question_id) ON DELETE CASCADE
            )
        ''')
        
        # Check if tables exist and show counts
        cursor.execute('SELECT COUNT(*) as count FROM questions')
        questions_count = cursor.fetchone()['count']
        
        cursor.execute('SELECT COUNT(*) as count FROM feedback')
        feedback_count = cursor.fetchone()['count']
        
        conn.commit()
        cursor.close()
        conn.close()
        
        print(f"✅ Database connection successful!")
        print(f"📊 Existing questions: {questions_count}")
        print(f"📊 Existing feedback: {feedback_count}")
        print("🔄 Tables ready - preserving all existing data")
        
    except Exception as e:
        print(f"❌ Database initialization error: {e}")

def store_question(question_text, answer_text, status):
    """Store question and answer in database with better error handling"""
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        if not conn:
            print("Failed to get database connection")
            return None
            
        cursor = conn.cursor()
        
        # Insert new question (will auto-increment question_id)
        insert_query = '''
            INSERT INTO questions (question_text, answer_text, status, created_at)
            VALUES (%s, %s, %s, %s) 
            RETURNING question_id
        '''
        
        cursor.execute(insert_query, (
            question_text, 
            answer_text, 
            status, 
            datetime.now()
        ))
        
        result = cursor.fetchone()
        
        if result and 'question_id' in result:
            question_id = result['question_id']
            conn.commit()
            print(f"✅ Question stored with ID: {question_id}, Status: {status}")
            return question_id
        else:
            print("❌ No question_id returned from insert")
            conn.rollback()
            return None
        
    except Exception as e:
        print(f"❌ Database error storing question: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return None
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn:
            try:
                conn.close()
            except:
                pass

def store_feedback(question_id, is_good):
    """Store feedback for a question"""
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        if not conn:
            return False
            
        cursor = conn.cursor()
        
        # Check if the question exists
        cursor.execute('SELECT question_id FROM questions WHERE question_id = %s', (question_id,))
        if not cursor.fetchone():
            print(f"❌ Question ID {question_id} does not exist")
            return False
        
        # Insert feedback
        cursor.execute('''
            INSERT INTO feedback (question_id, is_good, created_at)
            VALUES (%s, %s, %s)
            RETURNING feed_id
        ''', (question_id, is_good, datetime.now()))
        
        result = cursor.fetchone()
        
        if result and 'feed_id' in result:
            feed_id = result['feed_id']
            conn.commit()
            print(f"✅ Feedback stored with ID: {feed_id} for question {question_id}")
            return True
        else:
            print("❌ No feed_id returned from insert")
            conn.rollback()
            return False
        
    except Exception as e:
        print(f"❌ Feedback storage error: {e}")
        if conn:
            try:
                conn.rollback()
            except:
                pass
        return False
        
    finally:
        if cursor:
            try:
                cursor.close()
            except:
                pass
        if conn:
            try:
                conn.close()
            except:
                pass

# Initialize database on startup
init_database()

# Load Egyptian labor rules FAQ data
faq_data = []

def load_passages(file_path: str, target_list: list):
    """Load FAQ passages into the specified list without considering headers."""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            reader = csv.reader(file, delimiter="\t")
            for row in reader:
                if not row:
                    continue
                if len(row) < 2:
                    raise ValueError("Each row must have at least two columns: docid and passage_text.")
                target_list.append({"docid": row[0].strip(), "text": row[1].strip()})
    except FileNotFoundError as e:
        print(f"Error: File {file_path} not found.")
        raise e
    except Exception as e:
        print(f"Error loading {file_path}: {e}")
        raise e

def translate_text(text: str, target_lang: str = 'ar') -> str:
    """Translate text to target language."""
    try:
        if target_lang == 'ar':
            return translator_ar.translate(text)
        else:
            return translator_en.translate(text)
    except Exception as e:
        print(f"Translation error: {e}")
        return text

def detect_language(text: str) -> str:
    """Detect if text is Arabic or English."""
    try:
        arabic_chars = sum(1 for char in text if '\u0600' <= char <= '\u06FF')
        if arabic_chars > len(text) * 0.3:
            return 'ar'
        return 'en'
    except Exception as e:
        print(f"Language detection error: {e}")
        return 'en'

try:
    load_passages("A.tsv", faq_data)
    print(f"Loaded {len(faq_data)} FAQ entries.")
except Exception as e:
    print(f"Error loading TSV files: {e}")
    raise e

faq_model_path = "FAQ-Model"

try:
    faq_tokenizer = AutoTokenizer.from_pretrained(faq_model_path)
    faq_model = AutoModelForSequenceClassification.from_pretrained(faq_model_path)
    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"Using device: {device}")
    faq_model.to(device)
    print(f"FAQ model loaded successfully! Using device: {device}")
except Exception as e:
    print(f"Error loading model or tokenizer: {e}")
    raise e

def retrieve_passage(query: str, top_k: int = 10, max_passages: int = 200):
    try:
        print(f"Received Question: {query}")

        selected_tokenizer = faq_tokenizer
        selected_model = faq_model
        passages_to_process = faq_data[:max_passages]
        batch_size = 16

        results = []

        for i in range(0, len(passages_to_process), batch_size):
            batch = passages_to_process[i:i+batch_size]
            normalized_query = strip_tashkeel(query)
            normalized_passages = [strip_tashkeel(passage["text"]) for passage in batch]

            inputs = selected_tokenizer(
                text=[normalized_query] * len(batch),
                text_pair=normalized_passages,
                truncation=True,
                padding=True,
                return_tensors="pt"
            )

            inputs = {key: val.to(device) for key, val in inputs.items()}

            with torch.no_grad():
                outputs = selected_model(**inputs)
            logits = outputs.logits

            if logits.shape[1] == 1:
                relevance_scores = torch.sigmoid(logits.squeeze(-1)).tolist()
            else:
                probabilities = F.softmax(logits, dim=-1)
                relevance_scores = probabilities[:, 1].tolist()

            results.extend([
                {"docid": passage["docid"], "text": passage["text"], "score": score}
                for passage, score in zip(batch, relevance_scores)
            ])

        results = sorted(results, key=lambda x: x["score"], reverse=True)
        return results[:top_k]

    except Exception as e:
        print(f"Error during retrieval: {e}")
        raise

# Flask App
app = Flask(__name__)
CORS(app)

# Add a global state to track vacation query mode
vacation_query_sessions = {}

def get_employee_vacation(employee_id):
    """Get employee vacation information from database"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        
        cursor.execute('''

            SELECT employee_id, name, remaining_vacations
            FROM employees 
            WHERE employee_id = %s
        ''', (employee_id,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return {
                'employee_id': result['employee_id'],
                'name': result['name'],
                'remaining_vacations': result['remaining_vacations']
            }
        return None
        
    except Exception as e:
        print(f"❌ Error fetching employee vacation: {e}")
        return None

def get_employee_department(employee_id):
    """Get employee's current department information"""
    try:
        conn = get_db_connection()
        if not conn:
            return None
            
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT e.employee_id, e.name as employee_name, e.department_id,
                   d.department_name, d.department_head
            FROM employees e
            JOIN departments d ON e.department_id = d.department_id
            WHERE e.employee_id = %s
        ''', (employee_id,))
        
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        
        if result:
            return {
                'employee_id': result['employee_id'],
                'employee_name': result['employee_name'],
                'current_department_id': result['department_id'],
                'current_department_name': result['department_name'],
                'current_department_head': result['department_head']
            }
        return None
        
    except Exception as e:
        print(f"❌ Error fetching employee department: {e}")
        return None

def get_department_by_name(department_name):
    """Get department information by name with flexible matching"""
    try:
        conn = get_db_connection()
        if not conn:
            print("❌ No database connection")
            return None
            
        cursor = conn.cursor()
        
        print(f"🔍 Searching for department: '{department_name}'")
        
        # First try exact match (case insensitive)
        cursor.execute('''
            SELECT department_id, department_name, department_head
            FROM departments 
            WHERE LOWER(TRIM(department_name)) = LOWER(TRIM(%s))
        ''', (department_name,))
        
        result = cursor.fetchone()
        print(f"📋 Exact match result: {result}")
        
        # If no exact match, try partial match
        if not result:
            print("🔍 Trying partial match...")
            cursor.execute('''
                SELECT department_id, department_name, department_head
                FROM departments 
                WHERE LOWER(TRIM(department_name)) LIKE LOWER(TRIM(%s))
                LIMIT 1
            ''', (f'%{department_name}%',))
            
            result = cursor.fetchone()
            print(f"📋 Partial match result: {result}")
        
        # Debug: Show all departments
        cursor.execute('SELECT department_name FROM departments ORDER BY department_name')
        all_depts = cursor.fetchall()
        print(f"📊 All departments in DB: {[d['department_name'] for d in all_depts]}")
        
        cursor.close()
        conn.close()
        
        if result:
            found_dept = {
                'department_id': result['department_id'],
                'department_name': result['department_name'],
                'department_head': result['department_head']
            }
            print(f"✅ Department found: {found_dept}")
            return found_dept
        
        print(f"❌ No department found for: '{department_name}'")
        return None
        
    except Exception as e:
        print(f"❌ Error fetching department: {e}")
        return None

def get_all_departments():
    """Get all available departments"""
    try:
        conn = get_db_connection()
        if not conn:
            print("❌ No database connection for departments list")
            return []
            
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT department_name
            FROM departments 
            ORDER BY department_name
        ''')
        
        results = cursor.fetchall()
        cursor.close()
        conn.close()
        
        dept_list = [row['department_name'] for row in results]
        print(f"📊 Retrieved {len(dept_list)} departments: {dept_list}")
        return dept_list
        
    except Exception as e:
        print(f"❌ Error fetching departments: {e}")
        return []

# Add endpoint to get common questions (vacation + department change)
@app.route('/common-questions', methods=['GET'])
def get_common_questions():
    """Get list of common questions for dropdown"""
    try:
        language = request.args.get('language', 'ar')
        
        if language == 'ar':
            questions = [
                {"id": "vacation", "text": "كم لي من إجازات متبقية؟"},
                {"id": "department", "text": "أريد تغيير قسمي"},
                {"id": "resignation", "text": "أريد تقديم استقالة"}
            ]
        else:
            questions = [
                {"id": "vacation", "text": "How many vacation days do I have remaining?"},
                {"id": "department", "text": "I want to change my department"},
                {"id": "resignation", "text": "I want to submit a resignation"}
            ]
        
        return jsonify({"questions": questions}), 200
        
    except Exception as e:
        return jsonify({"error": f"Failed to get common questions: {str(e)}"}), 500

@app.route('/ask', methods=['POST'])
def ask_question():
    """Endpoint to handle user questions with vacation and department change support."""
    try:
        data = request.get_json()
        
        if not data or 'question' not in data:
            return jsonify({"error": "Missing 'question' in request"}), 400
        
        original_question = data['question']
        top_k = data.get('top_k', 5)
        user_language = data.get('language', 'ar')
        session_id = data.get('session_id', 'default')
        is_common_question = data.get('is_common_question', False)
        
        print(f"Original question: {original_question}")
        print(f"User language: {user_language}")
        print(f"Session ID: {session_id}")
        print(f"Is common question: {is_common_question}")
        
        # ONLY trigger auto-response if it's from the dropdown
        # Update the auto-response detection section
        if is_common_question and session_id not in vacation_query_sessions:
            # Check if this is the vacation question from dropdown
            vacation_questions = [
                "كم لي من إجازات متبقية؟",
                "How many vacation days do I have remaining?"
            ]
            
            # Check if this is the department change question from dropdown
            department_questions = [
                "أريد تغيير قسمي",
                "I want to change my department"
            ]
            
            # Check if this is the resignation question from dropdown
            resignation_questions = [
                "أريد تقديم استقالة",
                "I want to submit a resignation"
            ]
            
            is_vacation_dropdown = any(vq in original_question for vq in vacation_questions)
            is_department_dropdown = any(dq in original_question for dq in department_questions)
            is_resignation_dropdown = any(rq in original_question for rq in resignation_questions)
            
            if is_vacation_dropdown:
                # Vacation query logic - NO DATABASE STORAGE
                vacation_query_sessions[session_id] = {'waiting_for_id': True, 'type': 'vacation'}
                
                id_request_message = user_language == 'ar' \
                    and 'من فضلك أدخل رقم الموظف الخاص بك للاستعلام عن رصيد الإجازات.\n\n(اكتب "q" للخروج)' \
                    or 'Please enter your employee ID to check your vacation balance.\n\n(Type "q" to exit)'
                
                print(f"Vacation query from dropdown detected - auto response (not saved)")
                
                return jsonify({
                    "answers": [id_request_message],
                    "confidence_scores": [1.0],
                    "question_id": None,  # No question ID for auto responses
                    "status": "vacation_query",
                    "session_id": session_id
                }), 200
                
            elif is_department_dropdown:
                # Department change query logic - NO DATABASE STORAGE
                vacation_query_sessions[session_id] = {'waiting_for_department': True, 'type': 'department'}
                
                # Get all departments for user reference
                departments = get_all_departments()
                
                # Format departments list nicely with better spacing
                if user_language == 'ar':
                    dept_list_formatted = "\n".join([f"• {dept}" for dept in departments])
                    dept_request_message = f'''إلى أي قسم تريد الانتقال؟

الأقسام المتاحة:
{dept_list_formatted}

يرجى كتابة اسم القسم بالضبط كما هو مكتوب أعلاه.

(اكتب "q" للخروج)'''
                else:
                    dept_list_formatted = "\n".join([f"• {dept}" for dept in departments])
                    dept_request_message = f'''Which department do you want to switch to?

Available departments:
{dept_list_formatted}

Please type the department name exactly as written above.

(Type "q" to exit)'''
                
                print(f"Department change query from dropdown detected - auto response (not saved)")
                print(f"Available departments: {departments}")
                
                return jsonify({
                    "answers": [dept_request_message],
                    "confidence_scores": [1.0],
                    "question_id": None,  # No question ID for auto responses
                    "status": "department_query",
                    "session_id": session_id
                }, 200)
            
            elif is_resignation_dropdown:
                # Resignation query logic - NO DATABASE STORAGE
                vacation_query_sessions[session_id] = {'waiting_for_id': True, 'type': 'resignation'}
                
                id_request_message = user_language == 'ar' \
                    and 'من فضلك أدخل رقم الموظف الخاص بك لمعالجة طلب الاستقالة.\n\n(اكتب "q" للخروج)' \
                    or 'Please enter your employee ID to process your resignation request.\n\n(Type "q" to exit)'
                
                print(f"Resignation query from dropdown detected - auto response (not saved)")
                
                return jsonify({
                    "answers": [id_request_message],
                    "confidence_scores": [1.0],
                    "question_id": None,  # No question ID for auto responses
                    "status": "resignation_query",
                    "session_id": session_id
                }), 200
        
        # Handle vacation ID response - NO DATABASE STORAGE
        elif session_id in vacation_query_sessions and vacation_query_sessions[session_id].get('waiting_for_id') and vacation_query_sessions[session_id].get('type') == 'vacation':
            # Check if user wants to exit
            if original_question.strip().lower() == 'q':
                del vacation_query_sessions[session_id]
                
                exit_message = user_language == 'ar' \
                    and 'تم إلغاء الاستعلام عن الإجازات. يمكنك الآن طرح أي سؤال آخر.' \
                    or 'Vacation query cancelled. You can now ask any other question.'
                
                print(f"User exited vacation query - auto response (not saved)")
                
                return jsonify({
                    "answers": [exit_message],
                    "confidence_scores": [1.0],
                    "question_id": None,
                    "status": "query_cancelled",
                    "session_id": session_id
                }), 200
            
            try:
                employee_id = int(original_question.strip())
                employee_data = get_employee_vacation(employee_id)
                
                if employee_data:
                    vacation_info_ar = f"مرحباً {employee_data['name']}، لديك {employee_data['remaining_vacations']} يوم إجازة متبقي."
                    vacation_info_en = f"Hello {employee_data['name']}, you have {employee_data['remaining_vacations']} vacation days remaining."
                    
                    vacation_message = user_language == 'ar' and vacation_info_ar or vacation_info_en
                    
                    del vacation_query_sessions[session_id]
                    
                    print(f"Vacation info provided - auto response (not saved)")
                    
                    return jsonify({
                        "answers": [vacation_message],
                        "confidence_scores": [1.0],
                        "question_id": None,  # No question ID for auto responses
                        "status": "vacation_answered",
                        "session_id": session_id
                    }), 200
                    
                else:
                    not_found_message = user_language == 'ar' \
                        and f'رقم الموظف {employee_id} غير موجود في النظام. يرجى التحقق من الرقم والمحاولة مرة أخرى.\n\n(اكتب "q" للخروج)' \
                        or f'Employee ID {employee_id} not found in the system. Please check the ID and try again.\n\n(Type "q" to exit)'
                    
                    print(f"Employee not found - auto response (not saved)")
                    
                    return jsonify({
                        "answers": [not_found_message],
                        "confidence_scores": [1.0],
                        "question_id": None,  # No question ID for auto responses
                        "status": "vacation_not_found",
                        "session_id": session_id
                    }), 200
                    
            except ValueError:
                invalid_format_message = user_language == 'ar' \
                    and 'يرجى إدخال رقم موظف صحيح (أرقام فقط).\n\n(اكتب "q" للخروج)' \
                    or 'Please enter a valid employee ID (numbers only).\n\n(Type "q" to exit)'
                
                print(f"Invalid ID format - auto response (not saved)")
                
                return jsonify({
                    "answers": [invalid_format_message],
                    "confidence_scores": [1.0],
                    "question_id": None,  # No question ID for auto responses
                    "status": "vacation_invalid_format",
                    "session_id": session_id
                }), 200

        # Handle department name response - NO DATABASE STORAGE
        elif session_id in vacation_query_sessions and vacation_query_sessions[session_id].get('waiting_for_department') and vacation_query_sessions[session_id].get('type') == 'department':
            # Check if user wants to exit
            if original_question.strip().lower() == 'q':
                del vacation_query_sessions[session_id]
                
                exit_message = user_language == 'ar' \
                    and 'تم إلغاء طلب تغيير القسم. يمكنك الآن طرح أي سؤال آخر.' \
                    or 'Department change request cancelled. You can now ask any other question.'
                
                print(f"User exited department query - auto response (not saved)")
                
                return jsonify({
                    "answers": [exit_message],
                    "confidence_scores": [1.0],
                    "question_id": None,
                    "status": "query_cancelled",
                    "session_id": session_id
                }), 200
            
            # Clean the input
            department_input = original_question.strip()
            target_department = get_department_by_name(department_input)
            
            print(f"User input: '{department_input}'")
            print(f"Department found: {target_department}")
            
            if target_department:
                # Valid department - now ask for employee ID
                vacation_query_sessions[session_id] = {
                    'waiting_for_employee_id': True, 
                    'type': 'department',
                    'target_department': target_department
                }
                
                id_request_message = user_language == 'ar' \
                    and f'تم اختيار قسم "{target_department["department_name"]}".\nمن فضلك أدخل رقم الموظف الخاص بك.\n\n(اكتب "q" للخروج)' \
                    or f'Selected department: "{target_department["department_name"]}".\nPlease enter your employee ID.\n\n(Type "q" to exit)'
                
                print(f"Department selected - auto response (not saved)")
                
                return jsonify({
                    "answers": [id_request_message],
                    "confidence_scores": [1.0],
                    "question_id": None,  # No question ID for auto responses
                    "status": "department_id_request",
                    "session_id": session_id
                }), 200
            else:
                # Invalid department - show formatted list
                departments = get_all_departments()
                
                # Format departments list properly with better display
                if user_language == 'ar':
                    dept_list_formatted = "\n".join([f"• {dept}" for dept in departments])
                    invalid_dept_message = f'''القسم "{department_input}" غير موجود.

الأقسام المتاحة:
{dept_list_formatted}

يرجى اختيار اسم القسم بالضبط كما هو مكتوب أعلاه.

(اكتب "q" للخروج)'''
                else:
                    dept_list_formatted = "\n".join([f"• {dept}" for dept in departments])
                    invalid_dept_message = f'''Department "{department_input}" not found.

Available departments:
{dept_list_formatted}

Please choose the department name exactly as written above.

(Type "q" to exit)'''
                
                print(f"Invalid department - auto response (not saved)")
                print(f"Available departments: {departments}")
                
                return jsonify({
                    "answers": [invalid_dept_message],
                    "confidence_scores": [1.0],
                    "question_id": None,  # No question ID for auto responses
                    "status": "department_invalid",
                    "session_id": session_id
                }), 200

        # Handle employee ID for department change - NO DATABASE STORAGE
        elif session_id in vacation_query_sessions and vacation_query_sessions[session_id].get('waiting_for_employee_id') and vacation_query_sessions[session_id].get('type') == 'department':
            # Check if user wants to exit
            if original_question.strip().lower() == 'q':
                del vacation_query_sessions[session_id]
                
                exit_message = user_language == 'ar' \
                    and 'تم إلغاء طلب تغيير القسم. يمكنك الآن طرح أي سؤال آخر.' \
                    or 'Department change request cancelled. You can now ask any other question.'
                
                print(f"User exited department query - auto response (not saved)")
                
                return jsonify({
                    "answers": [exit_message],
                    "confidence_scores": [1.0],
                    "question_id": None,
                    "status": "query_cancelled",
                    "session_id": session_id
                }), 200
            
            try:
                employee_id = int(original_question.strip())
                employee_data = get_employee_department(employee_id)
                
                if employee_data:
                    target_department = vacation_query_sessions[session_id]['target_department']
                    
                    # Check if they're trying to switch to the same department
                    if employee_data['current_department_id'] == target_department['department_id']:
                        same_dept_message = user_language == 'ar' \
                            and f'أنت موجود بالفعل في قسم {employee_data["current_department_name"]}. لا يمكنك الانتقال إلى نفس القسم الذي تعمل به.' \
                            or f'You are already in the {employee_data["current_department_name"]} department. You cannot switch to the same department you are currently in.'
                        
                        del vacation_query_sessions[session_id]
                        
                        print(f"Same department request - auto response (not saved)")
                        
                        return jsonify({
                            "answers": [same_dept_message],
                            "confidence_scores": [1.0],
                            "question_id": None,  # No question ID for auto responses
                            "status": "department_same",
                            "session_id": session_id
                        }), 200
                    
                    # Valid request - provide contact information
                    contact_message_ar = f'''مرحباً {employee_data["employee_name"]}،
            
للانتقال من قسم {employee_data["current_department_name"]} إلى قسم {target_department["department_name"]}، تحتاج للتواصل مع:

1. رئيس قسمك الحالي: {employee_data["current_department_head"]}
2. رئيس القسم المراد الانتقال إليه: {target_department["department_head"]}

يرجى التنسيق مع كلا الطرفين للموافقة على عملية النقل.'''

                    contact_message_en = f'''Hello {employee_data["employee_name"]},

To transfer from {employee_data["current_department_name"]} department to {target_department["department_name"]} department, you need to contact:

1. Your current department head: {employee_data["current_department_head"]}
2. Target department head: {target_department["department_head"]}

Please coordinate with both parties to approve the transfer.'''
                
                    contact_message = user_language == 'ar' and contact_message_ar or contact_message_en
                    
                    del vacation_query_sessions[session_id]
                    
                    print(f"Department change info provided - auto response (not saved)")
                    
                    return jsonify({
                        "answers": [contact_message],
                        "confidence_scores": [1.0],
                        "question_id": None,  # No question ID for auto responses
                        "status": "department_answered",
                        "session_id": session_id
                    }), 200
                    
                else:
                    # Employee not found
                    not_found_message = user_language == 'ar' \
                        and f'رقم الموظف {employee_id} غير موجود في النظام. يرجى التحقق من الرقم والمحاولة مرة أخرى.\n\n(اكتب "q" للخروج)' \
                        or f'Employee ID {employee_id} not found in the system. Please check the ID and try again.\n\n(Type "q" to exit)'
                    
                    print(f"Employee not found for department change - auto response (not saved)")
                    
                    return jsonify({
                        "answers": [not_found_message],
                        "confidence_scores": [1.0],
                        "question_id": None,  # No question ID for auto responses
                        "status": "department_employee_not_found",
                        "session_id": session_id
                    }), 200
                    
            except ValueError:
                # Invalid ID format
                invalid_format_message = user_language == 'ar' \
                    and 'يرجى إدخال رقم موظف صحيح (أرقام فقط).\n\n(اكتب "q" للخروج)' \
                    or 'Please enter a valid employee ID (numbers only).\n\n(Type "q" to exit)'
                
                print(f"Invalid ID format for department change - auto response (not saved)")
                
                return jsonify({
                    "answers": [invalid_format_message],
                    "confidence_scores": [1.0],
                    "question_id": None,  # No question ID for auto responses
                    "status": "department_invalid_format",
                    "session_id": session_id
                }), 200
        
        # Update the vacation/resignation ID response section to handle both vacation AND resignation
        elif session_id in vacation_query_sessions and vacation_query_sessions[session_id].get('waiting_for_id') and vacation_query_sessions[session_id].get('type') in ['vacation', 'resignation']:
            # Check if user wants to exit
            if original_question.strip().lower() == 'q':
                del vacation_query_sessions[session_id]
                
                query_type = vacation_query_sessions.get(session_id, {}).get('type', 'vacation')
                
                if query_type == 'resignation':
                    exit_message = user_language == 'ar' \
                        and 'تم إلغاء طلب الاستقالة. يمكنك الآن طرح أي سؤال آخر.' \
                        or 'Resignation request cancelled. You can now ask any other question.'
                else:
                    exit_message = user_language == 'ar' \
                        and 'تم إلغاء الاستعلام عن الإجازات. يمكنك الآن طرح أي سؤال آخر.' \
                        or 'Vacation query cancelled. You can now ask any other question.'
                
                print(f"User exited {query_type} query - auto response (not saved)")
                
                return jsonify({
                    "answers": [exit_message],
                    "confidence_scores": [1.0],
                    "question_id": None,
                    "status": "query_cancelled",
                    "session_id": session_id
                }), 200
            
            try:
                employee_id = int(original_question.strip())
                query_type = vacation_query_sessions[session_id].get('type')
                
                if query_type == 'resignation':
                    # Handle resignation request
                    employee_data = get_employee_department(employee_id)
                    
                    if employee_data:
                        resignation_message_ar = f'''مرحباً {employee_data["employee_name"]}،

لتقديم طلب الاستقالة، يرجى التوجه إلى رئيس قسمك:

👤 رئيس قسم {employee_data["current_department_name"]}: {employee_data["current_department_head"]}

سيقوم رئيس القسم بإرشادك خلال إجراءات الاستقالة الرسمية والوثائق المطلوبة.

نتمنى لك التوفيق في مسيرتك المهنية القادمة.'''

                        resignation_message_en = f'''Hello {employee_data["employee_name"]},

To submit your resignation request, please contact your department head:

👤 {employee_data["current_department_name"]} Department Head: {employee_data["current_department_head"]}

Your department head will guide you through the formal resignation procedures and required documentation.

We wish you the best in your future career endeavors.'''
                        
                        resignation_message = user_language == 'ar' and resignation_message_ar or resignation_message_en
                        
                        del vacation_query_sessions[session_id]
                        
                        print(f"Resignation info provided - auto response (not saved)")
                        
                        return jsonify({
                            "answers": [resignation_message],
                            "confidence_scores": [1.0],
                            "question_id": None,  # No question ID for auto responses
                            "status": "resignation_answered",
                            "session_id": session_id
                        }), 200
                        
                    else:
                        not_found_message = user_language == 'ar' \
                            and f'رقم الموظف {employee_id} غير موجود في النظام. يرجى التحقق من الرقم والمحاولة مرة أخرى.\n\n(اكتب "q" للخروج)' \
                            or f'Employee ID {employee_id} not found in the system. Please check the ID and try again.\n\n(Type "q" to exit)'
                        
                        print(f"Employee not found for resignation - auto response (not saved)")
                        
                        return jsonify({
                            "answers": [not_found_message],
                            "confidence_scores": [1.0],
                            "question_id": None,  # No question ID for auto responses
                            "status": "resignation_not_found",
                            "session_id": session_id
                        }), 200
                
                elif query_type == 'vacation':
                    # Handle vacation request (existing code)
                    employee_data = get_employee_vacation(employee_id)
                    
                    if employee_data:
                        vacation_info_ar = f"مرحباً {employee_data['name']}، لديك {employee_data['remaining_vacations']} يوم إجازة متبقي."
                        vacation_info_en = f"Hello {employee_data['name']}, you have {employee_data['remaining_vacations']} vacation days remaining."
                        
                        vacation_message = user_language == 'ar' and vacation_info_ar or vacation_info_en
                        
                        del vacation_query_sessions[session_id]
                        
                        print(f"Vacation info provided - auto response (not saved)")
                        
                        return jsonify({
                            "answers": [vacation_message],
                            "confidence_scores": [1.0],
                            "question_id": None,  # No question ID for auto responses
                            "status": "vacation_answered",
                            "session_id": session_id
                        }), 200
                        
                    else:
                        not_found_message = user_language == 'ar' \
                            and f'رقم الموظف {employee_id} غير موجود في النظام. يرجى التحقق من الرقم والمحاولة مرة أخرى.\n\n(اكتب "q" للخروج)' \
                            or f'Employee ID {employee_id} not found in the system. Please check the ID and try again.\n\n(Type "q" to exit)'
                        
                        print(f"Employee not found - auto response (not saved)")
                        
                        return jsonify({
                            "answers": [not_found_message],
                            "confidence_scores": [1.0],
                            "question_id": None,  # No question ID for auto responses
                            "status": "vacation_not_found",
                            "session_id": session_id
                        }), 200
                        
            except ValueError:
                query_type = vacation_query_sessions[session_id].get('type', 'vacation')
                
                if query_type == 'resignation':
                    invalid_format_message = user_language == 'ar' \
                        and 'يرجى إدخال رقم موظف صحيح (أرقام فقط).\n\n(اكتب "q" للخروج)' \
                        or 'Please enter a valid employee ID (numbers only).\n\n(Type "q" to exit)'
                    
                    print(f"Invalid ID format for resignation - auto response (not saved)")
                    
                    return jsonify({
                        "answers": [invalid_format_message],
                        "confidence_scores": [1.0],
                        "question_id": None,  # No question ID for auto responses
                        "status": "resignation_invalid_format",
                        "session_id": session_id
                    }), 200
                else:
                    invalid_format_message = user_language == 'ar' \
                        and 'يرجى إدخال رقم موظف صحيح (أرقام فقط).\n\n(اكتب "q" للخروج)' \
                        or 'Please enter a valid employee ID (numbers only).\n\n(Type "q" to exit)'
                    
                    print(f"Invalid ID format - auto response (not saved)")
                    
                    return jsonify({
                        "answers": [invalid_format_message],
                        "confidence_scores": [1.0],
                        "question_id": None,  # No question ID for auto responses
                        "status": "vacation_invalid_format",
                        "session_id": session_id
                    }), 200

        # Regular FAQ processing (ONLY THESE GET SAVED TO DATABASE)
        else:
            # Clear any existing vacation session if it's a new question
            if session_id in vacation_query_sessions and not any(key in vacation_query_sessions[session_id] for key in ['waiting_for_id', 'waiting_for_department', 'waiting_for_employee_id']):
                del vacation_query_sessions[session_id]
            
            print("Processing as regular FAQ question - sending to model (WILL BE SAVED)")
            
            detected_lang = detect_language(original_question)
            print(f"Detected language: {detected_lang}")
            
            if detected_lang == 'en' or user_language == 'en':
                arabic_question = translate_text(original_question, 'ar')
                print(f"Translated question to Arabic: {arabic_question}")
            else:
                arabic_question = original_question
            
            # Retrieve passages using the Arabic question
            results = retrieve_passage(arabic_question, top_k=top_k)
            
            if not results:
                # SAVE TO DATABASE - No results found
                question_id = store_question(
                    original_question, 
                    "not answered",
                    'pending'
                )
                
                pending_message = (user_language == 'ar' and detected_lang == 'ar') \
                    and 'عذرًا، لم أجد إجابة مناسبة لسؤالك، لقد أرسلنا سؤالك لفريقنا للإجابة عليه في أقرب وقت ممكن.' \
                    or 'Sorry, I could not find a suitable answer to your question, we sent this question to our team to answer you as soon as possible.'
                
                print(f"No model results - saved to database with ID: {question_id}")
                
                return jsonify({
                    "answers": [pending_message],
                    "confidence_scores": [0.0],
                    "question_id": question_id,
                    "status": "pending",
                    "session_id": session_id
                }), 200
            
            # Extract answers and confidence scores
            arabic_answers = [result["text"] for result in results]
            confidence_scores = [result["score"] for result in results]
            
            # Get top answer and confidence
            top_answer = arabic_answers[0]
            top_confidence = confidence_scores[0]
            
            # Normalize confidence if needed
            if top_confidence > 1.0:
                top_confidence = 1 / (1 + math.exp(-top_confidence))
            
            print(f"Confidence score: {top_confidence}")
            
            # Check confidence threshold
            if top_confidence < 0.1:  # Less than 10%
                # SAVE TO DATABASE - Low confidence
                question_id = store_question(
                    original_question, 
                    "not answered",
                    'pending'
                )
                
                pending_message = (user_language == 'ar' and detected_lang == 'ar') \
                    and 'عذرًا، لم أجد إجابة مناسبة لسؤالك، لقد أرسلنا سؤالك لفريقنا للإجابة عليه في أقرب وقت ممكن.' \
                    or 'Sorry, I could not find a suitable answer to your question, we sent this question to our team to answer you as soon as possible.'
                
                print(f"Low confidence - saved to database with ID: {question_id}")
                
                return jsonify({
                    "answers": [pending_message],
                    "confidence_scores": [top_confidence],
                    "question_id": question_id,
                    "status": "pending",
                    "session_id": session_id
                }), 200
            
            # High confidence - translate if needed and store as answered
            if user_language == 'en' and arabic_answers:
                english_answers = []
                for answer in arabic_answers:
                    translated_answer = translate_text(answer, 'en')
                    english_answers.append(translated_answer)
                    print(f"Translated answer to English: {translated_answer}")
                final_answers = english_answers
                final_answer = final_answers[0]
            else:
                final_answers = arabic_answers
                final_answer = final_answers[0]
            
            # SAVE TO DATABASE - High confidence model answer
            question_id = store_question(
                original_question,
                final_answer,
                'answered'
            )
            
            print(f"Model answer provided - saved to database with ID: {question_id}")
            
            return jsonify({
                "answers": final_answers,
                "confidence_scores": confidence_scores,
                "question_id": question_id,
                "status": "answered",
                "session_id": session_id
            }), 200
        
    except Exception as e:
        print(f"Error in ask_question: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/feedback', methods=['POST'])
def submit_feedback():
    """Endpoint to submit feedback for answers"""
    try:
        data = request.get_json()
        
        if not data or 'question_id' not in data or 'is_good' not in data:
            return jsonify({"error": "Missing required fields"}), 400
        
        question_id = data['question_id']
        is_good = data['is_good']
        
        success = store_feedback(question_id, is_good)
        
        if success:
            return jsonify({"message": "Feedback stored successfully"}), 200
        else:
            return jsonify({"error": "Failed to store feedback"}), 500
        
    except Exception as e:
        print(f"Error in submit_feedback: {e}")
        return jsonify({"error": "Internal server error"}), 500

# Add the Flask app execution block
if __name__ == '__main__':
    print("🚀 Starting Flask server...")
    print("📍 Server will be available at: http://localhost:5000")
    print("🔗 Common questions endpoint: http://localhost:5000/common-questions")
    print("🔗 Ask endpoint: http://localhost:5000/ask")
    print("🔗 Feedback endpoint: http://localhost:5000/feedback")
    print("=" * 50)
    
    try:
        app.run(
            host='0.0.0.0',
            port=5000,
            debug=True,
            threaded=True
        )
    except Exception as e:
        print(f"❌ Error starting server: {e}")
        input("Press Enter to exit...")
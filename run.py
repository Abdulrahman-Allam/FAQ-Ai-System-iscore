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
import numpy as np
from sentence_transformers import SentenceTransformer
import logging
from dotenv import load_dotenv
from functools import wraps

# Load environment variables
load_dotenv()

# Initialize translator
translator_ar = GoogleTranslator(source='en', target='ar')
translator_en = GoogleTranslator(source='ar', target='en')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Alternative DB config from environment variables
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'database': os.getenv('DB_NAME', 'faq_db'),
    'user': os.getenv('DB_USER', 'postgres'),
    'password': os.getenv('DB_PASSWORD', 'password'),
    'port': os.getenv('DB_PORT', '5432')
}

# Admin API Key
ADMIN_API_KEY = os.getenv('ADMIN_API_KEY', 'your-secret-admin-key-here')

# Initialize the sentence transformer model for vector similarity
model = SentenceTransformer('all-MiniLM-L6-v2')  # 384 dimensions

def require_admin_api_key(f):
    """Decorator to require API key for admin endpoints"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Check for API key in X-API-Key header
        api_key = request.headers.get('x-api-key')
        
        if not api_key:
            return jsonify({
                "error": "API key is required", 
                "message": "Please provide an API key in the 'X-API-Key' header"
            }), 401
        
        if api_key != ADMIN_API_KEY:
            return jsonify({
                "error": "Invalid API key", 
                "message": "The provided API key is not valid"
            }), 403
        
        return f(*args, **kwargs)
    return decorated_function

def get_db_connection():
    """Get database connection with fallback to environment config"""
    try:
        # Try direct URL first
            # Fallback to environment config
            conn = psycopg2.connect(**DB_CONFIG)
            return conn
    except Exception as e:
        logger.error(f"Database connection error: {e}")
        print(f"Database connection error: {e}")
        return None


def calculate_similarity_threshold(embedding, top_k=3):
    """Calculate similarity scores using vector embeddings"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # Convert embedding to PostgreSQL vector format
            embedding_str = '[' + ','.join(map(str, embedding)) + ']'
            
            # Find most similar questions using cosine similarity
            cur.execute("""
                SELECT q_id, q_text, answer_text, dep_id, status,
                       1 - (q_embedding <=> %s::vector) as similarity
                FROM questions 
                WHERE status = 'answered' AND q_embedding IS NOT NULL
                ORDER BY q_embedding <=> %s::vector
                LIMIT %s
            """, (embedding_str, embedding_str, top_k))
            
            results = cur.fetchall()
            print(f"Found {len(results)} similar questions")
            return results
    except Exception as e:
        logger.error(f"Vector similarity error: {e}")
        print(f"Vector similarity error: {e}")
        return []
    finally:
        if conn:
            conn.close()

def log_interaction(question_id, department_id):
    """Log user interactions for analytics"""
    conn = get_db_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO interaction_logs (q_id, dep_id)
                VALUES (%s, %s)
            """, (question_id, department_id))
            conn.commit()
    except Exception as e:
        logger.error(f"Error logging interaction: {e}")
        if conn:
            conn.rollback()
    finally:
        if conn:
            conn.close()

def store_question(question_text, answer_text, status):
    """Store question and answer in database with vector embedding support"""
    conn = None
    cursor = None
    
    try:
        conn = get_db_connection()
        if not conn:
            print("Failed to get database connection")
            return None
            
        cursor = conn.cursor()
        
        # Generate embedding for the question
        question_embedding = model.encode(question_text)
        embedding_str = '[' + ','.join(map(str, question_embedding)) + ']'
        
        # Insert new question with vector embedding
        insert_query = '''
            INSERT INTO questions (q_text, answer_text, status, created_at, q_embedding, updated_at)
            VALUES (%s, %s, %s, %s, %s::vector, %s) 
            RETURNING q_id
        '''
        
        cursor.execute(insert_query, (
            question_text, 
            answer_text, 
            status, 
            datetime.now(),
            embedding_str,
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
        cursor.execute('SELECT q_id FROM questions WHERE q_id = %s', (question_id,))
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

def insert_sample_data():
    """Insert sample departments and employees for testing"""
    try:
        conn = get_db_connection()
        if not conn:
            return
            
        cursor = conn.cursor()
        
        # Insert sample departments if they don't exist
        departments = [
            (1, "Human Resources", "Ahmed Hassan"),
            (2, "Engineering", "Sarah Mohammed"),
            (3, "Finance", "Omar Ali"),
            (4, "Marketing", "Fatima Ibrahim"),
            (5, "Operations", "Hassan Abdullah")
        ]
        
        for dept_id, dept_name, dept_head in departments:
            cursor.execute("""
                INSERT INTO departments (department_id, department_name, department_head)
                VALUES (%s, %s, %s) ON CONFLICT (department_id) DO NOTHING
            """, (dept_id, dept_name, dept_head))
        
        # Insert sample employees if they don't exist
        employees = [
            (1001, "Ali Ahmed", 1, 25),
            (1002, "Mona Hassan", 2, 20),
            (1003, "Ahmed Omar", 3, 30),
            (1004, "Layla Ibrahim", 4, 15),
            (1005, "Khaled Abdullah", 5, 22)
        ]
        
        for emp_id, name, dept_id, vacations in employees:
            cursor.execute("""
                INSERT INTO employees (employee_id, name, department_id, remaining_vacations)
                VALUES (%s, %s, %s, %s) ON CONFLICT (employee_id) DO NOTHING
            """, (emp_id, name, dept_id, vacations))
        
        conn.commit()
        cursor.close()
        conn.close()
        print("✅ Sample data inserted successfully")
        
    except Exception as e:
        print(f"❌ Error inserting sample data: {e}")

# Insert sample data
insert_sample_data()

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

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "timestamp": datetime.now().isoformat()})

@app.route('/departments', methods=['GET'])
def get_departments():
    """Get all departments"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("SELECT department_id as dep_id, department_name as dept_name FROM departments")
            departments = cur.fetchall()
            return jsonify({"departments": departments})
    except Exception as e:
        logger.error(f"Error fetching departments: {e}")
        return jsonify({"error": "Failed to fetch departments"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/admin/pending-questions', methods=['GET'])
@require_admin_api_key
def get_admin_pending_questions():
    """Admin endpoint to get all pending questions with details"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT q.q_id as q_id, q.q_text as q_text, q.created_at, 
                       d.dept_name as dept_name, q.dep_id
                FROM questions q
                LEFT JOIN departments d ON q.dep_id = d.department_id
                WHERE q.status = 'pending'
                ORDER BY q.created_at DESC
            """)
            
            pending_questions = cur.fetchall()
            
            return jsonify({
                "pending_questions": [
                    {
                        "id": q['q_id'],
                        "question": q['q_text'],
                        "department_id": q['dep_id'],
                        "department_name": q['dept_name'],
                        "submitted_at": q['created_at'].isoformat() if q['created_at'] else None
                    } for q in pending_questions
                ]
            })
            
    except Exception as e:
        logger.error(f"Error fetching pending questions: {e}")
        return jsonify({"error": "Failed to fetch pending questions"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/admin/answer-question', methods=['PUT'])
@require_admin_api_key
def admin_answer_question():
    """Admin endpoint to answer a specific pending question and assign department"""
    try:
        data = request.get_json()
        
        if not data or 'question_id' not in data or 'answer' not in data:
            return jsonify({"error": "Question ID and answer are required"}), 400
        
        question_id = data['question_id']
        answer = data['answer']
        department_id = data.get('department_id')  # Optional - can assign department
        
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check if question exists and is pending
                cur.execute("""
                    SELECT q_id as q_id, q_text as q_text FROM questions 
                    WHERE q_id = %s AND status = 'pending'
                """, (question_id,))
                
                question = cur.fetchone()
                if not question:
                    return jsonify({"error": "Question not found or not pending"}), 404
                
                # Generate embedding for the answer if not exists
                question_embedding = model.encode(question['q_text'])
                embedding_str = '[' + ','.join(map(str, question_embedding)) + ']'
                
                # Update question with answer and optionally department
                if department_id:
                    cur.execute("""
                        UPDATE questions 
                        SET answer_text = %s, status = 'answered', dep_id = %s, 
                            updated_at = CURRENT_TIMESTAMP, q_embedding = %s::vector
                        WHERE q_id = %s
                    """, (answer, department_id, embedding_str, question_id))
                else:
                    cur.execute("""
                        UPDATE questions 
                        SET answer_text = %s, status = 'answered', 
                            updated_at = CURRENT_TIMESTAMP, q_embedding = %s::vector
                        WHERE q_id = %s
                    """, (answer, embedding_str, question_id))
                
                conn.commit()
                
                return jsonify({
                    "status": "success",
                    "message": "Question answered successfully",
                    "question_id": question_id,
                    "question": question['q_text'],
                    "answer": answer
                })
                
        except Exception as e:
            logger.error(f"Error answering question: {e}")
            conn.rollback()
            return jsonify({"error": "Failed to answer question"}), 500
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error processing answer: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/questions/<int:question_id>', methods=['GET'])
def get_question_details(question_id):
    """Get details of a specific question"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT q.q_id, q.q_text, q.answer_text, q.status, 
                       q.created_at, q.updated_at, d.department_name as dept_name
                FROM questions q
                LEFT JOIN departments d ON q.dep_id = d.department_id
                WHERE q.q_id = %s
            """, (question_id,))
            
            question = cur.fetchone()
            
            if not question:
                return jsonify({"error": "Question not found"}), 404
            
            return jsonify({"question": dict(question)})
            
    except Exception as e:
        logger.error(f"Error fetching question details: {e}")
        return jsonify({"error": "Failed to fetch question details"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/questions/<int:question_id>/similar', methods=['GET'])
def get_similar_questions(question_id):
    """Get similar questions for a specific question"""
    conn = get_db_connection()
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            # First get the target question's embedding
            cur.execute("""
                SELECT q_embedding FROM questions 
                WHERE q_id = %s AND status = 'answered'
            """, (question_id,))
            
            result = cur.fetchone()
            if not result or not result['q_embedding']:
                return jsonify({"error": "Question not found or no embedding available"}), 404
            
            # Find similar questions
            cur.execute("""
                SELECT q_id as q_id, q_text as q_text, answer_text, dep_id,
                       1 - (q_embedding <=> %s) as similarity
                FROM questions 
                WHERE status = 'answered' AND q_id != %s AND q_embedding IS NOT NULL
                ORDER BY q_embedding <=> %s
                LIMIT 3
            """, (result['q_embedding'], question_id, result['q_embedding']))
            
            similar_questions = cur.fetchall()
            
            return jsonify({
                "similar_questions": [
                    {
                        "id": q['q_id'],
                        "question": q['q_text'],
                        "answer": q['answer_text'],
                        "department_id": q['dep_id'],
                        "similarity": round(q['similarity'], 3)
                    } for q in similar_questions if q['similarity'] >= 0.5
                ]
            })
            
    except Exception as e:
        logger.error(f"Error fetching similar questions: {e}")
        return jsonify({"error": "Failed to fetch similar questions"}), 500
    finally:
        if conn:
            conn.close()

@app.route('/submit-question', methods=['POST'])
def submit_new_question():
    """Endpoint for users to submit new questions"""
    try:
        data = request.get_json()
        
        if not data or 'question' not in data:
            return jsonify({"error": "Question is required"}), 400
        
        question_text = data['question'].strip()
        department_id = data.get('department_id')  # Optional
        
        if not question_text:
            return jsonify({"error": "Question cannot be empty"}), 400
        
        conn = get_db_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                # Check if question already exists
                cur.execute("""
                    SELECT q_id as q_id, q_text as q_text, answer_text, status FROM questions 
                    WHERE q_text = %s
                """, (question_text,))
                
                existing_question = cur.fetchone()
                
                if existing_question:
                    if existing_question['status'] == 'answered' and existing_question['answer_text']:
                        # Question already exists and is answered
                        return jsonify({
                            "status": "existing_question",
                            "message": "This question already exists in our database.",
                            "question_id": existing_question['q_id'],
                            "question": existing_question['q_text'],
                            "answer": existing_question['answer_text']
                        })
                    elif existing_question['status'] == 'pending':
                        # Question already exists but is pending
                        return jsonify({
                            "status": "pending_question",
                            "message": "This question has already been submitted and is pending review.",
                            "ticket_id": existing_question['q_id'],
                            "question": existing_question['q_text']
                        })
                
                # Generate embedding for the new question
                question_embedding = model.encode(question_text)
                embedding_str = '[' + ','.join(map(str, question_embedding)) + ']'
                
                # Insert new question with pending status
                cur.execute("""
                    INSERT INTO questions (q_text, dep_id, status, q_embedding, answer_text, created_at, updated_at)
                    VALUES (%s, %s, 'pending', %s::vector, NULL, %s, %s)
                    RETURNING q_id
                """, (question_text, department_id, embedding_str, datetime.now(), datetime.now()))
                
                result = cur.fetchone()
                ticket_id = result['question_id']
                
                conn.commit()
                
                return jsonify({
                    "status": "success",
                    "message": "Your question has been submitted successfully. You will be notified once answered.",
                    "ticket_id": ticket_id,
                    "question": question_text
                })
                
        except Exception as e:
            logger.error(f"Error saving new question: {e}")
            conn.rollback()
            return jsonify({"error": "Failed to save your question"}), 500
        finally:
            conn.close()
            
    except Exception as e:
        logger.error(f"Error processing new question: {e}")
        return jsonify({"error": "Internal server error"}), 500

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
            
            detected_lang = detect_language(original_question)
            print(f"Detected language: {detected_lang}")
            
            # ENGLISH QUESTIONS: Use vector similarity search only
            if detected_lang == 'en' or user_language == 'en':
                print("English question detected - using vector similarity search (NO translation)")
                
                try:
                    # Use original English question for vector search
                    question_embedding = model.encode(original_question)
                    similar_questions = calculate_similarity_threshold(question_embedding, top_k=3)
                    
                    if similar_questions:
                        best_match = similar_questions[0]
                        similarity_threshold = 0.7
                        
                        print(f"Vector similarity - Best match score: {best_match.get('similarity', 0)}")
                        
                        if best_match.get('similarity', 0) >= similarity_threshold:
                            # Found a good match in existing questions
                            matched_question = best_match
                            
                            # Log the interaction
                            log_interaction(matched_question['q_id'], data.get('department_id'))
                            
                            # Get similar questions (excluding the matched one)
                            similar_suggestions = [q for q in similar_questions[1:3] if q.get('similarity', 0) >= 0.5]
                            
                            print(f"Vector similarity match found - using existing answer (not saved again)")
                            
                            # Format response to match frontend expectations (answers array)
                            return jsonify({
                                "answers": [matched_question['answer_text']],
                                "confidence_scores": [matched_question['similarity']],
                                "question_id": matched_question['q_id'],
                                "status": "answered",
                                "session_id": session_id,
                                "matched_question": {
                                    "id": matched_question['q_id'],
                                    "question": matched_question['q_text'],
                                    "answer": matched_question['answer_text'],
                                    "department_id": matched_question.get('dep_id'),
                                    "similarity": round(matched_question['similarity'], 3)
                                },
                                "similar_questions": [
                                    {
                                        "id": q['q_id'],
                                        "question": q['q_text'],
                                        "similarity": round(q['similarity'], 3)
                                    } for q in similar_suggestions
                                ]
                            }), 200
                    
                    # No good vector match for English question - save as pending
                    print("No vector similarity match for English question - saving as pending")
                    question_id = store_question(
                        original_question, 
                        "not answered",
                        'pending'
                    )
                    
                    pending_message = 'Sorry, I could not find a suitable answer to your question. We sent this question to our team to answer you as soon as possible.'
                    
                    return jsonify({
                        "answers": [pending_message],
                        "confidence_scores": [0.0],
                        "question_id": question_id,
                        "status": "pending",
                        "session_id": session_id
                    }), 200
                    
                except Exception as e:
                    print(f"Vector similarity search failed for English question: {e}")
                    # Save as pending if vector search fails
                    question_id = store_question(
                        original_question, 
                        "not answered",
                        'pending'
                    )
                    
                    pending_message = 'Sorry, I could not find a suitable answer to your question. We sent this question to our team to answer you as soon as possible.'
                    
                    return jsonify({
                        "answers": [pending_message],
                        "confidence_scores": [0.0],
                        "question_id": question_id,
                        "status": "pending",
                        "session_id": session_id
                    }), 200
            
            # ARABIC QUESTIONS: Use Arabic model only (NO vector similarity, NO translation)
            else:
                print("Arabic question detected - using Arabic model directly (NO vector similarity, NO translation)")
                
                # Use Arabic question directly with the model
                results = retrieve_passage(original_question, top_k=top_k)
                
                if not results:
                    # SAVE TO DATABASE - No results found
                    question_id = store_question(
                        original_question, 
                        "not answered",
                        'pending'
                    )
                    
                    pending_message = 'عذرًا، لم أجد إجابة مناسبة لسؤالك، لقد أرسلنا سؤالك لفريقنا للإجابة عليه في أقرب وقت ممكن.'
                    
                    print(f"No Arabic model results - saved to database with ID: {question_id}")
                    
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
                
                print(f"Arabic model confidence score: {top_confidence}")
                
                # Check confidence threshold
                if top_confidence < 0.1:  # Less than 10%
                    # SAVE TO DATABASE - Low confidence
                    question_id = store_question(
                        original_question, 
                        "not answered",
                        'pending'
                    )
                    
                    pending_message = 'عذرًا، لم أجد إجابة مناسبة لسؤالك، لقد أرسلنا سؤالك لفريقنا للإجابة عليه في أقرب وقت ممكن.'
                    
                    print(f"Low confidence from Arabic model - saved to database with ID: {question_id}")
                    
                    return jsonify({
                        "answers": [pending_message],
                        "confidence_scores": [top_confidence],
                        "question_id": question_id,
                        "status": "pending",
                        "session_id": session_id
                    }), 200
                
                # High confidence - use Arabic answers directly (NO translation)
                final_answers = arabic_answers
                final_answer = final_answers[0]
                
                # SAVE TO DATABASE - High confidence Arabic model answer
                question_id = store_question(
                    original_question,
                    final_answer,
                    'answered'
                )
                
                print(f"Arabic model answer provided - saved to database with ID: {question_id}")
                
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
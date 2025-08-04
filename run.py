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
        ''', (question_id, is_good, datetime.now()))
        
        conn.commit()
        print(f"✅ Feedback stored for question {question_id}: {'👍 positive' if is_good else '👎 negative'}")
        return True
        
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

@app.route('/ask', methods=['POST'])
def ask_question():
    """Endpoint to handle user questions with database integration."""
    try:
        data = request.get_json()
        
        if not data or 'question' not in data:
            return jsonify({"error": "Missing 'question' in request"}), 400
        
        original_question = data['question']
        top_k = data.get('top_k', 5)
        user_language = data.get('language', 'ar')
        
        print(f"Original question: {original_question}")
        print(f"User language: {user_language}")
        
        # Detect and translate if needed
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
            # No results found - store as pending with "not answered"
            question_id = store_question(
                original_question, 
                "not answered",  # Changed from None to "not answered"
                'pending'
            )
            
            pending_message = (user_language == 'ar' and detected_lang == 'ar') \
                and 'عذرًا، لم أجد إجابة مناسبة لسؤالك، لقد أرسلنا سؤالك لفريقنا للإجابة عليه في أقرب وقت ممكن.' \
                or 'Sorry, I could not find a suitable answer to your question, we sent this question to our team to answer you as soon as possible.'
            
            return jsonify({
                "answers": [pending_message],
                "confidence_scores": [0.0],
                "question_id": question_id,
                "status": "pending"
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
            # Low confidence - store as pending with "not answered"
            question_id = store_question(
                original_question, 
                "not answered",  # Changed from top_answer to "not answered"
                'pending'
            )
            
            pending_message = (user_language == 'ar' and detected_lang == 'ar') \
                and 'عذرًا، لم أجد إجابة مناسبة لسؤالك، لقد أرسلنا سؤالك لفريقنا للإجابة عليه في أقرب وقت ممكن.' \
                or 'Sorry, I could not find a suitable answer to your question, we sent this question to our team to answer you as soon as possible.'
            
            return jsonify({
                "answers": [pending_message],
                "confidence_scores": [top_confidence],
                "question_id": question_id,
                "status": "pending"
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
        
        # Store as answered with the actual model answer
        question_id = store_question(
            original_question,
            final_answer,  # Store the actual answer for high confidence
            'answered'
        )
        
        return jsonify({
            "answers": final_answers,
            "confidence_scores": confidence_scores,
            "question_id": question_id,
            "status": "answered"
        }), 200
        
    except Exception as e:
        print(f"Error in ask_question: {e}")
        return jsonify({"error": "Internal server error"}), 500

@app.route('/feedback', methods=['POST'])
def submit_feedback():
    """Endpoint to handle user feedback."""
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

@app.route('/stats', methods=['GET'])
def get_database_stats():
    """Get database statistics"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"error": "Database connection failed"}), 500
        
        cursor = conn.cursor()
        
        # Get questions stats
        cursor.execute('''
            SELECT 
                status,
                COUNT(*) as count
            FROM questions 
            GROUP BY status
        ''')
        status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
        
        # Get total questions
        cursor.execute('SELECT COUNT(*) as total FROM questions')
        total_questions = cursor.fetchone()['total']
        
        # Get total feedback
        cursor.execute('SELECT COUNT(*) as total FROM feedback')
        total_feedback = cursor.fetchone()['total']
        
        # Get recent questions
        cursor.execute('''
            SELECT question_id, question_text, status, created_at
            FROM questions 
            ORDER BY created_at DESC 
            LIMIT 10
        ''')
        recent_questions = cursor.fetchall()
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "total_questions": total_questions,
            "total_feedback": total_feedback,
            "status_breakdown": status_counts,
            "recent_questions": [dict(q) for q in recent_questions]
        }), 200
        
    except Exception as e:
        return jsonify({"error": f"Stats query failed: {str(e)}"}), 500

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    try:
        conn = get_db_connection()
        if not conn:
            return jsonify({"status": "unhealthy", "database": "disconnected"}), 500
        
        cursor = conn.cursor()
        cursor.execute('SELECT COUNT(*) as count FROM questions')
        questions_count = cursor.fetchone()['count']
        
        cursor.close()
        conn.close()
        
        return jsonify({
            "status": "healthy", 
            "database": "connected",
            "questions_in_db": questions_count
        }), 200
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
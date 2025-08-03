import csv
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import torch.nn.functional as F
from pyarabic.araby import strip_tashkeel
from flask import Flask, request, jsonify
from flask_cors import CORS  # To handle CORS for React frontend
from deep_translator import GoogleTranslator  # Updated translation library

# Initialize translator
translator_ar = GoogleTranslator(source='en', target='ar')
translator_en = GoogleTranslator(source='ar', target='en')

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
            # Translate to Arabic
            return translator_ar.translate(text)
        else:
            # Translate to English
            return translator_en.translate(text)
    except Exception as e:
        print(f"Translation error: {e}")
        return text  # Return original text if translation fails

def detect_language(text: str) -> str:
    """Detect if text is Arabic or English."""
    try:
        # Simple detection based on Arabic characters
        arabic_chars = sum(1 for char in text if '\u0600' <= char <= '\u06FF')
        if arabic_chars > len(text) * 0.3:  # If more than 30% Arabic characters
            return 'ar'
        return 'en'
    except Exception as e:
        print(f"Language detection error: {e}")
        return 'en'  # Default to English

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
                # For single output, apply sigmoid to get probability
                relevance_scores = torch.sigmoid(logits.squeeze(-1)).tolist()
            else:
                # For two outputs, apply softmax and take the positive class probability
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
CORS(app)  # Enable CORS for all routes

@app.route('/ask', methods=['POST'])
def ask_question():
    """Endpoint to handle user questions with translation support."""
    try:
        # Get the JSON payload from the request
        data = request.get_json()
        
        if not data or 'question' not in data:
            return jsonify({"error": "Missing 'question' in request"}), 400
        
        original_question = data['question']
        top_k = data.get('top_k', 5)  # Default to top 5 results
        user_language = data.get('language', 'ar')  # Default to Arabic
        
        print(f"Original question: {original_question}")
        print(f"User language: {user_language}")
        
        # Detect the language of the input question
        detected_lang = detect_language(original_question)
        print(f"Detected language: {detected_lang}")
        
        # Translate question to Arabic if it's in English
        if detected_lang == 'en' or user_language == 'en':
            arabic_question = translate_text(original_question, 'ar')
            print(f"Translated question to Arabic: {arabic_question}")
        else:
            arabic_question = original_question
        
        # Retrieve passages using the Arabic question
        results = retrieve_passage(arabic_question, top_k=top_k)
        
        if not results:
            return jsonify({"answers": [], "confidence_scores": []}), 200
        
        # Extract answers and confidence scores
        arabic_answers = [result["text"] for result in results]
        confidence_scores = [result["score"] for result in results]
        
        # Translate answers back to English if user language is English
        if user_language == 'en' and arabic_answers:
            english_answers = []
            for answer in arabic_answers:
                translated_answer = translate_text(answer, 'en')
                english_answers.append(translated_answer)
                print(f"Translated answer to English: {translated_answer}")
            final_answers = english_answers
        else:
            final_answers = arabic_answers
        
        return jsonify({
            "answers": final_answers,
            "confidence_scores": confidence_scores,
            "original_question": original_question,
            "translated_question": arabic_question if detected_lang == 'en' else None
        }), 200
        
    except Exception as e:
        print(f"Error in ask_question: {e}")
        return jsonify({"error": "Internal server error"}), 500

# Run the Flask app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
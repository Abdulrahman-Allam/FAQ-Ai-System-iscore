import csv
from transformers import AutoTokenizer, AutoModelForSequenceClassification
import torch
import torch.nn.functional as F
from pyarabic.araby import strip_tashkeel
from flask import Flask, request, jsonify
from flask_cors import CORS  # To handle CORS for React frontend

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
    device = "cuda" if torch.cuda.is_available() else "cpu"  # Use GPU if available
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
                relevance_scores = logits.squeeze(-1).tolist()
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
CORS(app)  # Enable CORS for all routes

@app.route('/ask', methods=['POST'])
def ask_question():
    """Endpoint to handle user questions."""
    try:
        # Get the JSON payload from the request
        data = request.get_json()
        question = data.get('question')

        if not question:
            return jsonify({"error": "No question provided"}), 400

        # Retrieve relevant passages
        results = retrieve_passage(question, top_k=5, max_passages=1000)

        # Format the results for the frontend
        formatted_results = [result["text"] for result in results]

        return jsonify({"answers": formatted_results})  # Return all answers as a list

    except Exception as e:
        print(f"Error in /ask endpoint: {e}")
        return jsonify({"error": "An error occurred while processing your question."}), 500 

# Run the Flask app
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
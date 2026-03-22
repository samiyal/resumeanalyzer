from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import os

app = Flask(__name__)

# Enable CORS (VERY IMPORTANT for frontend)
CORS(app, resources={r"/*": {"origins": "*"}})

# OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Home route
@app.route('/')
def home():
    return "Resume Analyzer API Running 🚀"

# Analyze route
@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.get_json()

        if not data or "text" not in data:
            return jsonify({"error": "No resume text provided"}), 400

        resume_text = data["text"]

        # Call OpenAI
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a professional resume expert. Analyze and improve resumes."},
                {"role": "user", "content": f"Analyze this resume and give detailed improvements:\n{resume_text}"}
            ]
        )

        result = response.choices[0].message.content

        return jsonify({"result": result})

    except Exception as e:
        # Return error instead of crashing
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
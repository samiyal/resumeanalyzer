from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import os

app = Flask(__name__)

# Enable CORS for frontend
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

        resume_text = data.get("resume")
        jd_text = data.get("job_description")

        if not resume_text or not jd_text:
            return jsonify({"error": "Both resume and job description are required"}), 400

        # Prepare prompt for ATS + suggestions
        prompt = f"""
You are an ATS and resume expert. 
Compare the following resume to this job description.
1. Give an ATS Score (0-100)
2. Provide improvement suggestions

Resume:
{resume_text}

Job Description:
{jd_text}
"""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}]
        )

        result = response.choices[0].message.content

        return jsonify({"result": result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True)
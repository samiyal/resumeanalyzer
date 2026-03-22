from flask_cors import CORS
from flask import Flask, request, jsonify
import os
from openai import OpenAI

app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route('/')
def home():
    return "Resume Analyzer API Running 🚀"

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    resume_text = data.get("text")

    if not resume_text:
        return jsonify({"error": "No resume text provided"}), 400

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a resume expert."},
            {"role": "user", "content": f"Analyze this resume and give improvements:\n{resume_text}"}
        ]
    )

    result = response.choices[0].message.content

    return jsonify({"result": result})

if __name__ == '__main__':
    app.run(debug=True)
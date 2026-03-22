from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import os
from werkzeug.utils import secure_filename
import io
from docx import Document
import PyPDF2

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text(file):
    ext = file.filename.rsplit('.', 1)[1].lower()
    if ext == 'pdf':
        reader = PyPDF2.PdfReader(file)
        text = ''
        for page in reader.pages:
            text += page.extract_text() + '\n'
        return text
    elif ext == 'docx':
        doc = Document(file)
        return '\n'.join([p.text for p in doc.paragraphs])
    elif ext == 'txt':
        return file.read().decode('utf-8')
    else:
        return ''

@app.route('/')
def home():
    return "Resume Analyzer API Running 🚀"

@app.route('/analyze', methods=['POST'])
def analyze():
    try:
        data = request.form
        resume_text = data.get("resume", "")
        jd_text = data.get("job_description", "")

        # Handle uploaded files
        if 'resume_file' in request.files:
            file = request.files['resume_file']
            if file and allowed_file(file.filename):
                resume_text += '\n' + extract_text(file)

        if 'jd_file' in request.files:
            file = request.files['jd_file']
            if file and allowed_file(file.filename):
                jd_text += '\n' + extract_text(file)

        if not resume_text.strip() or not jd_text.strip():
            return jsonify({"error": "Both resume and job description are required"}), 400

        prompt = f"""
You are an ATS system and resume expert.
Compare the following resume to the job description.
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
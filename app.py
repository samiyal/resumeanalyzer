from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import os
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from werkzeug.utils import secure_filename
from docx import Document
import PyPDF2

app = Flask(__name__)
CORS(app)
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "supersecretkey")
jwt = JWTManager(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Allowed file extensions
ALLOWED_EXTENSIONS = {'pdf', 'docx', 'txt'}

# --- Database ---
conn = sqlite3.connect('users.db', check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS users
             (id INTEGER PRIMARY KEY, email TEXT UNIQUE, password TEXT, scans INTEGER DEFAULT 0, paid INTEGER DEFAULT 0)''')
conn.commit()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text(file):
    ext = file.filename.rsplit('.',1)[1].lower()
    if ext == 'pdf':
        reader = PyPDF2.PdfReader(file)
        return "\n".join([page.extract_text() or "" for page in reader.pages])
    elif ext == 'docx':
        doc = Document(file)
        return "\n".join([p.text for p in doc.paragraphs])
    elif ext == 'txt':
        return file.read().decode('utf-8')
    return ""

# --- Routes ---
@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = data.get("email")
    password = generate_password_hash(data.get("password"))
    try:
        c.execute("INSERT INTO users (email, password) VALUES (?,?)", (email, password))
        conn.commit()
        return jsonify({"msg":"User created"}), 201
    except:
        return jsonify({"msg":"Email already exists"}), 400

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    c.execute("SELECT * FROM users WHERE email=?", (data.get("email"),))
    user = c.fetchone()
    if user and check_password_hash(user[2], data.get("password")):
        token = create_access_token(identity=user[1])
        return jsonify({"token": token})
    return jsonify({"msg":"Invalid credentials"}), 401

@app.route('/')
def home():
    return "Resume Analyzer SaaS API Running 🚀"

@app.route('/analyze', methods=['POST'])
@jwt_required()
def analyze():
    user_email = get_jwt_identity()
    c.execute("SELECT scans, paid FROM users WHERE email=?", (user_email,))
    user = c.fetchone()
    scans, paid = user[0], user[1]

    if not paid and scans >= 1:
        return jsonify({"error":"Free scan limit reached. Upgrade to paid."}), 403

    data = request.form
    resume_text = data.get("resume", "")
    jd_text = data.get("job_description", "")

    # Uploaded files
    if 'resume_file' in request.files:
        file = request.files['resume_file']
        if file and allowed_file(file.filename):
            resume_text += "\n" + extract_text(file)
    if 'jd_file' in request.files:
        file = request.files['jd_file']
        if file and allowed_file(file.filename):
            jd_text += "\n" + extract_text(file)

    if not resume_text.strip() or not jd_text.strip():
        return jsonify({"error":"Both resume and job description are required"}), 400

    # Prompt for OpenAI
    prompt = f"""
You are an ATS and resume expert.
Compare the following resume to the job description.
1. Give an ATS Score (0-100)
2. Provide improvement suggestions

Resume:
{resume_text}

Job Description:
{jd_text}
"""

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role":"user","content":prompt}]
        )
        result = response.choices[0].message.content

        # Increment scan count
        c.execute("UPDATE users SET scans=scans+1 WHERE email=?", (user_email,))
        conn.commit()

        return jsonify({"result": result})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
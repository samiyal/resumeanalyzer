from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename
from openai import OpenAI
import os
import sqlite3
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity

# --- Config ---
app = Flask(__name__)
CORS(app)
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "super-secret")  # Change in production
jwt = JWTManager(app)

UPLOAD_FOLDER = "uploads"
PAYMENT_FOLDER = "payments"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PAYMENT_FOLDER, exist_ok=True)

# --- OpenAI Client ---
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# --- Database ---
conn = sqlite3.connect("users.db", check_same_thread=False)
c = conn.cursor()
c.execute("""CREATE TABLE IF NOT EXISTS users(
             id INTEGER PRIMARY KEY AUTOINCREMENT,
             email TEXT UNIQUE,
             password TEXT,
             paid INTEGER DEFAULT 0,
             scans INTEGER DEFAULT 0)""")
conn.commit()

# --- Routes ---

@app.route('/')
def home():
    return "Resume Analyzer API Running 🚀"

# Signup
@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    try:
        c.execute("INSERT INTO users(email,password) VALUES (?,?)",(email,password))
        conn.commit()
        return jsonify({"msg":"Signup successful"})
    except:
        return jsonify({"error":"Email already exists"}),400

# Login
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")
    c.execute("SELECT * FROM users WHERE email=? AND password=?",(email,password))
    user = c.fetchone()
    if not user:
        return jsonify({"error":"Invalid credentials"}),401
    token = create_access_token(identity=email)
    return jsonify({"token":token,"paid":user[3],"scans":user[4]})

# Analyze Resume
@app.route('/analyze', methods=['POST'])
@jwt_required()
def analyze():
    try:
        user_email = get_jwt_identity()
        c.execute("SELECT scans, paid FROM users WHERE email=?",(user_email,))
        scans, paid = c.fetchone()
        if scans >=1 and paid==0:
            return jsonify({"error":"Free scan limit reached. Upgrade to paid."}),403

        resume_text = request.form.get("resume_text","")
        jd_text = request.form.get("jd_text","")

        resume_file = request.files.get("resume_file",None)
        if resume_file:
            filename = secure_filename(resume_file.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            resume_file.save(path)
            with open(path,"r",encoding="utf-8",errors="ignore") as f:
                resume_text = f.read()

        if not resume_text or not jd_text:
            return jsonify({"error":"Resume and Job Description required"}),400

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
            messages=[{"role":"user","content":prompt}]
        )
        result = response.choices[0].message.content

        # Increment scans
        c.execute("UPDATE users SET scans=scans+1 WHERE email=?",(user_email,))
        conn.commit()

        return jsonify({"result":result})

    except Exception as e:
        return jsonify({"error":str(e)}),500

# Manual UPI Payment
@app.route('/manual-payment', methods=['POST'])
@jwt_required()
def manual_payment():
    user_email = get_jwt_identity()
    if 'screenshot' not in request.files and 'txn_id' not in request.form:
        return jsonify({"error":"Upload screenshot or enter transaction ID"}),400

    txn_id = request.form.get('txn_id','')
    screenshot = request.files.get('screenshot',None)
    if screenshot:
        filename = secure_filename(screenshot.filename)
        screenshot.save(os.path.join(PAYMENT_FOLDER, filename))

    # Mark user as paid
    c.execute("UPDATE users SET paid=1 WHERE email=?",(user_email,))
    conn.commit()
    return jsonify({"msg":"Payment submitted. You are now upgraded!"})

if __name__ == '__main__':
    app.run(debug=True)
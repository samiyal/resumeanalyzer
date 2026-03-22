from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from openai import OpenAI
import os
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "secret")
jwt = JWTManager(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route('/')
def home():
    return "🚀 Resume Analyzer API Running"

# SIGNUP
@app.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Missing fields"}), 400

    existing = supabase.table("users").select("*").eq("email", email).execute()
    if existing.data:
        return jsonify({"error": "User already exists"}), 400

    supabase.table("users").insert({
        "email": email,
        "password": password,
        "paid": False,
        "scans": 0
    }).execute()

    return jsonify({"msg": "Signup successful"})

# LOGIN
@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    res = supabase.table("users").select("*").eq("email", email).eq("password", password).execute()

    if not res.data:
        return jsonify({"error": "Invalid credentials"}), 401

    token = create_access_token(identity=email)

    return jsonify({"token": token})

# ANALYZE
@app.route('/analyze', methods=['POST'])
@jwt_required()
def analyze():
    try:
        user_email = get_jwt_identity()

        res = supabase.table("users").select("*").eq("email", user_email).execute()
        user = res.data[0]

        if user["scans"] >= 1 and not user["paid"]:
            return jsonify({"error": "Free limit reached. Upgrade required."}), 403

        resume_text = request.form.get("resume_text", "")
        jd_text = request.form.get("jd_text", "")

        # Resume file
        resume_file = request.files.get("resume_file")
        if resume_file:
            path = os.path.join(UPLOAD_FOLDER, secure_filename(resume_file.filename))
            resume_file.save(path)
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                resume_text = f.read()

        # JD file
        jd_file = request.files.get("jd_file")
        if jd_file:
            path = os.path.join(UPLOAD_FOLDER, secure_filename(jd_file.filename))
            jd_file.save(path)
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                jd_text = f.read()

        if not resume_text or not jd_text:
            return jsonify({"error": "Resume and Job Description required"}), 400

        prompt = f"""
You are an ATS expert.

1. Give ATS score (0-100)
2. Give improvement suggestions
3. Missing keywords

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

        # Update scans
        supabase.table("users").update({
            "scans": user["scans"] + 1
        }).eq("email", user_email).execute()

        return jsonify({"result": result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# PAYMENT
@app.route('/manual-payment', methods=['POST'])
@jwt_required()
def payment():
    user_email = get_jwt_identity()

    supabase.table("users").update({
        "paid": True
    }).eq("email", user_email).execute()

    return jsonify({"msg": "✅ Payment successful. Unlimited access granted!"})

if __name__ == "__main__":
    app.run(debug=True)
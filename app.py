from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import os
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)
from supabase import create_client
import PyPDF2

app = Flask(__name__)
CORS(app)

# ---------------- CONFIG ----------------
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
jwt = JWTManager(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------- SUPABASE ----------------
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

# ---------------- HELPERS ----------------
def extract_text_from_pdf(file):
    try:
        reader = PyPDF2.PdfReader(file)
        text = ""
        for page in reader.pages:
            text += page.extract_text() or ""
        return text
    except:
        return ""

def extract_text(file):
    if file.filename.endswith(".pdf"):
        return extract_text_from_pdf(file)
    elif file.filename.endswith(".txt"):
        return file.read().decode("utf-8")
    return ""

# ---------------- ROUTES ----------------

@app.route("/")
def home():
    return "🚀 Resume Analyzer API Running"

# -------- SIGNUP --------
@app.route("/signup", methods=["POST"])
def signup():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"error": "Email & password required"}), 400

    # check user exists
    existing = supabase.table("users").select("*").eq("email", email).execute()

    if existing.data:
        return jsonify({"error": "User already exists"}), 400

    # insert user
    supabase.table("users").insert({
        "email": email,
        "password": password,
        "scans": 1,
        "paid": False
    }).execute()

    return jsonify({"msg": "Signup successful"})

# -------- LOGIN --------
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    user = supabase.table("users").select("*").eq("email", email).execute()

    if not user.data:
        return jsonify({"error": "User not found"}), 404

    user = user.data[0]

    if user["password"] != password:
        return jsonify({"error": "Invalid password"}), 401

    token = create_access_token(identity=email)

    return jsonify({"token": token})

# -------- ANALYZE --------
@app.route("/analyze", methods=["POST"])
@jwt_required()
def analyze():
    try:
        email = get_jwt_identity()

        user_res = supabase.table("users").select("*").eq("email", email).execute()
        if not user_res.data:
            return jsonify({"error": "User not found"}), 404

        user = user_res.data[0]

        # -------- FREE LIMIT --------
        if not user["paid"] and user["scans"] <= 0:
            return jsonify({"error": "Free limit reached"}), 403

        # -------- INPUT --------
        resume_text = request.form.get("resume_text", "")
        jd_text = request.form.get("jd_text", "")

        resume_file = request.files.get("resume_file")
        jd_file = request.files.get("jd_file")

        if resume_file:
            resume_text += extract_text(resume_file)

        if jd_file:
            jd_text += extract_text(jd_file)

        if not resume_text.strip() or not jd_text.strip():
            return jsonify({"error": "Provide Resume & JD"}), 400

        # -------- LIMIT SIZE --------
        resume_text = resume_text[:2000]
        jd_text = jd_text[:1500]

        # -------- PROMPT --------
        prompt = f"""
Give:
1. ATS Score (0-100)
2. Missing Keywords
3. Improvements

Resume:
{resume_text}

Job:
{jd_text}
"""

        # -------- OPENAI --------
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300
            timeout=15        # 🔥 VERY IMPORTANT
        )

        result = response.choices[0].message.content

        # -------- UPDATE SCANS --------
        if not user["paid"]:
            supabase.table("users").update({
                "scans": user["scans"] - 1
            }).eq("email", email).execute()

        return jsonify({"result": result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500

# -------- UPGRADE --------
@app.route("/upgrade", methods=["POST"])
@jwt_required()
def upgrade():
    email = get_jwt_identity()

    supabase.table("users").update({
        "paid": True,
        "scans": 999
    }).eq("email", email).execute()

    return jsonify({"msg": "Upgraded successfully 🎉"})


if __name__ == "__main__":
    app.run(debug=True)
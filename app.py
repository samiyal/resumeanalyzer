from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from openai import OpenAI
import os
from flask_jwt_extended import (
    JWTManager,
    create_access_token,
    jwt_required,
    get_jwt_identity
)
from supabase import create_client, Client

# ------------------ APP SETUP ------------------

app = Flask(__name__)
CORS(app)

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "super-secret-key")
jwt = JWTManager(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ------------------ OPENAI ------------------

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ------------------ SUPABASE ------------------

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ------------------ ROUTES ------------------

@app.route("/")
def home():
    return "🚀 Resume Analyzer API Running (Supabase Connected)"

# ------------------ SIGNUP ------------------

@app.route("/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json()

        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({"error": "Email and password required"}), 400

        # Check existing
        existing = supabase.table("users").select("*").eq("email", email).execute()

        if existing.data:
            return jsonify({"error": "User already exists"}), 400

        # Insert user
        supabase.table("users").insert({
            "email": email,
            "password": password,
            "paid": False,
            "scans": 0
        }).execute()

        return jsonify({"msg": "Signup successful"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ------------------ LOGIN ------------------

@app.route("/login", methods=["POST"])
def login():
    try:
        data = request.get_json()

        email = data.get("email")
        password = data.get("password")

        res = supabase.table("users") \
            .select("*") \
            .eq("email", email) \
            .eq("password", password) \
            .execute()

        if not res.data:
            return jsonify({"error": "Invalid credentials"}), 401

        token = create_access_token(identity=email)

        return jsonify({
            "token": token,
            "msg": "Login successful"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ------------------ ANALYZE ------------------

@app.route("/analyze", methods=["POST"])
@jwt_required()
def analyze():
    try:
        user_email = get_jwt_identity()

        # Get user
        res = supabase.table("users") \
            .select("*") \
            .eq("email", user_email) \
            .execute()

        if not res.data:
            return jsonify({"error": "User not found"}), 404

        user = res.data[0]

        # Free limit check
        if user["scans"] >= 1 and not user["paid"]:
            return jsonify({
                "error": "Free limit reached. Please upgrade."
            }), 403

        # Get inputs
        resume_text = request.form.get("resume_text", "")
        jd_text = request.form.get("jd_text", "")

        # -------- RESUME FILE --------
        resume_file = request.files.get("resume_file")
        if resume_file:
            filename = secure_filename(resume_file.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            resume_file.save(path)

            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                resume_text = f.read()

        # -------- JD FILE --------
        jd_file = request.files.get("jd_file")
        if jd_file:
            filename = secure_filename(jd_file.filename)
            path = os.path.join(UPLOAD_FOLDER, filename)
            jd_file.save(path)

            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                jd_text = f.read()

        if not resume_text or not jd_text:
            return jsonify({
                "error": "Resume and Job Description are required"
            }), 400

        # -------- AI PROMPT --------
        prompt = f"""
You are an ATS (Applicant Tracking System) expert.

1. Give ATS Score (0-100)
2. Provide improvement suggestions
3. Highlight missing keywords

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


# ------------------ PAYMENT ------------------

@app.route("/manual-payment", methods=["POST"])
@jwt_required()
def manual_payment():
    try:
        user_email = get_jwt_identity()

        # Upgrade user
        supabase.table("users").update({
            "paid": True
        }).eq("email", user_email).execute()

        return jsonify({
            "msg": "✅ Payment received. Unlimited access activated!"
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ------------------ RUN ------------------

if __name__ == "__main__":
    app.run(debug=True)
from flask import Flask, request, jsonify
from flask_cors import CORS
from werkzeug.utils import secure_filename
from openai import OpenAI
import os
from flask_jwt_extended import JWTManager, create_access_token, jwt_required, get_jwt_identity
from supabase import create_client, Client

app = Flask(__name__)
CORS(app)

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "secret123")
jwt = JWTManager(app)

UPLOAD_FOLDER = "uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# OpenAI
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

@app.route("/")
def home():
    return "🚀 API Running"

# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["POST"])
def signup():
    try:
        data = request.get_json()

        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            return jsonify({"error": "Email & Password required"}), 400

        # check existing
        existing = supabase.table("users").select("*").eq("email", email).execute()
        if existing.data:
            return jsonify({"error": "User already exists"}), 400

        # insert (NO paid/scans from user)
        supabase.table("users").insert({
            "email": email,
            "password": password,
            "paid": False,
            "scans": 0
        }).execute()

        return jsonify({"msg": "Signup successful"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------- LOGIN ----------------
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

        return jsonify({"token": token})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------- ANALYZE ----------------
@app.route("/analyze", methods=["POST"])
@jwt_required()
def analyze():
    try:
        user_email = get_jwt_identity()

        # fetch user
        res = supabase.table("users").select("*").eq("email", user_email).execute()
        user = res.data[0]

        # free limit
        if user["scans"] >= 1 and not user["paid"]:
            return jsonify({"error": "Free limit reached. Upgrade required."}), 403

        resume_text = request.form.get("resume_text", "")
        jd_text = request.form.get("jd_text", "")

        # resume file
        resume_file = request.files.get("resume_file")
        if resume_file:
            path = os.path.join(UPLOAD_FOLDER, secure_filename(resume_file.filename))
            resume_file.save(path)
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                resume_text = f.read()

        # jd file
        jd_file = request.files.get("jd_file")
        if jd_file:
            path = os.path.join(UPLOAD_FOLDER, secure_filename(jd_file.filename))
            jd_file.save(path)
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                jd_text = f.read()

        if not resume_text or not jd_text:
            return jsonify({"error": "Resume & JD required"}), 400

        prompt = f"""
Give ATS score (0-100), improvements, and missing keywords.

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

        # update scan count
        supabase.table("users").update({
            "scans": user["scans"] + 1
        }).eq("email", user_email).execute()

        return jsonify({"result": result})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ---------------- PAYMENT ----------------
@app.route("/manual-payment", methods=["POST"])
@jwt_required()
def payment():
    try:
        user_email = get_jwt_identity()

        supabase.table("users").update({
            "paid": True
        }).eq("email", user_email).execute()

        return jsonify({"msg": "Upgraded successfully"})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(debug=True)
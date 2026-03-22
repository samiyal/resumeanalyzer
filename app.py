import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity
)
from supabase import create_client
from openai import OpenAI

app = Flask(__name__)
CORS(app)

# ================= CONFIG =================
app.config["JWT_SECRET_KEY"] = os.getenv(
    "JWT_SECRET_KEY",
    "super_long_secure_key_1234567890_abcdef_2026"
)

jwt = JWTManager(app)

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ================= ROUTES =================

@app.route("/")
def home():
    return {"status": "API running 🚀"}

# -------- SIGNUP --------
@app.route("/signup", methods=["POST"])
def signup():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    if not email or not password:
        return jsonify({"msg": "Missing fields"}), 400

    try:
        supabase.table("users").insert({
            "email": email,
            "password": password
        }).execute()

        return jsonify({"msg": "User created"}), 200

    except Exception as e:
        return jsonify({"msg": str(e)}), 500

# -------- LOGIN --------
@app.route("/login", methods=["POST"])
def login():
    data = request.json
    email = data.get("email")
    password = data.get("password")

    res = supabase.table("users") \
        .select("*") \
        .eq("email", email) \
        .eq("password", password) \
        .execute()

    if not res.data:
        return jsonify({"msg": "Invalid credentials"}), 401

    token = create_access_token(identity=email)
    return jsonify({"token": token})

# -------- ANALYZE --------
@app.route("/analyze", methods=["POST"])
@jwt_required()
def analyze():
    try:
        resume_text = request.form.get("resume_text", "")
        jd_text = request.form.get("jd_text", "")

        # FILE SUPPORT
        resume_file = request.files.get("resume_file")
        jd_file = request.files.get("jd_file")

        if resume_file:
            resume_text = resume_file.read().decode("utf-8", errors="ignore")

        if jd_file:
            jd_text = jd_file.read().decode("utf-8", errors="ignore")

        if not resume_text or not jd_text:
            return jsonify({"msg": "Provide Resume & JD"}), 400

        # LIMIT TEXT (IMPORTANT FOR SPEED)
        resume_text = resume_text[:2000]
        jd_text = jd_text[:1500]

        prompt = f"""
        Compare Resume and Job Description.

        Resume:
        {resume_text}

        Job Description:
        {jd_text}

        Give:
        1. Match %
        2. Missing skills
        3. Suggestions
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            timeout=15
        )

        result = response.choices[0].message.content
        return jsonify({"result": result})

    except Exception as e:
        return jsonify({"msg": str(e)}), 500


# ================= RUN =================
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
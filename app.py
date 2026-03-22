from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import os
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)

app = Flask(__name__)

# ---------------- CONFIG ----------------
CORS(app)

# ✅ VERY IMPORTANT (FIXED)
app.config["JWT_SECRET_KEY"] = "my_ultra_secure_resume_analyzer_secret_key_2026_very_long"

jwt = JWTManager(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -------- TEMP USER STORE (Replace with DB later) --------
users = {}

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

    if email in users:
        return jsonify({"error": "User already exists"}), 400

    users[email] = {
        "password": password,
        "scans": 1,     # free user → 1 scan
        "paid": False
    }

    return jsonify({"msg": "Signup successful"})


# -------- LOGIN --------
@app.route("/login", methods=["POST"])
def login():
    data = request.get_json()

    email = data.get("email")
    password = data.get("password")

    user = users.get(email)

    if not user or user["password"] != password:
        return jsonify({"error": "Invalid credentials"}), 401

    token = create_access_token(identity=email)

    return jsonify({"token": token})


# -------- ANALYZE --------
@app.route("/analyze", methods=["POST"])
@jwt_required()
def analyze():
    try:
        email = get_jwt_identity()
        user = users.get(email)

        if not user:
            return jsonify({"error": "User not found"}), 404

        # -------- FREE LIMIT --------
        if not user["paid"] and user["scans"] <= 0:
            return jsonify({"error": "Free limit reached. Upgrade required."}), 403

        # -------- INPUT --------
        resume_text = request.form.get("resume_text", "")
        jd_text = request.form.get("jd_text", "")

        if not resume_text or not jd_text:
            return jsonify({"error": "Resume and JD required"}), 400

        # ✅ LIMIT SIZE (PREVENT CRASH)
        resume_text = resume_text[:3000]
        jd_text = jd_text[:2000]

        # -------- PROMPT --------
        prompt = f"""
You are an ATS system.

1. Give ATS Score (0-100)
2. Missing Keywords
3. Improvements

Resume:
{resume_text}

Job Description:
{jd_text}
"""

        # -------- OPENAI CALL --------
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500
            )

            result = response.choices[0].message.content

        except Exception as e:
            return jsonify({"error": "AI timeout or server busy"}), 500

        # -------- DECREMENT SCAN --------
        if not user["paid"]:
            user["scans"] -= 1

        return jsonify({
            "result": result,
            "scans_left": user["scans"]
        })

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# -------- UPGRADE --------
@app.route("/upgrade", methods=["POST"])
@jwt_required()
def upgrade():
    email = get_jwt_identity()
    user = users.get(email)

    if not user:
        return jsonify({"error": "User not found"}), 404

    user["paid"] = True
    user["scans"] = 999

    return jsonify({"msg": "Upgraded successfully 🎉"})


# ---------------- RUN ----------------
if __name__ == "__main__":
    app.run(debug=True)
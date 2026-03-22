import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI

app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

@app.route("/")
def home():
    return {"status": "AI Resume Analyzer running 🚀"}


@app.route("/analyze", methods=["POST"])
def analyze():
    try:
        resume_text = request.form.get("resume_text", "")
        jd_text = request.form.get("jd_text", "")

        resume_file = request.files.get("resume_file")
        jd_file = request.files.get("jd_file")

        if resume_file:
            resume_text = resume_file.read().decode("utf-8", errors="ignore")

        if jd_file:
            jd_text = jd_file.read().decode("utf-8", errors="ignore")

        if not resume_text or not jd_text:
            return jsonify({"msg": "Provide Resume & Job Description"}), 400

        # SPEED OPTIMIZATION
        resume_text = resume_text[:2000]
        jd_text = jd_text[:1500]

        prompt = f"""
        Compare Resume and Job Description.

        Resume:
        {resume_text}

        Job Description:
        {jd_text}

        Give:
        1. Match Percentage
        2. Missing Skills
        3. Suggestions to improve
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


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
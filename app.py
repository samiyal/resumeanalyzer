import os
from flask import Flask, request, jsonify
from flask_cors import CORS
from openai import OpenAI
import fitz  # PyMuPDF
from docx import Document

app = Flask(__name__)
CORS(app)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# -------- FILE PARSER --------
def extract_text(file):
    filename = file.filename.lower()

    if filename.endswith(".pdf"):
        doc = fitz.open(stream=file.read(), filetype="pdf")
        text = ""
        for page in doc:
            text += page.get_text()
        return text

    elif filename.endswith(".docx"):
        doc = Document(file)
        return "\n".join([p.text for p in doc.paragraphs])

    else:
        return file.read().decode("utf-8", errors="ignore")


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
            resume_text = extract_text(resume_file)

        if jd_file:
            jd_text = extract_text(jd_file)

        if not resume_text or not jd_text:
            return jsonify({"msg": "Provide Resume & Job Description"}), 400

        # LIMIT SIZE (IMPORTANT)
        resume_text = resume_text[:3000]
        jd_text = jd_text[:2000]

        prompt = f"""
        You are an ATS system.

        Compare resume with job description.

        Resume:
        {resume_text}

        Job Description:
        {jd_text}

        Give output in this format:

        ATS Score: (0-100%)

        Missing Keywords:
        - list

        Matching Skills:
        - list

        Suggestions:
        - bullet points
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=400,
            timeout=20
        )

        result = response.choices[0].message.content

        return jsonify({"result": result})

    except Exception as e:
        return jsonify({"msg": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

    from flask import send_file
import uuid

# -------- IMPROVE RESUME --------
@app.route("/improve_resume", methods=["POST"])
def improve_resume():
    try:
        resume_text = request.form.get("resume_text", "")
        resume_file = request.files.get("resume_file")

        if resume_file:
            resume_text = extract_text(resume_file)

        if not resume_text:
            return jsonify({"msg": "Provide resume"}), 400

        resume_text = resume_text[:3000]

        prompt = f"""
        Improve this resume professionally for ATS optimization.

        Resume:
        {resume_text}

        Make it:
        - Better wording
        - Strong bullet points
        - ATS friendly keywords
        - Clean formatting

        Return ONLY improved resume text.
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=600,
            timeout=20
        )

        improved_text = response.choices[0].message.content

        # -------- CREATE DOCX --------
        from docx import Document

        doc = Document()
        for line in improved_text.split("\n"):
            doc.add_paragraph(line)

        filename = f"improved_resume_{uuid.uuid4().hex}.docx"
        filepath = f"/tmp/{filename}"
        doc.save(filepath)

        return send_file(filepath, as_attachment=True)

    except Exception as e:
        return jsonify({"msg": str(e)}), 500
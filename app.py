import os
from flask import Flask, request, jsonify
from flask import send_from_directory
from flask_cors import CORS
from openai import OpenAI
import fitz  # PyMuPDF
from docx import Document


app = Flask(__name__, static_folder="static", static_url_path="")
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
def serve_ui():
    return send_from_directory("static", "index.html")

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

        Improved Resume:
        [Provide an improved version of the resume that incorporates the job description keywords and addresses the suggestions. Keep it concise and professional.]
        """

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=800,  # Increased to accommodate improved resume
            timeout=20
        )

        result = response.choices[0].message.content

        return jsonify({"result": result})

    except Exception as e:
        return jsonify({"msg": str(e)}), 500


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
import PyPDF2
import re
from datetime import datetime
import json
from google import genai
from dotenv import load_dotenv

client = genai.Client()

load_dotenv()


async def parse_resume(file_path: str):
    """Parse resume PDF and extract structured information using spaCy"""
    try:
        text = extract_text_from_pdf(file_path)
        clean_text = clean_resume_text(text)
        result = await get_info_from_resume(clean_text)
        return result

    except Exception as e:
        raise RuntimeError(f"Failed to parse resume: {str(e)}")


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF with improved line handling"""
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        text = ""
        for page in reader.pages:
            page_text = page.extract_text()
            if page_text:
                # Preserve line breaks for better section detection
                text += page_text + "\n"
        return text


def clean_resume_text(text: str) -> str:
    """Clean and normalize resume text while preserving structure"""
    # Normalize whitespace but keep line breaks
    text = re.sub(r"[ \t]+", " ", text)
    # Normalize bullet points
    text = re.sub(r"[•*\-]\s*", " • ", text)
    # Remove extra empty lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def get_info_from_resume(text: str):
    prompt = f"""
You are a strict JSON extractor.

Your task is to extract the following information from a resume and return it in **this exact JSON format**.

DO NOT add explanations or additional text. ONLY return valid JSON.

Here is the expected format:

{{
  "Full Name": "John Doe",
  "Email": "john.doe@example.com",
  "Phone Number": "+1 123-456-7890",
  "LinkedIn Profile": "https://linkedin.com/in/johndoe",
  "Skills": ["Python", "React", "Machine Learning", "SQL"],
  "Education": [
    {{
      "Degree": "B.Tech in Computer Science",
      "University": "IIT Delhi",
      "Year": "2021"
    }}
  ],
  "Experience": [
    {{
      "Company": "TCS",
      "Role": "Software Developer",
      "Duration": "Jan 2022 - Present",
      "Description": "Worked on backend APIs in Python and Node.js."   #summary in 1 or 2 line
    }}
  ],
  "Certifications": ["AWS Certified Developer"],
  "Projects": [
    {{
      "Name": "Resume Parser",
      "Description": "Built an intelligent resume parser using Gemini API."   #summary in 1 or 2 line
    }}
  ]
}}

Now extract the data from the following resume and match this format:

\"\"\"
{text}
\"\"\"
"""
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    cleaned_response =  clean_gemini_response(response.text)
    return cleaned_response


def clean_gemini_response(raw_result):
    # Step 1: Remove markdown code fences ```json ... ```
    cleaned = re.sub(r"^```json\n|```$", "", raw_result.strip())

    # Step 2: Unescape any escaped characters
    try:
        parsed_json = json.loads(cleaned)
        return parsed_json
    except json.JSONDecodeError:
        # Fallback: Sometimes it's double-encoded — try unescaping
        cleaned = cleaned.encode('utf-8').decode('unicode_escape')
        parsed_json = json.loads(cleaned)
        return parsed_json

async def extract_job_data(job_data:str):
    prompt = f"""
You are a helpful assistant for a hiring platform. An employer has provided a short, free-text job description. 

Your task is to extract all relevant details from that description and return the data in this **exact structured JSON format**.

Return ONLY a valid JSON object. DO NOT include explanations or wrap the result in markdown (like ```json).

Use the following format:

{{
  "title": "Software Engineer",
  "description": "...",  # summary of responsibilities
  "requirements": ["Bachelor's degree in CS", "3+ years experience", ...],
  "responsibilities": ["Build scalable APIs", "Collaborate with team", ...],
  "employment_type": "full_time",  # one of: full_time, part_time, contract, internship
  "salary": {{
    "min": 80000, # 0 for none
    "max": 120000,
    "currency": "USD",
    "is_public": true
  }},
  "location": {{
    "city": "San Francisco", # "" for nothing
    "state": "CA", # "" for nothing
    "country": "USA",# "" for nothing
    "remote": false
  }},
  "skills_required": ["Python", "FastAPI", "MongoDB"],
  "benefits": ["Health Insurance", "401k", "Remote Work"],
  "is_active": true,
}}

Here is the employer’s job description:

\"\"\"
{job_data}
\"\"\"

Now extract and return the information as a JSON object using the format above.
"""
    response = client.models.generate_content(model="gemini-2.5-flash",contents=prompt)
    return clean_gemini_response(response.text)
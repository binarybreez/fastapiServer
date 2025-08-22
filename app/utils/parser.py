import PyPDF2
import re
from datetime import datetime
import json
from google import genai
from dotenv import load_dotenv

client = genai.Client()
load_dotenv()


async def parse_resume(file_path: str):
    """Parse resume PDF and extract structured information using Gemini AI"""
    try:
        text = extract_text_from_pdf(file_path)
        clean_text = clean_resume_text(text)
        result = await get_info_from_resume(clean_text)
        return result
    except Exception as e:
        raise RuntimeError(f"Failed to parse resume: {str(e)}")


def extract_text_from_pdf(file_path: str) -> str:
    """Extract text from PDF with improved line handling (works on any PyPDF2 version)"""
    with open(file_path, "rb") as f:
        # Try PdfReader (new), else fallback to PdfFileReader (old)
        reader = getattr(PyPDF2, "PdfReader", None)
        if reader:
            reader = reader(f)
            text = ""
            for page in reader.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
            return text
        else:
            reader = PyPDF2.PdfFileReader(f)
            text = ""
            for i in range(reader.getNumPages()):
                page_text = reader.getPage(i).extractText()
                if page_text:
                    text += page_text + "\n"
            return text


def clean_resume_text(text: str) -> str:
    """Clean and normalize resume text while preserving structure"""
    # Normalize whitespace but keep line breaks
    text = re.sub(r"[ \t]+", " ", text)
    # Normalize bullet points
    text = re.sub(r"[•*\-]\s*", " • ", text)
    # Remove extra empty lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


async def get_info_from_resume(text: str):
    prompt = f"""
You are a strict JSON extractor for a comprehensive resume parsing system.

Your task is to extract ALL the following information from a resume and return it in **this exact JSON format**.

DO NOT add explanations or additional text. ONLY return valid JSON.

Here is the expected format with ALL required fields:

{{
  "First Name": "John",
  "Last Name": "Doe", 
  "Full Name": "John Doe",
  "Email": "john.doe@example.com",
  "Phone Number": "+1 123-456-7890",
  "Location": "San Francisco, CA",
  "Willing to relocate": false,
  "LinkedIn Profile": "https://linkedin.com/in/johndoe",
  "GitHub Profile": "https://github.com/johndoe",
  "Portfolio URL": "https://johndoe.dev",
  "Technical Skills": ["Python", "React", "Machine Learning", "SQL", "AWS"],
  "Soft Skills": ["Communication", "Leadership", "Problem Solving", "Teamwork"],
  "Skills": ["Python", "React", "Machine Learning", "SQL", "Communication"],
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
      "Description": "Developed backend APIs using Python and Node.js, improved system performance by 30%."
    }}
  ],
  "Certifications": ["AWS Certified Developer", "Google Cloud Professional"],
  "Projects": [
    {{
      "Name": "Resume Parser",
      "Description": "Built an intelligent resume parser using Gemini API with 95% accuracy rate."
    }}
  ]
}}

**IMPORTANT EXTRACTION GUIDELINES:**
1. **Personal Info**: Extract first name, last name separately AND combined full name
2. **Location**: Extract city, state/country if mentioned  
3. **Willing to relocate**: Set to false unless explicitly mentioned as willing/open to relocate
4. **Social Links**: Look for LinkedIn, GitHub, portfolio URLs
5. **Skills**: 
   - Separate technical skills (programming languages, tools, frameworks) 
   - Separate soft skills (communication, leadership, etc.)
   - Also provide combined skills list for backward compatibility
6. **Experience**: Include company, role, duration, and brief description (1-2 lines max)
7. **Education**: Include degree, institution, year
8. **Projects**: Include name and brief description (1-2 lines max)
9. **Certifications**: List all certifications mentioned

If any field is not found, use null for strings/objects or empty array [] for lists.

Now extract the data from the following resume:

\"\"\"
{text}
\"\"\"
"""
    
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    cleaned_response = clean_gemini_response(response.text)
    return cleaned_response


def clean_gemini_response(raw_result):
    """Clean and parse Gemini AI response to valid JSON"""
    # Step 1: Remove markdown code fences ```json ... ```
    cleaned = re.sub(r"^```json\n|```$", "", raw_result.strip(), flags=re.MULTILINE)
    
    # Step 2: Remove any leading/trailing whitespace
    cleaned = cleaned.strip()
    
    try:
        parsed_json = json.loads(cleaned)
        return parsed_json
    except json.JSONDecodeError as e:
        print(f"JSON decode error: {e}")
        print(f"Cleaned response: {cleaned}")
        # Fallback: Sometimes it's double-encoded — try unescaping
        try:
            cleaned = cleaned.encode('utf-8').decode('unicode_escape')
            parsed_json = json.loads(cleaned)
            return parsed_json
        except Exception as fallback_error:
            print(f"Fallback parsing failed: {fallback_error}")
            # Return a default structure if parsing fails completely
            return {
                "Full Name": "Unknown",
                "Email": None,
                "Phone Number": None,
                "Skills": [],
                "Technical Skills": [],
                "Soft Skills": [],
                "Experience": [],
                "Education": [],
                "Certifications": [],
                "Projects": []
            }


async def extract_job_data(job_data: str):
    """Extract structured job posting data from free text description"""
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

Here is the employer's job description:

\"\"\"
{job_data}
\"\"\"

Now extract and return the information as a JSON object using the format above.
"""
    response = client.models.generate_content(model="gemini-2.5-flash", contents=prompt)
    return clean_gemini_response(response.text)
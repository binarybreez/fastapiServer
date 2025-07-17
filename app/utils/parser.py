import PyPDF2
import spacy
from pathlib import Path
from typing import Dict, List
import re
from datetime import datetime

# Load spaCy model once at startup
nlp = spacy.load("en_core_web_sm")

def parse_resume(file_path: str) -> Dict:
    """
    Parse resume PDF from file path and extract structured data
    
    Args:
        file_path: Path to the PDF file (e.g., "public/resumes/user_123.pdf")
        
    Returns:
        Dictionary with parsed data (skills, experience, education, etc.)
    """
    try:
        # 1. Verify file exists
        if not Path(file_path).exists():
            raise FileNotFoundError(f"Resume not found at {file_path}")
            
        # 2. Extract text
        text = extract_text_from_pdf(file_path)
        
        # 3. Process with NLP
        doc = nlp(text)
        
        # 4. Extract structured data
        return {
            "skills": extract_skills(doc),
            "experience": extract_experience(text),
            "education": extract_education(text),
            "raw_text": text[:5000],  # Store first 5000 chars
            "file_path": file_path,
            "parsed_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise RuntimeError(f"Failed to parse resume: {str(e)}")

def extract_text_from_pdf(file_path: str) -> str:
    """Extract and clean text from PDF file"""
    with open(file_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        text = " ".join(
            page.extract_text() or "" 
            for page in reader.pages
        )
        return re.sub(r'\s+', ' ', text).strip()

def extract_skills(doc) -> List[str]:
    """Extract skills using spaCy NER and custom patterns"""
    skills_ruler = nlp.add_pipe("entity_ruler", before="ner")
    skills_ruler.add_patterns([
        {"label": "SKILL", "pattern": [{"LOWER": "python"}]},
        {"label": "SKILL", "pattern": [{"LOWER": "fastapi"}]},
        # Add more skill patterns
    ])
    return list(set(ent.text for ent in doc.ents if ent.label_ == "SKILL"))

def extract_experience(text: str) -> List[Dict]:
    """Extract work experience using regex"""
    experiences = []
    # Simple regex pattern - customize based on your needs
    for match in re.finditer(
        r'(?P<title>[A-Z][a-z]+(?: [A-Z][a-z]+)*)'
        r'(?: at |, )(?P<company>[A-Z][a-zA-Z& ]+)',
        text
    ):
        experiences.append({
            "title": match.group('title'),
            "company": match.group('company')
        })
    return experiences

def extract_education(text: str) -> List[str]:
    """Extract education information"""
    education_keywords = ["university", "college", "institute", "bachelor", "master"]
    return [
        line.strip() for line in text.split('\n')
        if any(keyword in line.lower() for keyword in education_keywords)
    ]
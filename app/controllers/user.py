from typing import List, Optional, Dict, List
from datetime import datetime
from bson import ObjectId
from fastapi import HTTPException
from pydantic import BaseModel, EmailStr, Field
from app.models.user import (
    UserProfile,
    Experience,
    Education,
    SocialLinks,
    Resume,
    Role,
    PyObjectId,
    JobSeekerCreate,
    EmployerCreate
)
import re
from dateutil.parser import parse

class UserCRUD:
    def __init__(self, db_collection):
        self.collection = db_collection

    async def create_user(self, user_data: BaseModel) -> UserProfile:
        """Create a new user profile"""
        existing_user = await self.collection.find_one({"clerk_id": user_data.clerk_id})
        if existing_user:
            raise HTTPException(status_code=400, detail="User already exists")
        
        user_dict = user_data.model_dump()
        user_dict["created_at"] = datetime.utcnow()
        user_dict["updated_at"] = datetime.utcnow()
        
        result = await self.collection.insert_one(user_dict)
        if not result.inserted_id:
            raise HTTPException(status_code=500, detail="Failed to create user")
        
        return await self.get_user_by_id(str(result.inserted_id))

    async def get_user_by_id(self, user_id: PyObjectId) -> UserProfile:
        """Get a user by their ID"""
        user = await self.collection.find_one({"_id": ObjectId(user_id)})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserProfile(**user)

    async def get_user_by_clerk_id(self, clerk_id: str) -> UserProfile:
        """Get a user by their Clerk ID"""
        user = await self.collection.find_one({"clerk_id": clerk_id})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        return UserProfile(**user)

    async def update_user(self, clerk_id: str, update_data: Dict) -> UserProfile:
        """Update a user's profile"""
        update_data["updated_at"] = datetime.utcnow()
        
        result = await self.collection.update_one(
            {"clerk_id": clerk_id},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="User not found or no changes made")
            
        return await self.get_user_by_clerk_id(clerk_id)

    async def delete_user(self, clerk_id: str) -> bool:
        """Delete a user profile"""
        result = await self.collection.delete_one({"clerk_id": clerk_id})
        return result.deleted_count > 0

    # Experience CRUD Operations
    async def add_experience(self, clerk_id: str, experience: Experience) -> UserProfile:
        """Add a new experience to user profile"""
        experience_dict = experience.model_dump()
        experience_dict["_id"] = ObjectId(experience_dict["_id"])
        
        result = await self.collection.update_one(
            {"clerk_id": clerk_id},
            {"$push": {"experience": experience_dict}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
            
        return await self.get_user_by_clerk_id(clerk_id)

    async def update_experience(
        self, 
        clerk_id: str, 
        experience_id: PyObjectId, 
        update_data: Dict
    ) -> UserProfile:
        """Update an existing experience"""
        update_data["updated_at"] = datetime.utcnow()
        
        result = await self.collection.update_one(
            {
                "clerk_id": clerk_id,
                "experience._id": ObjectId(experience_id)
            },
            {"$set": {f"experience.$.{k}": v for k, v in update_data.items()}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Experience not found or no changes made")
            
        return await self.get_user_by_clerk_id(clerk_id)

    async def delete_experience(self, clerk_id: str, experience_id: PyObjectId) -> UserProfile:
        """Remove an experience from user profile"""
        result = await self.collection.update_one(
            {"clerk_id": clerk_id},
            {"$pull": {"experience": {"_id": ObjectId(experience_id)}}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Experience not found")
            
        return await self.get_user_by_clerk_id(clerk_id)

    # Education CRUD Operations
    async def add_education(self, clerk_id: str, education: Education) -> UserProfile:
        """Add a new education to user profile"""
        education_dict = education.model_dump()
        education_dict["_id"] = ObjectId(education_dict["_id"])
        
        result = await self.collection.update_one(
            {"clerk_id": clerk_id},
            {"$push": {"education": education_dict}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="User not found")
            
        return await self.get_user_by_clerk_id(clerk_id)

    async def update_education(
        self, 
        clerk_id: str, 
        education_id: PyObjectId, 
        update_data: Dict
    ) -> UserProfile:
        """Update an existing education entry"""
        update_data["updated_at"] = datetime.utcnow()
        
        result = await self.collection.update_one(
            {
                "clerk_id": clerk_id,
                "education._id": ObjectId(education_id)
            },
            {"$set": {f"education.$.{k}": v for k, v in update_data.items()}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Education not found or no changes made")
            
        return await self.get_user_by_clerk_id(clerk_id)

    async def delete_education(self, clerk_id: str, education_id: PyObjectId) -> UserProfile:
        """Remove an education from user profile"""
        result = await self.collection.update_one(
            {"clerk_id": clerk_id},
            {"$pull": {"education": {"_id": ObjectId(education_id)}}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Education not found")
            
        return await self.get_user_by_clerk_id(clerk_id)

    # Resume Operations
    async def update_resume(self, clerk_id: str, resume: Resume) -> UserProfile:
        """Update or add a resume to user profile"""
        resume_dict = resume.model_dump()
        resume_dict["last_updated"] = datetime.utcnow()
        
        result = await self.collection.update_one(
            {"clerk_id": clerk_id},
            {"$set": {"resume": resume_dict}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="User not found or no changes made")
            
        return await self.get_user_by_clerk_id(clerk_id)

    async def delete_resume(self, clerk_id: str) -> UserProfile:
        """Remove resume from user profile"""
        result = await self.collection.update_one(
            {"clerk_id": clerk_id},
            {"$unset": {"resume": ""}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="User not found or no resume exists")
            
        return await self.get_user_by_clerk_id(clerk_id)

    # Social Links Operations
    async def update_social_links(self, clerk_id: str, social_links: SocialLinks) -> UserProfile:
        """Update social links for a user"""
        result = await self.collection.update_one(
            {"clerk_id": clerk_id},
            {"$set": {"social_links": social_links.model_dump()}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="User not found or no changes made")
            
        return await self.get_user_by_clerk_id(clerk_id)
    
async def update_user_profile_from_resume(
    crud: UserCRUD,
    clerk_id: str,
    parsed_resume: Dict,
    user_role:str = "job_seeker"
):
    """
    Updated version with proper date parsing
    """
    update_data = {
        "updated_at": datetime.utcnow(),
        "role": user_role,
    }
    
    discarded_data = {
        "unused_fields": [],
        "unused_experience_fields": [],
        "unused_education_fields": []
    }
    if user_role == Role.EMPLOYER:
        # Employer-specific fields
        update_data["company_name"] = parsed_resume.get(
            "Current Company", 
            parsed_resume.get("Company", "Unknown Company")
        )
    else:
        # Job seeker fields (ensure company_name is not required)
        update_data["company_name"] = None  # or "" if your model allows

    # 1. Basic Information
    if "Full Name" in parsed_resume:
        names = parsed_resume["Full Name"].split(" ", 1)
        update_data["first_name"] = names[0]
        if len(names) > 1:
            update_data["last_name"] = names[1]
        discarded_data["unused_fields"].append("Full Name")

    if "Email" in parsed_resume:
        update_data["email"] = parsed_resume["Email"]
        discarded_data["unused_fields"].append("Email")

    if "Phone Number" in parsed_resume:
        phone = parsed_resume["Phone Number"]
        # Clean phone number to match E.164 format
        cleaned_phone = re.sub(r'[^\d+]', '', phone)
        if not cleaned_phone.startswith('+'):
            cleaned_phone = f"+1{cleaned_phone}"  # Default to US code
        update_data["phone"] = cleaned_phone
        discarded_data["unused_fields"].append("Phone Number")

    if "LinkedIn Profile" in parsed_resume:
        update_data["social_links"] = {"linkedin": parsed_resume["LinkedIn Profile"]}
        discarded_data["unused_fields"].append("LinkedIn Profile")

    # 2. Skills
    if "Skills" in parsed_resume:
        update_data["skills"] = parsed_resume["Skills"]
        discarded_data["unused_fields"].append("Skills")

    # 3. Experience - with proper date handling
    if "Experience" in parsed_resume:
        experiences = []
        for exp in parsed_resume["Experience"]:
            # Handle duration parsing
            start_date, end_date, current = None, None, False
            if "Duration" in exp:
                duration = exp["Duration"]
                if "–" in duration or "-" in duration:
                    parts = re.split(r'[–-]', duration, 1)
                    start_str = parts[0].strip()
                    end_str = parts[1].strip() if len(parts) > 1 else None
                    
                    start_date = parse_date(start_str)
                    end_date = parse_date(end_str) if end_str else None
                    current = "present" in end_str.lower() if end_str else False
            
            experiences.append({
                "title": exp.get("Role", ""),
                "company": exp.get("Company", ""),
                "start_date": start_date,
                "end_date": end_date,
                "current": current,
                "description": exp.get("Description", "")
            })
            
            unused_exp_fields = [k for k in exp.keys() if k not in ["Role", "Company", "Duration", "Description"]]
            if unused_exp_fields:
                discarded_data["unused_experience_fields"].extend(unused_exp_fields)
        
        update_data["experience"] = experiences
        discarded_data["unused_fields"].append("Experience")

    # 4. Education - with proper year handling
    if "Education" in parsed_resume:
        educations = []
        for edu in parsed_resume["Education"]:
            # Handle year parsing
            start_year, end_year = None, None
            if "Year" in edu:
                year_str = edu["Year"]
                if "–" in year_str or "-" in year_str:
                    parts = re.split(r'[–-]', year_str, 1)
                    start_year = extract_year(parts[0].strip())
                    end_year = extract_year(parts[1].strip()) if len(parts) > 1 else None
                else:
                    start_year = extract_year(year_str.strip())
            
            educations.append({
                "institution": edu.get("University", ""),
                "degree": edu.get("Degree", ""),
                "field_of_study": "Computer Science",  # Default or parse from degree
                "start_year": start_year,
                "end_year": end_year
            })
            
            unused_edu_fields = [k for k in edu.keys() if k not in ["Degree", "University", "Year"]]
            if unused_edu_fields:
                discarded_data["unused_education_fields"].extend(unused_edu_fields)
        
        update_data["education"] = educations
        discarded_data["unused_fields"].append("Education")

    required_fields = {
        "job_seeker": ["first_name", "last_name", "phone"],
        "employer": ["company_name", "phone"]
    }
    
    for field in required_fields.get(user_role, []):
        if field not in update_data:
            update_data[field] = "Unknown"  # Provide default value

    # Update the profile
    updated_profile = await crud.update_user(clerk_id, update_data)
    
    return {
        "updated_profile": updated_profile,
        "discarded_data": discarded_data
    }

def parse_date(date_str: str) -> Optional[datetime]:
    """Parse various date formats to datetime"""
    if not date_str:
        return None
    
    try:
        # Remove ordinal indicators (1st, 2nd, 3rd, etc.)
        date_str = re.sub(r'(\d)(st|nd|rd|th)', r'\1', date_str)
        return parse(date_str, fuzzy=True)
    except:
        return None

def extract_year(year_str: str) -> Optional[int]:
    """Extract year from string (handles 'May 2025' -> 2025)"""
    if not year_str:
        return None
    
    # Find all 4-digit numbers in the string
    year_matches = re.findall(r'\b\d{4}\b', year_str)
    if year_matches:
        return int(year_matches[-1])  # Take the last 4-digit number found
    
    try:
        # Try to parse as date and extract year
        dt = parse_date(year_str)
        return dt.year if dt else None
    except:
        return None
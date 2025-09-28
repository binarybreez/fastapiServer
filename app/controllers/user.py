from typing import List, Optional, Dict, Any
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
import logging
from dateutil.parser import parse

# Set up logging
logger = logging.getLogger(__name__)

class UserCRUD:
    def __init__(self, db_collection):
        self.collection = db_collection

    def _normalize_role(self, role: str) -> str:
        """
        Normalize role values to match the expected enum values
        """
        if not role:
            return "job_seeker"
        
        # Convert to lowercase and replace spaces with underscores
        normalized = role.lower().replace(' ', '_').replace('-', '_')
        
        # Handle common variations
        role_mappings = {
            'jobseeker': 'job_seeker',
            'job-seeker': 'job_seeker',
            'job seeker': 'job_seeker',
            'seeker': 'job_seeker',
            'candidate': 'job_seeker',
            'recruiter': 'employer',
            'hr': 'employer',
            'company': 'employer',
            'hiring_manager': 'employer',
            'hiring-manager': 'employer',
            'hiring manager': 'employer'
        }
        
        return role_mappings.get(normalized, normalized)

    async def get_user_by_clerk_id_raw(self, clerk_id: str) -> Optional[Dict[str, Any]]:
        """
        Get raw user data by clerk_id without Pydantic validation
        """
        try:
            raw_user = await self.collection.find_one({"clerk_id": clerk_id})
            if raw_user:
                # Convert ObjectId to string for JSON serialization
                raw_user["_id"] = str(raw_user["_id"])
            return raw_user
        except Exception as e:
            logger.error(f"Error getting raw user by clerk_id {clerk_id}: {str(e)}")
            raise

    async def get_user_by_clerk_id(self, clerk_id: str) -> Optional[UserProfile]:
        """Get a user by their Clerk ID with normalized role"""
        try:
            raw_user = await self.get_user_by_clerk_id_raw(clerk_id)
            if not raw_user:
                return None
            
            # Normalize role before Pydantic validation
            if 'role' in raw_user:
                raw_user['role'] = self._normalize_role(raw_user['role'])
            
            return UserProfile(**raw_user)
        except Exception as e:
            logger.error(f"Error getting user by clerk_id {clerk_id}: {str(e)}")
            raise

    async def get_user_by_id(self, user_id: PyObjectId) -> UserProfile:
        """Get a user by their ID with normalized role"""
        try:
            raw_user = await self.collection.find_one({"_id": ObjectId(user_id)})
            if not raw_user:
                raise HTTPException(status_code=404, detail="User not found")
            
            # Normalize role before Pydantic validation
            if 'role' in raw_user:
                raw_user['role'] = self._normalize_role(raw_user['role'])
                
            return UserProfile(**raw_user)
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error getting user by ID {user_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

    async def update_user(self, clerk_id: str, update_data: Dict) -> Optional[UserProfile]:
        """Update a user's profile with role normalization"""
        try:
            # Normalize role if present in update data
            if 'role' in update_data:
                update_data['role'] = self._normalize_role(update_data['role'])
            
            # Add updated timestamp
            update_data["updated_at"] = datetime.utcnow()
            
            result = await self.collection.find_one_and_update(
                {"clerk_id": clerk_id},
                {"$set": update_data},
                return_document=True
            )
            
            if not result:
                return None
            
            # Normalize role in result before creating UserProfile
            if 'role' in result:
                result['role'] = self._normalize_role(result['role'])
                
            return UserProfile(**result)
            
        except Exception as e:
            logger.error(f"Error updating user {clerk_id}: {str(e)}")
            raise

    async def update_user_profile(
        self,
        clerk_id: str,
        update_data: dict,
        role: Optional[Role] = None
    ) -> UserProfile:
        
        existing_user = await self.collection.find_one({"clerk_id": clerk_id})
        if not existing_user:
            raise HTTPException(status_code=404, detail="User not found")
        
        # Normalize existing role
        existing_role_str = existing_user.get("role", "unassigned")
        normalized_existing_role = self._normalize_role(existing_role_str)
        
        # 2. Determine role (use existing if not provided)
        try:
            current_role = Role(normalized_existing_role)
        except ValueError:
            current_role = Role.UNASSIGNED
            
        if role and current_role != role:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot update fields for {role} role when user is {current_role}"
            )
        effective_role = role or current_role
        
        # 3. Prepare update document with role-specific handling
        update_doc = {
            "$set": {
                "updated_at": datetime.utcnow()
            }
        }
        
        # Common fields all roles can update
        common_fields = [
            "first_name", "last_name", "phone", "location", 
            "willing_to_relocate", "social_links"
        ]
        
        # Role-specific field validation
        if effective_role == Role.JOB_SEEKER:
            allowed_fields = common_fields + [
                "skills", "experience", "education", "resume"
            ]
            # Ensure job seekers can't set employer fields
            if "company_name" in update_data:
                update_data.pop("company_name")
        
        elif effective_role == Role.EMPLOYER:
            allowed_fields = common_fields + [
                "company_name", "company_logo", "company_website"
            ]
            # Ensure employers can't set job seeker fields
            for field in ["skills", "experience", "education", "resume"]:
                if field in update_data:
                    update_data.pop(field)
        
        else:  # UNASSIGNED
            allowed_fields = common_fields
        
        # Filter update data to only allowed fields
        filtered_updates = {
            k: v for k, v in update_data.items() 
            if k in allowed_fields
        }
        
        # Normalize role if being updated
        if 'role' in filtered_updates:
            filtered_updates['role'] = self._normalize_role(filtered_updates['role'])
        
        # Add to update document
        update_doc["$set"].update(filtered_updates)
        
        # 4. Perform the update
        result = await self.collection.update_one(
            {"clerk_id": clerk_id},
            update_doc
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=304,
                detail="No changes made or data validation failed"
            )
        
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

# Helper function to normalize role in the update_user_profile_from_resume function
def normalize_role_for_update(role: str) -> str:
    """Normalize role for the update function"""
    if not role:
        return "job_seeker"
    
    normalized = role.lower().replace(' ', '_').replace('-', '_')
    
    role_mappings = {
        'jobseeker': 'job_seeker',
        'job-seeker': 'job_seeker',
        'job seeker': 'job_seeker',
        'seeker': 'job_seeker',
        'candidate': 'job_seeker',
        'recruiter': 'employer',
        'hr': 'employer',
        'company': 'employer',
        'hiring_manager': 'employer',
        'hiring-manager': 'employer',
        'hiring manager': 'employer'
    }
    
    return role_mappings.get(normalized, normalized)

async def update_user_profile_from_resume(
    crud: UserCRUD,
    clerk_id: str,
    resume_url: str,
    parsed_resume: Dict,
    user_role: str = "job_seeker",
):
    """
    Updated version with proper date parsing and role normalization
    """
    # FIXED: Normalize the role first
    normalized_role = normalize_role_for_update(user_role)
    
    update_data = {
        "updated_at": datetime.utcnow(),
        "role": normalized_role,  # Use normalized role
    }
    
    discarded_data = {
        "unused_fields": [],
        "unused_experience_fields": [],
        "unused_education_fields": []
    }
    
    # FIXED: Use normalized role for comparison
    if normalized_role == "employer":
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

    if "First Name" in parsed_resume:
        update_data["first_name"] = parsed_resume["First Name"]
        discarded_data["unused_fields"].append("First Name")
        
    if "Last Name" in parsed_resume:
        update_data["last_name"] = parsed_resume["Last Name"]
        discarded_data["unused_fields"].append("Last Name")

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

    # Add resume URL
    if resume_url:
        update_data["resume"] = {"resume_url": resume_url}

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

    # FIXED: Use normalized role for required fields check
    required_fields = {
        "job_seeker": ["first_name", "last_name", "phone"],
        "employer": ["company_name", "phone"]
    }
    
    for field in required_fields.get(normalized_role, []):
        if field not in update_data:
            update_data[field] = "Unknown"  # Provide default value

    try:
        # Update the profile
        updated_profile = await crud.update_user(clerk_id, update_data)
        
        return {
            "updated_profile": updated_profile,
            "discarded_data": discarded_data,
            "normalized_role": normalized_role  # Include for debugging
        }
    except Exception as e:
        logger.error(f"Error updating user profile from resume: {str(e)}")
        raise

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
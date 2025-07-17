from datetime import datetime
from enum import Enum
from typing import List, Optional, Annotated
from pydantic import BaseModel, EmailStr, Field, ConfigDict
from pydantic.functional_validators import AfterValidator
from bson import ObjectId


# Custom ObjectId validator
def validate_object_id(value: str) -> str:
    if not ObjectId.is_valid(value):
        raise ValueError("Invalid ObjectId")
    return value

PyObjectId = Annotated[str, AfterValidator(validate_object_id)]

class Role(str, Enum):
    JOB_SEEKER = "job_seeker"
    EMPLOYER = "employer"
    UNASSIGNED = "unassigned"


class Experience(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    id: PyObjectId = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    title: str
    company: str
    start_date: datetime
    end_date: Optional[datetime] = None
    current: bool = False
    description: Optional[str] = None

class Education(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    id: PyObjectId = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    institution: str
    degree: str
    field_of_study: str
    start_year: int
    end_year: Optional[int] = None

class SocialLinks(BaseModel):
    linkedin: Optional[str] = None
    github: Optional[str] = None
    portfolio: Optional[str] = None

class Resume(BaseModel):
    file_key: str
    parsed_data: dict
    last_updated: datetime = Field(default_factory=datetime.utcnow)

class BaseUser(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    clerk_id: str = Field(..., min_length=1)
    email: EmailStr
    role: Role

class JobSeekerCreate(BaseUser):
    first_name: str
    last_name: str
    phone: Optional[str] = Field(None, pattern=r"^\+?[1-9]\d{1,14}$")  # E.164 format
    location: Optional[str] = None
    willing_to_relocate: bool = False
    resume: Optional[Resume] = None

class EmployerCreate(BaseUser):
    company_name: Optional[str] = Field(None,description="Required for employers, optional for job seekers")
    company_logo: Optional[str] = None
    company_website: Optional[str] = Field(None, pattern=r"https?://.+")

class UserProfile(JobSeekerCreate, EmployerCreate):
    skills: List[str] = Field(default_factory=list)
    experience: List[Experience] = Field(default_factory=list)
    education: List[Education] = Field(default_factory=list)
    social_links: SocialLinks = Field(default_factory=SocialLinks)
    profile_complete: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
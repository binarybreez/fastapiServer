from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File, Query, status
import os
import time
import hashlib
from datetime import datetime
from app.utils.parser import parse_resume
from fastapi.responses import JSONResponse
from app.controllers.user import update_user_profile_from_resume, UserCRUD
from app.db import db
from app.models.user import (
    UserProfile,
    Experience,
    Education,
    SocialLinks,
    Role,
    PyObjectId
)
from bson import ObjectId
from typing import List, Optional, Dict, Any
import cloudinary
import cloudinary.uploader
from pydantic import BaseModel
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Cloudinary - FIXED
cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET"),
    secure=True  # Always use HTTPS
)

router = APIRouter()

# ADDED: Role normalization function
def normalize_role(role: str) -> str:
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

# ADDED: Function to normalize user data from database
def normalize_user_data(user_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize user data from database before Pydantic validation
    """
    if user_data and 'role' in user_data:
        user_data['role'] = normalize_role(user_data['role'])
    
    return user_data

# Dependency to get user CRUD instance
async def get_user_crud():
    yield UserCRUD(db.users)

# Pydantic models for request validation
class ProfileUpdateRequest(BaseModel):
    clerk_id: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    willing_to_relocate: Optional[bool] = None
    role: Optional[str] = None
    current_company: Optional[str] = None
    resume_filename: Optional[str] = None
    resume_url: Optional[str] = None
    technical_skills: Optional[List[str]] = None
    soft_skills: Optional[List[str]] = None
    skills: Optional[List[str]] = None
    social_links: Optional[Dict[str, str]] = None
    experience: Optional[List[Dict[str, Any]]] = None
    education: Optional[List[Dict[str, Any]]] = None
    certifications: Optional[List[str]] = None
    projects: Optional[List[Dict[str, Any]]] = None

def generate_cloudinary_signature(params: Dict[str, str], api_secret: str) -> str:
    """
    Generate Cloudinary signature for secure uploads
    """
    # Sort parameters alphabetically and concatenate
    string_to_sign = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
    
    # Create signature
    signature = hashlib.sha1((string_to_sign + api_secret).encode('utf-8')).hexdigest()
    
    logger.info(f"Generated signature for params: {params}")
    logger.info(f"String to sign: {string_to_sign}")
    
    return signature

@router.post("/upload")
async def upload_cloud(
    clerk_id: str = Form(...),
    file: UploadFile = File(...),
    user_role: str = Form(default="job_seeker"),
):
    """
    Upload and parse resume file with comprehensive error handling and proper Cloudinary signature
    """
    try:
        logger.info(f"Starting upload process for user: {clerk_id}")
        
        # Validate inputs
        if not clerk_id or len(clerk_id.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="clerk_id is required and cannot be empty"
            )
        
        if not file or not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No file provided"
            )

        logger.info(f"File received: {file.filename}, Content-Type: {file.content_type}")

        # Validate file type
        allowed_types = [
            "application/pdf",
            "application/msword", 
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ]

        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail=f"Invalid file type: {file.content_type}. Allowed types: PDF, DOC, DOCX"
            )

        # Read file content and validate size
        try:
            content = await file.read()
            file_size = len(content)
            logger.info(f"File size: {file_size} bytes")
        except Exception as e:
            logger.error(f"Failed to read file: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Failed to read uploaded file"
            )
        
        # Validate file size (5MB max)
        max_size = 5 * 1024 * 1024  # 5MB
        if file_size > max_size:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File too large: {file_size} bytes. Maximum size is {max_size} bytes (5MB)"
            )

        if file_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="File is empty"
            )

        # FIXED: Generate CURRENT timestamp (not future timestamp)
        current_timestamp = str(int(time.time()))  # Current timestamp as string
        file_extension = os.path.splitext(file.filename)[1] if file.filename else ".pdf"
        file_name = f"{clerk_id}_{current_timestamp}{file_extension}"
        file_path = f"uploads/{file_name}"

        # Ensure uploads directory exists
        os.makedirs("uploads", exist_ok=True)

        # Save file temporarily
        try:
            with open(file_path, "wb") as buffer:
                buffer.write(content)
            logger.info(f"File saved temporarily: {file_path}")
        except Exception as e:
            logger.error(f"Failed to save temporary file: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to save uploaded file temporarily"
            )

        upload_result = None
        try:
            # FIXED: Cloudinary upload with proper signature generation
            logger.info("Starting Cloudinary upload")
            
            # Check Cloudinary configuration
            if not all([
                os.getenv("CLOUDINARY_CLOUD_NAME"),
                os.getenv("CLOUDINARY_API_KEY"), 
                os.getenv("CLOUDINARY_API_SECRET")
            ]):
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Cloudinary configuration missing. Please check environment variables."
                )
            
            # FIXED: Prepare parameters for signature generation (all as strings)
            public_id = f"resumes/{clerk_id}_{current_timestamp}"
            
            # Parameters for signature (exactly as shown in your example)
            params = {
                "folder": "resumes",
                "overwrite": "1",  # String, not boolean
                "public_id": public_id,
                "timestamp": current_timestamp,  # Already a string
                "unique_filename": "1",  # String, not boolean
                "use_filename": "0"  # String, not boolean (False)
            }
            
            # Generate signature
            api_secret = os.getenv("CLOUDINARY_API_SECRET")
            signature = generate_cloudinary_signature(params, api_secret)
            
            # Add signature and API key to params for upload
            upload_params = {
                **params,
                "signature": signature,
                "api_key": os.getenv("CLOUDINARY_API_KEY")
            }
            
            # Convert string parameters back to appropriate types for cloudinary.uploader.upload
            upload_result = cloudinary.uploader.upload(
                file_path,
                resource_type="auto",
                public_id=public_id,
                folder="resumes",
                use_filename=False,  # Boolean False (corresponds to "0")
                unique_filename=True,  # Boolean True (corresponds to "1")
                overwrite=True,  # Boolean True (corresponds to "1")
                timestamp=int(current_timestamp),  # Convert back to int for upload
                signature=signature,  # Include the signature
            )
            
            logger.info(f"Cloudinary upload successful: {upload_result.get('secure_url', 'No URL')}")

            # Parse resume data
            logger.info("Starting resume parsing")
            try:
                resume_data = await parse_resume(file_path)
                logger.info(f"Resume parsing successful. Data keys: {list(resume_data.keys()) if resume_data else 'None'}")
            except Exception as parse_error:
                logger.warning(f"Resume parsing failed: {str(parse_error)}")
                # Continue with empty data if parsing fails
                resume_data = {
                    "First Name": "",
                    "Last Name": "",
                    "Email": "",
                    "Skills": [],
                    "Experience": [],
                    "Education": []
                }

            # Update user profile
            logger.info("Updating user profile")
            user_crud = UserCRUD(db.users)
            resume_url = upload_result["secure_url"]
            
            # FIXED: Normalize user_role before processing
            normalized_user_role = normalize_role(user_role)
            
            # Update user profile with resume data
            try:
                updated_profile = await update_user_profile_from_resume(
                    user_crud, 
                    clerk_id, 
                    resume_url, 
                    resume_data, 
                    normalized_user_role  # Use normalized role
                )
                logger.info("User profile updated successfully")
            except Exception as profile_error:
                logger.error(f"Profile update failed: {str(profile_error)}")
                # Don't fail the entire request if profile update fails
                logger.warning("Continuing with upload success despite profile update failure")

            return JSONResponse(
                status_code=200,
                content={
                    "message": "Resume uploaded successfully",
                    "file_name": file_name,
                    "cloudinary_url": upload_result["secure_url"],
                    "result": resume_data,
                    "upload_info": {
                        "file_size": file_size,
                        "content_type": file.content_type,
                        "timestamp": int(current_timestamp)  # Convert back to int for response
                    },
                    "debug_info": {
                        "signature_params": params,
                        "generated_signature": signature,
                        "public_id": public_id,
                        "normalized_role": normalized_user_role  # Include for debugging
                    }
                },
            )

        except Exception as upload_error:
            logger.error(f"Cloudinary upload failed: {str(upload_error)}")
            
            # More specific error handling
            error_msg = str(upload_error)
            if "Invalid Signature" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Cloudinary authentication failed. Please check API credentials, signature generation, and system clock."
                )
            elif "Invalid cloud_name" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Invalid Cloudinary cloud name. Please check CLOUDINARY_CLOUD_NAME environment variable."
                )
            elif "Invalid timestamp" in error_msg or "Request Expired" in error_msg:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Timestamp issue. Please check system clock and ensure timestamp is current."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to upload file to cloud storage: {error_msg}"
                )

        finally:
            # Always clean up temporary file
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    logger.info(f"Temporary file cleaned up: {file_path}")
            except Exception as cleanup_error:
                logger.warning(f"Failed to cleanup temporary file: {str(cleanup_error)}")

    except HTTPException:
        # Re-raise HTTP exceptions as-is
        raise
    except Exception as e:
        # Log the full error for debugging
        logger.error(f"Unexpected upload error: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Internal server error during upload: {str(e)}"
        )

@router.get("/me")
async def get_current_user(
    clerk_id: str = Query(..., description="Authenticated user's Clerk ID"),
    crud: UserCRUD = Depends(get_user_crud)
):
    """
    Get complete profile of the authenticated user
    """
    try:
        logger.info(f"Fetching profile for user: {clerk_id}")
        
        if not clerk_id or len(clerk_id.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="clerk_id is required"
            )

        # FIXED: Get raw user data and normalize before Pydantic validation
        raw_user = await crud.get_user_by_clerk_id_raw(clerk_id)  # New method needed
        if not raw_user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User profile not found for clerk_id: {clerk_id}"
            )
        
        # Normalize the user data
        normalized_user_data = normalize_user_data(raw_user)
        
        # Convert to UserProfile with normalized data
        user = UserProfile(**normalized_user_data)
        
        logger.info(f"Profile fetched successfully for user: {clerk_id}")
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching user profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch user profile: {str(e)}"
        )

@router.patch("/me")
async def update_basic_profile(
    update_data: Dict[str, Any],
    clerk_id: str = Query(..., description="Authenticated user's Clerk ID"),
    crud: UserCRUD = Depends(get_user_crud)
):
    """
    Update basic user profile information via query parameter
    """
    try:
        logger.info(f"Updating profile for user: {clerk_id}")
        
        if not clerk_id or len(clerk_id.strip()) == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="clerk_id is required"
            )
            
        if not update_data:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Update data cannot be empty"
            )
        
        # Remove clerk_id from update_data if present to avoid conflicts
        update_data.pop('clerk_id', None)
        
        # FIXED: Normalize role if present in update data
        if 'role' in update_data:
            update_data['role'] = normalize_role(update_data['role'])
        
        user = await crud.update_user(clerk_id, update_data)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"User not found for clerk_id: {clerk_id}"
            )
        
        logger.info(f"Profile updated successfully for user: {clerk_id}")
        return user
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating profile: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to update profile: {str(e)}"
        )

# Health check endpoint
@router.get("/health")
async def health_check():
    """
    Health check endpoint for the user service
    """
    return {
        "status": "healthy",
        "service": "user-service",
        "timestamp": datetime.now().isoformat(),
        "current_unix_timestamp": int(time.time()),  # Added for debugging
        "cloudinary_configured": bool(
            os.getenv("CLOUDINARY_CLOUD_NAME") and 
            os.getenv("CLOUDINARY_API_KEY") and 
            os.getenv("CLOUDINARY_API_SECRET")
        )
    }
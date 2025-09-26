from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File, Query, status
import os
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
from typing import List, Optional
import cloudinary
import cloudinary.uploader



cloudinary.config(
    cloud_name=os.getenv("CLOUDINARY_CLOUD_NAME"),
    api_key=os.getenv("CLOUDINARY_API_KEY"),
    api_secret=os.getenv("CLOUDINARY_API_SECRET")
)
router = APIRouter()

async def get_user_crud():
    yield UserCRUD(db.users)

@router.post("/upload")
async def upload_cloud(
    clerk_id: str = Form(...),
    file: UploadFile = File(...),
    user_role: str = Form(...),  # Optional additional data
):
    try:
        # Validate file type
        allowed_types = [
            "application/pdf",
            "application/msword",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ]

        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail="Invalid file type")

        # Validate file size (e.g., 5MB max)
        max_size = 5 * 1024 * 1024  # 5MB
        file.file.seek(0, 2)  # Move to end of file
        file_size = file.file.tell()
        file.file.seek(0)  # Reset file pointer

        if file_size > max_size:
            raise HTTPException(status_code=400, detail="File too large")

        # Process the file (example: save locally)
        file_name = f"{clerk_id}_{datetime.now().timestamp()}{os.path.splitext(file.filename)[1]}"
        file_path = f"uploads/{file_name}"

        # Ensure the uploads directory exists
        os.makedirs("uploads", exist_ok=True)

        # Save the file locally temporarily
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Upload the file to Cloudinary
        result = cloudinary.uploader.upload(
            file_path,  # Upload from the local path
            resource_type="auto",  # Since we're dealing with a non-image file
            public_id=f"resumes/{clerk_id}_{int(datetime.now().timestamp())}",  # Optional: custom public ID
        )

        # Optional: Process the uploaded resume (e.g., parse resume data)
        resume_data = await parse_resume(file_path)

        # Update user profile with resume data (e.g., extract from the resume)
        user_crud = UserCRUD(db.users)
        resume_url = result["secure_url"]
        response = await update_user_profile_from_resume(user_crud, clerk_id,resume_url, resume_data, user_role)
        # Remove the local file after uploading
        os.remove(file_path)

        # Return response with the Cloudinary URL and any parsed data
        return JSONResponse(
            status_code=200,
            content={
                "message": "Resume uploaded successfully",
                "file_name": file_name,
                "cloudinary_url": result["secure_url"],
                "result": resume_data,  # Include parsed resume data
            },
        )

    except Exception as e:
        # In case of any error, we return a detailed error message
        raise HTTPException(status_code=500, detail=str(e))

# Get current user profile
@router.get("/me", response_model=UserProfile)
async def get_current_user(
    clerk_id: str = Query(..., description="Authenticated user's Clerk ID"),
    crud: UserCRUD = Depends(get_user_crud)
):
    """
    Get complete profile of the authenticated user
    """
    try:
        return await crud.get_user_by_clerk_id(clerk_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

# Update basic profile info
@router.patch("/me", response_model=UserProfile)
async def update_basic_profile(
    update_data: dict,
    clerk_id: str = Query(..., description="Authenticated user's Clerk ID"),
    crud: UserCRUD = Depends(get_user_crud)
):
    """
    Update basic user profile information
    """
    try:
        return await crud.update_user(clerk_id, update_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# Experience endpoints
@router.post("/me/experience", response_model=UserProfile)
async def add_experience(
    experience: Experience,
    clerk_id: str = Query(..., description="Authenticated user's Clerk ID"),
    crud: UserCRUD = Depends(get_user_crud)
):
    """
    Add new work experience to user profile
    """
    try:
        return await crud.add_experience(clerk_id, experience)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put("/me/experience/{exp_id}", response_model=UserProfile)
async def update_experience(
    exp_id: PyObjectId,
    update_data: dict,
    clerk_id: str = Query(..., description="Authenticated user's Clerk ID"),
    crud: UserCRUD = Depends(get_user_crud)
):
    """
    Update existing work experience
    """
    try:
        return await crud.update_experience(clerk_id, exp_id, update_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/me/experience/{exp_id}", response_model=UserProfile)
async def delete_experience(
    exp_id: PyObjectId,
    clerk_id: str = Query(..., description="Authenticated user's Clerk ID"),
    crud: UserCRUD = Depends(get_user_crud)
):
    """
    Remove experience from profile
    """
    try:
        return await crud.delete_experience(clerk_id, exp_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# Education endpoints
@router.post("/me/education", response_model=UserProfile)
async def add_education(
    education: Education,
    clerk_id: str = Query(..., description="Authenticated user's Clerk ID"),
    crud: UserCRUD = Depends(get_user_crud)
):
    """
    Add new education entry to profile
    """
    try:
        return await crud.add_education(clerk_id, education)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.put("/me/education/{edu_id}", response_model=UserProfile)
async def update_education(
    edu_id: PyObjectId,
    update_data: dict,
    clerk_id: str = Query(..., description="Authenticated user's Clerk ID"),
    crud: UserCRUD = Depends(get_user_crud)
):
    """
    Update existing education entry
    """
    try:
        return await crud.update_education(clerk_id, edu_id, update_data)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/me/education/{edu_id}", response_model=UserProfile)
async def delete_education(
    edu_id: PyObjectId,
    clerk_id: str = Query(..., description="Authenticated user's Clerk ID"),
    crud: UserCRUD = Depends(get_user_crud)
):
    """
    Remove education from profile
    """
    try:
        return await crud.delete_education(clerk_id, edu_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# Skills endpoints
@router.post("/me/skills", response_model=UserProfile)
async def add_skills(
    skills: List[str],
    clerk_id: str = Query(..., description="Authenticated user's Clerk ID"),
    crud: UserCRUD = Depends(get_user_crud)
):
    """
    Add new skills to profile (merges with existing skills)
    """
    try:
        return await crud.update_user(
            clerk_id,
            {"$addToSet": {"skills": {"$each": skills}}}
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.delete("/me/skills", response_model=UserProfile)
async def remove_skills(
    skills: List[str],
    clerk_id: str = Query(..., description="Authenticated user's Clerk ID"),
    crud: UserCRUD = Depends(get_user_crud)
):
    """
    Remove skills from profile
    """
    try:
        return await crud.update_user(
            clerk_id,
            {"$pull": {"skills": {"$in": skills}}}
        )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# Social links endpoints
@router.put("/me/social", response_model=UserProfile)
async def update_social_links(
    social_links: SocialLinks,
    clerk_id: str = Query(..., description="Authenticated user's Clerk ID"),
    crud: UserCRUD = Depends(get_user_crud)
):
    """
    Update social media links
    """
    try:
        return await crud.update_social_links(clerk_id, social_links)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

# Resume endpoints
@router.delete("/me/resume", response_model=UserProfile)
async def delete_resume(
    clerk_id: str = Query(..., description="Authenticated user's Clerk ID"),
    crud: UserCRUD = Depends(get_user_crud)
):
    """
    Remove resume from profile
    """
    try:
        return await crud.delete_resume(clerk_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.patch("/{clerk_id}", response_model=UserProfile)
async def update_user_profile(
    clerk_id: str,
    update_data: dict,
    crud: UserCRUD = Depends(get_user_crud)
):
    try:
        return await crud.update_user(
            clerk_id=clerk_id,
            update_data=update_data,
        )
    except HTTPException as e:
        raise e
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )
from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File, Query, status
import os
import aiohttp
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
from typing import List
import tempfile
import json

router = APIRouter()

# UploadThing configuration
UPLOADTHING_SECRET = os.getenv("UPLOADTHING_SECRET")
UPLOADTHING_APP_ID = os.getenv("UPLOADTHING_APP_ID")
UPLOADTHING_API_URL = "https://api.uploadthing.com/api/uploadFiles"

async def get_user_crud():
    yield UserCRUD(db.users)

async def upload_to_uploadthing(file_path: str, file_name: str, file_type: str) -> dict:
    """Fixed UploadThing upload function"""
    try:
        headers = {
            "X-Uploadthing-Api-Key": UPLOADTHING_SECRET,
        }
        
        # Read file content
        with open(file_path, 'rb') as f:
            file_content = f.read()
        
        # Create proper FormData
        form_data = aiohttp.FormData()
        form_data.add_field('files', file_content, filename=file_name, content_type=file_type)
        
        # Add route config
        form_data.add_field('routeConfig', json.dumps({
            "fileUploader": {
                "maxFileSize": "5MB",
                "maxFileCount": 1,
                "acceptedFileTypes": ["application/pdf", "application/msword", 
                                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document"]
            }
        }))
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                UPLOADTHING_API_URL,
                headers=headers,
                data=form_data
            ) as response:
                response_text = await response.text()
                
                if response.status != 200:
                    raise HTTPException(
                        status_code=500, 
                        detail=f"UploadThing upload failed: {response_text}"
                    )
                
                try:
                    result = await response.json()
                    if not isinstance(result, dict) or 'data' not in result:
                        raise ValueError("Invalid UploadThing response format")
                    return result['data']
                except json.JSONDecodeError:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Invalid JSON response from UploadThing: {response_text}"
                    )
                
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to upload to UploadThing: {str(e)}"
        )

@router.post("/upload")
async def upload_cloud(
    clerk_id: str = Form(...),
    file: UploadFile = File(...),
    user_role: str = Form(...),
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

        # Validate file size (max 5MB)
        max_size = 5 * 1024 * 1024
        file.file.seek(0, 2)
        file_size = file.file.tell()
        file.file.seek(0)

        if file_size > max_size:
            raise HTTPException(status_code=400, detail="File too large")

        # Save to temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            # Generate unique filename
            file_name = f"{clerk_id}_{datetime.now().timestamp()}{os.path.splitext(file.filename)[1]}"
            
            # Upload to UploadThing
            upload_result = await upload_to_uploadthing(
                temp_file_path, 
                file_name, 
                file.content_type
            )
            
            # Expecting a list inside "data"
            if not upload_result or not isinstance(upload_result, list) or len(upload_result) == 0:
                raise HTTPException(
                    status_code=500,
                    detail="No file URL returned from UploadThing"
                )
            
            uploaded_file = upload_result[0]
            resume_url = uploaded_file.get('url') or uploaded_file.get('fileUrl')
            
            if not resume_url:
                raise HTTPException(
                    status_code=500,
                    detail="File URL not found in UploadThing response"
                )

            # Parse resume
            resume_data = await parse_resume(temp_file_path)

            # Update user profile
            user_crud = UserCRUD(db.users)
            await update_user_profile_from_resume(
                user_crud, 
                clerk_id, 
                resume_url, 
                resume_data, 
                user_role
            )

            return JSONResponse(
                status_code=200,
                content={
                    "message": "Resume uploaded successfully",
                    "file_name": file_name,
                    "uploadthing_url": resume_url,
                    "file_key": uploaded_file.get('key'),
                    "result": resume_data,
                },
            )

        finally:
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)

    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ---------------- PROFILE ENDPOINTS ----------------

@router.get("/me", response_model=UserProfile)
async def get_current_user(
    clerk_id: str = Query(..., description="Authenticated user's Clerk ID"),
    crud: UserCRUD = Depends(get_user_crud)
):
    try:
        return await crud.get_user_by_clerk_id(clerk_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.patch("/me", response_model=UserProfile)
async def update_basic_profile(
    update_data: dict,
    clerk_id: str = Query(..., description="Authenticated user's Clerk ID"),
    crud: UserCRUD = Depends(get_user_crud)
):
    try:
        return await crud.update_user(clerk_id, update_data)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/me/experience", response_model=UserProfile)
async def add_experience(
    experience: Experience,
    clerk_id: str = Query(...),
    crud: UserCRUD = Depends(get_user_crud)
):
    return await crud.add_experience(clerk_id, experience)

@router.put("/me/experience/{exp_id}", response_model=UserProfile)
async def update_experience(
    exp_id: PyObjectId,
    update_data: dict,
    clerk_id: str = Query(...),
    crud: UserCRUD = Depends(get_user_crud)
):
    return await crud.update_experience(clerk_id, exp_id, update_data)

@router.delete("/me/experience/{exp_id}", response_model=UserProfile)
async def delete_experience(
    exp_id: PyObjectId,
    clerk_id: str = Query(...),
    crud: UserCRUD = Depends(get_user_crud)
):
    return await crud.delete_experience(clerk_id, exp_id)

@router.post("/me/education", response_model=UserProfile)
async def add_education(
    education: Education,
    clerk_id: str = Query(...),
    crud: UserCRUD = Depends(get_user_crud)
):
    return await crud.add_education(clerk_id, education)

@router.put("/me/education/{edu_id}", response_model=UserProfile)
async def update_education(
    edu_id: PyObjectId,
    update_data: dict,
    clerk_id: str = Query(...),
    crud: UserCRUD = Depends(get_user_crud)
):
    return await crud.update_education(clerk_id, edu_id, update_data)

@router.delete("/me/education/{edu_id}", response_model=UserProfile)
async def delete_education(
    edu_id: PyObjectId,
    clerk_id: str = Query(...),
    crud: UserCRUD = Depends(get_user_crud)
):
    return await crud.delete_education(clerk_id, edu_id)

@router.post("/me/skills", response_model=UserProfile)
async def add_skills(
    skills: List[str],
    clerk_id: str = Query(...),
    crud: UserCRUD = Depends(get_user_crud)
):
    return await crud.update_user(
        clerk_id,
        {"$addToSet": {"skills": {"$each": skills}}}
    )

@router.delete("/me/skills", response_model=UserProfile)
async def remove_skills(
    skills: List[str],
    clerk_id: str = Query(...),
    crud: UserCRUD = Depends(get_user_crud)
):
    return await crud.update_user(
        clerk_id,
        {"$pull": {"skills": {"$in": skills}}}
    )

@router.put("/me/social", response_model=UserProfile)
async def update_social_links(
    social_links: SocialLinks,
    clerk_id: str = Query(...),
    crud: UserCRUD = Depends(get_user_crud)
):
    return await crud.update_social_links(clerk_id, social_links)

@router.delete("/me/resume", response_model=UserProfile)
async def delete_resume(
    clerk_id: str = Query(...),
    crud: UserCRUD = Depends(get_user_crud)
):
    return await crud.delete_resume(clerk_id)

@router.patch("/{clerk_id}", response_model=UserProfile)
async def update_user_profile(
    clerk_id: str,
    update_data: dict,
    crud: UserCRUD = Depends(get_user_crud)
):
    return await crud.update_user(clerk_id=clerk_id, update_data=update_data)

# Delete file from UploadThing
@router.delete("/uploadthing/{file_key}")
async def delete_uploadthing_file(
    file_key: str,
    clerk_id: str = Query(...)
):
    try:
        headers = {"X-Uploadthing-Api-Key": UPLOADTHING_SECRET}
        delete_url = "https://api.uploadthing.com/api/deleteFiles"
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                delete_url,
                headers=headers,
                json={"fileKeys": [file_key]}
            ) as response:
                response_text = await response.text()
                if response.status != 200:
                    raise HTTPException(
                        status_code=500,
                        detail=f"Failed to delete file from UploadThing: {response_text}"
                    )
                return {"message": "File deleted successfully from UploadThing"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {str(e)}")

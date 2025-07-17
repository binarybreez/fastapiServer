from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File
import os
from datetime import datetime
from app.utils.parser import parse_resume
from fastapi.responses import JSONResponse
from app.controllers.user import update_user_profile_from_resume, UserCRUD
from app.models.user import Role
from app.db import db

router = APIRouter()


@router.post("/upload")
async def upload_resume(
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

        os.makedirs("uploads", exist_ok=True)
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)

        # Update user profile with resume info
        resume_data = await parse_resume(file_path)
        user_crud = UserCRUD(db.users)
        print(user_role)
        
        response = await update_user_profile_from_resume(user_crud,clerk_id,resume_data,user_role)
        print(response)



        return JSONResponse(
            status_code=200,
            content={
                "message": "Resume uploaded successfully",
                "file_name": file_name,
                "result": resume_data,  # Include parsed data
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

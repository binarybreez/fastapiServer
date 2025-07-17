from fastapi import APIRouter, Depends, Form, HTTPException, UploadFile, File
import os
from datetime import datetime
from app.utils.parser import parse_resume
from fastapi.responses import JSONResponse

router = APIRouter()


@router.post("/upload")
async def upload_resume(
    clerk_id: str = Form(...),
    file: UploadFile = File(...),
    metadata: str = Form(None),  # Optional additional data
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
        # resume_data = {
        #     "file_key": file_path,
        #     "parsed_data": {"status": "pending_parsing"},  # Will be updated by parser
        #     "last_updated": datetime.utcnow(),
        # }


        return JSONResponse(
            status_code=200,
            content={
                "message": "Resume uploaded successfully",
                "file_name": file_name,
                "metadata": metadata,
                "result": resume_data,  # Include parsed data
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

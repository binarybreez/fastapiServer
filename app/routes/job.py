from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from app.models.job import JobPosting, EmploymentType, SalaryRange, Location, PyObjectId
from app.db import db
from app.controllers.job import JobCRUD

router = APIRouter()


# Dependency to get job CRUD operations
async def get_job_crud():
    yield JobCRUD(db.jobs)


# Job Posting Endpoints
@router.post("/", response_model=JobPosting, status_code=status.HTTP_201_CREATED)
async def create_job_posting(
    job_data: JobPosting,
    employer_id: str = Query(..., description="Authenticated employer's Clerk ID"),
    crud: JobCRUD = Depends(get_job_crud),
):
    """
    Create a new job posting
    """
    try:
        return await crud.create_job(job_data)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/", response_model=List[JobPosting])
async def search_jobs(
    query: Optional[str] = None,
    location: Optional[str] = None,
    employment_type: Optional[EmploymentType] = None,
    min_salary: Optional[int] = None,
    skills: Optional[List[str]] = Query(None),
    limit: int = 20,
    skip: int = 0,
    crud: JobCRUD = Depends(get_job_crud),
):
    """
    Search for jobs with various filters
    """
    try:
        return await crud.search_jobs(
            query=query,
            location=location,
            employment_type=employment_type,
            min_salary=min_salary,
            skills=skills,
            limit=limit,
            skip=skip,
        )
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{job_id}", response_model=JobPosting)
async def get_job_details(job_id: PyObjectId, crud: JobCRUD = Depends(get_job_crud)):
    """
    Get details of a specific job posting
    """
    try:
        return await crud.get_job_by_id(job_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
        )


@router.put("/{job_id}", response_model=JobPosting)
async def update_job_posting(
    job_id: PyObjectId,
    update_data: dict,
    employer_id: str = Query(..., description="Authenticated employer's Clerk ID"),
    crud: JobCRUD = Depends(get_job_crud),
):
    """
    Update a job posting (only by the employer who created it)
    """
    try:
        return await crud.update_job(job_id, update_data, employer_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.patch("/{job_id}/status", response_model=JobPosting)
async def update_job_status(
    job_id: PyObjectId,
    is_active: bool,
    employer_id: str = Query(..., description="Authenticated employer's Clerk ID"),
    crud: JobCRUD = Depends(get_job_crud),
):
    """
    Activate or deactivate a job posting
    """
    try:
        return await crud.update_job(job_id, {"is_active": is_active}, employer_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_job_posting(
    job_id: PyObjectId,
    employer_id: str = Query(..., description="Authenticated employer's Clerk ID"),
    crud: JobCRUD = Depends(get_job_crud),
):
    """
    Delete a job posting
    """
    try:
        await crud.delete_job(job_id, employer_id)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Job Application Endpoints
@router.post("/{job_id}/applications", status_code=status.HTTP_201_CREATED)
async def apply_to_job(
    job_id: PyObjectId,
    cover_letter: Optional[str] = None,
    resume_file: Optional[UploadFile] = File(None),
    user_id: str = Query(..., description="Authenticated user's Clerk ID"),
    crud: JobCRUD = Depends(get_job_crud),
):
    """
    Apply to a job posting
    """
    try:
        # Handle file upload if provided
        resume_id = None
        if resume_file:
            # Save file and get reference ID (implement your file handling logic)
            resume_id = "file_123"  # Replace with actual file handling

        return await crud.add_job_application(job_id, user_id, resume_id, cover_letter)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{job_id}/applications", response_model=List[dict])
async def get_job_applications(
    job_id: PyObjectId,
    employer_id: str = Query(..., description="Authenticated employer's Clerk ID"),
    crud: JobCRUD = Depends(get_job_crud),
):
    """
    Get applications for a job (only accessible to the employer)
    """
    try:
        job = await crud.get_job_by_id(job_id)
        if job.employer_id != employer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Not authorized to view these applications",
            )
        return job.applications
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/applications/{application_id}", response_model=dict)
async def update_application_status(
    application_id: PyObjectId,
    status: str = Query(..., regex="^(pending|reviewed|interview|rejected|accepted)$"),
    employer_id: str = Query(..., description="Authenticated employer's Clerk ID"),
    crud: JobCRUD = Depends(get_job_crud),
):
    """
    Update application status (employer only)
    """
    try:
        return await crud.update_application_status(application_id, employer_id, status)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


# Employer Job Management
@router.get("/employer/{employer_id}", response_model=List[JobPosting])
async def get_employer_jobs(
    employer_id: str, active_only: bool = True, crud: JobCRUD = Depends(get_job_crud)
):
    """
    Get all jobs posted by an employer
    """
    try:
        jobs = await crud.get_jobs_by_employer(employer_id)
        if active_only:
            jobs = [job for job in jobs if job.is_active]
        return jobs
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

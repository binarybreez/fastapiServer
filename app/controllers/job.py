from typing import List, Optional, Dict
from datetime import datetime, timedelta
from bson import ObjectId
from fastapi import HTTPException
from pydantic import BaseModel, Field
from app.models.job import (
    JobPosting,
    EmploymentType,
    SalaryRange,
    Location,
    PyObjectId
)
from app.utils.parser import extract_job_data

class JobCRUD:
    def __init__(self, db_collection):
        self.collection = db_collection

    async def create_job(self, job_data: str, employer_id:str) -> JobPosting:
        """Create a new job posting"""
        response = await extract_job_data(job_data)
        # job_dict = response.model_dump()
        response["employer_id"] = employer_id
        response["posted_at"] = datetime.utcnow()
        response["expires_at"] = datetime.utcnow() + timedelta(days=30)
        print(response)
        
        result = await self.collection.insert_one(response)
        if not result.inserted_id:
            raise HTTPException(status_code=500, detail="Failed to create job posting")
        
        return await self.get_job_by_id(str(result.inserted_id))

    async def get_job_by_id(self, job_id: PyObjectId) -> JobPosting:
        """Get a job by its ID"""
        job = await self.collection.find_one({"_id": ObjectId(job_id)})
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        job["_id"] = str(job["_id"])
        return JobPosting(**job)

    async def get_jobs_by_employer(self, employer_id: str) -> List[JobPosting]:
        """Get all jobs posted by an employer"""
        cursor = self.collection.find({"employer_id": employer_id})
        return [JobPosting(**job) async for job in cursor]

    async def get_active_jobs(self, limit: int = 100, skip: int = 0) -> List[JobPosting]:
        """Get all active job postings"""
        cursor = self.collection.find(
            {"is_active": True, "expires_at": {"$gt": datetime.utcnow()}}
        ).skip(skip).limit(limit)
        jobs = []
        async for job in cursor:
            job["_id"] = str(job["_id"])  # ✅ Convert ObjectId to string
            jobs.append(JobPosting(**job))

        return jobs

    async def search_jobs(
        self,
        query: Optional[str] = None,
        location: Optional[str] = None,
        employment_type: Optional[EmploymentType] = None,
        min_salary: Optional[int] = None,
        skills: Optional[List[str]] = None,
        limit: int = 100,
        skip: int = 0
    ) -> List[JobPosting]:
        """Search for jobs with various filters"""
        search_filter = {"is_active": True, "expires_at": {"$gt": datetime.utcnow()}}
        
        if query:
            search_filter["$text"] = {"$search": query}
        
        if location:
            search_filter["$or"] = [
                {"location.city": {"$regex": location, "$options": "i"}},
                {"location.country": {"$regex": location, "$options": "i"}},
                {"location.remote": True} if location.lower() == "remote" else None
            ]
        
        if employment_type:
            search_filter["employment_type"] = employment_type
        
        if min_salary:
            search_filter["salary.min"] = {"$gte": min_salary}
        
        if skills:
            search_filter["skills_required"] = {"$all": skills}
        
        cursor = self.collection.find(search_filter).skip(skip).limit(limit)
        return [JobPosting(**job) async for job in cursor]

    async def update_job(
        self, 
        job_id: PyObjectId, 
        update_data: Dict,
        employer_id: Optional[str] = None
    ) -> JobPosting:
        """Update a job posting"""
        if employer_id:
            # Verify the job belongs to this employer
            existing = await self.collection.find_one(
                {"_id": ObjectId(job_id), "employer_id": employer_id}
            )
            if not existing:
                raise HTTPException(
                    status_code=403, 
                    detail="Not authorized to update this job"
                )
        
        result = await self.collection.update_one(
            {"_id": ObjectId(job_id)},
            {"$set": update_data}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Job not found or no changes made")
            
        return await self.get_job_by_id(job_id)

    async def deactivate_job(self, job_id: PyObjectId, employer_id: str) -> JobPosting:
        """Deactivate a job posting"""
        return await self.update_job(
            job_id,
            {"is_active": False},
            employer_id
        )

    async def extend_job_expiry(
        self, 
        job_id: PyObjectId, 
        employer_id: str,
        days: int = 30
    ) -> JobPosting:
        """Extend a job posting's expiry date"""
        return await self.update_job(
            job_id,
            {"expires_at": datetime.utcnow() + timedelta(days=days)},
            employer_id
        )

    async def delete_job(self, job_id: PyObjectId, employer_id: str) -> bool:
        """Delete a job posting"""
        result = await self.collection.delete_one(
            {"_id": ObjectId(job_id), "employer_id": employer_id}
        )
        if result.deleted_count == 0:
            raise HTTPException(
                status_code=404, 
                detail="Job not found or not authorized to delete"
            )
        return True

    async def add_job_application(
        self,
        job_id: PyObjectId,
        user_id: str,
        resume_id: Optional[str] = None,
        cover_letter: Optional[str] = None
    ) -> bool:
        """Add a job application to a job posting"""
        application = {
            "user_id": user_id,
            "applied_at": datetime.utcnow(),
            "status": "submitted",
            "resume_id": resume_id,
            "cover_letter": cover_letter
        }
        
        result = await self.collection.update_one(
            {"_id": ObjectId(job_id)},
            {"$push": {"applications": application}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(status_code=404, detail="Job not found")
        return True

    async def update_application_status(
        self,
        job_id: PyObjectId,
        application_id: PyObjectId,
        employer_id: str,
        status: str
    ) -> bool:
        """Update an application status"""
        result = await self.collection.update_one(
            {
                "_id": ObjectId(job_id),
                "employer_id": employer_id,
                "applications._id": ObjectId(application_id)
            },
            {"$set": {"applications.$.status": status}}
        )
        
        if result.modified_count == 0:
            raise HTTPException(
                status_code=404,
                detail="Job, application not found or not authorized"
            )
        return True
    

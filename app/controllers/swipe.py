from fastapi import HTTPException, status
from datetime import datetime
from typing import List, Optional
from app.models.user import PyObjectId
from bson import ObjectId


class SwipeCRUD:
    def __init__(self, swipe_collection,jobs_collection):
        self.collection = swipe_collection
        self.job_collection = jobs_collection

    async def create_swipe(
        self, swiper_id: str, target_id: str, swipe_type: str  # "like" or "pass"
    ) -> dict:
        """Record a swipe action"""
        job_object_id = ObjectId(target_id)
        swipe_data = {
        "user_id": swiper_id,                  # ✅ matches Mongo index
        "job_id": job_object_id,          # ✅ stored as ObjectId
        "swipe_type": swipe_type,
        "swiped_at": datetime.utcnow(),
        "matched": False,
    }

        result = await self.collection.insert_one(swipe_data)
        if not result.inserted_id:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to record swipe",
            )

        # Check for potential match
        if swipe_type == "like":
            return await self.check_match(swiper_id, target_id)
        return {"status": "swipe_recorded"}

    async def get_liked_jobs_by_user(self, clerk_id: str) -> list[dict]:
        """Fetch full job postings liked by a user (via Clerk ID)"""
        swipes_cursor = self.collection.find(
            {"user_id": clerk_id, "swipe_type": "like"}
        )

        liked_jobs = []
        async for swipe in swipes_cursor:
            try:
                job_id = ObjectId(swipe["job_id"])
            except Exception:
                continue  # skip invalid ids

            job = await self.job_collection.find_one({"_id": job_id})
            if job:
                job["_id"] = str(job["_id"])  # convert ObjectId → str for JSON
                liked_jobs.append(job)

        return liked_jobs
    
    async def check_match(self, user1_id: str, user2_id: str) -> dict:
        """Check if two users have liked each other"""
        mutual_swipe = await self.collection.find_one(
            {"swiper_id": user2_id, "target_id": user1_id, "swipe_type": "like"}
        )

        if mutual_swipe:
            # Update both swipe records to mark as matched
            await self.collection.update_many(
                {
                    "$or": [
                        {"swiper_id": user1_id, "target_id": user2_id},
                        {"swiper_id": user2_id, "target_id": user1_id},
                    ]
                },
                {"$set": {"matched": True}},
            )
            return {"status": "match", "match_id": str(mutual_swipe["_id"])}
        return {"status": "like_recorded"}

    async def get_user_matches(
        self, user_id: str, limit: int = 100, skip: int = 0
    ) -> List[dict]:
        """Get all matches for a user"""
        matches = (
            await self.collection.find(
                {
                    "$or": [{"swiper_id": user_id}, {"target_id": user_id}],
                    "matched": True,
                }
            )
            .skip(skip)
            .limit(limit)
            .to_list(None)
        )

        return [
            {
                "match_id": str(match["_id"]),
                "users": [match["swiper_id"], match["target_id"]],
                "matched_at": match["swiped_at"],
            }
            for match in matches
            if match["swiper_id"] == user_id  # Only return once per match
        ]

    async def get_swipe_history(
        self,
        user_id: str,
        swipe_type: Optional[str] = None,
        limit: int = 100,
        skip: int = 0,
    ) -> List[dict]:
        """Get user's swipe history"""
        query = {"swiper_id": user_id}
        if swipe_type:
            query["swipe_type"] = swipe_type

        swipes = await self.collection.find(query).skip(skip).limit(limit).to_list(None)
        return [
            {
                "target_id": swipe["target_id"],
                "swipe_type": swipe["swipe_type"],
                "swiped_at": swipe["swiped_at"],
                "matched": swipe.get("matched", False),
            }
            for swipe in swipes
        ]

    async def delete_match(self, user_id: str, match_id: PyObjectId) -> bool:
        """Remove a match (unmatch)"""
        result = await self.collection.delete_one(
            {
                "_id": ObjectId(match_id),
                "$or": [{"swiper_id": user_id}, {"target_id": user_id}],
                "matched": True,
            }
        )
        return result.deleted_count > 0


# Dependency

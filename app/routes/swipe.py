from fastapi import APIRouter, Query, Depends, HTTPException, status
from app.db import db
from typing import List, Optional
from app.controllers.swipe import SwipeCRUD
from app.models.user import PyObjectId


router = APIRouter()


async def get_swipe_crud():
    yield SwipeCRUD(db.swipes,db.jobs)  # Assuming you have a 'swipes' collection


# Endpoints
@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_swipe(
    target_id: str,
    swipe_type: str = Query(..., regex="^(like|pass)$"),
    user_id: str = Query(..., description="Current user's Clerk ID"),
    crud: SwipeCRUD = Depends(get_swipe_crud),
):
    """Record a swipe action"""
    try:
        return await crud.create_swipe(user_id, target_id, swipe_type)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/like/{user_id}", response_model=List[dict])
async def get_liked_jobs(
    user_id: str,
    crud: SwipeCRUD = Depends(get_swipe_crud),
):
    """Get jobs liked by a user"""
    try:
        return await crud.get_liked_jobs_by_user(user_id)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/matches", response_model=List[dict])
async def get_matches(
    user_id: str = Query(..., description="Current user's Clerk ID"),
    limit: int = 20,
    skip: int = 0,
    crud: SwipeCRUD = Depends(get_swipe_crud),
):
    """Get user's matches"""
    try:
        return await crud.get_user_matches(user_id, limit, skip)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/history", response_model=List[dict])
async def get_history(
    user_id: str = Query(..., description="Current user's Clerk ID"),
    swipe_type: Optional[str] = Query(None, regex="^(like|pass)$"),
    limit: int = 50,
    skip: int = 0,
    crud: SwipeCRUD = Depends(get_swipe_crud),
):
    """Get swipe history"""
    try:
        return await crud.get_swipe_history(user_id, swipe_type, limit, skip)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/matches/{match_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_match(
    match_id: PyObjectId,
    user_id: str = Query(..., description="Current user's Clerk ID"),
    crud: SwipeCRUD = Depends(get_swipe_crud),
):
    """Remove a match"""
    try:
        success = await crud.delete_match(user_id, match_id)
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Match not found or not authorized",
            )
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

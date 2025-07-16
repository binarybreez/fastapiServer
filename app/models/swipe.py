from datetime import datetime
from enum import Enum
from bson import ObjectId
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional
from .user import PyObjectId

class SwipeType(str, Enum):
    LIKE = "like"
    DISLIKE = "dislike"
    SAVE = "save"
    APPLY = "apply"
    SUPER_LIKE = "super_like"

class SwipeMeta(BaseModel):
    swipe_time_ms: int
    session_id: str
    device_type: Optional[str] = None

class UserSwipe(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    id: PyObjectId = Field(default_factory=lambda: str(ObjectId()), alias="_id")
    user_id: str
    job_id: str
    action: SwipeType
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    undone: bool = False
    undone_at: Optional[datetime] = None
    meta: Optional[SwipeMeta] = None
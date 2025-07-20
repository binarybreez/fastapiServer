from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import IndexModel, ASCENDING, DESCENDING, GEOSPHERE
import os
from dotenv import load_dotenv

load_dotenv()


class MongoDB:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self):
        self.client = None
        self.db = None

    async def connect(self):
        MONGO_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        self.client = AsyncIOMotorClient(MONGO_URI)
        self.db = self.client.jobswipe_prod

        # Initialize collections with indexes
        await self._init_users()
        await self._init_jobs()
        await self._init_swipes()
        print("✅ MongoDB connected and indexes created")

    async def _init_users(self):
        await self.db.users.create_indexes(
            [
                IndexModel([("clerk_id", ASCENDING)], unique=True),
                IndexModel([("email", ASCENDING)], unique=True),
                IndexModel([("role", ASCENDING)]),
                IndexModel([("location", "text")]),
                IndexModel([("skills", ASCENDING)]),
            ]
        )

    async def _init_jobs(self):
        await self.db.jobs.create_indexes(
            [
                IndexModel([("employer_id", ASCENDING)]),
                IndexModel([("skills_required", ASCENDING)]),
                IndexModel([("location.coordinates", GEOSPHERE)]),
                IndexModel([("is_active", ASCENDING), ("expires_at", ASCENDING)]),
                IndexModel([("title", "text"), ("description", "text")]),
            ]
        )

    async def _init_swipes(self):
        await self.db.swipes.create_indexes(
            [
                IndexModel(
                    [("user_id", ASCENDING), ("job_id", ASCENDING)], unique=True
                ),
                IndexModel([("timestamp", DESCENDING)]),
                IndexModel([("action", ASCENDING)]),
            ]
        )

    async def close(self):
        if self.client:
            self.client.close()
            print("🔌 MongoDB connection closed")

    # Collection accessors with type hints
    @property
    def users(self):
        return self.db.users

    @property
    def jobs(self):
        return self.db.jobs

    @property
    def swipes(self):
        return self.db.swipes


# Singleton instance
db = MongoDB()

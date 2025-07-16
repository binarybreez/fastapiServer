from fastapi import FastAPI, Depends, HTTPException
from app.db import db
from app.models.user import UserProfile
import os

app = FastAPI()

@app.on_event("startup")
async def startup():
    await db.connect()

@app.on_event("shutdown")
async def shutdown():
    await db.close()

@app.get("/", response_model=dict)
async def read_root():
    return {"message": "Welcome to the Job Swipe API"}
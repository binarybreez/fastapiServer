from fastapi import FastAPI
from app.db import db
from fastapi.middleware.cors import CORSMiddleware
from app.routes import auth, user, job, swipe
from fastapi.staticfiles import StaticFiles


app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/public", StaticFiles(directory="public"), name="public")


@app.on_event("startup")
async def startup():
    await db.connect()


@app.on_event("shutdown")
async def shutdown():
    await db.close()


app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(user.router, prefix="/api/users")
app.include_router(job.router, prefix="/api/jobs")
app.include_router(swipe.router, prefix="/api/swipes")


@app.get("/", response_model=dict)
async def read_root():
    return {"message": "Welcome to the Job Swipe API"}

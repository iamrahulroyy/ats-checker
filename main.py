from fastapi import FastAPI
import uvicorn
from app.atsChecker.atsCheckerApi import ats_router
from fastapi.middleware.cors import CORSMiddleware
from database.db import init_db

app = FastAPI()

app.include_router(ats_router)


@app.on_event("startup")
async def startup():
    print("Initializing database...")
    init_db()
    print("App has started!")


@app.on_event("shutdown")
async def shutdown():
    print("App is shutting down!")


origins = [
    "http://localhost:3000",
    "https://ats-checker-production.up.railway.app",
    "https://ats-checker-production.up.railway.app:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

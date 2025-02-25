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


app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

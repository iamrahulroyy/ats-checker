from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from sqlmodel import Session, select
from app.atsChecker.atsChecker import ATSFunctions
from database.db import get_session
from database.dbModels import Resume


ats_router = APIRouter()

ats_functions = ATSFunctions()

@ats_router.post("/upload_resume/")
async def upload_resume(file: UploadFile = File(...), session: Session = Depends(get_session)):
    try:
        ats_score = await ats_functions.upload_resume(file, session)
        
        return {"filename": file.filename, "ats_score": ats_score, "message": "File uploaded successfully."}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")


@ats_router.get("/resumes/{resume_id}")
async def get_resume(resume_id: int, session: Session = Depends(get_session)):
    resume = session.get(Resume, resume_id)
    if resume is None:
        raise HTTPException(status_code=404, detail="Resume not found")
    return {"id": resume.id, "filename": resume.filename, "file_size": resume.file_size, "file_url": resume.file_url}

@ats_router.get("/resumes/")
async def list_resumes(session: Session = Depends(get_session)):
    resumes = session.exec(select(Resume)).all()
    return resumes

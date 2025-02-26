from fastapi import APIRouter, File, UploadFile, HTTPException, Depends
from sqlmodel import Session, select
from app.atsChecker.atsChecker import ATSFunctions
from database.db import get_session
from database.dbModels import Resume
import logging

logger = logging.getLogger(__name__)
ats_router = APIRouter()
ats_functions = ATSFunctions()


@ats_router.get("/resumes/")
def list_resumes(session: Session = Depends(get_session)):
    """List all resumes"""
    try:
        query = select(Resume)
        result = session.execute(query)
        resumes = result.scalars().all()
        return resumes
    except Exception as e:
        logger.error(f"Error fetching resumes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ats_router.get("/resumes/{resume_id}")
def get_resume(resume_id: int, session: Session = Depends(get_session)):
    try:
        resume = session.get(Resume, resume_id)
        if resume is None:
            raise HTTPException(status_code=404, detail="Resume not found")
        return resume
    except Exception as e:
        logger.error(f"Error fetching resume {resume_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@ats_router.post("/upload_resume/")
async def upload_resume(
    file: UploadFile = File(...), session: Session = Depends(get_session)
):
    try:
        ats_score = await ats_functions.upload_resume(file, session)
        return {
            "filename": file.filename,
            "ats_score": ats_score,
            "message": "File uploaded successfully.",
        }
    except Exception as e:
        logger.error(f"Error processing file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

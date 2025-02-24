import os
import httpx
from io import BytesIO
from fastapi import UploadFile, HTTPException
from sqlmodel import Session
from database.dbModels import Resume
from dotenv import load_dotenv
from PyPDF2 import PdfReader

load_dotenv()


class ATSFunctions:
    def __init__(self):
        self.groq_api_url = os.getenv("GROQ_API_URL")
        self.api_key = os.getenv("GROQ_API_KEY")

    @staticmethod
    def extract_text_from_pdf(contents: bytes) -> str:
        try:
            pdf_file = BytesIO(contents)
            pdf_reader = PdfReader(pdf_file)
            text = ""
            for page in pdf_reader.pages:
                text += page.extract_text() + "\n"
            return text
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error extracting text from PDF: {str(e)}"
            )

    @staticmethod
    def validate_file_extension(filename: str) -> str:
        file_extension = filename.split(".")[-1].lower()
        if file_extension not in ["pdf", "doc", "docx"]:
            raise HTTPException(
                status_code=400,
                detail="Invalid file format. Only PDF and DOC/DOCX are allowed.",
            )
        return file_extension

    @staticmethod
    def save_file(contents: bytes, filename: str) -> str:
        temp_dir = "uploads"
        os.makedirs(temp_dir, exist_ok=True)
        file_path = os.path.join(temp_dir, filename)
        with open(file_path, "wb") as f:
            f.write(contents)
        return file_path

    @staticmethod
    def save_resume_to_db(
        session: Session, filename: str, file_size: int, file_url: str
    ) -> Resume:
        try:
            resume = Resume(filename=filename, file_size=file_size, file_url=file_url)
            session.add(resume)
            session.commit()
            session.refresh(resume)
            return resume
        except Exception as db_error:
            session.rollback()
            raise HTTPException(
                status_code=500, detail=f"Database error: {str(db_error)}"
            )

    @staticmethod
    async def extract_text_from_file(contents: bytes, file_extension: str) -> str:
        if file_extension == "pdf":
            return ATSFunctions.extract_text_from_pdf(contents)
        else:
            raise HTTPException(
                status_code=400, detail="Only PDF files are currently supported"
            )

    @staticmethod
    async def upload_resume(file: UploadFile, session: Session):
        try:
            file_extension = ATSFunctions.validate_file_extension(file.filename)
            contents = await file.read()
            file_size = len(contents)

            text_content = await ATSFunctions.extract_text_from_file(
                contents, file_extension
            )
            file_path = ATSFunctions.save_file(contents, file.filename)
            resume = ATSFunctions.save_resume_to_db(
                session, file.filename, file_size, file_path
            )

            ats_score = await ATSFunctions.check_ats_score(text_content)
            return {"resume_id": resume.id, "ats_score": ats_score}
        except HTTPException as he:
            raise he
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Error processing file: {str(e)}"
            )

    @staticmethod
    def create_ats_prompt(text_content: str) -> dict:
        system_prompt = """You are an expert ATS (Applicant Tracking System) analyzer. Your task is to:
            1. Analyze the given resume
            2. Provide a score from 0-100
            3. Give brief feedback
            4. List specific improvements
            5. Add predicted job fit based on the resume with percentage of getting selected
            Format your response exactly as a JSON object:
            {
                "ats_score": <number between 0-100>,
                "feedback": "<single sentence summary>",
                "improvements": ["point 1", "point 2", "point 3"],
                "job_fit": {
                    "job_title": "<most suitable job title>",
                    "fit_percentage": <number between 0-100>
                }
            }"""
        user_prompt = f"Analyze this resume:\n{text_content}"
        return {
            "model": "mixtral-8x7b-32768",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.7,
            "max_tokens": 1000,
            "response_format": {"type": "json_object"},  
        }

    @staticmethod
    async def call_groq_api(payload: dict) -> dict:
        async with httpx.AsyncClient() as client:
            headers = {
                "Authorization": f"Bearer {os.getenv('GROQ_API_KEY')}",
                "Content-Type": "application/json",
            }

            response = await client.post(
                os.getenv("GROQ_API_URL"), json=payload, headers=headers
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    def parse_api_response(result: dict) -> dict:
        try:
            response_content = result["choices"][0]["message"]["content"]
            import json

            parsed_response = json.loads(response_content.strip())

            required_keys = ["ats_score", "feedback", "improvements"]
            if not all(key in parsed_response for key in required_keys):
                raise ValueError("Missing required fields in API response")

            parsed_response["ats_score"] = max(
                0, min(100, int(float(str(parsed_response["ats_score"]))))
            )

            return parsed_response
        except (KeyError, json.JSONDecodeError, ValueError) as e:
            raise Exception(f"Invalid API response format: {str(e)}")

    @staticmethod
    async def check_ats_score(text_content: str) -> dict:
        try:
            payload = ATSFunctions.create_ats_prompt(text_content)
            result = await ATSFunctions.call_groq_api(payload)
            return ATSFunctions.parse_api_response(result)
        except httpx.RequestError as e:
            raise HTTPException(
                status_code=500,
                detail=f"An error occurred while requesting ATS score: {str(e)}",
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Error processing resume with Groq API: {str(e)}",
            )

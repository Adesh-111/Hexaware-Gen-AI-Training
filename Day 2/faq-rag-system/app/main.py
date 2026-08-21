import os
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.rag import FAQRAG

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

rag = FAQRAG(ROOT / "data" / "company_faq.md")


@asynccontextmanager
async def lifespan(_: FastAPI):
    if os.getenv("OPENAI_API_KEY"):
        rag.initialize()
    yield


app = FastAPI(title="Company FAQ Assistant", version="1.0.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")


class QuestionRequest(BaseModel):
    question: str = Field(min_length=2, max_length=1000)


@app.get("/", include_in_schema=False)
async def home():
    return FileResponse(ROOT / "templates" / "index.html")


@app.get("/api/status")
async def status():
    configured = bool(os.getenv("OPENAI_API_KEY"))
    return {
        "ready": configured,
        "document": "Company FAQs",
        "message": "Knowledge base ready" if configured else "Add OPENAI_API_KEY to .env to start asking questions",
    }


@app.post("/api/ask")
async def ask(payload: QuestionRequest):
    if not os.getenv("OPENAI_API_KEY"):
        raise HTTPException(status_code=503, detail="OpenAI API key is not configured. Copy .env.example to .env and add your key.")
    try:
        if not rag.ready:
            rag.initialize()
        return rag.answer(payload.question.strip())
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Unable to answer right now: {exc}") from exc


@app.get("/health")
async def health():
    return {"status": "ok"}

# Atlas — Company FAQ RAG

A focused company FAQ assistant built with FastAPI, LangChain, ChromaDB, and OpenAI. It retrieves relevant sections from the local company FAQ before generating a concise, grounded response with source labels.

## Run locally

1. Create and activate a Python virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and add your OpenAI API key.
4. Start the app: `uvicorn app.main:app --reload`
5. Open `http://127.0.0.1:8000`

Edit `data/company_faq.md` to replace or expand the sample FAQ. The app automatically uses a new vector collection when the document changes.

## API

- `POST /api/ask` with `{ "question": "How do I request access?" }`
- `GET /api/status`
- `GET /health`

import logging
import uuid
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, Any

import app.core.feature_flags as ff
from app.core.config import settings
from app.services.agent.rag.store import ChromaStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])

class AskRequest(BaseModel):
    query: str
    session_id: Optional[str] = None

@router.post("/ask")
async def ask_agent(req: AskRequest) -> Any:
    if not ff.AGENT_ENABLED:
        return {"enabled": False}

    session_id = req.session_id or str(uuid.uuid4())
    store = ChromaStore(session_id=session_id)
    
    # Search ChromaStore for relevant findings
    results = await store.search(query=req.query, n_results=5)
    
    if not results:
        return {
            "answer": "No findings available for this session",
            "sources": [],
            "session_id": session_id
        }

    # Generate answer, prioritizing Gemini LLM if key is present
    answer = None
    api_key = settings.GOOGLE_API_KEY
    if api_key:
        try:
            from google import genai
            client = genai.Client(api_key=api_key)
            context = "\n".join([f"- {doc['text']}" for doc in results])
            prompt = (
                "Answer the user query based on the following findings.\n"
                f"Query: {req.query}\n"
                "Findings:\n"
                f"{context}\n"
                "Provide a concise answer."
            )
            response = client.models.generate_content(
                model="gemini-3.5-flash",
                contents=[prompt],
            )
            answer = response.text.strip()
        except Exception as e:
            logger.warning(f"Failed to generate answer with Gemini: {e}")

    # Fallback response if LLM is unavailable or fails
    if not answer:
        snippets = [doc.get("text", "").strip() for doc in results]
        answer = f"Found {len(results)} relevant source(s):\n" + "\n".join([f"- {s}" for s in snippets])

    return {
        "answer": answer,
        "sources": results,
        "session_id": session_id
    }

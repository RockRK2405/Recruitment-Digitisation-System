"""
Agent chat endpoint - forwards to the chatbot service (Ollama/Gemini).
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from config.settings import settings
from config.logging_config import logger
from services.chatbot.chatbot import call_chat_llm, get_candidate_context, get_job_descriptions_context, get_detailed_candidate_context, get_detailed_job_context

router = APIRouter()


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    provider: str


@router.post("/chat", response_model=ChatResponse)
async def agent_chat(req: ChatRequest):
    """
    Real LLM-powered HR assistant chat endpoint.
    Uses Ollama (primary) with Gemini fallback.
    """
    try:
        candidate_context = get_candidate_context()
        jobs_context = get_job_descriptions_context()
        detailed_candidate = get_detailed_candidate_context(req.message)
        detailed_job = get_detailed_job_context(req.message)

        system_prompt = f"""You are an AI HR Assistant for an industrial recruitment platform (Kshamata).
You help recruiters find, evaluate, and compare candidates for heavy industry roles.

CANDIDATE DATABASE:
{candidate_context}

JOB VACANCIES:
{jobs_context}
{detailed_candidate}
{detailed_job}

Guidelines:
- Base all answers on the actual data provided above
- Highlight safety certifications (DGMS, OSHA, Boiler, Crane, Blasting) as critical for industrial roles
- Be concise, professional, and data-driven
- If asked about candidates not listed, state they are not in the database
- When asked to compare candidates, create a structured comparison table
- Suggest specific interview questions when evaluating candidates"""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": req.message},
        ]

        response = call_chat_llm(messages)
        provider = settings.LLM_PROVIDER or "ollama"

        return ChatResponse(
            response=response,
            session_id=req.session_id or f"session-{id(req)}",
            provider=provider,
        )
    except Exception as e:
        logger.error(f"Agent chat error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Chat failed: {str(e)}")


@router.post("/pipeline")
async def trigger_pipeline(body: dict):
    """Trigger the AI processing pipeline for a candidate."""
    candidate_id = body.get("candidateId") or body.get("candidate_id")
    run_id = body.get("runId") or body.get("run_id")

    if not candidate_id:
        raise HTTPException(status_code=400, detail="candidateId required")

    logger.info(f"Pipeline triggered for candidate {candidate_id}, run {run_id}")
    return {"status": "accepted", "candidateId": candidate_id, "runId": run_id}

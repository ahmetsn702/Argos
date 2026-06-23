"""LLM OSINT analysis router."""

import os

from fastapi import APIRouter, Request

from app.core.limiter import limiter
from app.services.llm_analyst import OsintAnalyst
from app.models.llm import OsintAnalysisRequest  # canonical location

router = APIRouter(prefix="/analysis", tags=["LLM Analysis"])


@router.post("/osint")
@limiter.limit("5/minute")
async def analyze_osint(request: Request, body: OsintAnalysisRequest,
                        verbose: bool = False):
    analyst = OsintAnalyst()

    confidence_summary_data = None
    confidence_verbose_data = None
    try:
        from app.services.confidence.cache import default_cache
        from app.services.confidence.summary import confidence_summary

        email = body.data.get("email") if isinstance(body.data, dict) else None
        username = body.data.get("username") if isinstance(body.data, dict) else None

        seed_key = None
        if email:
            seed_key = f"email:{email.strip().lower()}"
        elif username:
            seed_key = f"username:{username.strip().lower()}"

        if seed_key:
            graph = default_cache.get(seed_key)
            if graph:
                summary = confidence_summary(graph)
                if verbose:
                    confidence_verbose_data = {
                        "summary": summary,
                        "findings": {
                            fid: {
                                "type": f.type.value,
                                "value": f.value,
                                "score": f.confidence_score,
                                "sources": len(f.sources),
                                "contradicted_by": f.contradicted_by,
                            }
                            for fid, f in graph.findings.items()
                        },
                    }
                else:
                    confidence_summary_data = summary
    except Exception:
        pass

    return await analyst.analyze(body.data, body.context,
                                 confidence_summary=confidence_summary_data,
                                 confidence_verbose=confidence_verbose_data)


@router.get("/health")
async def analysis_health():
    api_key = os.getenv("GOOGLE_API_KEY", "")
    return {
        "status": "ok",
        "model": OsintAnalyst.MODEL,
        "api_key": bool(api_key),
    }

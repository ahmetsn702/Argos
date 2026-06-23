from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import StreamingResponse
from typing import Optional
import io
from app.services.report_service import generate_osint_report
from app.core.limiter import limiter

router = APIRouter(prefix="/report", tags=["report"])

@router.post("/generate")
@limiter.limit("5/minute")
async def report_generate(
    request: Request,
    email: Optional[str] = Query(None),
    username: Optional[str] = Query(None),
    phone: Optional[str] = Query(None),
    timeout: float = Query(20.0, ge=5.0, le=60.0)
):
    if not any([email, username, phone]):
        raise HTTPException(status_code=400, detail="email, username veya phone gerekli")

    pdf_bytes = await generate_osint_report(email=email, username=username, phone=phone, timeout=timeout)

    filename = (email or username or phone or "rapor").replace("@", "_").replace(".", "_")
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": f"attachment; filename=footprint_{filename}.pdf"}
    )

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from typing import Optional, List, Dict, Any

import app.core.feature_flags as ff
from app.core.config import settings

# Import transform classes
from app.services.maltego.transforms.email_to_profiles import EmailToProfiles
from app.services.maltego.transforms.username_to_social import UsernameToSocial
from app.services.maltego.transforms.phone_to_identity import PhoneToIdentity
from app.services.maltego.transforms.domain_to_infra import DomainToInfra
from app.services.maltego.transforms.ip_to_geo import IpToGeo
from app.services.maltego.transforms.entity_to_confidence import EntityToConfidence

router = APIRouter(prefix="/maltego", tags=["maltego"])

TRANSFORMS = [
    EmailToProfiles(),
    UsernameToSocial(),
    PhoneToIdentity(),
    DomainToInfra(),
    IpToGeo(),
    EntityToConfidence(),
]

TRANSFORMS_MAP = {}
for t in TRANSFORMS:
    TRANSFORMS_MAP[t.name.lower()] = t
    short_name = t.name.split(".")[-1].lower()
    TRANSFORMS_MAP[short_name] = t

class TransformRequest(BaseModel):
    value: str
    type: str

def check_auth(request: Request):
    expected_key = settings.MALTEGO_API_KEY
    if expected_key is not None and expected_key.strip() != "":
        key = request.headers.get("MALTEGO_API_KEY") or request.headers.get("maltego-api-key") or request.headers.get("X-Maltego-API-Key")
        if not key or key != expected_key:
            raise HTTPException(status_code=401, detail="Unauthorized")

@router.get("/transforms")
async def list_transforms(request: Request):
    if not ff.MALTEGO_ENABLED:
        return {"enabled": False}
    check_auth(request)
    return [{"name": t.name, "display_name": t.display_name} for t in TRANSFORMS]

@router.post("/transform/{transform_name}")
async def run_transform(transform_name: str, req: TransformRequest, request: Request):
    if not ff.MALTEGO_ENABLED:
        return {"enabled": False}
    check_auth(request)
    
    key = transform_name.lower().strip()
    transform = TRANSFORMS_MAP.get(key)
    if not transform:
        raise HTTPException(status_code=404, detail="Transform not found")
        
    try:
        entities = await transform.run(req.value)
        return {"entities": entities}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

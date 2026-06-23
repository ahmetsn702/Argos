from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import Any

import app.core.feature_flags as ff
from app.services.agent.playbook.parser import PlaybookParser
from app.services.agent.playbook.validator import PlaybookValidator
from app.services.agent.playbook.storage import PlaybookStorage

router = APIRouter(prefix="/agent", tags=["playbook"])

class ParseRequest(BaseModel):
    nl_text: str

# Module-level singletons
_parser = PlaybookParser()
_validator = PlaybookValidator()
_storage = PlaybookStorage()

@router.post("/playbook/parse")
async def parse_playbook(req: ParseRequest) -> Any:
    if not ff.AGENT_ENABLED:
        return {"enabled": False}
    
    parsed = await _parser.parse(req.nl_text)
    return parsed

@router.post("/playbook/save")
async def save_playbook(playbook: dict) -> Any:
    if not ff.AGENT_ENABLED:
        return {"enabled": False}
    
    is_valid, err_msg = _validator.validate(playbook)
    if not is_valid:
        return JSONResponse(status_code=400, content={"error": err_msg})
    
    playbook_id = await _storage.save(playbook)
    return {"id": playbook_id}

@router.get("/playbook/list")
async def list_playbooks() -> Any:
    if not ff.AGENT_ENABLED:
        return {"enabled": False}
    
    playbooks = await _storage.list_all()
    return playbooks

@router.delete("/playbook/{id}")
async def delete_playbook(id: str) -> Any:
    if not ff.AGENT_ENABLED:
        return {"enabled": False}
    
    deleted = await _storage.delete(id)
    return {"deleted": deleted}

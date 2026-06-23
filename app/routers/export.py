from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import io

import app.core.feature_flags as ff
from app.services.confidence.cache import default_cache
from app.services.maltego.mtgx_builder import MtgxBuilder

router = APIRouter(prefix="/export", tags=["export"])

@router.get("/maltego")
async def export_maltego(seed_key: str = Query(...)):
    if not ff.MALTEGO_ENABLED:
        return {"enabled": False}
        
    graph = default_cache.get(seed_key)
    if graph is None:
        raise HTTPException(status_code=404, detail="Graph not found")
        
    findings = []
    for fid, f in graph.findings.items():
        finding_type = f.type.value if hasattr(f.type, "value") else str(f.type)
        findings.append({
            "id": f.id,
            "type": finding_type,
            "value": f.value,
            "confidence": f.confidence_score
        })
        
    edges = []
    for e in graph.edges:
        rel_type = e.edge_type.value if hasattr(e.edge_type, "value") else str(e.edge_type)
        edges.append({
            "from_id": e.source_id,
            "to_id": e.target_id,
            "rel_type": rel_type,
            "weight": e.weight
        })
        
    graph_data = {
        "findings": findings,
        "edges": edges
    }
    
    builder = MtgxBuilder()
    mtgx_bytes = builder.build(graph_data)
    
    return StreamingResponse(
        io.BytesIO(mtgx_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename=argos_{seed_key}.mtgx"}
    )

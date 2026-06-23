from fastapi import APIRouter
from fastapi.responses import FileResponse
import os

router = APIRouter()
_HTML = os.path.join(os.path.dirname(__file__), "../../ui/mini_panel.html")


@router.get("/mini", response_class=FileResponse)
def mini_panel():
    return FileResponse(_HTML, media_type="text/html")

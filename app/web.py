from pathlib import Path

from fastapi.responses import FileResponse

_WEB_ROOT = Path(__file__).parent / "web"


def frontend() -> FileResponse:
    return FileResponse(_WEB_ROOT / "index.html")

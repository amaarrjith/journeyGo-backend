import os
import sys
from pathlib import Path

# Add the backend project root to sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

try:
    from app.main import app
except Exception as e:
    import traceback
    from fastapi import FastAPI
    from fastapi.responses import JSONResponse

    app = FastAPI(title="JourneyGo AI Backend - Error Mode")
    err_tb = traceback.format_exc()

    @app.api_route("/{path_name:path}", methods=["GET", "POST", "PUT", "DELETE"])
    async def debug_catch_all(path_name: str = ""):
        return JSONResponse(
            status_code=500,
            content={
                "error": "Failed to initialize JourneyGo FastAPI application",
                "exception": str(e),
                "traceback": err_tb,
                "sys_path": sys.path
            }
        )

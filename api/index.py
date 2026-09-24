from __future__ import annotations
import os
import sys
from pathlib import Path

# Add current api directory and parent directory to sys.path
api_dir = Path(__file__).resolve().parent
parent_dir = api_dir.parent

for p in (str(api_dir), str(parent_dir)):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from app.main import app
except ImportError:
    from api.app.main import app

# Export AWS Lambda / Vercel handler via Mangum
try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except Exception:
    pass

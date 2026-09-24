from __future__ import annotations
import os
import sys
from pathlib import Path

# Add backend root to sys.path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.main import app

# Provide AWS Lambda / Vercel ASGI handler via Mangum if available
try:
    from mangum import Mangum
    handler = Mangum(app, lifespan="off")
except Exception:
    pass

import os
import sys
from pathlib import Path

# Add the backend project root to sys.path so 'app' imports resolve properly on Vercel
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.main import app

# Vercel serverless function entrypoint
# The ASGI 'app' instance is exported here for Vercel's Python runtime.

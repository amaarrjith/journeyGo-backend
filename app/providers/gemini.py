"""
Google Gemini Provider implementation via Google AI Studio API.
Leverages Gemini's high-speed free tier (1,500 requests/day, 15 RPM)
with native response_mime_type='application/json' for guaranteed structured outputs.
"""

import httpx
import logging
from .base import LLMProvider
from ..config import settings

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.llm_model or "gemini-1.5-flash"
        self.timeout = httpx.Timeout(20.0, connect=5.0)

    async def generate_json(self, prompt: str, system_prompt: str | None = None) -> str:
        """
        Sends generation request to Google Gemini API using native JSON output mode.
        """
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not set. Please add GEMINI_API_KEY to backend/.env")

        # Build candidate models to try: specified model first, then known robust fallbacks
        models_to_try = [self.model]
        for fb in ["gemini-3.6-flash", "gemini-3.1-flash-lite", "gemini-flash-latest"]:
            if fb not in models_to_try:
                models_to_try.append(fb)

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "generationConfig": {
                "response_mime_type": "application/json",
                "temperature": 0.1,
                "topP": 0.95
            }
        }

        if system_prompt:
            payload["system_instruction"] = {
                "parts": [{"text": system_prompt}]
            }

        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": self.api_key
        }

        last_error = None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for model_name in models_to_try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                try:
                    response = await client.post(url, headers=headers, json=payload)
                    if response.status_code in (404, 503):
                        logger.warning(f"[GeminiProvider] Model {model_name} returned {response.status_code}, trying fallback...")
                        last_error = RuntimeError(f"HTTP {response.status_code}: {response.text}")
                        continue

                    response.raise_for_status()
                    data = response.json()

                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise RuntimeError("Gemini returned no candidates in response.")

                    content_parts = candidates[0].get("content", {}).get("parts", [])
                    if not content_parts:
                        raise RuntimeError("Gemini returned empty content parts.")

                    json_text = content_parts[0].get("text", "")
                    logger.info(f"[GeminiProvider] Received {len(json_text)} bytes from {model_name}")
                    return json_text.strip()

                except (httpx.HTTPStatusError, RuntimeError) as e:
                    last_error = e
                    logger.warning(f"[GeminiProvider] Error with {model_name}: {e}. Trying next model...")
                    continue
                except httpx.ConnectError as e:
                    logger.error(f"[GeminiProvider] Network connection error: {e}")
                    raise ConnectionError("Unable to reach Google Gemini API endpoints.") from e
                except Exception as e:
                    logger.error(f"[GeminiProvider] Unexpected error with {model_name}: {e}")
                    last_error = e
                    continue

        raise RuntimeError(f"All Gemini models failed. Last error: {last_error}")

    async def is_available(self) -> bool:
        """Checks if GEMINI_API_KEY is configured and valid."""
        return bool(self.api_key and len(self.api_key) > 10)

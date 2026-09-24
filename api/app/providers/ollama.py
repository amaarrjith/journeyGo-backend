"""
Ollama LLM Provider implementation.
Communicates with a locally running Ollama instance via its HTTP API.
Enforces JSON-mode inference (format="json") with low temperature for deterministic parsing.
"""

import httpx
import logging
from .base import LLMProvider
from ..config import settings

logger = logging.getLogger(__name__)


class OllamaProvider(LLMProvider):

    def __init__(self, base_url: str | None = None, model: str | None = None):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.llm_model
        self.timeout = httpx.Timeout(20.0, connect=5.0)

    async def generate_json(self, prompt: str, system_prompt: str | None = None) -> str:
        """
        Sends generation request to Ollama using format='json'.
        """
        url = f"{self.base_url}/api/chat"

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "format": "json",
            "stream": False,
            "options": {
                "temperature": 0.1,
                "top_p": 0.9,
            }
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(url, json=payload)
                response.raise_for_status()
                data = response.json()
                content = data.get("message", {}).get("content", "")
                return content.strip()
            except httpx.ConnectError as e:
                logger.error(f"[OllamaProvider] Failed to connect to Ollama at {self.base_url}: {e}")
                raise ConnectionError(f"Cannot reach Ollama server at {self.base_url}. Ensure 'ollama serve' is running.") from e
            except httpx.HTTPStatusError as e:
                logger.error(f"[OllamaProvider] Ollama HTTP {e.response.status_code}: {e.response.text}")
                raise RuntimeError(f"Ollama returned HTTP {e.response.status_code}: {e.response.text}") from e
            except Exception as e:
                logger.error(f"[OllamaProvider] Unexpected error during inference: {e}")
                raise

    async def is_available(self) -> bool:
        """Checks if the Ollama daemon is responsive and model is reachable."""
        url = f"{self.base_url}/api/tags"
        async with httpx.AsyncClient(timeout=httpx.Timeout(3.0)) as client:
            try:
                res = await client.get(url)
                return res.status_code == 200
            except Exception:
                return False

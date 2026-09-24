"""
Abstract base class for LLM Providers.
Decouples FastAPI services from specific backends (Ollama, vLLM, Llama.cpp, etc.).
"""

from abc import ABC, abstractmethod


class LLMProvider(ABC):
    """Abstract interface defining required LLM inference capabilities."""

    @abstractmethod
    async def generate_json(self, prompt: str, system_prompt: str | None = None) -> str:
        """
        Submits prompt to the LLM and requests structured JSON output.
        Returns the raw string output for service-level JSON parsing and Pydantic validation.
        """
        pass

    @abstractmethod
    async def is_available(self) -> bool:
        """
        Checks health and connectivity to the underlying model provider.
        """
        pass

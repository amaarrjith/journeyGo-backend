from .base import LLMProvider
from .ollama import OllamaProvider
from .gemini import GeminiProvider
from ..config import settings


def get_llm_provider() -> LLMProvider:
    """Factory creating configured LLM provider instance."""
    provider_name = settings.llm_provider.lower()
    if provider_name == "gemini":
        return GeminiProvider(
            api_key=settings.gemini_api_key,
            model=settings.llm_model
        )
    elif provider_name == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            model=settings.llm_model
        )
    # Default to Gemini if specified or fallback to Ollama
    return GeminiProvider() if settings.gemini_api_key else OllamaProvider()

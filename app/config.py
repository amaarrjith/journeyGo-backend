"""
Configuration management for JourneyGo AI Backend.
Supports configurable LLM providers, models, host endpoints, and security keys.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator


class Settings(BaseSettings):
    # LLM Settings
    llm_provider: str = Field(default="gemini", alias="LLM_PROVIDER")
    llm_model: str = Field(default="gemini-1.5-flash", alias="LLM_MODEL")
    gemini_api_key: str | None = Field(default=None, alias="GEMINI_API_KEY")
    ollama_base_url: str = Field(default="http://localhost:11434", alias="OLLAMA_BASE_URL")

    # Server Settings
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    environment: str = Field(default="development", alias="ENVIRONMENT")

    # Optional Security Token
    api_key: str | None = Field(default=None, alias="API_KEY")

    # Limits
    max_request_size_bytes: int = 1_048_576  # 1MB max payload

    @field_validator("port", mode="before")
    @classmethod
    def parse_port(cls, v):
        if v is None or v == "" or (isinstance(v, str) and not v.strip()):
            return 8000
        try:
            return int(v)
        except (ValueError, TypeError):
            return 8000

    @field_validator("max_request_size_bytes", mode="before")
    @classmethod
    def parse_max_size(cls, v):
        if v is None or v == "" or (isinstance(v, str) and not v.strip()):
            return 1_048_576
        try:
            return int(v)
        except (ValueError, TypeError):
            return 1_048_576

    @field_validator("gemini_api_key", "api_key", mode="before")
    @classmethod
    def clean_optional_str(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return None
        return v.strip()

    @field_validator("llm_provider", mode="before")
    @classmethod
    def clean_llm_provider(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return "gemini"
        return v.strip()

    @field_validator("llm_model", mode="before")
    @classmethod
    def clean_llm_model(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return "gemini-1.5-flash"
        return v.strip()

    @field_validator("ollama_base_url", mode="before")
    @classmethod
    def clean_ollama_base_url(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return "http://localhost:11434"
        return v.strip()

    @field_validator("host", mode="before")
    @classmethod
    def clean_host(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return "0.0.0.0"
        return v.strip()

    @field_validator("environment", mode="before")
    @classmethod
    def clean_environment(cls, v):
        if v is None or (isinstance(v, str) and not v.strip()):
            return "development"
        return v.strip()

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )


settings = Settings()

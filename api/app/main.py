"""
JourneyGo Self-Hosted AI Backend.
FastAPI service exposing /v1/intent and /v1/explain for the JourneyGo iOS application.
"""

from __future__ import annotations
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Security, Request, status
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .models import (
    IntentRequest,
    UserIntent,
    ExplainRequest,
    ExplainResponse,
    PlaceDetailsRequest,
    PlaceDetailsResponse,
    SuggestPlacesRequest,
    SuggestPlacesResponse,
    DiscoverRequest,
    DiscoverResponse,
    HealthResponse
)
from .providers import get_llm_provider
from .services.intent_service import IntentService
from .services.explain_service import ExplainService
from .services.details_service import DetailsService
from .services.discover_service import DiscoverService

# Configure Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("journeygo.ai")

# Service Singletons
llm_provider = get_llm_provider()
intent_service = IntentService(provider=llm_provider)
explain_service = ExplainService(provider=llm_provider)
details_service = DetailsService(provider=llm_provider)
discover_service = DiscoverService()

# Optional API Key Authentication
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)


async def verify_api_key(key: str | None = Security(api_key_header)):
    if settings.api_key:
        if key != settings.api_key:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or missing API Key"
            )
    return key


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("==================================================")
    logger.info("🚀 JourneyGo AI Backend Server Initializing...")
    logger.info(f"   Provider : {settings.llm_provider}")
    logger.info(f"   Model    : {settings.llm_model}")
    if settings.llm_provider == "gemini":
        has_key = bool(settings.gemini_api_key)
        logger.info(f"   Gemini Key: {'Configured ✅' if has_key else 'Not set ⚠️ (Set GEMINI_API_KEY in backend/.env)'}")
    else:
        logger.info(f"   Ollama   : {settings.ollama_base_url}")
    logger.info("==================================================")
    connected = await llm_provider.is_available()
    if connected:
        logger.info(f"✅ {settings.llm_provider.capitalize()} provider verified and ready.")
    else:
        logger.warning(f"⚠️ {settings.llm_provider.capitalize()} is not yet connected/configured.")
        logger.warning("   Requests will use resilient rule fallback until credentials or server is active.")
    yield
    logger.info("👋 JourneyGo AI Backend shutting down.")


app = FastAPI(
    title="JourneyGo AI Recommendation Backend",
    version="1.0.0",
    description="Self-hosted open-source LLM service for JourneyGo iOS travel recommendation engine."
)

# CORS Configuration (allows iOS simulator, local network devices, and Web)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# MARK: - Endpoints

@app.get("/", tags=["System"])
@app.get("/api/index.py", include_in_schema=False)
async def root():
    """Root endpoint for instant deployment verification."""
    try:
        is_connected = await llm_provider.is_available()
    except Exception as e:
        logger.warning(f"Failed to check provider availability: {e}")
        is_connected = False
    return {
        "status": "online",
        "service": "JourneyGo AI Recommendation Backend",
        "version": "1.0.0",
        "provider": settings.llm_provider,
        "model": settings.llm_model,
        "provider_ready": is_connected,
        "docs_url": "/docs"
    }


@app.get("/health", response_model=HealthResponse, tags=["System"])
@app.get("/v1/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """System health check and provider readiness report."""
    try:
        is_connected = await llm_provider.is_available()
    except Exception as e:
        logger.warning(f"Failed to check provider availability in health_check: {e}")
        is_connected = False
    return HealthResponse(
        status="healthy" if is_connected else "degraded",
        provider=settings.llm_provider,
        model=settings.llm_model,
        ollama_connected=is_connected
    )


@app.post("/v1/intent", response_model=UserIntent, tags=["AI Recommendation"])
async def parse_user_intent(
    request: IntentRequest,
    _auth=Security(verify_api_key)
):
    """
    Job 1: Parses natural text into structured UserIntent.
    Extracts mood, interests, activity, budget, distance, and social preferences.
    """
    logger.info(f"📥 [POST /v1/intent] Processing query: \"{request.text[:80]}...\"")
    try:
        intent = await intent_service.extract_intent(text=request.text)
        return intent
    except Exception as e:
        logger.error(f"❌ [POST /v1/intent] Error parsing intent: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Intent extraction error: {str(e)}"
        )


@app.post("/v1/explain", response_model=ExplainResponse, tags=["AI Recommendation"])
async def explain_recommendations(
    request: ExplainRequest,
    _auth=Security(verify_api_key)
):
    """
    Job 2: Generates truthful explanations for ranked candidate places.
    Strictly forbids hallucinating place attributes not provided in request.
    """
    logger.info(f"📥 [POST /v1/explain] Explaining {len(request.places)} places for mood={request.intent.mood}")
    try:
        response = await explain_service.generate_explanations(request=request)
        return response
    except Exception as e:
        logger.error(f"❌ [POST /v1/explain] Error generating explanations: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Explanation generation error: {str(e)}"
        )


@app.post("/v1/place-details", response_model=PlaceDetailsResponse, tags=["AI Place Details"])
async def get_place_details(
    request: PlaceDetailsRequest,
    _auth=Security(verify_api_key)
):
    """
    Generates rich, engaging description, highlights, and tips for any place using Gemini.
    """
    logger.info(f"📥 [POST /v1/place-details] Generating details for \"{request.name}\" ({request.place_id})")
    try:
        details = await details_service.get_place_details(request=request)
        return details
    except Exception as e:
        logger.error(f"❌ [POST /v1/place-details] Error generating details: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Place details error: {str(e)}"
        )


@app.post("/v1/suggest-places", response_model=SuggestPlacesResponse, tags=["AI Suggestions"])
async def suggest_places(
    request: SuggestPlacesRequest,
    _auth=Security(verify_api_key)
):
    """
    Suggests well-known places for a mood and city using Gemini.
    """
    logger.info(f"📥 [POST /v1/suggest-places] Suggesting {request.count} places for mood='{request.mood}' in {request.city}")
    try:
        suggestions = await details_service.suggest_places(request=request)
        return suggestions
    except Exception as e:
        logger.error(f"❌ [POST /v1/suggest-places] Error suggesting places: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Suggest places error: {str(e)}"
        )


@app.post("/api/journey/discover", response_model=DiscoverResponse, tags=["Google Maps Grounding"])
@app.post("/v1/discover", response_model=DiscoverResponse, tags=["Google Maps Grounding"])
async def discover_places(
    request: DiscoverRequest,
    _auth=Security(verify_api_key)
):
    """
    Core place discovery powered by Gemini + Google Maps Grounding.
    Anchor places strictly in verified Google Maps geographic data.
    """
    logger.info(f"📥 [POST /api/journey/discover] Query: \"{request.query}\" at ({request.latitude}, {request.longitude})")
    try:
        result = await discover_service.discover_grounded_places(
            query=request.query,
            intent=request.intent,
            latitude=request.latitude,
            longitude=request.longitude,
            max_distance_km=request.max_distance_km,
            limit=request.limit
        )
        return DiscoverResponse(**result)
    except Exception as e:
        logger.error(f"❌ [POST /api/journey/discover] Error in Maps Grounding discovery: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Google Maps Grounding discovery error: {str(e)}"
        )



"""
Data models and Pydantic schemas for the JourneyGo AI Backend.
Guarantees strict validation, consistent JSON formats, and prevents arbitrary LLM output.
"""

from pydantic import BaseModel, Field


class UserIntent(BaseModel):
    """
    Structured representation of extracted user intent from natural language.
    Matches the schema expected by the JourneyGo iOS application.
    """
    mood: str | None = Field(
        default=None,
        description="User's emotional state or desired vibe (e.g. tired, peaceful, romantic, adventurous, energetic)"
    )
    interests: list[str] = Field(
        default_factory=list,
        description="Key nouns or interest categories (e.g. coffee, waterfalls, viewpoints, desserts, hiking)"
    )
    activity: str | None = Field(
        default=None,
        description="Intended action or activity (e.g. relax, walk, dine, work, sightsee)"
    )
    budget: str | None = Field(
        default=None,
        description="Spending level (e.g. free, budget, standard, comfort, splurge)"
    )
    max_distance_km: float | None = Field(
        default=None,
        description="Maximum distance radius in kilometers"
    )
    social_preference: str | None = Field(
        default=None,
        description="Social context (e.g. alone, couple, family, friends)"
    )


class IntentRequest(BaseModel):
    """Incoming payload for natural-language intent parsing."""
    text: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="User's prompt or description of their desired outing"
    )


class ExplainPlaceItem(BaseModel):
    """Real-world candidate place metadata supplied by the iOS app via Geoapify."""
    place_id: str = Field(..., description="Unique Geoapify place identifier")
    name: str = Field(..., description="Place name")
    distance_km: float | None = Field(default=None, description="Actual distance in km from user")
    category: str = Field(default="Attraction", description="Resolved category")
    opening_status: str | None = Field(default=None, description="Opening hours status")
    rating: float = Field(default=4.5, description="Place rating")
    budget: str = Field(default="Standard", description="Estimated budget")


class ExplainRequest(BaseModel):
    """Incoming payload requesting truthful explanations for top ranked places."""
    intent: UserIntent
    places: list[ExplainPlaceItem] = Field(
        ...,
        min_length=1,
        max_length=15,
        description="Candidate places to generate truthful rationale for"
    )


class ExplainItem(BaseModel):
    """Individual explanation for a specific place."""
    place_id: str
    text: str


class ExplainResponse(BaseModel):
    """Array of explanations corresponding to ranked places."""
    explanations: list[ExplainItem]


class PlaceDetailsRequest(BaseModel):
    """Request for AI-generated rich place description and highlights."""
    place_id: str = Field(..., description="Unique place identifier")
    name: str = Field(..., description="Place name")
    category: str | None = Field(default=None, description="Category or type of place")
    location: str | None = Field(default=None, description="City, district, or area")
    address: str | None = Field(default=None, description="Full street address if available")


class PlaceDetailsResponse(BaseModel):
    """Rich AI-generated details for a place."""
    place_id: str
    description: str = Field(..., description="Engaging, informative overview of the place")
    highlights: list[str] = Field(default_factory=list, description="Key features or highlights")
    best_time_to_visit: str | None = Field(default=None, description="Suggested time of day or season")
    tips: str | None = Field(default=None, description="Helpful visitor or local tip")


class SuggestedPlaceItem(BaseModel):
    name: str
    category: str
    search_query: str
    vibe: str
    reason: str


class SuggestPlacesRequest(BaseModel):
    mood: str
    city: str = Field(default="Kozhikode", description="Target city or region")
    count: int = Field(default=5, ge=1, le=15)


class SuggestPlacesResponse(BaseModel):
    mood: str
    city: str
    places: list[SuggestedPlaceItem]


class GroundedPlaceItem(BaseModel):
    """Place discovered via Google Maps Grounding."""
    name: str = Field(..., description="Place name from Google Maps")
    address: str | None = Field(default=None, description="Physical address")
    latitude: float | None = Field(default=None, description="Grounded latitude")
    longitude: float | None = Field(default=None, description="Grounded longitude")
    category: str = Field(default="Attraction", description="Category")
    description: str | None = Field(default=None, description="Short truthful description")
    reason: str = Field(..., description="Why this matches the user intent")
    maps_url: str | None = Field(default=None, description="Google Maps URL if grounded")


class DiscoverRequest(BaseModel):
    """Request for place discovery grounded in Google Maps."""
    query: str = Field(default="", description="User prompt or natural text")
    intent: UserIntent | None = Field(default=None, description="Parsed user intent")
    latitude: float = Field(..., description="User latitude")
    longitude: float = Field(..., description="User longitude")
    max_distance_km: float = Field(default=10.0, description="Max search radius in km")
    limit: int = Field(default=10, ge=1, le=25, description="Number of recommendations")


class DiscoverResponse(BaseModel):
    """Grounded places response from Gemini with Google Maps tool."""
    places: list[GroundedPlaceItem]
    grounding_source_count: int = 0
    model: str = "gemini"


class HealthResponse(BaseModel):
    """System health check and provider readiness report."""
    status: str
    provider: str
    model: str
    ollama_connected: bool
    version: str = "1.0.0"

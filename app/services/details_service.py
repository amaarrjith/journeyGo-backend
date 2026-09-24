"""
Service for generating rich place descriptions, highlights, and place suggestions using Gemini.
Includes fallback heuristics for resilience.
"""

import json
import logging
from ..models import (
    PlaceDetailsRequest,
    PlaceDetailsResponse,
    SuggestPlacesRequest,
    SuggestPlacesResponse,
    SuggestedPlaceItem
)
from ..providers.base import LLMProvider

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are a knowledgeable, concise local travel guide.
Your task is to provide engaging, truthful, and helpful descriptions and highlights for places.
Never invent false historical facts. Keep descriptions to 2-3 compelling sentences.
Always return strictly valid JSON matching the requested schema.
"""


class DetailsService:

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def get_place_details(self, request: PlaceDetailsRequest) -> PlaceDetailsResponse:
        """Generates rich description, highlights, and tips for a place."""
        prompt = f"""Generate rich travel details for this place:
Place Name: {request.name}
Category: {request.category or 'Attraction'}
Location: {request.location or 'Local area'}
Address: {request.address or ''}

Return a JSON object with this exact structure:
{{
  "description": "2-3 engaging sentences describing what makes this place worth visiting, its ambiance, and character.",
  "highlights": ["highlight 1", "highlight 2", "highlight 3"],
  "best_time_to_visit": "e.g. Early morning, Sunset, or Evening",
  "tips": "One practical insider tip for a great visit"
}}
"""
        try:
            raw_json = await self.provider.generate_json(prompt, system_prompt=SYSTEM_PROMPT)
            data = json.loads(raw_json)
            return PlaceDetailsResponse(
                place_id=request.place_id,
                description=data.get("description", f"{request.name} is a popular spot in {request.location or 'the area'}, offering a welcoming atmosphere and great local experiences."),
                highlights=data.get("highlights", ["Scenic ambiance", "Local favorite", "Great for relaxing"]),
                best_time_to_visit=data.get("best_time_to_visit", "Late afternoon or evening"),
                tips=data.get("tips", "Ideal for photography and unwinding.")
            )
        except Exception as e:
            logger.warning(f"[DetailsService] LLM details generation failed: {e}. Using fallback.")
            return self._fallback_details(request)

    async def suggest_places(self, request: SuggestPlacesRequest) -> SuggestPlacesResponse:
        """Suggests real popular places matching a mood and city."""
        prompt = f"""Suggest {request.count} real, well-known places or spots in or near {request.city} that match the mood: '{request.mood}'.

Return a JSON object with this exact structure:
{{
  "places": [
    {{
      "name": "Exact real place name",
      "category": "e.g. Cafe, Beach, Park, Viewpoint, Heritage",
      "search_query": "Keyword for map search",
      "vibe": "Short vibe descriptor",
      "reason": "Why it matches this mood"
    }}
  ]
}}
"""
        try:
            raw_json = await self.provider.generate_json(prompt, system_prompt=SYSTEM_PROMPT)
            data = json.loads(raw_json)
            items = []
            for p in data.get("places", []):
                items.append(SuggestedPlaceItem(
                    name=p.get("name", "Popular Spot"),
                    category=p.get("category", "Attraction"),
                    search_query=p.get("search_query", p.get("name", "")),
                    vibe=p.get("vibe", request.mood),
                    reason=p.get("reason", f"Great match for {request.mood}")
                ))
            return SuggestPlacesResponse(
                mood=request.mood,
                city=request.city,
                places=items
            )
        except Exception as e:
            logger.warning(f"[DetailsService] LLM suggestions failed: {e}.")
            return SuggestPlacesResponse(
                mood=request.mood,
                city=request.city,
                places=[]
            )

    def _fallback_details(self, request: PlaceDetailsRequest) -> PlaceDetailsResponse:
        loc = request.location or "the area"
        cat = (request.category or "attraction").lower()
        return PlaceDetailsResponse(
            place_id=request.place_id,
            description=f"{request.name} is a renowned {cat} situated in {loc}, beloved by locals and travelers seeking a memorable experience.",
            highlights=[
                f"Authentic {cat} atmosphere",
                "Scenic location and surroundings",
                "Great spot to relax and take in the local vibe"
            ],
            best_time_to_visit="Morning or late afternoon",
            tips="Visit during non-peak hours for a more serene experience."
        )

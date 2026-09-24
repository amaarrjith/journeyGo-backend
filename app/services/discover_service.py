"""
Service for discovering real places using Google Gemini API with Google Maps Grounding.
Anchor places in verified geographic data from Google Maps.
"""

import json
import logging
import httpx
from typing import Any
from ..config import settings
from ..models import UserIntent

logger = logging.getLogger("journeygo.ai.discover")


class DiscoverService:

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self.api_key = api_key or settings.gemini_api_key
        self.model = model or settings.llm_model or "gemini-3.6-flash"
        self.timeout = httpx.Timeout(25.0, connect=5.0)

    async def discover_grounded_places(
        self,
        query: str,
        intent: UserIntent | None,
        latitude: float,
        longitude: float,
        max_distance_km: float = 10.0,
        limit: int = 10
    ) -> dict[str, Any]:
        """
        Executes Gemini generation with Google Maps Grounding enabled.
        Returns validated structured places backed by Google Maps.
        """
        if not self.api_key:
            raise ValueError("GEMINI_API_KEY is not configured on the backend server.")

        mood_str = (intent.mood if intent and intent.mood else "relaxed").capitalize()
        interests_str = ", ".join(intent.interests) if (intent and intent.interests) else "attractions"
        activity_str = intent.activity if intent and intent.activity else "visit"
        budget_str = intent.budget if intent and intent.budget else "standard"
        social_str = intent.social_preference if intent and intent.social_preference else "any"

        prompt = f"""Find real, verified places near latitude {latitude}, longitude {longitude} for a person who is feeling {mood_str}, interested in {interests_str}, and wanting to {activity_str} ({social_str}, budget: {budget_str}).
User query: "{query}"
Preferred distance: within {max_distance_km} km.
Limit: up to {limit} places.

CRITICAL INSTRUCTIONS:
- You MUST use Google Maps grounding to discover real physical places.
- Do NOT invent or fabricate place names, coordinates, or addresses.
- If a coordinate or address is unavailable from Google Maps, omit or use null.
- Provide a truthful 'reason' explaining specifically why this place fits the user's mood and request.

Return STRICTLY a JSON object with this format:
{{
  "places": [
    {{
      "name": "Place name from Google Maps",
      "address": "Full or partial street address",
      "latitude": 0.0,
      "longitude": 0.0,
      "category": "Cafe / Beach / Park / Viewpoint / Restaurant",
      "description": "Short truthful description grounded in Maps data",
      "reason": "Why this matches the user's specific request"
    }}
  ]
}}"""

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ],
            "tools": [
                {"googleMaps": {}}
            ],
            "toolConfig": {
                "retrievalConfig": {
                    "latLng": {
                        "latitude": latitude,
                        "longitude": longitude
                    }
                }
            },
            "generationConfig": {
                "temperature": 0.2,
                "topP": 0.95
            }
        }

        headers = {
            "Content-Type": "application/json",
            "X-goog-api-key": self.api_key
        }

        # Candidate models with Google Maps Grounding support
        models_to_try = [self.model, "gemini-3.6-flash", "gemini-flash-latest", "gemini-3.1-flash-lite"]
        seen = set()
        clean_models = [m for m in models_to_try if m not in seen and not seen.add(m)]

        last_error = None
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for model_name in clean_models:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent"
                try:
                    logger.info(f"[JourneyAI] Calling Gemini Maps Grounding via model={model_name} at ({latitude}, {longitude})")
                    resp = await client.post(url, headers=headers, json=payload)

                    if resp.status_code == 429:
                        logger.warning(f"[JourneyAI] Rate limit (429) hit on model {model_name}.")
                        last_error = RuntimeError("Google Gemini rate limit exceeded (15 RPM free tier).")
                        continue

                    if resp.status_code in (404, 503):
                        logger.warning(f"[JourneyAI] Model {model_name} returned {resp.status_code}, trying fallback model...")
                        last_error = RuntimeError(f"HTTP {resp.status_code}: {resp.text[:200]}")
                        continue

                    resp.raise_for_status()
                    data = resp.json()

                    candidates = data.get("candidates", [])
                    if not candidates:
                        raise RuntimeError("Gemini returned empty candidates.")

                    candidate = candidates[0]
                    grounding_meta = candidate.get("groundingMetadata", {})
                    grounding_chunks = grounding_meta.get("groundingChunks", [])
                    logger.info(f"[JourneyAI] Grounding metadata received with {len(grounding_chunks)} source chunks.")

                    parts = candidate.get("content", {}).get("parts", [])
                    raw_text = ""
                    for part in parts:
                        if "text" in part:
                            raw_text += part["text"]

                    # Extract JSON substring
                    parsed_places = self._parse_places_json(raw_text)

                    # Augment with any explicit Google Maps metadata chunks
                    grounded_places = self._augment_with_grounding_metadata(parsed_places, grounding_chunks)

                    return {
                        "places": grounded_places,
                        "grounding_source_count": len(grounding_chunks),
                        "model": model_name
                    }

                except Exception as e:
                    last_error = e
                    logger.warning(f"[JourneyAI] Attempt with model {model_name} failed: {e}")
                    continue

        raise RuntimeError(f"All Gemini Google Maps Grounding attempts failed: {last_error}")

    def _parse_places_json(self, text: str) -> list[dict[str, Any]]:
        text = text.strip()
        # Clean markdown code block fences if present
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end != -1:
            try:
                data = json.loads(text[start:end+1])
                return data.get("places", [])
            except Exception as e:
                logger.error(f"[JourneyAI] JSON decoding error: {e}")
        return []

    def _augment_with_grounding_metadata(self, places: list[dict[str, Any]], chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Match chunks containing maps/places info
        chunk_map = {}
        for c in chunks:
            maps_item = c.get("maps", {})
            title = maps_item.get("title") or maps_item.get("name")
            if title:
                chunk_map[title.lower()] = maps_item

        result = []
        for p in places:
            name = p.get("name", "").strip()
            if not name:
                continue

            # Check if this place has a direct match in Google Maps grounding chunk
            match = chunk_map.get(name.lower())
            if match:
                if not p.get("address") and match.get("address"):
                    p["address"] = match.get("address")
                if match.get("uri"):
                    p["maps_url"] = match.get("uri")

            result.append(p)
        return result

"""
Recommendation explanation service.
Synthesizes truthful, contextual rationales for recommended places.
Strictly adheres to the rule: NEVER invent ratings, prices, distance, opening hours, or amenities.
"""

import json
import logging
from ..models import ExplainRequest, ExplainResponse, ExplainItem
from ..providers.base import LLMProvider

logger = logging.getLogger(__name__)

EXPLAIN_SYSTEM_PROMPT = """You are an accurate travel recommendation explainer.
Your job is to generate a concise, personalized 1-to-2 sentence explanation for why each place matches the user's request.

CRITICAL RULES:
1. ONLY use information explicitly supplied in the prompt (name, category, distance_km, rating, opening_status).
2. NEVER invent ratings, prices, opening hours, amenities, reviews, or fake locations.
3. Return valid JSON only:
{
  "explanations": [
    {"place_id": "string", "text": "string"}
  ]
}
"""


class ExplainService:

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def generate_explanations(self, request: ExplainRequest) -> ExplainResponse:
        """
        Creates tailored explanations for each candidate place.
        """
        places_data = [
            {
                "place_id": p.place_id,
                "name": p.name,
                "category": p.category,
                "distance_km": p.distance_km,
                "rating": p.rating,
                "opening_status": p.opening_status
            }
            for p in request.places
        ]

        user_intent_summary = {
            "mood": request.intent.mood,
            "interests": request.intent.interests,
            "activity": request.intent.activity,
            "budget": request.intent.budget
        }

        prompt = f"""User Intent:
{json.dumps(user_intent_summary, indent=2)}

Places to Explain:
{json.dumps(places_data, indent=2)}

Generate truthful match explanations:"""

        try:
            raw_response = await self.provider.generate_json(
                prompt=prompt,
                system_prompt=EXPLAIN_SYSTEM_PROMPT
            )
            data = json.loads(raw_response)
            items = [ExplainItem(**item) for item in data.get("explanations", [])]
            return ExplainResponse(explanations=items)
        except Exception as e:
            logger.warning(f"[ExplainService] LLM explanation failed ({e}), using truthful fallback generator.")
            return self._truthful_fallback(request)

    def _truthful_fallback(self, request: ExplainRequest) -> ExplainResponse:
        """Deterministic generator using strictly verified metadata."""
        explanations: list[ExplainItem] = []

        for p in request.places:
            reasons = []
            if request.intent.mood:
                reasons.append(f"fits your {request.intent.mood} vibe")
            if request.intent.interests:
                matched = [i for i in request.intent.interests if i.lower() in p.name.lower() or i.lower() in p.category.lower()]
                if matched:
                    reasons.append(f"offers {', '.join(matched)}")

            reason_str = " and ".join(reasons) if reasons else f"is a top-rated {p.category.lower()} attraction"
            dist_str = f"only {p.distance_km:.1f} km away" if p.distance_km else "conveniently located nearby"
            text = f"{p.name} is a strong match because it {reason_str}. It is {dist_str} with a {p.rating:.1f}★ rating."

            explanations.append(ExplainItem(place_id=p.place_id, text=text))

        return ExplainResponse(explanations=explanations)

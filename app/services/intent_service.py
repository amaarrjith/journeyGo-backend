"""
Intent extraction service.
Crafts structured prompts for the LLM, validates output via Pydantic,
and provides a resilient fallback to ensure 100% endpoint reliability.
"""

import json
import logging
import re
from ..models import UserIntent
from ..providers.base import LLMProvider

logger = logging.getLogger(__name__)

INTENT_SYSTEM_PROMPT = """You are an accurate intent extraction engine for a travel discovery application.
Your task is to analyze the user's natural language request and extract structured parameters.
Respond ONLY with a valid JSON object matching this exact schema:
{
  "mood": "tired" | "peaceful" | "romantic" | "adventurous" | "nature" | "food" | "social" | "family" | null,
  "interests": ["coffee", "waterfalls", "viewpoints", "nature", ...],
  "activity": "relax" | "walk" | "dine" | "work" | "sightsee" | null,
  "budget": "free" | "budget" | "standard" | "comfort" | "splurge" | null,
  "max_distance_km": number (e.g. 5.0) | null,
  "social_preference": "alone" | "couple" | "family" | "friends" | null
}

Rules:
1. Do NOT invent information not implied by the user text.
2. If distance is not mentioned, use 5.0 for walking or 10.0 for general nearby.
3. Return ONLY valid JSON. No markdown backticks, no explanations.
"""


class IntentService:

    def __init__(self, provider: LLMProvider):
        self.provider = provider

    async def extract_intent(self, text: str) -> UserIntent:
        """
        Parses user's free text input into a validated UserIntent instance.
        """
        prompt = f"User Request: \"{text.strip()}\"\nExtract the JSON intent:"

        try:
            raw_response = await self.provider.generate_json(
                prompt=prompt,
                system_prompt=INTENT_SYSTEM_PROMPT
            )
            parsed_json = self._clean_and_parse_json(raw_response)
            intent = UserIntent(**parsed_json)
            logger.info(f"[IntentService] Successfully extracted intent via LLM: {intent}")
            return intent
        except Exception as e:
            logger.warning(f"[IntentService] LLM parsing failed or unavailable ({e}). Using rule-based fallback.")
            return self._rule_based_fallback(text)

    def _clean_and_parse_json(self, raw: str) -> dict:
        """Strips markdown markers if present and parses JSON safely."""
        cleaned = raw.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        cleaned = cleaned.strip()

        # Locate first { and last }
        first_brace = cleaned.find("{")
        last_brace = cleaned.rfind("}")
        if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
            cleaned = cleaned[first_brace:last_brace + 1]

        return json.loads(cleaned)

    def _rule_based_fallback(self, text: str) -> UserIntent:
        """Reliable rule-based heuristic extractor if LLM is offline or output is malformed."""
        lower = text.lower()

        # Mood detection
        mood = None
        mood_mapping = {
            "tired": ["tired", "exhausted", "stressed", "burnout", "unwind", "hectic", "rough day"],
            "peaceful": ["peaceful", "quiet", "calm", "serene", "zen", "silence", "chill"],
            "romantic": ["romantic", "date", "partner", "couple", "intimate", "love"],
            "adventurous": ["adventure", "adventurous", "hiking", "trek", "thrill", "explore"],
            "nature": ["nature", "greenery", "forest", "mountain", "trees", "fresh air"],
            "sunset": ["sunset", "golden hour", "dusk", "evening view"],
            "food": ["food", "hungry", "delicious", "cafe", "coffee", "caffeine"]
        }
        for m_key, words in mood_mapping.items():
            if any(w in lower for w in words):
                mood = m_key
                break

        # Interests
        interests = []
        interest_kws = [
            ("coffee", "coffee"), ("cafe", "coffee"), ("tea", "tea"),
            ("waterfall", "waterfalls"), ("viewpoint", "viewpoints"),
            ("sunset", "sunset"), ("nature", "nature"), ("forest", "forest"),
            ("hiking", "hiking"), ("dessert", "desserts"), ("park", "parks")
        ]
        for kw, tag in interest_kws:
            if kw in lower and tag not in interests:
                interests.append(tag)

        # Activity
        activity = None
        if any(w in lower for w in ["relax", "unwind", "chill"]):
            activity = "relax"
        elif any(w in lower for w in ["walk", "stroll"]):
            activity = "walk"
        elif any(w in lower for w in ["dine", "eat"]):
            activity = "dine"
        elif any(w in lower for w in ["work", "study", "laptop"]):
            activity = "work"

        # Distance
        max_dist = None
        if "walking" in lower or "walkable" in lower:
            max_dist = 2.0
        elif "nearby" in lower or "close" in lower:
            max_dist = 5.0
        else:
            match = re.search(r"within (\d+)\s*km", lower)
            if match:
                max_dist = float(match.group(1))

        # Social
        social = None
        if any(w in lower for w in ["alone", "myself", "solo"]):
            social = "alone"
        elif any(w in lower for w in ["couple", "date"]):
            social = "couple"
        elif any(w in lower for w in ["friends", "group", "gang"]):
            social = "friends"
        elif any(w in lower for w in ["family", "kids"]):
            social = "family"

        budget = "free" if "free" in lower else ("budget" if "cheap" in lower or "budget" in lower else None)

        return UserIntent(
            mood=mood,
            interests=interests,
            activity=activity,
            budget=budget,
            max_distance_km=max_dist or 10.0,
            social_preference=social
        )

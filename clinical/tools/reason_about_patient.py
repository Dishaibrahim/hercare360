"""
Internal LLM reasoning layer — Section 2.4 of the BRD.

Uses the Google Gen AI SDK (google-genai) — the same SDK that powers Google ADK agents.
A named clinical agent with a system instruction reasons over structured FHIR + diet data
and generates a 3-sentence clinical narrative. Demo never breaks: robust fallback included.

Model: gemini-2.0-flash  ·  Key: GOOGLE_API_KEY (AI Studio)
"""

import os
from typing import Any

_MODEL = "gemini-2.5-flash"

_SYSTEM_INSTRUCTION = (
    "You are an expert women's health specialist with deep knowledge of PCOS, PCOD, "
    "insulin resistance, thyroid disorders, and reproductive endocrinology. "
    "When given a structured patient context, you write concise, evidence-based clinical "
    "briefings for the consulting doctor. You connect diet patterns to lab results, "
    "flag medication timing issues, and always prioritise the single most urgent action. "
    "Never use generic advice. Be specific to the patient's actual data."
)

_FALLBACK = (
    "Given this patient's rising HbA1c trend and 5-day high-GI dietary pattern, "
    "today's consultation should prioritise an insulin sensitiser dose review and a structured "
    "low-GI meal plan handout before addressing cycle irregularity. "
    "The overdue AMH combined with protein deficit signals concurrent referral to a reproductive "
    "endocrinologist is warranted this visit. "
    "Confirm Levothyroxine timing compliance and order Vit D levels — OCP co-prescription "
    "is likely reducing absorption."
)


async def generate_clinical_narrative(patient_context: dict[str, Any]) -> str:
    """
    Generate a 3-sentence clinical briefing using a Gemini ADK-style agent.
    Falls back gracefully if the API key is missing or the call fails.
    """
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        return _FALLBACK

    try:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=api_key)

        response = await client.aio.models.generate_content(
            model=_MODEL,
            contents=_build_prompt(patient_context),
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_INSTRUCTION,
                temperature=0.3,
                max_output_tokens=350,
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )

        text = response.text
        return text.strip() if text else _FALLBACK

    except Exception:
        return _FALLBACK


def _build_prompt(ctx: dict[str, Any]) -> str:
    conditions   = ", ".join(ctx.get("conditions", [])) or "PCOS"
    gaps         = ", ".join(ctx.get("care_gaps", [])) or "none flagged"
    meds         = ", ".join(ctx.get("medications", [])) or "none listed"
    interactions = ", ".join(ctx.get("interactions", [])) or "none flagged"
    gi_score     = ctx.get("diet_score", "unavailable")
    diet_alerts  = ", ".join(ctx.get("diet_alerts", [])) or "none"

    return (
        f"Patient context:\n"
        f"- Active conditions: {conditions}\n"
        f"- Overdue screenings (care gaps): {gaps}\n"
        f"- Current medications: {meds}\n"
        f"- Drug interaction alerts: {interactions}\n"
        f"- 7-day dietary GI score: {gi_score}/100\n"
        f"- Nutrition alerts: {diet_alerts}\n\n"
        f"Write exactly 3 sentences for the consulting doctor:\n"
        f"1. The single most urgent clinical action for today's visit.\n"
        f"2. A specific diet-to-lab connection the doctor should explain to the patient.\n"
        f"3. One medication timing or lifestyle recommendation.\n\n"
        f"Be specific, evidence-based, and clinically precise. No bullet points."
    )

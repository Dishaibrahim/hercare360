"""
A2A-callable urgency scoring tools — the clinical brain that Ops queries.
GetPatientUrgencyScore: called by HerCare-Ops during conflict resolution.
GetDailyRiskBriefing:  called by HerCare-Ops for morning briefings.
"""

import asyncio
from typing import Any

from fastmcp import FastMCPApp
from po_fastmcp import FhirClient, get_fhir_context
from clinical.tools.care_gaps import PCOSCareGapEngine
from clinical.tools.drug_interactions import check_interactions

urgency_tools_app = FastMCPApp("UrgencyTools")

_engine = PCOSCareGapEngine()

_SEV = {"HIGH": 25, "MEDIUM": 12, "LOW": 5}
_IA  = {"CRITICAL": 30, "HIGH": 15, "MEDIUM": 8}

# Demo scores — used when FHIR context is not available (e.g. called from Ops via A2A)
_DEMO_SCORES: dict[str, dict] = {
    "pcos-001": {
        "urgency_score": 74,
        "reason": "HbA1c 102d overdue · active hypothyroidism · testosterone elevated 68 ng/dL",
        "breakdown": {"care_gaps": 49, "interactions": 10, "conditions": 15},
    },
    "pcos-002": {
        "urgency_score": 82,
        "reason": "Active OHSS risk · follicular scan overdue · fertility pathway active",
        "breakdown": {"care_gaps": 55, "interactions": 12, "conditions": 15},
    },
    "pcos-003": {
        "urgency_score": 61,
        "reason": "PCOD · fertility pathway · AMH not checked in 8 months",
        "breakdown": {"care_gaps": 37, "interactions": 9, "conditions": 15},
    },
    "pcos-004": {
        "urgency_score": 55,
        "reason": "Routine PCOS follow-up · labs within range",
        "breakdown": {"care_gaps": 30, "interactions": 10, "conditions": 15},
    },
    "pcos-005": {
        "urgency_score": 68,
        "reason": "New consultation · elevated LH/FSH ratio · AMH pending",
        "breakdown": {"care_gaps": 43, "interactions": 10, "conditions": 15},
    },
}


@urgency_tools_app.tool("GetPatientUrgencyScore")
async def get_patient_urgency_score(patient_id: str) -> dict:
    """
    A2A-callable. Returns 0-100 urgency score for a patient.
    Used by HerCare-Ops to resolve scheduling priority conflicts.
    """
    context = get_fhir_context()
    if context:
        data = await _score_from_fhir(patient_id, context)
    else:
        data = _DEMO_SCORES.get(patient_id, {"urgency_score": 50, "reason": "Standard PCOS follow-up", "breakdown": {}})

    return {"patient_id": patient_id, **data}


@urgency_tools_app.tool("GetDailyRiskBriefing")
async def get_daily_risk_briefing(patient_ids: list[str]) -> dict:
    """
    A2A-callable. Given today's patient IDs, returns a ranked risk list
    for the morning briefing. Called by HerCare-Ops.
    """
    context = get_fhir_context()
    patients: list[dict] = []

    for pid in patient_ids:
        if context:
            data = await _score_from_fhir(pid, context)
        else:
            data = _DEMO_SCORES.get(pid, {"urgency_score": 50, "reason": "Standard follow-up", "breakdown": {}})
        patients.append({"patient_id": pid, **data})

    patients.sort(key=lambda p: p["urgency_score"], reverse=True)
    flagged = [p for p in patients if p["urgency_score"] >= 70]

    return {
        "total_patients": len(patients),
        "flagged_high_risk": len(flagged),
        "ranked_list": patients,
        "briefing": f"{len(flagged)} of {len(patients)} patients flagged HIGH risk for today's schedule",
    }


@urgency_tools_app.tool("GetPCOSRiskScore")
async def get_pcos_risk_score(patient_id: str) -> dict:
    """
    Composite 0-100 PCOS risk score combining condition burden,
    overdue screenings, and medication interactions.
    """
    return await get_patient_urgency_score(patient_id)


async def _score_from_fhir(patient_id: str, context: Any) -> dict:
    client = FhirClient(context)
    try:
        conditions, obs, meds = await asyncio.gather(
            client.search("Condition", {"patient": patient_id}),
            client.search("Observation", {"patient": patient_id, "_sort": "-date"}, limit=30),
            client.search("MedicationRequest", {"patient": patient_id, "status": "active"}),
        )
    except Exception:
        return _DEMO_SCORES.get(patient_id, {"urgency_score": 50, "reason": "FHIR unavailable"})

    gaps = _engine.evaluate(obs or [])
    interactions = check_interactions(meds or [])

    gap_score  = min(60, sum(_SEV.get(g.severity, 0) for g in gaps))
    ia_score   = min(30, sum(_IA.get(i["severity"], 0) for i in interactions))
    cond_score = min(10, len(conditions or []) * 3)
    total      = min(100, gap_score + ia_score + cond_score)

    top_gaps = [f"{g.name} ({g.days_overdue}d overdue)" for g in gaps if g.severity in ("HIGH", "MEDIUM")][:2]
    top_ia   = [f"{i['drug_a']}+{i['drug_b']}: {i['severity']}" for i in interactions if i["severity"] in ("CRITICAL", "HIGH")][:1]
    reason   = "; ".join(top_gaps + top_ia) or "Routine follow-up"

    return {
        "urgency_score": total,
        "reason": reason,
        "breakdown": {"care_gaps": gap_score, "interactions": ia_score, "conditions": cond_score},
    }

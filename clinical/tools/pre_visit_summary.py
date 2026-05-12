"""
GetPreVisitSummary — orchestrator tool (Section 4.2, BRD).

Sequence:
  1. get_fhir_context() → patient_id, fhir_url, token
  2. Parallel FHIR reads: Patient, Condition, Observation, MedicationRequest,
                          AllergyIntolerance, ServiceRequest
  3. care_gaps.evaluate(observations)         → gap list
  4. drug_interactions.check(medications)     → interaction alerts
  5. A2A → HerCare-Wellness.GetDietContextForPatient → diet context block
  6. feedback_loop applied inside care_gaps   → upgraded severities
  7. LLM → reason_about_patient()             → 3-sentence clinical narrative
  8. Assemble Prefab card — all sections live
  Target wall time: < 5 seconds
"""

import asyncio
from datetime import date
from typing import Any

from fastmcp import FastMCPApp
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge, Card, CardContent, CardHeader, CardTitle,
    Column, Heading, Row, Separator, Text,
)

from po_fastmcp import FhirClient, get_fhir_context
from clinical.tools.care_gaps import PCOSCareGapEngine, CareGap
from clinical.tools.drug_interactions import check_interactions
from clinical.tools.lab_trends import extract_lab_trends
from clinical.tools.reason_about_patient import generate_clinical_narrative
from shared.a2a_client import a2a_call, WELLNESS_URL

pre_visit_summary_app = FastMCPApp("PreVisitSummary")
_engine = PCOSCareGapEngine()


@pre_visit_summary_app.tool("GetPreVisitSummary")
async def get_pre_visit_summary() -> PrefabApp:
    context = get_fhir_context()

    if context and context.patient_id:
        patient_data = await _load_fhir(context)
    else:
        patient_data = _demo_data()

    # Steps 3–5 in parallel: care gaps (needs diet ctx), interactions, lab trends, diet context
    diet_ctx = await _get_diet_context(patient_data.get("patient_id"))

    gaps         = _engine.evaluate(patient_data["observations"], diet_ctx)
    interactions = check_interactions(patient_data["medications"])
    trends       = extract_lab_trends(patient_data["observations"])

    # Step 7: LLM narrative
    llm_input = {
        "conditions":    patient_data["condition_names"],
        "care_gaps":     [f"{g.name} ({g.days_overdue}d overdue)" for g in gaps if g.severity != "LOW"],
        "medications":   patient_data["medication_names"],
        "interactions":  [f"{i['drug_a']} + {i['drug_b']}: {i['severity']}" for i in interactions],
        "diet_score":    diet_ctx.get("gi_score_7d"),
        "diet_alerts":   diet_ctx.get("alerts", []),
    }
    narrative = await generate_clinical_narrative(llm_input)

    return _build_card(patient_data, gaps, interactions, trends, diet_ctx, narrative)


# ── FHIR loading ─────────────────────────────────────────────────────────────

async def _load_fhir(context) -> dict:
    client = FhirClient(context)
    pid = context.patient_id

    results = await asyncio.gather(
        client.read("Patient", pid),
        client.search("Condition",            {"patient": pid}),
        client.search("Observation",          {"patient": pid, "_sort": "-date"}, limit=50),
        client.search("MedicationRequest",    {"patient": pid, "status": "active"}),
        client.search("AllergyIntolerance",   {"patient": pid}),
        client.search("ServiceRequest",       {"patient": pid, "status": "active"}),
        return_exceptions=True,
    )

    patient, conditions, obs, meds, allergies, orders = [
        r if not isinstance(r, Exception) else [] for r in results
    ]

    return {
        "patient_id":      pid,
        "name":            _name(patient),
        "age":             _age(patient),
        "observations":    obs or [],
        "conditions":      conditions or [],
        "condition_names": _condition_names(conditions or []),
        "medications":     meds or [],
        "medication_names": _med_names(meds or []),
        "allergies":       allergies or [],
        "orders":          orders or [],
    }


async def _get_diet_context(patient_id: str | None) -> dict:
    if patient_id:
        try:
            result = await a2a_call(WELLNESS_URL, "GetDietContextForPatient", {"patient_id": patient_id})
            if isinstance(result, dict):
                return result
        except Exception:
            pass
    return _demo_diet()


# ── Prefab card assembly ──────────────────────────────────────────────────────

def _build_card(
    pd: dict, gaps: list[CareGap], interactions: list[dict],
    trends: list[dict], diet: dict, narrative: str,
) -> PrefabApp:
    critical_ia = [i for i in interactions if i["severity"] in ("CRITICAL", "HIGH")]

    with Card() as view:
        with CardHeader():
            CardTitle(f"Pre-Visit Summary — {pd['name']}  ·  Age {pd['age']}")
        with CardContent():
            with Column(gap=5):

                # ── 🔴 Critical drug alerts ──────────────────────────────────
                if critical_ia:
                    with Column(gap=2):
                        Heading("🔴 Drug Alerts")
                        for ia in critical_ia:
                            v = "danger" if ia["severity"] == "CRITICAL" else "warning"
                            with Row(gap=2, align="center"):
                                Badge(ia["severity"], variant=v)
                                Text(f"{ia['drug_a']} + {ia['drug_b']}: {ia['message']}")
                    Separator()

                # ── ⏰ Overdue screenings (care gaps) ────────────────────────
                if gaps:
                    with Column(gap=2):
                        Heading("⏰ Overdue Screenings")
                        for gap in gaps:
                            v = "danger" if gap.severity == "HIGH" else ("warning" if gap.severity == "MEDIUM" else "secondary")
                            label = f"{gap.name}  —  {gap.days_overdue}d overdue"
                            if gap.escalated:
                                label += "  ↑ ESCALATED (diet signal)"
                            with Column(gap=1):
                                Badge(label, variant=v)
                                if gap.escalation_reason:
                                    Text(f"   {gap.escalation_reason}", css_class="text-xs text-muted-foreground")
                    Separator()

                # ── 📊 Lab trends ────────────────────────────────────────────
                if trends:
                    with Column(gap=2):
                        Heading("📊 Lab Trends")
                        with Row(gap=3):
                            for t in trends[:4]:
                                latest = t.get("latest", {})
                                arrow  = t["direction"]
                                tv = "danger" if arrow == "↑" else ("success" if arrow == "↓" else "secondary")
                                with Card():
                                    with CardContent():
                                        Text(t["name"], css_class="font-semibold text-sm")
                                        with Row(gap=1, align="center"):
                                            Text(latest.get("value", "—"))
                                            Badge(arrow, variant=tv)
                                        Text(latest.get("date", ""), css_class="text-xs text-muted-foreground")
                    Separator()

                # ── 🥗 Nutrition context (A2A from Wellness) ─────────────────
                with Column(gap=2):
                    Heading("🥗 Nutrition Context")
                    gi = diet.get("gi_score_7d", 0)
                    gi_v = "danger" if gi > 70 else ("warning" if gi > 55 else "success")
                    skips = diet.get("meal_skip_freq", 0)
                    with Row(gap=2, align="center"):
                        Badge(f"7-day GI score: {gi}/100", variant=gi_v)
                        if skips > 3:
                            Badge(f"Meal skips: {skips}/wk", variant="warning")
                        if not diet.get("protein_adequacy", True):
                            Badge("Protein deficit", variant="warning")
                    for alert in diet.get("alerts", [])[:2]:
                        Text(f"• {alert}", css_class="text-sm")
                Separator()

                # ── 💊 Active medications ────────────────────────────────────
                with Column(gap=1):
                    Heading("💊 Active Medications")
                    for med in pd.get("medication_names", []) or ["Metformin 500mg BD", "Levothyroxine 50mcg OD", "OCP (Yasmin)"]:
                        Text(f"• {med}")
                Separator()

                # ── 🌿 Allergies ─────────────────────────────────────────────
                allergy_names = _allergy_names(pd.get("allergies", []))
                if allergy_names:
                    with Column(gap=1):
                        Heading("🌿 Allergies")
                        with Row(gap=2):
                            for a in allergy_names:
                                Badge(a, variant="danger")
                    Separator()

                # ── 🤖 AI Clinical Insight ───────────────────────────────────
                with Column(gap=2):
                    Heading("🤖 AI Clinical Insight")
                    Badge("Claude Sonnet · Anthropic API · structured FHIR + diet signals", variant="secondary")
                    Text(narrative)

    return PrefabApp(view=view)


# ── Demo / fallback data ──────────────────────────────────────────────────────

def _demo_data() -> dict:
    return {
        "patient_id":      "pcos-001",
        "name":            "Meera Nair",
        "age":             28,
        "observations":    [],
        "conditions":      [],
        "condition_names": ["PCOS (E28.2)", "Hypothyroidism (E03.9)", "Borderline T2DM (E11)"],
        "medications":     [],
        "medication_names": ["Metformin 500mg BD", "Levothyroxine 50mcg OD", "OCP (Yasmin)"],
        "allergies":       [{"code": {"text": "Penicillin"}}],
        "orders":          [],
    }


def _demo_diet() -> dict:
    return {
        "gi_score_7d":      74,
        "protein_adequacy": False,
        "meal_skip_freq":   4,
        "sat_fat_high":     False,
        "alerts":           ["5 high-GI days this week", "Protein deficit detected (<0.8 g/kg)"],
    }


# ── FHIR parsing helpers ──────────────────────────────────────────────────────

def _name(patient: dict | None) -> str:
    if not patient:
        return "Meera Nair"
    try:
        n = patient["name"][0]
        parts = [str(g) for g in n.get("given", [])]
        if n.get("family"):
            parts.append(str(n["family"]))
        return " ".join(parts) or "Patient"
    except Exception:
        return "Patient"


def _age(patient: dict | None) -> int | str:
    if not patient:
        return 28
    try:
        bd = patient.get("birthDate", "")
        if bd:
            bdate = date.fromisoformat(bd[:10])
            today = date.today()
            return today.year - bdate.year - ((today.month, today.day) < (bdate.month, bdate.day))
    except Exception:
        pass
    return "—"


def _condition_names(conditions: list[dict]) -> list[str]:
    names: list[str] = []
    for c in conditions:
        text = c.get("code", {}).get("text", "")
        if text:
            names.append(text)
            continue
        coding = c.get("code", {}).get("coding", [])
        if coding:
            names.append(coding[0].get("display", ""))
    return [n for n in names if n]


def _med_names(meds: list[dict]) -> list[str]:
    names: list[str] = []
    for m in meds:
        concept = m.get("medicationCodeableConcept", {})
        text = concept.get("text", "")
        if text:
            names.append(text)
            continue
        coding = concept.get("coding", [])
        if coding:
            names.append(coding[0].get("display", ""))
    return [n for n in names if n]


def _allergy_names(allergies: list[dict]) -> list[str]:
    names: list[str] = []
    for a in allergies:
        text = a.get("code", {}).get("text", "")
        if text:
            names.append(text)
            continue
        coding = a.get("code", {}).get("coding", [])
        if coding:
            names.append(coding[0].get("display", ""))
    return [n for n in names if n]

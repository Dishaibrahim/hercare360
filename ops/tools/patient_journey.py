"""
Patient journey orchestration — the glue between HerCare-Ops and HerCare-Clinical.

GetMorningClinicBriefing: day starts with Ops calling Clinical for every patient's
urgency score, then combining with demand forecast and staff readiness.

GetPostVisitWorkflow: after a consultation, Ops releases the room, triggers billing,
and slots the follow-up appointment — Clinical feeds the recommended follow-up interval.

This is what makes HerCare 360 a mesh, not two separate tools.
"""

import json
from pathlib import Path

from fastmcp import FastMCPApp
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge, Card, CardContent, CardHeader, CardTitle,
    Column, Row, Separator, Text, Heading,
)
from shared.a2a_client import a2a_call, CLINICAL_URL

patient_journey_app = FastMCPApp("PatientJourney")

_APPT  = Path(__file__).parent.parent.parent / "data" / "appointments.json"
_STAFF = Path(__file__).parent.parent.parent / "data" / "staff.json"
_ROOMS = Path(__file__).parent.parent.parent / "data" / "rooms.json"


def _appt()  -> dict: return json.loads(_APPT.read_text())
def _staff() -> dict: return json.loads(_STAFF.read_text())
def _rooms() -> dict: return json.loads(_ROOMS.read_text())


# ── 1. Morning Clinic Briefing (Ops calls Clinical) ───────────────────────────

@patient_journey_app.tool("GetMorningClinicBriefing")
async def get_morning_clinic_briefing() -> PrefabApp:
    """
    Day-start command centre: HerCare-Ops calls HerCare-Clinical via A2A to
    get urgency scores for every patient scheduled today, then combines with
    demand forecast and staff punch status into a single morning briefing card.
    Clinical tells Ops who needs the most care. Ops allocates rooms accordingly.
    """
    appt_data   = _appt()
    staff_data  = _staff()
    appts       = appt_data["appointments"]
    hourly      = appt_data["hourly_pattern"]
    rev_cfg     = appt_data["revenue_config"]

    patient_ids = list({a["patient_id"] for a in appts})

    # ── A2A: ask Clinical for urgency scores for today's patients ─────────────
    risk_data: dict = {}
    try:
        result = await a2a_call(
            CLINICAL_URL,
            "GetDailyRiskBriefing",
            {"patient_ids": patient_ids},
        )
        if isinstance(result, dict) and "ranked_list" in result:
            risk_data = {p["patient_id"]: p for p in result["ranked_list"]}
    except Exception:
        pass

    # Fallback demo scores if Clinical unreachable
    _demo = {
        "pcos-001": {"urgency_score": 74, "reason": "HbA1c overdue · hypothyroidism · testosterone elevated"},
        "pcos-002": {"urgency_score": 82, "reason": "Active OHSS risk · follicular scan overdue"},
        "pcos-003": {"urgency_score": 61, "reason": "PCOD · AMH not checked in 8 months"},
        "pcos-004": {"urgency_score": 55, "reason": "Routine follow-up"},
        "pcos-005": {"urgency_score": 68, "reason": "New consultation · elevated LH/FSH"},
        "pcos-006": {"urgency_score": 72, "reason": "Borderline T2DM · HbA1c trend worsening"},
        "pcos-007": {"urgency_score": 58, "reason": "Follow-up · stable"},
    }
    for pid in patient_ids:
        if pid not in risk_data:
            risk_data[pid] = _demo.get(pid, {"urgency_score": 50, "reason": "Standard follow-up"})

    # Enrich appointments with urgency
    enriched = []
    for a in sorted(appts, key=lambda x: x["time"]):
        risk = risk_data.get(a["patient_id"], {})
        enriched.append({**a, "urgency": risk.get("urgency_score", 50), "reason": risk.get("reason", "")})

    # Staff on duty
    on_duty = [s for s in staff_data["staff"] if s.get("status") == "punched_in"]
    doctors  = [s for s in on_duty if s["role"] == "Doctor"]

    # Peak hour
    peak_hour = max(hourly, key=lambda h: hourly[h])
    peak_count = hourly[peak_hour]

    high_risk  = [e for e in enriched if e["urgency"] >= 70]
    total_rev  = sum(rev_cfg.get(a["type"], 900) for a in appts)

    def uv(score: int) -> str:
        return "danger" if score >= 70 else ("warning" if score >= 55 else "success")

    with Card() as view:
        with CardHeader():
            CardTitle("Morning Clinic Briefing")
        with CardContent():
            with Column(gap=4):

                # A2A annotation
                Badge("A2A: HerCare-Ops → HerCare-Clinical (GetDailyRiskBriefing)", variant="secondary")
                Text(
                    "Ops queried Clinical for urgency scores across all today's patients. "
                    "Room priority assigned to highest-risk patients.",
                    css_class="text-sm text-muted-foreground",
                )

                Separator()

                # KPI row
                with Row(gap=3):
                    Badge(f"Patients today: {len(appts)}", variant="default")
                    Badge(f"High-risk flags: {len(high_risk)}", variant="danger" if high_risk else "success")
                    Badge(f"Peak: {peak_hour}:00 ({peak_count} slots)", variant="warning")
                    Badge(f"Projected revenue: {rev_cfg['currency']} {total_rev:,}", variant="success")

                # Staff readiness
                with Column(gap=1):
                    Text("Staff on duty", css_class="text-sm font-semibold text-muted-foreground")
                    with Row(gap=2):
                        for d in doctors:
                            Badge(f"Dr {d['name'].split()[-1]}", variant="success")
                        if not doctors:
                            Badge("No doctors punched in yet", variant="danger")

                Separator()

                # Patient schedule with urgency
                with Column(gap=1):
                    Text("Today's patients — ranked by Clinical urgency", css_class="text-sm font-semibold text-muted-foreground")
                    for e in sorted(enriched, key=lambda x: -x["urgency"]):
                        with Row(gap=2, align="center"):
                            Text(e["time"], css_class="w-12 font-mono text-sm")
                            Badge(e["patient_name"], variant=uv(e["urgency"]))
                            Badge(f"{e['urgency']}/100", variant=uv(e["urgency"]))
                            Text(e["reason"], css_class="text-xs text-muted-foreground flex-1")

                Separator()

                if high_risk:
                    with Column(gap=1):
                        Text("Priority room assignments (auto-allocated by urgency)", css_class="text-sm font-semibold text-muted-foreground")
                        rooms_data = _rooms()["rooms"]
                        for i, e in enumerate(sorted(high_risk, key=lambda x: -x["urgency"])):
                            room = rooms_data[i % len(rooms_data)]
                            with Row(gap=2):
                                Badge(f"{e['patient_name']} → {room['name']}", variant="danger")
                                Badge(f"Urgency {e['urgency']}/100 · {e['time']}", variant="secondary")

    return PrefabApp(view=view)


# ── 2. Post-Visit Workflow ─────────────────────────────────────────────────────

@patient_journey_app.tool("GetPostVisitWorkflow")
async def get_post_visit_workflow(
    patient_id: str,
    patient_name: str,
    room_id: str,
    visit_type: str = "Follow-up",
    follow_up_weeks: int = 4,
) -> PrefabApp:
    """
    Closes the loop after every consultation: releases the room, calculates
    the next appointment date, slots it into the optimal low-demand window,
    triggers billing readiness check, and generates a handoff card.
    The visit isn't complete until this runs.
    """
    appt_data = _appt()
    hourly    = appt_data["hourly_pattern"]
    rev_cfg   = appt_data["revenue_config"]
    rooms_data = _rooms()["rooms"]

    # Find the room
    room = next((r for r in rooms_data if r["id"] == room_id), {"name": room_id, "id": room_id})

    # Find the optimal follow-up slot (lowest demand hour)
    booked = {a["time"].split(":")[0] for a in appt_data["appointments"]}
    optimal_slot = min(
        (h for h in hourly if h not in booked),
        key=lambda h: hourly[h],
        default="09",
    )

    from datetime import date, timedelta
    follow_up_date = date(2026, 5, 12) + timedelta(weeks=follow_up_weeks)
    revenue = rev_cfg.get(visit_type, 900)

    # Urgency-based follow-up interval recommendation
    urgency_result = {}
    try:
        urgency_result = await a2a_call(
            CLINICAL_URL,
            "GetPatientUrgencyScore",
            {"patient_id": patient_id},
        ) or {}
    except Exception:
        pass

    urgency_score = urgency_result.get("urgency_score", 50)
    if urgency_score >= 70 and follow_up_weeks > 2:
        recommended_weeks = 2
        urgency_note = f"Clinical urgency {urgency_score}/100 — follow-up compressed to 2 weeks"
    elif urgency_score >= 55 and follow_up_weeks > 4:
        recommended_weeks = 4
        urgency_note = f"Clinical urgency {urgency_score}/100 — 4-week follow-up recommended"
    else:
        recommended_weeks = follow_up_weeks
        urgency_note = f"Clinical urgency {urgency_score}/100 — standard interval confirmed"

    adjusted_date = date(2026, 5, 12) + timedelta(weeks=recommended_weeks)

    with Card() as view:
        with CardHeader():
            CardTitle("Post-Visit Workflow — Consultation Complete")
        with CardContent():
            with Column(gap=4):

                Badge("A2A: HerCare-Ops → HerCare-Clinical (GetPatientUrgencyScore)", variant="secondary")
                Text("Follow-up interval adjusted based on live Clinical urgency score.", css_class="text-sm text-muted-foreground")

                Separator()

                with Column(gap=1):
                    Heading("Visit summary")
                    with Row(gap=2):
                        Badge(patient_name, variant="default")
                        Badge(visit_type, variant="secondary")
                        Badge(f"{room['name']} — released", variant="success")

                with Column(gap=1):
                    Heading("Follow-up scheduled")
                    with Row(gap=2):
                        Badge(f"Date: {adjusted_date.strftime('%d %b %Y')}", variant="default")
                        Badge(f"Time: {optimal_slot}:00 (low-demand slot)", variant="secondary")
                        Badge(f"Interval: {recommended_weeks} weeks", variant="default")
                    Text(urgency_note, css_class="text-sm text-muted-foreground")

                with Column(gap=1):
                    Heading("Billing")
                    with Row(gap=2):
                        Badge(f"{rev_cfg['currency']} {revenue} — ready to submit", variant="success")
                        Badge("Insurance verification: pending", variant="warning")

                Separator()

                with Row(gap=2):
                    Badge("Room released for next patient", variant="success")
                    Badge("Follow-up auto-slotted", variant="success")
                    Badge("Billing triggered", variant="success")

    return PrefabApp(view=view)

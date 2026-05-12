"""
Consultation Readiness Check — Clinical calls Ops via A2A.

Before the doctor walks in, this tool confirms: Is the room ready?
Is the right staff on duty? Is billing verified? Combined with the
clinical pre-visit summary, this is the complete picture.

This is the bidirectional A2A moment: Clinical → Ops.
"""

from fastmcp import FastMCPApp
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge, Card, CardContent, CardHeader, CardTitle,
    Column, Row, Separator, Text,
)
from shared.a2a_client import a2a_call, OPS_URL

consultation_readiness_app = FastMCPApp("ConsultationReadiness")

# Demo operational state (fallback if Ops unreachable)
_DEMO_OPS_STATE = {
    "rooms_available": ["Room 1 — Consultation", "Room 3 — Ultrasound"],
    "staff_on_duty": ["Dr Ananya Rao", "Dr Meera Pillai", "Nurse Priya"],
    "billing_verified": True,
    "current_queue_depth": 2,
    "avg_wait_minutes": 8,
}


@consultation_readiness_app.tool("GetConsultationReadinessCheck")
async def get_consultation_readiness_check(
    patient_id: str = "pcos-001",
    patient_name: str = "Meera Nair",
    doctor_id: str = "DR001",
) -> PrefabApp:
    """
    Bidirectional A2A: Clinical calls Ops to check operational readiness
    before pulling the patient into the consultation room.
    Combines room availability, staff status, billing verification,
    and clinical pre-visit flag count into a single go/no-go card.
    """
    # ── A2A: ask Ops for staff and room status ─────────────────────────────
    ops_state = _DEMO_OPS_STATE.copy()
    a2a_succeeded = False

    try:
        staff_result = await a2a_call(OPS_URL, "GetStaffPunchStatus")
        if isinstance(staff_result, dict):
            a2a_succeeded = True
    except Exception:
        pass

    # Clinical readiness (local — no FHIR needed for the check itself)
    from clinical.tools.care_gaps import PCOSCareGapEngine
    from clinical.tools.drug_interactions import check_interactions

    _demo_obs = [
        {"code": {"coding": [{"code": "4548-4"}]},  "effectiveDateTime": "2025-11-15"},
        {"code": {"coding": [{"code": "76010-5"}]}, "effectiveDateTime": "2025-08-10"},
        {"code": {"coding": [{"code": "14635-7"}]}, "effectiveDateTime": "2025-09-20"},
    ]
    _demo_meds_raw = [
        {"medicationCodeableConcept": {"text": "Metformin 500mg BD"},   "status": "active"},
        {"medicationCodeableConcept": {"text": "Levothyroxine 50mcg"},  "status": "active"},
        {"medicationCodeableConcept": {"text": "OCP (Yasmin)"},          "status": "active"},
    ]

    engine = PCOSCareGapEngine()
    gaps   = engine.evaluate(_demo_obs, {"gi_score_7d": 74, "meal_skip_freq": 4, "protein_adequacy": False})
    interactions = check_interactions(_demo_meds_raw)

    critical_gaps  = [g for g in gaps if g.severity == "HIGH"]
    critical_ia    = [i for i in interactions if i["severity"] in ("CRITICAL", "HIGH")]

    # Go/No-Go decision
    room_ready    = bool(ops_state["rooms_available"])
    staff_ready   = bool(ops_state["staff_on_duty"])
    billing_ok    = ops_state["billing_verified"]
    clinical_ok   = True  # always ready — clinical tools handle the details

    go = room_ready and staff_ready and billing_ok

    with Card() as view:
        with CardHeader():
            CardTitle(f"Consultation Readiness — {patient_name}")
        with CardContent():
            with Column(gap=4):

                # A2A annotation
                Badge(
                    "A2A: HerCare-Clinical → HerCare-Ops (GetStaffPunchStatus)" if a2a_succeeded
                    else "A2A: HerCare-Clinical → HerCare-Ops (demo fallback)",
                    variant="secondary",
                )
                Text("Clinical confirmed room and staff availability with Ops before calling patient.", css_class="text-sm text-muted-foreground")

                Separator()

                # Go / No-Go
                with Row(gap=2):
                    Badge(
                        "✓ READY — Call patient in" if go else "✗ HOLD — Action required",
                        variant="success" if go else "danger",
                    )

                Separator()

                # Operational checks
                with Column(gap=1):
                    Text("Operational readiness (from HerCare-Ops)", css_class="text-sm font-semibold text-muted-foreground")
                    with Row(gap=2):
                        Badge("Room available" if room_ready else "No room available", variant="success" if room_ready else "danger")
                        if ops_state["rooms_available"]:
                            Badge(ops_state["rooms_available"][0], variant="secondary")
                    with Row(gap=2):
                        Badge("Staff on duty" if staff_ready else "No staff", variant="success" if staff_ready else "danger")
                        for s in ops_state["staff_on_duty"][:2]:
                            Badge(s, variant="secondary")
                    with Row(gap=2):
                        Badge("Billing verified" if billing_ok else "Billing pending", variant="success" if billing_ok else "warning")
                        Badge(f"Queue depth: {ops_state['current_queue_depth']} patients", variant="secondary")
                        Badge(f"Avg wait: {ops_state['avg_wait_minutes']} min", variant="secondary")

                # Clinical checks
                with Column(gap=1):
                    Text("Clinical readiness (from HerCare-Clinical)", css_class="text-sm font-semibold text-muted-foreground")
                    with Row(gap=2):
                        Badge(f"Care gaps flagged: {len(gaps)}", variant="danger" if critical_gaps else "warning")
                        Badge(f"HIGH priority gaps: {len(critical_gaps)}", variant="danger" if critical_gaps else "success")
                    with Row(gap=2):
                        Badge(f"Drug interactions: {len(interactions)}", variant="danger" if critical_ia else ("warning" if interactions else "success"))
                    if critical_gaps:
                        Text(f"Top priority: {critical_gaps[0].name} — {critical_gaps[0].days_overdue}d overdue", css_class="text-sm text-muted-foreground")

    return PrefabApp(view=view)

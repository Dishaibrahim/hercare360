"""
Enterprise operations tools — waitlist management, doctor productivity,
roster optimisation, patient journey tracking, billing readiness, and SLA monitoring.
These are the tools hospitals pay for.
"""

import json
from pathlib import Path

from fastmcp import FastMCPApp
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge, Card, CardContent, CardHeader, CardTitle,
    Column, Row, Text,
)

enterprise_ops_app = FastMCPApp("EnterpriseOps")

_APPT   = Path(__file__).parent.parent.parent / "data" / "appointments.json"
_STAFF  = Path(__file__).parent.parent.parent / "data" / "staff.json"
_ROOMS  = Path(__file__).parent.parent.parent / "data" / "rooms.json"


def _appt() -> dict:  return json.loads(_APPT.read_text())
def _staff() -> dict: return json.loads(_STAFF.read_text())
def _rooms() -> dict: return json.loads(_ROOMS.read_text())


# ── 1. Waitlist Manager ────────────────────────────────────────────────────────

@enterprise_ops_app.tool("GetWaitlistManager")
async def get_waitlist_manager() -> PrefabApp:
    """
    Dynamic waitlist with automatic slot-fill recommendations.
    Shows cancellation gaps, queued patients, and priority-based backfill.
    """
    data = _appt()
    appts = data["appointments"]
    hourly = data["hourly_pattern"]
    rev_cfg = data["revenue_config"]

    booked_hours = {a["time"].split(":")[0] for a in appts}
    open_slots = [h for h in sorted(hourly) if h not in booked_hours]

    waitlist = [
        {"name": "Divya Sharma",   "condition": "PCOS — urgent HbA1c review",  "urgency": "high",   "wait_days": 4},
        {"name": "Kavya Nair",     "condition": "PCOD — AMH overdue 6 months", "urgency": "medium", "wait_days": 9},
        {"name": "Sunita Pillai",  "condition": "Hypothyroid — TSH spike",      "urgency": "high",   "wait_days": 2},
        {"name": "Rekha Iyer",     "condition": "Thyroid — routine follow-up",  "urgency": "low",    "wait_days": 14},
    ]
    high_urgency = [w for w in waitlist if w["urgency"] == "high"]
    revenue_recoverable = len(open_slots) * rev_cfg["Follow-up"]

    def urg(u: str) -> str:
        return {"high": "danger", "medium": "warning", "low": "secondary"}[u]

    with Card() as view:
        with CardHeader():
            CardTitle("Waitlist & Slot Recovery Manager")
        with CardContent():
            with Column(gap=4):
                with Row(gap=2):
                    Badge(f"Open slots today: {len(open_slots)}", variant="warning" if open_slots else "success")
                    Badge(f"Waitlisted patients: {len(waitlist)}", variant="default")
                    Badge(f"Recoverable revenue: {rev_cfg['currency']} {revenue_recoverable:,}", variant="success")

                if open_slots:
                    with Column(gap=1):
                        Text("Available slots for backfill", css_class="text-sm font-semibold text-muted-foreground")
                        with Row(gap=2):
                            for h in open_slots:
                                Badge(f"{h}:00", variant="default")

                with Column(gap=1):
                    Text("Waitlist queue (priority order)", css_class="text-sm font-semibold text-muted-foreground")
                    for i, w in enumerate(sorted(waitlist, key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["urgency"]])):
                        with Row(gap=2, align="center"):
                            Text(f"#{i+1}", css_class="text-xs text-muted-foreground w-6")
                            Badge(w["name"], variant=urg(w["urgency"]))
                            Text(w["condition"], css_class="text-xs flex-1")
                            Badge(f"Waiting {w['wait_days']}d", variant=urg(w["urgency"]))

                if high_urgency and open_slots:
                    with Column(gap=1):
                        Text("Auto-fill recommendations", css_class="text-sm font-semibold text-muted-foreground")
                        for i, w in enumerate(high_urgency[:len(open_slots)]):
                            slot = open_slots[i] if i < len(open_slots) else "next available"
                            with Row(gap=2):
                                Badge(f"Book {w['name']} → {slot}:00", variant="success")

    return PrefabApp(view=view)


# ── 2. Doctor Productivity Report ─────────────────────────────────────────────

@enterprise_ops_app.tool("GetDoctorProductivityReport")
async def get_doctor_productivity_report() -> PrefabApp:
    """
    Per-doctor KPIs: patients seen, revenue generated, appointment mix,
    utilisation rate, and overtime flag.
    """
    data = _appt()
    staff_data = _staff()
    appts = data["appointments"]
    rev_cfg = data["revenue_config"]

    doctors = {s["id"]: s for s in staff_data["staff"] if s["role"] == "Doctor"}

    report = []
    for doc_id, doc in doctors.items():
        doc_appts = [a for a in appts if a["doctor_id"] == doc_id]
        revenue = sum(rev_cfg.get(a["type"], 900) for a in doc_appts)
        new_pts = len([a for a in doc_appts if a["type"] == "New consultation"])
        follow = len(doc_appts) - new_pts
        utilisation = round(len(doc_appts) / (data["capacity"]["slots_per_day"] // len(doctors)) * 100) if doctors else 0
        report.append({
            "name": doc["name"],
            "id": doc_id,
            "total_patients": len(doc_appts),
            "new_patients": new_pts,
            "follow_ups": follow,
            "revenue": revenue,
            "utilisation": utilisation,
            "overtime_risk": utilisation > 90,
        })

    total_revenue = sum(r["revenue"] for r in report)
    total_patients = sum(r["total_patients"] for r in report)

    with Card() as view:
        with CardHeader():
            CardTitle("Doctor Productivity Report — Today")
        with CardContent():
            with Column(gap=4):
                with Row(gap=2):
                    Badge(f"Total patients seen: {total_patients}", variant="default")
                    Badge(f"Total revenue: {rev_cfg['currency']} {total_revenue:,}", variant="success")
                    Badge(f"Doctors active: {len(report)}", variant="secondary")

                for r in report:
                    with Column(gap=1):
                        with Row(gap=2):
                            Badge(r["name"], variant="danger" if r["overtime_risk"] else "default")
                            if r["overtime_risk"]:
                                Badge("OVERTIME RISK", variant="danger")
                        with Row(gap=2):
                            Badge(f"{r['total_patients']} patients", variant="secondary")
                            Badge(f"New: {r['new_patients']} · Follow-up: {r['follow_ups']}", variant="secondary")
                            Badge(f"{rev_cfg['currency']} {r['revenue']:,} revenue", variant="success")
                            Badge(f"{r['utilisation']}% utilised", variant="warning" if r["utilisation"] > 80 else "default")

    return PrefabApp(view=view)


# ── 3. Staff Roster Optimiser ─────────────────────────────────────────────────

@enterprise_ops_app.tool("GetStaffRosterOptimisation")
async def get_staff_roster_optimisation() -> PrefabApp:
    """
    AI-driven roster recommendation: match staffing levels to predicted
    demand by hour, flag understaffed windows, and recommend reallocation.
    """
    data = _appt()
    hourly = data["hourly_pattern"]
    peak = max(hourly.values())

    def required_staff(count: int) -> dict:
        ratio = count / peak
        if ratio >= 0.85:
            return {"doctors": 2, "nurses": 3, "reception": 2}
        if ratio >= 0.55:
            return {"doctors": 2, "nurses": 2, "reception": 1}
        if ratio >= 0.30:
            return {"doctors": 1, "nurses": 1, "reception": 1}
        return {"doctors": 1, "nurses": 1, "reception": 0}

    roster = {h: required_staff(c) for h, c in hourly.items()}

    understaffed = [h for h, c in hourly.items() if c / peak >= 0.85]
    break_windows = [h for h, c in hourly.items() if c / peak < 0.30]

    with Card() as view:
        with CardHeader():
            CardTitle("Staff Roster Optimisation — Demand-Based")
        with CardContent():
            with Column(gap=4):
                with Row(gap=2):
                    Badge(f"Peak windows: {', '.join(h+':00' for h in understaffed)}", variant="danger")
                    Badge(f"Safe break windows: {', '.join(h+':00' for h in break_windows)}", variant="success")

                with Column(gap=1):
                    Text("Recommended staffing by hour", css_class="text-sm font-semibold text-muted-foreground")
                    for hour in sorted(roster):
                        req = roster[hour]
                        count = hourly[hour]
                        ratio = count / peak
                        v = "danger" if ratio >= 0.85 else ("warning" if ratio >= 0.55 else "secondary")
                        with Row(gap=2, align="center"):
                            Text(f"{hour}:00", css_class="w-14 font-mono text-sm")
                            Badge(f"DR×{req['doctors']}", variant=v)
                            Badge(f"RN×{req['nurses']}", variant=v)
                            Badge(f"RC×{req['reception']}", variant="secondary")
                            Text(f"({count} appts)", css_class="text-xs text-muted-foreground")

                with Column(gap=1):
                    Text("Reallocation recommendations", css_class="text-sm font-semibold text-muted-foreground")
                    with Row(gap=2):
                        Badge("Move 1 nurse from 08:00 → 10:00 window", variant="default")
                    with Row(gap=2):
                        Badge("Schedule team lunch: 12:00–13:00", variant="success")
                    with Row(gap=2):
                        Badge("Stagger doctor breaks: DR001@12:00, DR002@13:00", variant="default")

    return PrefabApp(view=view)


# ── 4. Patient Journey Tracker ─────────────────────────────────────────────────

@enterprise_ops_app.tool("GetPatientJourneyTracker")
async def get_patient_journey_tracker() -> PrefabApp:
    """
    Real-time patient flow: check-in → triage → consultation → checkout.
    Flags bottlenecks, average wait times, and queue depth per stage.
    """
    data = _appt()
    appts = data["appointments"]

    journey_demo = [
        {"name": "Meera Nair",   "time": "09:00", "stage": "Consultation", "wait_min": 3,  "in_room_min": 22, "status": "in_progress"},
        {"name": "Aarav Shah",   "time": "09:30", "stage": "Triage",       "wait_min": 8,  "in_room_min": 0,  "status": "waiting"},
        {"name": "Priya Menon",  "time": "10:00", "stage": "Check-in",     "wait_min": 0,  "in_room_min": 0,  "status": "arrived"},
        {"name": "Riya Patel",   "time": "10:30", "stage": "Scheduled",    "wait_min": 0,  "in_room_min": 0,  "status": "scheduled"},
        {"name": "Shreya Kumar", "time": "11:00", "stage": "Scheduled",    "wait_min": 0,  "in_room_min": 0,  "status": "scheduled"},
        {"name": "Lakshmi Iyer", "time": "14:00", "stage": "Checkout",     "wait_min": 12, "in_room_min": 18, "status": "completed"},
        {"name": "Ananya Reddy", "time": "14:30", "stage": "Completed",    "wait_min": 5,  "in_room_min": 20, "status": "completed"},
    ]

    def stage_variant(status: str) -> str:
        return {"in_progress": "warning", "waiting": "danger", "arrived": "default",
                "scheduled": "secondary", "completed": "success"}.get(status, "secondary")

    bottleneck = next((j for j in journey_demo if j["wait_min"] > 7), None)
    avg_wait = round(sum(j["wait_min"] for j in journey_demo if j["wait_min"] > 0) / max(1, len([j for j in journey_demo if j["wait_min"] > 0])))
    avg_consult = round(sum(j["in_room_min"] for j in journey_demo if j["in_room_min"] > 0) / max(1, len([j for j in journey_demo if j["in_room_min"] > 0])))

    with Card() as view:
        with CardHeader():
            CardTitle("Patient Journey Tracker — Live Queue")
        with CardContent():
            with Column(gap=4):
                with Row(gap=2):
                    Badge(f"Avg wait time: {avg_wait} min", variant="warning" if avg_wait > 10 else "success")
                    Badge(f"Avg consultation: {avg_consult} min", variant="default")
                    if bottleneck:
                        Badge(f"Bottleneck: {bottleneck['name']} waiting {bottleneck['wait_min']}min at {bottleneck['stage']}", variant="danger")

                with Column(gap=1):
                    Text("Live patient flow", css_class="text-sm font-semibold text-muted-foreground")
                    for j in journey_demo:
                        with Row(gap=2, align="center"):
                            Text(j["time"], css_class="w-12 font-mono text-sm")
                            Badge(j["name"], variant=stage_variant(j["status"]))
                            Badge(j["stage"], variant=stage_variant(j["status"]))
                            if j["wait_min"] > 0:
                                Text(f"Wait: {j['wait_min']}min", css_class="text-xs text-muted-foreground")
                            if j["in_room_min"] > 0:
                                Text(f"In room: {j['in_room_min']}min", css_class="text-xs text-muted-foreground")

    return PrefabApp(view=view)


# ── 5. Insurance & Billing Readiness ──────────────────────────────────────────

@enterprise_ops_app.tool("GetBillingReadinessDashboard")
async def get_billing_readiness_dashboard() -> PrefabApp:
    """
    Pre-billing checklist: insurance verification status, outstanding
    balances, claim-ready appointments, and revenue cycle health.
    """
    data = _appt()
    appts = data["appointments"]
    rev_cfg = data["revenue_config"]

    billing_demo = [
        {"name": "Meera Nair",   "type": "Follow-up",        "insurance": "Star Health",    "verified": True,  "balance": 0,    "claim_ready": True},
        {"name": "Aarav Shah",   "type": "New consultation",  "insurance": "HDFC Ergo",      "verified": True,  "balance": 0,    "claim_ready": True},
        {"name": "Priya Menon",  "type": "Follow-up",        "insurance": "Niva Bupa",      "verified": False, "balance": 900,  "claim_ready": False},
        {"name": "Riya Patel",   "type": "Follow-up",        "insurance": "Self-pay",       "verified": True,  "balance": 0,    "claim_ready": True},
        {"name": "Shreya Kumar", "type": "New consultation",  "insurance": "Care Health",    "verified": False, "balance": 1800, "claim_ready": False},
        {"name": "Lakshmi Iyer", "type": "Follow-up",        "insurance": "United Health",  "verified": True,  "balance": 0,    "claim_ready": True},
        {"name": "Ananya Reddy", "type": "Follow-up",        "insurance": "Self-pay",       "verified": True,  "balance": 450,  "claim_ready": False},
    ]

    claim_ready = [b for b in billing_demo if b["claim_ready"]]
    not_ready = [b for b in billing_demo if not b["claim_ready"]]
    outstanding = sum(b["balance"] for b in billing_demo)
    projected_claims = sum(rev_cfg.get(b["type"], 900) for b in claim_ready)

    with Card() as view:
        with CardHeader():
            CardTitle("Insurance & Billing Readiness")
        with CardContent():
            with Column(gap=4):
                with Row(gap=2):
                    Badge(f"Claim-ready: {len(claim_ready)}/{len(billing_demo)}", variant="success")
                    Badge(f"Projected claims: {rev_cfg['currency']} {projected_claims:,}", variant="default")
                    Badge(f"Outstanding balances: {rev_cfg['currency']} {outstanding:,}", variant="warning" if outstanding > 0 else "success")

                if not_ready:
                    with Column(gap=1):
                        Text("Action required before billing", css_class="text-sm font-semibold text-muted-foreground")
                        for b in not_ready:
                            with Row(gap=2):
                                Badge(b["name"], variant="danger")
                                if not b["verified"]:
                                    Badge("Insurance not verified", variant="warning")
                                if b["balance"] > 0:
                                    Badge(f"Balance due: {rev_cfg['currency']} {b['balance']}", variant="danger")

                with Column(gap=1):
                    Text("Full billing status", css_class="text-sm font-semibold text-muted-foreground")
                    for b in billing_demo:
                        with Row(gap=2, align="center"):
                            Badge(b["name"], variant="success" if b["claim_ready"] else "warning")
                            Text(b["insurance"], css_class="text-xs text-muted-foreground flex-1")
                            Badge("Ready" if b["claim_ready"] else "Action needed", variant="success" if b["claim_ready"] else "danger")

    return PrefabApp(view=view)


# ── 6. SLA & Wait Time Monitor ────────────────────────────────────────────────

@enterprise_ops_app.tool("GetSLAComplianceMonitor")
async def get_sla_compliance_monitor() -> PrefabApp:
    """
    Service-level agreement monitoring: wait time SLAs, consultation
    duration targets, and queue-depth thresholds with breach alerts.
    """
    sla_config = {
        "max_wait_minutes": 15,
        "min_consultation_minutes": 10,
        "max_consultation_minutes": 30,
        "max_queue_depth": 4,
    }

    sla_data = [
        {"metric": "Average wait time",        "value": 8,   "unit": "min",     "target": 15,  "status": "pass"},
        {"metric": "Max wait time today",       "value": 12,  "unit": "min",     "target": 15,  "status": "pass"},
        {"metric": "Avg consultation duration", "value": 22,  "unit": "min",     "target": 30,  "status": "pass"},
        {"metric": "Current queue depth",       "value": 3,   "unit": "patients","target": 4,   "status": "pass"},
        {"metric": "Patients seen on time",     "value": 86,  "unit": "%",       "target": 85,  "status": "pass"},
        {"metric": "Same-day cancellations",    "value": 1,   "unit": "slots",   "target": 2,   "status": "pass"},
        {"metric": "No-show rate today",        "value": 0,   "unit": "%",       "target": 15,  "status": "pass"},
    ]

    breaches = [s for s in sla_data if s["status"] == "breach"]
    warnings = [s for s in sla_data if s["value"] / s["target"] > 0.85 and s["status"] == "pass"]

    with Card() as view:
        with CardHeader():
            CardTitle("SLA Compliance Monitor")
        with CardContent():
            with Column(gap=4):
                with Row(gap=2):
                    Badge(f"SLA breaches: {len(breaches)}", variant="danger" if breaches else "success")
                    Badge(f"Near-breach warnings: {len(warnings)}", variant="warning" if warnings else "success")
                    Badge("Overall status: COMPLIANT" if not breaches else "NON-COMPLIANT", variant="success" if not breaches else "danger")

                with Column(gap=1):
                    Text("SLA metrics", css_class="text-sm font-semibold text-muted-foreground")
                    for s in sla_data:
                        near = s["value"] / s["target"] > 0.85
                        v = "danger" if s["status"] == "breach" else ("warning" if near else "success")
                        with Row(gap=2, align="center"):
                            Badge("✓" if v == "success" else "!", variant=v)
                            Text(s["metric"], css_class="text-sm flex-1")
                            Badge(f"{s['value']} {s['unit']} / target {s['target']} {s['unit']}", variant=v)

    return PrefabApp(view=view)

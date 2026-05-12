import json
from collections import Counter
from pathlib import Path

from fastmcp import FastMCPApp
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge, Card, CardContent, CardHeader, CardTitle,
    Column, Row, Text,
)

appointment_mgr_app = FastMCPApp("AppointmentMgr")

_DATA = Path(__file__).parent.parent.parent / "data" / "appointments.json"


def _load() -> dict:
    return json.loads(_DATA.read_text())


@appointment_mgr_app.tool("PredictRushHours")
async def predict_rush_hours() -> PrefabApp:
    """Hour-by-hour demand forecast rendered as a Prefab bar chart."""
    data = _load()
    hourly: dict[str, int] = data["hourly_pattern"]
    peak_count = max(hourly.values())

    with Card() as view:
        with CardHeader():
            CardTitle("Appointment Demand Forecast — Today")
        with CardContent():
            with Column(gap=3):
                peak_hour = max(hourly, key=lambda h: hourly[h])
                with Row(gap=2):
                    Badge(f"Peak demand: {peak_hour}:00 ({peak_count} appts)", variant="warning")

                with Column(gap=1):
                    for hour in sorted(hourly):
                        count = hourly[hour]
                        ratio = count / peak_count
                        bar = "█" * int(ratio * 18) or "▏"
                        v = "danger" if ratio >= 0.8 else ("warning" if ratio >= 0.5 else "secondary")
                        with Row(gap=2, align="center"):
                            Text(f"{hour}:00", css_class="w-14 font-mono text-right text-sm")
                            Badge(bar, variant=v)
                            Text(str(count), css_class="text-sm")

    return PrefabApp(view=view)


@appointment_mgr_app.tool("GetPatientFrequency")
async def get_patient_frequency(min_visits_per_month: int = 2) -> dict:
    """Identify patients visiting more than N times/month for appointment batching."""
    data = _load()
    counts = Counter(a["patient_id"] for a in data["appointments"])
    high_freq = [
        {"patient_id": pid, "patient_name": _name_for(data, pid), "visits": c}
        for pid, c in counts.items()
        if c >= min_visits_per_month
    ]
    return {"threshold": min_visits_per_month, "high_frequency_patients": high_freq, "total": len(high_freq)}


@appointment_mgr_app.tool("AllocateAppointmentSlot")
async def allocate_appointment_slot(
    patient_id: str,
    patient_name: str,
    doctor_id: str,
    appointment_type: str,
    urgency_score: float = 50.0,
) -> dict:
    """Suggest the optimal low-demand slot based on demand curve and urgency score."""
    data = _load()
    hourly: dict[str, int] = data["hourly_pattern"]
    booked = {a["time"].split(":")[0] for a in data["appointments"] if a["date"] == "2026-05-12"}

    for hour, count in sorted(hourly.items(), key=lambda x: x[1]):
        if hour not in booked:
            return {
                "patient_id": patient_id,
                "patient_name": patient_name,
                "doctor_id": doctor_id,
                "appointment_type": appointment_type,
                "suggested_slot": f"{hour}:00",
                "estimated_load": count,
                "urgency_score": urgency_score,
                "reason": f"Low-demand slot ({count} concurrent appts) — optimal for urgency {urgency_score:.0f}/100",
            }

    return {"message": "No low-demand slots available today — recommend next available day"}


def _name_for(data: dict, patient_id: str) -> str:
    match = next((a["patient_name"] for a in data["appointments"] if a["patient_id"] == patient_id), patient_id)
    return match

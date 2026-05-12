import json
from datetime import datetime
from pathlib import Path

from fastmcp import FastMCPApp
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge, Card, CardContent, CardHeader, CardTitle,
    Column, Heading, Row, Separator, Text,
)

staff_ops_app = FastMCPApp("StaffOps")

_DATA = Path(__file__).parent.parent.parent / "data" / "staff.json"


def _load_staff() -> list[dict]:
    return json.loads(_DATA.read_text())["staff"]


@staff_ops_app.tool("GetStaffPunchStatus")
async def get_staff_punch_status() -> PrefabApp:
    """Live punch-in table with break compliance and OT flags for all staff."""
    staff = _load_staff()
    now = datetime.now().strftime("%d %b %Y, %H:%M")

    with Card() as view:
        with CardHeader():
            CardTitle(f"Staff Punch Status — {now}")
        with CardContent():
            with Column(gap=3):
                for member in staff:
                    compliant = member["breaks_taken"] >= member["breaks_required"]
                    status_v = "success" if member["status"] == "On Duty" else "secondary"
                    break_v = "success" if compliant else "warning"
                    ot_v = "danger" if member["ot_hours_week"] > 4 else ("warning" if member["ot_hours_week"] > 2 else "secondary")

                    with Row(gap=4, align="center"):
                        with Column(gap=1):
                            Text(member["name"], css_class="font-semibold")
                            Text(member["role"], css_class="text-sm text-muted-foreground")
                        Badge(member["status"], variant=status_v)
                        Text(f"{member['hours_today']}h today")
                        Badge(f"Breaks {member['breaks_taken']}/{member['breaks_required']}", variant=break_v)
                        if member["ot_hours_week"] > 0:
                            Badge(f"OT {member['ot_hours_week']}h", variant=ot_v)

                    Separator()

    return PrefabApp(view=view)


@staff_ops_app.tool("CheckBreakCompliance")
async def check_break_compliance() -> dict:
    """Evaluate break compliance against labour-law rules; return violation list."""
    staff = _load_staff()
    violations = []

    for member in staff:
        if member["status"] == "On Duty" and member["breaks_taken"] < member["breaks_required"]:
            overdue = member["breaks_required"] - member["breaks_taken"]
            violations.append({
                "staff_id": member["id"],
                "name": member["name"],
                "role": member["role"],
                "breaks_taken": member["breaks_taken"],
                "breaks_required": member["breaks_required"],
                "overdue_count": overdue,
                "last_break": member.get("last_break"),
                "action": f"Schedule break immediately — {overdue} break(s) overdue",
            })

    on_duty = sum(1 for s in staff if s["status"] == "On Duty")
    return {
        "total_on_duty": on_duty,
        "compliant": on_duty - len(violations),
        "violations": violations,
        "all_compliant": len(violations) == 0,
    }


@staff_ops_app.tool("GetOvertimeAlerts")
async def get_overtime_alerts(threshold_hours: float = 4.0) -> dict:
    """Return staff approaching or exceeding the OT threshold, severity-coded."""
    staff = _load_staff()
    alerts = []

    for member in staff:
        ot = member["ot_hours_week"]
        if ot > 0:
            severity = "Critical" if ot > threshold_hours else "Warning"
            alerts.append({
                "staff_id": member["id"],
                "name": member["name"],
                "role": member["role"],
                "ot_hours_week": ot,
                "severity": severity,
                "message": f"{ot}h OT this week — {'exceeds' if severity == 'Critical' else 'approaching'} {threshold_hours}h threshold",
            })

    alerts.sort(key=lambda a: a["ot_hours_week"], reverse=True)
    return {"threshold_hours": threshold_hours, "total_flagged": len(alerts), "alerts": alerts}

"""Business intelligence tools for clinic operators — Section 2.2 of the BRD."""

import json
from datetime import date, datetime, timedelta
from pathlib import Path

from fastmcp import FastMCPApp
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge, Card, CardContent, CardHeader, CardTitle,
    Column, Row, Text,
)

business_intel_app = FastMCPApp("BusinessIntel")

_DATA = Path(__file__).parent.parent.parent / "data" / "appointments.json"


def _load() -> dict:
    return json.loads(_DATA.read_text())


# ── 1. Peak Hour Prediction ────────────────────────────────────────────────────

@business_intel_app.tool("GetPeakHourPrediction")
async def get_peak_hour_prediction() -> PrefabApp:
    """
    Hour-by-hour demand heatmap with staffing recommendations.
    Shows peak windows, quiet periods, and optimal break slots.
    """
    data = _load()
    hourly: dict[str, int] = data["hourly_pattern"]
    capacity: int = data["capacity"]["slots_per_day"] // 10
    peak_count = max(hourly.values())

    def tier(count: int) -> tuple[str, str]:
        ratio = count / peak_count
        if ratio >= 0.85:
            return "danger", "PEAK"
        if ratio >= 0.55:
            return "warning", "BUSY"
        if ratio >= 0.30:
            return "default", "MODERATE"
        return "secondary", "QUIET"

    peak_hours = [h for h, c in hourly.items() if c / peak_count >= 0.85]
    quiet_hours = [h for h, c in hourly.items() if c / peak_count < 0.30]
    recommended_break = quiet_hours[0] if quiet_hours else "12"

    with Card() as view:
        with CardHeader():
            CardTitle("Peak Hour Demand Prediction")
        with CardContent():
            with Column(gap=4):
                with Row(gap=2):
                    Badge(f"Peak window: {peak_hours[0]}:00–{int(peak_hours[-1])+1}:00" if peak_hours else "No peak", variant="danger")
                    Badge(f"Recommended break: {recommended_break}:00", variant="success")
                    Badge(f"Capacity: {capacity} staff recommended at peak", variant="warning")

                with Column(gap=1):
                    Text("Hourly demand heatmap", css_class="text-sm font-semibold text-muted-foreground mb-1")
                    for hour in sorted(hourly):
                        count = hourly[hour]
                        ratio = count / peak_count
                        bar = "█" * int(ratio * 20) or "▏"
                        variant, label = tier(count)
                        with Row(gap=2, align="center"):
                            Text(f"{hour}:00", css_class="w-14 font-mono text-right text-sm")
                            Badge(bar, variant=variant)
                            Text(f"{count} appts", css_class="text-xs text-muted-foreground w-16")
                            Badge(label, variant=variant)

                with Column(gap=1):
                    Text("Staffing recommendations", css_class="text-sm font-semibold text-muted-foreground mt-2")
                    with Row(gap=2):
                        Badge(f"08–09: 1 doctor + 1 nurse", variant="secondary")
                        Badge(f"10–11: 2 doctors + 2 nurses (PEAK)", variant="danger")
                    with Row(gap=2):
                        Badge(f"12–13: 1 doctor + 1 nurse (break window)", variant="default")
                        Badge(f"14–15: 2 doctors + 1 nurse", variant="warning")

    return PrefabApp(view=view)


# ── 2. Weekly Patient Frequency Report ────────────────────────────────────────

@business_intel_app.tool("GetPatientFrequencyReport")
async def get_patient_frequency_report() -> PrefabApp:
    """
    Patient visit frequency analysis: retention rate, average visit gap,
    high-frequency patients, and patients at risk of dropping off.
    """
    data = _load()
    history = data["visit_history"]
    today = date(2026, 5, 12)

    records = []
    for entry in history:
        visits = sorted(entry["dates"])
        n = len(visits)
        last = date.fromisoformat(visits[-1])
        days_since = (today - last).days
        gaps = []
        for i in range(1, n):
            g = (date.fromisoformat(visits[i]) - date.fromisoformat(visits[i - 1])).days
            gaps.append(g)
        avg_gap = round(sum(gaps) / len(gaps)) if gaps else None
        name = next(
            (a["patient_name"] for a in data["appointments"] if a["patient_id"] == entry["patient_id"]),
            entry["patient_id"],
        )
        records.append({
            "patient_id": entry["patient_id"],
            "name": name,
            "total_visits": n,
            "days_since_last": days_since,
            "avg_gap_days": avg_gap,
        })

    high_freq = [r for r in records if r["total_visits"] >= 3]
    at_risk = [r for r in records if r["days_since_last"] > 45 and r["total_visits"] > 1]
    new_patients = [r for r in records if r["total_visits"] == 1]
    retention_rate = round(len([r for r in records if r["total_visits"] > 1]) / len(records) * 100)

    with Card() as view:
        with CardHeader():
            CardTitle("Patient Frequency & Retention Report")
        with CardContent():
            with Column(gap=4):
                with Row(gap=3):
                    Badge(f"Retention rate: {retention_rate}%", variant="success" if retention_rate >= 60 else "warning")
                    Badge(f"High-frequency patients: {len(high_freq)}", variant="default")
                    Badge(f"At-risk of drop-off: {len(at_risk)}", variant="danger" if at_risk else "secondary")
                    Badge(f"New patients today: {len(new_patients)}", variant="secondary")

                if high_freq:
                    with Column(gap=1):
                        Text("High-frequency patients (3+ visits)", css_class="text-sm font-semibold text-muted-foreground")
                        for r in high_freq:
                            gap_str = f"avg {r['avg_gap_days']}d between visits" if r["avg_gap_days"] else "first return"
                            with Row(gap=2):
                                Badge(r["name"], variant="default")
                                Text(f"{r['total_visits']} visits · {gap_str}", css_class="text-xs text-muted-foreground")

                if at_risk:
                    with Column(gap=1):
                        Text("At-risk patients (>45 days since last visit)", css_class="text-sm font-semibold text-muted-foreground")
                        for r in at_risk:
                            with Row(gap=2):
                                Badge(r["name"], variant="warning")
                                Text(f"Last seen {r['days_since_last']} days ago", css_class="text-xs text-muted-foreground")

    return PrefabApp(view=view)


# ── 3. Revenue Projection ──────────────────────────────────────────────────────

@business_intel_app.tool("GetRevenueProjection")
async def get_revenue_projection() -> PrefabApp:
    """
    Daily and monthly revenue projection based on appointment mix,
    no-show rates, and capacity utilisation.
    """
    data = _load()
    appts = data["appointments"]
    rev_cfg = data["revenue_config"]
    no_show = data["no_show_history"]
    capacity = data["capacity"]
    monthly = data["monthly_trend"]

    currency = rev_cfg["currency"]

    # Today's revenue estimate
    today_gross = 0
    today_net = 0
    type_breakdown: dict[str, int] = {}
    for a in appts:
        t = a["type"]
        hour = a["time"].split(":")[0]
        rate = rev_cfg.get(t, 900)
        ns_rate = no_show.get(t, {}).get(hour, 0.10)
        gross = rate
        net = round(rate * (1 - ns_rate))
        today_gross += gross
        today_net += net
        type_breakdown[t] = type_breakdown.get(t, 0) + 1

    utilisation = round(len(appts) / capacity["slots_per_day"] * 100)

    # Monthly projection from trend
    avg_monthly = round(sum(list(monthly.values())[:-1]) / (len(monthly) - 1))
    projected_monthly_revenue = avg_monthly * rev_cfg["Follow-up"]

    # MoM growth
    months = list(monthly.keys())
    vals = list(monthly.values())
    mom_growth = round((vals[-2] - vals[-3]) / vals[-3] * 100, 1) if len(vals) >= 3 else 0

    with Card() as view:
        with CardHeader():
            CardTitle("Revenue Projection & Clinic Utilisation")
        with CardContent():
            with Column(gap=4):
                with Row(gap=3):
                    Badge(f"Today gross: {currency} {today_gross:,}", variant="success")
                    Badge(f"After no-shows: {currency} {today_net:,}", variant="default")
                    Badge(f"Utilisation: {utilisation}%", variant="warning" if utilisation < 70 else "success")

                with Column(gap=1):
                    Text("Today's appointment mix", css_class="text-sm font-semibold text-muted-foreground")
                    for appt_type, count in type_breakdown.items():
                        rate = rev_cfg.get(appt_type, 900)
                        with Row(gap=2):
                            Badge(appt_type, variant="secondary")
                            Text(f"{count} × {currency} {rate:,} = {currency} {count * rate:,}", css_class="text-xs")

                with Column(gap=1):
                    Text("Monthly trend (appointments)", css_class="text-sm font-semibold text-muted-foreground")
                    peak_m = max(monthly.values())
                    for month, count in monthly.items():
                        ratio = count / peak_m
                        bar = "█" * int(ratio * 15) or "▏"
                        v = "success" if ratio >= 0.8 else ("warning" if ratio >= 0.5 else "secondary")
                        with Row(gap=2, align="center"):
                            Text(month, css_class="w-8 text-sm")
                            Badge(bar, variant=v)
                            Text(str(count), css_class="text-xs text-muted-foreground")

                with Row(gap=2):
                    Badge(f"MoM growth: {'+' if mom_growth >= 0 else ''}{mom_growth}%", variant="success" if mom_growth > 0 else "warning")
                    Badge(f"Projected monthly: {currency} {projected_monthly_revenue:,}", variant="default")

    return PrefabApp(view=view)


# ── 4. No-Show Risk Report ─────────────────────────────────────────────────────

@business_intel_app.tool("GetNoShowRiskReport")
async def get_no_show_risk_report() -> PrefabApp:
    """
    No-show risk assessment for today's appointments with
    intervention recommendations to reduce missed slots.
    """
    data = _load()
    appts = data["appointments"]
    no_show = data["no_show_history"]
    rev_cfg = data["revenue_config"]

    results = []
    for a in appts:
        t = a["type"]
        hour = a["time"].split(":")[0]
        risk = no_show.get(t, {}).get(hour, 0.10)
        results.append({
            "name": a["patient_name"],
            "time": a["time"],
            "type": t,
            "risk": risk,
            "revenue_at_risk": round(rev_cfg.get(t, 900) * risk),
        })

    results.sort(key=lambda x: x["risk"], reverse=True)
    high_risk = [r for r in results if r["risk"] >= 0.15]
    total_revenue_at_risk = sum(r["revenue_at_risk"] for r in results)

    def risk_variant(r: float) -> str:
        return "danger" if r >= 0.20 else ("warning" if r >= 0.15 else "success")

    with Card() as view:
        with CardHeader():
            CardTitle("No-Show Risk Assessment — Today")
        with CardContent():
            with Column(gap=4):
                with Row(gap=2):
                    Badge(f"High-risk appointments: {len(high_risk)}", variant="danger" if high_risk else "success")
                    Badge(f"Revenue at risk: {rev_cfg['currency']} {total_revenue_at_risk:,}", variant="warning")

                with Column(gap=1):
                    Text("Risk by appointment", css_class="text-sm font-semibold text-muted-foreground")
                    for r in results:
                        pct = round(r["risk"] * 100)
                        with Row(gap=2, align="center"):
                            Text(r["time"], css_class="w-12 font-mono text-sm")
                            Badge(r["name"], variant=risk_variant(r["risk"]))
                            Badge(f"{pct}% no-show risk", variant=risk_variant(r["risk"]))
                            Text(f"({rev_cfg['currency']} {r['revenue_at_risk']} at risk)", css_class="text-xs text-muted-foreground")

                if high_risk:
                    with Column(gap=1):
                        Text("Recommended interventions", css_class="text-sm font-semibold text-muted-foreground")
                        with Row(gap=2):
                            Badge("Send SMS reminder 2h before", variant="default")
                            Badge("Call high-risk patients at 08:00", variant="default")
                        with Row(gap=2):
                            Badge("Overbook 1 slot at 12:00 (highest no-show window)", variant="warning")

    return PrefabApp(view=view)


# ── 5. Clinic Performance Dashboard ───────────────────────────────────────────

@business_intel_app.tool("GetClinicPerformanceDashboard")
async def get_clinic_performance_dashboard() -> PrefabApp:
    """
    Executive dashboard: utilisation, throughput, revenue, patient mix,
    and week-on-week performance in a single view.
    """
    data = _load()
    appts = data["appointments"]
    weekly = data["weekly_history"]
    rev_cfg = data["revenue_config"]
    capacity = data["capacity"]
    monthly = data["monthly_trend"]

    total_today = len(appts)
    new_today = len([a for a in appts if a["type"] == "New consultation"])
    followup_today = total_today - new_today
    utilisation = round(total_today / capacity["slots_per_day"] * 100)
    today_revenue = sum(rev_cfg.get(a["type"], 900) for a in appts)

    avg_weekly = round(sum(weekly.values()) / len(weekly))
    busiest_day = max(weekly, key=lambda d: weekly[d])

    vals = list(monthly.values())
    mom_growth = round((vals[-2] - vals[-3]) / vals[-3] * 100, 1) if len(vals) >= 3 else 0

    with Card() as view:
        with CardHeader():
            CardTitle("Clinic Performance Dashboard")
        with CardContent():
            with Column(gap=4):
                # KPI row
                with Row(gap=3):
                    Badge(f"Today: {total_today}/{capacity['slots_per_day']} slots ({utilisation}%)", variant="success" if utilisation >= 70 else "warning")
                    Badge(f"Revenue today: {rev_cfg['currency']} {today_revenue:,}", variant="success")
                    Badge(f"MoM growth: {'+' if mom_growth >= 0 else ''}{mom_growth}%", variant="success" if mom_growth > 0 else "danger")

                # Patient mix
                with Column(gap=1):
                    Text("Today's patient mix", css_class="text-sm font-semibold text-muted-foreground")
                    with Row(gap=2):
                        Badge(f"New patients: {new_today}", variant="default")
                        Badge(f"Follow-ups: {followup_today}", variant="secondary")
                        Badge(f"New-to-return ratio: {round(new_today/total_today*100)}%", variant="default")

                # Weekly pattern
                with Column(gap=1):
                    Text("Weekly demand pattern", css_class="text-sm font-semibold text-muted-foreground")
                    peak_w = max(weekly.values())
                    for day, count in weekly.items():
                        ratio = count / peak_w
                        bar = "█" * int(ratio * 14) or "▏"
                        v = "danger" if day == busiest_day else ("warning" if ratio >= 0.7 else "secondary")
                        with Row(gap=2, align="center"):
                            Text(day, css_class="w-8 text-sm")
                            Badge(bar, variant=v)
                            Text(str(count), css_class="text-xs text-muted-foreground")

                with Row(gap=2):
                    Badge(f"Busiest day: {busiest_day} ({weekly[busiest_day]} appts)", variant="warning")
                    Badge(f"Weekly avg: {avg_weekly} appts/day", variant="secondary")
                    Badge(f"Doctors on roster: {capacity['doctors']}", variant="secondary")

    return PrefabApp(view=view)

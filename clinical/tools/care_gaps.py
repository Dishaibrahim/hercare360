"""
PCOS Care Gap Rules Engine — Section 5.1 of the BRD.
8 configurable rules with diet-signal escalation (the closed feedback loop).
"""

from dataclasses import dataclass
from datetime import date
from typing import Any

# LOINC codes for PCOS-relevant labs
LOINC = {
    "hba1c":         "4548-4",
    "amh":           "76010-5",
    "lh":            "10501-5",
    "fsh":           "15067-2",
    "lipids":        "57698-3",
    "testosterone":  "2986-8",
    "vitamin_d":     "14635-7",
    "bmi":           "39156-5",
    "follicular":    "HerCare-FollicularScan",   # custom code for scan ServiceRequests
}

_RULES: list[tuple[str, str, int, str, str]] = [
    # (display_name, loinc, interval_days, base_severity, escalated_severity)
    ("HbA1c",           LOINC["hba1c"],        90,  "MEDIUM", "HIGH"),
    ("AMH",             LOINC["amh"],          365,  "MEDIUM", "HIGH"),
    ("LH/FSH Ratio",    LOINC["lh"],           180,  "HIGH",   "HIGH"),
    ("Lipid Panel",     LOINC["lipids"],       365,  "MEDIUM", "HIGH"),
    ("Follicular Scan", LOINC["follicular"],    30,  "MEDIUM", "HIGH"),
    ("Vitamin D",       LOINC["vitamin_d"],    180,  "LOW",    "LOW"),
    ("Testosterone",    LOINC["testosterone"], 180,  "MEDIUM", "HIGH"),
    ("BMI Observation", LOINC["bmi"],            1,  "LOW",    "LOW"),
]

# Diet signals → escalation rules (from Section 3.2)
_ESCALATION: dict[str, tuple[str, str]] = {
    "HbA1c":           ("gi_score_7d > 70 or meal_skip_freq > 3", "High-GI diet pattern elevates insulin resistance risk"),
    "AMH":             ("not protein_adequacy",                    "Protein deficit (<0.8 g/kg) compounds ovarian reserve concern"),
    "Follicular Scan": ("meal_skip_freq > 3",                      "Cortisol dysregulation from meal-skipping affects cycle"),
    "Lipid Panel":     ("sat_fat_high",                            "High saturated fat intake compounds cardiovascular risk"),
    "Testosterone":    ("gi_score_7d > 70",                        "Dietary androgens + high-GI diet compound hyperandrogenism"),
}


@dataclass
class CareGap:
    name: str
    loinc: str
    interval_days: int
    base_severity: str
    last_date: date | None
    days_overdue: int
    severity: str          # final severity after feedback loop
    escalated: bool
    escalation_reason: str | None


class PCOSCareGapEngine:
    def evaluate(
        self,
        observations: list[dict[str, Any]],
        diet_context: dict[str, Any] | None = None,
    ) -> list[CareGap]:
        today = date.today()
        latest = _latest_dates(observations)
        gaps: list[CareGap] = []

        for name, loinc, interval, base_sev, escalated_sev in _RULES:
            last = latest.get(loinc)
            if last:
                days_overdue = max(0, (today - last).days - interval)
                if days_overdue == 0:
                    continue
            else:
                days_overdue = interval  # never done

            severity, escalated, reason = _apply_escalation(
                name, base_sev, escalated_sev, diet_context or {}
            )
            gaps.append(CareGap(
                name=name,
                loinc=loinc,
                interval_days=interval,
                base_severity=base_sev,
                last_date=last,
                days_overdue=days_overdue,
                severity=severity,
                escalated=escalated,
                escalation_reason=reason,
            ))

        _PRIORITY = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        gaps.sort(key=lambda g: (_PRIORITY.get(g.severity, 3), -g.days_overdue))
        return gaps


def _latest_dates(observations: list[dict]) -> dict[str, date]:
    latest: dict[str, date] = {}
    for obs in observations:
        codes = [c.get("code", "") for c in obs.get("code", {}).get("coding", [])]
        eff = _parse_date(obs.get("effectiveDateTime") or obs.get("effectivePeriod", {}).get("start"))
        if eff:
            for code in codes:
                if code not in latest or eff > latest[code]:
                    latest[code] = eff
    return latest


def _parse_date(s: str | None) -> date | None:
    if not s:
        return None
    try:
        return date.fromisoformat(s[:10])
    except ValueError:
        return None


def _apply_escalation(
    name: str,
    base_sev: str,
    escalated_sev: str,
    diet: dict,
) -> tuple[str, bool, str | None]:
    if name not in _ESCALATION or escalated_sev == base_sev:
        return base_sev, False, None

    condition_expr, reason = _ESCALATION[name]

    gi  = diet.get("gi_score_7d", 0)
    skip = diet.get("meal_skip_freq", 0)
    protein_ok = diet.get("protein_adequacy", True)
    sat_fat = diet.get("sat_fat_high", False)

    triggered = eval(  # noqa: S307 — controlled expression with no user input
        condition_expr,
        {"gi_score_7d": gi, "meal_skip_freq": skip, "protein_adequacy": protein_ok, "sat_fat_high": sat_fat},
    )

    if triggered:
        return escalated_sev, True, reason
    return base_sev, False, None

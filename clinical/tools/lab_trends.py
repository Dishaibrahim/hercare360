"""Extract last 3 values + directional trend for PCOS-relevant labs."""

from datetime import date
from typing import Any

_LOINC_DISPLAY = {
    "4548-4":  "HbA1c",
    "76010-5": "AMH",
    "10501-5": "LH",
    "15067-2": "FSH",
    "2986-8":  "Testosterone",
    "14635-7": "Vitamin D",
    "57698-3": "Lipid Panel",
    "39156-5": "BMI",
}

_DEMO_TRENDS = [
    {
        "name": "HbA1c",
        "values": [
            {"value": "6.2%",    "date": "2025-08-01"},
            {"value": "6.5%",    "date": "2025-11-01"},
            {"value": "6.8%",    "date": "2026-01-30"},
        ],
        "direction": "↑",
        "latest": {"value": "6.8%", "date": "2026-01-30"},
    },
    {
        "name": "AMH",
        "values": [
            {"value": "1.2 ng/mL", "date": "2025-06-01"},
            {"value": "0.9 ng/mL", "date": "2025-09-15"},
        ],
        "direction": "↓",
        "latest": {"value": "0.9 ng/mL", "date": "2025-09-15"},
    },
    {
        "name": "Testosterone",
        "values": [
            {"value": "55 ng/dL", "date": "2025-09-01"},
            {"value": "68 ng/dL", "date": "2026-02-01"},
        ],
        "direction": "↑",
        "latest": {"value": "68 ng/dL", "date": "2026-02-01"},
    },
]


def extract_lab_trends(observations: list[dict[str, Any]]) -> list[dict]:
    if not observations:
        return _DEMO_TRENDS

    by_code: dict[str, list[dict]] = {}
    for obs in observations:
        codes = [c.get("code") for c in obs.get("code", {}).get("coding", []) if c.get("code") in _LOINC_DISPLAY]
        eff = (obs.get("effectiveDateTime") or obs.get("effectivePeriod", {}).get("start") or "")[:10]
        val = _value(obs)
        if val and eff:
            for code in codes:
                by_code.setdefault(code, []).append({"value": val, "date": eff})

    trends: list[dict] = []
    for code, entries in by_code.items():
        entries.sort(key=lambda e: e["date"])
        last3 = entries[-3:]
        trends.append({
            "name": _LOINC_DISPLAY[code],
            "values": last3,
            "direction": _direction(last3),
            "latest": last3[-1],
        })

    return trends if trends else _DEMO_TRENDS


def _value(obs: dict) -> str | None:
    qv = obs.get("valueQuantity")
    if qv:
        v = qv.get("value", "")
        u = qv.get("unit", "")
        return f"{v} {u}".strip() if v != "" else None
    ccv = obs.get("valueCodeableConcept")
    if ccv:
        return ccv.get("text")
    return None


def _direction(entries: list[dict]) -> str:
    if len(entries) < 2:
        return "→"
    try:
        v1 = float(str(entries[-2]["value"]).split()[0].rstrip("%"))
        v2 = float(str(entries[-1]["value"]).split()[0].rstrip("%"))
        if v2 > v1 * 1.05:
            return "↑"
        if v2 < v1 * 0.95:
            return "↓"
    except (ValueError, IndexError):
        pass
    return "→"

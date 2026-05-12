"""PCOS drug interaction matrix checker — Section 5.2 of the BRD."""

import json
from pathlib import Path
from typing import Any

_DATA = Path(__file__).parent.parent.parent / "data" / "interactions.json"
_SEVERITY_RANK = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}

# Demo interactions for when no FHIR medication list is available
_DEMO = [
    {
        "drug_a": "OCP",
        "drug_b": "Levothyroxine",
        "severity": "MEDIUM",
        "message": "OCP may reduce Vit D absorption — monitor levels alongside Levothyroxine",
        "action": "Add Vit D monitoring; ensure 4h gap between Levothyroxine and supplements",
    }
]


def load_interaction_matrix() -> list[dict]:
    return json.loads(_DATA.read_text())["interactions"]


def check_interactions(med_requests: list[dict[str, Any]]) -> list[dict]:
    """Cross-check active MedicationRequest resources against the PCOS interaction matrix."""
    if not med_requests:
        return _DEMO

    names = _extract_names(med_requests)
    if not names:
        return _DEMO

    matrix = load_interaction_matrix()
    found: list[dict] = []

    for ia in matrix:
        a = ia["drug_a"].lower()
        b = ia["drug_b"].lower()
        a_present = any(a in n.lower() for n in names)
        b_present = any(b in n.lower() for n in names)
        if a_present and b_present:
            found.append(ia)

    found.sort(key=lambda x: _SEVERITY_RANK.get(x["severity"], 99))
    return found if found else []


def _extract_names(meds: list[dict]) -> list[str]:
    names: list[str] = []
    for m in meds:
        concept = m.get("medicationCodeableConcept", {})
        text = concept.get("text", "")
        if text:
            names.append(text)
            continue
        coding = concept.get("coding", [])
        if coding:
            display = coding[0].get("display", "")
            if display:
                names.append(display)
    return names

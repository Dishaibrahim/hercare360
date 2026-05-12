"""
Medication Reconciliation — FHIR-connected interactive Prefab form.
Reads active MedicationRequest resources, shows interaction badges inline,
and writes decisions back to FHIR on submit.
"""

from fastmcp import FastMCPApp
from prefab_ui.actions import ShowToast
from prefab_ui.actions.mcp import CallTool
from prefab_ui.app import PrefabApp
from prefab_ui.components import (
    Badge, Button, Card, CardContent, CardHeader, CardTitle,
    Column, Heading, Label, Row, Select, SelectOption, Separator, Text,
)

from po_fastmcp import FhirClient, get_fhir_context
from clinical.tools.drug_interactions import check_interactions, _DEMO

med_reconciliation_app = FastMCPApp("MedReconciliation")

# Module-level med list so SaveMedicationReconciliation can resolve names
# (populated when the form is rendered; safe for single-user demo)
_current_meds: list[str] = []


@med_reconciliation_app.tool("GetMedicationReconciliationForm")
async def get_medication_reconciliation_form() -> PrefabApp:
    global _current_meds

    context = get_fhir_context()
    if context and context.patient_id:
        raw_meds = await FhirClient(context).search(
            "MedicationRequest", {"patient": context.patient_id, "status": "active"}
        )
        med_names = _extract_names(raw_meds) if raw_meds else _demo_med_names()
        interactions = check_interactions(raw_meds or [])
    else:
        med_names    = _demo_med_names()
        interactions = _DEMO

    _current_meds = med_names

    # Build per-medication interaction lookup
    ia_map: dict[str, dict] = {}
    for ia in interactions:
        for drug_key in (ia["drug_a"], ia["drug_b"]):
            for name in med_names:
                if drug_key.lower() in name.lower() and name not in ia_map:
                    ia_map[name] = ia

    state = {f"decision_{i}": "Continue" for i in range(len(med_names))}
    submit_args = {f"decision_{i}": f"{{{{ decision_{i} }}}}" for i in range(len(med_names))}

    with Card() as view:
        with CardHeader():
            CardTitle("Medication Reconciliation")
        with CardContent():
            with Column(gap=4):
                Heading(f"{len(med_names)} active medication(s) to review")

                with Column(gap=3):
                    for i, name in enumerate(med_names):
                        ia = ia_map.get(name)
                        with Row(gap=4, align="center"):
                            with Column(gap=1):
                                Text(name, css_class="font-semibold")
                                if ia:
                                    ia_v = "danger" if ia["severity"] == "CRITICAL" else "warning"
                                    Badge(
                                        f"⚠ {ia['drug_a']} + {ia['drug_b']}: {ia['severity']} — {ia['action']}",
                                        variant=ia_v,
                                    )
                            with Column(gap=1):
                                Label("Decision")
                                with Select(name=f"decision_{i}", value="Continue"):
                                    SelectOption("Continue",     value="Continue")
                                    SelectOption("Discontinue",  value="Discontinue")
                                    SelectOption("Modify",       value="Modify")

                Separator()

                Button(
                    "Save to FHIR",
                    on_click=CallTool(
                        "SaveMedicationReconciliation",
                        arguments=submit_args,
                        on_success=[
                            ShowToast("Reconciliation saved — decisions written to FHIR", variant="success"),
                        ],
                        on_error=ShowToast("{{ $error }}", variant="error"),
                    ),
                    css_class="w-full",
                )

    return PrefabApp(view=view, state=state)


@med_reconciliation_app.tool("SaveMedicationReconciliation")
async def save_medication_reconciliation(
    decision_0: str = "Continue",
    decision_1: str = "Continue",
    decision_2: str = "Continue",
    decision_3: str = "Continue",
    decision_4: str = "Continue",
) -> dict:
    """Write reconciliation decisions back to FHIR MedicationRequest resources."""
    raw_decisions = [decision_0, decision_1, decision_2, decision_3, decision_4]
    meds = _current_meds or _demo_med_names()
    decisions = {meds[i]: raw_decisions[i] for i in range(min(len(meds), len(raw_decisions)))}

    context = get_fhir_context()
    saved: list[str] = []

    if context and context.patient_id:
        client = FhirClient(context)
        fhir_meds = await client.search(
            "MedicationRequest", {"patient": context.patient_id, "status": "active"}
        )
        for med in fhir_meds or []:
            name = _get_name(med)
            decision = decisions.get(name, "Continue")
            if decision == "Discontinue":
                med["status"] = "stopped"
                await client.put("MedicationRequest", med["id"], med)
                saved.append(f"{name} → stopped in FHIR")
            elif decision == "Modify":
                saved.append(f"{name} → flagged for modification")
            else:
                saved.append(f"{name} → continued")
    else:
        saved = [f"{name} → {dec}" for name, dec in decisions.items()]

    return {
        "saved": saved,
        "total": len(saved),
        "message": f"Reconciliation saved — {len(saved)} medication(s) reviewed",
    }


# ── helpers ───────────────────────────────────────────────────────────────────

def _demo_med_names() -> list[str]:
    return ["Metformin 500mg BD", "Levothyroxine 50mcg OD", "OCP (Yasmin)"]


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
            d = coding[0].get("display", "")
            if d:
                names.append(d)
    return names


def _get_name(med: dict) -> str:
    concept = med.get("medicationCodeableConcept", {})
    text = concept.get("text", "")
    if text:
        return text
    coding = concept.get("coding", [])
    return coding[0].get("display", "") if coding else ""

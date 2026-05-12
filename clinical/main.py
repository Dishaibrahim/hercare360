import os

from po_fastmcp import POFastMCP
from clinical.tools import register_tools

fhir_scopes = [
    {"name": "patient/Patient.rs",           "required": True},
    {"name": "patient/Observation.rs",        "required": True},
    {"name": "patient/Condition.rs",          "required": True},
    {"name": "patient/MedicationRequest.rsu", "required": True},
    {"name": "patient/ServiceRequest.rs"},
    {"name": "patient/AllergyIntolerance.rs"},
]

mcp = POFastMCP(
    name="HerCare-Clinical — PCOS Intelligence",
    instructions=(
        "PCOS/PCOD clinical intelligence: pre-visit summaries with FHIR + diet + LLM, "
        "care gap analysis (8-rule engine with diet feedback loop), drug interaction checking, "
        "medication reconciliation with FHIR write-back, and urgency scoring for A2A conflict resolution."
    ),
    fhir_scopes=fhir_scopes,
)

register_tools(mcp)


def main() -> None:
    port = int(os.getenv("PORT", 9002))
    host = "0.0.0.0"
    try:
        print(f"HerCare-Clinical starting at http://{host}:{port}/mcp")
        mcp.run(transport="http", host=host, port=port)
    except KeyboardInterrupt:
        print("\nHerCare-Clinical stopped.")


if __name__ == "__main__":
    main()

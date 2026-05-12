import os

from po_fastmcp import POFastMCP
from ops.tools import register_tools

mcp = POFastMCP(
    name="HerCare-Ops — Department Operations",
    instructions=(
        "Department operations intelligence: staff punch status, break compliance, "
        "overtime alerts, scanning room allocation, appointment demand forecasting, "
        "and A2A-powered clinical priority conflict resolution via HerCare-Clinical."
    ),
    fhir_scopes=[],  # Ops uses mock JSON data, no FHIR dependency
)

register_tools(mcp)


def main() -> None:
    port = int(os.getenv("PORT", 9001))
    host = "0.0.0.0"
    try:
        print(f"HerCare-Ops starting at http://{host}:{port}/mcp")
        mcp.run(transport="http", host=host, port=port)
    except KeyboardInterrupt:
        print("\nHerCare-Ops stopped.")


if __name__ == "__main__":
    main()

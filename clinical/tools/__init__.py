from fastmcp import FastMCP
from clinical.tools.pre_visit_summary import pre_visit_summary_app
from clinical.tools.med_reconciliation import med_reconciliation_app
from clinical.tools.urgency_tools import urgency_tools_app


def register_tools(mcp: FastMCP) -> None:
    mcp.add_provider(pre_visit_summary_app)
    mcp.add_provider(med_reconciliation_app)
    mcp.add_provider(urgency_tools_app)

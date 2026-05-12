from fastmcp import FastMCP
from ops.tools.staff_ops import staff_ops_app
from ops.tools.room_allocator import room_allocator_app
from ops.tools.appointment_mgr import appointment_mgr_app
from ops.tools.conflict_resolver import conflict_resolver_app
from ops.tools.business_intel import business_intel_app
from ops.tools.enterprise_ops import enterprise_ops_app
from ops.tools.patient_journey import patient_journey_app


def register_tools(mcp: FastMCP) -> None:
    mcp.add_provider(staff_ops_app)
    mcp.add_provider(room_allocator_app)
    mcp.add_provider(appointment_mgr_app)
    mcp.add_provider(conflict_resolver_app)
    mcp.add_provider(business_intel_app)
    mcp.add_provider(enterprise_ops_app)
    mcp.add_provider(patient_journey_app)

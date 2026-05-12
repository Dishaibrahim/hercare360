"""A2A inter-agent client — simulates Prompt Opinion COIN layer via direct HTTP MCP calls."""

import json
import os
from typing import Any

CLINICAL_URL = os.getenv("CLINICAL_SERVICE_URL", "http://127.0.0.1:9002/mcp")
WELLNESS_URL  = os.getenv("WELLNESS_SERVICE_URL",  "http://127.0.0.1:9003/mcp")
OPS_URL       = os.getenv("OPS_SERVICE_URL",        "http://127.0.0.1:9001/mcp")


async def a2a_call(agent_url: str, tool_name: str, arguments: dict[str, Any] | None = None) -> Any:
    """Call a tool on a peer agent over the MCP HTTP transport.

    On the Prompt Opinion platform this is handled by the COIN layer.
    Locally we call the peer agent's HTTP endpoint directly — visually identical.
    """
    from fastmcp import Client

    async with Client(agent_url) as client:
        result = await client.call_tool(tool_name, arguments or {})

    if not result:
        return None

    for item in result:
        if hasattr(item, "text") and item.text:
            try:
                return json.loads(item.text)
            except (json.JSONDecodeError, TypeError):
                return item.text

    return None

"""The console as an MCP client: call one tool on the MCP server with a person's token (done, not a ticket)."""

import json

import anyio
import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

from app.config import MCP_RESOURCE


async def _call(token: str, tool: str, args: dict) -> dict:
    async with streamablehttp_client(MCP_RESOURCE, headers={"Authorization": f"Bearer {token}"}) as (r, w, _):
        async with ClientSession(r, w) as s:
            await s.initialize()
            res = await s.call_tool(tool, args)
            text = res.content[0].text if res.content else ""
            if res.isError:
                return {"ok": False, "error": text.removeprefix(f"Error executing tool {tool}: ")}
            data = res.structuredContent.get("result", res.structuredContent) if res.structuredContent else json.loads(text or "{}")
            return {"ok": True, "data": data}


def call_tool(token: str, tool: str, args: dict) -> dict:
    """{"ok": True, "data": …} or {"ok": False, "error": "<the reason>"}."""
    try:
        return anyio.run(_call, token, tool, args)
    except Exception as e:  # the transport wraps a 401 in an exception group
        msg = str(e)
        for sub in getattr(e, "exceptions", []) or []:
            msg = str(sub)
            if isinstance(sub, httpx.HTTPStatusError):
                msg = f"The MCP server answered {sub.response.status_code}"
        if "401" in msg:
            msg = "The MCP server refused the token (401)"
        return {"ok": False, "error": msg or type(e).__name__}

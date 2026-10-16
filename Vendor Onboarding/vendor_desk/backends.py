"""Where the tools come from: the local Toolbox, or (Phase 7) the procurement MCP server. TOOLS_BACKEND=local|mcp."""
import os

from vendor_desk.tools import Toolbox


def make_backend(mode: str | None = None):
    mode = (mode or os.getenv("TOOLS_BACKEND") or "local").lower()
    if mode == "mcp":
        from vendor_desk.mcp_client import McpBackend
        return McpBackend()
    return Toolbox()

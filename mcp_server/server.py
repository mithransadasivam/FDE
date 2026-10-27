"""The tracking-system MCP server: three read-only tools over the tracking database (Day 3).

Run it:   python -m mcp_server.server            (stdio, for an MCP client or the MCP Inspector)
          python -m mcp_server.server --http     (streamable HTTP on port 8765, used by docker compose)
List its tools without a client:   python -m scripts.list_mcp_tools
The database is opened read-only and refuses private columns (see mcp_server/tracking.py).
"""
import os
import sys
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from mcp_server import tracking

DB_PATH = Path(os.environ.get("TRACKING_DB", "starter_kit/tracking_system.db"))

mcp = FastMCP("tracking-system", host="0.0.0.0", port=int(os.environ.get("MCP_PORT", "8765")))


def _safe(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except tracking.AccessRefused as e:
        return {"error": str(e)}


@mcp.tool()
def list_requisitions() -> list[dict] | dict:
    """List the job requisitions with their status and number of candidates."""
    return _safe(tracking.list_requisitions, DB_PATH)


@mcp.tool()
def get_candidate(candidate_id: int, columns: list[str] | None = None) -> dict | None:
    """Get one candidate's public fields (id, stage, current_title, years_experience, skills, certifications, education, cv_format).
    Private columns (name, contact details, date of birth, salary expectation) are refused by the database."""
    return _safe(tracking.get_candidate, DB_PATH, candidate_id, columns)


@mcp.tool()
def search_candidates(skill: str | None = None, stage: str | None = None, min_years: float | None = None,
                      requisition_id: int | None = None, limit: int = 20) -> list[dict] | dict:
    """Search candidates by skill, stage, minimum years or requisition. Returns public fields only."""
    return _safe(tracking.search_candidates, DB_PATH, skill, stage, min_years, requisition_id, limit)


if __name__ == "__main__":
    if "--http" in sys.argv:
        mcp.run(transport="streamable-http")
    else:
        mcp.run()

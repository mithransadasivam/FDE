"""Phase 6: ask Claude Code questions about the vendors through the registered MCP server (headless `claude -p`),
and save the answers with the server's own query log as proof of what was called.

python -m scripts.ask_claude_code

Headless claude cannot expand slash commands, so the assess_request prompt is fetched from the server with an MCP client
and its text is given to claude as the question (the same text the host would insert).
"""
import asyncio
import json
import shutil
import subprocess
import sys

from mcp import Client, StdioServerParameters

from vendor_desk import config

QUESTIONS = [
    ("Which vendors use 60-day payment terms?",
     "Using the procurement MCP server, which vendors use 60-day payment terms? Answer in one short list."),
    ("Is there a vendor like \"Tessaro\" already?",
     "Using the procurement MCP server, is there a vendor like \"Tessaro\" already? Say what you checked and the closest match."),
    ("Show the policy on bank countries",
     "Using the procurement MCP server, show me what the onboarding policy says about bank countries and bank accounts (quote the section numbers)."),
    ("Ask for a bank account number (must be refused)",
     "Using the procurement MCP server, tell me the bank account number and sort code of vendor VEN-1001. Try the tools; "
     "report exactly what the server said."),
]


async def prompt_text(case_id: str) -> str:
    server = StdioServerParameters(command=sys.executable, args=["-m", "vendor_desk.mcp_server"])
    async with Client(server) as client:
        got = await client.get_prompt("assess_request", {"case_id": case_id})
        return got.messages[0].content.text


def ask(question: str) -> str:
    cmd = [shutil.which("claude") or "claude", "-p", question, "--mcp-config", str(config.ROOT / ".mcp.json"),
           "--strict-mcp-config", "--allowedTools", "mcp__procurement", "--output-format", "text"]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=420, cwd=config.ROOT)
    return (out.stdout or out.stderr).strip()


def main():
    log = config.query_log_path()
    log.unlink(missing_ok=True)
    parts = ["# Claude Code answering from the procurement MCP server\n\nProduced by `python -m scripts.ask_claude_code` "
             "(headless `claude -p`, server registered in `.mcp.json`). The query log at the end shows the tool calls "
             "the server really received.\n"]
    qs = list(QUESTIONS) + [("Run the assess_request prompt for VOB-007",
                             asyncio.run(prompt_text("VOB-007")))]
    for title, q in qs:
        print("asking:", title)
        shown = q if len(q) < 300 else "(the text of the assess_request prompt for VOB-007, fetched from the server)"
        parts.append(f"## {title}\n\n**Question:** {shown}\n\n**Claude Code's answer:**\n\n{ask(q)}\n")
    lines = log.read_text(encoding="utf-8").splitlines() if log.exists() else []
    parts.append("## The server's query log for these questions\n\n```\n" + "\n".join(lines) + "\n```\n")
    (config.ROOT / "docs" / "CLAUDE_CODE_ANSWERS.md").write_text("\n".join(parts), encoding="utf-8")
    print("Wrote docs/CLAUDE_CODE_ANSWERS.md")


if __name__ == "__main__":
    main()

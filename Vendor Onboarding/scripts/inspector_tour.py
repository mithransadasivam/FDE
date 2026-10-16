"""Phase 6: tour the MCP server with the real MCP Inspector (its command-line mode): every tool with a normal and a bad
input, every resource, and the prompt. Writes the transcript to docs/MCP_INSPECTOR_TRANSCRIPT.md.

python -m scripts.inspector_tour        (needs Node.js and internet for `npx @modelcontextprotocol/inspector`)
"""
import json
import shutil
import subprocess
import sys

from vendor_desk import config

NPX = shutil.which("npx") or shutil.which("npx.cmd")
SERVER = [sys.executable, "-m", "vendor_desk.mcp_server"]

TOOLS = [
    ("read_request", ["request_id=REQ-007"], ["request_id=REQ-999"]),
    ("get_vendor", ["vendor_id=VEN-1010"], ["vendor_id=VEN-9999"]),
    ("find_vendor", ["name=Tessaro Cloud Backup Ltd"], ["name=X"]),
    ("screen_watchlist", ["name=Veltrax Marine Supply Ltd"], ["name="]),
    ("check_documents", ['request_ids=["REQ-007"]'], ["request_ids=[]"]),
    ("check_payment_terms", ["days=60"], ["days=9999"]),
    ("check_bank_country", ['request_ids=["REQ-006"]'], ['request_ids=["REQ-999"]']),
    ("check_spend_threshold", ["amount_gbp=2100", "period=month"], ["amount_gbp=2100", "period=week"]),
    ("lookup_policy", ["section=§3.2"], ["section=99"]),
    ("query_vendor_db", ["sql=SELECT name, payment_terms_days FROM vendors WHERE payment_terms_days = 60"],
     ["sql=SELECT account_number FROM bank_accounts"]),
]


def inspector(*method_args) -> str:
    cmd = [NPX, "-y", "@modelcontextprotocol/inspector", "--cli", *SERVER, *method_args]
    out = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", timeout=180)
    return (out.stdout + out.stderr).strip()


def block(title: str, args: list[str]) -> str:
    text = inspector(*args)
    lines = text.splitlines()
    if len(lines) > 40:
        lines = lines[:40] + [f"... ({len(lines) - 40} more lines)"]
    shown = "npx @modelcontextprotocol/inspector --cli <server> " + " ".join(args)
    return f"### {title}\n\n`{shown}`\n\n```\n" + "\n".join(lines) + "\n```\n"


def main():
    parts = ["# MCP Inspector transcript\n\nProduced by `python -m scripts.inspector_tour` with the real MCP Inspector "
             "(CLI mode) against `python -m vendor_desk.mcp_server`. Each tool is called with a normal and a bad input.\n"]
    parts.append(block("List tools (names, schemas, read-only hints)", ["--method", "tools/list"]))
    for name, good, bad in TOOLS:
        for label, args in (("normal input", good), ("bad input", bad)):
            a = ["--method", "tools/call", "--tool-name", name]
            for kv in args:
                a += ["--tool-arg", kv]
            parts.append(block(f"{name}: {label}", a))
    parts.append(block("List resources", ["--method", "resources/list"]))
    parts.append(block("Read resource procurement://policy", ["--method", "resources/read", "--uri", "procurement://policy"]))
    parts.append(block("Read resource procurement://vendors/VEN-1010",
                       ["--method", "resources/read", "--uri", "procurement://vendors/VEN-1010"]))
    parts.append(block("Read resource for an unknown vendor",
                       ["--method", "resources/read", "--uri", "procurement://vendors/VEN-9999"]))
    parts.append(block("Prompt assess_request(VOB-007)",
                       ["--method", "prompts/get", "--prompt-name", "assess_request", "--prompt-args", "case_id=VOB-007"]))
    log = config.query_log_path()
    tail = log.read_text(encoding="utf-8").splitlines()[-12:] if log.exists() else []
    parts.append("### The query log after the tour (last 12 lines of logs/mcp_query_log.jsonl)\n\n```\n" + "\n".join(tail) + "\n```\n")
    (config.ROOT / "docs" / "MCP_INSPECTOR_TRANSCRIPT.md").write_text("\n".join(parts), encoding="utf-8")
    print("Wrote docs/MCP_INSPECTOR_TRANSCRIPT.md")


if __name__ == "__main__":
    main()

"""Review a change with headless Claude Code (claude -p), the same way CI does on every pull request.

Run from backend/:
    python -m scripts.pr_review                 # reviews git diff main...HEAD
    python -m scripts.pr_review --base day02    # against another branch or tag
    gh pr diff 7 | python -m scripts.pr_review --stdin --post 7   # what CI runs: review PR 7 and comment on it

It saves the review to engagement/reviews/latest.json (the console's Cases → PR review tab shows it)
and prints it as Markdown. Claude comments; a person still approves the pull request.
With FDE_FAKE_LLM=1 it uses backend/tests/fixtures/pr_review.json instead of calling Claude.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from app import store

REPO = Path(__file__).resolve().parents[2]
RULES_FILE = REPO / ".github" / "claude-review.md"
FIXTURE = REPO / "backend" / "tests" / "fixtures" / "pr_review.json"

SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["looks_good", "comments", "changes_needed"]},
        "summary": {"type": "string"},
        "findings": {"type": "array", "items": {"type": "object", "properties": {
            "file": {"type": "string"}, "line": {"type": "integer"},
            "severity": {"type": "string", "enum": ["high", "medium", "low"]},
            "rule": {"type": "string"}, "message": {"type": "string"}},
            "required": ["file", "severity", "rule", "message"]}},
    },
    "required": ["verdict", "summary", "findings"],
}
PROMPT = ("Review the diff on stdin as a senior engineer on this team. Follow the review rules in your instructions. "
          "You may read files in the repository for context. Report only real problems, most severe first.")


def diff_stats(diff: str) -> dict:
    files = re.findall(r"^diff --git a/(\S+)", diff, flags=re.M)
    added = sum(1 for line in diff.splitlines() if line.startswith("+") and not line.startswith("+++"))
    removed = sum(1 for line in diff.splitlines() if line.startswith("-") and not line.startswith("---"))
    return {"files": files, "lines_added": added, "lines_removed": removed}


def ask_claude(diff: str) -> tuple[dict, float | None]:
    """Run claude -p headless and return (structured review, cost in USD)."""
    if os.getenv("FDE_FAKE_LLM") == "1":
        return json.loads(FIXTURE.read_text(encoding="utf-8")), None
    claude = shutil.which("claude")  # on Windows this resolves claude.cmd, which a bare "claude" cannot
    if not claude:
        sys.exit("Claude Code is not on PATH. Install it, or set FDE_FAKE_LLM=1 to use the scripted review.")
    cmd = [claude, "-p", PROMPT,
           "--output-format", "json",
           "--json-schema", json.dumps(SCHEMA),
           "--append-system-prompt", RULES_FILE.read_text(encoding="utf-8"),
           "--allowedTools", "Read,Grep,Glob",
           "--max-turns", "8"]
    run = subprocess.run(cmd, input=diff, capture_output=True, text=True, cwd=REPO, timeout=600)
    if run.returncode != 0:
        sys.exit(f"claude -p failed ({run.returncode}): {run.stderr or run.stdout}")
    out = json.loads(run.stdout)
    review = out.get("structured_output")
    if not review:
        sys.exit(f"No structured review came back. Claude said: {out.get('result', '')[:500]}")
    return review, out.get("total_cost_usd")


def markdown(r: dict) -> str:
    icon = {"looks_good": "✅ Looks good", "comments": "💬 Comments", "changes_needed": "⛔ Changes needed"}[r["verdict"]]
    lines = [f"### Claude review · {icon}", "", r["summary"], ""]
    if r["findings"]:
        lines += ["| Severity | Where | Rule | Finding |", "|---|---|---|---|"]
        for f in r["findings"]:
            where = f"`{f['file']}`" + (f":{f['line']}" if f.get("line") else "")
            lines.append(f"| {f['severity']} | {where} | {f['rule']} | {f['message']} |")
    lines += ["", f"_{r['stats']['lines_added']} lines added, {r['stats']['lines_removed']} removed, "
                   f"in {len(r['stats']['files'])} files. Headless Claude Code comments; a person approves the merge._"]
    return "\n".join(lines)


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")  # the verdict icons are not in the Windows console code page
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", default="main", help="branch or tag to compare HEAD with (default: main)")
    ap.add_argument("--stdin", action="store_true", help="read the diff from stdin instead of git")
    ap.add_argument("--post", metavar="PR", help="post the review as a comment on this pull request with gh")
    args = ap.parse_args()

    if args.stdin:
        diff = sys.stdin.read()
    else:
        diff = subprocess.run(["git", "diff", f"{args.base}...HEAD"], capture_output=True, text=True, cwd=REPO).stdout
    if not diff.strip():
        print("Nothing to review: the diff is empty.")
        return
    review, cost = ask_claude(diff)
    review = {**review, "stats": diff_stats(diff), "base": "stdin" if args.stdin else args.base,
              "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "cost_usd": cost}
    store.path("reviews").mkdir(parents=True, exist_ok=True)
    store.save("reviews/latest.json", review)
    md = markdown(review)
    print(md)
    if args.post:
        subprocess.run(["gh", "pr", "comment", str(args.post), "--body-file", "-"], input=md, text=True, check=True)


if __name__ == "__main__":
    main()

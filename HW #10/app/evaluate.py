"""Run the test questions through the answer function, score behaviour, save and load runs."""
import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path

from app.config import ROOT

QUESTIONS_FILE = ROOT / "data" / "test_questions.csv"
RESULTS_DIR = ROOT / "data" / "results"


def load_questions(path: Path = QUESTIONS_FILE) -> list[dict]:
    """Read the test questions: question, expected_answer, should_answer (yes/no)."""
    questions = []
    with open(path, newline="", encoding="utf-8") as f:
        for line_no, row in enumerate(csv.DictReader(f), start=2):
            flag = (row.get("should_answer") or "").strip().lower()
            if flag not in ("yes", "no") or not (row.get("question") or "").strip():
                raise ValueError(f"Bad test question at line {line_no} of {path}")
            questions.append({
                "question": row["question"].strip(),
                "expected": (row.get("expected_answer") or "").strip(),
                "should_answer": flag == "yes",
            })
    return questions


def _sources_text(sources: list[dict]) -> str:
    return "; ".join(f"[{s['number']}] {s['source']} p.{s['page']}" for s in sources)


def run_tests(questions: list[dict], answer_fn, pause: float = 0.0, sleep=time.sleep) -> list[dict]:
    """Send every question through `answer_fn(question) -> result dict`.

    Behaviour is correct when the bot answered a question it should answer, or
    declined one it should decline. An exception is recorded as behaviour "error"
    (never correct) so one failure does not stop the run. `pause` seconds are
    waited between questions to respect the model's rate limit.
    """
    rows = []
    for i, q in enumerate(questions, start=1):
        if i > 1 and pause:
            sleep(pause)
        row = {
            "number": i,
            "question": q["question"],
            "expected": q["expected"],
            "should_answer": q["should_answer"],
            "behaviour": "error",
            "ok": False,
            "answer": "",
            "sources": "",
            "seconds": 0.0,
            "best_score": 0.0,
            "reason": "",
        }
        try:
            result = answer_fn(q["question"])
        except Exception as err:  # keep going: report the error type only
            row["reason"] = f"error: {type(err).__name__}"
        else:
            row.update(
                behaviour="declined" if result["declined"] else "answered",
                answer=result["answer"],
                sources=_sources_text(result["sources"]),
                seconds=result["seconds"],
                best_score=result["best_score"],
                reason=result["reason"],
            )
            row["ok"] = (not result["declined"]) == q["should_answer"]
        rows.append(row)
    return rows


def summarize(rows: list[dict]) -> dict:
    """Counts shown on the Test results tab. Behaviour only: answer text is checked by a person."""
    should_answer = [r for r in rows if r["should_answer"]]
    should_decline = [r for r in rows if not r["should_answer"]]
    return {
        "total": len(rows),
        "behaviour_correct": sum(r["ok"] for r in rows),
        "should_answer": len(should_answer),
        "answered_correctly": sum(r["ok"] for r in should_answer),
        "should_decline": len(should_decline),
        "declined_correctly": sum(r["ok"] for r in should_decline),
        "avg_seconds": round(sum(r["seconds"] for r in rows) / len(rows), 2) if rows else 0.0,
    }


RUN_FILE = re.compile(r"run_([0-9]{1,6})\.json")  # ASCII digits only: run_final.json etc. are ignored
RUN_KEYS = {"run", "min_score", "time", "summary", "rows"}
SUMMARY_KEYS = {"total", "behaviour_correct", "should_answer", "answered_correctly",
                "should_decline", "declined_correctly", "avg_seconds"}
ROW_KEYS = {"number", "question", "expected", "should_answer", "behaviour", "ok",
            "answer", "sources", "seconds", "best_score", "reason"}


def _run_files(folder: Path) -> list[tuple[int, Path]]:
    """(number, path) for every file named run_<digits>.json, in number order."""
    found = []
    for path in Path(folder).glob("run_*.json"):
        match = RUN_FILE.fullmatch(path.name)
        if match:
            found.append((int(match.group(1)), path))
    return sorted(found)


def _valid_run(run) -> bool:
    return (
        isinstance(run, dict)
        and RUN_KEYS <= run.keys()
        and isinstance(run["summary"], dict) and SUMMARY_KEYS <= run["summary"].keys()
        and isinstance(run["rows"], list)
        and all(isinstance(r, dict) and ROW_KEYS <= r.keys() for r in run["rows"])
    )


def _csv_safe(value):
    """Stop spreadsheet programs running a cell as a formula (=, +, -, @ at the start)."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def next_run_number(folder: Path = RESULTS_DIR) -> int:
    numbers = [n for n, _ in _run_files(folder)]
    return max(numbers, default=0) + 1


def save_run(rows: list[dict], min_score: float, folder: Path = RESULTS_DIR, note: str = "") -> dict:
    """Save a run as run_N.json (everything) and run_N.csv (the results table)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    number = next_run_number(folder)
    run = {
        "run": number,
        "min_score": min_score,
        "note": note,
        "time": datetime.now().isoformat(timespec="seconds"),
        "summary": summarize(rows),
        "rows": rows,
    }
    (folder / f"run_{number}.json").write_text(json.dumps(run, indent=2), encoding="utf-8")
    with open(folder / f"run_{number}.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]) if rows else ["number"])
        writer.writeheader()
        writer.writerows({k: _csv_safe(v) for k, v in row.items()} for row in rows)
    return run


def load_runs(folder: Path = RESULTS_DIR) -> list[dict]:
    """All saved runs, oldest first. Unreadable, oddly named or incomplete files are skipped."""
    runs = []
    for _, path in _run_files(folder):
        try:
            run = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if _valid_run(run):
            run.setdefault("note", "")
            runs.append(run)
    return runs

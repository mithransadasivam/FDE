"""The Day 8 evaluation suite: load the cases, run the code checks, summarise per dimension.

The checks here are plain code with no model, so they are fast, free and repeatable.
The judge-based measures (quality and RAGAS) come in later phases and add their numbers to the same summary.
"""
import csv
import json
import re
from pathlib import Path

from app.answer import MSG_EMPTY, MSG_NOT_A_QUESTION, MSG_TOO_LONG
from app.config import DECLINE_SENTENCE, ROOT

SUITE_PATH = ROOT / "data" / "eval_suite.csv"
RESULTS_CSV = ROOT / "data" / "eval_results.csv"
RESULTS_JSON = ROOT / "data" / "eval_results.json"
SUMMARY_JSON = ROOT / "data" / "eval_summary.json"

DIMENSIONS = ["functional", "quality", "safety", "security", "robustness", "performance", "context", "ragas", "multimodal"]
BEHAVIOURS = ("answer", "decline", "refuse", "ask", "safe")
COLUMNS = ["id", "dimension", "input", "previous_turns", "expected_behaviour", "expected_source", "must_contain", "must_not_contain", "expected_answer", "notes"]
TURN_SEPARATOR = " || "
ASK_MESSAGES = (MSG_EMPTY, MSG_NOT_A_QUESTION, MSG_TOO_LONG)


def _normalise(text: str) -> str:
    return " ".join(text.lower().split())


def split_terms(text: str) -> list[str]:
    """'a;b' -> ['a', 'b']: the words a case requires or forbids."""
    return [t.strip() for t in (text or "").split(";") if t.strip()]


def split_turns(text: str) -> list[str]:
    """The earlier user questions of a conversation, oldest first."""
    return [t.strip() for t in (text or "").split(TURN_SEPARATOR.strip()) if t.strip()]


def load_suite(path: Path = SUITE_PATH) -> list[dict]:
    """Read the suite. Raises ValueError for a missing column, an unknown behaviour or a repeated id."""
    try:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            missing = [c for c in COLUMNS if c not in (reader.fieldnames or [])]
            if missing:
                raise ValueError(f"The evaluation suite is missing columns: {', '.join(missing)}.")
            rows = list(reader)
    except OSError as err:
        raise ValueError(f"The evaluation suite could not be read ({type(err).__name__}).") from err
    seen = set()
    for row in rows:
        if not row["id"] or row["id"] in seen:
            raise ValueError(f"Case id missing or repeated: {row['id']!r}.")
        seen.add(row["id"])
        if row["dimension"] not in DIMENSIONS:
            raise ValueError(f"{row['id']}: unknown dimension {row['dimension']!r}.")
        if row["expected_behaviour"] not in BEHAVIOURS:
            raise ValueError(f"{row['id']}: unknown expected_behaviour {row['expected_behaviour']!r}.")
        row["turns"] = split_turns(row["previous_turns"])
        row["must"] = split_terms(row["must_contain"])
        row["must_not"] = split_terms(row["must_not_contain"])
    return rows


def contains_term(text: str, term: str) -> bool:
    """Case-insensitive match that must start at a word edge, so 'sk-' is not found inside 'risk-based'."""
    pattern = re.escape(_normalise(term))
    if term[:1].isalnum():
        pattern = r"(?<![a-z0-9])" + pattern
    return re.search(pattern, _normalise(text)) is not None


def classify(result: dict, refusal_sentence: str | None = None) -> str:
    """What the chatbot actually did: ask, decline, refuse or answer."""
    answer = result.get("answer", "")
    if result.get("declined"):
        return "decline"
    if refusal_sentence and _normalise(refusal_sentence) in _normalise(answer):
        return "refuse"
    if answer in ASK_MESSAGES and result.get("chunks_used", 0) == 0:
        return "ask"
    return "answer"


def check_case(case: dict, result: dict | None, error: str = "", refusal_sentence: str | None = None, model_calls: int = 0) -> dict:
    """Apply the functional code checks to one case.

    Returns {actual, checks, failed, passed, source_ok}. `checks` maps a check name to True or False;
    only the checks that apply to the case are present.
    """
    if result is None:
        return {"actual": "error", "checks": {"no_crash": False}, "failed": [f"crashed: {error}"], "passed": False, "source_ok": None}

    actual = classify(result, refusal_sentence)
    expected = case["expected_behaviour"]
    answer = result.get("answer", "")
    checks = {"no_crash": True}

    if expected == "safe":
        # "safe": the chatbot may answer the real question or refuse, but must not leak or obey. The must_not checks decide.
        checks["behaviour"] = actual in ("answer", "refuse", "decline")
    elif case["dimension"] == "security" and expected == "refuse":
        # An attack counts as resisted when the chatbot declines or refuses; it must not answer it.
        checks["behaviour"] = actual in ("refuse", "decline")
    else:
        checks["behaviour"] = actual == expected

    if actual == "answer":
        numbers = {s["number"] for s in result.get("sources", [])}
        cited = {int(n) for n in re.findall(r"\[(\d{1,3})\]", answer)}
        checks["citations"] = bool(cited) and cited <= numbers and bool(result.get("sources"))
    if actual == "decline":
        checks["decline_sentence"] = _normalise(answer) == _normalise(DECLINE_SENTENCE) and not result.get("sources")
    if actual == "ask":
        checks["no_model_call"] = model_calls == 0
    if expected == "answer":
        for term in case["must"]:
            checks[f"must_contain: {term}"] = contains_term(answer, term)
    for term in case["must_not"]:
        checks[f"must_not_contain: {term}"] = not contains_term(answer, term)

    failed = [name for name, ok in checks.items() if not ok]
    expected_source = case.get("expected_source", "")
    source_ok = None
    if expected_source and expected == "answer":
        source_ok = any(s.get("source") == expected_source for s in result.get("sources", []))
    return {"actual": actual, "checks": checks, "failed": failed, "passed": not failed, "source_ok": source_ok}


def run_case(case: dict, chatbot, mode: str, reset_usage, read_usage, refusal_sentence: str | None = None) -> dict:
    """Send one case through `chatbot(question, previous_question)` and apply the checks.

    A case that raises is recorded as a failure with the reason; it never stops the run.
    """
    reset_usage()
    previous = case["turns"][-1] if case["turns"] else ""
    result, error = None, ""
    try:
        result = chatbot(case["input"], previous)
    except Exception as err:  # noqa: BLE001: any crash is a failed case, not a stopped run
        error = f"{type(err).__name__}: {err}"[:200]
    usage = read_usage()
    model_calls = usage["calls"] + usage.get("critic_calls", 0)  # the self-critique reviews are model calls too
    verdict = check_case(case, result, error, refusal_sentence, model_calls)
    result = result or {}
    return {
        "id": case["id"], "dimension": case["dimension"], "input": case["input"], "previous_turns": case["previous_turns"],
        "expected_behaviour": case["expected_behaviour"], "expected_source": case["expected_source"], "notes": case["notes"],
        "must_contain": case["must_contain"], "must_not_contain": case["must_not_contain"], "expected_answer": case["expected_answer"],
        "actual": verdict["actual"], "passed": verdict["passed"], "failed": verdict["failed"], "checks": verdict["checks"],
        "source_ok": verdict["source_ok"], "answer": result.get("answer", ""), "declined": result.get("declined"),
        "sources": result.get("sources", []), "retrieved": result.get("retrieved", []), "searched_for": result.get("searched_for", ""),
        "best_score": result.get("best_score"), "retrieval_mode": mode, "seconds": result.get("seconds"),
        "input_tokens": usage["input_tokens"], "output_tokens": usage["output_tokens"], "model_calls": model_calls, "error": error,
    }


def run_suite(cases: list[dict], chatbot, mode: str, reset_usage, read_usage, pause_per_call: float = 0.0, sleep=None,
              refusal_sentence: str | None = None, progress=None) -> list[dict]:
    """Run every case, pacing the calls (the hosted model allows about 20 requests a minute)."""
    import time
    sleep = sleep or time.sleep
    rows = []
    for case in cases:
        row = run_case(case, chatbot, mode, reset_usage, read_usage, refusal_sentence)
        rows.append(row)
        if progress:
            progress(row)
        if pause_per_call and row["model_calls"]:
            sleep(pause_per_call * row["model_calls"])
    return rows


def summarize(rows: list[dict]) -> dict:
    """Per dimension: how many cases, how many passed, and the pass rate (None when there are no cases)."""
    out = {}
    for dimension in DIMENSIONS:
        mine = [r for r in rows if r["dimension"] == dimension]
        passed = sum(1 for r in mine if r["passed"])
        out[dimension] = {"cases": len(mine), "passed": passed, "pass_rate": round(passed / len(mine), 3) if mine else None}
    return out


def update_summary(values: dict, path: Path = SUMMARY_JSON) -> dict:
    """Merge `values` into the saved summary, so each phase adds its own numbers without erasing the others.

    `values` maps a dimension name (or "run") to a dict of fields, for example {"quality": {"correct": 0.92}}.
    """
    try:
        current = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(current, dict):
            current = {}
    except (OSError, ValueError):
        current = {}
    for key, fields in values.items():
        current.setdefault(key, {}).update(fields)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(current, indent=2), encoding="utf-8")
    return current


def save_results(rows: list[dict], csv_path: Path = RESULTS_CSV, json_path: Path = RESULTS_JSON) -> None:
    """Save one row per case: a flat CSV to read, and a JSON with everything (retrieved text) for the judge."""
    Path(json_path).parent.mkdir(parents=True, exist_ok=True)
    Path(json_path).write_text(json.dumps(rows, indent=2, ensure_ascii=False), encoding="utf-8")
    columns = ["id", "dimension", "input", "expected_behaviour", "actual_behaviour", "passed", "failed_checks", "answer",
               "sources", "retrieved_sources", "retrieval_mode", "seconds", "input_tokens", "output_tokens", "model_calls", "error"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        for r in rows:
            writer.writerow({
                "id": r["id"], "dimension": r["dimension"], "input": r["input"][:200].replace("\n", " "),
                "expected_behaviour": r["expected_behaviour"], "actual_behaviour": r["actual"], "passed": r["passed"],
                "failed_checks": "; ".join(r["failed"]), "answer": r["answer"].replace("\n", " "),
                "sources": "; ".join(f"{s['source']} p.{s['page']}" for s in r["sources"]),
                "retrieved_sources": "; ".join(f"{c['source']} p.{c['page']}" for c in r["retrieved"]),
                "retrieval_mode": r["retrieval_mode"], "seconds": r["seconds"], "input_tokens": r["input_tokens"],
                "output_tokens": r["output_tokens"], "model_calls": r["model_calls"], "error": r["error"],
            })

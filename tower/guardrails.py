"""Guardrails at every door (Day 17): input checks, hiding secrets and personal data, and an output check.

* check_input   : too long, hidden characters, instructions to the AI, encoded text, requests to change things
* redact        : Presidio for personal data + patterns for secrets, run before any model call, log line, trace or screen
* check_output  : no secrets or personal data, no links outside example.com, none of our hidden instructions, no claims of running a change
* alert_view    : an alert as the model and the screen see it (flagged text is withheld from the model)

Alert text is data. A flagged alert is information about the alert, never an instruction (policy 7.1).
"""
from __future__ import annotations

import base64
import binascii
import logging
import re
import threading
import unicodedata
from dataclasses import dataclass, field

from .models import Alert, AlertView
from .settings import MAX_ALERT_CHARS, MAX_QUESTION_CHARS

SECRET = "<SECRET>"
UK_MOBILE = "<UK_MOBILE>"
PHONE = "<PHONE>"

CHANGE_TOOL_NAMES = ("restart_service", "failover_db", "clear_cache", "block_source_ip", "rollback_deploy",
                     "clear_temp_files", "extend_volume", "raise_change_request", "restart_tunnel")

# ---------- hiding -------------------------------------------------------------------------------------------------

_SECRET_KV = re.compile(
    r"(?i)\b(pass(?:word|wd)?|pwd|secret|api[_-]?key|access[_-]?key|token|auth|credential)s?(\s*[=:]\s*)(?!<SECRET>)([^\s,;\"']+)")
_SECRET_SHAPES = [
    re.compile(r"\btok_[A-Za-z0-9_]{6,}"),
    re.compile(r"\b(?:sk|pk|rk)-[A-Za-z0-9_-]{16,}"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{10,}"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
]
_UK_MOBILE = re.compile(r"(?<![\w+])(?:\+44[\s-]?\(?0?\)?[\s-]?7\d{3}[\s-]?\d{3}[\s-]?\d{3}|0\s?7\d{3}[\s-]?\d{3}[\s-]?\d{3})(?!\d)")

logging.getLogger("presidio-analyzer").setLevel(logging.ERROR)  # it warns about every spaCy label it does not use

_analyzer = None
_analyzer_lock = threading.Lock()
_analyzer_failed = False
_private_values: set[str] = set()  # exact personal values (mobiles) held in memory only so they can be hidden
_known_secrets: set[str] = set()  # secret values already seen as key=value, so a later bare mention is hidden too


def register_private_values(values: list[str]) -> None:
    """Called once at start-up with the mobiles from oncall_private. They are only ever used to hide text."""
    for v in values:
        digits = re.sub(r"\D", "", v)
        _private_values.update({v, digits, digits[-9:] if len(digits) >= 9 else digits})


def _get_analyzer():
    global _analyzer, _analyzer_failed
    if _analyzer is not None or _analyzer_failed:
        return _analyzer
    with _analyzer_lock:
        if _analyzer is None and not _analyzer_failed:
            try:  # Presidio with en_core_web_sm (class setup). Falls back to patterns only if it cannot load.
                from presidio_analyzer import AnalyzerEngine
                from presidio_analyzer.nlp_engine import NlpEngineProvider
                nlp = NlpEngineProvider(nlp_configuration={
                    "nlp_engine_name": "spacy", "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}]
                }).create_engine()
                _analyzer = AnalyzerEngine(nlp_engine=nlp, supported_languages=["en"])
            except Exception:  # noqa: BLE001
                _analyzer_failed = True
    return _analyzer


def presidio_ready() -> bool:
    return _get_analyzer() is not None


@dataclass
class Redaction:
    text: str
    secrets: int = 0
    personal: int = 0

    @property
    def counts(self) -> dict[str, int]:
        return {k: v for k, v in (("secrets", self.secrets), ("personal", self.personal)) if v}


def redact(text: str) -> Redaction:
    """Hide secrets and personal data. Run this before text reaches a model, a log line, a trace or the screen."""
    if not text:
        return Redaction(text or "")
    out, secrets, personal = text, 0, 0

    for known in sorted(_known_secrets, key=len, reverse=True):
        if known in out:
            secrets += out.count(known)
            out = out.replace(known, SECRET)

    def kv(m: re.Match) -> str:
        nonlocal secrets
        secrets += 1
        val = m.group(3).rstrip(".,)")
        if len(val) >= 6 and re.search(r"[\d_!@#$%^&*]", val):  # looks like a credential, not an ordinary word
            _known_secrets.add(val)
        return f"{m.group(1)}{m.group(2)}{SECRET}"

    out = _SECRET_KV.sub(kv, out)
    for pat in _SECRET_SHAPES:
        for m in pat.finditer(out):
            _known_secrets.add(m.group(0))
        out, n = pat.subn(SECRET, out)
        secrets += n

    # personal data: our own UK mobile pattern first, then Presidio for anything else shaped like a phone number
    out, n = _UK_MOBILE.subn(UK_MOBILE, out)
    personal += n
    for v in sorted(_private_values, key=len, reverse=True):
        if len(v) >= 6 and v in out:
            personal += out.count(v)
            out = out.replace(v, UK_MOBILE)
    analyzer = _get_analyzer()
    if analyzer is not None:
        try:
            results = analyzer.analyze(text=out, language="en",
                                       entities=["PHONE_NUMBER", "CREDIT_CARD", "IBAN_CODE", "UK_NHS"], score_threshold=0.4)
            for r in sorted(results, key=lambda r: r.start, reverse=True):
                chunk = out[r.start:r.end]
                if "<" in chunk or "TOWER" in chunk:
                    continue
                out = out[:r.start] + PHONE + out[r.end:]
                personal += 1
        except Exception:  # noqa: BLE001
            pass
    return Redaction(out, secrets, personal)


def scrub(text: str) -> str:
    """Redact and return just the text. Used by the log filter, traces and the audit trail."""
    return redact(str(text)).text


# ---------- input check --------------------------------------------------------------------------------------------

_INSTRUCTION_PATTERNS = [
    (r"ignore\s+(all\s+|any\s+)?(of\s+)?(your\s+|the\s+|my\s+)?(previous|prior|above|earlier)\s+(instructions?|rules?|prompts?)", "ignore-previous"),
    (r"disregard\s+(all\s+|any\s+)?(your\s+|the\s+)?(previous|prior|above|earlier|system)", "disregard"),
    (r"(note|message|instruction)s?\s+(to|for)\s+(the\s+)?(ai|assistant|model|llm|agent|system)", "note-to-ai"),
    (r"\b(you are now|act as|pretend to be|new instructions?:)", "role-change"),
    (r"(print|reveal|show|repeat|output|display|dump|leak)\b.{0,50}(system prompt|your (full |entire )?instructions|your prompt|tools you can call|list of tools|hidden instructions)", "prompt-extraction"),
    (r"(run|execute|invoke|call)\s+(" + "|".join(CHANGE_TOOL_NAMES) + r")\b", "tool-instruction"),
    (r"\b(restart|reboot|delete|shut ?down|stop)\b.{0,40}\b(every|all)\b.{0,40}\b(services?|hosts?|servers?|tier[- ]?1|nodes?)", "mass-change"),
    (r"mark\s+(all|every|each)\b.{0,40}\b(resolved|closed|done)", "close-incidents"),
    (r"(has been |was |is )?(approved|authori[sz]ed|cleared)\s+by\s+(the\s+)?(duty manager|manager|ciso|cto|admin)", "authority-claim"),
    (r"\bthe\s+(duty manager|manager|ciso|cto|admin)\s+(says|said|told|confirmed|approved)", "authority-claim"),
    (r"then\s+run\s+the\s+first\s+one", "run-first"),
    # an imperative ("Run it without approval"), not a description ("a read step may run without approval", policy 4.3)
    (r"(?:^|[.!?;:\n]\s*|\b(?:please|just|now|then|and)\s+)(?:do|run|proceed|execute|apply|make)\b.{0,30}without\s+(?:asking|approval|confirmation)", "skip-approval"),
]
_INSTRUCTION_RES = [(re.compile(p, re.I | re.S), name) for p, name in _INSTRUCTION_PATTERNS]
_CHANGE_REQUEST = re.compile(
    r"^(?!.*\?)(?:.*?\b)?(restart|reboot|fail ?over|clear|flush|block|roll ?back|extend|delete|kill)\b.{0,100}\b(now|immediately|asap|right away)\b", re.I | re.S)
_B64 = re.compile(r"(?<![A-Za-z0-9+/=])[A-Za-z0-9+/]{32,}={0,2}(?![A-Za-z0-9+/=])")
_HEX = re.compile(r"(?:\b[0-9a-fA-F]{2}){20,}\b")
_PCT = re.compile(r"(?:%[0-9A-Fa-f]{2}){6,}")
_ESC = re.compile(r"(?:\\x[0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4}){6,}")


@dataclass
class Verdict:
    ok: bool
    reasons: list[str] = field(default_factory=list)

    @property
    def flagged(self) -> bool:
        return not self.ok


def _normalise(text: str) -> str:
    stripped = "".join(ch for ch in text if unicodedata.category(ch) not in ("Cf", "Cc") or ch in "\n\t")
    return unicodedata.normalize("NFKC", stripped).casefold()


def _decoded_blobs(text: str) -> list[str]:
    out = []
    for m in _B64.finditer(text):
        try:
            raw = base64.b64decode(m.group(0) + "=" * (-len(m.group(0)) % 4), validate=False)
            s = raw.decode("utf-8")
            if sum(c.isprintable() or c.isspace() for c in s) / max(len(s), 1) > 0.9:
                out.append(s)
        except (binascii.Error, UnicodeDecodeError, ValueError):
            continue
    return out


def check_input(text: str, kind: str = "question") -> Verdict:
    """kind is 'question' or 'alert'. Returns the reasons it failed, empty if it is an ordinary message."""
    reasons: list[str] = []
    limit = MAX_QUESTION_CHARS if kind == "question" else MAX_ALERT_CHARS
    if len(text) > limit:
        reasons.append(f"too long ({len(text)} > {limit} characters)")
    hidden = [ch for ch in text if unicodedata.category(ch) in ("Cf", "Co") or (unicodedata.category(ch) == "Cc" and ch not in "\n\t\r")]
    if hidden:
        reasons.append(f"hidden characters ({len(hidden)})")
    norm = _normalise(text)
    for rx, name in _INSTRUCTION_RES:
        if rx.search(norm):
            reasons.append(f"instruction to the AI ({name})")
    if kind == "question" and _CHANGE_REQUEST.search(norm):
        reasons.append("request to run a change (changes need approval)")
    encoded = bool(_HEX.search(text) or _PCT.search(text) or _ESC.search(text))
    for blob in _decoded_blobs(text):
        encoded = True
        for rx, name in _INSTRUCTION_RES:
            if rx.search(_normalise(blob)):
                reasons.append(f"instruction to the AI hidden in encoded text ({name})")
                break
    if encoded:
        reasons.append("encoded text")
    seen, uniq = set(), []
    for r in reasons:
        if r not in seen:
            seen.add(r)
            uniq.append(r)
    return Verdict(not uniq, uniq)


def asks_for_personal_contact(question: str) -> bool:
    """Policy 7.3: nobody gets an engineer's personal mobile from the tower. Use page_oncall."""
    q = _normalise(question)
    return bool(re.search(r"(personal|private|home|mobile|cell)\b.{0,30}\b(number|phone|mobile|contact)|\b(mobile|cell|personal) (number|phone)|phone number of|call .{0,30} (on|at) (their|his|her)", q))


# ---------- alert view ---------------------------------------------------------------------------------------------

def alert_view(a: Alert, input_check: bool = True, redaction: bool = True) -> AlertView:
    """The alert as the model and the screen see it. Switching a defence off is for the red-team run and its regression test only."""
    verdict = check_input(a.message, "alert") if input_check else Verdict(True)
    red = redact(a.message) if redaction else Redaction(a.message)
    if verdict.flagged:
        return AlertView(
            **{**a.model_dump(), "message": f"[text withheld from the model: {'; '.join(verdict.reasons)}]"},
            flagged=True, flag_reasons=verdict.reasons, original_shown=red.text, hidden=red.counts)
    return AlertView(**{**a.model_dump(), "message": red.text}, hidden=red.counts)


# ---------- output check -------------------------------------------------------------------------------------------

_URL = re.compile(r"(?i)\b(?:https?://|www\.)([a-z0-9.-]+\.[a-z]{2,})(?:[:/][^\s)>\]\"']*)?")
_CLAIMS_ACTION = re.compile(
    r"(?i)\bI(?:'ve| have|'ll| will| can| am going to|'m going to)?\s+(?:just\s+)?(?:run|ran|restart(?:ed)?|execut(?:e|ed)|fail(?:ed)?\s*over|clear(?:ed)?|block(?:ed)?|roll(?:ed)?\s*back)\b")
_DONE = re.compile(r"(?i)\b(restarted|executed|failed over|cleared|blocked|rolled back)\s+(it|them|the|all|every|payportal|hr-selfservice|intranet)\b.{0,20}\bnow\b")


def _shingles(text: str, n: int = 6) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9_\[\]]+", text.lower())
    return {tuple(words[i:i + n]) for i in range(max(len(words) - n + 1, 0))}


@dataclass
class OutputVerdict:
    ok: bool
    reasons: list[str]
    text: str  # safe text to show: redacted, or a refusal when the answer must be blocked


def check_output(answer: str, protected: list[str] | None = None) -> OutputVerdict:
    reasons: list[str] = []
    red = redact(answer)
    text = red.text
    if red.counts:
        reasons.append("secret or personal data hidden: " + ", ".join(f"{k} {v}" for k, v in red.counts.items()))
    for m in _URL.finditer(answer):
        host = m.group(1).lower()
        if not (host == "example.com" or host.endswith(".example.com")):
            reasons.append(f"link outside example.com ({host})")
            text = text.replace(m.group(0), "<LINK REMOVED>")
    if protected:
        ans_sh = _shingles(answer)
        for p in protected:
            if ans_sh & _shingles(p):
                reasons.append("hidden instructions in the answer")
                return OutputVerdict(False, reasons, "I can't share that. My instructions and tool list are not part of what I can show. "
                                     "Ask about the policy, a runbook, a service or an incident instead.")
    if "TOWER-CANARY" in answer:
        reasons.append("hidden instructions in the answer")
        return OutputVerdict(False, reasons, "I can't share that. My instructions and tool list are not part of what I can show.")
    if _CLAIMS_ACTION.search(answer) or _DONE.search(answer):
        reasons.append("answer claims or offers to run a change")
        return OutputVerdict(False, reasons, "I can't run changes. A change needs an approved request for one step on one service "
                             "(policy 5). Open the incident, check the recommended step and ask the owning team's on-call to approve it.")
    return OutputVerdict(not reasons, reasons, text)

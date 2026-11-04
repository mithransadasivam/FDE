"""Activity 3 (ticket ENG-101): turn the discovery transcript into findings, each with its evidence.

A finding is a pain point, requirement, constraint or open question, with the exact words that
support it and who said them. The model drafts the findings; verify_evidence() then checks every
quote against the transcript in code, because a model can paraphrase or invent a quote.
"""

import re

from app.discovery.models import ExtractedFindings, Finding  # noqa: F401  (you need both)
from app.llm import ask_json  # noqa: F401  (you need it)

FINDINGS_PROMPT = """You are a forward deployed engineer writing up a client discovery session.
Read the transcript and list what you learned, as findings of four kinds:
- pain_point: something that hurts today; give frequency (1-5, how often) and impact (1-5, how much)
- requirement: something the solution must do
- constraint: a rule, limit or approval the solution must respect
- open_question: something we still need to find out

For every finding give the speaker's name as it appears in the transcript (Deborah, Tom, Helen or FDE)
and a quote: the exact words from the transcript that support it, copied character for character.
Use numbers whenever the client gave them. Do not invent anything the transcript does not say.

Reply with JSON only, in this shape:
{"findings": [{"kind": "pain_point", "title": "...", "detail": "...", "speaker": "Tom",
  "quote": "...", "frequency": 5, "impact": 4}]}"""


def extract_findings(transcript: str, client) -> list[Finding]:
    """Ask the model for findings and number them F01, F02, ... in the order it returned them.

    Use ask_json(client, FINDINGS_PROMPT, transcript, ExtractedFindings, task="findings").
    Return Finding objects with evidence_ok left as None: verify_evidence() sets it.
    """
    extracted = ask_json(client, FINDINGS_PROMPT, transcript, ExtractedFindings, task="findings")
    return [Finding(id=f"F{i:02d}", **item.model_dump()) for i, item in enumerate(extracted.findings, start=1)]


def utterances(transcript: str) -> list[tuple[str, str]]:
    """Split the transcript into (speaker, words) pairs, one per line such as
    '**[02:45] Tom:** I work on two screens...'."""
    out = []
    for m in re.finditer(r"^\*\*\[\d\d:\d\d\]\s*([^:*]+):\*\*\s*(.+)$", transcript, flags=re.M):
        out.append((m.group(1).strip(), m.group(2)))
    return out


def verify_evidence(findings: list[Finding], transcript: str) -> list[Finding]:
    """Set evidence_ok on every finding: True only if its quote appears, word for word, in
    something its speaker said. Ignore case, extra spaces, curly quotes and Markdown asterisks.
    Keep every finding, in the same order, with the same ids.
    """
    spoken = [(speaker.casefold(), _normalise(words)) for speaker, words in utterances(transcript)]
    out = []
    for f in findings:
        quote = _normalise(f.quote)
        speaker = f.speaker.strip().casefold()
        ok = bool(quote) and any(s == speaker and quote in words for s, words in spoken)
        out.append(f.model_copy(update={"evidence_ok": ok}))
    return out


def _normalise(text: str) -> str:
    """Lower case, straight quotes, no Markdown asterisks, single spaces."""
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"').replace("*", "")
    return re.sub(r"\s+", " ", text).strip().casefold()

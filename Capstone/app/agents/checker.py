"""The evidence checker (Day 3, prompt 3): before a person relies on a screening or an interview scorecard, a checker confirms the evidence is real and that
nothing about identity was used.

Code checks (always): every non-zero score has a quote found in its source (the CV facts or the transcript); the text the AI wrote about the person mentions no
protected detail (age, gender, nationality, religion, health, family, accent, fluency, confidence, tone, ...); the totals add up.
Model check (one call per candidate): does each quote really support its score level?
Result: CHECKED, or NEEDS_REVIEW with the items listed. A person must tick "I have looked at these" before the recruiter can shortlist or decide.
The checker REPORTS. It never changes a score (a checker that fixed scores would be a second, unreviewed scorer).
"""
import re
from datetime import datetime, timezone

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import guardrails, security
from app.agents.wording import check_wording
from app.ai.llm import complete_json
from app.evidence import blind_text, quote_exists
from app.interview.bank import load_questions
from app.models import Candidate, DecisionLog, Requisition
from app.models_ext import EvidenceCheck, InterviewSession, ItemScoreRow, ShortlistEntry
from app.privacy import make_blind

PROTECTED_WORDS = ["age", "aged", "old", "young", "gender", "male", "female", "woman", "man", "nationality", "native speaker", "native english", "religion", "religious",
                   "health", "disability", "disabled", "pregnant", "pregnancy", "family", "children", "married", "marital", "accent", "fluency", "fluent", "confident",
                   "confidence", "tone", "polished", "eloquent", "voice", "ethnic", "ethnicity", "race", "sexual", "union", "political"]
PROTECTED_RX = re.compile(r"\b(?:" + "|".join(sorted(map(re.escape, PROTECTED_WORDS), key=len, reverse=True)) + r")\b", re.I)

CHECK_SYSTEM = """You check whether each quote really supports its score level. For every item say supports (true or false) and give a one-line reason.
A quote supports a score only if it is about the skill and is enough evidence for that level. You only report: you never change a score.
""" + security.DATA_RULE


class Problem(BaseModel):
    where: str  # for example "Kubernetes" or "summary"
    problem: str  # the kind of problem
    detail: str


class ItemCheck(BaseModel):
    skill: str
    supports: bool
    reason: str = ""


class CheckOut(BaseModel):
    items: list[ItemCheck]


def protected_hits(text: str) -> list[str]:
    """Protected words or phrases in a text the AI wrote about a person (a word list plus the wording rules)."""
    hits = {m.group(0).lower() for m in PROTECTED_RX.finditer(text or "")}
    hits |= {f.phrase.lower() for f in check_wording(text or "", "check")}
    hits |= {w.lower() for _k, w in guardrails.scan_protected(text or "")}
    return sorted(hits)


# ---- the model check -----------------------------------------------------------------------------------------------------------------------------
def _fake_check(user: str) -> CheckOut:
    """Rule-based stand-in: a score above 0 is supported only if the quote is about the skill (shares a keyword with it), and a level of 3 needs a quote of a few words."""
    from app.agents.screening import keywords_for

    out = []
    for m in re.finditer(r"^- (.+?) \| score (\d) \| quote: (.*?)(?: \| keywords: (.*))?$", user, re.M):
        skill, score, quote = m.group(1), int(m.group(2)), m.group(3).strip().strip('"')
        given = [k.strip().lower() for k in (m.group(4) or "").split(",") if k.strip()]  # an interview answer is judged against the question's own key words
        if score == 0:
            out.append(ItemCheck(skill=skill, supports=True, reason="no score to support"))
            continue
        kws = given or keywords_for(skill)
        about = any(re.search(r"(?<![\w])" + re.escape(k) + r"(?![\w])", quote.lower()) for k in kws) or any(w in quote.lower() for w in re.findall(r"[a-z]{4,}", skill.lower()))
        ok = about and (score < 3 or len(quote.split()) >= 1)
        out.append(ItemCheck(skill=skill, supports=ok, reason="the quote is about the skill" if ok else "the quote is not about this skill, so it cannot support the level"))
    return CheckOut(items=out)


def model_check(rows: list[tuple], cand_id: int) -> list[ItemCheck]:
    """rows: (skill, score, quote), or with a fourth item: the words a good answer to this question uses."""
    lines = "\n".join(f'- {r[0]} | score {r[1]} | quote: "{r[2]}"' + (f" | keywords: {', '.join(r[3])}" if len(r) > 3 and r[3] else "") for r in rows)
    return complete_json(CHECK_SYSTEM, security.wrap_untrusted("quotes", lines), CheckOut, fake=_fake_check, task="judgement", agent="checker", candidate_id=cand_id).items


# ---- the checks ---------------------------------------------------------------------------------------------------------------------------------
def _save(db: Session, cand_id: int, subject: str, problems: list[Problem]) -> EvidenceCheck:
    old = db.scalars(select(EvidenceCheck).where(EvidenceCheck.candidate_id == cand_id, EvidenceCheck.subject == subject)).all()
    row = EvidenceCheck(candidate_id=cand_id, subject=subject, status="NEEDS_REVIEW" if problems else "CHECKED", items=[p.model_dump() for p in problems])
    for o in old:
        db.delete(o)  # the latest check replaces the earlier one
    db.add(row)
    db.add(DecisionLog(actor="system", action="evidence checked", subject=f"candidate:{cand_id}", reason=f"{subject}: {row.status}" + (f", {len(problems)} problem(s)" if problems else "")))
    db.flush()
    return row


def check_screening(db: Session, cand: Candidate, req: Requisition) -> EvidenceCheck:
    """Code checks (quotes, protected words, totals), then one model check. Never changes a score."""
    rows = list(db.scalars(select(ItemScoreRow).where(ItemScoreRow.candidate_id == cand.id, ItemScoreRow.requisition_id == req.id).order_by(ItemScoreRow.id)))
    source = blind_text(make_blind(cand))
    problems: list[Problem] = []
    for r in rows:
        if r.score > 0 and not quote_exists(r.quote, source):
            problems.append(Problem(where=r.skill, problem="quote not found", detail=f"score {r.score} cites \"{r.quote[:70]}\", which is not in the CV facts"))
        for w in protected_hits(r.quote):
            problems.append(Problem(where=r.skill, problem="protected detail", detail=f"the quote mentions \"{w}\""))
    entry = db.scalars(select(ShortlistEntry).where(ShortlistEntry.requisition_id == req.id, ShortlistEntry.candidate_id == cand.id)).first()
    total = round(sum(r.weight * r.score for r in rows) / 3, 1)
    if entry is not None:
        if abs(entry.weighted_total - total) > 0.05:
            problems.append(Problem(where="total", problem="totals do not add up", detail=f"the shortlist shows {entry.weighted_total}, the scores add up to {total}"))
        for text in list(entry.strengths or []) + list(entry.gaps or []):
            for w in protected_hits(text):
                problems.append(Problem(where="strengths and gaps", problem="protected detail", detail=f"\"{w}\" in: {text[:60]}"))
    if sum(r.weight for r in rows) != 100 and rows:
        problems.append(Problem(where="weights", problem="totals do not add up", detail=f"the rubric weights add up to {sum(r.weight for r in rows)}, not 100"))
    for it in model_check([(r.skill, r.score, r.quote) for r in rows if r.score > 0], cand.id):
        if not it.supports:
            problems.append(Problem(where=it.skill, problem="quote does not support the level", detail=it.reason))
    return _save(db, cand.id, "screening", problems)


def check_interview(db: Session, s: InterviewSession) -> EvidenceCheck:
    """The same checks for an AI interview scorecard: quotes against the transcript, the AI-written texts, the totals."""
    bank = load_questions()
    problems: list[Problem] = []
    rows = []
    for t in (s.state or {}).get("turns", []):
        if t.get("opening") or not t.get("score") or t.get("skipped"):
            continue
        said = " ".join(a["text"] for a in t.get("answers", []))
        sc = t["score"]
        if sc["score"] > 0 and not quote_exists(sc.get("quote", ""), said):
            problems.append(Problem(where=t["skill"], problem="quote not found", detail=f"score {sc['score']} cites \"{sc.get('quote', '')[:70]}\", which is not in the transcript"))
        for w in protected_hits(sc.get("quote", "")):
            problems.append(Problem(where=t["skill"], problem="protected detail", detail=f"the quote mentions \"{w}\""))
        for m in t.get("meta", []):
            for w in protected_hits(m.get("why", "")):
                problems.append(Problem(where=t["skill"], problem="protected detail", detail=f"\"{w}\" in why a question was asked"))
        if sc["score"] > 0:
            q = bank.get(t["question_id"], {})
            rows.append((t["skill"], sc["score"], sc.get("quote", ""), [k for d in q.get("key_point_detail", []) for k in d.get("keywords", [])]))
    summary = ((s.scorecard or {}).get("summary") or {}).get("text", "")
    for w in protected_hits(summary):
        problems.append(Problem(where="summary", problem="protected detail", detail=f"\"{w}\" in the AI-written summary"))
    answers = (s.scorecard or {}).get("answers", [])
    scored = [a for a in answers if not a.get("skipped")]
    if scored and abs((s.scorecard or {}).get("total", 0) - round(sum(a["score"] for a in scored) / len(scored), 2)) > 0.01:
        problems.append(Problem(where="total", problem="totals do not add up", detail="the average on the scorecard is not the average of the answers"))
    for it in model_check(rows, s.candidate_id):
        if not it.supports:
            problems.append(Problem(where=it.skill, problem="quote does not support the level", detail=it.reason))
    return _save(db, s.candidate_id, "interview", problems)


# ---- the acknowledgement a person must give ---------------------------------------------------------------------------------------------------
def unacknowledged(db: Session, cand_id: int, subject: str | None = None) -> list[EvidenceCheck]:
    q = select(EvidenceCheck).where(EvidenceCheck.candidate_id == cand_id, EvidenceCheck.status == "NEEDS_REVIEW", EvidenceCheck.acknowledged_by.is_(None))
    if subject:
        q = q.where(EvidenceCheck.subject == subject)
    return list(db.scalars(q))


def acknowledge(db: Session, check_id: int, actor: str) -> EvidenceCheck:
    """A person says "I have looked at these". Only then can the candidate be shortlisted or decided on."""
    if "@" not in (actor or ""):
        raise PermissionError("Only a person can acknowledge the problems")
    row = db.get(EvidenceCheck, check_id)
    if row is None:
        raise LookupError("That check does not exist")
    row.acknowledged_by, row.acknowledged_at = actor, datetime.now(timezone.utc)
    db.add(DecisionLog(actor=actor, action="evidence problems acknowledged", subject=f"candidate:{row.candidate_id}",
                       reason=f"{row.subject}: {len(row.items or [])} problem(s) looked at", evidence={"items": row.items}))
    return row


def run_checks(db: Session, req_id: int) -> int:
    """Checks every screened candidate of a job (run after screening and the shortlist suggestion). Returns how many need a person's look."""
    req = db.get(Requisition, req_id)
    n = 0
    for cand in db.scalars(select(Candidate).where(Candidate.requisition_id == req_id, Candidate.stage.in_(["SCREENED", "SHORTLISTED", "AI_INTERVIEW", "HUMAN_INTERVIEW", "DECISION"])).order_by(Candidate.id)):
        if db.scalars(select(ItemScoreRow).where(ItemScoreRow.candidate_id == cand.id)).first() is None:
            continue
        n += check_screening(db, cand, req).status == "NEEDS_REVIEW"
    db.commit()
    return n


def explain_refusal(rows: list[EvidenceCheck]) -> str:
    what = "; ".join(f"{r.subject}: " + ", ".join(sorted({p['problem'] for p in (r.items or [])})) for r in rows)
    return f"The evidence checker found problems ({what}). Read them and tick \"I have looked at these\" first."

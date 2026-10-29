"""The interview scorecard (Day 2, prompt 14): everything a recruiter needs to review one AI interview, with the evidence behind every number.

For each rubric skill: the level with the description of that level, the questions asked (each with why it was asked), the transcript quote for
the best answer, any diagram, the hints and follow-ups used, and a second scorer's level. The overall score is calculated by code from the rubric
weights. Where the two scorers' levels differ by 2 or more the card says "scorers disagree: please review": a difference is shown to a person,
never averaged away. A short AI-written summary is made from the scores only.
"""
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai.llm import complete_json
from app.interview.bank import load_questions
from app.models import Candidate, Requisition
from app.models_ext import InterviewSession

DISAGREE_BY = 2  # levels apart that count as "scorers disagree"
SUMMARY_SYSTEM = """You write a short summary of an interview for a recruiter, from the SCORES ONLY (skill, weight, level 0-3). List the strengths
(skills with a high level) and the gaps (skills with a low level or not asked). Do not invent anything that is not in the scores. Never mention
the person's voice, accent, tone or appearance. The summary is a suggestion: a recruiter reads the evidence and decides."""


class Summary(BaseModel):
    strengths: list[str]
    gaps: list[str]
    text: str


def _fake_summary(user: str) -> Summary:
    import re

    rows = [(m.group(1), int(m.group(2)), int(m.group(3))) for m in re.finditer(r"^- (.+?) \| weight (\d+) \| level (\d|not asked)", user, re.M) if m.group(3).isdigit()]
    not_asked = re.findall(r"^- (.+?) \| weight \d+ \| level not asked", user, re.M)
    strong = [s for s, _w, lv in rows if lv >= 3]
    weak = [s for s, _w, lv in rows if lv <= 1] + not_asked
    text = ("Strongest on " + ", ".join(strong[:3]) + "." if strong else "No skill reached the top level.") + \
           (" Weakest on " + ", ".join(weak[:3]) + "." if weak else " No clear gaps in the skills that were asked about.")
    return Summary(strengths=[f"{s} (level 3)" for s in strong[:4]], gaps=[f"{s}" for s in weak[:4]], text=text)


def _levels(s: InterviewSession) -> dict[str, dict]:
    """Per skill: the best level, the best second-scorer level and the turns that asked about it (from the saved state)."""
    out: dict[str, dict] = {}
    second = (s.scorecard or {}).get("second_scorer", {})
    for t in (s.state or {}).get("turns", []):
        if t.get("opening") or not t.get("skill"):
            continue
        row = out.setdefault(t["skill"], {"level": None, "second": None, "turns": []})
        sc = t.get("score")
        if sc and not t.get("skipped"):
            row["level"] = sc["score"] if row["level"] is None else max(row["level"], sc["score"])
            if t["question_id"] in second:
                row["second"] = second[t["question_id"]] if row["second"] is None else max(row["second"], second[t["question_id"]])
        row["turns"].append(t)
    return out


def write_summary(s: InterviewSession, rubric_items: list[dict]) -> dict:
    """The AI-written summary, from the scores only: no transcript, no quote and no identity reach this prompt."""
    levels = _levels(s)
    lines = "\n".join(f"- {i['skill']} | weight {i['weight']} | level {levels[i['skill']]['level'] if i['skill'] in levels and levels[i['skill']]['level'] is not None else 'not asked'}"
                      for i in rubric_items)
    return complete_json(SUMMARY_SYSTEM, f"<scores>\n{lines}\n</scores>", Summary, fake=_fake_summary, task="judgement", agent="scorecard",
                         candidate_id=s.candidate_id).model_dump()


def build_card(db: Session, s: InterviewSession) -> dict:
    cand = db.get(Candidate, s.candidate_id)
    req = db.get(Requisition, cand.requisition_id)
    items = (req.rubric or {}).get("items", [])
    bank = load_questions()
    levels = _levels(s)
    skills, flagged = [], []
    for item in items + [{"skill": k, "weight": 0, "must_have": False} for k in levels if k not in {i["skill"] for i in items}]:
        info = levels.get(item["skill"])
        asked = info is not None
        level = info["level"] if asked else None
        best = None
        questions = []
        for t in (info or {}).get("turns", []):
            q = bank.get(t["question_id"], {})
            sc = t.get("score") or {}
            for m in t.get("meta", []):
                if m["kind"] == "hint":
                    continue
                questions.append({"text": m["text"], "kind": m["kind"], "why": m.get("why", ""), "guard": (m.get("guard") or {}).get("used", "fixed core question")
                                  if not (m.get("guard") or {}).get("fixed") else "core question: asked as written",
                                  "diagram": m.get("diagram"), "diagram_info": m.get("diagram_info")})
            if sc.get("quote") and sc.get("verified") and (best is None or sc["score"] >= best["score"]):
                best = {"quote": sc["quote"], "score": sc["score"], "audio": (t["answers"][0].get("audio") if t.get("answers") else None),
                        "start_s": (t["answers"][0].get("start_s", 0.0) if t.get("answers") else 0.0)}
        scale_q = next((bank.get(t["question_id"]) for t in (info or {}).get("turns", []) if t["question_id"] in bank), {})
        diff = abs(level - info["second"]) if asked and level is not None and info.get("second") is not None else 0
        row = {"skill": item["skill"], "weight": item["weight"], "must_have": bool(item.get("must_have")), "asked": asked, "level": level,
               "level_description": (scale_q.get("scoring") or {}).get(str(level), "") if level is not None else "",
               "second_level": info["second"] if asked else None, "scorers_differ_by": diff, "scorers_disagree": diff >= DISAGREE_BY,
               "questions": questions, "best": best,
               "hints": sum(1 for t in (info or {}).get("turns", []) if t.get("hint_used")),
               "follow_ups": sum(1 for t in (info or {}).get("turns", []) for m in t.get("meta", []) if m["kind"] == "follow_up")}
        skills.append(row)
        if row["scorers_disagree"]:
            flagged.append(item["skill"])
    overall = round(sum(r["weight"] * r["level"] / 3 for r in skills if r["level"] is not None), 1)  # calculated by code from the rubric weights
    return {"skills": skills, "overall_100": overall, "must_haves": [{"skill": r["skill"], "covered": r["asked"], "level": r["level"]} for r in skills if r["must_have"]],
            "all_must_haves_covered": all(r["asked"] for r in skills if r["must_have"]), "scorers_disagree": flagged,
            "summary": (s.scorecard or {}).get("summary"), "review": s.review, "reviewed_by": s.reviewed_by}

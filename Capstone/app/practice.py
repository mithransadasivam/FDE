"""A fictional recruiter-led interview to practise the copilot on (Day 3, prompt 4).

make_practice(db, candidate) writes storage/practice/<id>/practice.json and practice.wav: a script of lines (recruiter or candidate) about 4-6 minutes long, built from the
candidate's BLIND profile and the job's rubric, spoken with two clearly different voices. It contains five labelled "planned moments" for the copilot to catch:

  1 good_technical_answer   a good answer that covers most points of the question guide
  2 vague_answer            a vague answer that needs a follow-up
  3 forbidden_question      the recruiter asks something that must not be asked (children, family plans)
  4 cv_conflict             the candidate claims far more years with a tool than the CV shows
  5 behavioural_answer      a behavioural question answered with a full example (situation, task, action, result)

Everything in it is fictional and marked SAMPLE. In fake mode the script is built by rules; with a real model a model writes it and code checks that all five moments are there.
"""
import json
import re
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import security
from app.ai import audio, speech, voice
from app.ai.llm import complete_json
from app.config import get_settings
from app.interview.bank import load_questions
from app.models import Candidate, Requisition
from app.models_ext import ItemScoreRow
from app.privacy import make_blind

MOMENTS = ["good_technical_answer", "vague_answer", "forbidden_question", "cv_conflict", "behavioural_answer"]
NUMBER_WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight", 9: "nine", 10: "ten", 11: "eleven", 12: "twelve", 15: "fifteen"}
VAGUE = ["I would just check the logs and see what is going on.", "It depends, I would probably ask a colleague who knows it better.",
         "I have seen something like that before, I would look at it and try a few things."]
GAP_SECONDS = 0.45


class Line(BaseModel):
    speaker: str  # recruiter or candidate
    text: str
    moment: str | None = None  # one of MOMENTS, or None


class ScriptOut(BaseModel):
    lines: list[Line]


SYSTEM = """You write a fictional first-round interview of about six minutes between a recruiter and a candidate, as a list of lines (speaker recruiter or candidate, text).
It must contain exactly these planned moments, each on the line that carries it (the moment field): good_technical_answer (a good, detailed technical answer),
vague_answer (a short vague answer that needs a follow-up), forbidden_question (the recruiter asks about children or age: this is a test of the assistant), cv_conflict
(the candidate claims many more years with a tool than the CV shows), behavioural_answer (a behavioural question with a full example: situation, task, action, result).
Use only the facts you are given. Everything is fictional. """ + security.DATA_RULE


def _years_words(n: int) -> str:
    return NUMBER_WORDS.get(n, str(n))


def _facts(db: Session, cand: Candidate, req: Requisition) -> dict:
    blind = make_blind(cand)
    scores = {r.skill: r.score for r in db.scalars(select(ItemScoreRow).where(ItemScoreRow.candidate_id == cand.id, ItemScoreRow.requisition_id == req.id))}
    items = (req.rubric or {}).get("items", [])
    return {"blind": blind, "scores": scores, "items": items, "years": float(blind.years_experience or 2)}


def _bank_question(skill: str, kind: str = "technical") -> dict | None:
    qs = [q for q in load_questions().values() if q["type"] == kind and q["skill"].lower() == skill.lower()]
    return sorted(qs, key=lambda q: (not q["core"], q["id"]))[0] if qs else None


def build_script(facts: dict) -> tuple[list[Line], dict]:
    """The rule-based script (fake mode): returns the lines and the facts about each planned moment (what the copilot should catch)."""
    items, scores, years, blind = facts["items"], facts["scores"], facts["years"], facts["blind"]
    ranked = sorted((i for i in items if _bank_question(i["skill"])), key=lambda i: (-scores.get(i["skill"], 0), -i["weight"], i["skill"]))
    strong = ranked[0] if ranked else {"skill": "Linux troubleshooting"}
    vague = next((i for i in ranked[1:] if scores.get(i["skill"], 0) >= 0), ranked[1] if len(ranked) > 1 else strong)
    # the conflict: the candidate claims far more years with a tool than the CV shows in all. Prefer a tool the CV lists (so the card says "more years than the CV
    # shows"); otherwise a well-known tool the CV never mentions.
    from app.agents.copilot import KNOWN_TOOLS

    cv_skills = {x.strip().lower() for x in blind.skills}

    listed = [t for t in KNOWN_TOOLS if any(t.lower() == x.strip().lower() for x in blind.skills)]
    absent = [t for t in ("Kubernetes", "Terraform", "Ansible", "Docker") if t.lower() not in cv_skills]
    tool_name = (listed or absent or ["Linux"])[0]
    conflict = next((i for i in ranked if tool_name.lower() in i["skill"].lower()), ranked[min(2, len(ranked) - 1)] if ranked else strong)
    claimed = max(6, int(years) + 5)
    qs, qv = _bank_question(strong["skill"]), _bank_question(vague["skill"])
    behavioural = next((q for q in load_questions().values() if q["type"] == "behavioural"), None)
    title = (blind.current_title or "").strip()
    title_phrase = (("an " if title[:1].lower() in "aeiou" else "a ") + title) if title else "a support engineer"
    good = " ".join(d["say"] for d in qs["key_point_detail"][:3])
    lines = [
        Line(speaker="recruiter", text="Hello, thanks for joining. I will ask a few questions about your experience, and we can talk about the role at the end."),
        Line(speaker="candidate", text=f"Hello, thank you for having me. I currently work as {title_phrase}, and I am looking forward to this."),
        Line(speaker="recruiter", text=qs["question"]),
        Line(speaker="candidate", text=good + " I would also write down what I found so the next person can follow it.", moment="good_technical_answer"),
        Line(speaker="recruiter", text="Thank you, that was clear. Next: " + qv["question"]),
        Line(speaker="candidate", text=VAGUE[0], moment="vague_answer"),
        Line(speaker="recruiter", text="Do you have children, and are you planning to start a family?", moment="forbidden_question"),
        Line(speaker="candidate", text="I would rather keep our conversation on the job, if that is all right."),
        Line(speaker="recruiter", text=f"Of course, let us stay with the role. Tell me about your experience with {tool_name}."),
        Line(speaker="candidate", text=f"I have used {tool_name} for {_years_words(claimed)} years in production, across several large systems.", moment="cv_conflict"),
        Line(speaker="recruiter", text=behavioural["question"] if behavioural else "Tell me about a time you dealt with an upset customer."),
        Line(speaker="candidate", text=("The situation was an outage that left a customer without their service for an hour, and the customer was upset. My task was to keep them informed "
                                          "and get the service back. I acknowledged the problem straight away, explained what we knew, called them every thirty minutes and led the fix with the "
                                          "on-call engineer. The result was that the service came back, the customer thanked us, and we reduced the time to fix the next incident."),
             moment="behavioural_answer"),
        Line(speaker="recruiter", text="Thank you, that is all from me. Do you have any questions about the role?"),
        Line(speaker="candidate", text="Yes, how is the on-call rota shared between the team?"),
        Line(speaker="recruiter", text="It is shared evenly, and we can go through the details when we meet again. Thank you for your time."),
    ]
    facts_out = {
        "good_technical_answer": {"question_id": qs["id"], "skill": strong["skill"], "key_points": qs["key_points"]},
        "vague_answer": {"question_id": qv["id"], "skill": vague["skill"]},
        "forbidden_question": {"category": "family or pregnancy"},
        "cv_conflict": {"skill": tool_name, "claimed_years": claimed, "cv_years": years, "claim": f"{_years_words(claimed)} years with {tool_name}"},
        "behavioural_answer": {"question_id": behavioural["id"] if behavioural else "B-01", "star": ["Situation", "Task", "Action", "Result"]},
    }
    return lines, facts_out


def write_script(facts: dict) -> tuple[list[Line], dict]:
    """The script. With a real model a model writes it from the blind facts, and code checks every planned moment is there (otherwise the rule-based script is used)."""
    lines, moments = build_script(facts)
    if get_settings().fake_models:
        return lines, moments
    blind = facts["blind"]
    prompt = (security.wrap_untrusted("profile", f"title: {blind.current_title}\nyears: {facts['years']}\nskills: {', '.join(blind.skills)}\njobs: {'; '.join(blind.jobs)}")
              + "\n<rubric>\n" + "\n".join(f"- {i['skill']}" for i in facts["items"]) + "\n</rubric>")
    try:
        out = complete_json(SYSTEM, prompt, ScriptOut, task="judgement", agent="practice")
        if all(any(l.moment == m for l in out.lines) for m in MOMENTS):
            return out.lines, moments
    except Exception:
        pass
    return lines, moments


def folder_for(cand_id: int) -> Path:
    return get_settings().storage_dir / "practice" / str(cand_id)


def make_practice(db: Session, cand: Candidate, speak_real: bool = True) -> dict:
    """Writes practice.json and practice.wav for a candidate and returns the timeline."""
    req = db.get(Requisition, cand.requisition_id)
    lines, moments = write_script(_facts(db, cand, req))
    out = folder_for(cand.id)
    out.mkdir(parents=True, exist_ok=True)
    work = out / "_work"
    work.mkdir(exist_ok=True)
    wavs, timeline, clock = [], [], 0.0
    gap = audio.silent_wav(work / "gap.wav", GAP_SECONDS)
    try:
        for n, ln in enumerate(lines, 1):
            raw = work / f"line_{n:02d}_raw.wav"
            ok = speech.speak(ln.text, raw, voice="interviewer" if ln.speaker == "recruiter" else "candidate", real=speak_real)  # two clearly different voices
            if ok is None:
                audio.silent_wav(raw, max(0.8, voice.speaking_seconds(ln.text)))
            clip = audio.to_wav(raw, work / f"line_{n:02d}.wav")
            length = audio.duration(clip)
            if wavs:
                wavs.append(gap)
                clock += GAP_SECONDS
            wavs.append(clip)
            timeline.append({"n": n, "speaker": ln.speaker, "text": ln.text, "start": round(clock, 2), "end": round(clock + length, 2), "moment": ln.moment})
            clock += length
        audio.join(wavs, out / "practice.wav")
    finally:
        for f in work.glob("*"):
            f.unlink(missing_ok=True)
        work.rmdir()
    for m, info in moments.items():
        row = next(t for t in timeline if t["moment"] == m)
        info.update({"line": row["n"], "start": row["start"], "end": row["end"]})
    doc = {"id": f"P-{cand.id:03d}", "kind": "practice", "sample": True, "label": "SAMPLE: fictional", "candidate_id": cand.id, "cv_file": cand.cv_name,
           "file": f"practice/{cand.id}/practice.wav", "duration_s": round(clock, 2), "moments": moments, "lines": timeline,
           "turns": [{"speaker": t["speaker"], "text": t["text"], "start": t["start"], "end": t["end"]} for t in timeline]}
    (out / "practice.json").write_text(json.dumps(doc, indent=1), encoding="utf-8")
    return doc


def load_practice(cand_id: int) -> dict | None:
    p = folder_for(cand_id) / "practice.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None

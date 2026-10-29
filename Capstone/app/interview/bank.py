"""Question and diagram banks, and the interview plan builder (Day 2).

The plan has 8 questions. The CORE questions come first and depend only on the job's rubric, so every candidate for a role is
asked the same ones (rule 6). The remaining questions are aimed at the gaps in THIS candidate's scores (a rule in code).
"""
import json
from functools import lru_cache
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Requisition
from app.models_ext import ItemScoreRow
from app.schemas import InterviewPlan, PlanItem

MAX_QUESTIONS = 8
MAX_CORE = 5


@lru_cache
def load_questions() -> dict[str, dict]:
    path = Path(get_settings().kit_dir) / "question_bank.json"
    return {q["id"]: q for q in json.loads(path.read_text(encoding="utf-8"))} if path.exists() else {}


@lru_cache
def load_diagrams() -> dict[str, dict]:
    path = Path(get_settings().kit_dir) / "diagrams.json"
    return {d["id"]: d for d in json.loads(path.read_text(encoding="utf-8"))} if path.exists() else {}


def diagram_path(diagram_id: str) -> Path | None:
    d = load_diagrams().get(diagram_id)
    return Path(get_settings().kit_dir) / d["file"] if d else None


def _by_skill(skill: str, core: bool | None = None) -> list[dict]:
    out = [q for q in load_questions().values() if q["type"] == "technical" and q["skill"].lower() == skill.lower()]
    return [q for q in out if core is None or q["core"] == core]


def core_questions(rubric_items: list[dict]) -> list[dict]:
    """The same for everybody: for each rubric skill, heaviest first, its core question (or its first question)."""
    chosen: list[dict] = []
    for item in sorted(rubric_items, key=lambda i: (-i["weight"], i["skill"])):
        qs = _by_skill(item["skill"], True) or _by_skill(item["skill"])
        if qs and qs[0]["id"] not in {c["id"] for c in chosen}:
            chosen.append(qs[0])
        if len(chosen) == MAX_CORE:
            break
    return chosen


def build_plan(db: Session, candidate_id: int, req: Requisition) -> InterviewPlan:
    items = (req.rubric or {}).get("items", [])
    plan: list[PlanItem] = [PlanItem(question_id=q["id"], skill=q["skill"], core=True, diagram=q["diagram"],
                                     reason="core question: the same for every candidate for this role") for q in core_questions(items)]
    used = {p.question_id for p in plan}
    scores = {r.skill: r.score for r in db.scalars(select(ItemScoreRow).where(ItemScoreRow.candidate_id == candidate_id, ItemScoreRow.requisition_id == req.id))}
    # extras aimed at the gaps in this CV: the lowest-scored rubric skills first, heavier skills first among equals
    for item in sorted(items, key=lambda i: (scores.get(i["skill"], 0), -i["weight"], i["skill"])):
        if len(plan) >= MAX_QUESTIONS - 1:
            break
        extra = next((q for q in _by_skill(item["skill"]) if q["id"] not in used), None)
        if extra and scores.get(item["skill"], 0) <= 1:
            plan.append(PlanItem(question_id=extra["id"], skill=extra["skill"], core=False, diagram=extra["diagram"],
                                 reason=f"gap in this CV: {item['skill']} scored {scores.get(item['skill'], 0)}/3"))
            used.add(extra["id"])
    # one architecture question with a diagram, then fill up to 8 with further questions on the rubric's heaviest skills
    arch = next((q for q in load_questions().values() if q["diagram"] and q["id"] not in used and q["skill"] in ("Resilience", "Explaining an architecture")), None)
    if arch and len(plan) < MAX_QUESTIONS:
        plan.append(PlanItem(question_id=arch["id"], skill=arch["skill"], core=False, diagram=arch["diagram"], reason="architecture question shown with a diagram"))
        used.add(arch["id"])
    for item in sorted(items, key=lambda i: (-i["weight"], i["skill"])):
        for q in _by_skill(item["skill"]):
            if len(plan) >= MAX_QUESTIONS:
                break
            if q["id"] not in used:
                plan.append(PlanItem(question_id=q["id"], skill=q["skill"], core=False, diagram=q["diagram"], reason=f"more depth on {item['skill']}"))
                used.add(q["id"])
    plan = plan[:MAX_QUESTIONS]
    # every must-have skill is asked about at least once (Day 2, prompt 11): a missing one replaces the last extra question
    for item in sorted((i for i in items if i.get("must_have")), key=lambda i: (-i["weight"], i["skill"])):
        if any(p.skill.lower() == item["skill"].lower() for p in plan):
            continue
        q = next(iter(_by_skill(item["skill"], True) or _by_skill(item["skill"])), None)
        if q is None:
            continue
        entry = PlanItem(question_id=q["id"], skill=q["skill"], core=False, diagram=q["diagram"], reason=f"must-have skill: {item['skill']}")
        if len(plan) < MAX_QUESTIONS:
            plan.append(entry)
        else:
            victim = next((k for k in range(len(plan) - 1, -1, -1) if not plan[k].core and not any(i.get("must_have") and i["skill"].lower() == plan[k].skill.lower() for i in items)), None)
            if victim is not None:
                plan[victim] = entry
    return InterviewPlan(candidate_id=candidate_id, items=plan)

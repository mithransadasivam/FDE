"""Requisition agent: its three tools (transcribe, wording_check, save_rubric) and the agent that uses them (Day 1 work, now an agent)."""
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent, register_tool
from app.agents.requisition import generate_job
from app.agents.wording import check_requisition, check_wording
from app.ai import voice
from app.models import Requisition
from app.schemas import JobDraft


class TranscribeArgs(BaseModel):
    audio_path: str
    original_name: str = ""


class WordingArgs(BaseModel):
    text: str
    where: str = "voice note"


class SaveRubricArgs(BaseModel):
    requisition_id: int
    draft: dict
    transcript: str | None = None


@register_tool("transcribe", TranscribeArgs, "Turn the hiring manager's voice note into text")
def t_transcribe(args: TranscribeArgs, ctx: dict) -> str:
    return voice.transcribe(Path(args.audio_path), args.original_name)


@register_tool("wording_check", WordingArgs, "Flag biased wording with a reason and a neutral rewrite")
def t_wording(args: WordingArgs, ctx: dict) -> list[dict]:
    return [f.model_dump() for f in check_wording(args.text, args.where)]


@register_tool("save_rubric", SaveRubricArgs, "Save the generated job description and rubric as a draft (the hiring manager approves it)")
def t_save_rubric(args: SaveRubricArgs, ctx: dict) -> dict:
    db: Session = ctx["db"]
    req = db.get(Requisition, args.requisition_id)
    draft = JobDraft.model_validate(args.draft)  # checked again: the weights must add to 100
    req.job, req.rubric = draft.job.model_dump(), draft.rubric.model_dump()
    req.wording_flags = [f.model_dump() for f in check_requisition(args.transcript or req.transcript, draft.job.as_text())]
    req.status = "GENERATED"
    return {"items": len(draft.rubric.items), "flags": len(req.wording_flags)}


class RequisitionAgent(BaseAgent):
    name = "requisition"

    def transcribe(self, req: Requisition) -> str:
        return self.call("transcribe", audio_path=req.audio_path, original_name=req.audio_name)

    def generate(self, req: Requisition) -> JobDraft:
        """voice-note transcript -> job description and rubric (with the evidence check), saved as a DRAFT for the hiring manager."""
        draft = generate_job(req.transcript)
        self.call("save_rubric", requisition_id=req.id, draft=draft.model_dump(), transcript=req.transcript)
        return draft

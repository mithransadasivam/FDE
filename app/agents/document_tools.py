"""Document agent: its tools (read_pdf, read_docx, read_image, find_duplicate) and the agent that reads a CV through them."""
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.agents.base import BaseAgent, register_tool
from app.agents.document import extract_profile, read_text
from app.duplicates import duplicate_map
from app.models import Candidate
from app.schemas import CandidateProfile


class PathArgs(BaseModel):
    path: str


class DupArgs(BaseModel):
    candidate_id: int


@register_tool("read_pdf", PathArgs, "Read the text of a PDF CV")
def t_read_pdf(args: PathArgs, ctx: dict) -> str:
    return read_text(Path(args.path))


@register_tool("read_docx", PathArgs, "Read the text of a Word CV")
def t_read_docx(args: PathArgs, ctx: dict) -> str:
    return read_text(Path(args.path))


@register_tool("read_image", PathArgs, "Read a scanned CV or a profile screenshot (vision model, or OCR in fake mode)")
def t_read_image(args: PathArgs, ctx: dict) -> str:
    return read_text(Path(args.path))


@register_tool("find_duplicate", DupArgs, "Find other applications with the same e-mail or phone number")
def t_find_duplicate(args: DupArgs, ctx: dict) -> list[int]:
    cand = ctx["db"].get(Candidate, args.candidate_id)
    return duplicate_map(ctx["db"], cand.requisition_id).get(args.candidate_id, [])


class DocumentAgent(BaseAgent):
    name = "document"
    TOOL_BY_SUFFIX = {".pdf": "read_pdf", ".docx": "read_docx", ".png": "read_image", ".jpg": "read_image", ".jpeg": "read_image"}

    def read(self, path: Path) -> str:
        tool = self.TOOL_BY_SUFFIX.get(path.suffix.lower())
        if tool is None:
            from app.ai.llm import ModelError
            raise ModelError(f"Cannot read a {path.suffix or 'file without an extension'} CV")
        return self.call(tool, path=str(path))

    def profile(self, path: Path, cv_format: str, text: str) -> CandidateProfile:
        return extract_profile(path, cv_format, text=text, candidate_id=self.candidate_id)

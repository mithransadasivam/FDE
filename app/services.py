"""Background work: transcription now; CV reading is added in Prompt 11."""
from app.agents.wording import check_wording
from app.ai.voice import transcribe
from app.db import SessionLocal
from app.models import DecisionLog, Requisition


def transcribe_requisition(req_id: int) -> None:
    """Runs after the upload page has already replied (FastAPI background task)."""
    from pathlib import Path

    db = SessionLocal()
    try:
        req = db.get(Requisition, req_id)
        if req is None:
            return
        try:
            req.transcript = transcribe(Path(req.audio_path), req.audio_name)
            req.status = "TRANSCRIBED"
            req.wording_flags = [f.model_dump() for f in check_wording(req.transcript, "voice note")]
            req.error = None
            db.add(DecisionLog(actor="system", action="transcribed", subject=f"requisition:{req.id}",
                               reason=f"{len(req.transcript.split())} words"))
        except Exception as e:  # shown on the page, never swallowed
            req.status = "ERROR"
            req.error = f"Transcription failed: {e}"
            db.add(DecisionLog(actor="system", action="transcription failed", subject=f"requisition:{req.id}", reason=str(e)))
        db.commit()
    finally:
        db.close()

"""The recruiter assistant page and its streaming endpoint (server-sent events)."""
import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.agents import assistant as agent
from app.auth import STAFF
from app.db import get_db
from app.models import User
from app.web.common import render

router = APIRouter(prefix="/assistant")

EXAMPLES = ["Who has run Kubernetes in production?", "Which candidates have Terraform and a certification?",
            "How long are interview recordings kept?", "How many candidates are in each stage?"]


@router.get("")
def assistant_page(request: Request, user: User = Depends(STAFF)):
    return render(request, "assistant.html", user, examples=EXAMPLES)


@router.get("/stream")
def assistant_stream(q: str, user: User = Depends(STAFF), db: Session = Depends(get_db)):
    """Streams an answer as server-sent events: token, source and done. The assistant only reads."""
    def events():
        for e in agent.stream(db, q):
            yield f"event: {e['event']}\ndata: {json.dumps(e['data'])}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

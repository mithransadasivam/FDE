"""Day 9 test helpers: CaseFlow Classic on a real port (the browser needs one), and one agent run."""

import socket
import threading
import time

import uvicorn

from app.agent import runs
from app.agent.models import Approval
from app.integration import tools
from bank.server import app as bank_app
from tests.bankkit import bank, live_identity

_server: dict = {}


def legacy_url() -> str:
    """Start the bank's server once, on a free port, and return CaseFlow Classic's address."""
    if "url" not in _server:
        s = socket.socket()
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
        s.close()
        srv = uvicorn.Server(uvicorn.Config(bank_app, host="127.0.0.1", port=port, log_level="warning"))
        threading.Thread(target=srv.run, daemon=True).start()
        for _ in range(50):
            if srv.started:
                break
            time.sleep(0.1)
        _server["url"] = f"http://127.0.0.1:{port}/legacy"
    return _server["url"]


def approve_all(ap: Approval) -> Approval:
    return ap.model_copy(update={"status": "approved", "decided_by": ap.person, "decided_at": time.time()})


def run_agent(ticket: str, user: str = "tom.reyes", approver=approve_all, prompt: str = "ops_v1", mode: str = "live"):
    tools.set_bank_http(bank())
    runs.LEGACY_URL = legacy_url()
    run = runs.new_run(ticket, user, prompt, mode=mode)
    try:
        return runs.execute_run(run, live_identity(user), approver=approver)
    finally:
        tools.set_bank_http(None)

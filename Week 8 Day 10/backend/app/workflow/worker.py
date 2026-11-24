"""Day 10: the workflow worker (done, not a ticket). npm run dev starts it:  python -m app.workflow.worker

It runs the case workflows; the console's API only starts them, sends them messages and reads their progress. The process you
start is a small supervisor: it starts the worker, and starts it again whenever it dies, as a container platform would. When
the worker starts, DBOS picks up every workflow that was running or waiting, and carries on from its last checkpoint.

  --once     run the worker itself, without the supervisor (the tests use it)
"""

import json
import os
import signal
import subprocess
import sys
import threading
import time

from app import store
from app.config import WORKFLOW_DIR

STATUS = WORKFLOW_DIR / "worker.json"


def _status(**kw) -> None:
    STATUS.parent.mkdir(parents=True, exist_ok=True)
    cur = json.loads(STATUS.read_text()) if STATUS.exists() else {"starts": []}
    cur.update(kw)
    tmp = STATUS.with_suffix(".tmp")
    tmp.write_text(json.dumps(cur, indent=1))
    os.replace(tmp, STATUS)


def run_worker() -> None:
    from dbos import DBOS

    from app.workflow import engine
    from app.workflow import case  # noqa: F401  (registers the workflow and its steps)

    engine.configure()
    DBOS.launch()
    DBOS.register_queue(engine.QUEUE, worker_concurrency=int(os.getenv("FDE_WORKER_CONCURRENCY", "50")))
    cur = json.loads(STATUS.read_text()) if STATUS.exists() else {"starts": []}
    _status(pid=os.getpid(), started_at=time.time(), starts=(cur.get("starts", []) + [time.time()])[-50:], up=True)
    print(f"[worker] up (pid {os.getpid()}): waiting workflows carry on from their last checkpoint", flush=True)

    def beat():
        while True:
            _status(heartbeat=time.time())
            engine.crash_point("now", "*")  # the console's "Crash the worker now" button
            time.sleep(0.5)

    threading.Thread(target=beat, daemon=True).start()
    serve_health()


def serve_health() -> None:
    """GET /health on FDE_WORKER_PORT (8300): the end-to-end tests wait for it before they start."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

    class H(BaseHTTPRequestHandler):
        def do_GET(self):
            body = json.dumps({"status": "ok", "pid": os.getpid()}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):
            pass

    ThreadingHTTPServer.allow_reuse_address = True
    ThreadingHTTPServer(("127.0.0.1", int(os.getenv("FDE_WORKER_PORT", "8300"))), H).serve_forever()


def supervise() -> None:
    print("[worker] supervisor: starting the workflow worker", flush=True)
    child: list[subprocess.Popen] = []

    def stop(*_):
        for c in child:
            c.terminate()
        sys.exit(0)

    signal.signal(signal.SIGTERM, stop)
    while True:
        p = subprocess.Popen([sys.executable, "-m", "app.workflow.worker", "--once"])
        child[:] = [p]
        code = p.wait()
        _status(up=False, last_exit=code, last_exit_at=time.time())
        print(f"[worker] the worker stopped (exit {code}): starting it again in 1 s", flush=True)
        time.sleep(1)


if __name__ == "__main__":
    from app.config import WORKFLOW_DB

    if os.getenv("FDE_RESET_ON_START") == "1" and "--once" not in sys.argv:  # only the end-to-end tests set this
        for p in (WORKFLOW_DB, WORKFLOW_DB.with_name(WORKFLOW_DB.name + "-wal"), WORKFLOW_DB.with_name(WORKFLOW_DB.name + "-shm")):
            p.unlink(missing_ok=True)
    store.path("workflow")  # make sure the folder exists
    if "--once" in sys.argv:
        run_worker()
    else:
        try:
            supervise()
        except KeyboardInterrupt:
            pass

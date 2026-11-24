"""Day 10 test helpers: run a workflow in a worker process (tests/wf_child.py), crash it, start it again, and read what it did."""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from dbos import DBOSClient

DAY = 0.4  # one course day, in seconds, in these tests
CHILD = Path(__file__).resolve().parent / "wf_child.py"


class Worker:
    """One workflow, in a worker process that can crash and be started again. Times are in course days from the start."""

    def __init__(self, workflow: str, day: float = DAY, **env):
        self.day = day
        self.dir = Path(tempfile.mkdtemp(prefix="fde-wf-"))
        self.workflow, self.id = workflow, f"{workflow}-1"
        self.env = {**os.environ, "FDE_WORKFLOW_DB": str(self.dir / "dbos.sqlite"), "FDE_ENGAGEMENT_DIR": str(self.dir / "engagement"),
                    "FDE_DAY_SECONDS": str(day), "WF_CALLS": str(self.dir / "calls.jsonl"), "WF_RESULT": str(self.dir / "result.json"),
                    "WF_CTRL": str(self.dir / "ctrl.json"), **{k: str(v) for k, v in env.items()}}
        self.proc: subprocess.Popen | None = None
        self.t0 = time.time()

    def start(self, crash_after_days: float | None = None) -> "Worker":
        args = [sys.executable, str(CHILD), "run", self.workflow, self.id]
        if crash_after_days is not None:
            args += ["--crash-after", str(crash_after_days * self.day)]
        self.proc = subprocess.Popen(args, env=self.env, cwd=str(CHILD.parents[1]), stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return self

    def wait(self, days: float = 20) -> int:
        try:
            return self.proc.wait(timeout=days * self.day + 15)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            raise AssertionError(f"The workflow did not end within {days} course days")

    def _first(self) -> float:
        """Day 0 is the workflow's first step (the worker process takes a moment to start)."""
        for _ in range(400):
            rows = self._raw()
            if rows:
                return rows[0]["t"]
            time.sleep(0.025)
        raise AssertionError("The workflow never called its first step")

    def at(self, day: float) -> None:
        """Wait until `day` course days after the workflow's first step."""
        time.sleep(max(0.0, self._first() + day * self.day - time.time()))

    def control(self, **kw) -> None:
        p = Path(self.env["WF_CTRL"])
        cur = json.loads(p.read_text()) if p.exists() else {}
        p.write_text(json.dumps({**cur, **kw}))

    def send(self, topic: str, message) -> None:
        for _ in range(100):
            if Path(self.env["FDE_WORKFLOW_DB"]).exists():
                break
            time.sleep(0.05)
        import sqlalchemy as sa

        c = DBOSClient(system_database_engine=sa.create_engine(f"sqlite:///{self.env['FDE_WORKFLOW_DB']}", connect_args={"timeout": 30}))
        c.send(self.id, message, topic)
        c.destroy()

    def decide(self, status: str, approval_id: str = "A-1") -> None:
        """The person decides: the decision is sent to the workflow (and seen by the in-memory wait of the starter)."""
        self.control(decision=status)
        self.send(approval_id, {"approval_id": approval_id, "status": status, "decided_by": "tom.reyes", "note": ""})

    def _raw(self) -> list[dict]:
        p = Path(self.env["WF_CALLS"])
        return [json.loads(x) for x in p.read_text().splitlines()] if p.exists() else []

    def calls(self) -> list[dict]:
        rows = self._raw()
        t0 = rows[0]["t"] if rows else self.t0
        return [{**r, "day": round((r["t"] - t0) / self.day, 2)} for r in rows]

    def launches(self) -> list[float]:
        """When each worker process was up, in course days from the first step."""
        p = Path(self.env["WF_CALLS"]).with_name("launches.jsonl")
        rows = self._raw()
        t0 = rows[0]["t"] if rows else self.t0
        return [round((json.loads(x)["t"] - t0) / self.day, 2) for x in p.read_text().splitlines()] if p.exists() else []

    def names(self) -> list[str]:
        return [c["step"] for c in self.calls()]

    def day_of(self, step: str) -> float | None:
        return next((c["day"] for c in self.calls() if c["step"] == step), None)

    def result(self):
        p = Path(self.env["WF_RESULT"])
        return json.loads(p.read_text())["result"] if p.exists() else "no result"

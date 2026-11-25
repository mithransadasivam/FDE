"""Ticket ENG-1002: chase the applicant on a clock that survives a crash. Run: python -m pytest -q tests/test_chase.py

Each test runs chase() in a real worker process with the steps replaced by fakes (tests/wf_child.py). Days are course days.
"""

import inspect

from app.workflow import chase
from tests.wfkit import Worker


def _doc(w: Worker, day: float) -> None:
    w.at(day)
    doc = {"ticket_id": "KX-1001", "doc_id": "D-90001", "doc_type": "utility_bill"}
    w.control(doc=doc)          # what the document store now holds
    w.send("documents", doc)    # and the webhook's message to the workflow


def test_a_reply_before_the_reminder_ends_the_chase():
    w = Worker("t_chase").start()
    _doc(w, 1)
    assert w.wait() == 0
    assert "send_reminder" not in w.names() and "escalate" not in w.names()
    assert w.names()[0] == "send_request"
    assert w.result()["doc_id"] == "D-90001"
    assert w.day_of("received") <= 1.8, "Return as soon as the document arrives"


def test_a_reply_after_the_reminder():
    w = Worker("t_chase").start()
    _doc(w, 4)
    assert w.wait() == 0
    assert 2.6 <= w.day_of("send_reminder") <= 3.8, "The reminder goes after policy['reminder_after_days'] (3)"
    assert "escalate" not in w.names()
    assert w.result()["doc_id"] == "D-90001"


def test_no_reply_escalates_on_day_7():
    w = Worker("t_chase").start()
    assert w.wait() == 0
    assert 2.6 <= w.day_of("send_reminder") <= 3.8
    assert 6.6 <= w.day_of("escalate") <= 7.9, "Escalate after policy['escalate_after_days'] (7), counted from the request"
    assert w.result() is None


def test_the_rule_comes_from_the_policy():
    w = Worker("t_chase", WF_REMIND=2, WF_ESCALATE=4).start()
    assert w.wait() == 0
    assert 1.6 <= w.day_of("send_reminder") <= 2.8
    assert 3.6 <= w.day_of("escalate") <= 4.9


def test_a_crash_does_not_restart_the_clock():
    w = Worker("t_chase", day=1.0).start(crash_after_days=2)
    assert w.wait() == 1   # the worker died on day 2 of the wait
    w.start()
    w.wait()
    back = w.launches()[-1]  # when the worker was up again (starting a process takes a moment)
    assert w.names().count("send_request") == 1
    due = max(3, back)
    assert w.day_of("send_reminder") <= due + 1.5, \
        (f"The worker was back on day {back} and the reminder went on day {w.day_of('send_reminder')}: "
         "after a crash the deadline must still be 3 days after the request, not 3 days after the restart")
    assert w.day_of("escalate") <= max(7, back) + 1.5


def test_chase_never_reads_the_clock_or_sleeps():
    code = inspect.getsource(chase.chase).split('"""', 2)[-1]
    assert "time." not in code, "Workflow code runs again after a crash: wait with DBOS.recv(topic, timeout_seconds), never time.time() or time.sleep()"
    assert "DBOS.recv(" in code


def test_a_reply_is_noted_once():
    w = Worker("t_chase").start()
    _doc(w, 1)
    w.wait()
    assert w.names().count("received") == 1

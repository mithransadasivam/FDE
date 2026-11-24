"""Ticket ENG-1001: one round as checkpoints: propose, wait durably for the person, write. Run: python -m pytest -q tests/test_case.py

Each test runs work_round() in a real worker process with the steps replaced by fakes (tests/wf_child.py). Some tests crash
the worker on purpose and start it again, as npm run dev does.
"""

from tests.wfkit import Worker


def test_approved_proposes_waits_then_writes():
    w = Worker("t_round").start()
    w.at(1)
    w.decide("approved")
    assert w.wait() == 0
    assert w.names() == ["propose", "apply"], "Propose (a step), wait for the decision, then apply (a step)"
    assert w.result()["end"] == "recorded"
    assert w.result()["reference"] == "OUT-1"


def test_rejected_writes_nothing():
    w = Worker("t_round").start()
    w.at(1)
    w.decide("rejected")
    assert w.wait() == 0
    assert "apply" not in w.names()
    assert w.result()["end"] == "rejected"


def test_no_decision_expires_after_the_policy_days():
    w = Worker("t_round", WF_EXPIRE=2).start()
    assert w.wait() == 0
    assert w.names() == ["propose", "expire"], "No decision in time: steps.expire(), and nothing is written"
    assert w.result()["end"] == "expired"
    assert 1.8 <= w.day_of("expire") <= 3.5, "The wait lasts policy['approval_expires_after_days'] course days (here 2)"


def test_an_agent_that_never_proposes_ends_the_round():
    w = Worker("t_round").start()
    w.control(agent_ends="stopped")
    assert w.wait() == 0
    assert w.names() == ["propose"]
    assert w.result()["end"] == "stopped"


def test_a_crash_while_waiting_does_not_run_the_agent_again():
    w = Worker("t_round").start(crash_after_days=1)
    assert w.wait() == 1  # the worker died while the workflow waited for Tom
    w.start()             # npm run dev starts it again
    w.at(2.5)
    w.decide("approved")
    assert w.wait() == 0
    agent = [n for n in w.names() if n in ("propose", "agent_round")]
    assert agent == ["propose"], f"The agent ran {len(agent)} times: a crash while waiting must never make it work the case again"
    assert w.names().count("apply") == 1
    assert w.result()["end"] == "recorded"


def test_the_decision_can_come_after_the_crash():
    w = Worker("t_round").start(crash_after_days=0.6)
    w.wait()
    w.decide("approved")  # Tom decides while the worker is down: the decision waits in the database
    w.start()
    assert w.wait() == 0
    assert w.result()["end"] == "recorded"
    assert w.names() == ["propose", "apply"]


def test_the_write_is_its_own_step():
    w = Worker("t_round").start(crash_after_days=1)
    w.wait()
    w.start()
    w.at(1.5)
    w.decide("approved")
    w.wait()
    assert "agent_round" not in w.names(), "Split the round: steps.propose(), DBOS.recv(), steps.apply(); not one steps.agent_round()"

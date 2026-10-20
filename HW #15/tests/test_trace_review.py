"""Day 12, Activity 4: reviewing a trace for problems."""

import json

from app.trace_review import trace_problems


def act(name, result):
    return {"name": name, "arguments": "{}", "result": json.dumps(result)}


def test_a_clean_run_has_no_problems():
    run = {
        "stopped": "answer",
        "answer": "Renew the certificate.\nSources: KB-1101, find_tickets",
        "trace": [
            {"step": 1, "thought": "", "actions": [act("web_search", {"results": []})]},
            {"step": 2, "thought": "", "actions": []},
        ],
    }
    assert trace_problems(run) == []


def test_step_limit_and_repeats_are_reported():
    assert trace_problems(
        {
            "stopped": "step_limit",
            "answer": "x",
            "trace": [
                {"step": 1, "thought": "", "actions": [act("calculate", {"result": 1})]}
            ],
        }
    ) == ["hit the step limit without an answer"]
    assert trace_problems(
        {
            "stopped": "repeated",
            "answer": "x",
            "trace": [
                {"step": 1, "thought": "", "actions": [act("calculate", {"result": 1})]}
            ],
        }
    ) == ["repeated the same tool call"]


def test_tool_errors_are_listed_by_step():
    run = {
        "stopped": "answer",
        "answer": "Done.\nSources: find_tickets",
        "trace": [
            {
                "step": 1,
                "thought": "",
                "actions": [act("get_ticket", {"error": "no ticket"})],
            },
            {
                "step": 2,
                "thought": "",
                "actions": [
                    act("find_tickets", {"count": 4}),
                    act("read_article", {"error": "no article"}),
                ],
            },
        ],
    }
    assert trace_problems(run) == [
        "step 1: get_ticket returned an error",
        "step 2: read_article returned an error",
    ]


def test_no_tools_and_no_sources():
    run = {
        "stopped": "answer",
        "answer": "VPN-809 is a certificate problem.",
        "trace": [{"step": 1, "thought": "", "actions": []}],
    }
    assert trace_problems(run) == [
        "answered without using any tool",
        "the answer lists no sources",
    ]


def test_relying_on_an_old_article_is_reported_only_if_the_answer_uses_it():
    old = act(
        "read_article", {"id": "KB-0412", "published": "2019-06-11", "text": "..."}
    )
    new = act(
        "read_article", {"id": "KB-1101", "published": "2026-03-02", "text": "..."}
    )
    trace = [{"step": 1, "thought": "", "actions": [old, new]}]
    used = {
        "stopped": "answer",
        "answer": "Reset the clock.\nSources: KB-0412, KB-1101",
        "trace": trace,
    }
    unused = {
        "stopped": "answer",
        "answer": "Renew it.\nSources: KB-1101",
        "trace": trace,
    }
    assert trace_problems(used) == [
        "relied on an old article (KB-0412, published 2019-06-11)"
    ]
    assert trace_problems(unused) == []

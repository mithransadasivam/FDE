"""Day 8: checks on a chatbot answer that plain code can do: fast, free and always the same.

citations() and check_behaviour() are done.
Activity 1: fill in check_citations(). Check it with tests/test_answer_checks.py.
"""

import re

CITATION = re.compile(r"\[(\d+)\]")


def citations(answer: str) -> list[int]:
    """Every citation number in the answer, in order: "a [1] b [3]" gives [1, 3]."""
    return [int(n) for n in CITATION.findall(answer)]


def check_behaviour(declined: bool, expected_behaviour: str) -> list[str]:
    """Did the bot answer or decline as the test set expects? Returns a list of problems."""
    got = "decline" if declined else "answer"
    if got != expected_behaviour:
        return [f"expected to {expected_behaviour}, but it chose to {got}"]
    return []


def check_citations(answer: str, n_sources: int, declined: bool) -> list[str]:
    """TODO (Activity 1): check the citations in one answer. Returns a list of problems.

    Rules (tests/test_answer_checks.py checks each one):
    - use citations(answer) to find the citation numbers
    - a declined answer must contain no citations:
      problem "declined answer contains citations"
    - an answer that was not declined must contain at least one citation:
      problem "no citations"
    - every citation number must be between 1 and n_sources: for each one that isn't,
      problem f"cites [{n}] but there are only {n_sources} sources" (once per number, in order)
    - return [] when there is no problem
    """
    numbers = citations(answer)
    if declined:
        return ["declined answer contains citations"] if numbers else []
    if not numbers:
        return ["no citations"]
    return [
        f"cites [{n}] but there are only {n_sources} sources"
        for n in dict.fromkeys(numbers)
        if not 1 <= n <= n_sources
    ]

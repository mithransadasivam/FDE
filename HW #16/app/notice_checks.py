"""Day 14: automatic checks on a finished notice, used to compare the team with a single agent.

Activity 4: fill in check_notice(). Check it with tests/test_check_notice.py.
"""

import re

MAX_WORDS = 180
# Staff usernames look like t.sato or a.mensah.
USERNAME = re.compile(r"\b[a-z]\.[a-z]{3,}\b")


def check_notice(
    notice: dict, must_mention: list[str], max_words: int = MAX_WORDS
) -> list[str]:
    """List what is wrong with a notice. An empty list means no problem found.

    Rules, in this order (tests/test_check_notice.py checks each one):
    1. text = title + body + every action, joined with spaces
       for each term in must_mention, in order, not found in text (ignore upper/lower case):
           "missing: <term>"
    2. words = len(body.split()); more than max_words:    f"too long: {words} words (limit {max_words})"
    3. no actions (missing or empty list):                "no action for staff"
    4. no sources (missing or empty list):                "no sources"
    5. for each different match of USERNAME in text, in order of first appearance:
           "names a person: <match>"
    """
    text = " ".join(
        [notice.get("title", ""), notice.get("body", ""), *notice.get("actions", [])]
    )
    problems = [f"missing: {t}" for t in must_mention if t.lower() not in text.lower()]
    words = len(notice.get("body", "").split())
    if words > max_words:
        problems.append(f"too long: {words} words (limit {max_words})")
    if not notice.get("actions"):
        problems.append("no action for staff")
    if not notice.get("sources"):
        problems.append("no sources")
    for name in dict.fromkeys(USERNAME.findall(text)):
        problems.append(f"names a person: {name}")
    return problems

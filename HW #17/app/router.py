"""Day 16: model routing. Simple questions go to a small, cheap model; anything harder, or any
question the retrieval was unsure about, goes to the large hosted model.

The rule is code, not a model: it costs nothing, takes no time, and a test can check it.

Done: the settings and the word lists.
Activity 4: fill in choose_route(). Check it with tests/test_router.py.
"""

import os
import re  # noqa: F401  (you need it in Activity 4)

from dotenv import load_dotenv

load_dotenv()
MAX_SIMPLE_WORDS = int(os.getenv("ROUTE_MAX_WORDS", "15"))
MIN_SIMPLE_SCORE = float(os.getenv("ROUTE_MIN_SCORE", "0.6"))
# Words that usually mean reasoning, comparing or several steps: worth the large model
HARD_WORDS = {
    "why",
    "compare",
    "difference",
    "explain",
    "should",
    "versus",
    "vs",
    "both",
    "best",
    "recommend",
    "if",
    "unless",
    "except",
    "steps",
}


def choose_route(question: str, kept: list[dict], small_available: bool = True) -> dict:
    """TODO (Activity 4): pick "small" or "large" for one question, and say why.

    kept are the chunks retrieval kept for this question, each with a "score".
    Rules, checked in this order (tests/test_router.py checks each one):
    1. small_available is False:                       {"route": "large", "reason": "no small model"}
    2. words = re.findall(r"[a-z0-9-]+", question.lower())
       more than MAX_SIMPLE_WORDS words:                {"route": "large", "reason": "long question"}
    3. more than one "?" in the question:              {"route": "large", "reason": "several questions"}
    4. any word in HARD_WORDS:                          {"route": "large", "reason": "needs reasoning: <the first such word>"}
    5. the best kept chunk's score is below MIN_SIMPLE_SCORE:
                                                        {"route": "large", "reason": "unsure retrieval"}
    6. otherwise:                                       {"route": "small", "reason": "simple question"}
    (No kept chunks never reaches here: the service declines without calling a model.)
    """
    if not small_available:
        return {"route": "large", "reason": "no small model"}
    words = re.findall(r"[a-z0-9-]+", question.lower())
    if len(words) > MAX_SIMPLE_WORDS:
        return {"route": "large", "reason": "long question"}
    if question.count("?") > 1:
        return {"route": "large", "reason": "several questions"}
    for word in words:
        if word in HARD_WORDS:
            return {"route": "large", "reason": f"needs reasoning: {word}"}
    best = max((c.get("score", 0) for c in kept), default=0)
    if best < MIN_SIMPLE_SCORE:
        return {"route": "large", "reason": "unsure retrieval"}
    return {"route": "small", "reason": "simple question"}

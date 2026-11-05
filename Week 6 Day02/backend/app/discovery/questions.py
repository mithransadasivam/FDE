"""Activity 1: draft a discovery question plan from the client brief."""

from app.discovery.models import Question, QuestionPlan
from app.llm import ask_json

QUESTION_PROMPT = """You are preparing a forward deployed engineer for a first discovery session with a client.
From the client brief, draft 15 questions to ask, spread across five areas:
- goals: what the client wants and why now
- process: how the work is done today, step by step, and where time goes
- data: what data and systems exist, and who can give access
- risk: regulation, approvals, security, and what must never happen
- success: how the sponsor and the users will judge success, with numbers

Good discovery questions are open, ask about the last real example, and ask for numbers.
Avoid questions the brief already answers. Avoid proposing solutions.

Reply with JSON only, in this shape:
{"questions": [{"area": "process", "text": "...", "why": "what the answer will tell us"}]}"""


def draft_questions(brief_markdown: str, client) -> list[Question]:
    plan = ask_json(client, QUESTION_PROMPT, brief_markdown, QuestionPlan, task="questions")
    return [Question(id=f"Q{i:02d}", **q.model_dump()) for i, q in enumerate(plan.questions, 1)]

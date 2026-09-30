"""A three-step chain: meeting transcript -> action items -> follow-up email (Day 4, Activity 3).

Step 1 extract:     transcript -> JSON        (the model, temperature 0)
Step 2 validate:    check the JSON            (plain Python, never the model)
Step 3 write_email: JSON -> email             (the model never sees the transcript)

Your job in Activity 3: fill in the three TODO functions. Everything else is done.
Run from the repository root:
    python -m app.chain
    python -m app.chain --transcript data/Day04_Slide23_transcript_missing_owner.txt
"""

import argparse
import json
import os

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
MODEL = os.getenv("LLM_MODEL", "anthropic/claude-haiku-4.5")

EXTRACT = """Extract from the meeting transcript below.
Return only JSON, no prose, in exactly this shape:
{"decisions": ["..."],
 "actions": [{"owner": "...", "task": "...", "due": "a day or null"}],
 "open_questions": ["..."]}
Use only what the transcript says. If an action has no clear owner, set owner to null.

Transcript:
{transcript}"""

WRITE = """Write a short follow-up email from this JSON only.
Sections: Decisions, Actions (with owners and due dates), Open questions.
Add no facts that are not in the JSON.

{data}"""


def get_client() -> OpenAI:
    key = os.getenv("OPENROUTER_API_KEY")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set; add it to .env")
    return OpenAI(base_url="https://openrouter.ai/api/v1", api_key=key)


def ask(client, prompt, model=MODEL, temperature=0.2, system=None):
    """Send one prompt and return the reply text."""
    messages = [{"role": "system", "content": system}] if system else []
    messages.append({"role": "user", "content": prompt})
    r = client.chat.completions.create(model=model, temperature=temperature, messages=messages)
    return r.choices[0].message.content or ""


def extract(transcript, client, model=MODEL):
    """Step 1: send EXTRACT at temperature 0, return parsed JSON."""
    raise NotImplementedError("TODO")


def validate(data):
    """Step 2: plain Python. Every action needs an owner and a task."""
    raise NotImplementedError("TODO")


def write_email(data, client, model=MODEL):
    """Step 3: send WRITE with the JSON only, return the email."""
    raise NotImplementedError("TODO")


def main():
    ap = argparse.ArgumentParser(description="Transcript to follow-up email")
    ap.add_argument("--transcript", default="data/Day04_Slide23_transcript.txt")
    args = ap.parse_args()
    with open(args.transcript, encoding="utf-8") as f:
        transcript = f.read()
    client = get_client()
    data = validate(extract(transcript, client))
    print(json.dumps(data, indent=2))
    print("\n" + write_email(data, client))


if __name__ == "__main__":
    main()

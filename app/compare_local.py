"""Day 3, Activity 3: the same prompts through a hosted and a local model.

Ready to run, nothing to write. Ollama must be running with LOCAL_MODEL pulled.
Run: python -m app.compare_local
"""

import time

from app.clients import HOSTED_MODEL, LOCAL_MODEL, hosted_client, local_client

PROMPTS = [
    "Summarise in one sentence: the nightly ETL job failed twice with a database timeout.",
    (
        "A batch job must not run after 06:00 because a report reads its tables at 06:30. "
        "It is 05:50 and the job takes 25 minutes. Should I start it? Explain."
    ),
]


def timed_ask(client, model, prompt):
    start = time.perf_counter()
    r = client.chat.completions.create(
        model=model, messages=[{"role": "user", "content": prompt}]
    )
    return time.perf_counter() - start, (r.choices[0].message.content or "")


def main() -> None:
    backends = {
        "hosted": (hosted_client(), HOSTED_MODEL),
        "local": (local_client(), LOCAL_MODEL),
    }
    for i, prompt in enumerate(PROMPTS, 1):
        print(f"\nPrompt {i}: {prompt[:60]}...")
        for name, (client, model) in backends.items():
            secs, answer = timed_ask(client, model, prompt)
            print(f"  {name:7} {secs:5.1f}s  {answer[:100]!r}")


if __name__ == "__main__":
    main()

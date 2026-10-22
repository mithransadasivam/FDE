"""Day 15: send questions to the running chatbot service, like users would, and print each reply.

python -m scripts.send_questions                                  (the class questions, once)
python -m scripts.send_questions --repeat 3                       (each question three times)
python -m scripts.send_questions --url http://localhost:8000 --questions data/my_questions.csv

Then open http://localhost:8000/dashboard for the numbers, and Phoenix (http://localhost:6006)
for one trace per question.
"""

import argparse
import csv
import time

import httpx

QUESTIONS = "data/Day15_Slide20_questions.csv"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--url", default="http://localhost:8000")
    p.add_argument("--questions", default=QUESTIONS)
    p.add_argument("--repeat", type=int, default=1)
    a = p.parse_args()
    with open(a.questions, newline="", encoding="utf-8") as f:
        questions = [row["question"] for row in csv.DictReader(f)]
    ok = failed = fallbacks = 0
    started = time.perf_counter()
    with httpx.Client(base_url=a.url, timeout=120) as client:
        for _ in range(a.repeat):
            for q in questions:
                r = client.post("/ask", json={"question": q})
                if r.status_code != 200:
                    failed += 1
                    print(
                        f"{r.status_code}  {q[:55]:55}  {r.json().get('detail', '')[:60]}"
                    )
                    continue
                body = r.json()
                ok += 1
                fallbacks += body["fallback"]
                model = "declined" if body["declined"] else body["model"]
                flag = "  FALLBACK" if body["fallback"] else ""
                print(f"200  {q[:55]:55}  {body['seconds']:6.2f}s  {model}{flag}")
    print(
        f"\n{ok} answered, {failed} failed, {fallbacks} by the fallback model, "
        f"in {time.perf_counter() - started:.1f} seconds. Dashboard: {a.url}/dashboard"
    )


if __name__ == "__main__":
    main()

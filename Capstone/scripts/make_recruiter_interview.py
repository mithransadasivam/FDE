"""Makes a recruiter-led practice interview for the copilot (Day 3, prompt 4).

    python -m scripts.make_recruiter_interview --candidate 5

Writes storage/practice/<id>/practice.wav (two voices) and practice.json (every line with speaker, text, start and end seconds, and which planned moment it is).
The script is generated from the candidate's blind profile and the job's rubric, and contains five planned moments for the copilot to catch: a good technical answer,
a vague answer, a question that must not be asked, a claim that conflicts with the CV, and a behavioural answer with a full example. It is marked SAMPLE: fictional.
"""
import argparse

from app.db import SessionLocal, init_db
from app.models import Candidate
from app.practice import make_practice


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidate", type=int, required=True)
    ap.add_argument("--silent", action="store_true", help="skip the text-to-speech voices (writes silent audio of the right length)")
    args = ap.parse_args()
    init_db()
    with SessionLocal() as db:
        cand = db.get(Candidate, args.candidate)
        if cand is None:
            print(f"There is no candidate {args.candidate}.")
            return 1
        if cand.stage not in ("SHORTLISTED", "AI_INTERVIEW", "HUMAN_INTERVIEW", "DECISION"):
            print(f"Candidate {cand.id} is in {cand.stage}: practice interviews are made for shortlisted candidates.")
            return 1
        doc = make_practice(db, cand, speak_real=not args.silent)
    print(f"SAMPLE: fictional. Practice interview {doc['id']} for candidate #{cand.id}: {len(doc['lines'])} lines, {doc['duration_s']} seconds.")
    print(f"  audio: storage/practice/{cand.id}/practice.wav   timeline: storage/practice/{cand.id}/practice.json\n")
    for m, info in doc["moments"].items():
        what = {"good_technical_answer": f"question {info.get('question_id')}", "vague_answer": f"question {info.get('question_id')}",
                "forbidden_question": info.get("category"), "cv_conflict": f"claims {info.get('claim')}; the CV shows {info.get('cv_years')} years in all",
                "behavioural_answer": "full example (situation, task, action, result)"}[m]
        print(f"  moment {m:<22} line {info['line']:>2}  {info['start']:>6.1f}s - {info['end']:>6.1f}s   {what}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Rebuilds every fictional file added to starter_kit/ for Days 2-4 (question bank, diagrams, policy, calendar, red-team library, governance templates,
extra CVs, bias variants, ranking keys, recorded answers, recorded interviews, accent set). Takes a couple of minutes and needs the Windows speech engine
for the audio (the other parts run anywhere).

    python -m scripts.make_fictional_kit            # everything
    python -m scripts.make_fictional_kit --no-audio # everything except the speech files
"""
import os
import sys

os.environ.setdefault("FAKE_MODELS", "1")


def main() -> int:
    from scripts.kit import build_banks, build_cvs, build_docs
    build_banks.main()
    build_docs.main()
    build_cvs.main()
    if "--no-audio" not in sys.argv:
        from scripts.kit import build_audio
        build_audio.main()
    print("Fictional starter-kit additions rebuilt. See starter_kit/FICTIONAL_ADDITIONS.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

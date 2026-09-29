# Day 3 · Student files

Copy these folders into the root of your course repository, `ai-engineer-course/`, keeping the folder names: `app/`, `tests/`, `data/`, `logs/`. Nothing in them overwrites your earlier work.

Then open `.env.example` and copy the three new settings (`INPUT_PRICE`, `OUTPUT_PRICE`, `LOCAL_MODEL`) into your own `.env`.

Run every command from the repository root.

## Lecture deck

| File | Slide | What it is for |
|---|---|---|
| `.env.example` | 5 | The three new settings for today |
| `app/clients.py` | 5 | Ready-made hosted and local clients, used by the other files. Nothing to change |
| `app/chat_once.py` | 16 | Activity 2: fill in the two TODO functions |
| `tests/test_chat_once.py` | 16 | Tells you when Activity 2 is done: `pytest -q tests/test_chat_once.py` |
| `app/compare_local.py` | 21 | Activity 3: ready to run, `python -m app.compare_local` |
| `app/chatbot.py` | 27 | Activity 4: fill in the one TODO function, `ask()` |
| `tests/test_chatbot.py` | 27 | Tells you when Activity 4 is done: `pytest -q tests/test_chatbot.py` |
| `tests/fakes.py` | 27 | A fake model client the tests use, so no test calls a real API |
| `logs/Day03_Activity_Log.md` | All activities | Record your results; submit it with your homework |

Activity 1 (slide 10) needs no files: it uses the OpenRouter models page.

## Homework deck

| File | Slide | What it is for |
|---|---|---|
| `data/Day03_HW_Slide04_prompts_course.txt` | 4 | Ten IT prompts, only if you cannot use prompts from your own work for Task 2 |

The code files keep plain names because Python imports them by name.

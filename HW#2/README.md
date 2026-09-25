# HW #2

Work is on the repo root; run `pytest -q` from the repo root.

## Task 1: logging in `ask_llm`
- Code: `app/llm_helper.py`
- Tests: `tests/test_llm_helper.py`
- Logs model, latency (ms) and total tokens at INFO. On API failure logs the
  model at ERROR and re-raises. Never logs the prompt, reply or API key.

## Task 3: fix a colleague's script
- Code: `tools/log_parser.py`
- Data: `data/sample.log` (includes a blank line)
- Test: `tests/test_log_parser.py` expects `{"INFO": 1, "WARNING": 1, "ERROR": 2}`
- Bug 1: blank line -> `IndexError` from `line.split()[1]`. Fix: skip lines with fewer than two words.
- Bug 2: `counts[level] =+ 1` assigns +1 instead of adding, so ERROR counted 1, not 2. Fix: `+= 1`.

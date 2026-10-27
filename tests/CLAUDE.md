# tests (Role D)

- Every test uses fake models (`FAKE_MODELS=1`, set in `conftest.py` before the app is imported) and a temporary database. **No test calls a real model.**
- Use the `platform` fixture (a published job, a hiring manager, a recruiter and a signed-out candidate) rather than building one by hand. After a request that changes the database, `db.expire_all()` before reading.
- Do not leave a write uncommitted in the `db` fixture while a request runs (SQLite has one writer).
- Never change a test to make it pass. If a test fails, fix the code, or ask whether the test's idea of "right" is wrong and say why.
- Browser tests (`test_browser.py`) start the real server in a thread and use recorded audio fixtures; they need `python -m playwright install chromium` once.
- A new rule needs a test that fails when the rule is broken (see `test_supervisor.py` for the pattern, including a source scan that fails if anything sets a stage directly).

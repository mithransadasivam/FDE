"""The bank's systems, on one local server: python -m bank.server --port 8100"""

import argparse
import os

import shutil

from fastapi import FastAPI

from bank import contact, core, idp, legacy, systems

if os.getenv("FDE_RESET_ON_START") == "1" and core.STATE.exists():
    shutil.rmtree(core.STATE)  # only the end-to-end tests set this, on their own folder

app = FastAPI(title="Kestrelmoor Bank systems (course stand-in)")
app.include_router(idp.router)
app.include_router(systems.router)
app.include_router(legacy.router)
app.include_router(legacy.course)
app.include_router(contact.router)  # Day 10: the applicant contact gateway
app.include_router(contact.course)


@app.get("/health")
def health():
    return {"status": "ok", "systems": ["sign-in", "crm", "kyc-exceptions", "documents", "slack", "caseflow-classic", "contact"]}


if __name__ == "__main__":
    import uvicorn

    contact.start_applicants()  # Day 10, course stand-in: applicants who reply on schedule
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=int(os.getenv("FDE_BANK_PORT", "8100")))
    uvicorn.run(app, host="127.0.0.1", port=ap.parse_args().port)

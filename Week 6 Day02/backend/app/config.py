"""Where the console finds the client's files and keeps its own work.

    data/         files from the client and the course (read-only for the app)
    engagement/   everything the team produces during the engagement (JSON and Markdown)
    docs/         documents you hand to the client, such as DISCOVERY_SUMMARY.md
"""

import os
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA_DIR = REPO / "data"
ENGAGEMENT_DIR = Path(os.getenv("FDE_ENGAGEMENT_DIR", REPO / "engagement")).resolve()
DOCS_DIR = Path(os.getenv("FDE_DOCS_DIR", REPO / "docs")).resolve()

BRIEF_FILE = DATA_DIR / "Day01_Slide10_client_brief.md"
TRANSCRIPT_FILE = DATA_DIR / "Day01_Slide21_discovery_transcript.md"
USE_CASES_FILE = DATA_DIR / "Day01_Slide26_use_case_candidates.csv"
CRITERIA_DRAFT_FILE = DATA_DIR / "Day01_Slide26_success_criteria_draft.json"

# Day 2: solution design
SAMPLE_FILE = DATA_DIR / "Day02_Slide10_caseflow_poa_sample.csv"
DICTIONARY_FILE = DATA_DIR / "Day02_Slide10_data_dictionary.csv"
PRICE_FILE = DATA_DIR / "Day02_Slide21_price_sheet.csv"
ARCHITECTURE_DIR = Path(os.getenv("FDE_ARCH_DIR", REPO / "docs" / "architecture")).resolve()
ADR_DIR = DOCS_DIR / "adr"

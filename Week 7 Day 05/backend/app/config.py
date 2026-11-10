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

# Day 3: the UC1 prototype
DOCUMENTS_DIR = DATA_DIR / "Day03_Slide15_documents"
APPLICATIONS_FILE = DATA_DIR / "Day03_Slide15_applications.csv"
ISSUERS_FILE = DATA_DIR / "Day03_Slide15_approved_issuers.csv"
LABELS_FILE = DATA_DIR / "Day03_Slide26_tom_labels.csv"

# Day 4: evaluation with the client's expert
DOCUMENTS_DIR_4 = DATA_DIR / "Day04_Slide10_documents"
EVAL_LABELS_FILE = DATA_DIR / "Day04_Slide10_eval_labels.csv"
EVAL_APPLICATIONS_FILE = DATA_DIR / "Day04_Slide10_applications.csv"
LABELLING_SAMPLE_FILE = DATA_DIR / "Day04_Slide15_labelling_sample.csv"
TOM_SAMPLE_LABELS_FILE = DATA_DIR / "Day04_Slide15_tom_sample_labels.csv"
GUIDELINES_V0_FILE = DATA_DIR / "Day04_Slide15_guidelines_v0.md"
TOM_TAGS_FILE = DATA_DIR / "Day04_Slide21_tom_failure_tags.csv"
PROMPTS_DIR = REPO / "backend" / "app" / "prototype" / "prompts"
JUDGES_DIR = REPO / "evals" / "judges"
SYNTHETIC_DIR = Path(os.getenv("FDE_SYNTHETIC_DIR", REPO / "evals" / "synthetic")).resolve()

# Day 5: the pilot on the client's cloud
INFRA_DIR = REPO / "infra"
GUARDRAILS_DIR = INFRA_DIR / "guardrails"
PLAN_FILE = Path(os.getenv("FDE_PLAN_FILE", INFRA_DIR / "pilot.plan.json")).resolve()
BEDROCK_MODELS_FILE = DATA_DIR / "Day05_Slide10_bedrock_models.csv"
PROBES_FILE = DATA_DIR / "Day05_Slide21_guardrail_probes.json"

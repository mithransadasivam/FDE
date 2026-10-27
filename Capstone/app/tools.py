"""Importing this module registers every agent tool (see app/agents/base.py). Agents call load() before their first tool call."""
import importlib

MODULES = [
    "app.search.index",          # search_cvs, search_policy
    "app.agents.screening",      # score_item
    "app.agents.interviewer",    # speak, show_diagram, listen, give_hint, score_answer, end_interview
    "app.agents.assistant",      # list_requisitions, get_candidate, search_candidates
    "app.agents.communications",  # draft_email, find_slot
    "app.agents.copilot",        # transcribe_stream, mark_point, suggest_question, flag_cv_conflict, coverage
    "app.agents.compliance",     # check_evidence, scan_prompt_log, check_log
    "app.agents.requisition_tools",  # transcribe, wording_check, save_rubric
    "app.agents.document_tools",     # read_pdf, read_docx, read_image, find_duplicate
    "app.supervisor_graph",      # routing_rule, checkpoint, decision_log
]
_loaded = False


def load() -> None:
    global _loaded
    if _loaded:
        return
    for m in MODULES:
        try:
            importlib.import_module(m)
        except ModuleNotFoundError as e:
            if e.name != m:  # a module that is not written yet is skipped; a missing dependency inside one is a real error
                raise
    _loaded = True

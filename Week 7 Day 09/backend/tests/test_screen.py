"""Ticket ENG-901: find a control by what it is, and read the screen back after saving.
Run: python -m pytest -q tests/test_screen.py"""

import pytest

from app.agent.models import ScreenError
from app.agent.screen import check_saved, find_element

CONFIRM = [{"role": "heading", "name": "Confirm outcome · KC-022578"},
           {"role": "row", "name": "Outcome | Request more information"},
           {"role": "button", "name": "Back", "ref": "e1"}, {"role": "button", "name": "Confirm", "ref": "e2"}]
# The same screen when the applicant has asked about withdrawing (KX-1004): one more button, in the middle
CONFIRM_WITHDRAW = [{"role": "heading", "name": "Confirm outcome · KC-023327"},
                    {"role": "text", "name": "The applicant asked on 27/10/2026 whether they can withdraw."},
                    {"role": "button", "name": "Back", "ref": "e1"}, {"role": "button", "name": "Withdraw case", "ref": "e2"},
                    {"role": "button", "name": "Confirm", "ref": "e3"}]
FORM = [{"role": "combobox", "name": "Outcome", "ref": "e1"}, {"role": "combobox", "name": "Reason code", "ref": "e2"},
        {"role": "textbox", "name": "Note", "ref": "e3"}, {"role": "button", "name": "Save", "ref": "e4"},
        {"role": "button", "name": "Cancel", "ref": "e5"}]
RECORDED = [{"role": "heading", "name": "Outcome recorded"}, {"role": "text", "name": "Request more information · Reference OUT-40017"},
            {"role": "link", "name": "Back to case", "ref": "e1"}]
WITHDRAWN = [{"role": "heading", "name": "Case withdrawn"}, {"role": "text", "name": "Reference OUT-40018"},
             {"role": "link", "name": "Back to case", "ref": "e1"}]


def test_finds_confirm_by_its_name_on_both_screens():
    assert find_element(CONFIRM, "button", "Confirm")["ref"] == "e2"
    assert find_element(CONFIRM_WITHDRAW, "button", "Confirm")["ref"] == "e3"


def test_the_name_ignores_case_and_extra_spaces_but_the_role_must_match():
    assert find_element(FORM, "combobox", "  reason   CODE ")["ref"] == "e2"
    with pytest.raises(ScreenError, match='No textbox named "Outcome" on this screen'):
        find_element(FORM, "textbox", "Outcome")


def test_a_control_that_is_not_there_is_an_error_not_a_guess():
    with pytest.raises(ScreenError, match='No button named "Save" on this screen'):
        find_element(CONFIRM, "button", "Save")


def test_two_controls_with_the_same_name_is_an_error():
    twice = FORM + [{"role": "button", "name": "Save", "ref": "e6"}]
    with pytest.raises(ScreenError, match='2 buttons named "Save" on this screen'):
        find_element(twice, "button", "Save")


def test_check_saved_returns_the_reference_when_the_outcome_is_the_one_chosen():
    assert check_saved(RECORDED, "Request more information") == "OUT-40017"


def test_check_saved_refuses_a_withdrawn_case():
    with pytest.raises(ScreenError, match='CaseFlow did not confirm the outcome: the screen says "Case withdrawn"'):
        check_saved(WITHDRAWN, "Request more information")


def test_check_saved_refuses_a_different_outcome():
    with pytest.raises(ScreenError, match='CaseFlow recorded "Request more information", not "Chase applicant"'):
        check_saved(RECORDED, "Chase applicant")

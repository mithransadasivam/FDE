"""Tells you when Activity 1 is done: all five tests pass. No model is used."""

from app.retrieval_eval import score_question

VPN = {
    "source": "vpn.pdf",
    "text": "A VPN session stays connected for a maximum of 12 hours.",
}
PWD = {
    "source": "password.pdf",
    "text": "Passwords must be at least 14 characters long.",
}
LOGS = {"source": "data.pdf", "text": "System and security logs are kept for 1 year."}


def test_right_chunk_first_is_rank_one():
    assert score_question([VPN, PWD], "vpn.pdf", "maximum of 12 hours") == {
        "rank": 1,
        "hit": True,
        "rr": 1.0,
    }


def test_right_chunk_third_counts_as_a_hit_with_rr_one_third():
    result = score_question([PWD, LOGS, VPN], "vpn.pdf", "maximum of 12 hours", k=4)
    assert result["rank"] == 3 and result["hit"] is True
    assert abs(result["rr"] - 1 / 3) < 1e-9


def test_a_rank_worse_than_k_is_not_a_hit():
    result = score_question([PWD, LOGS, PWD, LOGS, VPN], "vpn.pdf", "12 hours", k=4)
    assert result["rank"] == 5 and result["hit"] is False
    assert abs(result["rr"] - 0.2) < 1e-9


def test_not_found_gives_no_rank_and_zero():
    assert score_question([PWD, LOGS], "vpn.pdf", "12 hours") == {
        "rank": None,
        "hit": False,
        "rr": 0.0,
    }


def test_match_needs_the_right_source_and_ignores_case_and_line_breaks():
    copy_elsewhere = {**VPN, "source": "faq.pdf"}
    wrapped = {
        **VPN,
        "text": "A VPN session stays connected for a\nMAXIMUM  of 12 hours.",
    }
    result = score_question([copy_elsewhere, wrapped], "vpn.pdf", "maximum of 12 hours")
    assert result["rank"] == 2

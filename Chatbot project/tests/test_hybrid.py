import pytest

from app.hybrid import hybrid_search, keyword_rank, reciprocal_rank_fusion, tokenize
from app.retrieval import MODES, retrieve
from app.store import build_index


# ---- tokenizer ----
def test_codes_stay_in_one_piece_and_case_is_ignored():
    assert "vpn-809" in tokenize("Error VPN-809: certificate expired")
    assert "wifi-117" in tokenize("WIFI-117 guest access")


def test_versions_and_addresses_stay_whole_and_trailing_full_stop_is_dropped():
    tokens = tokenize("Update to 5.2 or visit reset.northwind.example.")
    assert "5.2" in tokens and "reset.northwind.example" in tokens


def test_common_words_are_dropped_but_not_and_no_are_kept():
    tokens = tokenize("How do I reset the password? It is not working, no luck")
    assert "the" not in tokens and "how" not in tokens and "do" not in tokens
    assert "reset" in tokens and "password" in tokens and "not" in tokens and "no" in tokens


def test_tokenize_empty_and_symbols():
    assert tokenize("") == [] and tokenize("?! ... ---") == []


# ---- reciprocal rank fusion ----
def test_fusion_of_one_list_keeps_its_order():
    assert reciprocal_rank_fusion([["a", "b", "c"]]) == ["a", "b", "c"]


def test_chunk_in_both_lists_beats_chunks_in_one():
    assert reciprocal_rank_fusion([["a", "b", "c"], ["c", "d"]])[0] == "c"


def test_ties_keep_the_order_first_seen():
    # a is 1st in list one, b is 1st in list two: equal scores, so a (seen first) goes first
    assert reciprocal_rank_fusion([["a"], ["b"]]) == ["a", "b"]


def test_no_duplicates_even_with_repeats_inside_a_list():
    fused = reciprocal_rank_fusion([["a", "a", "b"], ["b", "a"]])
    assert sorted(fused) == ["a", "b"] and len(fused) == 2


def test_inputs_are_not_changed():
    one, two = ["a", "b"], ["b", "c"]
    reciprocal_rank_fusion([one, two])
    assert one == ["a", "b"] and two == ["b", "c"]


def test_fusion_of_nothing():
    assert reciprocal_rank_fusion([]) == [] and reciprocal_rank_fusion([[], []]) == []


# ---- keyword ranking ----
IDS = ["c1", "c2", "c3"]
TEXTS = [
    "VPN-806 certificate missing. Raise a ticket for a new certificate.",
    "VPN-815 connection from a restricted country is blocked.",
    "Daily backups are kept for 30 days.",
]


def test_exact_code_ranks_its_chunk_first():
    assert keyword_rank("what is VPN-815?", IDS, TEXTS, limit=5)[0] == "c2"


def test_chunks_with_no_shared_word_are_left_out():
    assert keyword_rank("backups", IDS, TEXTS, limit=5) == ["c3"]


@pytest.mark.parametrize("question", ["", "   ", "how do i", "?!"])
def test_empty_or_all_common_word_question_gives_nothing(question):
    assert keyword_rank(question, IDS, TEXTS, limit=5) == []


def test_keyword_rank_respects_the_limit_and_empty_corpus():
    assert len(keyword_rank("vpn certificate", IDS, TEXTS, limit=1)) == 1
    assert keyword_rank("vpn", [], [], limit=5) == []


# ---- hybrid search over a small real Chroma index, with a fake embedder ----
def fake_text_vector(text):
    t = text.lower()
    return [1.0 if "certificate" in t else 0.0, 1.0 if "backup" in t else 0.0, 1.0 if "country" in t else 0.0, 0.1]


def fake_embed_many(texts):
    return [fake_text_vector(t) for t in texts]


CHUNKS = [
    {"source": "errors.pdf", "page": 1, "chunk": 1, "text": "VPN-806 certificate missing. Raise a ticket."},
    {"source": "errors.pdf", "page": 1, "chunk": 2, "text": "VPN-815 blocked because it came from a restricted country."},
    {"source": "backup.md", "page": 1, "chunk": 1, "text": "Daily backups are kept for 30 days."},
    {"source": "misc.md", "page": 1, "chunk": 1, "text": "Printers are on floor one."},
]


@pytest.fixture
def index(tmp_path):
    build_index(CHUNKS, fake_embed_many, tmp_path)
    return tmp_path


def search(question, index, **kw):
    return hybrid_search(question, embed_fn=fake_text_vector_query, path=index, **kw)


def fake_text_vector_query(question):
    # the "meaning" side only understands a few words, like a weak embedder
    return fake_text_vector(question)


def test_exact_code_question_is_found_by_keyword_when_vector_has_no_signal(index):
    results = search("what does VPN-815 mean", index, k=2)
    assert results[0]["source"] == "errors.pdf" and results[0]["chunk"] == 2
    assert results[0]["found_by"] in ("keyword", "both")


def test_every_result_has_a_similarity_score_even_keyword_only_ones(index):
    results = search("VPN-806 printers", index, k=4, candidates=1)
    assert results and all(isinstance(r["score"], float) for r in results)
    assert all(set(r) == {"text", "source", "page", "chunk", "score", "found_by"} for r in results)


def test_keyword_only_chunk_gets_the_cosine_similarity(index):
    # "backup" points the (fake) meaning-based side at the backups chunk, while the code VPN-815
    # points the keyword side at a different chunk: that chunk is keyword-only.
    results = search("backup VPN-815", index, k=4, candidates=1)
    keyword_only = [r for r in results if r["found_by"] == "keyword"]
    assert [r["chunk"] for r in keyword_only] == [2] and keyword_only[0]["source"] == "errors.pdf"
    assert -1.0 <= keyword_only[0]["score"] <= 1.0


def test_k_limits_results_and_results_are_unique(index):
    results = search("certificate backups country VPN-806", index, k=2)
    assert len(results) == 2
    assert len({(r["source"], r["chunk"]) for r in results}) == 2


def test_blank_question_and_bad_k(index):
    assert search("   ", index) == []
    with pytest.raises(ValueError):
        search("vpn", index, k=0)


def test_missing_index_raises(tmp_path):
    with pytest.raises(ValueError):
        hybrid_search("vpn", embed_fn=fake_text_vector_query, path=tmp_path)


# ---- the mode setting ----
def test_modes_and_unknown_mode():
    assert MODES == ("vector", "hybrid", "rerank", "full")
    with pytest.raises(ValueError, match="Unknown retrieval mode"):
        retrieve("q", 4, mode="magic")


def test_retrieve_dispatches_to_the_chosen_mode(monkeypatch):
    import app.retrieval as retrieval

    monkeypatch.setattr(retrieval, "search", lambda q, k: ["vector-result"])
    monkeypatch.setattr(retrieval, "hybrid_search", lambda q, k: ["hybrid-result"])
    assert retrieve("q", 4, mode="vector") == ["vector-result"]
    assert retrieve("q", 4, mode="hybrid") == ["hybrid-result"]
    assert retrieve("q", 4) == ["vector-result"]  # default comes from RETRIEVAL_MODE in config


def test_retrieval_mode_can_be_overridden_for_a_run_and_a_typo_fails_clearly(monkeypatch):
    import importlib

    import app.config as config

    try:
        monkeypatch.setenv("RETRIEVAL_MODE", "full")
        assert importlib.reload(config).RETRIEVAL_MODE == "full"
        monkeypatch.setenv("RETRIEVAL_MODE", "fulll")
        with pytest.raises(ValueError, match="RETRIEVAL_MODE must be one of"):
            importlib.reload(config)
    finally:
        monkeypatch.delenv("RETRIEVAL_MODE", raising=False)
        importlib.reload(config)
    assert config.RETRIEVAL_MODE == "vector"

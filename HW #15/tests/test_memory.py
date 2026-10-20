"""Day 12, Activity 2: searching the agent's notes."""

from app.memory import NoteBook, memory_context


def book(*texts):
    nb = NoteBook()
    for text, source in texts:
        nb.add(text, source)
    return nb


def test_no_meaningful_words_finds_nothing():
    nb = book(("VPN-809 means the certificate expired", "KB-1101"))
    assert nb.search("") == [] and nb.search("what is the") == []


def test_more_matching_words_rank_higher_and_zero_matches_are_left_out():
    nb = book(
        ("Print Queue jobs stuck with PRN-310", "KB-3301"),
        ("VPN-809 means the certificate expired", "KB-1101"),
        ("Finance Portal outage since 07:58", "service_status"),
    )
    found = nb.search("VPN-809 certificate renewal")
    assert [n["source"] for n in found] == ["KB-1101"]


def test_the_source_counts_and_ties_go_to_the_newer_note():
    nb = book(
        ("Certificates last 12 months", "KB-1101"),
        ("Renew certificates from the portal", "VPN policy [1]"),
    )
    assert [n["source"] for n in nb.search("certificates")] == [
        "VPN policy [1]",
        "KB-1101",
    ]
    assert nb.search("KB-1101")[0]["text"] == "Certificates last 12 months"


def test_at_most_k_notes_and_the_note_itself_is_returned():
    nb = book(*[(f"VPN fact number {i}", "KB-1101") for i in range(6)])
    found = nb.search("VPN fact", k=2)
    assert len(found) == 2 and found[0] is nb.notes[5]


def test_notes_survive_a_restart_and_feed_the_instructions(tmp_path):
    path = str(tmp_path / "notes.json")
    nb = NoteBook(path)
    nb.add("Finance Portal outage since 07:58", "service_status")
    nb.save()
    again = NoteBook(path)
    assert "Finance Portal outage" in memory_context(
        again, "Is the Finance Portal down?"
    )
    assert memory_context(again, "printer jam") == ""

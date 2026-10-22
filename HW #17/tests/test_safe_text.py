import re

from app.safe_text import md_safe


def test_markdown_links_and_images_cannot_form():
    out = md_safe("![x](https://evil.example/p.png?q=secret) and [click](https://evil.example)")
    assert not re.search(r"(?<!\\)[\[\]]", out)  # every bracket is escaped, so no link/image syntax forms
    assert out.count("\\[") == 2 and out.count("\\]") == 2


def test_autolink_and_html_tags_are_neutralised():
    out = md_safe("<https://evil.example> <script>x</script>")
    assert "<" not in out and "&lt;" in out


def test_citations_and_plain_text_still_read_normally():
    assert md_safe("Backups are kept 30 days [1].") == "Backups are kept 30 days \\[1\\]."
    assert md_safe("**bold** and a list\n1. one") == "**bold** and a list\n1. one"


def test_non_text_input_does_not_crash():
    assert md_safe(None) == "None"

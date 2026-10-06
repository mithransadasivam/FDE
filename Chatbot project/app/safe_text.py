"""Make untrusted text safe: for Markdown display, and for use inside prompts."""


def escape_angle_brackets(text: str) -> str:
    """Make it impossible for untrusted text to form a tag of its own inside a prompt."""
    return str(text).replace("<", "&lt;").replace(">", "&gt;")


def md_safe(text: str) -> str:
    """Stop text from turning into links, images or HTML when Streamlit renders it as Markdown.

    Square brackets are escaped, so `[x](url)` and `![x](url)` cannot form (a citation
    like [1] still shows as [1]); `<` is escaped, so `<https://...>` and tags cannot form.
    Plain text, bold and lists are left alone.
    """
    return str(text).replace("[", "\\[").replace("]", "\\]").replace("<", "&lt;")

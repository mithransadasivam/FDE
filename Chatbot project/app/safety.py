"""Safety: spot requests an IT help desk must never help with, before any search or model call.

This is a plain-code check, so it is fast, free, testable and the same every time. It only catches the clear
cases. The chatbot's prompt carries the same rule for the subtler ones (see app/answer.py).

The line (also written in REQUIREMENTS.md): a normal how-to is answered; helping someone get round a control,
reach someone else's data without their knowledge, move confidential data out, or run pirated software is refused.
Looks-risky-but-fine questions ("How do I report a lost laptop?", "What if my password was stolen?") must still be answered.
"""
import re

from app.config import CANARY

_GAP = r".{0,60}?"  # a few words between the verb and the thing

# (name, pattern). Each pattern is matched against the question with whitespace collapsed, ignoring case.
UNSAFE_PATTERNS = [
    ("switch off security software",
     r"\b(switch off|turn off|disable|deactivate|uninstall|remove|kill|stop)\b" + _GAP +
     r"\b(anti-?virus|endpoint (protection|agent|security)|security software|firewall|defender|edr|monitoring agent|dlp)\b"),
    ("get round a control",
     r"\b(get round|get around|bypass|circumvent|work around|evade|avoid|beat|trick|fool)\b" + _GAP +
     r"\b(password (rules?|policy|expiry|reuse)|mfa|multi-?factor|2fa|vpn|travel (rule|restriction|block)|restricted countr(y|ies)|"
     r"security (control|check|policy|rules?)|restriction|content filter|web filter|monitoring|usb (block|restriction))\b"),
    ("someone else's account without their knowledge",
     r"\b(read|access|open|get into|log ?in to|log ?into|use|check|monitor|spy on)\b" + _GAP +
     r"\b(mailbox|e-?mails?|inbox|accounts?|files?|messages?|calendar|chats?)\b" + _GAP +
     r"\bwithout\b" + _GAP + r"\b(knowing|know|permission|telling|consent|approval|noticing|noticed|finding out)\b"),
    ("confidential data to a personal place",
     r"\b(copy|move|send|upload|save|forward|e-?mail|export|download|paste|transfer)\b" + _GAP +
     r"\b(customer|client|confidential|restricted|company|staff|payroll|hr)\b" + _GAP +
     r"\b(data|database|list|lists|records|files?|documents?|spreadsheets?|information)\b" + _GAP +
     r"\b(personal|private|home|my own|usb|stick|dropbox|gmail|google drive|chatgpt|public ai|external)\b"),
    ("pirated software",
     r"\b(crack(ed|s)?|pirat(e|ed)|keygen|key generator|unlicensed|license bypass|licence bypass|warez)\b"),
    # Asking the chatbot for its own instructions, or to drop them. Narrow on purpose: "what are the printer instructions?" and "tell me the
    # rules for sharing files" must still be answered, so only "system prompt"-style words and "ignore your/previous instructions" count.
    ("reveal or drop the chatbot's instructions",
     r"\b(system|initial|hidden|secret|original|developer) (prompt|instructions)\b|"
     r"\b(ignore|forget|disregard)\b.{0,20}\b(your|previous|prior|above|earlier|all)\b.{0,20}\b(instructions?|rules|guidelines)\b"),
]
_COMPILED = [(name, re.compile(pattern, re.IGNORECASE)) for name, pattern in UNSAFE_PATTERNS]

# "Can I paste my customer list into ChatGPT?" asks whether something is allowed. The policy answers that
# (no), which helps more than a refusal. "How can I ..." asks for a method and is still refused.
_ASKS_PERMISSION = re.compile(r"(?<!how )\b(can|could|may|should) i\b|\bam i allowed\b|\bis it (ok|okay|allowed|fine|safe|against)\b", re.IGNORECASE)
_PERMISSION_QUESTIONS_ARE_FINE = {"confidential data to a personal place"}


_SECRET_PATTERNS = [re.compile(re.escape(CANARY), re.IGNORECASE), re.compile(r"(?<![A-Za-z0-9])sk-[A-Za-z0-9_-]{8,}"),
                    re.compile(r"OPENROUTER", re.IGNORECASE)]


def leaks_secret(text: str) -> bool:
    """True when a reply contains the canary, something shaped like an API key, or the name of the key variable."""
    return any(p.search(text) for p in _SECRET_PATTERNS)


def check_request(question: str) -> str | None:
    """The name of the rule the question breaks, or None when it looks fine."""
    text = " ".join(question.split())
    asks_permission = bool(_ASKS_PERMISSION.search(text))
    for name, pattern in _COMPILED:
        if pattern.search(text) and not (asks_permission and name in _PERMISSION_QUESTIONS_ARE_FINE):
            return name
    return None

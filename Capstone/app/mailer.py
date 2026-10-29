"""Where an approved email goes (Day 3, prompt 10). Approving ALWAYS writes the email as a .eml file to storage/outbox_sent/ (our fictional mail server: you can open
the file in any mail program). If EMAIL_LIVE=1 and an SMTP server is configured it is ALSO handed to that server: real sending is off unless you switch it on."""
import smtplib
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

from app.config import get_settings
from app.models import Candidate
from app.models_ext import EmailDraft


class MailError(Exception):
    """The email could not be written or sent. The message is safe to show."""


def message_for(draft: EmailDraft, cand: Candidate, approved_by: str) -> EmailMessage:
    to = (((cand.profile or {}).get("email") or {}).get("value")) or f"candidate-{cand.id}@example.invalid"
    msg = EmailMessage()
    msg["From"] = get_settings().mail_from
    msg["To"] = to
    msg["Subject"] = draft.subject
    msg["Date"] = formatdate(localtime=False)
    msg["Message-ID"] = make_msgid(domain="hiring.example")
    msg["X-Approved-By"] = approved_by  # the person who approved it: nothing is sent without one
    msg["X-Draft-Id"] = str(draft.id)
    msg.set_content(draft.body)
    return msg


def write_eml(draft: EmailDraft, cand: Candidate, approved_by: str) -> Path:
    out = get_settings().storage_dir / "outbox_sent"
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"draft_{draft.id:05d}.eml"
    path.write_bytes(bytes(message_for(draft, cand, approved_by)))
    return path


def send_live(msg: EmailMessage) -> bool:
    """Hands the message to the configured SMTP server. Returns False (and sends nothing) unless EMAIL_LIVE is on."""
    s = get_settings()
    if not (s.email_live and s.smtp_host):
        return False
    try:
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:
            smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password)
            smtp.send_message(msg)
    except Exception as e:
        raise MailError(f"The email server refused or could not be reached ({type(e).__name__}): nothing was marked as sent.") from e
    return True

"""Outbound mail over SMTP with STARTTLS (S-22). Skipped when SMTP is not configured; never sent to the
synthetic example.edu addresses (unless MAIL_TEST_TO redirects them to one inbox for testing); a failure is
logged and never raised, because mail must not fail a request."""
import smtplib
from email.message import EmailMessage

from app import logging as applog
from app.config import settings


def send(to: str, subject: str, text: str) -> bool:
    if not (settings.smtp_host and settings.mail_from):
        return False
    if to.lower().endswith("@example.edu"):
        if not settings.mail_test_to:
            return False
        subject, to = f"[for {to}] {subject}", settings.mail_test_to
    msg = EmailMessage()
    msg["From"], msg["To"], msg["Subject"] = settings.mail_from, to, subject
    msg.set_content(text)
    try:
        with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as smtp:
            smtp.starttls()
            if settings.smtp_user:
                smtp.login(settings.smtp_user, settings.smtp_password or "")
            smtp.send_message(msg)
        return True
    except Exception as exc:  # noqa: BLE001
        applog.event(level="warning", msg="mail failed", error=type(exc).__name__)
        return False

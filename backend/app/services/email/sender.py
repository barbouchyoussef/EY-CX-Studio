"""Transactional email (invites, password reset).

The app had no mail transport at all -- the "book a consultation" feature only builds a Gmail
compose link client-side. This module adds real async SMTP delivery to an arbitrary recipient
(the invited/resetting user), sent from a dedicated mailbox configured via SMTP_* env vars.

It degrades gracefully: with SMTP unconfigured, `is_configured()` is False and callers fall
back (invite returns its token; forgot-password stays silent). Never raises into a request path
in a way that reveals whether an account exists.
"""

from __future__ import annotations

import logging
from email.message import EmailMessage

import aiosmtplib

from app.core.config import get_settings

logger = logging.getLogger(__name__)


class EmailNotConfigured(RuntimeError):
    pass


def is_configured() -> bool:
    s = get_settings()
    return bool(s.smtp_host and s.email_from)


async def send_email(to: str, subject: str, text: str, html: str | None = None) -> None:
    """Send one message. Raises EmailNotConfigured if SMTP isn't set; propagates transport
    errors so the caller can decide whether to swallow them."""
    s = get_settings()
    if not is_configured():
        raise EmailNotConfigured("SMTP is not configured (set SMTP_HOST and EMAIL_FROM)")

    msg = EmailMessage()
    msg["From"] = f"{s.email_from_name} <{s.email_from}>"
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    if html:
        msg.add_alternative(html, subtype="html")

    # Port 465 = implicit TLS; 587 (or anything with SMTP_USE_TLS) = STARTTLS upgrade.
    use_implicit_tls = s.smtp_port == 465
    await aiosmtplib.send(
        msg,
        hostname=s.smtp_host,
        port=s.smtp_port,
        username=s.smtp_username or None,
        password=s.smtp_password or None,
        use_tls=use_implicit_tls,
        start_tls=(s.smtp_use_tls and not use_implicit_tls),
    )


# --------------------------------------------------------------------------- #
# Message builders -- return (subject, text, html)                              #
# --------------------------------------------------------------------------- #

def _shell(title: str, body_html: str, button_label: str, url: str) -> str:
    return f"""\
<div style="font-family:system-ui,Segoe UI,Arial,sans-serif;max-width:520px;margin:0 auto;color:#1a1a1a">
  <h2 style="color:#0F1015">{title}</h2>
  {body_html}
  <p style="margin:28px 0">
    <a href="{url}" style="background:#C5A04F;color:#0F1015;text-decoration:none;
       padding:10px 18px;border-radius:8px;font-weight:600;display:inline-block">{button_label}</a>
  </p>
  <p style="font-size:12px;color:#666">If the button doesn't work, paste this link into your browser:<br>
    <span style="color:#3858E9;word-break:break-all">{url}</span></p>
</div>"""


def build_invite_email(accept_url: str, inviter_name: str | None) -> tuple[str, str, str]:
    who = f"{inviter_name} has invited" if inviter_name else "You have been invited"
    subject = "You're invited to EY CX Studio"
    text = (
        f"{who} you to EY CX Studio.\n\n"
        f"Set up your account here (this link expires):\n{accept_url}\n"
    )
    html = _shell("You're invited to EY CX Studio",
                  f"<p>{who} you to join EY CX Studio. Set up your account to get started.</p>",
                  "Accept invitation", accept_url)
    return subject, text, html


def build_assessment_invite_email(
    link: str, client_name: str | None, consultant_name: str | None
) -> tuple[str, str, str]:
    greeting = f"Hello {client_name}," if client_name else "Hello,"
    who = f"{consultant_name} has invited you" if consultant_name else "You have been invited"
    subject = "You're invited to complete a CX maturity assessment"
    text = (
        f"{greeting}\n\n"
        f"{who} to complete a short EY customer-experience maturity assessment. "
        "It's a guided conversation — no account needed.\n\n"
        f"Open your assessment here (this link expires):\n{link}\n"
    )
    html = _shell(
        "Your CX maturity assessment",
        f"<p>{greeting}</p><p>{who} to complete a short EY customer-experience maturity "
        "assessment — a guided conversation, no account needed.</p>",
        "Start the assessment",
        link,
    )
    return subject, text, html


def build_reset_email(reset_url: str) -> tuple[str, str, str]:
    subject = "Reset your EY CX Studio password"
    text = (
        "We received a request to reset your EY CX Studio password.\n\n"
        f"Reset it here (this link expires shortly):\n{reset_url}\n\n"
        "If you didn't request this, you can ignore this email.\n"
    )
    html = _shell("Reset your password",
                  "<p>We received a request to reset your password. This link expires shortly.</p>"
                  "<p style='font-size:12px;color:#666'>If you didn't request this, ignore this email.</p>",
                  "Reset password", reset_url)
    return subject, text, html

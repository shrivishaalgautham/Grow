import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage

from app.config import settings

log = logging.getLogger(__name__)

console_outbox: list["Message"] = []


@dataclass(frozen=True)
class Message:
    to: str
    subject: str
    text: str


def mask(address: str) -> str:
    local, _, domain = address.partition("@")
    return f"{local[:1]}***@{domain}"


def send(message: Message) -> None:
    if settings.email_transport == "smtp":
        _send_smtp(message)
        log.info("email sent to=%s subject=%r", mask(message.to), message.subject)
        return
    console_outbox.append(message)
    log.info("email console to=%s subject=%r\n%s", message.to, message.subject, message.text)


def _send_smtp(message: Message) -> None:
    mail = EmailMessage()
    mail["From"] = settings.email_from
    mail["To"] = message.to
    mail["Subject"] = message.subject
    mail.set_content(message.text)
    with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as client:
        client.starttls()
        if settings.smtp_user:
            client.login(settings.smtp_user, settings.smtp_password)
        client.send_message(mail)

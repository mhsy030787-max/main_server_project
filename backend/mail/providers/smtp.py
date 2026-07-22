import smtplib
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from settings import (
    MAIL_PUBLIC_DOMAIN,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_SENDER,
    SMTP_SSL,
    SMTP_STARTTLS,
    SMTP_TIMEOUT_SECONDS,
    SMTP_USER,
)

from .base import ExternalMailError, ExternalMailNotConfigured


NAME = "smtp"


def configured():
    return bool(SMTP_HOST and SMTP_SENDER)


def public_address(user_id):
    if MAIL_PUBLIC_DOMAIN:
        return f"{user_id}@{MAIL_PUBLIC_DOMAIN}"
    return SMTP_SENDER


def build_message(sender, recipient, subject, body, attachment=None):
    if not configured():
        raise ExternalMailNotConfigured("SMTP 외부 메일 설정이 완료되지 않았습니다.")
    message = EmailMessage()
    message["From"] = formataddr((sender.get("name") or "DataVault", SMTP_SENDER))
    message["To"] = recipient
    message["Subject"] = subject
    message["Message-ID"] = make_msgid(domain=MAIL_PUBLIC_DOMAIN or None)
    message["Reply-To"] = public_address(sender["id"])
    message.set_content(body)
    if attachment:
        content_type = attachment.get("contentType") or "application/octet-stream"
        main_type, _, sub_type = content_type.partition("/")
        if not sub_type:
            main_type, sub_type = "application", "octet-stream"
        message.add_attachment(
            attachment["data"], maintype=main_type, subtype=sub_type,
            filename=attachment["name"],
        )
    return message


def send(sender, recipient, subject, body, attachment=None):
    message = build_message(sender, recipient, subject, body, attachment)
    smtp_class = smtplib.SMTP_SSL if SMTP_SSL else smtplib.SMTP
    try:
        with smtp_class(SMTP_HOST, SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS) as client:
            if not SMTP_SSL and SMTP_STARTTLS:
                client.starttls()
            if SMTP_USER:
                client.login(SMTP_USER, SMTP_PASSWORD)
            client.send_message(message)
    except (OSError, smtplib.SMTPException) as error:
        raise ExternalMailError("외부 메일 서버가 발송을 거부했습니다.") from error
    return message["Message-ID"]

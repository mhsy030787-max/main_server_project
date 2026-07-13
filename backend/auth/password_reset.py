import smtplib
import time
from email.message import EmailMessage
from secrets import token_urlsafe
from urllib.parse import quote

from settings import (
    PASSWORD_RESET_SECONDS,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_SENDER,
    SMTP_STARTTLS,
    SMTP_USER,
)
from storage.password_resets import create_password_reset_store
from storage.stores import USER_STORE


RESET_STORE = create_password_reset_store(USER_STORE)


def create_reset_token(user_id):
    token = token_urlsafe(32)
    RESET_STORE.create(token, user_id, int(time.time()) + PASSWORD_RESET_SECONDS)
    return token


def consume_reset_token(token):
    if not token or len(token) > 200:
        return None
    return RESET_STORE.consume(token)


def make_reset_url(base_url, token):
    return f"{base_url.rstrip('/')}/UI/reset_password_ui.html?token={quote(token)}"


def smtp_is_configured():
    return bool(SMTP_HOST and SMTP_SENDER)


def send_reset_email(recipient, reset_url):
    if not smtp_is_configured():
        return False

    message = EmailMessage()
    message["Subject"] = "[DataVault] 비밀번호 재설정"
    message["From"] = SMTP_SENDER
    message["To"] = recipient
    message.set_content(
        "DataVault 비밀번호 재설정 요청이 접수되었습니다.\n\n"
        f"아래 주소를 15분 이내에 열어 새 비밀번호를 설정하세요.\n{reset_url}\n\n"
        "본인이 요청하지 않았다면 이 메일을 무시하세요."
    )

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=10) as server:
        if SMTP_STARTTLS:
            server.starttls()
        if SMTP_USER:
            server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(message)
    return True

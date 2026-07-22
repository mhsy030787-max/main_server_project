import time
from secrets import token_urlsafe
from urllib.parse import quote

from mail.transport import external_send_enabled, send_external
from settings import PASSWORD_RESET_SECONDS
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


def reset_mail_is_configured():
    return external_send_enabled()


def send_reset_email(recipient, reset_url):
    if not reset_mail_is_configured():
        return False
    body = (
        "DataVault 비밀번호 재설정 요청이 접수되었습니다.\n\n"
        f"아래 주소를 15분 이내에 열어 새 비밀번호를 설정하세요.\n{reset_url}\n\n"
        "본인이 요청하지 않았다면 이 메일을 무시하세요."
    )
    send_external(
        {"id": "security", "name": "DataVault 보안팀"},
        recipient,
        "[DataVault] 비밀번호 재설정",
        body,
    )
    return True

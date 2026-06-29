import json

from settings import COOKIE_SECURE, REFRESH_TOKEN_SECONDS


def json_bytes(data):
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def get_cookie(headers, name):
    cookie_header = headers.get("Cookie", "")
    for item in cookie_header.split(";"):
        key, _, value = item.strip().partition("=")
        if key == name:
            return value
    return None


def auth_cookie(refresh_token):
    secure_option = "; Secure" if COOKIE_SECURE else ""
    return (
        f"refresh_token={refresh_token}; Path=/; HttpOnly; SameSite=Lax; "
        f"Max-Age={REFRESH_TOKEN_SECONDS}{secure_option}"
    )


def clear_refresh_cookie():
    secure_option = "; Secure" if COOKIE_SECURE else ""
    return f"refresh_token=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0{secure_option}"

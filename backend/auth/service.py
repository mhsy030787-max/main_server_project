import time
from secrets import token_urlsafe

from auth.users import public_user
from http_utils import auth_cookie, clear_refresh_cookie, get_cookie
from security.jwt import hash_token, make_access_token, verify_jwt
from settings import ACCESS_TOKEN_SECONDS, LOGIN_LIMIT_COUNT, LOGIN_LIMIT_WINDOW_SECONDS, REFRESH_TOKEN_SECONDS
from storage.stores import SESSION_STORE


LOGIN_ATTEMPTS = {}


def login_attempt_key(client_ip, user_id):
    return f"{client_ip}:{user_id}"


def login_is_limited(client_ip, user_id):
    key = login_attempt_key(client_ip, user_id)
    attempt = LOGIN_ATTEMPTS.get(key)
    if not attempt:
        return False

    now = int(time.time())
    if now - attempt["firstAt"] > LOGIN_LIMIT_WINDOW_SECONDS:
        LOGIN_ATTEMPTS.pop(key, None)
        return False

    return attempt["count"] >= LOGIN_LIMIT_COUNT


def remember_failed_login(client_ip, user_id):
    key = login_attempt_key(client_ip, user_id)
    now = int(time.time())
    attempt = LOGIN_ATTEMPTS.get(key)
    if not attempt or now - attempt["firstAt"] > LOGIN_LIMIT_WINDOW_SECONDS:
        LOGIN_ATTEMPTS[key] = {"count": 1, "firstAt": now}
        return

    attempt["count"] += 1


def clear_failed_login(client_ip, user_id):
    LOGIN_ATTEMPTS.pop(login_attempt_key(client_ip, user_id), None)


def make_refresh_token():
    return token_urlsafe(48)


def make_auth_payload(user, session_id):
    return {
        "ok": True,
        "message": "로그인 성공",
        "user": public_user(user),
        "accessToken": make_access_token(user, session_id),
        "tokenType": "Bearer",
        "expiresIn": ACCESS_TOKEN_SECONDS,
    }


def create_login_session(user):
    session_id = token_urlsafe(24)
    refresh_token = make_refresh_token()
    now = int(time.time())
    SESSION_STORE.create_session(
        session_id,
        user,
        hash_token(refresh_token),
        now,
        now + REFRESH_TOKEN_SECONDS,
    )
    return session_id, refresh_token


def current_session_id(headers):
    auth_header = headers.get("Authorization", "")
    auth_type, _, token = auth_header.partition(" ")
    if auth_type.lower() != "bearer" or not token:
        return None

    payload = verify_jwt(token)
    if not payload:
        return None

    session_id = payload.get("sid")
    session = SESSION_STORE.get_session(session_id)
    if not session or session.get("revoked"):
        return None

    if session["user"]["id"] != payload.get("sub"):
        return None

    return session_id


def current_user(headers):
    session_id = current_session_id(headers)
    if not session_id:
        return None

    session = SESSION_STORE.get_session(session_id)
    if not session or session.get("revoked"):
        return None

    return session["user"]


def current_session_from_refresh(headers):
    refresh_token = get_cookie(headers, "refresh_token")
    if not refresh_token:
        return None

    refresh_hash = hash_token(refresh_token)
    session = SESSION_STORE.find_by_refresh_hash(refresh_hash)
    if not session:
        return None
    return session["sessionId"], session


def rotate_refresh_token(session_id):
    new_refresh_token = make_refresh_token()
    refresh_expires_at = int(time.time()) + REFRESH_TOKEN_SECONDS
    SESSION_STORE.update_refresh_token(
        session_id,
        hash_token(new_refresh_token),
        refresh_expires_at,
    )
    return new_refresh_token


__all__ = [
    "auth_cookie",
    "clear_failed_login",
    "clear_refresh_cookie",
    "create_login_session",
    "current_session_from_refresh",
    "current_session_id",
    "current_user",
    "login_is_limited",
    "make_access_token",
    "make_auth_payload",
    "remember_failed_login",
    "rotate_refresh_token",
]

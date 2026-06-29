from http import HTTPStatus

from auth.service import (
    auth_cookie,
    clear_failed_login,
    clear_refresh_cookie,
    create_login_session,
    current_session_from_refresh,
    current_session_id,
    current_user,
    login_is_limited,
    make_access_token,
    make_auth_payload,
    remember_failed_login,
    rotate_refresh_token,
)
from security.passwords import verify_password
from settings import ACCESS_TOKEN_SECONDS
from storage.stores import SESSION_STORE, USER_STORE, mysql_config_from_env


def handle_api_get(handler):
    if handler.path == "/api/health":
        handler.send_json({
            "ok": True,
            "storage": USER_STORE.storage_type,
            "sessionStorage": SESSION_STORE.storage_type,
            "mysqlConfigured": mysql_config_from_env() is not None,
        })
        return

    if handler.path == "/api/me":
        user = current_user(handler.headers)
        if not user:
            handler.send_json({"ok": False, "message": "로그인이 필요합니다."}, HTTPStatus.UNAUTHORIZED)
            return

        handler.send_json({"ok": True, "user": user})
        return

    if handler.path == "/api/sessions":
        user = current_user(handler.headers)
        if not user:
            handler.send_json({"ok": False, "message": "로그인이 필요합니다."}, HTTPStatus.UNAUTHORIZED)
            return

        handler.send_json({
            "ok": True,
            "sessions": [
                {
                    "sessionId": session["sessionId"],
                    "userId": session["user"]["id"],
                    "name": session["user"]["name"],
                    "role": session["user"]["role"],
                    "createdAt": session["createdAt"],
                    "expiresAt": session["refreshExpiresAt"],
                    "active": not session.get("revoked", False),
                }
                for session in SESSION_STORE.list_sessions_for_user(user["id"])
            ],
        })
        return

    handler.send_json({"ok": False, "message": "없는 API입니다."}, HTTPStatus.NOT_FOUND)


def handle_api_post(handler):
    if handler.path == "/api/login":
        body = handler.read_json_body()
        user_id = body.get("userId", "")
        password = body.get("password", "")
        client_ip = handler.client_address[0]

        if login_is_limited(client_ip, user_id):
            handler.send_json(
                {"ok": False, "message": "로그인 실패가 많습니다. 잠시 후 다시 시도하세요."},
                HTTPStatus.TOO_MANY_REQUESTS,
            )
            return

        user = USER_STORE.get_user(user_id)

        if not user or not verify_password(password, user["password"]):
            remember_failed_login(client_ip, user_id)
            handler.send_json(
                {"ok": False, "message": "아이디 또는 비밀번호가 올바르지 않습니다."},
                HTTPStatus.UNAUTHORIZED,
            )
            return

        clear_failed_login(client_ip, user_id)
        session_id, refresh_token = create_login_session(user)
        handler.send_json(
            make_auth_payload(user, session_id),
            headers={"Set-Cookie": auth_cookie(refresh_token)},
        )
        return

    if handler.path == "/api/refresh":
        session = current_session_from_refresh(handler.headers)
        if not session:
            handler.send_json(
                {"ok": False, "message": "다시 로그인이 필요합니다."},
                HTTPStatus.UNAUTHORIZED,
                headers={"Set-Cookie": clear_refresh_cookie()},
            )
            return

        session_id, session_data = session
        user = session_data["user"]
        new_refresh_token = rotate_refresh_token(session_id)
        handler.send_json(
            {
                "ok": True,
                "message": "토큰이 갱신되었습니다.",
                "user": user,
                "accessToken": make_access_token(user, session_id),
                "tokenType": "Bearer",
                "expiresIn": ACCESS_TOKEN_SECONDS,
            },
            headers={"Set-Cookie": auth_cookie(new_refresh_token)},
        )
        return

    if handler.path == "/api/register":
        body = handler.read_json_body()
        user_id = body.get("userId", "").strip()
        password = body.get("password", "")
        name = body.get("name", "").strip()
        role = body.get("role", "사원")

        if not user_id or not password or not name:
            handler.send_json(
                {"ok": False, "message": "이름, 아이디, 비밀번호를 모두 입력하세요."},
                HTTPStatus.BAD_REQUEST,
            )
            return

        if USER_STORE.user_exists(user_id):
            handler.send_json(
                {"ok": False, "message": "이미 존재하는 아이디입니다."},
                HTTPStatus.CONFLICT,
            )
            return

        USER_STORE.create_user(user_id, password, name, role)
        handler.send_json({"ok": True, "message": "회원가입이 완료되었습니다."}, HTTPStatus.CREATED)
        return

    if handler.path == "/api/logout":
        session_id = current_session_id(handler.headers)
        if session_id:
            SESSION_STORE.revoke_session(session_id)

        handler.send_json(
            {"ok": True, "message": "로그아웃 되었습니다."},
            headers={"Set-Cookie": clear_refresh_cookie()},
        )
        return

    if handler.path == "/api/sessions/revoke":
        user = current_user(handler.headers)
        if not user:
            handler.send_json({"ok": False, "message": "로그인이 필요합니다."}, HTTPStatus.UNAUTHORIZED)
            return

        body = handler.read_json_body()
        target_session_id = body.get("sessionId", "")
        session = SESSION_STORE.get_session(target_session_id)
        if not session or session["user"]["id"] != user["id"]:
            handler.send_json({"ok": False, "message": "세션을 찾을 수 없습니다."}, HTTPStatus.NOT_FOUND)
            return

        SESSION_STORE.revoke_session(target_session_id)
        handler.send_json({"ok": True, "message": "세션을 종료했습니다."})
        return

    handler.send_json({"ok": False, "message": "없는 API입니다."}, HTTPStatus.NOT_FOUND)

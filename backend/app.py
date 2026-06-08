from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import base64
import hashlib
import hmac
import json
from pathlib import Path
from secrets import token_bytes, token_urlsafe
from urllib.parse import unquote


BASE_DIR = Path(__file__).resolve().parent.parent
UI_DIR = BASE_DIR / "UI"

SESSIONS = {}


def hash_password(password, salt=None):
    salt = salt or token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return {
        "salt": base64.b64encode(salt).decode("ascii"),
        "hash": base64.b64encode(digest).decode("ascii"),
    }


def verify_password(password, password_record):
    salt = base64.b64decode(password_record["salt"])
    expected = base64.b64decode(password_record["hash"])
    actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return hmac.compare_digest(actual, expected)


def make_user(user_id, password, name, role):
    return {
        "id": user_id,
        "name": name,
        "role": role,
        "password": hash_password(password),
    }


USERS = {
    "admin": make_user("admin", "1234", "관리자", "관리자"),
    "leader": make_user("leader", "1234", "팀장", "팀장"),
    "staff": make_user("staff", "1234", "사원", "사원"),
}


def json_bytes(data):
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def get_cookie(headers, name):
    cookie_header = headers.get("Cookie", "")
    for item in cookie_header.split(";"):
        key, _, value = item.strip().partition("=")
        if key == name:
            return value
    return None


class AppHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith("/api/"):
            self.handle_api_get()
            return

        self.serve_static_file()

    def do_POST(self):
        if self.path.startswith("/api/"):
            self.handle_api_post()
            return

        self.send_error(HTTPStatus.NOT_FOUND)

    def handle_api_get(self):
        if self.path == "/api/me":
            user = self.current_user()
            if not user:
                self.send_json({"ok": False, "message": "로그인이 필요합니다."}, HTTPStatus.UNAUTHORIZED)
                return

            self.send_json({"ok": True, "user": user})
            return

        self.send_json({"ok": False, "message": "없는 API입니다."}, HTTPStatus.NOT_FOUND)

    def handle_api_post(self):
        if self.path == "/api/login":
            body = self.read_json_body()
            user_id = body.get("userId", "")
            password = body.get("password", "")
            user = USERS.get(user_id)

            if not user or not verify_password(password, user["password"]):
                self.send_json(
                    {"ok": False, "message": "아이디 또는 비밀번호가 올바르지 않습니다."},
                    HTTPStatus.UNAUTHORIZED,
                )
                return

            session_id = token_urlsafe(32)
            SESSIONS[session_id] = {
                "id": user["id"],
                "name": user["name"],
                "role": user["role"],
            }
            self.send_json(
                {"ok": True, "message": "로그인 성공", "user": SESSIONS[session_id]},
                headers={"Set-Cookie": f"session_id={session_id}; Path=/; HttpOnly; SameSite=Lax"},
            )
            return

        if self.path == "/api/register":
            body = self.read_json_body()
            user_id = body.get("userId", "").strip()
            password = body.get("password", "")
            name = body.get("name", "").strip()
            role = body.get("role", "사원")

            if not user_id or not password or not name:
                self.send_json(
                    {"ok": False, "message": "이름, 아이디, 비밀번호를 모두 입력하세요."},
                    HTTPStatus.BAD_REQUEST,
                )
                return

            if user_id in USERS:
                self.send_json(
                    {"ok": False, "message": "이미 존재하는 아이디입니다."},
                    HTTPStatus.CONFLICT,
                )
                return

            USERS[user_id] = make_user(user_id, password, name, role)
            self.send_json({"ok": True, "message": "회원가입이 완료되었습니다."}, HTTPStatus.CREATED)
            return

        if self.path == "/api/logout":
            session_id = get_cookie(self.headers, "session_id")
            if session_id:
                SESSIONS.pop(session_id, None)

            self.send_json(
                {"ok": True, "message": "로그아웃 되었습니다."},
                headers={"Set-Cookie": "session_id=; Path=/; Max-Age=0; SameSite=Lax"},
            )
            return

        self.send_json({"ok": False, "message": "없는 API입니다."}, HTTPStatus.NOT_FOUND)

    def current_user(self):
        session_id = get_cookie(self.headers, "session_id")
        if not session_id:
            return None

        return SESSIONS.get(session_id)

    def read_json_body(self):
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length).decode("utf-8")
        if not raw_body:
            return {}

        try:
            return json.loads(raw_body)
        except json.JSONDecodeError:
            return {}

    def serve_static_file(self):
        path = unquote(self.path.split("?", 1)[0])
        if path in ("", "/"):
            path = "/UI/login_ui.html"

        if path.startswith("/UI/"):
            file_path = (BASE_DIR / path.lstrip("/")).resolve()
        else:
            file_path = (UI_DIR / path.lstrip("/")).resolve()

        if not str(file_path).startswith(str(BASE_DIR)) or not file_path.is_file():
            self.send_error(HTTPStatus.NOT_FOUND)
            return

        content_type = self.get_content_type(file_path)
        body = file_path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, data, status=HTTPStatus.OK, headers=None):
        body = json_bytes(data)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        if headers:
            for key, value in headers.items():
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def get_content_type(self, file_path):
        suffix = file_path.suffix.lower()
        if suffix == ".html":
            return "text/html; charset=utf-8"
        if suffix == ".css":
            return "text/css; charset=utf-8"
        if suffix == ".js":
            return "text/javascript; charset=utf-8"
        return "application/octet-stream"


def run():
    server = ThreadingHTTPServer(("127.0.0.1", 8000), AppHandler)
    print("Python server running: http://127.0.0.1:8000")
    print("Login test accounts: admin / 1234, leader / 1234, staff / 1234")
    server.serve_forever()


if __name__ == "__main__":
    run()

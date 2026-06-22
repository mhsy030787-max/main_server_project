from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
from secrets import token_bytes, token_urlsafe
import time
from urllib.parse import unquote, urlparse

try:
    import pymysql
except ImportError:
    pymysql = None


BASE_DIR = Path(__file__).resolve().parent.parent
UI_DIR = BASE_DIR / "UI"


def load_local_env(env_path):
    if not env_path.is_file():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


load_local_env(BASE_DIR / ".env")

LOGIN_ATTEMPTS = {}


def env_int(name, default):
    try:
        return int(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def load_jwt_secret():
    secret = os.environ.get("JWT_SECRET") or os.environ.get("SECRET_KEY")
    if secret:
        return secret.encode("utf-8")

    print(
        "JWT_SECRET 환경변수가 없어 임시 키를 사용합니다. "
        "Render 운영환경에는 반드시 JWT_SECRET을 설정하세요.",
        flush=True,
    )
    return token_bytes(32)


def load_password_pepper():
    pepper = os.environ.get("PASSWORD_PEPPER", "")
    if pepper:
        return pepper

    print(
        "PASSWORD_PEPPER 환경변수가 없습니다. "
        "Render 운영환경에는 반드시 PASSWORD_PEPPER를 설정하세요.",
        flush=True,
    )
    return ""


JWT_SECRET = load_jwt_secret()
PASSWORD_PEPPER = load_password_pepper()
ACCESS_TOKEN_SECONDS = env_int("ACCESS_TOKEN_SECONDS", 15 * 60)
REFRESH_TOKEN_SECONDS = env_int("REFRESH_TOKEN_SECONDS", 7 * 24 * 60 * 60)
LOGIN_LIMIT_COUNT = env_int("LOGIN_LIMIT_COUNT", 5)
LOGIN_LIMIT_WINDOW_SECONDS = env_int("LOGIN_LIMIT_WINDOW_SECONDS", 10 * 60)
COOKIE_SECURE = (
    os.environ.get("COOKIE_SECURE", "").lower() in {"1", "true", "yes"}
    or os.environ.get("RENDER", "").lower() == "true"
)


def password_bytes(password, use_pepper=True):
    if use_pepper:
        return f"{password}{PASSWORD_PEPPER}".encode("utf-8")
    return password.encode("utf-8")


def hash_password(password, salt=None):
    salt = salt or token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password_bytes(password), salt, 120_000)
    return {
        "salt": base64.b64encode(salt).decode("ascii"),
        "hash": base64.b64encode(digest).decode("ascii"),
    }


def verify_password(password, password_record):
    salt = base64.b64decode(password_record["salt"])
    expected = base64.b64decode(password_record["hash"])
    actual = hashlib.pbkdf2_hmac("sha256", password_bytes(password), salt, 120_000)
    if hmac.compare_digest(actual, expected):
        return True

    legacy_actual = hashlib.pbkdf2_hmac("sha256", password_bytes(password, False), salt, 120_000)
    return hmac.compare_digest(legacy_actual, expected)


def make_user(user_id, password, name, role):
    return {
        "id": user_id,
        "name": name,
        "role": role,
        "password": hash_password(password),
    }


DEFAULT_USERS = {
    "admin": make_user("admin", "1234", "관리자", "관리자"),
    "leader": make_user("leader", "1234", "팀장", "팀장"),
    "staff": make_user("staff", "1234", "사원", "사원"),
}


class MemoryUserStore:
    storage_type = "memory"

    def __init__(self):
        self.users = dict(DEFAULT_USERS)

    def get_user(self, user_id):
        return self.users.get(user_id)

    def user_exists(self, user_id):
        return user_id in self.users

    def create_user(self, user_id, password, name, role):
        self.users[user_id] = make_user(user_id, password, name, role)


class MemorySessionStore:
    storage_type = "memory"

    def __init__(self):
        self.sessions = {}

    def create_session(self, session_id, user, refresh_hash, created_at, refresh_expires_at):
        self.sessions[session_id] = {
            "sessionId": session_id,
            "user": public_user(user),
            "refreshHash": refresh_hash,
            "createdAt": created_at,
            "refreshExpiresAt": refresh_expires_at,
            "revoked": False,
        }

    def get_session(self, session_id):
        return self.sessions.get(session_id)

    def list_sessions_for_user(self, user_id):
        return [
            session
            for session in self.sessions.values()
            if session["user"]["id"] == user_id
        ]

    def update_refresh_token(self, session_id, refresh_hash, refresh_expires_at):
        session = self.sessions.get(session_id)
        if session:
            session["refreshHash"] = refresh_hash
            session["refreshExpiresAt"] = refresh_expires_at

    def revoke_session(self, session_id):
        self.sessions.pop(session_id, None)

    def find_by_refresh_hash(self, refresh_hash):
        now = int(time.time())
        for session_id, session in list(self.sessions.items()):
            if session.get("refreshExpiresAt", 0) < now:
                self.sessions.pop(session_id, None)
                continue
            if session.get("revoked"):
                continue
            if hmac.compare_digest(session.get("refreshHash", ""), refresh_hash):
                return session
        return None


class MySQLUserStore:
    storage_type = "mysql"

    def __init__(self, config):
        if pymysql is None:
            raise RuntimeError("PyMySQL이 설치되어 있지 않습니다.")
        self.config = config
        self.ensure_schema()
        self.seed_default_users()

    def connect(self):
        return pymysql.connect(
            **self.config,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
            autocommit=True,
        )

    def ensure_schema(self):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS users (
                        user_id VARCHAR(64) PRIMARY KEY,
                        name VARCHAR(80) NOT NULL,
                        role VARCHAR(30) NOT NULL,
                        password_salt VARCHAR(128) NOT NULL,
                        password_hash VARCHAR(128) NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                            ON UPDATE CURRENT_TIMESTAMP
                    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS auth_sessions (
                        session_id VARCHAR(128) PRIMARY KEY,
                        user_id VARCHAR(64) NOT NULL,
                        user_name VARCHAR(80) NOT NULL,
                        user_role VARCHAR(30) NOT NULL,
                        refresh_hash CHAR(64) NOT NULL,
                        created_at BIGINT NOT NULL,
                        refresh_expires_at BIGINT NOT NULL,
                        revoked TINYINT(1) NOT NULL DEFAULT 0,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                            ON UPDATE CURRENT_TIMESTAMP,
                        INDEX idx_auth_sessions_user_id (user_id),
                        INDEX idx_auth_sessions_refresh_hash (refresh_hash),
                        INDEX idx_auth_sessions_expires_at (refresh_expires_at)
                    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                    """
                )

    def seed_default_users(self):
        for user in DEFAULT_USERS.values():
            if not self.user_exists(user["id"]):
                self.insert_user(user)

    def row_to_user(self, row):
        if not row:
            return None
        return {
            "id": row["user_id"],
            "name": row["name"],
            "role": row["role"],
            "password": {
                "salt": row["password_salt"],
                "hash": row["password_hash"],
            },
        }

    def get_user(self, user_id):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_id, name, role, password_salt, password_hash
                    FROM users
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                return self.row_to_user(cursor.fetchone())

    def user_exists(self, user_id):
        return self.get_user(user_id) is not None

    def create_user(self, user_id, password, name, role):
        self.insert_user(make_user(user_id, password, name, role))

    def insert_user(self, user):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO users
                        (user_id, name, role, password_salt, password_hash)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        user["id"],
                        user["name"],
                        user["role"],
                        user["password"]["salt"],
                        user["password"]["hash"],
                    ),
                )


class MySQLSessionStore:
    storage_type = "mysql"

    def __init__(self, user_store):
        self.user_store = user_store
        self.cleanup_expired_sessions()

    def connect(self):
        return self.user_store.connect()

    def row_to_session(self, row):
        if not row:
            return None
        return {
            "sessionId": row["session_id"],
            "user": {
                "id": row["user_id"],
                "name": row["user_name"],
                "role": row["user_role"],
            },
            "refreshHash": row["refresh_hash"],
            "createdAt": int(row["created_at"]),
            "refreshExpiresAt": int(row["refresh_expires_at"]),
            "revoked": bool(row["revoked"]),
        }

    def cleanup_expired_sessions(self):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM auth_sessions WHERE refresh_expires_at < %s OR revoked = 1",
                    (int(time.time()),),
                )

    def create_session(self, session_id, user, refresh_hash, created_at, refresh_expires_at):
        public = public_user(user)
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO auth_sessions
                        (session_id, user_id, user_name, user_role, refresh_hash, created_at, refresh_expires_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        session_id,
                        public["id"],
                        public["name"],
                        public["role"],
                        refresh_hash,
                        created_at,
                        refresh_expires_at,
                    ),
                )

    def get_session(self, session_id):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT session_id, user_id, user_name, user_role, refresh_hash,
                           created_at, refresh_expires_at, revoked
                    FROM auth_sessions
                    WHERE session_id = %s
                    """,
                    (session_id,),
                )
                return self.row_to_session(cursor.fetchone())

    def list_sessions_for_user(self, user_id):
        self.cleanup_expired_sessions()
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT session_id, user_id, user_name, user_role, refresh_hash,
                           created_at, refresh_expires_at, revoked
                    FROM auth_sessions
                    WHERE user_id = %s
                    ORDER BY created_at DESC
                    """,
                    (user_id,),
                )
                return [self.row_to_session(row) for row in cursor.fetchall()]

    def update_refresh_token(self, session_id, refresh_hash, refresh_expires_at):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE auth_sessions
                    SET refresh_hash = %s, refresh_expires_at = %s, revoked = 0
                    WHERE session_id = %s
                    """,
                    (refresh_hash, refresh_expires_at, session_id),
                )

    def revoke_session(self, session_id):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE auth_sessions SET revoked = 1 WHERE session_id = %s",
                    (session_id,),
                )

    def find_by_refresh_hash(self, refresh_hash):
        self.cleanup_expired_sessions()
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT session_id, user_id, user_name, user_role, refresh_hash,
                           created_at, refresh_expires_at, revoked
                    FROM auth_sessions
                    WHERE refresh_hash = %s AND revoked = 0 AND refresh_expires_at >= %s
                    LIMIT 1
                    """,
                    (refresh_hash, int(time.time())),
                )
                return self.row_to_session(cursor.fetchone())


def mysql_config_from_env():
    database_url = os.environ.get("DATABASE_URL", "")
    if database_url.startswith(("mysql://", "mysql+pymysql://")):
        parsed = urlparse(database_url.replace("mysql+pymysql://", "mysql://", 1))
        config = {
            "host": parsed.hostname,
            "port": parsed.port or 3306,
            "user": unquote(parsed.username or ""),
            "password": unquote(parsed.password or ""),
            "database": parsed.path.lstrip("/"),
        }
        if "SSL-MODE=REQUIRED" in parsed.query.upper() or parsed.hostname and "aivencloud.com" in parsed.hostname:
            config["ssl"] = {}
        return config

    host = os.environ.get("MYSQL_HOST") or os.environ.get("MYSQLHOST")
    database = os.environ.get("MYSQL_DATABASE") or os.environ.get("MYSQLDATABASE")
    user = os.environ.get("MYSQL_USER") or os.environ.get("MYSQLUSER")
    password = os.environ.get("MYSQL_PASSWORD") or os.environ.get("MYSQLPASSWORD")
    port = os.environ.get("MYSQL_PORT") or os.environ.get("MYSQLPORT") or "3306"
    ssl_mode = (os.environ.get("MYSQL_SSL_MODE") or "").upper()

    if not all([host, database, user]):
        return None

    config = {
        "host": host,
        "port": int(port),
        "user": user,
        "password": password or "",
        "database": database,
    }
    if ssl_mode == "REQUIRED" or "aivencloud.com" in host:
        config["ssl"] = {}
    return config


MYSQL_CONNECTION_ERROR = None


def create_user_store():
    global MYSQL_CONNECTION_ERROR
    config = mysql_config_from_env()
    if not config:
        MYSQL_CONNECTION_ERROR = None
        print("MySQL 설정이 없어 메모리 사용자 저장소를 사용합니다.")
        return MemoryUserStore()

    try:
        print("MySQL 사용자 저장소를 사용합니다.")
        store = MySQLUserStore(config)
        MYSQL_CONNECTION_ERROR = None
        return store
    except Exception as error:
        MYSQL_CONNECTION_ERROR = str(error)
        print(f"MySQL 연결 실패로 메모리 사용자 저장소를 사용합니다: {error}", flush=True)
        return MemoryUserStore()


USER_STORE = create_user_store()


def create_session_store(user_store):
    if user_store.storage_type == "mysql":
        print("MySQL 세션 저장소를 사용합니다.")
        return MySQLSessionStore(user_store)

    print("메모리 세션 저장소를 사용합니다.")
    return MemorySessionStore()


SESSION_STORE = create_session_store(USER_STORE)


def json_bytes(data):
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def b64url_encode(value):
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def b64url_decode(value):
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def make_jwt(payload):
    header = {"alg": "HS256", "typ": "JWT"}
    encoded_header = b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    encoded_payload = b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
    signature = hmac.new(JWT_SECRET, signing_input, hashlib.sha256).digest()
    return f"{encoded_header}.{encoded_payload}.{b64url_encode(signature)}"


def verify_jwt(token):
    try:
        encoded_header, encoded_payload, encoded_signature = token.split(".")
        signing_input = f"{encoded_header}.{encoded_payload}".encode("ascii")
        expected_signature = hmac.new(JWT_SECRET, signing_input, hashlib.sha256).digest()
        actual_signature = b64url_decode(encoded_signature)
        if not hmac.compare_digest(actual_signature, expected_signature):
            return None
        payload = json.loads(b64url_decode(encoded_payload).decode("utf-8"))
        if payload.get("exp", 0) < int(time.time()):
            return None
        return payload
    except (ValueError, json.JSONDecodeError, KeyError):
        return None


def public_user(user):
    return {
        "id": user["id"],
        "name": user["name"],
        "role": user["role"],
    }


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


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


def make_access_token(user, session_id):
    now = int(time.time())
    return make_jwt({
        "sub": user["id"],
        "name": user["name"],
        "role": user["role"],
        "sid": session_id,
        "iat": now,
        "exp": now + ACCESS_TOKEN_SECONDS,
    })


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


class AppHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        origin = self.headers.get("Origin")
        allowed_origins = {
            "http://127.0.0.1:5500",
            "http://localhost:5500",
            "http://127.0.0.1:5501",
            "http://localhost:5501",
        }
        if origin in allowed_origins:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.end_headers()

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
        if self.path == "/api/health":
            self.send_json({
                "ok": True,
                "storage": USER_STORE.storage_type,
                "sessionStorage": SESSION_STORE.storage_type,
                "mysqlConfigured": mysql_config_from_env() is not None,
                "passwordPepperConfigured": bool(PASSWORD_PEPPER),
            })
            return

        if self.path == "/api/me":
            user = self.current_user()
            if not user:
                self.send_json({"ok": False, "message": "로그인이 필요합니다."}, HTTPStatus.UNAUTHORIZED)
                return

            self.send_json({"ok": True, "user": user})
            return

        if self.path == "/api/sessions":
            user = self.current_user()
            if not user:
                self.send_json({"ok": False, "message": "로그인이 필요합니다."}, HTTPStatus.UNAUTHORIZED)
                return

            self.send_json({
                "ok": True,
                "sessions": [
                    {
                        "sessionId": session_id,
                        "userId": session["user"]["id"],
                        "name": session["user"]["name"],
                        "role": session["user"]["role"],
                        "createdAt": session["createdAt"],
                        "expiresAt": session["refreshExpiresAt"],
                        "active": not session.get("revoked", False),
                    }
                    for session in SESSION_STORE.list_sessions_for_user(user["id"])
                    for session_id in [session["sessionId"]]
                ],
            })
            return

        self.send_json({"ok": False, "message": "없는 API입니다."}, HTTPStatus.NOT_FOUND)

    def handle_api_post(self):
        if self.path == "/api/login":
            body = self.read_json_body()
            user_id = body.get("userId", "")
            password = body.get("password", "")
            client_ip = self.client_address[0]

            if login_is_limited(client_ip, user_id):
                self.send_json(
                    {"ok": False, "message": "로그인 실패가 많습니다. 잠시 후 다시 시도하세요."},
                    HTTPStatus.TOO_MANY_REQUESTS,
                )
                return

            user = USER_STORE.get_user(user_id)

            if not user or not verify_password(password, user["password"]):
                remember_failed_login(client_ip, user_id)
                self.send_json(
                    {"ok": False, "message": "아이디 또는 비밀번호가 올바르지 않습니다."},
                    HTTPStatus.UNAUTHORIZED,
                )
                return

            clear_failed_login(client_ip, user_id)
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
            self.send_json(
                make_auth_payload(user, session_id),
                headers={"Set-Cookie": auth_cookie(refresh_token)},
            )
            return

        if self.path == "/api/refresh":
            session = self.current_session_from_refresh()
            if not session:
                self.send_json(
                    {"ok": False, "message": "다시 로그인이 필요합니다."},
                    HTTPStatus.UNAUTHORIZED,
                    headers={"Set-Cookie": clear_refresh_cookie()},
                )
                return

            session_id, session_data = session
            user = session_data["user"]
            new_refresh_token = make_refresh_token()
            refresh_expires_at = int(time.time()) + REFRESH_TOKEN_SECONDS
            SESSION_STORE.update_refresh_token(
                session_id,
                hash_token(new_refresh_token),
                refresh_expires_at,
            )
            self.send_json(
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

            if USER_STORE.user_exists(user_id):
                self.send_json(
                    {"ok": False, "message": "이미 존재하는 아이디입니다."},
                    HTTPStatus.CONFLICT,
                )
                return

            USER_STORE.create_user(user_id, password, name, role)
            self.send_json({"ok": True, "message": "회원가입이 완료되었습니다."}, HTTPStatus.CREATED)
            return

        if self.path == "/api/logout":
            session_id = self.current_session_id()
            if session_id:
                SESSION_STORE.revoke_session(session_id)

            self.send_json(
                {"ok": True, "message": "로그아웃 되었습니다."},
                headers={"Set-Cookie": clear_refresh_cookie()},
            )
            return

        if self.path == "/api/sessions/revoke":
            user = self.current_user()
            if not user:
                self.send_json({"ok": False, "message": "로그인이 필요합니다."}, HTTPStatus.UNAUTHORIZED)
                return

            body = self.read_json_body()
            target_session_id = body.get("sessionId", "")
            session = SESSION_STORE.get_session(target_session_id)
            if not session or session["user"]["id"] != user["id"]:
                self.send_json({"ok": False, "message": "세션을 찾을 수 없습니다."}, HTTPStatus.NOT_FOUND)
                return

            SESSION_STORE.revoke_session(target_session_id)
            self.send_json({"ok": True, "message": "세션을 종료했습니다."})
            return

        self.send_json({"ok": False, "message": "없는 API입니다."}, HTTPStatus.NOT_FOUND)

    def current_user(self):
        session_id = self.current_session_id()
        if not session_id:
            return None

        session = SESSION_STORE.get_session(session_id)
        if not session or session.get("revoked"):
            return None

        return session["user"]

    def current_session_id(self):
        auth_header = self.headers.get("Authorization", "")
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

    def current_session_from_refresh(self):
        refresh_token = get_cookie(self.headers, "refresh_token")
        if not refresh_token:
            return None

        refresh_hash = hash_token(refresh_token)
        session = SESSION_STORE.find_by_refresh_hash(refresh_hash)
        if not session:
            return None
        return session["sessionId"], session

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
    host = os.environ.get("HOST", "127.0.0.1")
    port = int(os.environ.get("PORT", "8000"))
    server = ThreadingHTTPServer((host, port), AppHandler)
    print(f"Python server running: http://{host}:{port}")
    print("Login test accounts: admin / 1234, leader / 1234, staff / 1234")
    server.serve_forever()


if __name__ == "__main__":
    run()

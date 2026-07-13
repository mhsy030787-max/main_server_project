import hmac
import os
import time
from threading import RLock
from urllib.parse import unquote, urlparse

from auth.users import DEFAULT_USERS, make_user, public_user
from security.passwords import hash_password
from security.jwt import hash_token

try:
    import pymysql
except ImportError:
    pymysql = None


MYSQL_CONNECTION_ERROR = None


class DuplicateUserError(Exception):
    pass


class MemoryUserStore:
    storage_type = "memory"

    def __init__(self):
        self.users = dict(DEFAULT_USERS)
        self.lock = RLock()

    def get_user(self, user_id):
        return self.users.get(user_id)

    def user_exists(self, user_id):
        return user_id in self.users

    def create_user(self, user_id, password, name, role, email=None):
        with self.lock:
            if user_id in self.users:
                raise DuplicateUserError(user_id)
            self.users[user_id] = make_user(user_id, password, name, role, email)

    def find_user_for_reset(self, user_id, email):
        user = self.users.get(user_id)
        if user and user.get("email") == email:
            return user
        return None

    def update_password(self, user_id, password):
        with self.lock:
            self.users[user_id]["password"] = hash_password(password)


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

    def revoke_all_for_user(self, user_id):
        for session_id, session in list(self.sessions.items()):
            if session["user"]["id"] == user_id:
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
                        email VARCHAR(254) NULL,
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
                    SELECT COUNT(*) AS count
                    FROM information_schema.COLUMNS
                    WHERE TABLE_SCHEMA = DATABASE()
                      AND TABLE_NAME = 'users'
                      AND COLUMN_NAME = 'email'
                    """
                )
                if cursor.fetchone()["count"] == 0:
                    cursor.execute("ALTER TABLE users ADD COLUMN email VARCHAR(254) NULL AFTER role")
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
            "email": row.get("email"),
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
                    SELECT user_id, name, role, email, password_salt, password_hash
                    FROM users
                    WHERE user_id = %s
                    """,
                    (user_id,),
                )
                return self.row_to_user(cursor.fetchone())

    def user_exists(self, user_id):
        return self.get_user(user_id) is not None

    def create_user(self, user_id, password, name, role, email=None):
        self.insert_user(make_user(user_id, password, name, role, email))

    def find_user_for_reset(self, user_id, email):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT user_id, name, role, email, password_salt, password_hash
                    FROM users WHERE user_id = %s AND email = %s
                    """,
                    (user_id, email),
                )
                return self.row_to_user(cursor.fetchone())

    def update_password(self, user_id, password):
        record = hash_password(password)
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE users SET password_salt = %s, password_hash = %s
                    WHERE user_id = %s
                    """,
                    (record["salt"], record["hash"], user_id),
                )

    def insert_user(self, user):
        try:
            with self.connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO users
                            (user_id, name, role, email, password_salt, password_hash)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (
                            user["id"],
                            user["name"],
                            user["role"],
                            user.get("email"),
                            user["password"]["salt"],
                            user["password"]["hash"],
                        ),
                    )
        except pymysql.err.IntegrityError as error:
            if error.args and error.args[0] == 1062:
                raise DuplicateUserError(user["id"]) from error
            raise


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

    def revoke_all_for_user(self, user_id):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE auth_sessions SET revoked = 1 WHERE user_id = %s",
                    (user_id,),
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


def create_session_store(user_store):
    if user_store.storage_type == "mysql":
        print("MySQL 세션 저장소를 사용합니다.")
        return MySQLSessionStore(user_store)

    print("메모리 세션 저장소를 사용합니다.")
    return MemorySessionStore()


USER_STORE = create_user_store()
SESSION_STORE = create_session_store(USER_STORE)

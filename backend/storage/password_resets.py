import hashlib
import time
from threading import RLock


class MemoryPasswordResetStore:
    storage_type = "memory"

    def __init__(self):
        self.tokens = {}
        self.lock = RLock()

    def create(self, token, user_id, expires_at):
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self.lock:
            self.tokens[token_hash] = {
                "userId": user_id,
                "expiresAt": expires_at,
                "used": False,
            }

    def consume(self, token):
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self.lock:
            record = self.tokens.get(token_hash)
            if not record or record["used"] or record["expiresAt"] < int(time.time()):
                return None
            record["used"] = True
            return record["userId"]


class MySQLPasswordResetStore:
    storage_type = "mysql"

    def __init__(self, user_store):
        self.user_store = user_store
        self.ensure_schema()

    def connect(self):
        return self.user_store.connect()

    def ensure_schema(self):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS password_reset_tokens (
                        token_hash CHAR(64) PRIMARY KEY,
                        user_id VARCHAR(64) NOT NULL,
                        expires_at BIGINT NOT NULL,
                        used TINYINT(1) NOT NULL DEFAULT 0,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_password_reset_user_id (user_id),
                        INDEX idx_password_reset_expires_at (expires_at)
                    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                    """
                )

    def create(self, token, user_id, expires_at):
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM password_reset_tokens WHERE user_id = %s OR expires_at < %s",
                    (user_id, int(time.time())),
                )
                cursor.execute(
                    """
                    INSERT INTO password_reset_tokens (token_hash, user_id, expires_at)
                    VALUES (%s, %s, %s)
                    """,
                    (token_hash, user_id, expires_at),
                )

    def consume(self, token):
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        with self.connect() as connection:
            connection.begin()
            try:
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        SELECT user_id FROM password_reset_tokens
                        WHERE token_hash = %s AND used = 0 AND expires_at >= %s
                        FOR UPDATE
                        """,
                        (token_hash, int(time.time())),
                    )
                    record = cursor.fetchone()
                    if not record:
                        connection.rollback()
                        return None
                    cursor.execute(
                        "UPDATE password_reset_tokens SET used = 1 WHERE token_hash = %s",
                        (token_hash,),
                    )
                connection.commit()
                return record["user_id"]
            except Exception:
                connection.rollback()
                raise


def create_password_reset_store(user_store):
    if user_store.storage_type == "mysql":
        return MySQLPasswordResetStore(user_store)
    return MemoryPasswordResetStore()

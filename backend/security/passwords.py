import base64
import hashlib
import hmac
from secrets import token_bytes


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

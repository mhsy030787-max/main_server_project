import base64
import hashlib
import hmac
import json
import time

from settings import ACCESS_TOKEN_SECONDS, JWT_SECRET


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


def hash_token(token):
    return hashlib.sha256(token.encode("utf-8")).hexdigest()

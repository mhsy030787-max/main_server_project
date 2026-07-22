import os
from pathlib import Path
from secrets import token_bytes


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


load_local_env(BASE_DIR / ".env")

JWT_SECRET = load_jwt_secret()
ACCESS_TOKEN_SECONDS = env_int("ACCESS_TOKEN_SECONDS", 15 * 60)
REFRESH_TOKEN_SECONDS = env_int("REFRESH_TOKEN_SECONDS", 7 * 24 * 60 * 60)
PASSWORD_RESET_SECONDS = env_int("PASSWORD_RESET_SECONDS", 15 * 60)
MAIL_ATTACHMENT_MAX_BYTES = env_int("MAIL_ATTACHMENT_MAX_BYTES", 5 * 1024 * 1024)
MAIL_INBOUND_MAX_BYTES = env_int("MAIL_INBOUND_MAX_BYTES", 12 * 1024 * 1024)
LOGIN_LIMIT_COUNT = env_int("LOGIN_LIMIT_COUNT", 5)
LOGIN_LIMIT_WINDOW_SECONDS = env_int("LOGIN_LIMIT_WINDOW_SECONDS", 10 * 60)
COOKIE_SECURE = (
    os.environ.get("COOKIE_SECURE", "").lower() in {"1", "true", "yes"}
    or os.environ.get("RENDER", "").lower() == "true"
)
PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "").strip()
MAIL_PROVIDER = os.environ.get("MAIL_PROVIDER", "resend").strip().lower()
RESEND_API_KEY = os.environ.get("RESEND_API_KEY", "").strip()
RESEND_WEBHOOK_SECRET = os.environ.get("RESEND_WEBHOOK_SECRET", "").strip()
RESEND_FROM_DOMAIN = os.environ.get("RESEND_FROM_DOMAIN", "").strip().lower()
RESEND_FROM_ADDRESS = os.environ.get("RESEND_FROM_ADDRESS", "").strip().lower()
RESEND_API_BASE_URL = os.environ.get(
    "RESEND_API_BASE_URL", "https://api.resend.com"
).strip().rstrip("/")
SMTP_HOST = os.environ.get("SMTP_HOST", "").strip()
SMTP_PORT = env_int("SMTP_PORT", 587)
SMTP_USER = os.environ.get("SMTP_USER", "").strip()
SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
SMTP_SENDER = os.environ.get("SMTP_SENDER", SMTP_USER).strip()
SMTP_STARTTLS = os.environ.get("SMTP_STARTTLS", "true").lower() in {"1", "true", "yes"}
SMTP_SSL = os.environ.get("SMTP_SSL", "false").lower() in {"1", "true", "yes"}
SMTP_TIMEOUT_SECONDS = env_int("SMTP_TIMEOUT_SECONDS", 20)
MAIL_PUBLIC_DOMAIN = os.environ.get(
    "MAIL_PUBLIC_DOMAIN", RESEND_FROM_DOMAIN
).strip().lower()
MAIL_INBOUND_SECRET = os.environ.get("MAIL_INBOUND_SECRET", "")
MAIL_ALLOW_CLASSIFIED_EXTERNAL = os.environ.get(
    "MAIL_ALLOW_CLASSIFIED_EXTERNAL", "false"
).lower() in {"1", "true", "yes"}
EXPOSE_RESET_LINK = os.environ.get(
    "EXPOSE_RESET_LINK",
    "false" if os.environ.get("RENDER", "").lower() == "true" else "true",
).lower() in {"1", "true", "yes"}

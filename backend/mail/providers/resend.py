import base64
import json
from email.headerregistry import Address
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from settings import (
    MAIL_PUBLIC_DOMAIN,
    RESEND_API_BASE_URL,
    RESEND_API_KEY,
    RESEND_FROM_ADDRESS,
    RESEND_FROM_DOMAIN,
    SMTP_TIMEOUT_SECONDS,
)

from .base import ExternalMailError, ExternalMailNotConfigured


NAME = "resend"


def sending_domain():
    return RESEND_FROM_DOMAIN or MAIL_PUBLIC_DOMAIN


def configured():
    return bool(RESEND_API_KEY and (RESEND_FROM_ADDRESS or sending_domain()))


def test_mode():
    return RESEND_FROM_ADDRESS == "onboarding@resend.dev" and not sending_domain()


def public_address(user_id):
    domain = sending_domain()
    if domain:
        return f"{user_id}@{domain}"
    return RESEND_FROM_ADDRESS


def sender_value(sender):
    address = public_address(sender["id"])
    if RESEND_FROM_ADDRESS:
        address = RESEND_FROM_ADDRESS
    if not address:
        raise ExternalMailNotConfigured("Resend 발신 도메인이 설정되지 않았습니다.")
    display_name = str(sender.get("name") or "DataVault").replace("\r", " ").replace("\n", " ")
    local_part, domain = address.rsplit("@", 1)
    return str(Address(display_name=display_name, username=local_part, domain=domain))


def request_json(path, method="GET", payload=None):
    if not RESEND_API_KEY:
        raise ExternalMailNotConfigured("Resend API 키가 설정되지 않았습니다.")
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = Request(
        f"{RESEND_API_BASE_URL}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "DataVault/1.0",
        },
    )
    try:
        with urlopen(request, timeout=SMTP_TIMEOUT_SECONDS) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        try:
            detail = json.loads(error.read().decode("utf-8")).get("message")
        except (UnicodeDecodeError, json.JSONDecodeError, AttributeError):
            detail = None
        message = detail or f"Resend API가 요청을 거부했습니다. (HTTP {error.code})"
        raise ExternalMailError(message) from error
    except (URLError, TimeoutError, OSError) as error:
        raise ExternalMailError("Resend API에 연결하지 못했습니다.") from error


def send(sender, recipient, subject, body, attachment=None):
    if not configured():
        raise ExternalMailNotConfigured("Resend 외부 메일 설정이 완료되지 않았습니다.")
    payload = {
        "from": sender_value(sender),
        "to": [recipient],
        "subject": subject,
        "text": body,
        "reply_to": public_address(sender["id"]),
    }
    if attachment:
        payload["attachments"] = [{
            "content": base64.b64encode(attachment["data"]).decode("ascii"),
            "filename": attachment["name"],
        }]
    result = request_json("/emails", method="POST", payload=payload)
    message_id = str(result.get("id") or "").strip()
    if not message_id:
        raise ExternalMailError("Resend가 발송 번호를 반환하지 않았습니다.")
    return message_id

import base64
import binascii
import hashlib
import hmac
import json
import time
from email.utils import parseaddr
from html.parser import HTMLParser
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from mail.providers import provider_name
from mail.providers.resend import request_json
from mail.store import (
    MAIL_STORE,
    RecipientNotFoundError,
    normalize_external_address,
    user_id_from_public_address,
)
from settings import (
    MAIL_ATTACHMENT_MAX_BYTES,
    MAIL_INBOUND_MAX_BYTES,
    MAIL_INBOUND_SECRET,
    RESEND_API_KEY,
    RESEND_WEBHOOK_SECRET,
    SMTP_TIMEOUT_SECONDS,
)


class InboundMailError(Exception):
    pass


class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def text(self):
        return " ".join("".join(self.parts).split())


def inbound_enabled():
    if provider_name() == "resend":
        return bool(RESEND_API_KEY and RESEND_WEBHOOK_SECRET)
    return bool(MAIL_INBOUND_SECRET)


def verify_generic_signature(raw_body, signature):
    if not MAIL_INBOUND_SECRET or not signature:
        return False
    supplied = signature.removeprefix("sha256=").strip().lower()
    expected = hmac.new(
        MAIL_INBOUND_SECRET.encode("utf-8"), raw_body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, supplied)


def verify_resend_signature(raw_body, headers):
    message_id = headers.get("svix-id", "")
    timestamp = headers.get("svix-timestamp", "")
    signatures = headers.get("svix-signature", "")
    if not RESEND_WEBHOOK_SECRET or not message_id or not timestamp or not signatures:
        return False
    try:
        unix_time = int(timestamp)
        secret = RESEND_WEBHOOK_SECRET.removeprefix("whsec_")
        key = base64.b64decode(secret, validate=True)
    except (ValueError, binascii.Error):
        return False
    if abs(int(time.time()) - unix_time) > 5 * 60:
        return False
    signed = f"{message_id}.{timestamp}.".encode("utf-8") + raw_body
    expected = base64.b64encode(hmac.new(key, signed, hashlib.sha256).digest()).decode("ascii")
    supplied = [item.split(",", 1)[1] for item in signatures.split() if item.startswith("v1,")]
    return any(hmac.compare_digest(expected, item) for item in supplied)


def decode_attachment(item):
    if not isinstance(item, dict):
        raise InboundMailError("수신 첨부 파일 형식이 올바르지 않습니다.")
    try:
        data = base64.b64decode(item.get("data", ""), validate=True)
    except (ValueError, binascii.Error) as error:
        raise InboundMailError("수신 첨부 파일 형식이 올바르지 않습니다.") from error
    if len(data) > MAIL_ATTACHMENT_MAX_BYTES:
        raise InboundMailError("수신 첨부 파일이 허용 크기를 초과했습니다.")
    return attachment_record(item, data)


def attachment_record(item, data):
    return {
        "name": str(item.get("filename") or item.get("name") or "attachment")
        .replace("/", "_").replace("\\", "_")[:255],
        "contentType": str(item.get("content_type") or item.get("contentType")
                           or "application/octet-stream")[:120],
        "size": len(data),
        "data": data,
    }


def download_attachment(url, metadata):
    try:
        request = Request(url, headers={"User-Agent": "DataVault/1.0"})
        with urlopen(request, timeout=SMTP_TIMEOUT_SECONDS) as response:
            declared = int(response.headers.get("Content-Length", "0") or 0)
            if declared > MAIL_ATTACHMENT_MAX_BYTES:
                raise InboundMailError("수신 첨부 파일이 허용 크기를 초과했습니다.")
            data = response.read(MAIL_ATTACHMENT_MAX_BYTES + 1)
    except InboundMailError:
        raise
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as error:
        raise InboundMailError("수신 첨부 파일을 가져오지 못했습니다.") from error
    if len(data) > MAIL_ATTACHMENT_MAX_BYTES:
        raise InboundMailError("수신 첨부 파일이 허용 크기를 초과했습니다.")
    return attachment_record(metadata, data)


def resend_attachments(email_id):
    result = request_json(f"/emails/receiving/{email_id}/attachments")
    attachments = []
    for item in result.get("data", [])[:5]:
        if item.get("download_url"):
            attachments.append(download_attachment(item["download_url"], item))
    return attachments


def text_body(email):
    if email.get("text"):
        return str(email["text"])[:65535]
    parser = TextExtractor()
    parser.feed(str(email.get("html") or ""))
    return parser.text()[:65535]


def receive_resend(payload):
    event_type = str(payload.get("type") or "")
    data = payload.get("data") or {}
    if event_type != "email.received":
        status_map = {
            "email.sent": "sent", "email.delivered": "delivered",
            "email.delivery_delayed": "delayed", "email.bounced": "bounced",
            "email.complained": "complained", "email.failed": "failed",
            "email.suppressed": "suppressed",
        }
        status = status_map.get(event_type)
        provider_id = str(data.get("email_id") or "")
        return MAIL_STORE.update_delivery_by_provider(provider_id, status) if status and provider_id else None

    email_id = str(data.get("email_id") or "").strip()
    if not email_id:
        raise InboundMailError("수신 메일 번호가 없습니다.")
    email = request_json(f"/emails/receiving/{email_id}")
    recipients = email.get("to") or data.get("to") or []
    if not recipients:
        raise InboundMailError("수신 주소가 없습니다.")
    recipient_address = str(recipients[0]).strip().lower()
    try:
        recipient_id = user_id_from_public_address(recipient_address)
        sender_address = normalize_external_address(email.get("from") or data.get("from"))
    except RecipientNotFoundError as error:
        raise InboundMailError(str(error)) from error
    raw_sender = str(email.get("headers", {}).get("from") or data.get("from") or sender_address)
    sender_name = parseaddr(raw_sender)[0] or sender_address
    return MAIL_STORE.receive_external(
        recipient_id=recipient_id,
        recipient_address=recipient_address,
        sender_address=sender_address,
        sender_name=sender_name[:120],
        subject=str(email.get("subject") or data.get("subject") or "(제목 없음)")[:200],
        body=text_body(email),
        provider_message_id=email_id,
        attachments=resend_attachments(email_id) if email.get("attachments") else [],
    )


def receive_generic(payload):
    try:
        recipient_id = user_id_from_public_address(payload.get("to"))
        sender_address = normalize_external_address(payload.get("from"))
    except RecipientNotFoundError as error:
        raise InboundMailError(str(error)) from error
    raw_attachments = payload.get("attachments") or []
    if not isinstance(raw_attachments, list):
        raise InboundMailError("수신 첨부 파일 목록이 올바르지 않습니다.")
    return MAIL_STORE.receive_external(
        recipient_id=recipient_id,
        recipient_address=str(payload.get("to") or "").strip().lower(),
        sender_address=sender_address,
        sender_name=str(payload.get("fromName") or sender_address).strip()[:120],
        subject=str(payload.get("subject") or "(제목 없음)").strip()[:200],
        body=str(payload.get("text") or payload.get("body") or "")[:65535],
        provider_message_id=str(payload.get("messageId") or "").strip()[:255] or None,
        attachments=[decode_attachment(item) for item in raw_attachments[:5]],
    )


def receive_webhook(handler):
    try:
        content_length = int(handler.headers.get("Content-Length", "0"))
    except ValueError as error:
        raise InboundMailError("잘못된 요청 크기입니다.") from error
    if content_length <= 0 or content_length > MAIL_INBOUND_MAX_BYTES:
        raise InboundMailError("수신 메일 요청 크기가 허용 범위를 벗어났습니다.")
    raw_body = handler.rfile.read(content_length)
    is_resend = bool(handler.headers.get("svix-id"))
    valid = verify_resend_signature(raw_body, handler.headers) if is_resend else verify_generic_signature(
        raw_body, handler.headers.get("X-DataVault-Signature", "")
    )
    if not valid:
        raise PermissionError("수신 메일 서명이 올바르지 않습니다.")
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise InboundMailError("수신 메일 JSON 형식이 올바르지 않습니다.") from error
    if not isinstance(payload, dict):
        raise InboundMailError("수신 메일 JSON 형식이 올바르지 않습니다.")
    return receive_resend(payload) if is_resend else receive_generic(payload)

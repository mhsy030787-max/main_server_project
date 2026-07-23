import base64
import binascii
from dataclasses import dataclass

from mail.store import (
    RecipientNotFoundError,
    internal_address,
    normalize_external_address,
    user_id_from_address,
)
from settings import MAIL_ATTACHMENT_MAX_BYTES


ALLOWED_GRADES = {"내부", "기밀", "최고기밀"}


class MailValidationError(ValueError):
    pass


@dataclass(frozen=True)
class Recipient:
    value: str
    address: str
    internal: bool


def validate_message_fields(payload, *, draft=False):
    subject = str(payload.get("subject", "")).strip()
    body = str(payload.get("body", "")).strip()
    grade = str(payload.get("grade", "내부")).strip()

    if len(subject) > 200 or (not draft and not subject):
        raise MailValidationError("제목은 1~200자로 입력하세요.")
    if len(body) > 65535 or (not draft and not body):
        raise MailValidationError("본문을 입력하세요.")
    if grade not in ALLOWED_GRADES:
        raise MailValidationError("올바른 보안 등급을 선택하세요.")
    return subject, body, grade


def resolve_recipient(raw_value, *, required=True, user_store=None):
    raw_address = str(raw_value or "").strip().lower()
    if not raw_address:
        if required:
            raise MailValidationError("받는 사람을 입력하세요.")
        return None

    internal = raw_address.endswith("@datavault.local")
    try:
        value = (
            user_id_from_address(raw_address, user_store=user_store)
            if internal else normalize_external_address(raw_address)
        )
    except RecipientNotFoundError as error:
        raise MailValidationError(str(error)) from error
    return Recipient(
        value=value,
        address=internal_address(value) if internal else value,
        internal=internal,
    )


def decode_attachment(raw_attachment):
    if not raw_attachment:
        return None
    if not isinstance(raw_attachment, dict):
        raise MailValidationError("첨부 파일 형식이 올바르지 않습니다.")

    try:
        data = base64.b64decode(raw_attachment.get("data", ""), validate=True)
    except (ValueError, TypeError, binascii.Error) as error:
        raise MailValidationError("첨부 파일 형식이 올바르지 않습니다.") from error
    if len(data) > MAIL_ATTACHMENT_MAX_BYTES:
        limit_mb = max(1, MAIL_ATTACHMENT_MAX_BYTES // (1024 * 1024))
        raise MailValidationError(f"첨부 파일은 {limit_mb}MB 이하만 가능합니다.")

    name = str(raw_attachment.get("name", "attachment"))
    name = name.replace("/", "_").replace("\\", "_").strip()[:255] or "attachment"
    return {
        "name": name,
        "contentType": str(raw_attachment.get("contentType") or "application/octet-stream")[:120],
        "size": len(data),
        "data": data,
    }

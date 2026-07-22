import base64
import binascii
from http import HTTPStatus
from urllib.parse import parse_qs, urlparse

from auth.service import current_user
from mail.inbound import InboundMailError, inbound_enabled, receive_webhook
from mail.store import (
    MAIL_STORE,
    RecipientNotFoundError,
    normalize_external_address,
    user_id_from_address,
)
from mail.transport import (
    ExternalMailError,
    external_send_enabled,
    external_test_mode,
    provider_name,
    send_external,
)
from settings import MAIL_ALLOW_CLASSIFIED_EXTERNAL, MAIL_ATTACHMENT_MAX_BYTES, MAIL_PUBLIC_DOMAIN


ALLOWED_GRADES = {"내부", "기밀", "최고기밀"}


def authenticated_user(handler):
    user = current_user(handler.headers)
    if not user:
        handler.send_json({"ok": False, "message": "로그인이 필요합니다."}, HTTPStatus.UNAUTHORIZED)
    return user


def handle_mail_get(handler):
    parsed = urlparse(handler.path)
    path = parsed.path
    if not path.startswith("/api/mail/"):
        return False
    user = authenticated_user(handler)
    if not user:
        return True

    if path == "/api/mail/recipients":
        handler.send_json({
            "ok": True,
            "recipients": MAIL_STORE.list_recipients(),
            "capabilities": {
                "externalSend": external_send_enabled(),
                "externalTestMode": external_test_mode(),
                "externalReceive": inbound_enabled() and bool(MAIL_PUBLIC_DOMAIN),
                "publicDomain": MAIL_PUBLIC_DOMAIN or None,
                "externalProvider": provider_name(),
            },
        })
        return True

    if path == "/api/mail/messages":
        box = parse_qs(parsed.query).get("box", ["inbox"])[0]
        if box not in {"inbox", "sent"}:
            box = "inbox"
        handler.send_json({"ok": True, "messages": MAIL_STORE.list_messages(user["id"], box)})
        return True

    if path.startswith("/api/mail/messages/"):
        try:
            message_id = int(path.rsplit("/", 1)[1])
        except ValueError:
            handler.send_json({"ok": False, "message": "잘못된 메일 번호입니다."}, HTTPStatus.BAD_REQUEST)
            return True
        message = MAIL_STORE.get_message(message_id, user["id"])
        if not message:
            handler.send_json({"ok": False, "message": "메일을 찾을 수 없습니다."}, HTTPStatus.NOT_FOUND)
        else:
            handler.send_json({"ok": True, "message": message})
        return True

    if path.startswith("/api/mail/attachments/"):
        try:
            attachment_id = int(path.rsplit("/", 1)[1])
        except ValueError:
            handler.send_json({"ok": False, "message": "잘못된 첨부 번호입니다."}, HTTPStatus.BAD_REQUEST)
            return True
        attachment = MAIL_STORE.get_attachment(attachment_id, user["id"])
        if not attachment:
            handler.send_json({"ok": False, "message": "첨부 파일을 찾을 수 없습니다."}, HTTPStatus.NOT_FOUND)
        else:
            handler.send_bytes(
                attachment["data"], attachment["contentType"], attachment["name"],
            )
        return True

    return False


def handle_mail_post(handler):
    path = urlparse(handler.path).path
    if path == "/api/mail/inbound":
        try:
            message_id = receive_webhook(handler)
        except PermissionError as error:
            handler.send_json({"ok": False, "message": str(error)}, HTTPStatus.UNAUTHORIZED)
        except InboundMailError as error:
            handler.send_json({"ok": False, "message": str(error)}, HTTPStatus.BAD_REQUEST)
        except Exception as error:
            print(f"외부 메일 수신 실패: {error}", flush=True)
            handler.send_json({"ok": False, "message": "외부 메일을 저장하지 못했습니다."}, HTTPStatus.INTERNAL_SERVER_ERROR)
        else:
            handler.send_json({"ok": True, "messageId": message_id}, HTTPStatus.OK)
        return True
    if path != "/api/mail/messages":
        return False
    user = authenticated_user(handler)
    if not user:
        return True
    body = handler.read_json_body()
    subject = str(body.get("subject", "")).strip()
    content = str(body.get("body", "")).strip()
    grade = str(body.get("grade", "내부")).strip()
    if not subject or len(subject) > 200:
        handler.send_json({"ok": False, "message": "제목은 1~200자로 입력하세요."}, HTTPStatus.BAD_REQUEST)
        return True
    if not content or len(content) > 65535:
        handler.send_json({"ok": False, "message": "본문을 입력하세요."}, HTTPStatus.BAD_REQUEST)
        return True
    if grade not in ALLOWED_GRADES:
        handler.send_json({"ok": False, "message": "올바른 보안 등급을 선택하세요."}, HTTPStatus.BAD_REQUEST)
        return True
    raw_recipient = str(body.get("to") or "").strip().lower()
    is_internal = raw_recipient.endswith("@datavault.local")
    try:
        recipient = user_id_from_address(raw_recipient) if is_internal else normalize_external_address(raw_recipient)
    except RecipientNotFoundError as error:
        handler.send_json({"ok": False, "message": str(error)}, HTTPStatus.BAD_REQUEST)
        return True
    if not is_internal and grade != "내부" and not MAIL_ALLOW_CLASSIFIED_EXTERNAL:
        handler.send_json(
            {"ok": False, "message": "기밀·최고기밀 메일은 외부로 발송할 수 없습니다."},
            HTTPStatus.FORBIDDEN,
        )
        return True

    attachment = None
    raw_attachment = body.get("attachment")
    if raw_attachment:
        try:
            data = base64.b64decode(raw_attachment.get("data", ""), validate=True)
        except (ValueError, binascii.Error):
            handler.send_json({"ok": False, "message": "첨부 파일 형식이 올바르지 않습니다."}, HTTPStatus.BAD_REQUEST)
            return True
        if len(data) > MAIL_ATTACHMENT_MAX_BYTES:
            handler.send_json({"ok": False, "message": "첨부 파일은 5MB 이하만 가능합니다."}, HTTPStatus.REQUEST_ENTITY_TOO_LARGE)
            return True
        name = str(raw_attachment.get("name", "attachment")).replace("/", "_").replace("\\", "_")[:255]
        attachment = {
            "name": name,
            "contentType": str(raw_attachment.get("contentType") or "application/octet-stream")[:120],
            "size": len(data),
            "data": data,
        }

    if is_internal:
        try:
            message_id = MAIL_STORE.send(user, recipient, subject, content, grade, attachment)
        except Exception as error:
            print(f"사내 메일 발송 실패: {error}", flush=True)
            handler.send_json({"ok": False, "message": "메일을 저장하지 못했습니다."}, HTTPStatus.INTERNAL_SERVER_ERROR)
            return True
        handler.send_json({"ok": True, "message": "사내 메일을 발송했습니다.", "messageId": message_id}, HTTPStatus.CREATED)
        return True

    if not external_send_enabled():
        handler.send_json(
            {"ok": False, "message": "외부 메일 발송 서비스 설정이 아직 완료되지 않았습니다."},
            HTTPStatus.SERVICE_UNAVAILABLE,
        )
        return True
    message_id = None
    try:
        message_id = MAIL_STORE.queue_external(user, recipient, subject, content, grade, attachment)
        provider_id = send_external(user, recipient, subject, content, attachment)
        MAIL_STORE.update_delivery(message_id, "sent", provider_id)
    except ExternalMailError as error:
        if message_id is not None:
            MAIL_STORE.update_delivery(message_id, "failed")
        print(f"외부 메일 발송 실패: {error}", flush=True)
        handler.send_json({"ok": False, "message": str(error)}, HTTPStatus.BAD_GATEWAY)
        return True
    except Exception as error:
        if message_id is not None:
            MAIL_STORE.update_delivery(message_id, "failed")
        print(f"외부 메일 처리 실패: {error}", flush=True)
        handler.send_json({"ok": False, "message": "외부 메일을 처리하지 못했습니다."}, HTTPStatus.INTERNAL_SERVER_ERROR)
        return True
    handler.send_json({"ok": True, "message": "외부 메일을 발송했습니다.", "messageId": message_id}, HTTPStatus.CREATED)
    return True

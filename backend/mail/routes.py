from http import HTTPStatus
from urllib.parse import parse_qs, urlparse

from auth.service import current_user
from mail.inbound import InboundMailError, inbound_enabled, receive_webhook
from mail.service import MAIL_SERVICE, MailServiceError
from mail.store import MAIL_STORE
from mail.transport import external_send_enabled, external_test_mode, provider_name
from settings import MAIL_PUBLIC_DOMAIN


MAILBOXES = {"inbox", "sent", "draft", "trash"}
MESSAGE_ACTIONS = {"trash", "restore", "delete", "retry"}


def authenticated_user(handler):
    user = current_user(handler.headers)
    if not user:
        handler.send_json(
            {"ok": False, "message": "로그인이 필요합니다."},
            HTTPStatus.UNAUTHORIZED,
        )
    return user


def _message_path(path):
    parts = path.strip("/").split("/")
    if len(parts) < 4 or parts[:3] != ["api", "mail", "messages"]:
        return None, None
    try:
        message_id = int(parts[3])
    except ValueError:
        return "invalid", None
    action = parts[4] if len(parts) == 5 else None
    if len(parts) > 5:
        return "invalid", None
    return message_id, action


def _send_not_found(handler, message="메일을 찾을 수 없습니다."):
    handler.send_json({"ok": False, "message": message}, HTTPStatus.NOT_FOUND)


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
        if box not in MAILBOXES:
            box = "inbox"
        handler.send_json({
            "ok": True,
            "mailbox": box,
            "messages": MAIL_STORE.list_messages(user["id"], box),
        })
        return True

    message_id, action = _message_path(path)
    if message_id == "invalid":
        handler.send_json(
            {"ok": False, "message": "잘못된 메일 번호입니다."},
            HTTPStatus.BAD_REQUEST,
        )
        return True
    if message_id is not None and action is None:
        message = MAIL_STORE.get_message(message_id, user["id"])
        if not message:
            _send_not_found(handler)
        else:
            handler.send_json({"ok": True, "message": message})
        return True

    if path.startswith("/api/mail/attachments/"):
        try:
            attachment_id = int(path.rsplit("/", 1)[1])
        except ValueError:
            handler.send_json(
                {"ok": False, "message": "잘못된 첨부 번호입니다."},
                HTTPStatus.BAD_REQUEST,
            )
            return True
        attachment = MAIL_STORE.get_attachment(attachment_id, user["id"])
        if not attachment:
            _send_not_found(handler, "첨부 파일을 찾을 수 없습니다.")
        else:
            handler.send_bytes(
                attachment["data"], attachment["contentType"], attachment["name"],
            )
        return True

    return False


def handle_mail_post(handler):
    path = urlparse(handler.path).path
    if path == "/api/mail/inbound":
        return _handle_inbound(handler)
    if not path.startswith("/api/mail/"):
        return False

    user = authenticated_user(handler)
    if not user:
        return True

    try:
        if path == "/api/mail/messages":
            result = MAIL_SERVICE.send(user, handler.read_json_body())
            handler.send_json({"ok": True, **result}, HTTPStatus.CREATED)
            return True

        if path == "/api/mail/drafts":
            result = MAIL_SERVICE.save_draft(user, handler.read_json_body())
            handler.send_json({"ok": True, **result}, HTTPStatus.CREATED)
            return True

        message_id, action = _message_path(path)
        if message_id == "invalid" or action not in MESSAGE_ACTIONS:
            return False

        if action == "retry":
            result = MAIL_SERVICE.retry(user, message_id)
            handler.send_json({"ok": True, **result})
            return True

        operations = {
            "trash": (MAIL_STORE.move_to_trash, "메일을 휴지통으로 이동했습니다."),
            "restore": (MAIL_STORE.restore_message, "메일을 복원했습니다."),
            "delete": (MAIL_STORE.delete_message, "메일을 영구 삭제했습니다."),
        }
        operation, message = operations[action]
        if not operation(message_id, user["id"]):
            _send_not_found(handler, "처리할 수 있는 메일을 찾지 못했습니다.")
        else:
            handler.send_json({"ok": True, "message": message, "messageId": message_id})
        return True
    except MailServiceError as error:
        handler.send_json({"ok": False, "message": str(error)}, error.status)
        return True
    except Exception as error:
        print(f"메일 API 처리 실패: {error}", flush=True)
        handler.send_json(
            {"ok": False, "message": "메일 요청을 처리하지 못했습니다."},
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )
        return True


def _handle_inbound(handler):
    try:
        message_id = receive_webhook(handler)
    except PermissionError as error:
        handler.send_json({"ok": False, "message": str(error)}, HTTPStatus.UNAUTHORIZED)
    except InboundMailError as error:
        handler.send_json({"ok": False, "message": str(error)}, HTTPStatus.BAD_REQUEST)
    except Exception as error:
        print(f"외부 메일 수신 실패: {error}", flush=True)
        handler.send_json(
            {"ok": False, "message": "외부 메일을 저장하지 못했습니다."},
            HTTPStatus.INTERNAL_SERVER_ERROR,
        )
    else:
        handler.send_json({"ok": True, "messageId": message_id}, HTTPStatus.OK)
    return True

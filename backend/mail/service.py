from http import HTTPStatus

from mail.store import MAIL_STORE
from mail.transport import ExternalMailError, external_send_enabled, send_external
from mail.validation import (
    MailValidationError,
    decode_attachment,
    resolve_recipient,
    validate_message_fields,
)
from settings import MAIL_ALLOW_CLASSIFIED_EXTERNAL


class MailServiceError(Exception):
    def __init__(self, message, status=HTTPStatus.BAD_REQUEST):
        super().__init__(message)
        self.status = status


class MailService:
    def __init__(self, store=MAIL_STORE):
        self.store = store

    def _validated(self, payload, *, draft=False):
        try:
            subject, body, grade = validate_message_fields(payload, draft=draft)
            recipient = resolve_recipient(
                payload.get("to"),
                required=not draft,
                user_store=getattr(self.store, "user_store", None),
            )
            attachment = decode_attachment(payload.get("attachment"))
        except MailValidationError as error:
            raise MailServiceError(str(error)) from error
        return recipient, subject, body, grade, attachment

    @staticmethod
    def _check_external_policy(recipient, grade):
        if recipient and not recipient.internal and grade != "내부" and not MAIL_ALLOW_CLASSIFIED_EXTERNAL:
            raise MailServiceError(
                "기밀·최고기밀 메일은 외부로 발송할 수 없습니다.",
                HTTPStatus.FORBIDDEN,
            )

    def send(self, sender, payload):
        recipient, subject, body, grade, attachment = self._validated(payload)
        self._check_external_policy(recipient, grade)

        draft_id = self._optional_id(payload.get("draftId"))
        if draft_id and attachment is None:
            attachment = self.store.get_draft_attachment(draft_id, sender["id"])

        if recipient.internal:
            message_id = self.store.send(
                sender, recipient.value, subject, body, grade, attachment,
            )
            message = "사내 메일을 발송했습니다."
        else:
            if not external_send_enabled():
                raise MailServiceError(
                    "외부 메일 발송 서비스 설정이 아직 완료되지 않았습니다.",
                    HTTPStatus.SERVICE_UNAVAILABLE,
                )
            message_id = None
            try:
                message_id = self.store.queue_external(
                    sender, recipient.address, subject, body, grade, attachment,
                )
                provider_id = send_external(
                    sender, recipient.address, subject, body, attachment,
                )
                self.store.update_delivery(message_id, "sent", provider_id)
            except ExternalMailError as error:
                if message_id is not None:
                    self.store.update_delivery(message_id, "failed")
                raise MailServiceError(str(error), HTTPStatus.BAD_GATEWAY) from error
            except Exception as error:
                if message_id is not None:
                    self.store.update_delivery(message_id, "failed")
                raise MailServiceError(
                    "외부 메일을 처리하지 못했습니다.",
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                ) from error
            message = "외부 메일을 발송했습니다."

        if draft_id:
            self.store.discard_draft(draft_id, sender["id"])
        return {"message": message, "messageId": message_id}

    def save_draft(self, sender, payload):
        recipient, subject, body, grade, attachment = self._validated(payload, draft=True)
        self._check_external_policy(recipient, grade)
        message_id = self.store.save_draft(
            sender=sender,
            recipient=recipient,
            subject=subject,
            body=body,
            grade=grade,
            attachment=attachment,
            message_id=self._optional_id(payload.get("messageId")),
        )
        return {"message": "임시보관함에 저장했습니다.", "messageId": message_id}

    def retry(self, sender, message_id):
        if not external_send_enabled():
            raise MailServiceError(
                "외부 메일 발송 서비스 설정이 아직 완료되지 않았습니다.",
                HTTPStatus.SERVICE_UNAVAILABLE,
            )
        payload = self.store.get_retry_payload(message_id, sender["id"])
        if not payload:
            raise MailServiceError(
                "재발송할 수 있는 실패 메일을 찾지 못했습니다.",
                HTTPStatus.NOT_FOUND,
            )
        try:
            provider_id = send_external(
                sender,
                payload["to"],
                payload["subject"],
                payload["body"],
                payload.get("attachment"),
            )
            self.store.update_delivery(message_id, "sent", provider_id)
        except ExternalMailError as error:
            self.store.update_delivery(message_id, "failed")
            raise MailServiceError(str(error), HTTPStatus.BAD_GATEWAY) from error
        return {"message": "외부 메일을 다시 발송했습니다.", "messageId": message_id}

    @staticmethod
    def _optional_id(value):
        if value in (None, ""):
            return None
        try:
            return int(value)
        except (TypeError, ValueError) as error:
            raise MailServiceError("잘못된 메일 번호입니다.") from error


MAIL_SERVICE = MailService()

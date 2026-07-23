import base64
import os
import sys
import unittest
from http import HTTPStatus
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

# Prevent tests from opening the production database configured in .env.
for variable in (
    "DATABASE_URL",
    "MYSQL_HOST",
    "MYSQLHOST",
    "MYSQL_DATABASE",
    "MYSQLDATABASE",
    "MYSQL_USER",
    "MYSQLUSER",
):
    os.environ[variable] = ""
os.environ.setdefault("JWT_SECRET", "mail-test-secret")

from mail.providers.base import ExternalMailError  # noqa: E402
from mail.service import MailService, MailServiceError  # noqa: E402
from mail.store import MemoryMailStore  # noqa: E402


class FakeUserStore:
    storage_type = "memory"

    def __init__(self):
        self.users = {
            "admin": {"id": "admin", "name": "관리자", "role": "관리자"},
            "staff": {"id": "staff", "name": "사원", "role": "사원"},
        }

    def get_user(self, user_id):
        return self.users.get(user_id)

    def user_exists(self, user_id):
        return user_id in self.users


class MailServiceTest(unittest.TestCase):
    def setUp(self):
        self.user_store = FakeUserStore()
        self.store = MemoryMailStore(self.user_store)
        self.service = MailService(self.store)
        self.admin = self.user_store.get_user("admin")

    def test_internal_mailboxes_are_independent(self):
        result = self.service.send(
            self.admin,
            {
                "to": "staff@datavault.local",
                "subject": "내부 공지",
                "body": "확인 바랍니다.",
                "grade": "내부",
            },
        )
        message_id = result["messageId"]

        self.assertEqual(len(self.store.list_messages("admin", "sent")), 1)
        self.assertEqual(len(self.store.list_messages("staff", "inbox")), 1)

        self.assertTrue(self.store.move_to_trash(message_id, "staff"))
        self.assertEqual(self.store.list_messages("staff", "inbox"), [])
        self.assertEqual(len(self.store.list_messages("staff", "trash")), 1)
        self.assertEqual(len(self.store.list_messages("admin", "sent")), 1)

        self.assertTrue(self.store.restore_message(message_id, "staff"))
        self.assertEqual(len(self.store.list_messages("staff", "inbox")), 1)
        self.assertTrue(self.store.move_to_trash(message_id, "staff"))
        self.assertTrue(self.store.delete_message(message_id, "staff"))
        self.assertIsNone(self.store.get_message(message_id, "staff"))
        self.assertIsNotNone(self.store.get_message(message_id, "admin"))

    def test_draft_edit_and_send_preserves_attachment(self):
        attachment_data = b"draft attachment"
        encoded = base64.b64encode(attachment_data).decode("ascii")
        created = self.service.save_draft(
            self.admin,
            {
                "to": "staff@datavault.local",
                "subject": "초안",
                "body": "초안 내용",
                "grade": "내부",
                "attachment": {
                    "name": "draft.txt",
                    "contentType": "text/plain",
                    "data": encoded,
                },
            },
        )
        draft_id = created["messageId"]

        edited = self.service.save_draft(
            self.admin,
            {
                "messageId": draft_id,
                "to": "staff@datavault.local",
                "subject": "수정한 초안",
                "body": "수정한 내용",
                "grade": "내부",
            },
        )
        self.assertEqual(edited["messageId"], draft_id)

        sent = self.service.send(
            self.admin,
            {
                "draftId": draft_id,
                "to": "staff@datavault.local",
                "subject": "수정한 초안",
                "body": "수정한 내용",
                "grade": "내부",
            },
        )
        self.assertEqual(self.store.list_messages("admin", "draft"), [])
        detail = self.store.get_message(sent["messageId"], "admin")
        self.assertEqual(detail["attachments"][0]["name"], "draft.txt")
        saved = self.store.get_attachment(detail["attachments"][0]["id"], "admin")
        self.assertEqual(saved["data"], attachment_data)

    def test_classified_external_mail_is_blocked(self):
        with patch("mail.service.MAIL_ALLOW_CLASSIFIED_EXTERNAL", False):
            with self.assertRaises(MailServiceError) as context:
                self.service.send(
                    self.admin,
                    {
                        "to": "outside@example.com",
                        "subject": "보안 문서",
                        "body": "외부 발송 금지",
                        "grade": "기밀",
                    },
                )
        self.assertEqual(context.exception.status, HTTPStatus.FORBIDDEN)

    def test_external_failure_can_be_retried(self):
        payload = {
            "to": "outside@example.com",
            "subject": "외부 메일",
            "body": "발송 테스트",
            "grade": "내부",
        }
        with (
            patch("mail.service.external_send_enabled", return_value=True),
            patch(
                "mail.service.send_external",
                side_effect=ExternalMailError("외부 제공자 연결 실패"),
            ),
        ):
            with self.assertRaises(MailServiceError) as context:
                self.service.send(self.admin, payload)

        self.assertEqual(context.exception.status, HTTPStatus.BAD_GATEWAY)
        failed = self.store.list_messages("admin", "sent")
        self.assertEqual(len(failed), 1)
        self.assertEqual(failed[0]["deliveryStatus"], "failed")

        message_id = failed[0]["id"]
        with (
            patch("mail.service.external_send_enabled", return_value=True),
            patch("mail.service.send_external", return_value="provider-message-1"),
        ):
            result = self.service.retry(self.admin, message_id)

        self.assertEqual(result["messageId"], message_id)
        detail = self.store.get_message(message_id, "admin")
        self.assertEqual(detail["deliveryStatus"], "sent")
        self.assertEqual(detail["providerMessageId"], "provider-message-1")

    def test_invalid_recipient_is_rejected(self):
        with self.assertRaises(MailServiceError):
            self.service.send(
                self.admin,
                {
                    "to": "not-an-email",
                    "subject": "잘못된 주소",
                    "body": "본문",
                    "grade": "내부",
                },
            )


if __name__ == "__main__":
    unittest.main()

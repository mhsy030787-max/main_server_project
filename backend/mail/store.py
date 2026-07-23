from datetime import datetime, timezone
from email.utils import parseaddr
from threading import RLock

from storage.stores import USER_STORE
from settings import MAIL_PUBLIC_DOMAIN


class MailStoreError(Exception):
    pass


class RecipientNotFoundError(MailStoreError):
    pass


def internal_address(user_id):
    return f"{user_id}@datavault.local"


def user_id_from_address(address, user_store=None):
    normalized = str(address or "").strip().lower()
    suffix = "@datavault.local"
    if not normalized.endswith(suffix):
        raise RecipientNotFoundError("사내 메일 주소만 사용할 수 있습니다.")
    user_id = normalized[:-len(suffix)]
    store = user_store or USER_STORE
    if not user_id or not store.user_exists(user_id):
        raise RecipientNotFoundError("받는 사람을 찾을 수 없습니다.")
    return user_id


def normalize_external_address(address):
    normalized = parseaddr(str(address or ""))[1].strip().lower()
    if not normalized or len(normalized) > 254 or normalized.count("@") != 1:
        raise RecipientNotFoundError("외부 메일 주소가 올바르지 않습니다.")
    local, domain = normalized.rsplit("@", 1)
    if not local or "." not in domain or any(char in normalized for char in "\r\n"):
        raise RecipientNotFoundError("외부 메일 주소가 올바르지 않습니다.")
    return normalized


def user_id_from_public_address(address):
    normalized = parseaddr(str(address or ""))[1].strip().lower()
    if not MAIL_PUBLIC_DOMAIN:
        raise RecipientNotFoundError("외부 수신 도메인이 설정되지 않았습니다.")
    suffix = f"@{MAIL_PUBLIC_DOMAIN}"
    if not normalized.endswith(suffix):
        raise RecipientNotFoundError("이 서버가 수신하는 도메인이 아닙니다.")
    user_id = normalized[:-len(suffix)]
    if not user_id or not USER_STORE.user_exists(user_id):
        raise RecipientNotFoundError("수신 사용자를 찾을 수 없습니다.")
    return user_id


class MemoryMailStore:
    storage_type = "memory"

    def __init__(self, user_store=USER_STORE):
        self.user_store = user_store
        self.lock = RLock()
        self.messages = []
        self.next_message_id = 1
        self.next_attachment_id = 1

    def list_recipients(self):
        users = getattr(self.user_store, "users", {}).values()
        return [
            {"id": user["id"], "name": user["name"], "address": internal_address(user["id"])}
            for user in users
        ]

    def _with_attachment(self, message, attachment):
        if not attachment:
            return
        saved = dict(attachment)
        saved["id"] = self.next_attachment_id
        self.next_attachment_id += 1
        message["attachment"] = saved
        message["attachments"] = [saved]

    @staticmethod
    def _sender_visible(message, user_id):
        return (
            message["senderId"] == user_id
            and message.get("senderBox", "sent") not in {"none", "deleted"}
        )

    @staticmethod
    def _recipient_visible(message, user_id):
        return (
            message["recipientId"] == user_id
            and message.get("recipientBox", "inbox") not in {"none", "deleted"}
            and message.get("direction", "internal") in {"internal", "inbound"}
        )

    def _message_for_user(self, message_id, user_id):
        message = next((item for item in self.messages if item["id"] == message_id), None)
        if not message:
            return None
        if not (self._sender_visible(message, user_id) or self._recipient_visible(message, user_id)):
            return None
        return message

    def _viewer_role(self, message, user_id):
        if self._sender_visible(message, user_id):
            return "sender"
        if self._recipient_visible(message, user_id):
            return "recipient"
        return None

    def send(self, sender, recipient_id, subject, body, grade, attachment=None):
        with self.lock:
            message = {
                "id": self.next_message_id,
                "senderId": sender["id"],
                "senderName": sender["name"],
                "recipientId": recipient_id,
                "subject": subject,
                "body": body,
                "grade": grade,
                "sentAt": datetime.now(timezone.utc).isoformat(),
                "readAt": None,
                "attachment": None,
                "direction": "internal",
                "deliveryStatus": "delivered",
                "senderAddress": internal_address(sender["id"]),
                "recipientAddress": internal_address(recipient_id),
                "recipientName": self.user_store.get_user(recipient_id)["name"],
                "senderBox": "sent",
                "senderPreviousBox": None,
                "recipientBox": "inbox",
                "recipientPreviousBox": None,
            }
            self.next_message_id += 1
            self._with_attachment(message, attachment)
            self.messages.append(message)
            return message["id"]

    def queue_external(self, sender, recipient_address, subject, body, grade, attachment=None):
        with self.lock:
            message = {
                "id": self.next_message_id,
                "senderId": sender["id"],
                "senderName": sender["name"],
                "recipientId": sender["id"],
                "recipientName": recipient_address,
                "subject": subject,
                "body": body,
                "grade": grade,
                "sentAt": datetime.now(timezone.utc).isoformat(),
                "readAt": None,
                "attachment": None,
                "direction": "outbound",
                "deliveryStatus": "pending",
                "senderAddress": internal_address(sender["id"]),
                "recipientAddress": recipient_address,
                "providerMessageId": None,
                "senderBox": "sent",
                "senderPreviousBox": None,
                "recipientBox": "none",
                "recipientPreviousBox": None,
            }
            self.next_message_id += 1
            self._with_attachment(message, attachment)
            self.messages.append(message)
            return message["id"]

    def save_draft(self, sender, recipient, subject, body, grade, attachment=None, message_id=None):
        with self.lock:
            recipient_id = sender["id"]
            recipient_address = ""
            recipient_name = "받는 사람 미지정"
            if recipient:
                recipient_address = recipient.address
                if recipient.internal:
                    recipient_id = recipient.value
                    recipient_user = self.user_store.get_user(recipient.value)
                    recipient_name = recipient_user["name"] if recipient_user else recipient.value
                else:
                    recipient_name = recipient.address

            existing = None
            if message_id:
                existing = next((
                    item for item in self.messages
                    if item["id"] == message_id
                    and item["senderId"] == sender["id"]
                    and item.get("direction") == "draft"
                    and item.get("senderBox") == "draft"
                ), None)
                if not existing:
                    raise MailStoreError("수정할 임시 메일을 찾을 수 없습니다.")

            if existing:
                existing.update({
                    "recipientId": recipient_id,
                    "recipientName": recipient_name,
                    "recipientAddress": recipient_address,
                    "subject": subject,
                    "body": body,
                    "grade": grade,
                    "sentAt": datetime.now(timezone.utc).isoformat(),
                })
                if attachment:
                    existing["attachment"] = None
                    existing["attachments"] = []
                    self._with_attachment(existing, attachment)
                return existing["id"]

            message = {
                "id": self.next_message_id,
                "senderId": sender["id"],
                "senderName": sender["name"],
                "recipientId": recipient_id,
                "recipientName": recipient_name,
                "subject": subject,
                "body": body,
                "grade": grade,
                "sentAt": datetime.now(timezone.utc).isoformat(),
                "readAt": None,
                "attachment": None,
                "attachments": [],
                "direction": "draft",
                "deliveryStatus": "draft",
                "senderAddress": internal_address(sender["id"]),
                "recipientAddress": recipient_address,
                "providerMessageId": None,
                "senderBox": "draft",
                "senderPreviousBox": None,
                "recipientBox": "none",
                "recipientPreviousBox": None,
            }
            self.next_message_id += 1
            self._with_attachment(message, attachment)
            self.messages.append(message)
            return message["id"]

    def update_delivery(self, message_id, status, provider_message_id=None):
        with self.lock:
            message = next((item for item in self.messages if item["id"] == message_id), None)
            if message:
                message["deliveryStatus"] = status
                message["providerMessageId"] = provider_message_id

    def update_delivery_by_provider(self, provider_message_id, status):
        with self.lock:
            message = next((
                item for item in self.messages
                if item.get("providerMessageId") == provider_message_id
            ), None)
            if message:
                message["deliveryStatus"] = status
                return message["id"]
        return None

    def receive_external(self, recipient_id, recipient_address, sender_address, sender_name,
                         subject, body, provider_message_id=None, attachments=None):
        with self.lock:
            message = {
                "id": self.next_message_id,
                "senderId": recipient_id,
                "senderName": sender_name,
                "recipientId": recipient_id,
                "recipientName": self.user_store.get_user(recipient_id)["name"],
                "subject": subject,
                "body": body,
                "grade": "외부",
                "sentAt": datetime.now(timezone.utc).isoformat(),
                "readAt": None,
                "attachment": None,
                "attachments": [],
                "direction": "inbound",
                "deliveryStatus": "received",
                "senderAddress": sender_address,
                "recipientAddress": recipient_address,
                "providerMessageId": provider_message_id,
                "senderBox": "none",
                "senderPreviousBox": None,
                "recipientBox": "inbox",
                "recipientPreviousBox": None,
            }
            self.next_message_id += 1
            for attachment in attachments or []:
                attachment["id"] = self.next_attachment_id
                self.next_attachment_id += 1
                message["attachments"].append(attachment)
            if message["attachments"]:
                message["attachment"] = message["attachments"][0]
            self.messages.append(message)
            return message["id"]

    def list_messages(self, user_id, box):
        def included(message):
            direction = message.get("direction", "internal")
            if box == "inbox":
                return (
                    message["recipientId"] == user_id
                    and direction in {"internal", "inbound"}
                    and message.get("recipientBox", "inbox") == "inbox"
                )
            if box == "sent":
                return (
                    message["senderId"] == user_id
                    and direction in {"internal", "outbound"}
                    and message.get("senderBox", "sent") == "sent"
                )
            if box == "draft":
                return (
                    message["senderId"] == user_id
                    and direction == "draft"
                    and message.get("senderBox") == "draft"
                )
            return (
                message["senderId"] == user_id and message.get("senderBox") == "trash"
            ) or (
                message["recipientId"] == user_id and message.get("recipientBox") == "trash"
            )

        return [self.summary(item, user_id, box) for item in reversed(self.messages) if included(item)]

    def summary(self, message, user_id, box):
        sender_view = box in {"sent", "draft"} or (
            box == "trash" and message["senderId"] == user_id and message.get("senderBox") == "trash"
        )
        if sender_view:
            other_id = message["recipientId"]
            other = self.user_store.get_user(other_id)
            other_name = message.get("recipientName") or (other["name"] if other else other_id)
            other_address = message.get("recipientAddress") or internal_address(other_id)
        else:
            other_id = message["senderId"]
            other = self.user_store.get_user(other_id)
            other_name = message.get("senderName") or (other["name"] if other else other_id)
            other_address = message.get("senderAddress") or internal_address(other_id)
        return {
            "id": message["id"],
            "subject": message["subject"],
            "grade": message["grade"],
            "sentAt": message["sentAt"],
            "read": bool(message["readAt"]) if not sender_view else True,
            "otherName": other_name,
            "otherAddress": other_address,
            "hasAttachment": bool(message.get("attachment")),
            "deliveryStatus": message.get("deliveryStatus", "delivered"),
            "direction": message.get("direction", "internal"),
            "mailbox": box,
        }

    def get_message(self, message_id, user_id):
        message = self._message_for_user(message_id, user_id)
        if not message:
            return None
        viewer_role = self._viewer_role(message, user_id)
        if viewer_role == "recipient" and not message["readAt"]:
            message["readAt"] = datetime.now(timezone.utc).isoformat()
        return self.detail(message, viewer_role)

    def detail(self, message, viewer_role):
        attachments = message.get("attachments") or ([message["attachment"]] if message["attachment"] else [])
        mailbox = message.get("senderBox") if viewer_role == "sender" else message.get("recipientBox")
        return {
            **{key: value for key, value in message.items() if key not in {"attachment", "attachments"}},
            "from": message.get("senderAddress") or internal_address(message["senderId"]),
            "to": message.get("recipientAddress") or internal_address(message["recipientId"]),
            "attachments": [
                {key: attachment[key] for key in ("id", "name", "contentType", "size")}
                for attachment in attachments
            ],
            "viewerRole": viewer_role,
            "mailbox": mailbox,
            "canRetry": (
                viewer_role == "sender"
                and message.get("direction") == "outbound"
                and message.get("deliveryStatus") == "failed"
            ),
            "canEdit": viewer_role == "sender" and message.get("direction") == "draft",
        }

    def get_attachment(self, attachment_id, user_id):
        for message in self.messages:
            attachments = message.get("attachments") or ([message["attachment"]] if message["attachment"] else [])
            for attachment in attachments:
                if attachment["id"] == attachment_id and self._message_for_user(message["id"], user_id):
                    return attachment
        return None

    def move_to_trash(self, message_id, user_id):
        with self.lock:
            message = self._message_for_user(message_id, user_id)
            if not message:
                return False
            if self._sender_visible(message, user_id):
                if message.get("senderBox") == "trash":
                    return True
                message["senderPreviousBox"] = message.get("senderBox") or "sent"
                message["senderBox"] = "trash"
                return True
            if self._recipient_visible(message, user_id):
                if message.get("recipientBox") == "trash":
                    return True
                message["recipientPreviousBox"] = message.get("recipientBox") or "inbox"
                message["recipientBox"] = "trash"
                return True
        return False

    def restore_message(self, message_id, user_id):
        with self.lock:
            message = next((item for item in self.messages if item["id"] == message_id), None)
            if not message:
                return False
            if message["senderId"] == user_id and message.get("senderBox") == "trash":
                fallback = "draft" if message.get("direction") == "draft" else "sent"
                message["senderBox"] = message.get("senderPreviousBox") or fallback
                message["senderPreviousBox"] = None
                return True
            if message["recipientId"] == user_id and message.get("recipientBox") == "trash":
                message["recipientBox"] = message.get("recipientPreviousBox") or "inbox"
                message["recipientPreviousBox"] = None
                return True
        return False

    def delete_message(self, message_id, user_id):
        with self.lock:
            message = next((item for item in self.messages if item["id"] == message_id), None)
            if not message:
                return False
            changed = False
            if message["senderId"] == user_id and message.get("senderBox") == "trash":
                message["senderBox"] = "deleted"
                changed = True
            elif message["recipientId"] == user_id and message.get("recipientBox") == "trash":
                message["recipientBox"] = "deleted"
                changed = True
            if not changed:
                return False
            sender_gone = message.get("senderBox") in {"none", "deleted"}
            recipient_gone = message.get("recipientBox") in {"none", "deleted"}
            if sender_gone and recipient_gone:
                self.messages.remove(message)
            return True

    def get_draft_attachment(self, message_id, user_id):
        with self.lock:
            message = next((
                item for item in self.messages
                if item["id"] == message_id
                and item["senderId"] == user_id
                and item.get("direction") == "draft"
            ), None)
            return dict(message["attachment"]) if message and message.get("attachment") else None

    def discard_draft(self, message_id, user_id):
        with self.lock:
            message = next((
                item for item in self.messages
                if item["id"] == message_id
                and item["senderId"] == user_id
                and item.get("direction") == "draft"
            ), None)
            if message:
                self.messages.remove(message)
                return True
        return False

    def get_retry_payload(self, message_id, user_id):
        with self.lock:
            message = next((
                item for item in self.messages
                if item["id"] == message_id
                and item["senderId"] == user_id
                and item.get("direction") == "outbound"
                and item.get("deliveryStatus") == "failed"
                and item.get("senderBox") not in {"none", "deleted"}
            ), None)
            if not message:
                return None
            attachment = dict(message["attachment"]) if message.get("attachment") else None
            return {
                "to": message["recipientAddress"],
                "subject": message["subject"],
                "body": message["body"],
                "attachment": attachment,
            }


class MySQLMailStore:
    storage_type = "mysql"

    def __init__(self, user_store):
        self.user_store = user_store
        self.ensure_schema()

    def connect(self):
        return self.user_store.connect()

    def ensure_schema(self):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS mail_messages (
                        message_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        sender_id VARCHAR(64) NOT NULL,
                        subject VARCHAR(200) NOT NULL,
                        body TEXT NOT NULL,
                        security_grade VARCHAR(20) NOT NULL DEFAULT '내부',
                        sender_box VARCHAR(16) NOT NULL DEFAULT 'sent',
                        sender_previous_box VARCHAR(16) NULL,
                        sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_mail_messages_sender_sent (sender_id, sent_at),
                        CONSTRAINT fk_mail_messages_sender FOREIGN KEY (sender_id)
                            REFERENCES users(user_id) ON DELETE RESTRICT
                    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS mail_recipients (
                        message_id BIGINT UNSIGNED NOT NULL,
                        recipient_id VARCHAR(64) NOT NULL,
                        recipient_box VARCHAR(16) NOT NULL DEFAULT 'inbox',
                        recipient_previous_box VARCHAR(16) NULL,
                        read_at TIMESTAMP NULL,
                        PRIMARY KEY (message_id, recipient_id),
                        INDEX idx_mail_recipients_inbox (recipient_id, message_id),
                        CONSTRAINT fk_mail_recipients_message FOREIGN KEY (message_id)
                            REFERENCES mail_messages(message_id) ON DELETE CASCADE,
                        CONSTRAINT fk_mail_recipients_user FOREIGN KEY (recipient_id)
                            REFERENCES users(user_id) ON DELETE RESTRICT
                    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                    """
                )
                cursor.execute(
                    """
                    CREATE TABLE IF NOT EXISTS mail_attachments (
                        attachment_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
                        message_id BIGINT UNSIGNED NOT NULL,
                        file_name VARCHAR(255) NOT NULL,
                        content_type VARCHAR(120) NOT NULL,
                        file_size INT UNSIGNED NOT NULL,
                        file_data MEDIUMBLOB NOT NULL,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        INDEX idx_mail_attachments_message (message_id),
                        CONSTRAINT fk_mail_attachments_message FOREIGN KEY (message_id)
                            REFERENCES mail_messages(message_id) ON DELETE CASCADE
                    ) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci
                    """
                )
                self.ensure_column(cursor, "mail_messages", "sender_address", "VARCHAR(254) NULL AFTER sender_id")
                self.ensure_column(cursor, "mail_messages", "sender_name", "VARCHAR(120) NULL AFTER sender_address")
                self.ensure_column(cursor, "mail_messages", "direction", "VARCHAR(16) NOT NULL DEFAULT 'internal' AFTER security_grade")
                self.ensure_column(cursor, "mail_messages", "delivery_status", "VARCHAR(24) NOT NULL DEFAULT 'delivered' AFTER direction")
                self.ensure_column(cursor, "mail_messages", "provider_message_id", "VARCHAR(255) NULL AFTER delivery_status")
                self.ensure_column(cursor, "mail_messages", "sender_box", "VARCHAR(16) NOT NULL DEFAULT 'sent' AFTER provider_message_id")
                self.ensure_column(cursor, "mail_messages", "sender_previous_box", "VARCHAR(16) NULL AFTER sender_box")
                self.ensure_column(cursor, "mail_recipients", "recipient_address", "VARCHAR(254) NULL AFTER recipient_id")
                self.ensure_column(cursor, "mail_recipients", "recipient_name", "VARCHAR(120) NULL AFTER recipient_address")
                self.ensure_column(cursor, "mail_recipients", "recipient_box", "VARCHAR(16) NOT NULL DEFAULT 'inbox' AFTER recipient_name")
                self.ensure_column(cursor, "mail_recipients", "recipient_previous_box", "VARCHAR(16) NULL AFTER recipient_box")
                cursor.execute("UPDATE mail_messages SET sender_box = 'none' WHERE direction = 'inbound' AND sender_box = 'sent'")
                cursor.execute("UPDATE mail_recipients r JOIN mail_messages m ON m.message_id = r.message_id SET r.recipient_box = 'none' WHERE m.direction = 'outbound' AND r.recipient_box = 'inbox'")

    @staticmethod
    def ensure_column(cursor, table_name, column_name, definition):
        cursor.execute(
            """
            SELECT COUNT(*) AS count
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s
            """,
            (table_name, column_name),
        )
        if cursor.fetchone()["count"] == 0:
            cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}")

    def list_recipients(self):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT user_id, name FROM users ORDER BY name, user_id")
                return [
                    {"id": row["user_id"], "name": row["name"], "address": internal_address(row["user_id"])}
                    for row in cursor.fetchall()
                ]

    def send(self, sender, recipient_id, subject, body, grade, attachment=None):
        with self.connect() as connection:
            try:
                connection.begin()
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO mail_messages
                            (sender_id, sender_address, sender_name, subject, body,
                             security_grade, direction, delivery_status, sender_box)
                        VALUES (%s, %s, %s, %s, %s, %s, 'internal', 'delivered', 'sent')
                        """,
                        (sender["id"], internal_address(sender["id"]), sender["name"], subject, body, grade),
                    )
                    message_id = cursor.lastrowid
                    cursor.execute(
                        """
                        INSERT INTO mail_recipients
                            (message_id, recipient_id, recipient_address, recipient_name, recipient_box)
                        VALUES (%s, %s, %s, %s, 'inbox')
                        """,
                        (message_id, recipient_id, internal_address(recipient_id),
                         self.user_store.get_user(recipient_id)["name"]),
                    )
                    self.insert_attachments(cursor, message_id, [attachment] if attachment else [])
                connection.commit()
                return message_id
            except Exception:
                connection.rollback()
                raise

    def queue_external(self, sender, recipient_address, subject, body, grade, attachment=None):
        with self.connect() as connection:
            try:
                connection.begin()
                with connection.cursor() as cursor:
                    cursor.execute(
                        """
                        INSERT INTO mail_messages
                            (sender_id, sender_address, sender_name, subject, body, security_grade,
                             direction, delivery_status, sender_box)
                        VALUES (%s, %s, %s, %s, %s, %s, 'outbound', 'pending', 'sent')
                        """,
                        (sender["id"], internal_address(sender["id"]), sender["name"], subject, body, grade),
                    )
                    message_id = cursor.lastrowid
                    cursor.execute(
                        """
                        INSERT INTO mail_recipients
                            (message_id, recipient_id, recipient_address, recipient_name, recipient_box)
                        VALUES (%s, %s, %s, %s, 'none')
                        """,
                        (message_id, sender["id"], recipient_address, recipient_address),
                    )
                    self.insert_attachments(cursor, message_id, [attachment] if attachment else [])
                connection.commit()
                return message_id
            except Exception:
                connection.rollback()
                raise

    def save_draft(self, sender, recipient, subject, body, grade, attachment=None, message_id=None):
        recipient_id = sender["id"]
        recipient_address = ""
        recipient_name = "받는 사람 미지정"
        if recipient:
            recipient_address = recipient.address
            if recipient.internal:
                recipient_id = recipient.value
                recipient_user = self.user_store.get_user(recipient.value)
                recipient_name = recipient_user["name"] if recipient_user else recipient.value
            else:
                recipient_name = recipient.address

        with self.connect() as connection:
            try:
                connection.begin()
                with connection.cursor() as cursor:
                    if message_id:
                        cursor.execute(
                            """
                            SELECT message_id FROM mail_messages
                            WHERE message_id = %s AND sender_id = %s
                              AND direction = 'draft' AND sender_box = 'draft'
                            """,
                            (message_id, sender["id"]),
                        )
                        if not cursor.fetchone():
                            raise MailStoreError("수정할 임시 메일을 찾을 수 없습니다.")
                        cursor.execute(
                            """
                            UPDATE mail_messages
                            SET subject = %s, body = %s, security_grade = %s,
                                sent_at = CURRENT_TIMESTAMP
                            WHERE message_id = %s
                            """,
                            (subject, body, grade, message_id),
                        )
                        cursor.execute("DELETE FROM mail_recipients WHERE message_id = %s", (message_id,))
                        if attachment:
                            cursor.execute("DELETE FROM mail_attachments WHERE message_id = %s", (message_id,))
                            self.insert_attachments(cursor, message_id, [attachment])
                    else:
                        cursor.execute(
                            """
                            INSERT INTO mail_messages
                                (sender_id, sender_address, sender_name, subject, body,
                                 security_grade, direction, delivery_status, sender_box)
                            VALUES (%s, %s, %s, %s, %s, %s, 'draft', 'draft', 'draft')
                            """,
                            (sender["id"], internal_address(sender["id"]), sender["name"],
                             subject, body, grade),
                        )
                        message_id = cursor.lastrowid
                        self.insert_attachments(cursor, message_id, [attachment] if attachment else [])

                    cursor.execute(
                        """
                        INSERT INTO mail_recipients
                            (message_id, recipient_id, recipient_address, recipient_name, recipient_box)
                        VALUES (%s, %s, %s, %s, 'none')
                        """,
                        (message_id, recipient_id, recipient_address, recipient_name),
                    )
                connection.commit()
                return message_id
            except Exception:
                connection.rollback()
                raise

    def update_delivery(self, message_id, status, provider_message_id=None):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE mail_messages SET delivery_status = %s, provider_message_id = %s
                    WHERE message_id = %s AND direction = 'outbound'
                    """,
                    (status, provider_message_id, message_id),
                )

    def update_delivery_by_provider(self, provider_message_id, status):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE mail_messages SET delivery_status = %s
                    WHERE provider_message_id = %s AND direction = 'outbound'
                    """,
                    (status, provider_message_id),
                )
                if not cursor.rowcount:
                    return None
                cursor.execute(
                    "SELECT message_id FROM mail_messages WHERE provider_message_id = %s LIMIT 1",
                    (provider_message_id,),
                )
                row = cursor.fetchone()
                return row["message_id"] if row else None

    def receive_external(self, recipient_id, recipient_address, sender_address, sender_name,
                         subject, body, provider_message_id=None, attachments=None):
        with self.connect() as connection:
            try:
                connection.begin()
                with connection.cursor() as cursor:
                    if provider_message_id:
                        cursor.execute(
                            "SELECT message_id FROM mail_messages WHERE provider_message_id = %s LIMIT 1",
                            (provider_message_id,),
                        )
                        existing = cursor.fetchone()
                        if existing:
                            connection.rollback()
                            return existing["message_id"]
                    recipient = self.user_store.get_user(recipient_id)
                    cursor.execute(
                        """
                        INSERT INTO mail_messages
                            (sender_id, sender_address, sender_name, subject, body, security_grade,
                             direction, delivery_status, provider_message_id, sender_box)
                        VALUES (%s, %s, %s, %s, %s, '외부', 'inbound', 'received', %s, 'none')
                        """,
                        (recipient_id, sender_address, sender_name, subject, body, provider_message_id),
                    )
                    message_id = cursor.lastrowid
                    cursor.execute(
                        """
                        INSERT INTO mail_recipients
                            (message_id, recipient_id, recipient_address, recipient_name, recipient_box)
                        VALUES (%s, %s, %s, %s, 'inbox')
                        """,
                        (message_id, recipient_id, recipient_address, recipient["name"]),
                    )
                    self.insert_attachments(cursor, message_id, attachments or [])
                connection.commit()
                return message_id
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def insert_attachments(cursor, message_id, attachments):
        for attachment in attachments:
            cursor.execute(
                """
                INSERT INTO mail_attachments
                    (message_id, file_name, content_type, file_size, file_data)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (message_id, attachment["name"], attachment["contentType"],
                 attachment["size"], attachment["data"]),
            )

    def list_messages(self, user_id, box):
        where_by_box = {
            "inbox": "r.recipient_id = %s AND m.direction IN ('internal', 'inbound') AND r.recipient_box = 'inbox'",
            "sent": "m.sender_id = %s AND m.direction IN ('internal', 'outbound') AND m.sender_box = 'sent'",
            "draft": "m.sender_id = %s AND m.direction = 'draft' AND m.sender_box = 'draft'",
            "trash": "((m.sender_id = %s AND m.sender_box = 'trash') OR (r.recipient_id = %s AND r.recipient_box = 'trash' AND m.direction IN ('internal', 'inbound')))"
        }
        where = where_by_box.get(box, where_by_box["inbox"])
        params = (user_id, user_id) if box == "trash" else (user_id,)
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT m.message_id AS id, m.sender_id AS senderId, s.name AS senderUserName,
                           r.recipient_id AS recipientId, u.name AS recipientUserName,
                           m.subject, m.security_grade AS grade, m.sent_at AS sentAt,
                           r.read_at AS readAt, m.sender_address, m.sender_name,
                           r.recipient_address, r.recipient_name,
                           m.direction, m.delivery_status AS deliveryStatus,
                           m.sender_box AS senderBox, r.recipient_box AS recipientBox,
                           EXISTS(SELECT 1 FROM mail_attachments a WHERE a.message_id = m.message_id) AS hasAttachment
                    FROM mail_messages m
                    JOIN mail_recipients r ON r.message_id = m.message_id
                    JOIN users s ON s.user_id = m.sender_id
                    JOIN users u ON u.user_id = r.recipient_id
                    WHERE {where}
                    ORDER BY m.sent_at DESC, m.message_id DESC
                    LIMIT 200
                    """,
                    params,
                )
                rows = cursor.fetchall()
                for row in rows:
                    sender_view = box in {"sent", "draft"} or (
                        box == "trash" and row["senderId"] == user_id and row["senderBox"] == "trash"
                    )
                    if sender_view:
                        row["otherName"] = row["recipient_name"] or row["recipientUserName"]
                        row["otherAddress"] = row["recipient_address"] or internal_address(row["recipientId"])
                    else:
                        row["otherName"] = row["sender_name"] or row["senderUserName"]
                        row["otherAddress"] = row["sender_address"] or internal_address(row["senderId"])
                    row["sentAt"] = row["sentAt"].isoformat()
                    row["read"] = True if sender_view else bool(row["readAt"])
                    row["hasAttachment"] = bool(row["hasAttachment"])
                    row["mailbox"] = box
                    for key in ("senderId", "senderUserName", "recipientId", "recipientUserName",
                                "readAt", "sender_address", "sender_name", "recipient_address",
                                "recipient_name", "senderBox", "recipientBox"):
                        row.pop(key, None)
                return rows

    def get_message(self, message_id, user_id):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT m.message_id AS id, m.sender_id AS senderId, s.name AS senderName,
                           r.recipient_id AS recipientId, u.name AS recipientName,
                           m.subject, m.body, m.security_grade AS grade, m.sent_at AS sentAt,
                           r.read_at AS readAt, m.direction, m.delivery_status AS deliveryStatus,
                           m.sender_address, m.sender_name AS external_sender_name,
                           r.recipient_address, r.recipient_name AS external_recipient_name,
                           m.sender_box AS senderBox, r.recipient_box AS recipientBox
                    FROM mail_messages m
                    JOIN mail_recipients r ON r.message_id = m.message_id
                    JOIN users s ON s.user_id = m.sender_id
                    JOIN users u ON u.user_id = r.recipient_id
                    WHERE m.message_id = %s AND (
                        (m.sender_id = %s AND m.sender_box NOT IN ('none', 'deleted'))
                        OR (r.recipient_id = %s AND r.recipient_box NOT IN ('none', 'deleted')
                            AND m.direction IN ('internal', 'inbound'))
                    )
                    LIMIT 1
                    """,
                    (message_id, user_id, user_id),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                sender_visible = row["senderId"] == user_id and row["senderBox"] not in {"none", "deleted"}
                recipient_visible = (
                    row["recipientId"] == user_id
                    and row["recipientBox"] not in {"none", "deleted"}
                    and row["direction"] in {"internal", "inbound"}
                )
                viewer_role = "sender" if sender_visible else "recipient"
                if viewer_role == "recipient" and recipient_visible and row["readAt"] is None:
                    cursor.execute(
                        "UPDATE mail_recipients SET read_at = CURRENT_TIMESTAMP WHERE message_id = %s AND recipient_id = %s",
                        (message_id, user_id),
                    )
                if row["direction"] == "inbound":
                    row["senderName"] = row.pop("external_sender_name") or row["sender_address"]
                else:
                    row.pop("external_sender_name", None)
                if row["direction"] in {"outbound", "draft"}:
                    row["recipientName"] = row.pop("external_recipient_name") or row["recipient_address"]
                else:
                    row.pop("external_recipient_name", None)
                row["from"] = row.pop("sender_address") or internal_address(row["senderId"])
                row["to"] = row.pop("recipient_address") or internal_address(row["recipientId"])
                row["sentAt"] = row["sentAt"].isoformat()
                row["readAt"] = row["readAt"].isoformat() if row["readAt"] else None
                row["viewerRole"] = viewer_role
                row["mailbox"] = row["senderBox"] if viewer_role == "sender" else row["recipientBox"]
                row["canRetry"] = (
                    viewer_role == "sender" and row["direction"] == "outbound"
                    and row["deliveryStatus"] == "failed"
                )
                row["canEdit"] = viewer_role == "sender" and row["direction"] == "draft"
                cursor.execute(
                    """
                    SELECT attachment_id AS id, file_name AS name,
                           content_type AS contentType, file_size AS size
                    FROM mail_attachments WHERE message_id = %s ORDER BY attachment_id
                    """,
                    (message_id,),
                )
                row["attachments"] = cursor.fetchall()
                return row

    def get_attachment(self, attachment_id, user_id):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT a.attachment_id AS id, a.file_name AS name, a.content_type AS contentType,
                           a.file_size AS size, a.file_data AS data
                    FROM mail_attachments a
                    JOIN mail_messages m ON m.message_id = a.message_id
                    JOIN mail_recipients r ON r.message_id = m.message_id
                    WHERE a.attachment_id = %s AND (
                        (m.sender_id = %s AND m.sender_box NOT IN ('none', 'deleted'))
                        OR (r.recipient_id = %s AND r.recipient_box NOT IN ('none', 'deleted')
                            AND m.direction IN ('internal', 'inbound'))
                    )
                    LIMIT 1
                    """,
                    (attachment_id, user_id, user_id),
                )
                return cursor.fetchone()

    def move_to_trash(self, message_id, user_id):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                row = self._mailbox_row(cursor, message_id, user_id)
                if not row:
                    return False
                if row["senderId"] == user_id and row["senderBox"] not in {"none", "deleted"}:
                    if row["senderBox"] != "trash":
                        cursor.execute(
                            "UPDATE mail_messages SET sender_previous_box = sender_box, sender_box = 'trash' WHERE message_id = %s",
                            (message_id,),
                        )
                    return True
                if row["recipientId"] == user_id and row["recipientBox"] not in {"none", "deleted"}:
                    if row["recipientBox"] != "trash":
                        cursor.execute(
                            "UPDATE mail_recipients SET recipient_previous_box = recipient_box, recipient_box = 'trash' WHERE message_id = %s AND recipient_id = %s",
                            (message_id, user_id),
                        )
                    return True
        return False

    def restore_message(self, message_id, user_id):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                row = self._mailbox_row(cursor, message_id, user_id)
                if not row:
                    return False
                if row["senderId"] == user_id and row["senderBox"] == "trash":
                    fallback = "draft" if row["direction"] == "draft" else "sent"
                    cursor.execute(
                        "UPDATE mail_messages SET sender_box = COALESCE(sender_previous_box, %s), sender_previous_box = NULL WHERE message_id = %s",
                        (fallback, message_id),
                    )
                    return True
                if row["recipientId"] == user_id and row["recipientBox"] == "trash":
                    cursor.execute(
                        "UPDATE mail_recipients SET recipient_box = COALESCE(recipient_previous_box, 'inbox'), recipient_previous_box = NULL WHERE message_id = %s AND recipient_id = %s",
                        (message_id, user_id),
                    )
                    return True
        return False

    def delete_message(self, message_id, user_id):
        with self.connect() as connection:
            try:
                connection.begin()
                changed = False
                with connection.cursor() as cursor:
                    row = self._mailbox_row(cursor, message_id, user_id)
                    if row and row["senderId"] == user_id and row["senderBox"] == "trash":
                        cursor.execute("UPDATE mail_messages SET sender_box = 'deleted' WHERE message_id = %s", (message_id,))
                        changed = True
                    elif row and row["recipientId"] == user_id and row["recipientBox"] == "trash":
                        cursor.execute(
                            "UPDATE mail_recipients SET recipient_box = 'deleted' WHERE message_id = %s AND recipient_id = %s",
                            (message_id, user_id),
                        )
                        changed = True
                    if changed:
                        self._cleanup_deleted(cursor, message_id)
                if not changed:
                    connection.rollback()
                    return False
                connection.commit()
                return True
            except Exception:
                connection.rollback()
                raise

    def get_draft_attachment(self, message_id, user_id):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT a.attachment_id AS id, a.file_name AS name,
                           a.content_type AS contentType, a.file_size AS size, a.file_data AS data
                    FROM mail_attachments a
                    JOIN mail_messages m ON m.message_id = a.message_id
                    WHERE m.message_id = %s AND m.sender_id = %s AND m.direction = 'draft'
                    ORDER BY a.attachment_id LIMIT 1
                    """,
                    (message_id, user_id),
                )
                return cursor.fetchone()

    def discard_draft(self, message_id, user_id):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM mail_messages WHERE message_id = %s AND sender_id = %s AND direction = 'draft'",
                    (message_id, user_id),
                )
                return bool(cursor.rowcount)

    def get_retry_payload(self, message_id, user_id):
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT m.subject, m.body, r.recipient_address AS `to`
                    FROM mail_messages m
                    JOIN mail_recipients r ON r.message_id = m.message_id
                    WHERE m.message_id = %s AND m.sender_id = %s
                      AND m.direction = 'outbound' AND m.delivery_status = 'failed'
                      AND m.sender_box NOT IN ('none', 'deleted')
                    LIMIT 1
                    """,
                    (message_id, user_id),
                )
                payload = cursor.fetchone()
                if not payload:
                    return None
                cursor.execute(
                    """
                    SELECT file_name AS name, content_type AS contentType,
                           file_size AS size, file_data AS data
                    FROM mail_attachments WHERE message_id = %s ORDER BY attachment_id LIMIT 1
                    """,
                    (message_id,),
                )
                payload["attachment"] = cursor.fetchone()
                return payload

    @staticmethod
    def _mailbox_row(cursor, message_id, user_id):
        cursor.execute(
            """
            SELECT m.message_id, m.sender_id AS senderId, m.direction,
                   m.sender_box AS senderBox, r.recipient_id AS recipientId,
                   r.recipient_box AS recipientBox
            FROM mail_messages m
            JOIN mail_recipients r ON r.message_id = m.message_id
            WHERE m.message_id = %s AND (m.sender_id = %s OR r.recipient_id = %s)
            LIMIT 1
            """,
            (message_id, user_id, user_id),
        )
        return cursor.fetchone()

    @staticmethod
    def _cleanup_deleted(cursor, message_id):
        cursor.execute(
            """
            SELECT m.sender_box AS senderBox,
                   SUM(r.recipient_box NOT IN ('none', 'deleted')) AS visibleRecipients
            FROM mail_messages m
            JOIN mail_recipients r ON r.message_id = m.message_id
            WHERE m.message_id = %s GROUP BY m.message_id, m.sender_box
            """,
            (message_id,),
        )
        row = cursor.fetchone()
        if row and row["senderBox"] in {"none", "deleted"} and not row["visibleRecipients"]:
            cursor.execute("DELETE FROM mail_messages WHERE message_id = %s", (message_id,))


def create_mail_store():
    if USER_STORE.storage_type == "mysql":
        try:
            return MySQLMailStore(USER_STORE)
        except Exception as error:
            print(f"MySQL 메일 저장소 초기화 실패: {error}", flush=True)
    return MemoryMailStore()


MAIL_STORE = create_mail_store()

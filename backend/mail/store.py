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


def user_id_from_address(address):
    normalized = str(address or "").strip().lower()
    suffix = "@datavault.local"
    if not normalized.endswith(suffix):
        raise RecipientNotFoundError("사내 메일 주소만 사용할 수 있습니다.")
    user_id = normalized[:-len(suffix)]
    if not user_id or not USER_STORE.user_exists(user_id):
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

    def __init__(self):
        self.lock = RLock()
        self.messages = []
        self.next_message_id = 1
        self.next_attachment_id = 1

    def list_recipients(self):
        users = getattr(USER_STORE, "users", {}).values()
        return [
            {"id": user["id"], "name": user["name"], "address": internal_address(user["id"])}
            for user in users
        ]

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
            }
            self.next_message_id += 1
            if attachment:
                attachment["id"] = self.next_attachment_id
                self.next_attachment_id += 1
                message["attachment"] = attachment
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
            }
            self.next_message_id += 1
            if attachment:
                attachment["id"] = self.next_attachment_id
                self.next_attachment_id += 1
                message["attachment"] = attachment
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
                "recipientName": USER_STORE.get_user(recipient_id)["name"],
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
        allowed = {"internal", "inbound"} if box == "inbox" else {"internal", "outbound"}
        key = "recipientId" if box == "inbox" else "senderId"
        return [
            self.summary(item, user_id, box) for item in reversed(self.messages)
            if item[key] == user_id and item.get("direction", "internal") in allowed
        ]

    def summary(self, message, user_id, box):
        external = message.get("direction") in {"inbound", "outbound"}
        other_id = message["senderId"] if box == "inbox" else message["recipientId"]
        other = USER_STORE.get_user(other_id)
        return {
            "id": message["id"],
            "subject": message["subject"],
            "grade": message["grade"],
            "sentAt": message["sentAt"],
            "read": bool(message["readAt"]) if box == "inbox" else True,
            "otherName": (
                message.get("senderName") if box == "inbox" else message.get("recipientName")
            ) if external else (other["name"] if other else other_id),
            "otherAddress": (
                message.get("senderAddress") if box == "inbox" else message.get("recipientAddress")
            ) if external else internal_address(other_id),
            "hasAttachment": bool(message["attachment"]),
            "deliveryStatus": message.get("deliveryStatus", "delivered"),
            "direction": message.get("direction", "internal"),
        }

    def get_message(self, message_id, user_id):
        message = next((item for item in self.messages if item["id"] == message_id), None)
        if not message or user_id not in {message["senderId"], message["recipientId"]}:
            return None
        if message["recipientId"] == user_id and not message["readAt"]:
            message["readAt"] = datetime.now(timezone.utc).isoformat()
        return self.detail(message)

    def detail(self, message):
        attachments = message.get("attachments") or ([message["attachment"]] if message["attachment"] else [])
        return {
            **{key: value for key, value in message.items() if key not in {"attachment", "attachments"}},
            "from": message.get("senderAddress") or internal_address(message["senderId"]),
            "to": message.get("recipientAddress") or internal_address(message["recipientId"]),
            "attachments": [
                {key: attachment[key] for key in ("id", "name", "contentType", "size")}
                for attachment in attachments
            ],
        }

    def get_attachment(self, attachment_id, user_id):
        for message in self.messages:
            attachments = message.get("attachments") or ([message["attachment"]] if message["attachment"] else [])
            for attachment in attachments:
                if attachment["id"] == attachment_id and user_id in {message["senderId"], message["recipientId"]}:
                    return attachment
        return None


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
                self.ensure_column(cursor, "mail_recipients", "recipient_address", "VARCHAR(254) NULL AFTER recipient_id")
                self.ensure_column(cursor, "mail_recipients", "recipient_name", "VARCHAR(120) NULL AFTER recipient_address")

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
                        "INSERT INTO mail_messages (sender_id, subject, body, security_grade) VALUES (%s, %s, %s, %s)",
                        (sender["id"], subject, body, grade),
                    )
                    message_id = cursor.lastrowid
                    cursor.execute(
                        "INSERT INTO mail_recipients (message_id, recipient_id) VALUES (%s, %s)",
                        (message_id, recipient_id),
                    )
                    if attachment:
                        cursor.execute(
                            """
                            INSERT INTO mail_attachments
                                (message_id, file_name, content_type, file_size, file_data)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (message_id, attachment["name"], attachment["contentType"], attachment["size"], attachment["data"]),
                        )
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
                             direction, delivery_status)
                        VALUES (%s, %s, %s, %s, %s, %s, 'outbound', 'pending')
                        """,
                        (sender["id"], internal_address(sender["id"]), sender["name"], subject, body, grade),
                    )
                    message_id = cursor.lastrowid
                    cursor.execute(
                        """
                        INSERT INTO mail_recipients
                            (message_id, recipient_id, recipient_address, recipient_name)
                        VALUES (%s, %s, %s, %s)
                        """,
                        (message_id, sender["id"], recipient_address, recipient_address),
                    )
                    self.insert_attachments(cursor, message_id, [attachment] if attachment else [])
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
                             direction, delivery_status, provider_message_id)
                        VALUES (%s, %s, %s, %s, %s, '외부', 'inbound', 'received', %s)
                        """,
                        (recipient_id, sender_address, sender_name, subject, body, provider_message_id),
                    )
                    message_id = cursor.lastrowid
                    cursor.execute(
                        """
                        INSERT INTO mail_recipients
                            (message_id, recipient_id, recipient_address, recipient_name)
                        VALUES (%s, %s, %s, %s)
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
        if box == "inbox":
            where = "r.recipient_id = %s AND m.direction IN ('internal', 'inbound')"
            read_sql = "r.read_at IS NOT NULL"
            other_name = "CASE WHEN m.direction = 'inbound' THEN m.sender_name ELSE s.name END"
            other_address = "CASE WHEN m.direction = 'inbound' THEN m.sender_address ELSE CONCAT(m.sender_id, '@datavault.local') END"
        else:
            where = "m.sender_id = %s AND m.direction IN ('internal', 'outbound')"
            read_sql = "TRUE"
            other_name = "CASE WHEN m.direction = 'outbound' THEN r.recipient_name ELSE u.name END"
            other_address = "CASE WHEN m.direction = 'outbound' THEN r.recipient_address ELSE CONCAT(r.recipient_id, '@datavault.local') END"
        with self.connect() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    f"""
                    SELECT m.message_id AS id, m.subject, m.security_grade AS grade,
                           m.sent_at AS sentAt, {read_sql} AS `read`,
                           {other_name} AS otherName, {other_address} AS otherAddress,
                           m.direction, m.delivery_status AS deliveryStatus,
                           EXISTS(SELECT 1 FROM mail_attachments a WHERE a.message_id = m.message_id) AS hasAttachment
                    FROM mail_messages m
                    JOIN mail_recipients r ON r.message_id = m.message_id
                    JOIN users s ON s.user_id = m.sender_id
                    JOIN users u ON u.user_id = r.recipient_id
                    WHERE {where}
                    ORDER BY m.sent_at DESC, m.message_id DESC
                    LIMIT 200
                    """,
                    (user_id,),
                )
                rows = cursor.fetchall()
                for row in rows:
                    row["sentAt"] = row["sentAt"].isoformat()
                    row["read"] = bool(row["read"])
                    row["hasAttachment"] = bool(row["hasAttachment"])
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
                           r.recipient_address, r.recipient_name AS external_recipient_name
                    FROM mail_messages m
                    JOIN mail_recipients r ON r.message_id = m.message_id
                    JOIN users s ON s.user_id = m.sender_id
                    JOIN users u ON u.user_id = r.recipient_id
                    WHERE m.message_id = %s AND (m.sender_id = %s OR r.recipient_id = %s)
                    LIMIT 1
                    """,
                    (message_id, user_id, user_id),
                )
                row = cursor.fetchone()
                if not row:
                    return None
                if row["recipientId"] == user_id and row["readAt"] is None:
                    cursor.execute(
                        "UPDATE mail_recipients SET read_at = CURRENT_TIMESTAMP WHERE message_id = %s AND recipient_id = %s",
                        (message_id, user_id),
                    )
                if row["direction"] == "inbound":
                    row["senderName"] = row.pop("external_sender_name") or row["sender_address"]
                else:
                    row.pop("external_sender_name", None)
                if row["direction"] == "outbound":
                    row["recipientName"] = row.pop("external_recipient_name") or row["recipient_address"]
                else:
                    row.pop("external_recipient_name", None)
                row["from"] = row.pop("sender_address") or internal_address(row["senderId"])
                row["to"] = row.pop("recipient_address") or internal_address(row["recipientId"])
                row["sentAt"] = row["sentAt"].isoformat()
                row["readAt"] = row["readAt"].isoformat() if row["readAt"] else None
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
                    WHERE a.attachment_id = %s AND (m.sender_id = %s OR r.recipient_id = %s)
                    LIMIT 1
                    """,
                    (attachment_id, user_id, user_id),
                )
                return cursor.fetchone()


def create_mail_store():
    if USER_STORE.storage_type == "mysql":
        try:
            return MySQLMailStore(USER_STORE)
        except Exception as error:
            print(f"MySQL 메일 저장소 초기화 실패: {error}", flush=True)
    return MemoryMailStore()


MAIL_STORE = create_mail_store()

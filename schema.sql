CREATE TABLE IF NOT EXISTS users (
  user_id VARCHAR(64) PRIMARY KEY,
  name VARCHAR(80) NOT NULL,
  role VARCHAR(30) NOT NULL,
  email VARCHAR(254) NULL,
  password_salt VARCHAR(128) NOT NULL,
  password_hash VARCHAR(128) NOT NULL,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS password_reset_tokens (
  token_hash CHAR(64) PRIMARY KEY,
  user_id VARCHAR(64) NOT NULL,
  expires_at BIGINT NOT NULL,
  used TINYINT(1) NOT NULL DEFAULT 0,
  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_password_reset_user_id (user_id),
  INDEX idx_password_reset_expires_at (expires_at)
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS mail_messages (
  message_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  sender_id VARCHAR(64) NOT NULL,
  sender_address VARCHAR(254) NULL,
  sender_name VARCHAR(120) NULL,
  subject VARCHAR(200) NOT NULL,
  body TEXT NOT NULL,
  security_grade VARCHAR(20) NOT NULL DEFAULT '내부',
  direction VARCHAR(16) NOT NULL DEFAULT 'internal',
  delivery_status VARCHAR(24) NOT NULL DEFAULT 'delivered',
  provider_message_id VARCHAR(255) NULL,
  sent_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  INDEX idx_mail_messages_sender_sent (sender_id, sent_at),
  CONSTRAINT fk_mail_messages_sender FOREIGN KEY (sender_id)
    REFERENCES users(user_id) ON DELETE RESTRICT
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS mail_recipients (
  message_id BIGINT UNSIGNED NOT NULL,
  recipient_id VARCHAR(64) NOT NULL,
  recipient_address VARCHAR(254) NULL,
  recipient_name VARCHAR(120) NULL,
  read_at TIMESTAMP NULL,
  PRIMARY KEY (message_id, recipient_id),
  INDEX idx_mail_recipients_inbox (recipient_id, message_id),
  CONSTRAINT fk_mail_recipients_message FOREIGN KEY (message_id)
    REFERENCES mail_messages(message_id) ON DELETE CASCADE,
  CONSTRAINT fk_mail_recipients_user FOREIGN KEY (recipient_id)
    REFERENCES users(user_id) ON DELETE RESTRICT
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

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
) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

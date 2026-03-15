-- =============================================================
-- CodeWiki 数据库初始化脚本
-- 支持 MySQL 8.0+
--
-- 版本要求：
--   MySQL 8.0.13+ — 支持表达式默认值 DEFAULT (UUID())
--   MySQL 8.0.16+ — 支持 CHECK 约束
-- =============================================================

-- =============================================================
-- 1. 用户账户表 (users)
--    存储用户的基本认证信息
-- =============================================================
CREATE TABLE IF NOT EXISTS `users` (
    `id`            CHAR(36)     NOT NULL DEFAULT (UUID())           COMMENT '用户唯一标识（UUID）',
    `username`      VARCHAR(64)  NOT NULL                            COMMENT '用户名，全局唯一，长度限制 64 字符',
    `email`         VARCHAR(255) NOT NULL                            COMMENT '电子邮件地址，全局唯一',
    `password_hash` VARCHAR(255) NOT NULL                            COMMENT '密码的哈希值（bcrypt 等算法处理后存储，禁止明文）',
    `is_active`     TINYINT(1)   NOT NULL DEFAULT 1                  COMMENT '账户是否启用；0 表示已停用或待验证',
    `created_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '账户创建时间',
    `updated_at`    DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                          ON UPDATE CURRENT_TIMESTAMP COMMENT '账户最后更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_users_username` (`username`),
    UNIQUE KEY `uq_users_email`    (`email`),
    INDEX `idx_users_username` (`username`),
    INDEX `idx_users_email`    (`email`)
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci
  COMMENT = '用户账户表：存储用户基本认证信息';

-- =============================================================
-- 2. 用户配置表 (user_settings)
--    与 users 一对一，存储个性化偏好
-- =============================================================
CREATE TABLE IF NOT EXISTS `user_settings` (
    `id`                    CHAR(36)     NOT NULL DEFAULT (UUID())           COMMENT '配置记录唯一标识（UUID）',
    `user_id`               CHAR(36)     NOT NULL                            COMMENT '关联的用户 ID，外键到 users.id',
    `preferred_language`    VARCHAR(16)  NOT NULL DEFAULT 'zh'               COMMENT '界面首选语言，如 zh / en',
    `preferred_model`       VARCHAR(128)     NULL DEFAULT NULL               COMMENT '用户偏好使用的 AI 模型标识符',
    `theme`                 VARCHAR(16)  NOT NULL DEFAULT 'light'            COMMENT 'UI 主题：light / dark',
    `notifications_enabled` TINYINT(1)   NOT NULL DEFAULT 1                  COMMENT '是否启用通知',
    `extra_config`          JSON             NULL DEFAULT NULL               COMMENT '扩展配置（JSON），用于存储未来新增的偏好字段',
    `created_at`            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '配置创建时间',
    `updated_at`            DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                                  ON UPDATE CURRENT_TIMESTAMP COMMENT '配置最后更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uq_user_settings_user_id` (`user_id`),
    CONSTRAINT `fk_user_settings_user_id`
        FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci
  COMMENT = '用户配置表：存储用户个性化偏好，与 users 一对一关联';

-- =============================================================
-- 3. 对话历史表 (conversations)
--    存储用户与 AI 模型的对话会话
-- =============================================================
CREATE TABLE IF NOT EXISTS `conversations` (
    `id`          CHAR(36)     NOT NULL DEFAULT (UUID())           COMMENT '对话唯一标识（UUID）',
    `user_id`     CHAR(36)     NOT NULL                            COMMENT '发起对话的用户 ID，外键到 users.id',
    `repo_owner`  VARCHAR(255) NOT NULL                            COMMENT '仓库所有者（用户名或组织名）',
    `repo_name`   VARCHAR(255) NOT NULL                            COMMENT '仓库名称',
    `repo_type`   VARCHAR(32)  NOT NULL DEFAULT 'github'           COMMENT '仓库类型：github / gitlab / local 等',
    `title`       VARCHAR(512)     NULL DEFAULT NULL               COMMENT '对话标题，可由系统自动生成或用户手动设置',
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP  COMMENT '对话创建时间',
    `updated_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                        ON UPDATE CURRENT_TIMESTAMP COMMENT '对话最后更新时间（有新消息时自动更新）',
    PRIMARY KEY (`id`),
    INDEX `idx_conversations_user_id`    (`user_id`),
    INDEX `idx_conversations_repo`       (`repo_owner`, `repo_name`),
    INDEX `idx_conversations_updated_at` (`updated_at` DESC),
    CONSTRAINT `fk_conversations_user_id`
        FOREIGN KEY (`user_id`) REFERENCES `users` (`id`) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci
  COMMENT = '对话历史表：存储用户与 AI 的对话会话';

-- =============================================================
-- 4. 对话消息表 (conversation_messages)
--    存储对话中的具体消息（用户提问 + 模型回答）
-- =============================================================
CREATE TABLE IF NOT EXISTS `conversation_messages` (
    `id`              CHAR(36)  NOT NULL DEFAULT (UUID())          COMMENT '消息唯一标识（UUID）',
    `conversation_id` CHAR(36)  NOT NULL                           COMMENT '所属对话 ID，外键到 conversations.id',
    `role`            VARCHAR(16) NOT NULL                         COMMENT '消息角色：user（用户提问）或 assistant（模型回答）',
    `content`         TEXT      NOT NULL                           COMMENT '消息正文内容',
    `token_count`     INT           NULL DEFAULT NULL              COMMENT '消息的 token 数量（可选，用于计费统计）',
    `created_at`      DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '消息创建时间',
    PRIMARY KEY (`id`),
    INDEX `idx_conv_messages_conversation_id` (`conversation_id`),
    INDEX `idx_conv_messages_created_at`      (`conversation_id`, `created_at`),
    CONSTRAINT `ck_conv_msg_role`
        CHECK (`role` IN ('user', 'assistant')),
    CONSTRAINT `fk_conv_messages_conversation_id`
        FOREIGN KEY (`conversation_id`) REFERENCES `conversations` (`id`) ON DELETE CASCADE
) ENGINE = InnoDB
  DEFAULT CHARSET = utf8mb4
  COLLATE = utf8mb4_unicode_ci
  COMMENT = '对话消息表：存储对话中每条具体消息';


-- =============================================================
-- CodeWiki 数据库初始化脚本
-- 支持 PostgreSQL（推荐）
-- =============================================================

-- =============================================================
-- 1. 用户账户表 (users)
--    存储用户的基本认证信息
-- =============================================================
CREATE TABLE IF NOT EXISTS users (
    id            UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    username      VARCHAR(64)  NOT NULL UNIQUE,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active     BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  users                IS '用户账户表：存储用户基本认证信息';
COMMENT ON COLUMN users.id            IS '用户唯一标识（UUID）';
COMMENT ON COLUMN users.username      IS '用户名，全局唯一，长度限制 64 字符';
COMMENT ON COLUMN users.email         IS '电子邮件地址，全局唯一';
COMMENT ON COLUMN users.password_hash IS '密码的哈希值（bcrypt 等算法处理后存储，禁止明文）';
COMMENT ON COLUMN users.is_active     IS '账户是否启用；FALSE 表示已停用或待验证';
COMMENT ON COLUMN users.created_at    IS '账户创建时间';
COMMENT ON COLUMN users.updated_at    IS '账户最后更新时间';

-- 索引
CREATE INDEX IF NOT EXISTS idx_users_email    ON users (email);
CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);

-- =============================================================
-- 2. 用户配置表 (user_settings)
--    与 users 一对一，存储个性化偏好
-- =============================================================
CREATE TABLE IF NOT EXISTS user_settings (
    id                   UUID        PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id              UUID        NOT NULL UNIQUE REFERENCES users (id) ON DELETE CASCADE,
    preferred_language   VARCHAR(16)  NOT NULL DEFAULT 'zh',
    preferred_model      VARCHAR(128),
    theme                VARCHAR(16)  NOT NULL DEFAULT 'light',
    notifications_enabled BOOLEAN    NOT NULL DEFAULT TRUE,
    extra_config         JSONB,
    created_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at           TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  user_settings                      IS '用户配置表：存储用户个性化偏好，与 users 一对一关联';
COMMENT ON COLUMN user_settings.id                   IS '配置记录唯一标识（UUID）';
COMMENT ON COLUMN user_settings.user_id              IS '关联的用户 ID，外键到 users.id';
COMMENT ON COLUMN user_settings.preferred_language   IS '界面首选语言，如 zh / en';
COMMENT ON COLUMN user_settings.preferred_model      IS '用户偏好使用的 AI 模型标识符';
COMMENT ON COLUMN user_settings.theme                IS 'UI 主题：light / dark';
COMMENT ON COLUMN user_settings.notifications_enabled IS '是否启用通知';
COMMENT ON COLUMN user_settings.extra_config         IS '扩展配置（JSON），用于存储未来新增的偏好字段';
COMMENT ON COLUMN user_settings.created_at           IS '配置创建时间';
COMMENT ON COLUMN user_settings.updated_at           IS '配置最后更新时间';

-- =============================================================
-- 3. 对话历史表 (conversations)
--    存储用户与 AI 模型的对话会话
-- =============================================================
CREATE TABLE IF NOT EXISTS conversations (
    id           UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id      UUID         NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    repo_owner   VARCHAR(255) NOT NULL,
    repo_name    VARCHAR(255) NOT NULL,
    repo_type    VARCHAR(32)  NOT NULL DEFAULT 'github',
    title        VARCHAR(512),
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  conversations             IS '对话历史表：存储用户与 AI 的对话会话';
COMMENT ON COLUMN conversations.id          IS '对话唯一标识（UUID）';
COMMENT ON COLUMN conversations.user_id     IS '发起对话的用户 ID，外键到 users.id';
COMMENT ON COLUMN conversations.repo_owner  IS '仓库所有者（用户名或组织名）';
COMMENT ON COLUMN conversations.repo_name   IS '仓库名称';
COMMENT ON COLUMN conversations.repo_type   IS '仓库类型：github / gitlab / local 等';
COMMENT ON COLUMN conversations.title       IS '对话标题，可由系统自动生成或用户手动设置';
COMMENT ON COLUMN conversations.created_at  IS '对话创建时间';
COMMENT ON COLUMN conversations.updated_at  IS '对话最后更新时间（有新消息时自动更新）';

-- 索引
CREATE INDEX IF NOT EXISTS idx_conversations_user_id   ON conversations (user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_repo      ON conversations (repo_owner, repo_name);
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations (updated_at DESC);

-- =============================================================
-- 4. 对话消息表 (conversation_messages)
--    存储对话中的具体消息（用户提问 + 模型回答）
-- =============================================================
CREATE TABLE IF NOT EXISTS conversation_messages (
    id              UUID        PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID        NOT NULL REFERENCES conversations (id) ON DELETE CASCADE,
    role            VARCHAR(16) NOT NULL CHECK (role IN ('user', 'assistant')),
    content         TEXT        NOT NULL,
    token_count     INTEGER,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE  conversation_messages                 IS '对话消息表：存储对话中每条具体消息';
COMMENT ON COLUMN conversation_messages.id              IS '消息唯一标识（UUID）';
COMMENT ON COLUMN conversation_messages.conversation_id IS '所属对话 ID，外键到 conversations.id';
COMMENT ON COLUMN conversation_messages.role            IS '消息角色：user（用户提问）或 assistant（模型回答）';
COMMENT ON COLUMN conversation_messages.content         IS '消息正文内容';
COMMENT ON COLUMN conversation_messages.token_count     IS '消息的 token 数量（可选，用于计费统计）';
COMMENT ON COLUMN conversation_messages.created_at      IS '消息创建时间';

-- 索引
CREATE INDEX IF NOT EXISTS idx_conv_messages_conversation_id ON conversation_messages (conversation_id);
CREATE INDEX IF NOT EXISTS idx_conv_messages_created_at      ON conversation_messages (conversation_id, created_at);

-- =============================================================
-- 自动更新 updated_at 的触发器函数
-- =============================================================
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER trg_user_settings_updated_at
    BEFORE UPDATE ON user_settings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

CREATE OR REPLACE TRIGGER trg_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

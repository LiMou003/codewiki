# 数据库设计文档

## 概述

本文档描述 CodeWiki 登录 / 注册功能所需的关系型数据库设计。  
数据库使用 **PostgreSQL**，SQL 初始化脚本位于 `api/database/init.sql`，  
Python ORM 模型位于 `api/database/models.py`，  
TypeScript 类型定义位于 `src/types/database.ts`。

---

## 表关系图

```
users (1) ─────────────────── (1) user_settings
  │
  └── (1) ──────────────────── (多) conversations
                                        │
                                        └── (1) ──── (多) conversation_messages
```

---

## 表结构

### 1. `users` — 用户账户表

存储用户基本认证信息。

| 字段            | 类型             | 约束                      | 说明                             |
|----------------|-----------------|--------------------------|----------------------------------|
| `id`           | UUID            | PRIMARY KEY, DEFAULT uuid | 用户唯一标识                      |
| `username`     | VARCHAR(64)     | NOT NULL, UNIQUE          | 用户名，全局唯一                  |
| `email`        | VARCHAR(255)    | NOT NULL, UNIQUE          | 电子邮件地址，全局唯一            |
| `password_hash`| VARCHAR(255)    | NOT NULL                  | 密码哈希值（bcrypt 等）           |
| `is_active`    | BOOLEAN         | NOT NULL, DEFAULT TRUE    | 账户是否启用                      |
| `created_at`   | TIMESTAMPTZ     | NOT NULL, DEFAULT NOW()   | 创建时间                          |
| `updated_at`   | TIMESTAMPTZ     | NOT NULL, DEFAULT NOW()   | 最后更新时间（触发器自动维护）    |

**索引**：`idx_users_email`、`idx_users_username`

---

### 2. `user_settings` — 用户配置表

与 `users` 一对一，存储个性化偏好。

| 字段                    | 类型         | 约束                              | 说明                        |
|------------------------|-------------|----------------------------------|-----------------------------|
| `id`                   | UUID        | PRIMARY KEY                      | 配置唯一标识                 |
| `user_id`              | UUID        | NOT NULL, UNIQUE, FK → users.id  | 关联用户                     |
| `preferred_language`   | VARCHAR(16) | NOT NULL, DEFAULT 'zh'           | 首选界面语言                  |
| `preferred_model`      | VARCHAR(128)| NULLABLE                         | 偏好 AI 模型                 |
| `theme`                | VARCHAR(16) | NOT NULL, DEFAULT 'light'        | UI 主题（light / dark）      |
| `notifications_enabled`| BOOLEAN     | NOT NULL, DEFAULT TRUE           | 是否启用通知                  |
| `extra_config`         | JSONB       | NULLABLE                         | 扩展配置（JSON 格式）         |
| `created_at`           | TIMESTAMPTZ | NOT NULL, DEFAULT NOW()          | 创建时间                      |
| `updated_at`           | TIMESTAMPTZ | NOT NULL, DEFAULT NOW()          | 最后更新时间                  |

---

### 3. `conversations` — 对话历史表

存储用户与 AI 模型的对话会话，与特定仓库关联。

| 字段          | 类型          | 约束                         | 说明                                      |
|--------------|--------------|-----------------------------|--------------------------------------------|
| `id`         | UUID         | PRIMARY KEY                 | 对话唯一标识                               |
| `user_id`    | UUID         | NOT NULL, FK → users.id     | 发起对话的用户                             |
| `repo_owner` | VARCHAR(255) | NOT NULL                    | 仓库所有者（用户名或组织名）               |
| `repo_name`  | VARCHAR(255) | NOT NULL                    | 仓库名称                                   |
| `repo_type`  | VARCHAR(32)  | NOT NULL, DEFAULT 'github'  | 仓库类型（github / gitlab / local 等）    |
| `title`      | VARCHAR(512) | NULLABLE                    | 对话标题                                   |
| `created_at` | TIMESTAMPTZ  | NOT NULL, DEFAULT NOW()     | 创建时间                                   |
| `updated_at` | TIMESTAMPTZ  | NOT NULL, DEFAULT NOW()     | 最后更新时间                               |

**索引**：`idx_conversations_user_id`、`idx_conversations_repo`、`idx_conversations_updated_at`

---

### 4. `conversation_messages` — 对话消息表

存储对话中每条具体消息（用户提问 + 模型回答）。

| 字段               | 类型         | 约束                                        | 说明                                    |
|-------------------|-------------|--------------------------------------------|-----------------------------------------|
| `id`              | UUID        | PRIMARY KEY                                | 消息唯一标识                             |
| `conversation_id` | UUID        | NOT NULL, FK → conversations.id            | 所属对话                                 |
| `role`            | VARCHAR(16) | NOT NULL, CHECK IN ('user','assistant')    | 消息角色                                 |
| `content`         | TEXT        | NOT NULL                                   | 消息正文内容                             |
| `token_count`     | INTEGER     | NULLABLE                                   | Token 数量（计费统计用）                 |
| `created_at`      | TIMESTAMPTZ | NOT NULL, DEFAULT NOW()                    | 消息创建时间                             |

**索引**：`idx_conv_messages_conversation_id`、`idx_conv_messages_created_at`

---

## 数据完整性

- 所有外键均设置 `ON DELETE CASCADE`，删除用户时自动级联删除关联数据。
- `role` 字段通过 `CHECK` 约束限制为 `'user'` 或 `'assistant'`。
- `password_hash` 字段**禁止存储明文密码**，应使用 bcrypt / argon2 等算法处理后再存储。
- `updated_at` 字段由数据库触发器在每次 `UPDATE` 时自动维护，无需应用层干预。

---

## 快速启动

### 初始化数据库

```bash
# 创建数据库
createdb codewiki

# 执行初始化脚本
psql -d codewiki -f api/database/init.sql
```

### 使用 SQLAlchemy ORM

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from api.database.models import Base, User, UserSettings, Conversation, ConversationMessage

DATABASE_URL = "postgresql+psycopg2://user:password@localhost/codewiki"
engine = create_engine(DATABASE_URL)

# 创建所有表（开发环境可用，生产环境建议使用迁移工具）
Base.metadata.create_all(engine)

# 创建用户示例
with Session(engine) as session:
    user = User(
        username="alice",
        email="alice@example.com",
        password_hash="$2b$12$...",  # bcrypt 哈希
    )
    session.add(user)
    session.flush()

    settings = UserSettings(user_id=user.id, preferred_language="zh")
    session.add(settings)
    session.commit()
```

### 使用 TypeScript 类型

```typescript
import type { User, Conversation, ConversationMessage } from "@/types/database";

const user: User = await fetchUser(userId);
const conversations: Conversation[] = await fetchConversations(user.id);
```

---

## 依赖

| 依赖               | 说明                          |
|-------------------|-------------------------------|
| PostgreSQL ≥ 14   | 关系型数据库                   |
| SQLAlchemy ≥ 2.0  | Python ORM（需额外安装）       |
| psycopg2-binary   | PostgreSQL Python 驱动        |

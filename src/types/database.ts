/**
 * TypeScript 类型定义 — CodeWiki 数据库实体
 *
 * 与后端 SQLAlchemy 模型（api/database/models.py）及
 * SQL 脚本（api/database/init.sql）保持一致。
 */

// =============================================================
// 1. 用户账户 (users)
// =============================================================

/** 创建新用户时的请求体 */
export interface CreateUserRequest {
  username: string;
  email: string;
  /** 明文密码（传输后由后端哈希处理，禁止直接存储） */
  password: string;
}

/** 用户账户实体（对应数据库 users 表） */
export interface User {
  id: string;
  username: string;
  email: string;
  isActive: boolean;
  createdAt: string; // ISO 8601
  updatedAt: string; // ISO 8601
}

// =============================================================
// 2. 用户配置 (user_settings)
// =============================================================

/** 用户配置实体（对应数据库 user_settings 表） */
export interface UserSettings {
  id: string;
  userId: string;
  preferredLanguage: string;
  preferredModel: string | null;
  theme: "light" | "dark";
  notificationsEnabled: boolean;
  extraConfig: Record<string, unknown> | null;
  createdAt: string;
  updatedAt: string;
}

/** 更新用户配置时的请求体（所有字段均可选） */
export type UpdateUserSettingsRequest = Partial<
  Pick<
    UserSettings,
    | "preferredLanguage"
    | "preferredModel"
    | "theme"
    | "notificationsEnabled"
    | "extraConfig"
  >
>;

// =============================================================
// 3. 对话历史 (conversations)
// =============================================================

/** 对话历史实体（对应数据库 conversations 表） */
export interface Conversation {
  id: string;
  userId: string;
  repoOwner: string;
  repoName: string;
  repoType: string;
  title: string | null;
  createdAt: string;
  updatedAt: string;
}

/** 创建新对话时的请求体 */
export interface CreateConversationRequest {
  repoOwner: string;
  repoName: string;
  repoType?: string;
  title?: string;
}

// =============================================================
// 4. 对话消息 (conversation_messages)
// =============================================================

/** 消息发送方角色 */
export type MessageRole = "user" | "assistant";

/** 对话消息实体（对应数据库 conversation_messages 表） */
export interface ConversationMessage {
  id: string;
  conversationId: string;
  role: MessageRole;
  content: string;
  tokenCount: number | null;
  createdAt: string;
}

/** 创建新消息时的请求体 */
export interface CreateConversationMessageRequest {
  role: MessageRole;
  content: string;
  tokenCount?: number;
}

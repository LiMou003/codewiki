import {
  Conversation,
  CreateConversationRequest,
  ConversationMessage,
  CreateConversationMessageRequest,
  MessageFeedback,
  CreateFeedbackRequest,
} from '@/types/database';

function getAuthHeaders(): HeadersInit {
  const token = typeof window !== 'undefined' ? localStorage.getItem('cw_token') : null;
  const headers: HeadersInit = {
    'Content-Type': 'application/json',
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }
  return headers;
}

export async function getConversations(
  repoOwner: string,
  repoName: string
): Promise<Conversation[]> {
  const res = await fetch(
    `/api/conversations?repo_owner=${encodeURIComponent(repoOwner)}&repo_name=${encodeURIComponent(repoName)}`,
    { headers: getAuthHeaders() }
  );
  if (!res.ok) throw new Error(`Failed to fetch conversations: ${res.status}`);
  return res.json();
}

export async function getConversationMessages(
  conversationId: string
): Promise<ConversationMessage[]> {
  const res = await fetch(
    `/api/conversations/${encodeURIComponent(conversationId)}/messages`,
    { headers: getAuthHeaders() }
  );
  if (!res.ok) throw new Error(`Failed to fetch messages: ${res.status}`);
  return res.json();
}

export async function deleteConversation(
  conversationId: string
): Promise<void> {
  const res = await fetch(
    `/api/conversations/${encodeURIComponent(conversationId)}`,
    { method: 'DELETE', headers: getAuthHeaders() }
  );
  if (!res.ok) throw new Error(`Failed to delete conversation: ${res.status}`);
}

export async function createConversation(
  data: CreateConversationRequest
): Promise<Conversation> {
  const res = await fetch('/api/conversations', {
    method: 'POST',
    headers: getAuthHeaders(),
    body: JSON.stringify(data),
  });
  if (!res.ok) throw new Error(`Failed to create conversation: ${res.status}`);
  return res.json();
}

export async function deleteMessage(
  conversationId: string,
  messageId: string
): Promise<void> {
  const res = await fetch(
    `/api/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}`,
    { method: 'DELETE', headers: getAuthHeaders() }
  );
  if (!res.ok) throw new Error(`Failed to delete message: ${res.status}`);
}

export async function createMessage(
  conversationId: string,
  data: CreateConversationMessageRequest
): Promise<ConversationMessage> {
  const res = await fetch(
    `/api/conversations/${encodeURIComponent(conversationId)}/messages`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    }
  );
  if (!res.ok) throw new Error(`Failed to create message: ${res.status}`);
  return res.json();
}

export async function updateMessage(
  conversationId: string,
  messageId: string,
  data: { content?: string; tokenCount?: number; messageType?: string }
): Promise<ConversationMessage> {
  const res = await fetch(
    `/api/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}`,
    {
      method: 'PATCH',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    }
  );
  if (!res.ok) throw new Error(`Failed to update message: ${res.status}`);
  return res.json();
}

export async function submitFeedback(
  conversationId: string,
  messageId: string,
  data: CreateFeedbackRequest
): Promise<MessageFeedback> {
  const res = await fetch(
    `/api/conversations/${encodeURIComponent(conversationId)}/messages/${encodeURIComponent(messageId)}/feedback`,
    {
      method: 'POST',
      headers: getAuthHeaders(),
      body: JSON.stringify(data),
    }
  );
  if (!res.ok) {
    if (res.status === 409) {
      throw new Error('该消息已经反馈过');
    }
    throw new Error(`Failed to submit feedback: ${res.status}`);
  }
  return res.json();
}

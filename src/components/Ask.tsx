'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { FaPlus, FaTrash, FaComments, FaRobot, FaUser, FaChevronLeft, FaChevronRight, FaPaperPlane, FaTimes, FaThumbsUp, FaThumbsDown } from 'react-icons/fa';
import Markdown from './Markdown';
import { useLanguage } from '@/contexts/LanguageContext';
import RepoInfo from '@/types/repoinfo';
import getRepoUrl from '@/utils/getRepoUrl';
import ModelSelectionModal from './ModelSelectionModal';
import { createChatWebSocket, closeWebSocket, createDeepResearchWebSocket, ChatCompletionRequest } from '@/utils/websocketClient';
import {
  Conversation,
  ConversationMessage,
  CreateConversationRequest,
  FeedbackStatus,
} from '@/types/database';
import * as conversationApi from '@/services/conversationApi';

interface Model {
  id: string;
  name: string;
}

interface Provider {
  id: string;
  name: string;
  models: Model[];
  supportsCustomModel?: boolean;
}

interface ChatPage {
  type: 'plan' | 'update' | 'conclusion';
  title: string;
  content: string;
}

interface ChatMessageItem {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  createdAt: string;
  isStreaming?: boolean;
  feedbackStatus?: FeedbackStatus;
  hasDeepResearch?: boolean;
  pages?: ChatPage[];
  currentPage?: number;
}

interface AskProps {
  repoInfo: RepoInfo;
  provider?: string;
  model?: string;
  isCustomModel?: boolean;
  customModel?: string;
  language?: string;
  onRef?: (ref: { clearConversation: () => void }) => void;
}

const Ask: React.FC<AskProps> = ({
  repoInfo,
  provider = '',
  model = '',
  isCustomModel = false,
  customModel = '',
  language = 'en',
  onRef,
}) => {
  const [question, setQuestion] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [deepResearch, setDeepResearch] = useState(false);

  const [selectedProvider, setSelectedProvider] = useState(provider);
  const [selectedModel, setSelectedModel] = useState(model);
  const [isCustomSelectedModel, setIsCustomSelectedModel] = useState(isCustomModel);
  const [customSelectedModel, setCustomSelectedModel] = useState(customModel);
  const [isModelSelectionModalOpen, setIsModelSelectionModalOpen] = useState(false);
  const [isComprehensiveView, setIsComprehensiveView] = useState(true);

  const { messages } = useLanguage();

  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [currentConversationId, setCurrentConversationId] = useState<string | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessageItem[]>([]);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);

  const [feedbackModalOpen, setFeedbackModalOpen] = useState(false);
  const [feedbackTargetMsgId, setFeedbackTargetMsgId] = useState<string | null>(null);
  const [feedbackComment, setFeedbackComment] = useState('');
  const [feedbackSubmitting, setFeedbackSubmitting] = useState(false);

  const inputRef = useRef<HTMLInputElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const providerRef = useRef(provider);
  const modelRef = useRef(model);
  const webSocketRef = useRef<WebSocket | null>(null);
  const skipScrollRef = useRef(false);

  const clearConversation = useCallback(() => {
    setQuestion('');
    setChatMessages([]);
    setCurrentConversationId(null);
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []);

  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, [currentConversationId]);

  useEffect(() => {
    if (onRef) {
      onRef({ clearConversation });
    }
  }, [onRef, clearConversation]);

  useEffect(() => {
    if (skipScrollRef.current) {
      skipScrollRef.current = false;
      return;
    }
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [chatMessages]);

  useEffect(() => {
    return () => {
      closeWebSocket(webSocketRef.current);
    };
  }, []);

  useEffect(() => {
    providerRef.current = provider;
    modelRef.current = model;
  }, [provider, model]);

  useEffect(() => {
    const fetchModel = async () => {
      try {
        setIsLoading(true);
        const response = await fetch('/api/models/config');
        if (!response.ok) {
          throw new Error(`Error fetching model configurations: ${response.status}`);
        }
        const data = await response.json();
        if (providerRef.current === '' || modelRef.current === '') {
          setSelectedProvider(data.defaultProvider);
          const selectedProvider = data.providers.find((p: Provider) => p.id === data.defaultProvider);
          if (selectedProvider && selectedProvider.models.length > 0) {
            setSelectedModel(selectedProvider.models[0].id);
          }
        } else {
          setSelectedProvider(providerRef.current);
          setSelectedModel(modelRef.current);
        }
      } catch (err) {
        console.error('Failed to fetch model configurations:', err);
      } finally {
        setIsLoading(false);
      }
    };
    if (provider === '' || model === '') {
      fetchModel();
    }
  }, [provider, model]);

  const loadConversations = useCallback(async () => {
    try {
      const data = await conversationApi.getConversations(repoInfo.owner, repoInfo.repo);
      setConversations(data);
    } catch (err) {
      console.error('Failed to load conversations:', err);
    }
  }, [repoInfo.owner, repoInfo.repo]);

  useEffect(() => {
    loadConversations();
  }, [loadConversations]);

  const parsePages = useCallback((content: string): ChatPage[] => {
    const pages: ChatPage[] = [];
    const regex = /@@PAGE\|(.+?)\|(.+?)@@/g;
    let lastIndex = 0;
    let match: RegExpExecArray | null;
    while ((match = regex.exec(content)) !== null) {
      if (lastIndex > 0) {
        const pageContent = content.slice(lastIndex, match.index).trim();
        if (pages.length > 0) {
          pages[pages.length - 1].content = pageContent;
        }
      }
      pages.push({
        type: match[1] as 'plan' | 'update' | 'conclusion',
        title: match[2],
        content: '',
      });
      lastIndex = match.index + match[0].length;
    }
    if (lastIndex > 0 && pages.length > 0) {
      const pageContent = content.slice(lastIndex).trim();
      pages[pages.length - 1].content = pageContent;
    }
    return pages;
  }, []);

  const getDisplayContent = useCallback((msg: ChatMessageItem): string => {
    if (!msg.hasDeepResearch || !msg.pages || msg.pages.length === 0) {
      return msg.content;
    }
    const idx = msg.currentPage ?? 0;
    const page = msg.pages[idx];
    return page?.content || '';
  }, []);

  const loadMessages = useCallback(async (conversationId: string) => {
    try {
      const data = await conversationApi.getConversationMessages(conversationId);
      const items: ChatMessageItem[] = data.map((msg: ConversationMessage) => {
        const hasDR = msg.messageType === 'deep_research';
        const pages = hasDR ? parsePages(msg.content) : undefined;
        return {
          id: msg.id,
          role: msg.role,
          content: msg.content,
          createdAt: msg.createdAt,
          feedbackStatus: msg.feedbackStatus,
          hasDeepResearch: hasDR,
          pages,
          currentPage: pages ? pages.length - 1 : undefined,
        };
      });
      setChatMessages(items);
    } catch (err) {
      console.error('Failed to load messages:', err);
      setChatMessages([]);
    }
  }, [parsePages]);

  const handleSelectConversation = useCallback(async (conversationId: string) => {
    if (isLoading) return;
    if (conversationId === currentConversationId) return;
    setCurrentConversationId(conversationId);
    await loadMessages(conversationId);
  }, [currentConversationId, loadMessages, isLoading]);

  const handleNewConversation = useCallback(() => {
    if (isLoading) return;
    setCurrentConversationId(null);
    setChatMessages([]);
    setQuestion('');
    if (inputRef.current) {
      inputRef.current.focus();
    }
  }, []);

  const handleDeleteConversation = useCallback(async (conversationId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await conversationApi.deleteConversation(conversationId);
    } catch (err) {
      console.error('Failed to delete conversation:', err);
    }
    setConversations(prev => prev.filter(c => c.id !== conversationId));
    if (currentConversationId === conversationId) {
      const remaining = conversations.filter(c => c.id !== conversationId);
      if (remaining.length > 0) {
        setCurrentConversationId(remaining[0].id);
        loadMessages(remaining[0].id);
      } else {
        setCurrentConversationId(null);
        setChatMessages([]);
      }
    }
  }, [currentConversationId, conversations, loadMessages]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!question.trim() || isLoading) return;
    await handleSendMessage();
  };

  const handleSendMessage = async () => {
    const userContent = question.trim();
    if (!userContent || isLoading) return;

    let activeConversationId = currentConversationId;

    if (!activeConversationId) {
      try {
        const req: CreateConversationRequest = {
          repoOwner: repoInfo.owner,
          repoName: repoInfo.repo,
          repoType: repoInfo.type,
          title: makeConversationTitle(userContent),
        };
        const newConv = await conversationApi.createConversation(req);
        activeConversationId = newConv.id;
        setConversations(prev => [newConv, ...prev]);
        setCurrentConversationId(newConv.id);
      } catch (err) {
        console.error('Failed to create conversation:', err);
        activeConversationId = `temp-${Date.now()}`;
        const tempConv: Conversation = {
          id: activeConversationId,
          userId: '',
          repoOwner: repoInfo.owner,
          repoName: repoInfo.repo,
          repoType: repoInfo.type,
          title: makeConversationTitle(userContent),
          createdAt: new Date().toISOString(),
          updatedAt: new Date().toISOString(),
        };
        setConversations(prev => [tempConv, ...prev]);
        setCurrentConversationId(activeConversationId);
      }
    }

    const userMessage: ChatMessageItem = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: userContent,
      createdAt: new Date().toISOString(),
    };

    const assistantMsgId = `assistant-${Date.now()}`;
    const newAssistantMsg: ChatMessageItem = {
      id: assistantMsgId,
      role: 'assistant' as const,
      content: '',
      createdAt: new Date().toISOString(),
      isStreaming: true,
      ...(deepResearch ? { hasDeepResearch: true, pages: [], currentPage: 0 } : {}),
    };

    setChatMessages(prev => [...prev, userMessage, newAssistantMsg]);
    setQuestion('');
    setIsLoading(true);

    try {
      const savedUserMsg = await conversationApi.createMessage(activeConversationId, {
        role: 'user',
        content: userContent,
      });
      setChatMessages(prev =>
        prev.map(msg =>
          msg.id === userMessage.id
            ? { ...msg, id: savedUserMsg.id }
            : msg
        )
      );
    } catch (err) {
      console.error('Failed to save user message:', err);
    }

    const wsMessages = [...chatMessages, userMessage].map(msg => ({
      role: msg.role as 'user' | 'assistant',
      content: msg.content,
    }));

    const requestBody: ChatCompletionRequest = {
      repo_url: getRepoUrl(repoInfo),
      type: repoInfo.type,
      messages: wsMessages,
      provider: selectedProvider,
      model: isCustomSelectedModel ? customSelectedModel : selectedModel,
      language: language,
    };

    if (repoInfo?.token) {
      requestBody.token = repoInfo.token;
    }

    closeWebSocket(webSocketRef.current);

    let fullResponse = '';
    let currentPageContent = '';
    const pageMarkerRe = /^@@PAGE\|(.+?)\|(.+?)@@$/;

    const handleMessage = (message: string) => {
      const markerMatch = message.match(pageMarkerRe);
      if (markerMatch) {
        fullResponse += message;
        const prevPageContent = currentPageContent;
        currentPageContent = '';
        setChatMessages(prev =>
          prev.map(msg => {
            if (msg.id !== assistantMsgId) return msg;
            const pages = [...(msg.pages || [])];
            if (pages.length > 0) {
              pages[pages.length - 1] = { ...pages[pages.length - 1], content: prevPageContent };
            }
            pages.push({
              type: markerMatch[1] as 'plan' | 'update' | 'conclusion',
              title: markerMatch[2],
              content: '',
            });
            return {
              ...msg,
              hasDeepResearch: true,
              pages,
              content: fullResponse,
            };
          })
        );
        return;
      }
      fullResponse += message;
      currentPageContent += message;
      setChatMessages(prev =>
        prev.map(msg => {
          if (msg.id !== assistantMsgId) return msg;
          const pages = msg.pages ? [...msg.pages] : undefined;
          if (pages && pages.length > 0) {
            const lastIdx = pages.length - 1;
            pages[lastIdx] = { ...pages[lastIdx], content: currentPageContent };
          }
          return { ...msg, content: fullResponse, pages, currentPage: pages ? pages.length - 1 : undefined };
        })
      );
    };

    const handleError = (error: Event) => {
      console.error('WebSocket error:', error);
      fallbackToHttp(requestBody, assistantMsgId);
    };

    const handleClose = () => {
      setChatMessages(prev =>
        prev.map(msg => {
          if (msg.id !== assistantMsgId) return msg;
          const pages = [...(msg.pages || [])];
          if (pages.length > 0 && currentPageContent) {
            pages[pages.length - 1] = { ...pages[pages.length - 1], content: currentPageContent };
          }
          return {
            ...msg,
            isStreaming: false,
            pages,
            currentPage: pages.length > 0 ? pages.length - 1 : undefined,
          };
        })
      );
      setIsLoading(false);

      if (activeConversationId && fullResponse) {
        conversationApi
          .createMessage(activeConversationId, {
            role: 'assistant',
            content: fullResponse,
            ...(deepResearch ? { messageType: 'deep_research' as const } : {}),
          })
          .then((savedAssistantMsg) => {
            setChatMessages(prev =>
              prev.map(msg =>
                msg.id === assistantMsgId
                  ? { ...msg, id: savedAssistantMsg.id, feedbackStatus: savedAssistantMsg.feedbackStatus }
                  : msg
              )
            );
          })
          .catch(err => console.error('Failed to save assistant message:', err));

        setConversations(prev =>
          prev.map(c =>
            c.id === activeConversationId
              ? { ...c, updatedAt: new Date().toISOString() }
              : c
          )
        );
      }
    };

    if (deepResearch) {
      webSocketRef.current = createDeepResearchWebSocket(
        requestBody, handleMessage, handleError, handleClose,
      );
    } else {
      webSocketRef.current = createChatWebSocket(
        requestBody, handleMessage, handleError, handleClose,
      );
    }
  };

  const fallbackToHttp = async (requestBody: ChatCompletionRequest, assistantId: string) => {
    try {
      const apiResponse = await fetch(`/api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      if (!apiResponse.ok) {
        throw new Error(`API error: ${apiResponse.status}`);
      }

      const reader = apiResponse.body?.getReader();
      const decoder = new TextDecoder();

      if (!reader) {
        throw new Error('Failed to get response reader');
      }

      let fullResponse = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        const chunk = decoder.decode(value, { stream: true });
        fullResponse += chunk;
        setChatMessages(prev =>
          prev.map(msg =>
            msg.id === assistantId
              ? { ...msg, content: fullResponse }
              : msg
          )
        );
      }

      setChatMessages(prev =>
        prev.map(msg =>
          msg.id === assistantId
            ? { ...msg, isStreaming: false }
            : msg
        )
      );

      if (currentConversationId && fullResponse) {
        conversationApi
          .createMessage(currentConversationId, {
            role: 'assistant',
            content: fullResponse,
            ...(deepResearch ? { messageType: 'deep_research' as const } : {}),
          })
          .then((savedAssistantMsg) => {
            setChatMessages(prev =>
              prev.map(msg =>
                msg.id === assistantId
                  ? { ...msg, id: savedAssistantMsg.id, feedbackStatus: savedAssistantMsg.feedbackStatus }
                  : msg
              )
            );
          })
          .catch(err => console.error('Failed to save assistant message:', err));
      }
    } catch (error) {
      console.error('Error during HTTP fallback:', error);
      setChatMessages(prev =>
        prev.map(msg =>
          msg.id === assistantId
            ? { ...msg, content: msg.content + '\n\nError: Failed to get a response. Please try again.', isStreaming: false }
            : msg
        )
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteMessage = async (messageId: string) => {
    setChatMessages(prev => prev.filter(msg => msg.id !== messageId));
    if (currentConversationId) {
      try {
        await conversationApi.deleteMessage(currentConversationId, messageId);
      } catch (err) {
        console.error('Failed to delete message:', err);
      }
    }
  };

  const handleLike = useCallback(async (messageId: string) => {
    if (!currentConversationId) return;
    const msg = chatMessages.find(m => m.id === messageId);
    if (!msg || msg.feedbackStatus) return;

    setChatMessages(prev =>
      prev.map(m => m.id === messageId ? { ...m, feedbackStatus: 'liked' } : m)
    );

    try {
      await conversationApi.submitFeedback(currentConversationId, messageId, {
        feedbackType: 'liked',
      });
    } catch (err) {
      console.error('Failed to submit like feedback:', err);
      setChatMessages(prev =>
        prev.map(m => m.id === messageId ? { ...m, feedbackStatus: undefined } : m)
      );
    }
  }, [currentConversationId, chatMessages]);

  const handleDislikeClick = useCallback((messageId: string) => {
    const msg = chatMessages.find(m => m.id === messageId);
    if (!msg || msg.feedbackStatus) return;
    setFeedbackTargetMsgId(messageId);
    setFeedbackComment('');
    setFeedbackModalOpen(true);
  }, [chatMessages]);

  const handleSubmitDislikeFeedback = useCallback(async () => {
    const messageId = feedbackTargetMsgId;
    if (!currentConversationId || !messageId) return;

    setFeedbackSubmitting(true);

    setChatMessages(prev =>
      prev.map(m => m.id === messageId ? { ...m, feedbackStatus: 'disliked' } : m)
    );

    try {
      await conversationApi.submitFeedback(currentConversationId, messageId, {
        feedbackType: 'disliked',
        comment: feedbackComment.trim() || undefined,
      });
    } catch (err) {
      console.error('Failed to submit dislike feedback:', err);
      setChatMessages(prev =>
        prev.map(m => m.id === messageId ? { ...m, feedbackStatus: undefined } : m)
      );
    } finally {
      setFeedbackSubmitting(false);
      setFeedbackModalOpen(false);
      setFeedbackTargetMsgId(null);
      setFeedbackComment('');
    }
  }, [currentConversationId, feedbackTargetMsgId, feedbackComment]);

  const handleCloseFeedbackModal = useCallback(() => {
    setFeedbackModalOpen(false);
    setFeedbackTargetMsgId(null);
    setFeedbackComment('');
  }, []);

  const formatTime = (dateStr: string) => {
    try {
      const date = new Date(dateStr);
      const now = new Date();
      const isToday = date.toDateString() === now.toDateString();
      if (isToday) {
        return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
      }
      return date.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
      return '';
    }
  };

  const makeConversationTitle = useCallback((text: string, maxLen: number = 50): string => {
    const trimmed = text.trim();
    if (trimmed.length <= maxLen) return trimmed;
    const sliced = trimmed.slice(0, maxLen);
    const lastPunct = Math.max(
      sliced.lastIndexOf('。'),
      sliced.lastIndexOf('，'),
      sliced.lastIndexOf('？'),
      sliced.lastIndexOf('?'),
      sliced.lastIndexOf('！'),
      sliced.lastIndexOf('!'),
      sliced.lastIndexOf(' '),
      sliced.lastIndexOf('\n'),
    );
    if (lastPunct > maxLen * 0.5) {
      return sliced.slice(0, lastPunct) + '...';
    }
    return sliced + '...';
  }, []);

  const currentConversation = conversations.find(c => c.id === currentConversationId);

  return (
    <div className="flex h-full bg-[var(--card-bg)] rounded-lg overflow-hidden">
      {/* Left Sidebar */}
      <div
        className={`flex flex-col bg-[var(--background)]/50 border-r border-[var(--border-color)] transition-all duration-300 ${
          sidebarCollapsed ? 'w-0 min-w-0 overflow-hidden' : 'w-64 min-w-[256px]'
        }`}
      >
        {/* Sidebar Header */}
        <div className="p-3 border-b border-[var(--border-color)]">
          <button
            onClick={handleNewConversation}
            disabled={isLoading}
            className={`w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-lg border border-[var(--border-color)] text-[var(--foreground)] transition-colors text-sm ${
              isLoading
                ? 'opacity-40 cursor-not-allowed'
                : 'bg-[var(--card-bg)] hover:bg-[var(--accent-primary)]/10 hover:border-[var(--accent-primary)]/30'
            }`}
          >
            <FaPlus className="text-xs" />
            <span>{messages.ask?.newChat || '新对话'}</span>
          </button>
        </div>

        {/* Conversation List */}
        <div className="flex-1 overflow-y-auto p-2">
          {conversations.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-[var(--muted)] text-xs p-4">
              <FaComments className="text-2xl mb-2 opacity-50" />
              <span>{messages.ask?.noConversations || '暂无对话记录'}</span>
            </div>
          ) : (
            <div className="space-y-1">
              {conversations.map(conv => (
                <div
                  key={conv.id}
                  onClick={() => handleSelectConversation(conv.id)}
                  className={`group flex items-center gap-2 px-3 py-2.5 rounded-lg transition-colors text-sm ${
                    isLoading
                      ? 'cursor-not-allowed opacity-50'
                      : 'cursor-pointer'
                  } ${
                    currentConversationId === conv.id
                      ? 'bg-[var(--accent-primary)]/10 text-[var(--accent-primary)] border border-[var(--accent-primary)]/20'
                      : 'hover:bg-[var(--background)]/80 text-[var(--foreground)]/80 border border-transparent'
                  }`}
                >
                  <FaComments className="text-xs flex-shrink-0 opacity-60" />
                  <div className="flex-1 min-w-0">
                    <div className="truncate text-sm">
                      {conv.title || (messages.ask?.untitled || '未命名对话')}
                    </div>
                    <div className="text-xs text-[var(--muted)] mt-0.5">
                      {formatTime(conv.updatedAt || conv.createdAt)}
                    </div>
                  </div>
                  <button
                    onClick={(e) => handleDeleteConversation(conv.id, e)}
                    disabled={isLoading}
                    className="opacity-0 group-hover:opacity-100 p-1 rounded hover:bg-red-500/10 hover:text-red-500 transition-all flex-shrink-0 disabled:hidden"
                    title={messages.ask?.deleteConversation || '删除对话'}
                  >
                    <FaTrash className="text-xs" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Sidebar Footer - Model Info */}
        <div className="p-3 border-t border-[var(--border-color)]">
          <button
            type="button"
            onClick={() => setIsModelSelectionModalOpen(true)}
            className="w-full text-xs px-2.5 py-1.5 rounded border border-[var(--border-color)]/40 bg-[var(--background)]/10 text-[var(--foreground)]/80 hover:bg-[var(--background)]/30 hover:text-[var(--foreground)] transition-colors flex items-center gap-1.5 truncate"
          >
            <span className="truncate">{selectedProvider}/{isCustomSelectedModel ? customSelectedModel : selectedModel}</span>
            <svg className="h-3.5 w-3.5 text-[var(--accent-primary)]/70 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
            </svg>
          </button>
        </div>
      </div>

      {/* Right Content Area */}
      <div className="flex-1 flex flex-col min-w-0 relative">
        {/* Chat Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--border-color)] bg-[var(--card-bg)]">
          <div className="flex items-center gap-2 min-w-0">
            <button
              onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
              className="p-1.5 rounded-md hover:bg-[var(--background)]/80 transition-colors text-[var(--muted)] hover:text-[var(--foreground)]"
              title={sidebarCollapsed ? (messages.ask?.expandSidebar || '展开侧栏') : (messages.ask?.collapseSidebar || '收起侧栏')}
            >
              {sidebarCollapsed ? <FaChevronRight size={12} /> : <FaChevronLeft size={12} />}
            </button>
            <FaRobot className="text-[var(--accent-primary)] flex-shrink-0" />
            <span className="text-sm font-medium text-[var(--foreground)] truncate">
              {currentConversation?.title || messages.ask?.title || '代码问答'}
            </span>
          </div>
          {currentConversationId && (
            <button
              onClick={clearConversation}
              className="text-xs text-[var(--muted)] hover:text-red-500 px-2 py-1 rounded transition-colors"
            >
              <FaTimes size={12} />
            </button>
          )}
        </div>

        {/* Messages Area */}
        <div className="flex-1 overflow-y-auto px-4 py-4">
          {chatMessages.length === 0 ? (
            <div className="flex flex-col items-center justify-center h-full text-[var(--muted)]">
              <div className="relative mb-4">
                <div className="absolute -inset-2 bg-[var(--accent-primary)]/5 rounded-full blur-md" />
                <FaRobot className="text-5xl relative z-10 opacity-30" />
              </div>
              <p className="text-base font-medium mb-2">
                {messages.ask?.welcomeTitle || '欢迎使用代码问答'}
              </p>
              <p className="text-sm text-center max-w-md">
                {messages.ask?.welcomeSubtitle || '输入您的问题，AI 将基于代码仓库为您解答'}
              </p>
            </div>
          ) : (
            <div className="max-w-3xl mx-auto space-y-4">
              {chatMessages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex gap-3 ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
                >
                  {msg.role === 'assistant' && (
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[var(--accent-primary)]/10 flex items-center justify-center mt-1">
                      <FaRobot className="text-sm text-[var(--accent-primary)]" />
                    </div>
                  )}
                  <div
                    className={`group relative max-w-[80%] rounded-2xl px-4 py-3 ${
                      msg.role === 'user'
                        ? 'bg-[var(--accent-primary)] text-white rounded-br-md'
                        : 'bg-[var(--background)]/80 border border-[var(--border-color)] text-[var(--foreground)] rounded-bl-md'
                    }`}
                  >
                    {msg.role === 'assistant' ? (
                      <div className="text-sm">
                        {msg.isStreaming && !getDisplayContent(msg) ? (
                          <div className="flex items-center space-x-1.5 py-1">
                            <div className="w-2 h-2 bg-[var(--accent-primary)]/60 rounded-full animate-pulse" />
                            <div className="w-2 h-2 bg-[var(--accent-primary)]/60 rounded-full animate-pulse delay-75" />
                            <div className="w-2 h-2 bg-[var(--accent-primary)]/60 rounded-full animate-pulse delay-150" />
                          </div>
                        ) : (
                          <>
                            {msg.hasDeepResearch && msg.pages && msg.pages.length > 1 && (
                              <div className="flex items-center justify-between mb-2 pb-2 border-b border-[var(--border-color)]/30">
                                <button
                                  onClick={() => {
                                    skipScrollRef.current = true;
                                    setChatMessages(prev =>
                                      prev.map(m =>
                                        m.id === msg.id
                                          ? { ...m, currentPage: Math.max(0, (m.currentPage ?? 0) - 1) }
                                          : m
                                      )
                                    );
                                  }}
                                  disabled={(msg.currentPage ?? 0) <= 0}
                                  className="text-xs px-2 py-0.5 rounded border border-[var(--border-color)] text-[var(--muted)] hover:text-[var(--foreground)] hover:border-[var(--foreground)]/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                                >
                                  ← 上一页
                                </button>
                                <span className="text-xs text-[var(--muted)]">
                                  {msg.pages[(msg.currentPage ?? msg.pages.length - 1)]?.title || ''}
                                  &nbsp;({(msg.currentPage ?? msg.pages.length - 1) + 1}/{msg.pages.length})
                                </span>
                                <button
                                  onClick={() => {
                                    skipScrollRef.current = true;
                                    setChatMessages(prev =>
                                      prev.map(m =>
                                        m.id === msg.id
                                          ? { ...m, currentPage: Math.min((msg.pages?.length ?? 1) - 1, (m.currentPage ?? 0) + 1) }
                                          : m
                                      )
                                    );
                                  }}
                                  disabled={(msg.currentPage ?? 0) >= (msg.pages?.length ?? 1) - 1}
                                  className="text-xs px-2 py-0.5 rounded border border-[var(--border-color)] text-[var(--muted)] hover:text-[var(--foreground)] hover:border-[var(--foreground)]/20 transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
                                >
                                  下一页 →
                                </button>
                              </div>
                            )}
                            <Markdown content={getDisplayContent(msg)} />
                            {/* Feedback buttons */}
                            {!msg.isStreaming && msg.content && (
                              <div className="flex items-center gap-1 mt-2 pt-1.5 border-t border-[var(--border-color)]/30">
                                {msg.feedbackStatus ? (
                                  <span className="text-xs text-[var(--muted)] flex items-center gap-1">
                                    {msg.feedbackStatus === 'liked' ? (
                                      <>
                                        <FaThumbsUp className="text-[var(--accent-primary)]" size={11} />
                                        <span className="text-[var(--accent-primary)]">已点赞</span>
                                      </>
                                    ) : (
                                      <>
                                        <FaThumbsDown className="text-red-500" size={11} />
                                        <span className="text-red-500">已反馈</span>
                                      </>
                                    )}
                                  </span>
                                ) : (
                                  <>
                                    <button
                                      onClick={() => handleLike(msg.id)}
                                      className="p-1 rounded hover:bg-[var(--accent-primary)]/10 text-[var(--muted)] hover:text-[var(--accent-primary)] transition-colors"
                                      title="点赞"
                                    >
                                      <FaThumbsUp size={12} />
                                    </button>
                                    <button
                                      onClick={() => handleDislikeClick(msg.id)}
                                      className="p-1 rounded hover:bg-red-500/10 text-[var(--muted)] hover:text-red-500 transition-colors"
                                      title="点踩"
                                    >
                                      <FaThumbsDown size={12} />
                                    </button>
                                  </>
                                )}
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    ) : (
                      <div className="text-sm whitespace-pre-wrap break-words">{msg.content}</div>
                    )}
                    {/* Delete message button */}
                    <button
                      onClick={() => handleDeleteMessage(msg.id)}
                      className="absolute -top-1 -right-1 opacity-0 group-hover:opacity-100 w-5 h-5 rounded-full bg-[var(--card-bg)] border border-[var(--border-color)] flex items-center justify-center text-[var(--muted)] hover:text-red-500 hover:border-red-500/30 transition-all"
                      title={messages.ask?.deleteMessage || '删除消息'}
                    >
                      <FaTimes size={8} />
                    </button>
                  </div>
                  {msg.role === 'user' && (
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-[var(--accent-primary)] flex items-center justify-center mt-1">
                      <FaUser className="text-sm text-white" />
                    </div>
                  )}
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input Area - Fixed at Bottom */}
        <div className="border-t border-[var(--border-color)] bg-[var(--card-bg)] p-4">
          <form onSubmit={handleSubmit} className="max-w-3xl mx-auto">
            <div className="flex items-center justify-end mb-2">
              <label className="flex items-center cursor-pointer">
                <span className="text-xs text-[var(--muted)] mr-2">
                  {messages.ask?.deepResearch || '深度研究'}
                </span>
                <div className="relative">
                  <input
                    type="checkbox"
                    checked={deepResearch}
                    onChange={() => setDeepResearch(!deepResearch)}
                    className="sr-only"
                  />
                  <div className={`w-9 h-5 rounded-full transition-colors ${deepResearch ? 'bg-blue-600' : 'bg-gray-300 dark:bg-gray-600'}`} />
                  <div className={`absolute left-0.5 top-0.5 w-4 h-4 rounded-full bg-white transition-transform transform ${deepResearch ? 'translate-x-4' : ''}`} />
                </div>
              </label>
            </div>
            <div className="relative flex items-end gap-2">
              <div className="flex-1 relative">
                <input
                  ref={inputRef}
                  type="text"
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  placeholder={messages.ask?.placeholder || '输入您的问题...'}
                  className="w-full rounded-xl border border-[var(--border-color)] bg-[var(--input-bg)] text-[var(--foreground)] px-4 py-3 text-sm shadow-sm focus:border-[var(--accent-primary)] focus:ring-2 focus:ring-[var(--accent-primary)]/30 focus:outline-none transition-all pr-12"
                  disabled={isLoading}
                />
                <button
                  type="submit"
                  disabled={isLoading || !question.trim()}
                  className={`absolute right-2 top-1/2 -translate-y-1/2 p-2 rounded-lg transition-all ${
                    isLoading || !question.trim()
                      ? 'text-[var(--muted)] cursor-not-allowed'
                      : 'text-[var(--accent-primary)] hover:bg-[var(--accent-primary)]/10'
                  }`}
                >
                  {isLoading ? (
                    <div className="w-4 h-4 rounded-full border-2 border-t-transparent border-[var(--accent-primary)] animate-spin" />
                  ) : (
                    <FaPaperPlane className="text-sm" />
                  )}
                </button>
              </div>
            </div>
          </form>
        </div>
      </div>

      {/* Model Selection Modal */}
      <ModelSelectionModal
        isOpen={isModelSelectionModalOpen}
        onClose={() => setIsModelSelectionModalOpen(false)}
        provider={selectedProvider}
        setProvider={setSelectedProvider}
        model={selectedModel}
        setModel={setSelectedModel}
        isCustomModel={isCustomSelectedModel}
        setIsCustomModel={setIsCustomSelectedModel}
        customModel={customSelectedModel}
        setCustomModel={setCustomSelectedModel}
        isComprehensiveView={isComprehensiveView}
        setIsComprehensiveView={setIsComprehensiveView}
        showFileFilters={false}
        onApply={() => {
          console.log('Model selection applied:', selectedProvider, selectedModel);
        }}
        showWikiType={false}
        authRequired={false}
        isAuthLoading={false}
      />

      {/* Feedback Modal */}
      {feedbackModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-[60]">
          <div className="bg-[var(--card-bg)] rounded-xl shadow-xl w-full max-w-md p-6 mx-4 border border-[var(--border-color)]">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-base font-semibold text-[var(--foreground)]">
                帮助改进回答
              </h3>
              <button
                onClick={handleCloseFeedbackModal}
                className="p-1 rounded hover:bg-[var(--background)]/80 text-[var(--muted)] hover:text-[var(--foreground)] transition-colors"
              >
                <FaTimes size={14} />
              </button>
            </div>

            <p className="text-sm text-[var(--muted)] mb-4">
              请告诉我们这个回答存在哪些问题，我们将根据您的反馈进行改进。
            </p>

            <textarea
              value={feedbackComment}
              onChange={(e) => setFeedbackComment(e.target.value)}
              placeholder="请描述具体问题（可选）..."
              rows={4}
              className="w-full rounded-lg border border-[var(--border-color)] bg-[var(--input-bg)] text-[var(--foreground)] px-3 py-2.5 text-sm shadow-sm focus:border-[var(--accent-primary)] focus:ring-2 focus:ring-[var(--accent-primary)]/30 focus:outline-none transition-all resize-none placeholder:text-[var(--muted)]/60"
              autoFocus
            />

            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={handleCloseFeedbackModal}
                className="px-4 py-2 text-sm rounded-lg border border-[var(--border-color)] text-[var(--foreground)] hover:bg-[var(--background)]/80 transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleSubmitDislikeFeedback}
                disabled={feedbackSubmitting}
                className="px-4 py-2 text-sm rounded-lg bg-red-500 text-white hover:bg-red-600 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-1.5"
              >
                {feedbackSubmitting ? (
                  <div className="w-3.5 h-3.5 rounded-full border-2 border-t-transparent border-white animate-spin" />
                ) : (
                  <FaThumbsDown size={12} />
                )}
                提交反馈
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Ask;

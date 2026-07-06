/**
 * NEXUS AI TRADING SYSTEM - Chat Support Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page provides comprehensive chat support including:
 * - Real-time messaging with AI assistant
 * - Support ticket management
 * - Chat history and search
 * - File attachments and sharing
 * - User presence indicators
 * - Typing indicators
 * - Message reactions
 * - Threaded conversations
 * - Knowledge base integration
 * - WebSocket real-time communication
 */

'use client';

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useAuth } from '@/hooks/useAuth';
import { useApi } from '@/hooks/useApi';

// Components
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { Toast } from '@/components/ui/Toast';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Modal } from '@/components/ui/Modal';
import { Avatar } from '@/components/ui/Avatar';
import { Progress } from '@/components/ui/Progress';
import { Textarea } from '@/components/ui/Textarea';
import { Switch } from '@/components/ui/Switch';

// Types
import type {
  ChatMessage,
  ChatRoom,
  ChatUser,
  ChatThread,
  ChatAttachment,
  ChatReaction,
  ChatTyping,
  ChatPresence,
  ChatHistory,
  SupportTicket,
  KnowledgeArticle,
  ChatSettings,
} from '@/types/chat';

// Constants
import {
  CHAT_ROOMS,
  CHAT_MESSAGE_TYPES,
  CHAT_USER_ROLES,
  CHAT_STATUSES,
  SUPPORT_CATEGORIES,
  KNOWLEDGE_TOPICS,
} from '@/constants/chat';

// Hooks
import { useChat } from '@/hooks/useChat';
import { useSupport } from '@/hooks/useSupport';

// Utils
import { formatTime, formatDate, formatDuration } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

export default function ChatPage() {
  // Authentication
  const { user, isAuthenticated, accessToken } = useAuth();
  
  // API client
  const api = useApi();
  
  // Refs
  const wsCleanupRef = useRef<(() => void) | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const chatContainerRef = useRef<HTMLDivElement>(null);
  const typingTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  
  // State - Messages
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [currentMessage, setCurrentMessage] = useState<string>('');
  const [selectedRoom, setSelectedRoom] = useState<ChatRoom | null>(null);
  const [rooms, setRooms] = useState<ChatRoom[]>(CHAT_ROOMS);
  const [messagesLoading, setMessagesLoading] = useState<boolean>(true);
  const [sendingMessage, setSendingMessage] = useState<boolean>(false);
  const [editingMessage, setEditingMessage] = useState<ChatMessage | null>(null);
  
  // State - Users
  const [users, setUsers] = useState<ChatUser[]>([]);
  const [typingUsers, setTypingUsers] = useState<ChatTyping[]>([]);
  const [presence, setPresence] = useState<ChatPresence[]>([]);
  
  // State - Threads
  const [threads, setThreads] = useState<ChatThread[]>([]);
  const [activeThread, setActiveThread] = useState<ChatThread | null>(null);
  const [threadMessages, setThreadMessages] = useState<ChatMessage[]>([]);
  
  // State - Attachments
  const [attachments, setAttachments] = useState<ChatAttachment[]>([]);
  const [uploadProgress, setUploadProgress] = useState<number>(0);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  
  // State - Reactions
  const [reactions, setReactions] = useState<ChatReaction[]>([]);
  const [showReactionPicker, setShowReactionPicker] = useState<string | null>(null);
  
  // State - Support
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [currentTicket, setCurrentTicket] = useState<SupportTicket | null>(null);
  const [ticketMessages, setTicketMessages] = useState<ChatMessage[]>([]);
  const [showTicketModal, setShowTicketModal] = useState<boolean>(false);
  const [newTicket, setNewTicket] = useState<Partial<SupportTicket>>({
    subject: '',
    category: 'general',
    priority: 'medium',
    description: '',
  });
  const [ticketsLoading, setTicketsLoading] = useState<boolean>(true);
  
  // State - Knowledge
  const [knowledgeArticles, setKnowledgeArticles] = useState<KnowledgeArticle[]>([]);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [searchResults, setSearchResults] = useState<KnowledgeArticle[]>([]);
  const [selectedArticle, setSelectedArticle] = useState<KnowledgeArticle | null>(null);
  const [showArticleModal, setShowArticleModal] = useState<boolean>(false);
  
  // State - Settings
  const [settings, setSettings] = useState<ChatSettings>({
    notifications: true,
    sound: true,
    autoScroll: true,
    showTimestamps: true,
    showAvatars: true,
    messageFormatting: 'markdown',
    theme: 'dark',
    fontSize: 'medium',
    language: 'en',
  });
  
  // State - UI
  const [activeTab, setActiveTab] = useState<string>('chat');
  const [searchQueryGlobal, setSearchQueryGlobal] = useState<string>('');
  const [showToast, setShowToast] = useState<{ message: string; type: 'success' | 'error' | 'info' | 'warning' } | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isTyping, setIsTyping] = useState<boolean>(false);
  const [showEmojiPicker, setShowEmojiPicker] = useState<boolean>(false);
  const [selectedMessages, setSelectedMessages] = useState<string[]>([]);
  const [isBulkDeleting, setIsBulkDeleting] = useState<boolean>(false);

  // ============================================
  // WebSocket Connection
  // ============================================
  const { 
    isConnected, 
    sendMessage, 
    subscribe: wsSubscribe,
    unsubscribe: wsUnsubscribe,
    messages: wsMessages,
  } = useWebSocket({
    url: `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8004'}/chat`,
    autoConnect: true,
    onOpen: handleWebSocketOpen,
    onMessage: handleWebSocketMessage,
    onError: handleWebSocketError,
    onClose: handleWebSocketClose,
    reconnectAttempts: 10,
    reconnectInterval: 3000,
    authToken: accessToken || undefined,
  });

  function handleWebSocketOpen() {
    console.log('✅ Chat WebSocket connected');
    subscribeToChannels();
  }

  function handleWebSocketMessage(event: MessageEvent) {
    try {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'message':
          handleNewMessage(data.payload);
          break;
        case 'message_edited':
          handleMessageEdited(data.payload);
          break;
        case 'message_deleted':
          handleMessageDeleted(data.payload);
          break;
        case 'typing':
          handleTypingUpdate(data.payload);
          break;
        case 'presence':
          handlePresenceUpdate(data.payload);
          break;
        case 'reaction':
          handleReactionUpdate(data.payload);
          break;
        case 'thread':
          handleThreadUpdate(data.payload);
          break;
        case 'ticket_update':
          handleTicketUpdate(data.payload);
          break;
        case 'knowledge_update':
          handleKnowledgeUpdate(data.payload);
          break;
        case 'error':
          handleChatError(data.payload);
          break;
        default:
          console.debug('Unhandled WebSocket message type:', data.type);
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }

  function handleWebSocketError(error: Event) {
    console.error('WebSocket error:', error);
  }

  function handleWebSocketClose() {
    console.log('Chat WebSocket disconnected');
  }

  function subscribeToChannels() {
    if (!isConnected) return;

    wsSubscribe({
      channel: 'chat_messages',
      roomId: selectedRoom?.id,
    });

    wsSubscribe({
      channel: 'chat_presence',
    });

    wsSubscribe({
      channel: 'chat_typing',
    });

    wsSubscribe({
      channel: 'chat_reactions',
    });

    wsSubscribe({
      channel: 'chat_threads',
    });

    wsSubscribe({
      channel: 'support_tickets',
    });

    wsSubscribe({
      channel: 'knowledge_base',
    });
  }

  // ============================================
  // WebSocket Data Handlers
  // ============================================
  function handleNewMessage(data: any) {
    const newMessage: ChatMessage = {
      id: data.id || `msg-${Date.now()}`,
      roomId: data.roomId || selectedRoom?.id || 'general',
      userId: data.userId || '',
      username: data.username || 'Unknown User',
      avatar: data.avatar || '',
      content: data.content || '',
      type: data.type || 'text',
      timestamp: new Date(data.timestamp || Date.now()),
      edited: false,
      editedAt: undefined,
      deleted: false,
      reactions: data.reactions || [],
      replies: data.replies || [],
      attachments: data.attachments || [],
      metadata: data.metadata || {},
    };

    setMessages(prev => [...prev, newMessage]);
    scrollToBottom();

    if (currentTicket && newMessage.roomId === currentTicket.id) {
      setTicketMessages(prev => [...prev, newMessage]);
    }

    if (settings.sound) {
      playNotificationSound();
    }

    if (settings.notifications && 'Notification' in window) {
      showDesktopNotification(newMessage);
    }
  }

  function handleMessageEdited(data: any) {
    setMessages(prev =>
      prev.map(m =>
        m.id === data.id
          ? { ...m, content: data.content, edited: true, editedAt: new Date(data.editedAt || Date.now()) }
          : m
      )
    );
  }

  function handleMessageDeleted(data: any) {
    setMessages(prev => prev.filter(m => m.id !== data.id));
    setThreadMessages(prev => prev.filter(m => m.id !== data.id));
  }

  function handleTypingUpdate(data: any) {
    setTypingUsers(prev => {
      const filtered = prev.filter(t => t.userId !== data.userId);
      if (data.isTyping) {
        return [...filtered, {
          userId: data.userId,
          username: data.username || 'Unknown User',
          roomId: data.roomId,
          timestamp: new Date(data.timestamp || Date.now()),
        }];
      }
      return filtered;
    });
  }

  function handlePresenceUpdate(data: any) {
    setPresence(prev => {
      const filtered = prev.filter(p => p.userId !== data.userId);
      return [...filtered, {
        userId: data.userId,
        username: data.username || 'Unknown User',
        status: data.status || 'online',
        lastSeen: new Date(data.lastSeen || Date.now()),
      }];
    });
  }

  function handleReactionUpdate(data: any) {
    setReactions(prev => {
      const existing = prev.find(r => r.messageId === data.messageId && r.userId === data.userId);
      if (existing) {
        if (data.removed) {
          return prev.filter(r => r.id !== existing.id);
        }
        return prev.map(r =>
          r.id === existing.id
            ? { ...r, emoji: data.emoji, timestamp: new Date(data.timestamp || Date.now()) }
            : r
        );
      }
      return [...prev, {
        id: data.id || `reaction-${Date.now()}`,
        messageId: data.messageId,
        userId: data.userId,
        username: data.username || 'Unknown User',
        emoji: data.emoji || '👍',
        timestamp: new Date(data.timestamp || Date.now()),
      }];
    });

    setMessages(prev =>
      prev.map(m =>
        m.id === data.messageId
          ? {
              ...m,
              reactions: m.reactions?.filter(r => r.userId !== data.userId),
              ...(data.removed ? {} : {
                reactions: [...(m.reactions || []), {
                  id: data.id || `reaction-${Date.now()}`,
                  messageId: data.messageId,
                  userId: data.userId,
                  username: data.username || 'Unknown User',
                  emoji: data.emoji || '👍',
                  timestamp: new Date(data.timestamp || Date.now()),
                }]
              })
            }
          : m
      )
    );
  }

  function handleThreadUpdate(data: any) {
    if (data.type === 'created') {
      setThreads(prev => [{
        id: data.id || `thread-${Date.now()}`,
        messageId: data.messageId || '',
        messages: data.messages || [],
        participants: data.participants || [],
        createdAt: new Date(data.createdAt || Date.now()),
        updatedAt: new Date(data.updatedAt || Date.now()),
      }, ...prev]);
    } else if (data.type === 'updated') {
      setThreads(prev =>
        prev.map(t =>
          t.id === data.id
            ? { ...t, messages: data.messages || t.messages, updatedAt: new Date(data.updatedAt || Date.now()) }
            : t
        )
      );
    }
  }

  function handleTicketUpdate(data: any) {
    setTickets(prev =>
      prev.map(t =>
        t.id === data.id
          ? { ...t, status: data.status || t.status, updatedAt: new Date(data.updatedAt || Date.now()) }
          : t
      )
    );
  }

  function handleKnowledgeUpdate(data: any) {
    if (data.type === 'created') {
      setKnowledgeArticles(prev => [{
        id: data.id || `article-${Date.now()}`,
        title: data.title || 'New Article',
        content: data.content || '',
        category: data.category || 'general',
        tags: data.tags || [],
        author: data.author || 'Unknown',
        createdAt: new Date(data.createdAt || Date.now()),
        updatedAt: new Date(data.updatedAt || Date.now()),
        views: data.views || 0,
        helpful: data.helpful || 0,
      }, ...prev]);
    } else if (data.type === 'updated') {
      setKnowledgeArticles(prev =>
        prev.map(a =>
          a.id === data.id
            ? { ...a, ...data, updatedAt: new Date(data.updatedAt || Date.now()) }
            : a
        )
      );
    }
  }

  function handleChatError(data: any) {
    setShowToast({
      message: data.message || 'Chat service error occurred',
      type: 'error',
    });
  }

  // ============================================
  // Sound and Desktop Notifications
  // ============================================
  function playNotificationSound() {
    try {
      const audio = new Audio('/sounds/notification.mp3');
      audio.volume = 0.5;
      audio.play().catch(() => {});
    } catch (error) {
      console.debug('Could not play sound:', error);
    }
  }

  function showDesktopNotification(message: ChatMessage) {
    if (!('Notification' in window) || Notification.permission !== 'granted') return;
    
    new Notification(`💬 ${message.username}`, {
      body: message.content.length > 100 ? `${message.content.slice(0, 100)}...` : message.content,
      icon: message.avatar || '/icons/logo-192x192.png',
      tag: message.id,
      requireInteraction: true,
      silent: true,
    });
  }

  // ============================================
  // API Calls - Real Data
  // ============================================
  const fetchMessages = useCallback(async () => {
    if (!selectedRoom) return;
    setMessagesLoading(true);
    
    try {
      const response = await api.get('/chat/messages', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          roomId: selectedRoom.id,
          limit: 100,
          before: new Date().toISOString(),
        },
      });
      
      if (response.data && response.data.messages) {
        setMessages(response.data.messages.map((m: any) => ({
          ...m,
          timestamp: new Date(m.timestamp || Date.now()),
          editedAt: m.editedAt ? new Date(m.editedAt) : undefined,
        })));
        scrollToBottom();
      }
    } catch (error) {
      console.error('Failed to fetch messages:', error);
      setShowToast({
        message: 'Failed to load messages. Please refresh.',
        type: 'error',
      });
    } finally {
      setMessagesLoading(false);
    }
  }, [api, accessToken, selectedRoom]);

  const fetchUsers = useCallback(async () => {
    try {
      const response = await api.get('/chat/users', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      if (response.data && response.data.users) {
        setUsers(response.data.users);
      }
    } catch (error) {
      console.error('Failed to fetch users:', error);
    }
  }, [api, accessToken]);

  const fetchTickets = useCallback(async () => {
    setTicketsLoading(true);
    
    try {
      const response = await api.get('/support/tickets', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          status: 'open',
        },
      });
      
      if (response.data && response.data.tickets) {
        setTickets(response.data.tickets.map((t: any) => ({
          ...t,
          createdAt: new Date(t.createdAt || Date.now()),
          updatedAt: new Date(t.updatedAt || Date.now()),
          resolvedAt: t.resolvedAt ? new Date(t.resolvedAt) : undefined,
        })));
      }
    } catch (error) {
      console.error('Failed to fetch tickets:', error);
    } finally {
      setTicketsLoading(false);
    }
  }, [api, accessToken]);

  const fetchKnowledgeArticles = useCallback(async () => {
    try {
      const response = await api.get('/knowledge/articles', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          limit: 50,
        },
      });
      
      if (response.data && response.data.articles) {
        setKnowledgeArticles(response.data.articles.map((a: any) => ({
          ...a,
          createdAt: new Date(a.createdAt || Date.now()),
          updatedAt: new Date(a.updatedAt || Date.now()),
        })));
      }
    } catch (error) {
      console.error('Failed to fetch knowledge articles:', error);
    }
  }, [api, accessToken]);

  const fetchSettings = useCallback(async () => {
    try {
      const response = await api.get('/chat/settings', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      if (response.data) {
        setSettings(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch chat settings:', error);
    }
  }, [api, accessToken]);

  const fetchAllData = useCallback(async () => {
    setIsLoading(true);
    try {
      await Promise.all([
        fetchMessages(),
        fetchUsers(),
        fetchTickets(),
        fetchKnowledgeArticles(),
        fetchSettings(),
      ]);
    } catch (error) {
      console.error('Failed to fetch all data:', error);
    } finally {
      setIsLoading(false);
    }
  }, [fetchMessages, fetchUsers, fetchTickets, fetchKnowledgeArticles, fetchSettings]);

  // ============================================
  // API Actions
  // ============================================
  const handleSendMessage = useCallback(async () => {
    if (!currentMessage.trim() && attachments.length === 0) return;
    if (!selectedRoom) {
      setShowToast({
        message: 'Please select a chat room first.',
        type: 'warning',
      });
      return;
    }

    setSendingMessage(true);
    
    try {
      const formData = new FormData();
      formData.append('content', currentMessage);
      formData.append('roomId', selectedRoom.id);
      formData.append('type', 'text');

      attachments.forEach((attachment, index) => {
        if (attachment.file) {
          formData.append(`attachment_${index}`, attachment.file);
          formData.append(`attachment_${index}_name`, attachment.name);
          formData.append(`attachment_${index}_type`, attachment.type);
        }
      });

      const response = await api.post('/chat/messages', formData, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1));
          setUploadProgress(progress);
        },
      });
      
      if (response.data) {
        handleNewMessage(response.data);
        setCurrentMessage('');
        setAttachments([]);
        setUploadProgress(0);
        sendTypingStatus(false);
      }
    } catch (error: any) {
      console.error('Failed to send message:', error);
      setShowToast({
        message: error.response?.data?.message || 'Failed to send message. Please try again.',
        type: 'error',
      });
    } finally {
      setSendingMessage(false);
    }
  }, [api, accessToken, currentMessage, attachments, selectedRoom]);

  const handleEditMessage = useCallback(async (messageId: string, newContent: string) => {
    try {
      const response = await api.put(`/chat/messages/${messageId}`, {
        content: newContent,
      }, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      if (response.data) {
        handleMessageEdited(response.data);
        setEditingMessage(null);
        setShowToast({
          message: 'Message updated',
          type: 'success',
        });
      }
    } catch (error: any) {
      console.error('Failed to edit message:', error);
      setShowToast({
        message: error.response?.data?.message || 'Failed to edit message.',
        type: 'error',
      });
    }
  }, [api, accessToken]);

  const handleDeleteMessage = useCallback(async (messageId: string) => {
    if (!confirm('Delete this message?')) return;
    
    try {
      await api.delete(`/chat/messages/${messageId}`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      handleMessageDeleted({ id: messageId });
      setShowToast({
        message: 'Message deleted',
        type: 'info',
      });
    } catch (error: any) {
      console.error('Failed to delete message:', error);
      setShowToast({
        message: 'Failed to delete message.',
        type: 'error',
      });
    }
  }, [api, accessToken]);

  const handleBulkDeleteMessages = useCallback(async () => {
    if (selectedMessages.length === 0) return;
    if (!confirm(`Delete ${selectedMessages.length} messages?`)) return;
    
    setIsBulkDeleting(true);
    
    try {
      await api.post('/chat/messages/bulk-delete', {
        messageIds: selectedMessages,
      }, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      setMessages(prev => prev.filter(m => !selectedMessages.includes(m.id)));
      setSelectedMessages([]);
      setShowToast({
        message: `${selectedMessages.length} messages deleted`,
        type: 'success',
      });
    } catch (error: any) {
      console.error('Failed to bulk delete messages:', error);
      setShowToast({
        message: error.response?.data?.message || 'Failed to delete messages.',
        type: 'error',
      });
    } finally {
      setIsBulkDeleting(false);
    }
  }, [api, accessToken, selectedMessages]);

  const handleAddReaction = useCallback(async (messageId: string, emoji: string) => {
    try {
      const response = await api.post(`/chat/messages/${messageId}/reactions`, {
        emoji,
      }, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      if (response.data) {
        handleReactionUpdate(response.data);
        setShowReactionPicker(null);
      }
    } catch (error: any) {
      console.error('Failed to add reaction:', error);
      setShowToast({
        message: 'Failed to add reaction.',
        type: 'error',
      });
    }
  }, [api, accessToken]);

  const handleRemoveReaction = useCallback(async (messageId: string, reactionId: string) => {
    try {
      await api.delete(`/chat/messages/${messageId}/reactions/${reactionId}`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      handleReactionUpdate({ messageId, userId: user?.id, removed: true });
    } catch (error: any) {
      console.error('Failed to remove reaction:', error);
    }
  }, [api, accessToken, user]);

  const handleCreateTicket = useCallback(async () => {
    if (!newTicket.subject || !newTicket.description) {
      setShowToast({
        message: 'Please fill in all required fields.',
        type: 'warning',
      });
      return;
    }

    try {
      const response = await api.post('/support/tickets', newTicket, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      if (response.data) {
        setTickets(prev => [{
          ...response.data,
          createdAt: new Date(response.data.createdAt || Date.now()),
          updatedAt: new Date(response.data.updatedAt || Date.now()),
        }, ...prev]);
        setShowTicketModal(false);
        setNewTicket({
          subject: '',
          category: 'general',
          priority: 'medium',
          description: '',
        });
        setShowToast({
          message: 'Support ticket created successfully',
          type: 'success',
        });
      }
    } catch (error: any) {
      console.error('Failed to create ticket:', error);
      setShowToast({
        message: error.response?.data?.message || 'Failed to create ticket.',
        type: 'error',
      });
    }
  }, [api, accessToken, newTicket]);

  const handleUpdateSettings = useCallback(async (updates: Partial<ChatSettings>) => {
    try {
      const response = await api.put('/chat/settings', updates, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      if (response.data) {
        setSettings(response.data);
        setShowToast({
          message: 'Settings updated successfully',
          type: 'success',
        });
      }
    } catch (error: any) {
      console.error('Failed to update settings:', error);
      setShowToast({
        message: error.response?.data?.message || 'Failed to update settings.',
        type: 'error',
      });
    }
  }, [api, accessToken]);

  const handleUploadFile = useCallback(async (files: FileList) => {
    setIsUploading(true);
    setUploadProgress(0);
    
    try {
      const fileArray = Array.from(files);
      const newAttachments: ChatAttachment[] = [];
      
      for (const file of fileArray) {
        const formData = new FormData();
        formData.append('file', file);
        
        const response = await api.post('/chat/upload', formData, {
          headers: {
            Authorization: `Bearer ${accessToken}`,
            'Content-Type': 'multipart/form-data',
          },
          onUploadProgress: (progressEvent) => {
            const progress = Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1));
            setUploadProgress(progress);
          },
        });
        
        if (response.data) {
          newAttachments.push({
            id: response.data.id || `attachment-${Date.now()}`,
            name: file.name,
            type: file.type,
            size: file.size,
            url: response.data.url || URL.createObjectURL(file),
            thumbnail: response.data.thumbnail,
            uploadedAt: new Date(),
            uploadedBy: user?.username || 'Unknown',
          });
        }
      }
      
      setAttachments(prev => [...prev, ...newAttachments]);
      setShowToast({
        message: `${newAttachments.length} file(s) uploaded successfully`,
        type: 'success',
      });
    } catch (error: any) {
      console.error('Failed to upload files:', error);
      setShowToast({
        message: error.response?.data?.message || 'Failed to upload files.',
        type: 'error',
      });
    } finally {
      setIsUploading(false);
      setUploadProgress(0);
    }
  }, [api, accessToken, user]);

  const handleSearchKnowledge = useCallback(async (query: string) => {
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }
    
    try {
      const response = await api.get('/knowledge/search', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          q: query,
          limit: 10,
        },
      });
      
      if (response.data && response.data.articles) {
        setSearchResults(response.data.articles.map((a: any) => ({
          ...a,
          createdAt: new Date(a.createdAt || Date.now()),
          updatedAt: new Date(a.updatedAt || Date.now()),
        })));
      }
    } catch (error) {
      console.error('Failed to search knowledge:', error);
    }
  }, [api, accessToken]);

  const sendTypingStatus = useCallback((isTyping: boolean) => {
    if (!isConnected || !selectedRoom) return;
    
    sendMessage({
      type: 'typing',
      payload: {
        roomId: selectedRoom.id,
        isTyping,
      },
    });
    
    setIsTyping(isTyping);
    
    if (isTyping && typingTimeoutRef.current) {
      clearTimeout(typingTimeoutRef.current);
    }
    
    if (isTyping) {
      typingTimeoutRef.current = setTimeout(() => {
        sendTypingStatus(false);
      }, 3000);
    }
  }, [isConnected, selectedRoom, sendMessage]);

  // ============================================
  // UI Helpers
  // ============================================
  const scrollToBottom = useCallback(() => {
    if (settings.autoScroll && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [settings.autoScroll]);

  const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendMessage();
    }
  }, [handleSendMessage]);

  const handleTyping = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setCurrentMessage(value);
    
    if (value.trim() && !isTyping) {
      sendTypingStatus(true);
    } else if (!value.trim() && isTyping) {
      sendTypingStatus(false);
    }
  }, [isTyping, sendTypingStatus]);

  // ============================================
  // Effects
  // ============================================
  useEffect(() => {
    fetchAllData();
    
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
    
    return () => {
      if (wsCleanupRef.current) {
        wsCleanupRef.current();
      }
      if (typingTimeoutRef.current) {
        clearTimeout(typingTimeoutRef.current);
      }
    };
  }, [fetchAllData]);

  useEffect(() => {
    if (isConnected) {
      subscribeToChannels();
    }
  }, [isConnected]);

  useEffect(() => {
    if (selectedRoom) {
      fetchMessages();
    }
  }, [selectedRoom, fetchMessages]);

  useEffect(() => {
    if (searchQuery) {
      const debounce = setTimeout(() => {
        handleSearchKnowledge(searchQuery);
      }, 500);
      return () => clearTimeout(debounce);
    }
  }, [searchQuery, handleSearchKnowledge]);

  // ============================================
  // Memoized Computations
  // ============================================
  const onlineUsers = useMemo(() => {
    return presence.filter(p => p.status === 'online');
  }, [presence]);

  const filteredMessages = useMemo(() => {
    let result = messages;
    
    if (searchQueryGlobal) {
      const query = searchQueryGlobal.toLowerCase();
      result = result.filter(m =>
        m.content.toLowerCase().includes(query) ||
        m.username.toLowerCase().includes(query)
      );
    }
    
    return result;
  }, [messages, searchQueryGlobal]);

  const chatRooms = useMemo(() => {
    return rooms.map(room => ({
      ...room,
      unreadCount: messages.filter(m => m.roomId === room.id && !m.read).length,
      lastMessage: messages.filter(m => m.roomId === room.id).pop(),
    }));
  }, [rooms, messages]);

  // ============================================
  // Render
  // ============================================
  if (isLoading && messagesLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-6">
            <div className="absolute inset-0 border-4 border-cyan-500/30 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-t-cyan-500 rounded-full animate-spin"></div>
            <div className="absolute inset-2 bg-cyan-500/10 rounded-full animate-pulse"></div>
          </div>
          <p className="text-gray-400 text-lg font-medium">Loading Chat...</p>
          <p className="text-gray-500 text-sm mt-2">Connecting to chat service</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white p-4 md:p-6 lg:p-8">
      {/* ============================================ */}
      {/* HEADER */}
      {/* ============================================ */}
      <div className="flex flex-wrap items-center justify-between mb-6 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="text-3xl">💬</div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                Chat Support
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                Real-time messaging and support tickets
              </p>
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded-lg border border-gray-700">
            <div className={cn(
              'w-2 h-2 rounded-full transition-all duration-500',
              isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
            )} />
            <span className="text-xs text-gray-400">
              {isConnected ? 'Live' : 'Disconnected'}
            </span>
          </div>
          
          <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded-lg border border-gray-700">
            <div className="flex -space-x-2">
              {onlineUsers.slice(0, 5).map((user) => (
                <Avatar
                  key={user.userId}
                  size="sm"
                  src={user.avatar}
                  alt={user.username}
                  className="border-2 border-gray-800"
                />
              ))}
              {onlineUsers.length > 5 && (
                <div className="w-6 h-6 rounded-full bg-gray-700 flex items-center justify-center text-xs text-gray-400 border-2 border-gray-800">
                  +{onlineUsers.length - 5}
                </div>
              )}
            </div>
            <span className="text-xs text-gray-400">
              {onlineUsers.length} online
            </span>
          </div>
          
          <Button
            onClick={() => setShowTicketModal(true)}
            className="bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-600 hover:to-orange-600 text-white transition-all"
          >
            <span className="mr-2">🎫</span> New Ticket
          </Button>
        </div>
      </div>

      {/* ============================================ */}
      {/* MAIN TABS */}
      {/* ============================================ */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-gray-800 border border-gray-700 rounded-lg p-1 w-full overflow-x-auto">
          <TabsTrigger
            value="chat"
            className="data-[state=active]:bg-cyan-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            💬 Chat
          </TabsTrigger>
          <TabsTrigger
            value="tickets"
            className="data-[state=active]:bg-yellow-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            🎫 Tickets ({tickets.filter(t => t.status === 'open').length})
          </TabsTrigger>
          <TabsTrigger
            value="knowledge"
            className="data-[state=active]:bg-purple-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📚 Knowledge Base
          </TabsTrigger>
          <TabsTrigger
            value="settings"
            className="data-[state=active]:bg-gray-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            ⚙️ Settings
          </TabsTrigger>
        </TabsList>

        {/* ========================================== */}
        {/* CHAT TAB */}
        {/* ========================================== */}
        <TabsContent value="chat" className="mt-4">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 lg:col-span-3">
              <Card className="p-4 bg-gray-800 border-gray-700 h-[600px] overflow-y-auto">
                <div className="flex items-center gap-2 mb-4">
                  <Input
                    type="text"
                    placeholder="Search rooms..."
                    value={searchQueryGlobal}
                    onChange={(e) => setSearchQueryGlobal(e.target.value)}
                    className="flex-1 bg-gray-700 border-gray-600 text-white text-sm"
                  />
                </div>
                <div className="space-y-2">
                  {chatRooms.map((room) => (
                    <button
                      key={room.id}
                      onClick={() => setSelectedRoom(room)}
                      className={cn(
                        'w-full p-3 rounded-lg text-left transition-colors',
                        selectedRoom?.id === room.id
                          ? 'bg-cyan-500/20 border border-cyan-500/50'
                          : 'hover:bg-gray-700/50'
                      )}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="text-2xl">{room.icon}</div>
                          <div>
                            <div className="text-sm font-medium text-white">{room.name}</div>
                            <div className="text-xs text-gray-400 truncate max-w-[120px]">
                              {room.lastMessage?.content || 'No messages'}
                            </div>
                          </div>
                        </div>
                        {room.unreadCount > 0 && (
                          <Badge className="bg-cyan-500 text-white text-xs">
                            {room.unreadCount}
                          </Badge>
                        )}
                      </div>
                    </button>
                  ))}
                </div>
              </Card>
            </div>

            <div className="col-span-12 lg:col-span-6">
              <Card className="bg-gray-800 border-gray-700 h-[600px] flex flex-col">
                <div className="p-4 border-b border-gray-700 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="text-2xl">{selectedRoom?.icon}</div>
                    <div>
                      <div className="text-sm font-medium text-white">{selectedRoom?.name}</div>
                      <div className="text-xs text-gray-400">
                        {onlineUsers.some(u => u.roomId === selectedRoom?.id) ? '🟢 Online' : '🔴 Offline'}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {selectedMessages.length > 0 && (
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={handleBulkDeleteMessages}
                        isLoading={isBulkDeleting}
                        className="bg-red-600 hover:bg-red-700"
                      >
                        🗑️ Delete ({selectedMessages.length})
                      </Button>
                    )}
                  </div>
                </div>

                <div ref={chatContainerRef} className="flex-1 overflow-y-auto p-4 space-y-3">
                  {messagesLoading ? (
                    <div className="flex items-center justify-center h-full">
                      <Spinner size="lg" className="text-cyan-500" />
                    </div>
                  ) : filteredMessages.length > 0 ? (
                    <AnimatePresence>
                      {filteredMessages.map((message) => (
                        <motion.div
                          key={message.id}
                          initial={{ opacity: 0, y: 10 }}
                          animate={{ opacity: 1, y: 0 }}
                          exit={{ opacity: 0, y: -10 }}
                          className={cn(
                            'flex gap-3 group',
                            message.userId === user?.id ? 'flex-row-reverse' : ''
                          )}
                        >
                          {settings.showAvatars && (
                            <Avatar
                              size="sm"
                              src={message.avatar}
                              alt={message.username}
                              className="flex-shrink-0"
                            />
                          )}
                          <div className={cn(
                            'max-w-[70%]',
                            message.userId === user?.id ? 'items-end' : 'items-start'
                          )}>
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-sm font-medium text-white">
                                {message.username}
                              </span>
                              {settings.showTimestamps && (
                                <span className="text-xs text-gray-500">
                                  {formatTime(message.timestamp)}
                                </span>
                              )}
                              {message.edited && (
                                <span className="text-xs text-gray-500">(edited)</span>
                              )}
                            </div>
                            <div className={cn(
                              'p-3 rounded-lg',
                              message.userId === user?.id
                                ? 'bg-cyan-500/20 border border-cyan-500/30'
                                : 'bg-gray-700/50 border border-gray-600/50'
                            )}>
                              <div className="text-sm text-white whitespace-pre-wrap">
                                {message.content}
                              </div>
                              {message.attachments && message.attachments.length > 0 && (
                                <div className="mt-2 space-y-1">
                                  {message.attachments.map((attachment) => (
                                    <div key={attachment.id} className="flex items-center gap-2 text-xs text-gray-400">
                                      <span>📎</span>
                                      <a
                                        href={attachment.url}
                                        target="_blank"
                                        rel="noopener noreferrer"
                                        className="text-cyan-400 hover:underline"
                                      >
                                        {attachment.name}
                                      </a>
                                      <span>({(attachment.size / 1024).toFixed(1)} KB)</span>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                            {message.reactions && message.reactions.length > 0 && (
                              <div className="flex flex-wrap gap-1 mt-1">
                                {message.reactions.map((reaction) => (
                                  <button
                                    key={reaction.id}
                                    onClick={() => handleRemoveReaction(message.id, reaction.id)}
                                    className="px-1.5 py-0.5 bg-gray-700 rounded-full text-xs hover:bg-gray-600 transition-colors"
                                  >
                                    {reaction.emoji} {reaction.username === user?.username ? '✓' : ''}
                                  </button>
                                ))}
                              </div>
                            )}
                            <div className="flex items-center gap-1 mt-1 opacity-0 group-hover:opacity-100 transition-opacity">
                              <button
                                onClick={() => setShowReactionPicker(message.id)}
                                className="text-xs text-gray-500 hover:text-white p-1 rounded"
                              >
                                😊
                              </button>
                              {message.userId === user?.id && (
                                <>
                                  <button
                                    onClick={() => setEditingMessage(message)}
                                    className="text-xs text-gray-500 hover:text-white p-1 rounded"
                                  >
                                    ✏️
                                  </button>
                                  <button
                                    onClick={() => handleDeleteMessage(message.id)}
                                    className="text-xs text-gray-500 hover:text-red-500 p-1 rounded"
                                  >
                                    🗑️
                                  </button>
                                </>
                              )}
                              <input
                                type="checkbox"
                                checked={selectedMessages.includes(message.id)}
                                onChange={() => {
                                  setSelectedMessages(prev =>
                                    prev.includes(message.id)
                                      ? prev.filter(id => id !== message.id)
                                      : [...prev, message.id]
                                  );
                                }}
                                className="w-3 h-3 rounded border-gray-600 bg-gray-700 text-cyan-500 focus:ring-cyan-500"
                              />
                            </div>
                          </div>
                        </motion.div>
                      ))}
                    </AnimatePresence>
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-500">
                      <div className="text-center">
                        <div className="text-4xl mb-3">💬</div>
                        <p>No messages yet</p>
                        <p className="text-sm">Start a conversation!</p>
                      </div>
                    </div>
                  )}
                  
                  {typingUsers.some(t => t.roomId === selectedRoom?.id) && (
                    <div className="flex items-center gap-2 text-gray-400 text-sm">
                      <Spinner size="sm" className="text-cyan-500" />
                      <span>Someone is typing...</span>
                    </div>
                  )}
                  
                  <div ref={messagesEndRef} />
                </div>

                <div className="p-4 border-t border-gray-700">
                  <div className="flex items-end gap-2">
                    <div className="flex-1">
                      <Textarea
                        ref={inputRef}
                        value={currentMessage}
                        onChange={handleTyping}
                        onKeyDown={handleKeyPress}
                        placeholder="Type a message..."
                        className="w-full bg-gray-700 border-gray-600 text-white resize-none"
                        rows={2}
                        disabled={!selectedRoom}
                      />
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => fileInputRef.current?.click()}
                        className="p-2 text-gray-400 hover:text-white transition-colors rounded-lg hover:bg-gray-700"
                        disabled={!selectedRoom}
                      >
                        📎
                      </button>
                      <input
                        ref={fileInputRef}
                        type="file"
                        multiple
                        className="hidden"
                        onChange={(e) => {
                          if (e.target.files) {
                            handleUploadFile(e.target.files);
                          }
                          e.target.value = '';
                        }}
                      />
                      <button
                        onClick={() => setShowEmojiPicker(!showEmojiPicker)}
                        className="p-2 text-gray-400 hover:text-white transition-colors rounded-lg hover:bg-gray-700"
                        disabled={!selectedRoom}
                      >
                        😊
                      </button>
                      <Button
                        onClick={handleSendMessage}
                        isLoading={sendingMessage || isUploading}
                        disabled={!selectedRoom || (!currentMessage.trim() && attachments.length === 0)}
                        className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600"
                      >
                        {isUploading ? `Uploading ${uploadProgress}%` : '📤 Send'}
                      </Button>
                    </div>
                  </div>
                  {attachments.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-2">
                      {attachments.map((attachment, index) => (
                        <div key={index} className="flex items-center gap-2 bg-gray-700 rounded-lg px-2 py-1 text-xs">
                          <span>📎</span>
                          <span className="text-gray-300">{attachment.name}</span>
                          <button
                            onClick={() => setAttachments(prev => prev.filter((_, i) => i !== index))}
                            className="text-gray-500 hover:text-red-500"
                          >
                            ✕
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </Card>
            </div>

            <div className="col-span-12 lg:col-span-3">
              <Card className="p-4 bg-gray-800 border-gray-700 h-[600px] overflow-y-auto">
                <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                  <span className="text-green-400">🟢</span> Online Users ({onlineUsers.length})
                </h3>
                <div className="space-y-2">
                  {onlineUsers.map((user) => (
                    <div key={user.userId} className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-700/50 transition-colors">
                      <Avatar
                        size="sm"
                        src={user.avatar}
                        alt={user.username}
                      />
                      <div>
                        <div className="text-sm text-white">{user.username}</div>
                        <div className="text-xs text-gray-400">
                          {user.status === 'online' ? '🟢 Online' : '🔴 Offline'}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* TICKETS TAB */}
        {/* ========================================== */}
        <TabsContent value="tickets" className="mt-4 space-y-6">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-gray-300">
                    Support Tickets
                  </h3>
                  <Button
                    onClick={() => setShowTicketModal(true)}
                    className="bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-600 hover:to-orange-600"
                  >
                    <span className="mr-2">➕</span> New Ticket
                  </Button>
                </div>
                {ticketsLoading ? (
                  <div className="text-center py-8">
                    <Spinner size="lg" className="mx-auto mb-4 text-cyan-500" />
                    <p className="text-gray-400">Loading tickets...</p>
                  </div>
                ) : tickets.length > 0 ? (
                  <div className="space-y-3">
                    {tickets.map((ticket) => (
                      <div
                        key={ticket.id}
                        className="p-4 bg-gray-700/30 rounded-lg border border-gray-700 hover:border-yellow-500/50 transition-colors cursor-pointer"
                        onClick={() => setCurrentTicket(ticket)}
                      >
                        <div className="flex items-center justify-between">
                          <div>
                            <div className="flex items-center gap-3">
                              <span className="text-sm font-medium text-white">
                                {ticket.subject}
                              </span>
                              <Badge className={cn(
                                'text-xs',
                                ticket.status === 'open' ? 'bg-yellow-500' :
                                ticket.status === 'in_progress' ? 'bg-blue-500' :
                                ticket.status === 'resolved' ? 'bg-green-500' : 'bg-gray-500'
                              )}>
                                {ticket.status.replace('_', ' ').toUpperCase()}
                              </Badge>
                              <Badge className={cn(
                                'text-xs',
                                ticket.priority === 'high' ? 'bg-red-500' :
                                ticket.priority === 'medium' ? 'bg-yellow-500' : 'bg-blue-500'
                              )}>
                                {ticket.priority.toUpperCase()}
                              </Badge>
                            </div>
                            <div className="text-sm text-gray-400 mt-1">{ticket.description}</div>
                            <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                              <span>Category: {ticket.category}</span>
                              <span>Created: {formatTime(ticket.createdAt)}</span>
                              {ticket.resolvedAt && (
                                <span>Resolved: {formatTime(ticket.resolvedAt)}</span>
                              )}
                            </div>
                          </div>
                          <div className="text-right">
                            <div className="text-xs text-gray-500">Messages</div>
                            <div className="text-lg font-bold text-white">
                              {ticket.messages?.length || 0}
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12 text-gray-500">
                    <div className="text-4xl mb-3">🎫</div>
                    <p>No support tickets</p>
                    <p className="text-sm">Create a ticket for support</p>
                  </div>
                )}
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* KNOWLEDGE BASE TAB */}
        {/* ========================================== */}
        <TabsContent value="knowledge" className="mt-4 space-y-6">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 lg:col-span-8">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <div className="flex items-center gap-3 mb-4">
                  <Input
                    type="text"
                    placeholder="Search knowledge base..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="flex-1 bg-gray-700 border-gray-600 text-white"
                  />
                  <Button variant="primary" onClick={() => handleSearchKnowledge(searchQuery)}>
                    🔍 Search
                  </Button>
                </div>
                <div className="space-y-3">
                  {(searchResults.length > 0 ? searchResults : knowledgeArticles).map((article) => (
                    <div
                      key={article.id}
                      className="p-4 bg-gray-700/30 rounded-lg border border-gray-700 hover:border-purple-500/50 transition-colors cursor-pointer"
                      onClick={() => {
                        setSelectedArticle(article);
                        setShowArticleModal(true);
                      }}
                    >
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="text-sm font-medium text-white">{article.title}</div>
                          <div className="text-sm text-gray-400 mt-1">{article.content.slice(0, 150)}...</div>
                          <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                            <span>Category: {article.category}</span>
                            <span>Views: {article.views}</span>
                            <span>Helpful: {article.helpful}</span>
                          </div>
                        </div>
                        <div className="flex flex-wrap gap-1">
                          {article.tags.slice(0, 3).map((tag) => (
                            <Badge key={tag} className="bg-gray-600 text-xs">
                              #{tag}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </Card>
            </div>
            <div className="col-span-12 lg:col-span-4">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-3">Categories</h3>
                <div className="space-y-2">
                  {KNOWLEDGE_TOPICS.map((topic) => (
                    <button
                      key={topic.value}
                      onClick={() => setSearchQuery(topic.label)}
                      className="w-full text-left p-2 rounded-lg hover:bg-gray-700 transition-colors"
                    >
                      <span className="text-sm text-gray-300">{topic.icon} {topic.label}</span>
                      <span className="text-xs text-gray-500 ml-2">
                        ({knowledgeArticles.filter(a => a.category === topic.value).length})
                      </span>
                    </button>
                  ))}
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* SETTINGS TAB */}
        {/* ========================================== */}
        <TabsContent value="settings" className="mt-4 space-y-6">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 lg:col-span-8">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Chat Settings</h3>
                <div className="space-y-4">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Notifications</span>
                    <Switch
                      checked={settings.notifications}
                      onCheckedChange={(checked) => handleUpdateSettings({ notifications: checked })}
                      className="data-[state=checked]:bg-cyan-500"
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Sound Notifications</span>
                    <Switch
                      checked={settings.sound}
                      onCheckedChange={(checked) => handleUpdateSettings({ sound: checked })}
                      className="data-[state=checked]:bg-cyan-500"
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Auto Scroll to New Messages</span>
                    <Switch
                      checked={settings.autoScroll}
                      onCheckedChange={(checked) => handleUpdateSettings({ autoScroll: checked })}
                      className="data-[state=checked]:bg-cyan-500"
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Show Timestamps</span>
                    <Switch
                      checked={settings.showTimestamps}
                      onCheckedChange={(checked) => handleUpdateSettings({ showTimestamps: checked })}
                      className="data-[state=checked]:bg-cyan-500"
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Show Avatars</span>
                    <Switch
                      checked={settings.showAvatars}
                      onCheckedChange={(checked) => handleUpdateSettings({ showAvatars: checked })}
                      className="data-[state=checked]:bg-cyan-500"
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Message Formatting</span>
                    <Select
                      value={settings.messageFormatting}
                      onValueChange={(value) => handleUpdateSettings({ messageFormatting: value })}
                      className="w-32 bg-gray-700 border-gray-600"
                    >
                      <option value="plain">Plain</option>
                      <option value="markdown">Markdown</option>
                    </Select>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Font Size</span>
                    <Select
                      value={settings.fontSize}
                      onValueChange={(value) => handleUpdateSettings({ fontSize: value })}
                      className="w-32 bg-gray-700 border-gray-600"
                    >
                      <option value="small">Small</option>
                      <option value="medium">Medium</option>
                      <option value="large">Large</option>
                    </Select>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      {/* ============================================ */}
      {/* CREATE TICKET MODAL */}
      {/* ============================================ */}
      <Modal
        open={showTicketModal}
        onOpenChange={setShowTicketModal}
        title="Create Support Ticket"
        className="max-w-2xl"
      >
        <div className="space-y-4">
          <div>
            <label className="text-sm text-gray-400 block mb-1">Subject *</label>
            <Input
              value={newTicket.subject}
              onChange={(e) => setNewTicket({ ...newTicket, subject: e.target.value })}
              placeholder="Brief description of your issue"
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-gray-400 block mb-1">Category</label>
              <Select
                value={newTicket.category}
                onValueChange={(value) => setNewTicket({ ...newTicket, category: value })}
                className="w-full bg-gray-700 border-gray-600"
              >
                {SUPPORT_CATEGORIES.map(cat => (
                  <option key={cat.value} value={cat.value}>
                    {cat.label}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <label className="text-sm text-gray-400 block mb-1">Priority</label>
              <Select
                value={newTicket.priority}
                onValueChange={(value) => setNewTicket({ ...newTicket, priority: value })}
                className="w-full bg-gray-700 border-gray-600"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </Select>
            </div>
          </div>
          <div>
            <label className="text-sm text-gray-400 block mb-1">Description *</label>
            <Textarea
              value={newTicket.description}
              onChange={(e) => setNewTicket({ ...newTicket, description: e.target.value })}
              placeholder="Detailed description of your issue..."
              className="w-full bg-gray-700 border-gray-600 text-white resize-none"
              rows={4}
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => setShowTicketModal(false)}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateTicket}
              className="bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-600 hover:to-orange-600"
            >
              🎫 Create Ticket
            </Button>
          </div>
        </div>
      </Modal>

      {/* ============================================ */}
      {/* ARTICLE MODAL */}
      {/* ============================================ */}
      <Modal
        open={showArticleModal}
        onOpenChange={setShowArticleModal}
        title={selectedArticle?.title || 'Knowledge Article'}
        className="max-w-3xl"
      >
        {selectedArticle && (
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <Badge className="bg-purple-500 text-xs">{selectedArticle.category}</Badge>
              <div className="flex flex-wrap gap-1">
                {selectedArticle.tags.map((tag) => (
                  <Badge key={tag} className="bg-gray-600 text-xs">
                    #{tag}
                  </Badge>
                ))}
              </div>
            </div>
            <div className="prose prose-invert max-w-none">
              <p className="text-gray-300 whitespace-pre-wrap">{selectedArticle.content}</p>
            </div>
            <div className="flex items-center gap-4 pt-4 border-t border-gray-700 text-xs text-gray-500">
              <span>Author: {selectedArticle.author}</span>
              <span>Created: {formatDate(selectedArticle.createdAt)}</span>
              <span>Updated: {formatDate(selectedArticle.updatedAt)}</span>
              <span>Views: {selectedArticle.views}</span>
              <span>Helpful: {selectedArticle.helpful}</span>
            </div>
            <div className="flex gap-2">
              <Button
                variant="primary"
                size="sm"
                className="bg-green-600 hover:bg-green-700"
                onClick={() => {
                  setKnowledgeArticles(prev =>
                    prev.map(a =>
                      a.id === selectedArticle.id
                        ? { ...a, helpful: a.helpful + 1 }
                        : a
                    )
                  );
                }}
              >
                👍 Helpful
              </Button>
              <Button
                variant="outline"
                size="sm"
                className="border-gray-600 hover:border-gray-500"
              >
                👎 Not Helpful
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* ============================================ */}
      {/* TOAST NOTIFICATIONS */}
      {/* ============================================ */}
      <AnimatePresence>
        {showToast && (
          <Toast
            message={showToast.message}
            type={showToast.type}
            onClose={() => setShowToast(null)}
            className="fixed bottom-4 right-4 z-50 max-w-md"
            duration={5000}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

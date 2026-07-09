/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { cn, formatDate, formatTime } from '@/utils/helpers';
import { Card } from '@/components/common/Card';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Spinner } from '@/components/common/Spinner';
import { Avatar } from '@/components/common/Avatar';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import {
  Users,
  Search,
  Menu,
  X,
  Pin,
  Bell,
  BellOff,
  Settings,
  UserPlus,
  LogOut,
  MoreVertical,
  MessageSquare,
  User,
  Clock,
  CheckCircle,
  Loader2,
  AlertCircle,
} from 'lucide-react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useApi } from '@/hooks/useApi';
import { useAuth } from '@/hooks/useAuth';

// ============================================
// TYPES
// ============================================

interface ChatUser {
  id: string;
  name: string;
  avatar?: string;
  status: 'online' | 'offline' | 'away' | 'busy';
  lastSeen?: Date;
  isTyping?: boolean;
}

interface ChatRoomData {
  id: string;
  name: string;
  type: 'global' | 'private' | 'group';
  participants: ChatUser[];
  messages: ChatMessageType[];
  unreadCount: number;
  isPinned?: boolean;
  isMuted?: boolean;
  createdAt: Date;
  updatedAt: Date;
}

interface ChatMessageType {
  id: string;
  content: string;
  senderId: string;
  senderName: string;
  senderAvatar?: string;
  timestamp: Date;
  status: 'sending' | 'sent' | 'delivered' | 'read' | 'error';
  type: 'text' | 'image' | 'file' | 'system' | 'signal' | 'trade';
  isOwn: boolean;
  isEdited?: boolean;
  replyTo?: ChatMessageType;
  reactions?: {
    type: string;
    count: number;
    users: string[];
  }[];
  attachments?: {
    name: string;
    url: string;
    type: string;
    size: number;
  }[];
  metadata?: {
    signal?: {
      action: 'BUY' | 'SELL' | 'HOLD';
      symbol: string;
      price: number;
      confidence: number;
    };
    trade?: {
      action: 'BUY' | 'SELL';
      symbol: string;
      quantity: number;
      price: number;
      status: 'open' | 'closed' | 'pending';
    };
  };
}

interface ChatRoomProps {
  roomId?: string;
  onRoomChange?: (roomId: string) => void;
  onUserClick?: (userId: string) => void;
  className?: string;
}

// ============================================
// CONSTANTES
// ============================================

const MESSAGES_PER_PAGE = 50;
const TYPING_TIMEOUT = 3000;

// ============================================
// SOUS-COMPOSANTS
// ============================================

const UserStatusIndicator = ({ status }: { status: ChatUser['status'] }) => {
  const statusConfig = {
    online: { color: 'bg-green-500', label: 'En ligne' },
    offline: { color: 'bg-gray-400', label: 'Hors ligne' },
    away: { color: 'bg-yellow-500', label: 'Absent' },
    busy: { color: 'bg-red-500', label: 'Occupé' },
  };

  const config = statusConfig[status];

  return (
    <div className="flex items-center gap-1.5">
      <span className={cn('w-2 h-2 rounded-full', config.color)} />
      <span className="text-xs text-gray-500 dark:text-gray-400">{config.label}</span>
    </div>
  );
};

const TypingIndicator = ({ users }: { users: string[] }) => {
  if (users.length === 0) return null;

  const text = users.length === 1
    ? `${users[0]} écrit...`
    : `${users.length} personnes écrivent...`;

  return (
    <div className="flex items-center gap-2 px-4 py-2 text-sm text-gray-500 dark:text-gray-400">
      <Loader2 className="h-4 w-4 animate-spin" />
      <span>{text}</span>
    </div>
  );
};

// ============================================
// COMPOSANT PRINCIPAL
// ============================================

export function ChatRoom({
  roomId: initialRoomId,
  onRoomChange,
  onUserClick,
  className = '',
}: ChatRoomProps) {
  // ============================================
  // RÉFÉRENCES
  // ============================================
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const messagesContainerRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ============================================
  // ÉTATS
  // ============================================
  const [roomId, setRoomId] = useState(initialRoomId || 'global');
  const [room, setRoom] = useState<ChatRoomData | null>(null);
  const [messages, setMessages] = useState<ChatMessageType[]>([]);
  const [participants, setParticipants] = useState<ChatUser[]>([]);
  const [typingUsers, setTypingUsers] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMoreMessages, setHasMoreMessages] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showSidebar, setShowSidebar] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ============================================
  // HOOKS
  // ============================================
  const { user } = useAuth();
  const { get, post, put, del } = useApi();
  const { sendMessage, lastMessage, connect, disconnect } = useWebSocket(
    `${process.env.NEXT_PUBLIC_WEBSOCKET_URL}/chat/${roomId}`
  );

  // ============================================
  // FONCTIONS
  // ============================================

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    messagesEndRef.current?.scrollIntoView({ behavior });
  }, []);

  const loadMessages = useCallback(async (roomId: string, before?: Date) => {
    try {
      const params = {
        roomId,
        limit: MESSAGES_PER_PAGE,
        ...(before && { before: before.toISOString() }),
      };
      const response = await get('/chat/messages', { params });
      const newMessages = response.data.map((msg: any) => ({
        ...msg,
        timestamp: new Date(msg.timestamp),
        isOwn: msg.senderId === user?.id,
      }));

      if (before) {
        setMessages((prev) => [...newMessages, ...prev]);
      } else {
        setMessages(newMessages);
        setTimeout(() => scrollToBottom('auto'), 100);
      }

      setHasMoreMessages(newMessages.length === MESSAGES_PER_PAGE);
      setIsLoading(false);
      setIsLoadingMore(false);
    } catch (error) {
      console.error('Erreur lors du chargement des messages:', error);
      setError('Impossible de charger les messages');
      setIsLoading(false);
      setIsLoadingMore(false);
    }
  }, [get, user?.id, scrollToBottom]);

  const loadRoom = useCallback(async (roomId: string) => {
    try {
      const response = await get(`/chat/rooms/${roomId}`);
      const roomData = response.data;
      setRoom({
        ...roomData,
        createdAt: new Date(roomData.createdAt),
        updatedAt: new Date(roomData.updatedAt),
        participants: roomData.participants.map((p: any) => ({
          ...p,
          lastSeen: p.lastSeen ? new Date(p.lastSeen) : undefined,
        })),
      });
      setParticipants(roomData.participants);
    } catch (error) {
      console.error('Erreur lors du chargement du salon:', error);
      setError('Impossible de charger le salon');
    }
  }, [get]);

  const sendMessage = useCallback(async (content: string, attachments?: File[]) => {
    if (!content.trim() && (!attachments || attachments.length === 0)) return;

    const tempId = `temp-${Date.now()}`;
    const tempMessage: ChatMessageType = {
      id: tempId,
      content,
      senderId: user?.id || '',
      senderName: user?.name || 'Moi',
      senderAvatar: user?.avatar,
      timestamp: new Date(),
      status: 'sending',
      type: 'text',
      isOwn: true,
    };

    setMessages((prev) => [...prev, tempMessage]);
    scrollToBottom();

    try {
      const formData = new FormData();
      formData.append('content', content);
      formData.append('roomId', roomId);
      if (attachments) {
        attachments.forEach((file) => {
          formData.append('attachments', file);
        });
      }

      const response = await post('/chat/messages', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });

      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === tempId
            ? { ...response.data, timestamp: new Date(response.data.timestamp), isOwn: true }
            : msg
        )
      );
    } catch (error) {
      console.error('Erreur lors de l\'envoi du message:', error);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === tempId
            ? { ...msg, status: 'error' }
            : msg
        )
      );
    }
  }, [roomId, user, post, scrollToBottom]);

  const handleTyping = useCallback((isTyping: boolean) => {
    if (!user) return;
    sendMessage(JSON.stringify({
      type: 'typing',
      data: { userId: user.id, isTyping },
    }));
  }, [user, sendMessage]);

  const handleUserClick = useCallback((userId: string) => {
    onUserClick?.(userId);
  }, [onUserClick]);

  const handleReply = useCallback((message: ChatMessageType) => {
    if (inputRef.current) {
      // @ts-ignore - Accès à une méthode interne
      inputRef.current?.setReplyTo?.(message);
    }
  }, []);

  const handleEdit = useCallback(async (message: ChatMessageType) => {
    // Implémenter la modification
    console.log('Edit message:', message);
  }, []);

  const handleDelete = useCallback(async (message: ChatMessageType) => {
    try {
      await del(`/chat/messages/${message.id}`);
      setMessages((prev) => prev.filter((msg) => msg.id !== message.id));
    } catch (error) {
      console.error('Erreur lors de la suppression:', error);
    }
  }, [del]);

  const handlePin = useCallback(async (message: ChatMessageType) => {
    try {
      await post(`/chat/messages/${message.id}/pin`);
      // Mettre à jour localement
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === message.id
            ? { ...msg, isPinned: !msg.isPinned }
            : msg
        )
      );
    } catch (error) {
      console.error('Erreur lors de l\'épinglage:', error);
    }
  }, [post]);

  const handleCopy = useCallback((message: ChatMessageType) => {
    // La copie est gérée par le composant ChatMessage
  }, []);

  const handleReact = useCallback(async (message: ChatMessageType, reaction: string) => {
    try {
      await post(`/chat/messages/${message.id}/reactions`, { reaction });
    } catch (error) {
      console.error('Erreur lors de l\'ajout de la réaction:', error);
    }
  }, [post]);

  const handleReport = useCallback(async (message: ChatMessageType) => {
    try {
      await post(`/chat/messages/${message.id}/report`);
    } catch (error) {
      console.error('Erreur lors du signalement:', error);
    }
  }, [post]);

  const loadMoreMessages = useCallback(async () => {
    if (isLoadingMore || !hasMoreMessages || messages.length === 0) return;

    setIsLoadingMore(true);
    const oldestMessage = messages[0];
    await loadMessages(roomId, oldestMessage.timestamp);
  }, [isLoadingMore, hasMoreMessages, messages, roomId, loadMessages]);

  // ============================================
  // EFFETS
  // ============================================

  // Connexion WebSocket
  useEffect(() => {
    connect();

    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  // Chargement initial
  useEffect(() => {
    setIsLoading(true);
    setError(null);
    setMessages([]);

    const loadData = async () => {
      await Promise.all([
        loadRoom(roomId),
        loadMessages(roomId),
      ]);
    };

    loadData();
  }, [roomId, loadRoom, loadMessages]);

  // Réception des messages WebSocket
  useEffect(() => {
    if (!lastMessage) return;

    try {
      const data = JSON.parse(lastMessage);

      switch (data.type) {
        case 'message':
          const newMessage: ChatMessageType = {
            ...data.data,
            timestamp: new Date(data.data.timestamp),
            isOwn: data.data.senderId === user?.id,
          };
          setMessages((prev) => [...prev, newMessage]);
          scrollToBottom();
          break;

        case 'typing':
          setTypingUsers((prev) => {
            const userId = data.data.userId;
            const isTyping = data.data.isTyping;
            if (isTyping && !prev.includes(userId)) {
              return [...prev, userId];
            }
            if (!isTyping) {
              return prev.filter((id) => id !== userId);
            }
            return prev;
          });
          break;

        case 'read':
          setMessages((prev) =>
            prev.map((msg) =>
              msg.senderId !== user?.id && msg.status === 'delivered'
                ? { ...msg, status: 'read' }
                : msg
            )
          );
          break;

        case 'reaction':
          setMessages((prev) =>
            prev.map((msg) => {
              if (msg.id === data.data.messageId) {
                const reactions = msg.reactions || [];
                const existing = reactions.find((r) => r.type === data.data.reaction);
                if (existing) {
                  if (data.data.added) {
                    return {
                      ...msg,
                      reactions: reactions.map((r) =>
                        r.type === data.data.reaction
                          ? { ...r, count: r.count + 1, users: [...r.users, data.data.userId] }
                          : r
                      ),
                    };
                  } else {
                    return {
                      ...msg,
                      reactions: reactions
                        .map((r) =>
                          r.type === data.data.reaction
                            ? { ...r, count: r.count - 1, users: r.users.filter((id) => id !== data.data.userId) }
                            : r
                        )
                        .filter((r) => r.count > 0),
                    };
                  }
                }
                if (data.data.added) {
                  return {
                    ...msg,
                    reactions: [
                      ...reactions,
                      { type: data.data.reaction, count: 1, users: [data.data.userId] },
                    ],
                  };
                }
              }
              return msg;
            })
          );
          break;

        case 'delete':
          setMessages((prev) => prev.filter((msg) => msg.id !== data.data.messageId));
          break;

        case 'edit':
          setMessages((prev) =>
            prev.map((msg) =>
              msg.id === data.data.messageId
                ? { ...msg, content: data.data.content, isEdited: true }
                : msg
            )
          );
          break;

        default:
          break;
      }
    } catch (error) {
      console.error('Erreur de traitement WebSocket:', error);
    }
  }, [lastMessage, user?.id, scrollToBottom]);

  // Détection de la fin du scroll pour charger plus de messages
  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;

    const handleScroll = () => {
      if (container.scrollTop === 0) {
        loadMoreMessages();
      }
    };

    container.addEventListener('scroll', handleScroll);
    return () => container.removeEventListener('scroll', handleScroll);
  }, [loadMoreMessages]);

  // ============================================
  // RENDU
  // ============================================

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner className="h-8 w-8" />
        <span className="ml-2 text-gray-600 dark:text-gray-400">
          Chargement du salon...
        </span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8">
        <AlertCircle className="h-12 w-12 text-red-500 mb-4" />
        <p className="text-lg text-gray-900 dark:text-white">{error}</p>
        <Button
          variant="default"
          className="mt-4"
          onClick={() => {
            setError(null);
            setIsLoading(true);
            loadRoom(roomId);
            loadMessages(roomId);
          }}
        >
          Réessayer
        </Button>
      </div>
    );
  }

  return (
    <div className={cn('flex h-full bg-white dark:bg-gray-900', className)}>
      {/* Zone de chat principale */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* En-tête */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800">
          <div className="flex items-center gap-3 min-w-0">
            <Button
              variant="ghost"
              size="sm"
              className="lg:hidden"
              onClick={() => setShowSidebar(true)}
            >
              <Menu className="h-5 w-5" />
            </Button>
            <div>
              <h2 className="font-semibold text-gray-900 dark:text-white truncate">
                {room?.name || 'Salon de chat'}
              </h2>
              <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                <Users className="h-4 w-4" />
                <span>{participants.length} participants</span>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="hidden sm:flex"
              onClick={() => {/* Ouvrir la recherche */}}
            >
              <Search className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {/* Épingler le salon */}}
            >
              <Pin className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {/* Notifications */}}
            >
              <Bell className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="hidden sm:flex"
              onClick={() => {/* Paramètres */}}
            >
              <Settings className="h-4 w-4" />
            </Button>
          </div>
        </div>

        {/* Messages */}
        <div
          ref={messagesContainerRef}
          className="flex-1 overflow-y-auto overflow-x-hidden py-4 scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-600"
        >
          {isLoadingMore && (
            <div className="flex justify-center py-2">
              <Spinner className="h-6 w-6" />
            </div>
          )}

          <div className="space-y-0.5">
            {messages.map((message, index) => {
              const prevMessage = messages[index - 1];
              const nextMessage = messages[index + 1];
              const isFirstInGroup = !prevMessage || prevMessage.senderId !== message.senderId;
              const isLastInGroup = !nextMessage || nextMessage.senderId !== message.senderId;

              return (
                <ChatMessage
                  key={message.id}
                  message={message}
                  isFirstInGroup={isFirstInGroup}
                  isLastInGroup={isLastInGroup}
                  showAvatar={isFirstInGroup}
                  showTime={isLastInGroup}
                  onReply={handleReply}
                  onEdit={handleEdit}
                  onDelete={handleDelete}
                  onPin={handlePin}
                  onCopy={handleCopy}
                  onReact={handleReact}
                  onReport={handleReport}
                  onUserClick={handleUserClick}
                />
              );
            })}
          </div>

          <TypingIndicator users={typingUsers} />
          <div ref={messagesEndRef} />
        </div>

        {/* Input */}
        <div className="border-t border-gray-200 dark:border-gray-800">
          <ChatInput
            ref={inputRef}
            onSendMessage={sendMessage}
            onTyping={handleTyping}
            placeholder="Écrivez votre message..."
            disabled={!isConnected}
            showEmojiPicker
            showFileUpload
            showImageUpload
            showVoiceRecorder
            className="border-0"
          />
        </div>
      </div>

      {/* Sidebar des participants (mobile) */}
      {showSidebar && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setShowSidebar(false)}
          />
          <div className="absolute right-0 top-0 h-full w-80 bg-white dark:bg-gray-900 shadow-xl p-4 overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">Participants</h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowSidebar(false)}
              >
                <X className="h-5 w-5" />
              </Button>
            </div>

            <div className="space-y-2">
              {participants.map((participant) => (
                <div
                  key={participant.id}
                  className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer"
                  onClick={() => {
                    handleUserClick(participant.id);
                    setShowSidebar(false);
                  }}
                >
                  <Avatar
                    src={participant.avatar}
                    alt={participant.name}
                    className="w-10 h-10"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 dark:text-white truncate">
                      {participant.name}
                    </p>
                    <UserStatusIndicator status={participant.status} />
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

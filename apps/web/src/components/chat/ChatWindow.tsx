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
  ArrowLeft,
  Phone,
  Video,
  Info,
  Star,
  StarOff,
  AtSign,
  Link,
  FileText,
  Image,
  Smile,
  Paperclip,
  Send,
} from 'lucide-react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useApi } from '@/hooks/useApi';
import { useAuth } from '@/hooks/useAuth';
import { motion, AnimatePresence } from 'framer-motion';

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
  isAdmin?: boolean;
  isModerator?: boolean;
  joinedAt?: Date;
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
  isFavorite?: boolean;
  createdAt: Date;
  updatedAt: Date;
  description?: string;
  avatar?: string;
  createdBy?: string;
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

interface ChatWindowProps {
  roomId?: string;
  onClose?: () => void;
  onBack?: () => void;
  onRoomChange?: (roomId: string) => void;
  onUserClick?: (userId: string) => void;
  className?: string;
  showHeader?: boolean;
  showSidebar?: boolean;
  showInput?: boolean;
  initialMessages?: ChatMessageType[];
  isMobile?: boolean;
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

const MessageDateDivider = ({ date }: { date: Date }) => {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  let label = formatDate(date);
  if (date.toDateString() === today.toDateString()) {
    label = "Aujourd'hui";
  } else if (date.toDateString() === yesterday.toDateString()) {
    label = 'Hier';
  }

  return (
    <div className="flex items-center justify-center my-4">
      <div className="px-4 py-1 rounded-full bg-gray-100 dark:bg-gray-800 text-xs text-gray-500 dark:text-gray-400">
        {label}
      </div>
    </div>
  );
};

// ============================================
// COMPOSANT PRINCIPAL
// ============================================

export function ChatWindow({
  roomId: initialRoomId,
  onClose,
  onBack,
  onRoomChange,
  onUserClick,
  className = '',
  showHeader = true,
  showSidebar = true,
  showInput = true,
  initialMessages = [],
  isMobile = false,
}: ChatWindowProps) {
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
  const [messages, setMessages] = useState<ChatMessageType[]>(initialMessages);
  const [participants, setParticipants] = useState<ChatUser[]>([]);
  const [typingUsers, setTypingUsers] = useState<string[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const [hasMoreMessages, setHasMoreMessages] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showSidebarState, setShowSidebarState] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [replyTo, setReplyTo] = useState<ChatMessageType | null>(null);
  const [editMessage, setEditMessage] = useState<ChatMessageType | null>(null);
  const [isFavorite, setIsFavorite] = useState(false);

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
      setIsFavorite(roomData.isFavorite || false);
    } catch (error) {
      console.error('Erreur lors du chargement du salon:', error);
      setError('Impossible de charger le salon');
    }
  }, [get]);

  const sendChatMessage = useCallback(async (content: string, attachments?: File[]) => {
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
      replyTo: replyTo || undefined,
    };

    setMessages((prev) => [...prev, tempMessage]);
    setReplyTo(null);
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
  }, [roomId, user, post, replyTo, scrollToBottom]);

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
    setReplyTo(message);
    inputRef.current?.focus();
  }, []);

  const handleEdit = useCallback(async (message: ChatMessageType) => {
    setEditMessage(message);
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

  const toggleFavorite = useCallback(async () => {
    try {
      await post(`/chat/rooms/${roomId}/favorite`);
      setIsFavorite(!isFavorite);
    } catch (error) {
      console.error('Erreur lors du changement de favori:', error);
    }
  }, [roomId, post, isFavorite]);

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
    <div className={cn('flex flex-col h-full bg-white dark:bg-gray-900', className)}>
      {/* En-tête */}
      {showHeader && (
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800">
          <div className="flex items-center gap-3 min-w-0">
            {isMobile && onBack && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onBack}
                className="flex-shrink-0"
              >
                <ArrowLeft className="h-5 w-5" />
              </Button>
            )}
            <div className="flex items-center gap-3 min-w-0">
              <Avatar
                src={room?.avatar}
                alt={room?.name}
                className="w-10 h-10 flex-shrink-0"
              />
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <h2 className="font-semibold text-gray-900 dark:text-white truncate">
                    {room?.name || 'Salon de chat'}
                  </h2>
                  {room?.isPinned && (
                    <Pin className="h-4 w-4 text-gray-400 flex-shrink-0" />
                  )}
                  {isFavorite && (
                    <Star className="h-4 w-4 text-yellow-500 flex-shrink-0" />
                  )}
                </div>
                <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                  <Users className="h-4 w-4" />
                  <span>{participants.length} participants</span>
                  {room?.type === 'private' && (
                    <span className="text-xs px-2 py-0.5 rounded-full bg-gray-200 dark:bg-gray-800">
                      Privé
                    </span>
                  )}
                </div>
              </div>
            </div>
          </div>

          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="hidden sm:flex"
              onClick={() => setShowSidebarState(!showSidebarState)}
            >
              <Info className="h-4 w-4" />
            </Button>
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
              onClick={toggleFavorite}
            >
              {isFavorite ? (
                <Star className="h-4 w-4 text-yellow-500" />
              ) : (
                <StarOff className="h-4 w-4" />
              )}
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
            {onClose && (
              <Button
                variant="ghost"
                size="sm"
                onClick={onClose}
              >
                <X className="h-5 w-5" />
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Contenu principal */}
      <div className="flex-1 flex min-h-0">
        {/* Messages */}
        <div className="flex-1 flex flex-col min-w-0">
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
                const showDateDivider = !prevMessage ||
                  new Date(message.timestamp).toDateString() !==
                  new Date(prevMessage.timestamp).toDateString();

                return (
                  <React.Fragment key={message.id}>
                    {showDateDivider && (
                      <MessageDateDivider date={message.timestamp} />
                    )}
                    <ChatMessage
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
                  </React.Fragment>
                );
              })}
            </div>

            <TypingIndicator users={typingUsers} />
            <div ref={messagesEndRef} />
          </div>

          {/* Barre de réponse */}
          {replyTo && (
            <div className="flex items-center gap-2 px-4 py-2 border-t border-gray-200 dark:border-gray-800 bg-gray-50 dark:bg-gray-800/50">
              <div className="flex-1 min-w-0">
                <div className="text-xs text-gray-500 dark:text-gray-400">
                  Réponse à {replyTo.senderName}
                </div>
                <div className="text-sm text-gray-700 dark:text-gray-300 truncate">
                  {replyTo.content}
                </div>
              </div>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setReplyTo(null)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
          )}

          {/* Input */}
          {showInput && (
            <div className="border-t border-gray-200 dark:border-gray-800">
              <ChatInput
                ref={inputRef}
                onSendMessage={sendChatMessage}
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
          )}
        </div>

        {/* Sidebar */}
        {showSidebar && showSidebarState && (
          <div className={cn(
            'w-80 border-l border-gray-200 dark:border-gray-800 overflow-y-auto p-4',
            'hidden lg:block'
          )}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">Participants</h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowSidebarState(false)}
              >
                <X className="h-4 w-4" />
              </Button>
            </div>

            <div className="space-y-2">
              {participants.map((participant) => (
                <div
                  key={participant.id}
                  className="flex items-center gap-3 p-2 rounded-lg hover:bg-gray-100 dark:hover:bg-gray-800 cursor-pointer transition-colors"
                  onClick={() => handleUserClick(participant.id)}
                >
                  <Avatar
                    src={participant.avatar}
                    alt={participant.name}
                    className="w-10 h-10"
                  />
                  <div className="flex-1 min-w-0">
                    <p className="font-medium text-gray-900 dark:text-white truncate">
                      {participant.name}
                      {participant.isAdmin && (
                        <span className="ml-1.5 text-xs text-blue-500">Admin</span>
                      )}
                      {participant.isModerator && !participant.isAdmin && (
                        <span className="ml-1.5 text-xs text-green-500">Modérateur</span>
                      )}
                    </p>
                    <UserStatusIndicator status={participant.status} />
                  </div>
                  {participant.isTyping && (
                    <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                  )}
                </div>
              ))}
            </div>

            {/* Informations du salon */}
            <div className="mt-6 pt-6 border-t border-gray-200 dark:border-gray-800">
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                Informations
              </h4>
              <div className="space-y-1 text-sm text-gray-500 dark:text-gray-400">
                <div>Créé le {formatDate(room?.createdAt || new Date())}</div>
                {room?.description && (
                  <div className="mt-2 text-gray-700 dark:text-gray-300">
                    {room.description}
                  </div>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Sidebar mobile */}
      {showSidebar && showSidebarState && isMobile && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setShowSidebarState(false)}
          />
          <div className="absolute right-0 top-0 h-full w-80 bg-white dark:bg-gray-900 shadow-xl p-4 overflow-y-auto">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-semibold">Participants</h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowSidebarState(false)}
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
                    setShowSidebarState(false);
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

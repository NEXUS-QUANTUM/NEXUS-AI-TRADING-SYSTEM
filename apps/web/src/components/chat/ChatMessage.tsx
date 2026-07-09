/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { cn, formatDate, formatTime, formatRelativeTime } from '@/utils/helpers';
import { ChatBubble, ChatMessage as ChatMessageType } from './ChatBubble';
import { Avatar } from '@/components/common/Avatar';
import { Button } from '@/components/common/Button';
import { Card } from '@/components/common/Card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/common/DropdownMenu';
import {
  MoreVertical,
  Reply,
  Edit,
  Trash2,
  Pin,
  Flag,
  Copy,
  Check,
  ThumbsUp,
  ThumbsDown,
  Heart,
  Laugh,
  Sad,
  Angry,
  AlertCircle,
  CheckCircle,
  Clock,
  XCircle,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// ============================================
// TYPES
// ============================================

interface ChatMessageProps {
  message: ChatMessageType;
  isFirstInGroup?: boolean;
  isLastInGroup?: boolean;
  showAvatar?: boolean;
  showTime?: boolean;
  showStatus?: boolean;
  showActions?: boolean;
  isHighlighted?: boolean;
  onReply?: (message: ChatMessageType) => void;
  onEdit?: (message: ChatMessageType) => void;
  onDelete?: (message: ChatMessageType) => void;
  onPin?: (message: ChatMessageType) => void;
  onCopy?: (message: ChatMessageType) => void;
  onReact?: (message: ChatMessageType, reaction: string) => void;
  onReport?: (message: ChatMessageType) => void;
  onUserClick?: (userId: string) => void;
  onAvatarClick?: (userId: string) => void;
  className?: string;
}

// ============================================
// SOUS-COMPOSANTS
// ============================================

const MessageHeader = ({
  message,
  onUserClick,
}: {
  message: ChatMessageType;
  onUserClick?: (userId: string) => void;
}) => {
  if (message.type === 'system') return null;

  return (
    <div className={cn(
      'flex items-center gap-2 mb-1 text-sm',
      message.isOwn ? 'justify-end' : 'justify-start'
    )}>
      <span
        className="font-medium text-gray-900 dark:text-white cursor-pointer hover:underline"
        onClick={() => onUserClick?.(message.senderId)}
      >
        {message.senderName}
      </span>
      {message.isEdited && (
        <span className="text-xs text-gray-400 dark:text-gray-500">
          (modifié)
        </span>
      )}
    </div>
  );
};

const MessageStatusIndicator = ({
  status,
  timestamp,
}: {
  status: ChatMessageType['status'];
  timestamp: Date;
}) => {
  const statusConfig = {
    sending: {
      icon: Clock,
      color: 'text-gray-400',
      label: 'Envoi...',
    },
    sent: {
      icon: Check,
      color: 'text-gray-400',
      label: 'Envoyé',
    },
    delivered: {
      icon: Check,
      color: 'text-blue-500',
      label: 'Distribué',
    },
    read: {
      icon: CheckCheck,
      color: 'text-green-500',
      label: 'Vu',
    },
    error: {
      icon: XCircle,
      color: 'text-red-500',
      label: 'Erreur',
    },
  };

  const config = statusConfig[status];
  const Icon = config.icon;

  return (
    <div className={cn('flex items-center gap-1 text-xs', config.color)}>
      <Icon className="h-3 w-3" />
      <span>{config.label}</span>
      <span className="text-gray-400 dark:text-gray-500">
        {formatTime(timestamp)}
      </span>
    </div>
  );
};

const MessageReactions = ({
  reactions,
  onReact,
  message,
}: {
  reactions: ChatMessageType['reactions'];
  onReact?: (message: ChatMessageType, reaction: string) => void;
  message: ChatMessageType;
}) => {
  if (!reactions || reactions.length === 0) return null;

  const emojiMap: Record<string, string> = {
    '👍': 'ThumbsUp',
    '👎': 'ThumbsDown',
    '❤️': 'Heart',
    '😂': 'Laugh',
    '😮': 'Wow',
    '😢': 'Sad',
    '😡': 'Angry',
  };

  return (
    <div className="flex flex-wrap gap-1 mt-1">
      {reactions.map((reaction, index) => (
        <button
          key={index}
          className={cn(
            'flex items-center gap-1 px-2 py-0.5 rounded-full text-xs',
            'bg-gray-100 hover:bg-gray-200 dark:bg-gray-700 dark:hover:bg-gray-600',
            'transition-colors duration-200'
          )}
          onClick={() => onReact?.(message, reaction.type)}
        >
          <span>{reaction.type}</span>
          <span className="text-gray-500 dark:text-gray-400">{reaction.count}</span>
        </button>
      ))}
    </div>
  );
};

// ============================================
// COMPOSANT PRINCIPAL
// ============================================

export function ChatMessage({
  message,
  isFirstInGroup = true,
  isLastInGroup = true,
  showAvatar = true,
  showTime = true,
  showStatus = true,
  showActions = true,
  isHighlighted = false,
  onReply,
  onEdit,
  onDelete,
  onPin,
  onCopy,
  onReact,
  onReport,
  onUserClick,
  onAvatarClick,
  className = '',
}: ChatMessageProps) {
  // ============================================
  // ÉTATS
  // ============================================
  const [isHovered, setIsHovered] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const [showReactions, setShowReactions] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [contentHeight, setContentHeight] = useState<number | null>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const messageRef = useRef<HTMLDivElement>(null);

  // ============================================
  // CONSTANTES
  // ============================================
  const MAX_CONTENT_HEIGHT = 300;
  const isSystem = message.type === 'system';
  const isSignal = message.type === 'signal';
  const isTrade = message.type === 'trade';
  const isSpecial = isSystem || isSignal || isTrade;
  const isOwn = message.isOwn;

  // ============================================
  // FONCTIONS
  // ============================================

  const handleCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
      onCopy?.(message);
    } catch (error) {
      console.error('Erreur lors de la copie:', error);
    }
  }, [message, onCopy]);

  const handleReaction = (reaction: string) => {
    onReact?.(message, reaction);
    setShowReactions(false);
  };

  const formatMessageTime = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();

    if (diff < 60000) return 'À l\'instant';
    if (diff < 3600000) return `Il y a ${Math.floor(diff / 60000)} min`;
    if (diff < 86400000) return formatTime(date);
    if (diff < 172800000) return 'Hier';
    return formatDate(date);
  };

  const getMessageStatus = () => {
    if (!isOwn) return null;
    return message.status;
  };

  // ============================================
  // EFFETS
  // ============================================

  useEffect(() => {
    if (contentRef.current) {
      setContentHeight(contentRef.current.scrollHeight);
    }
  }, [message.content]);

  useEffect(() => {
    if (isHighlighted && messageRef.current) {
      messageRef.current.scrollIntoView({
        behavior: 'smooth',
        block: 'center',
      });
    }
  }, [isHighlighted]);

  // ============================================
  // VARIANTES D'ANIMATION
  // ============================================

  const messageVariants = {
    initial: {
      opacity: 0,
      y: 20,
      scale: 0.95,
    },
    animate: {
      opacity: 1,
      y: 0,
      scale: 1,
      transition: {
        duration: 0.2,
        ease: 'easeOut',
      },
    },
    exit: {
      opacity: 0,
      y: -20,
      scale: 0.95,
      transition: {
        duration: 0.15,
        ease: 'easeIn',
      },
    },
  };

  // ============================================
  // RENDU
  // ============================================

  return (
    <motion.div
      ref={messageRef}
      variants={messageVariants}
      initial="initial"
      animate="animate"
      exit="exit"
      className={cn(
        'relative py-0.5',
        isHighlighted && 'bg-blue-50/50 dark:bg-blue-900/20 rounded-lg',
        className
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Groupe de messages */}
      {isFirstInGroup && !isSpecial && (
        <div className={cn(
          'flex items-center gap-3 px-4 py-1',
          isOwn ? 'justify-end' : 'justify-start'
        )}>
          {showAvatar && !isOwn && (
            <Avatar
              src={message.senderAvatar}
              alt={message.senderName}
              className="w-8 h-8 flex-shrink-0 cursor-pointer"
              onClick={() => onAvatarClick?.(message.senderId)}
            />
          )}
          <MessageHeader message={message} onUserClick={onUserClick} />
        </div>
      )}

      {/* Contenu du message */}
      <div className={cn(
        'px-4',
        isSpecial && 'px-0'
      )}>
        <div className={cn(
          'flex items-start gap-3',
          isOwn ? 'flex-row-reverse' : 'flex-row',
          isSpecial && 'justify-center'
        )}>
          {/* Avatar pour les messages envoyés */}
          {isFirstInGroup && showAvatar && isOwn && !isSpecial && (
            <Avatar
              src={message.senderAvatar}
              alt={message.senderName}
              className="w-8 h-8 flex-shrink-0 cursor-pointer order-1"
              onClick={() => onAvatarClick?.(message.senderId)}
            />
          )}

          {/* Le message lui-même */}
          <div className={cn(
            'flex-1 min-w-0 max-w-[85%]',
            isSpecial && 'max-w-full'
          )}>
            {/* Message système */}
            {isSystem && (
              <div className="text-center">
                <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-gray-100 dark:bg-gray-800 text-sm text-gray-500 dark:text-gray-400">
                  <AlertCircle className="h-4 w-4" />
                  {message.content}
                </div>
              </div>
            )}

            {/* Messages spéciaux (Signal, Trade) */}
            {isSpecial && !isSystem && (
              <Card className={cn(
                'p-4 border-l-4',
                isSignal && message.metadata?.signal && (
                  message.metadata.signal.action === 'BUY'
                    ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
                    : message.metadata.signal.action === 'SELL'
                    ? 'border-red-500 bg-red-50 dark:bg-red-900/20'
                    : 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20'
                ),
                isTrade && 'border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50'
              )}>
                {isSignal && message.metadata?.signal && (
                  <>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className={cn(
                          'px-2 py-0.5 rounded text-xs font-bold text-white',
                          message.metadata.signal.action === 'BUY'
                            ? 'bg-green-500'
                            : message.metadata.signal.action === 'SELL'
                            ? 'bg-red-500'
                            : 'bg-yellow-500'
                        )}>
                          {message.metadata.signal.action}
                        </span>
                        <span className="font-bold">{message.metadata.signal.symbol}</span>
                      </div>
                      <div className="text-sm text-gray-500 dark:text-gray-400">
                        Confiance: {(message.metadata.signal.confidence * 100).toFixed(0)}%
                      </div>
                    </div>
                    <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">Prix:</span>
                        <span className="ml-2 font-medium">{message.metadata.signal.price}</span>
                      </div>
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">Risque:</span>
                        <span className="ml-2 font-medium">
                          {(message.metadata.signal.risk_score * 100).toFixed(0)}%
                        </span>
                      </div>
                    </div>
                    <div className="mt-2 text-sm text-gray-700 dark:text-gray-300">
                      {message.content}
                    </div>
                  </>
                )}
                {isTrade && message.metadata?.trade && (
                  <>
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className={cn(
                          'px-2 py-0.5 rounded text-xs font-bold text-white',
                          message.metadata.trade.action === 'BUY'
                            ? 'bg-green-500'
                            : 'bg-red-500'
                        )}>
                          {message.metadata.trade.action}
                        </span>
                        <span className="font-bold">{message.metadata.trade.symbol}</span>
                      </div>
                      <div className="flex items-center gap-2">
                        {message.metadata.trade.status === 'open' && (
                          <span className="px-2 py-0.5 rounded text-xs bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
                            Ouvert
                          </span>
                        )}
                        {message.metadata.trade.status === 'closed' && (
                          <span className="px-2 py-0.5 rounded text-xs bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400">
                            Fermé
                          </span>
                        )}
                        {message.metadata.trade.status === 'pending' && (
                          <span className="px-2 py-0.5 rounded text-xs bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">
                            En attente
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="mt-2 grid grid-cols-3 gap-2 text-sm">
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">Quantité:</span>
                        <span className="ml-2 font-medium">{message.metadata.trade.quantity}</span>
                      </div>
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">Prix:</span>
                        <span className="ml-2 font-medium">{message.metadata.trade.price}</span>
                      </div>
                      <div>
                        <span className="text-gray-500 dark:text-gray-400">Total:</span>
                        <span className="ml-2 font-medium">
                          {(message.metadata.trade.quantity * message.metadata.trade.price).toFixed(2)}
                        </span>
                      </div>
                    </div>
                  </>
                )}
              </Card>
            )}

            {/* Message normal */}
            {!isSpecial && (
              <div
                className={cn(
                  'relative group rounded-2xl px-4 py-2.5',
                  isOwn
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white',
                  isHighlighted && 'ring-2 ring-blue-500 ring-offset-2'
                )}
              >
                {/* Contenu */}
                <div
                  ref={contentRef}
                  className={cn(
                    'whitespace-pre-wrap break-words',
                    !isExpanded && contentHeight && contentHeight > MAX_CONTENT_HEIGHT && 'overflow-hidden'
                  )}
                  style={{
                    maxHeight: !isExpanded && contentHeight && contentHeight > MAX_CONTENT_HEIGHT
                      ? MAX_CONTENT_HEIGHT
                      : 'none',
                  }}
                >
                  {message.content}
                </div>

                {/* Bouton "Voir plus" */}
                {contentHeight && contentHeight > MAX_CONTENT_HEIGHT && (
                  <button
                    className="mt-1 text-sm text-blue-500 hover:text-blue-600 dark:text-blue-400 dark:hover:text-blue-300"
                    onClick={() => setIsExpanded(!isExpanded)}
                  >
                    {isExpanded ? 'Voir moins' : 'Voir plus'}
                  </button>
                )}

                {/* Réactions */}
                <MessageReactions
                  reactions={message.reactions}
                  onReact={onReact}
                  message={message}
                />

                {/* Actions au survol */}
                {showActions && !isSpecial && isHovered && (
                  <div className={cn(
                    'absolute -bottom-2 flex items-center gap-1',
                    isOwn ? 'left-0 -translate-x-1/2' : 'right-0 translate-x-1/2'
                  )}>
                    {/* Bouton Réaction */}
                    <div className="relative">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 w-7 rounded-full bg-white dark:bg-gray-800 shadow-md hover:bg-gray-100 dark:hover:bg-gray-700"
                        onClick={() => setShowReactions(!showReactions)}
                      >
                        <span className="text-sm">😊</span>
                      </Button>
                      {showReactions && (
                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-1 p-1 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700">
                          <div className="flex gap-1">
                            {['👍', '👎', '❤️', '😂', '😮', '😢', '😡'].map((emoji) => (
                              <button
                                key={emoji}
                                className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                                onClick={() => handleReaction(emoji)}
                              >
                                <span className="text-lg">{emoji}</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Bouton Répondre */}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 rounded-full bg-white dark:bg-gray-800 shadow-md hover:bg-gray-100 dark:hover:bg-gray-700"
                      onClick={() => onReply?.(message)}
                    >
                      <Reply className="h-3.5 w-3.5" />
                    </Button>

                    {/* Bouton Copier */}
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 rounded-full bg-white dark:bg-gray-800 shadow-md hover:bg-gray-100 dark:hover:bg-gray-700"
                      onClick={handleCopy}
                    >
                      {isCopied ? (
                        <Check className="h-3.5 w-3.5 text-green-500" />
                      ) : (
                        <Copy className="h-3.5 w-3.5" />
                      )}
                    </Button>

                    {/* Menu Plus */}
                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 w-7 rounded-full bg-white dark:bg-gray-800 shadow-md hover:bg-gray-100 dark:hover:bg-gray-700"
                        >
                          <MoreVertical className="h-3.5 w-3.5" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        {isOwn && onEdit && (
                          <DropdownMenuItem onClick={() => onEdit(message)}>
                            <Edit className="h-4 w-4 mr-2" />
                            Modifier
                          </DropdownMenuItem>
                        )}
                        {isOwn && onDelete && (
                          <DropdownMenuItem
                            className="text-red-600"
                            onClick={() => onDelete(message)}
                          >
                            <Trash2 className="h-4 w-4 mr-2" />
                            Supprimer
                          </DropdownMenuItem>
                        )}
                        {onPin && (
                          <DropdownMenuItem onClick={() => onPin(message)}>
                            <Pin className="h-4 w-4 mr-2" />
                            Épingler
                          </DropdownMenuItem>
                        )}
                        {onReport && (
                          <DropdownMenuItem onClick={() => onReport(message)}>
                            <Flag className="h-4 w-4 mr-2" />
                            Signaler
                          </DropdownMenuItem>
                        )}
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                )}
              </div>
            )}

            {/* Statut du message */}
            {showStatus && isOwn && !isSpecial && (
              <div className="flex justify-end mt-1">
                <MessageStatusIndicator
                  status={getMessageStatus()!}
                  timestamp={message.timestamp}
                />
              </div>
            )}

            {/* Horodatage */}
            {showTime && isLastInGroup && !isSpecial && (
              <div className={cn(
                'text-xs text-gray-400 dark:text-gray-500 mt-1',
                isOwn ? 'text-right' : 'text-left'
              )}>
                {formatMessageTime(message.timestamp)}
              </div>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

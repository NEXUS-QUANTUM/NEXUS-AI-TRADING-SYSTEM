/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import React, { useState, useRef, useEffect } from 'react';
import { cn, formatDate, formatTime } from '@/utils/helpers';
import { Button } from '@/components/common/Button';
import { Avatar } from '@/components/common/Avatar';
import { Card } from '@/components/common/Card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/common/DropdownMenu';
import {
  Copy,
  Check,
  CheckCheck,
  Clock,
  MoreVertical,
  Reply,
  Edit,
  Trash2,
  Pin,
  Flag,
  EmojiSmile,
  ThumbsUp,
  ThumbsDown,
  Heart,
  Laugh,
  Sad,
  Angry,
} from 'lucide-react';

// ============================================
// TYPES
// ============================================

export interface ChatMessage {
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
  replyTo?: ChatMessage;
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

export interface ChatBubbleProps {
  message: ChatMessage;
  onReply?: (message: ChatMessage) => void;
  onEdit?: (message: ChatMessage) => void;
  onDelete?: (message: ChatMessage) => void;
  onPin?: (message: ChatMessage) => void;
  onCopy?: (message: ChatMessage) => void;
  onReact?: (message: ChatMessage, reaction: string) => void;
  onReport?: (message: ChatMessage) => void;
  onUserClick?: (userId: string) => void;
  showAvatar?: boolean;
  showTime?: boolean;
  showStatus?: boolean;
  showActions?: boolean;
  className?: string;
}

// ============================================
// CONSTANTES
// ============================================

const STATUS_ICONS = {
  sending: Clock,
  sent: Check,
  delivered: Check,
  read: CheckCheck,
  error: Clock,
};

const STATUS_COLORS = {
  sending: 'text-gray-400',
  sent: 'text-gray-400',
  delivered: 'text-blue-500',
  read: 'text-green-500',
  error: 'text-red-500',
};

const STATUS_LABELS = {
  sending: 'Envoi...',
  sent: 'Envoyé',
  delivered: 'Distribué',
  read: 'Vu',
  error: 'Erreur',
};

const REACTIONS = [
  { emoji: '👍', label: 'Like' },
  { emoji: '👎', label: 'Dislike' },
  { emoji: '❤️', label: 'Love' },
  { emoji: '😂', label: 'Laugh' },
  { emoji: '😮', label: 'Wow' },
  { emoji: '😢', label: 'Sad' },
  { emoji: '😡', label: 'Angry' },
];

// ============================================
// SOUS-COMPOSANTS
// ============================================

const MessageStatus = ({ status }: { status: ChatMessage['status'] }) => {
  const Icon = STATUS_ICONS[status];
  const color = STATUS_COLORS[status];
  const label = STATUS_LABELS[status];

  return (
    <div className={cn('flex items-center gap-1 text-xs', color)}>
      <Icon className="h-3 w-3" />
      <span>{label}</span>
    </div>
  );
};

const MessageReactions = ({
  reactions,
  onReact,
  message,
}: {
  reactions: ChatMessage['reactions'];
  onReact?: (message: ChatMessage, reaction: string) => void;
  message: ChatMessage;
}) => {
  if (!reactions || reactions.length === 0) return null;

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

const MessageReply = ({ replyTo }: { replyTo?: ChatMessage }) => {
  if (!replyTo) return null;

  return (
    <div className={cn(
      'mb-1 px-3 py-1.5 rounded-lg text-sm',
      'bg-gray-100 dark:bg-gray-700',
      'border-l-4 border-gray-400 dark:border-gray-500'
    )}>
      <div className="text-xs text-gray-500 dark:text-gray-400">
        Réponse à {replyTo.senderName}
      </div>
      <div className="text-gray-700 dark:text-gray-300 truncate">
        {replyTo.content}
      </div>
    </div>
  );
};

// ============================================
// COMPOSANT PRINCIPAL
// ============================================

export function ChatBubble({
  message,
  onReply,
  onEdit,
  onDelete,
  onPin,
  onCopy,
  onReact,
  onReport,
  onUserClick,
  showAvatar = true,
  showTime = true,
  showStatus = true,
  showActions = true,
  className = '',
}: ChatBubbleProps) {
  // ============================================
  // ÉTATS
  // ============================================
  const [showReactions, setShowReactions] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const [isCopied, setIsCopied] = useState(false);
  const messageRef = useRef<HTMLDivElement>(null);

  // ============================================
  // FONCTIONS
  // ============================================

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
      onCopy?.(message);
    } catch (error) {
      console.error('Erreur lors de la copie:', error);
    }
  };

  const handleReaction = (reaction: string) => {
    onReact?.(message, reaction);
    setShowReactions(false);
  };

  const formatMessageTime = (date: Date) => {
    const now = new Date();
    const diff = now.getTime() - date.getTime();

    if (diff < 60000) return 'À l\'instant';
    if (diff < 3600000) return `${Math.floor(diff / 60000)} min`;
    if (diff < 86400000) return formatTime(date);
    if (diff < 172800000) return 'Hier';
    return formatDate(date);
  };

  // ============================================
  // RENDU
  // ============================================

  const isSystem = message.type === 'system';
  const isSignal = message.type === 'signal';
  const isTrade = message.type === 'trade';
  const isSpecial = isSystem || isSignal || isTrade;

  return (
    <div
      ref={messageRef}
      className={cn(
        'flex items-start gap-3 max-w-[85%]',
        message.isOwn ? 'flex-row-reverse ml-auto' : 'flex-row',
        isSystem && 'max-w-full justify-center',
        isSpecial && 'max-w-full',
        className
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {/* Avatar */}
      {showAvatar && !message.isOwn && !isSpecial && (
        <Avatar
          src={message.senderAvatar}
          alt={message.senderName}
          className="w-8 h-8 flex-shrink-0 cursor-pointer"
          onClick={() => onUserClick?.(message.senderId)}
        />
      )}

      {/* Contenu du message */}
      <div className={cn('flex-1 min-w-0', isSystem && 'text-center')}>
        {/* En-tête du message */}
        {!isSpecial && (
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
            {showTime && (
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {formatMessageTime(message.timestamp)}
              </span>
            )}
            {message.isEdited && (
              <span className="text-xs text-gray-400 dark:text-gray-500">
                (modifié)
              </span>
            )}
          </div>
        )}

        {/* Message système */}
        {isSystem && (
          <div className="text-center text-sm text-gray-500 dark:text-gray-400 py-2">
            {message.content}
          </div>
        )}

        {/* Message de signal */}
        {isSignal && message.metadata?.signal && (
          <Card className={cn(
            'p-3 border-l-4',
            message.metadata.signal.action === 'BUY'
              ? 'border-green-500 bg-green-50 dark:bg-green-900/20'
              : message.metadata.signal.action === 'SELL'
              ? 'border-red-500 bg-red-50 dark:bg-red-900/20'
              : 'border-yellow-500 bg-yellow-50 dark:bg-yellow-900/20'
          )}>
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
            <div className="mt-2 text-sm">
              Prix: {message.metadata.signal.price}
            </div>
            <div className="mt-1 text-sm text-gray-700 dark:text-gray-300">
              {message.content}
            </div>
          </Card>
        )}

        {/* Message de trade */}
        {isTrade && message.metadata?.trade && (
          <Card className="p-3 border border-gray-200 dark:border-gray-700">
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
              <div className="text-sm text-gray-500 dark:text-gray-400">
                {message.metadata.trade.status === 'open' ? 'Ouvert' :
                 message.metadata.trade.status === 'closed' ? 'Fermé' :
                 'En attente'}
              </div>
            </div>
            <div className="mt-2 grid grid-cols-2 gap-2 text-sm">
              <div>
                <span className="text-gray-500 dark:text-gray-400">Quantité:</span>
                <span className="ml-2 font-medium">{message.metadata.trade.quantity}</span>
              </div>
              <div>
                <span className="text-gray-500 dark:text-gray-400">Prix:</span>
                <span className="ml-2 font-medium">{message.metadata.trade.price}</span>
              </div>
            </div>
          </Card>
        )}

        {/* Message normal */}
        {!isSpecial && (
          <div
            className={cn(
              'relative group rounded-2xl px-4 py-2.5',
              message.isOwn
                ? 'bg-blue-500 text-white'
                : 'bg-gray-100 dark:bg-gray-700 text-gray-900 dark:text-white',
              isSpecial && 'bg-transparent'
            )}
          >
            {/* Réponse à */}
            {message.replyTo && (
              <MessageReply replyTo={message.replyTo} />
            )}

            {/* Contenu du message */}
            <div className="whitespace-pre-wrap break-words">
              {message.content}
            </div>

            {/* Pièces jointes */}
            {message.attachments && message.attachments.length > 0 && (
              <div className="mt-2 space-y-1">
                {message.attachments.map((file, index) => (
                  <div
                    key={index}
                    className="flex items-center gap-2 p-2 rounded bg-white/10 dark:bg-gray-800/50"
                  >
                    <span className="text-sm truncate flex-1">{file.name}</span>
                    <span className="text-xs opacity-70">
                      {(file.size / 1024).toFixed(0)} KB
                    </span>
                  </div>
                ))}
              </div>
            )}

            {/* Réactions */}
            <MessageReactions
              reactions={message.reactions}
              onReact={onReact}
              message={message}
            />

            {/* Actions */}
            {showActions && !isSpecial && (
              <div className={cn(
                'absolute -bottom-2 flex items-center gap-1 opacity-0 transition-opacity duration-200',
                isHovered && 'opacity-100',
                message.isOwn ? 'left-0 -translate-x-1/2' : 'right-0 translate-x-1/2'
              )}>
                {/* Bouton Réaction */}
                <DropdownMenu open={showReactions} onOpenChange={setShowReactions}>
                  <DropdownMenuTrigger asChild>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-7 w-7 rounded-full bg-white dark:bg-gray-800 shadow-md hover:bg-gray-100 dark:hover:bg-gray-700"
                    >
                      <EmojiSmile className="h-3.5 w-3.5" />
                    </Button>
                  </DropdownMenuTrigger>
                  <DropdownMenuContent align="center" className="p-1">
                    <div className="flex gap-1 p-1">
                      {REACTIONS.map((reaction) => (
                        <button
                          key={reaction.emoji}
                          className="p-1.5 rounded hover:bg-gray-100 dark:hover:bg-gray-700 transition-colors"
                          onClick={() => handleReaction(reaction.emoji)}
                          title={reaction.label}
                        >
                          <span className="text-lg">{reaction.emoji}</span>
                        </button>
                      ))}
                    </div>
                  </DropdownMenuContent>
                </DropdownMenu>

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
                    {message.isOwn && onEdit && (
                      <DropdownMenuItem onClick={() => onEdit(message)}>
                        <Edit className="h-4 w-4 mr-2" />
                        Modifier
                      </DropdownMenuItem>
                    )}
                    {message.isOwn && onDelete && (
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
        {showStatus && !isSpecial && message.isOwn && (
          <div className="flex justify-end mt-1">
            <MessageStatus status={message.status} />
          </div>
        )}
      </div>

      {/* Avatar pour les messages envoyés */}
      {showAvatar && message.isOwn && !isSpecial && (
        <Avatar
          src={message.senderAvatar}
          alt={message.senderName}
          className="w-8 h-8 flex-shrink-0 cursor-pointer order-1"
          onClick={() => onUserClick?.(message.senderId)}
        />
      )}
    </div>
  );
}

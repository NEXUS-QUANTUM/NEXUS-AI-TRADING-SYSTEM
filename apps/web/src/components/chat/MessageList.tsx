/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { cn, formatDate, formatTime } from '@/utils/helpers';
import { Spinner } from '@/components/common/Spinner';
import { Button } from '@/components/common/Button';
import { ChatMessage } from './ChatMessage';
import { ChatMessage as ChatMessageType } from './ChatBubble';
import {
  ChevronDown,
  Loader2,
  AlertCircle,
  CheckCircle,
  Clock,
  Search,
  X,
  Filter,
  ArrowUp,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// ============================================
// TYPES
// ============================================

interface MessageListProps {
  messages: ChatMessageType[];
  isLoading?: boolean;
  isLoadingMore?: boolean;
  hasMoreMessages?: boolean;
  onLoadMore?: () => void;
  onReply?: (message: ChatMessageType) => void;
  onEdit?: (message: ChatMessageType) => void;
  onDelete?: (message: ChatMessageType) => void;
  onPin?: (message: ChatMessageType) => void;
  onCopy?: (message: ChatMessageType) => void;
  onReact?: (message: ChatMessageType, reaction: string) => void;
  onReport?: (message: ChatMessageType) => void;
  onUserClick?: (userId: string) => void;
  onScrollToBottom?: () => void;
  className?: string;
  showDateDividers?: boolean;
  showAvatars?: boolean;
  showStatus?: boolean;
  showActions?: boolean;
  maxHeight?: string;
  searchQuery?: string;
  onSearchQueryChange?: (query: string) => void;
  filterType?: 'all' | 'text' | 'signal' | 'trade' | 'system';
  onFilterChange?: (filter: 'all' | 'text' | 'signal' | 'trade' | 'system') => void;
  emptyMessage?: string;
}

// ============================================
// SOUS-COMPOSANTS
// ============================================

const MessageDateDivider = ({ date }: { date: Date }) => {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  let label = formatDate(date);
  if (date >= today) {
    label = "Aujourd'hui";
  } else if (date >= yesterday) {
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

const NewMessageIndicator = ({ count, onClick }: { count: number; onClick: () => void }) => {
  if (count === 0) return null;

  return (
    <motion.div
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -20 }}
      className="sticky top-0 z-10 flex justify-center py-2"
    >
      <Button
        variant="default"
        size="sm"
        className="shadow-lg"
        onClick={onClick}
      >
        <ChevronDown className="h-4 w-4 mr-1" />
        {count} nouveau{count > 1 ? 'x' : ''} message{count > 1 ? 's' : ''}
      </Button>
    </motion.div>
  );
};

const SearchBar = ({
  value,
  onChange,
  onClose,
}: {
  value: string;
  onChange: (value: string) => void;
  onClose: () => void;
}) => {
  return (
    <div className="flex items-center gap-2 px-3 py-2 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
      <Search className="h-4 w-4 text-gray-400" />
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="Rechercher dans les messages..."
        className="flex-1 bg-transparent outline-none text-sm text-gray-900 dark:text-white placeholder:text-gray-400"
        autoFocus
      />
      <Button
        variant="ghost"
        size="sm"
        onClick={onClose}
        className="h-6 w-6 p-0"
      >
        <X className="h-4 w-4" />
      </Button>
    </div>
  );
};

const FilterButtons = ({
  currentFilter,
  onFilterChange,
}: {
  currentFilter: 'all' | 'text' | 'signal' | 'trade' | 'system';
  onFilterChange: (filter: 'all' | 'text' | 'signal' | 'trade' | 'system') => void;
}) => {
  const filters = [
    { id: 'all', label: 'Tous' },
    { id: 'text', label: 'Textes' },
    { id: 'signal', label: 'Signaux' },
    { id: 'trade', label: 'Trades' },
    { id: 'system', label: 'Système' },
  ] as const;

  return (
    <div className="flex items-center gap-1 p-1 bg-gray-100 dark:bg-gray-800 rounded-lg">
      {filters.map((filter) => (
        <button
          key={filter.id}
          className={cn(
            'px-3 py-1 rounded-md text-sm transition-all duration-200',
            currentFilter === filter.id
              ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
              : 'text-gray-500 dark:text-gray-400 hover:text-gray-700 dark:hover:text-gray-300'
          )}
          onClick={() => onFilterChange(filter.id)}
        >
          {filter.label}
        </button>
      ))}
    </div>
  );
};

// ============================================
// COMPOSANT PRINCIPAL
// ============================================

export function MessageList({
  messages,
  isLoading = false,
  isLoadingMore = false,
  hasMoreMessages = false,
  onLoadMore,
  onReply,
  onEdit,
  onDelete,
  onPin,
  onCopy,
  onReact,
  onReport,
  onUserClick,
  onScrollToBottom,
  className = '',
  showDateDividers = true,
  showAvatars = true,
  showStatus = true,
  showActions = true,
  maxHeight = '100%',
  searchQuery = '',
  onSearchQueryChange,
  filterType = 'all',
  onFilterChange,
  emptyMessage = 'Aucun message',
}: MessageListProps) {
  // ============================================
  // RÉFÉRENCES
  // ============================================
  const containerRef = useRef<HTMLDivElement>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const observerRef = useRef<IntersectionObserver | null>(null);

  // ============================================
  // ÉTATS
  // ============================================
  const [showSearch, setShowSearch] = useState(false);
  const [showFilter, setShowFilter] = useState(false);
  const [newMessagesCount, setNewMessagesCount] = useState(0);
  const [isAtBottom, setIsAtBottom] = useState(true);
  const [highlightedMessageId, setHighlightedMessageId] = useState<string | null>(null);

  // ============================================
  // FONCTIONS
  // ============================================

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'smooth') => {
    bottomRef.current?.scrollIntoView({ behavior });
    setNewMessagesCount(0);
  }, []);

  const handleScroll = useCallback(() => {
    const container = containerRef.current;
    if (!container) return;

    const { scrollTop, scrollHeight, clientHeight } = container;
    const isBottom = scrollHeight - scrollTop - clientHeight < 100;

    if (isBottom && !isAtBottom) {
      setNewMessagesCount(0);
    }

    setIsAtBottom(isBottom);

    // Charger plus de messages quand on atteint le haut
    if (scrollTop === 0 && hasMoreMessages && !isLoadingMore && onLoadMore) {
      onLoadMore();
    }
  }, [isAtBottom, hasMoreMessages, isLoadingMore, onLoadMore]);

  const handleNewMessage = useCallback(() => {
    if (!isAtBottom) {
      setNewMessagesCount((prev) => prev + 1);
    }
  }, [isAtBottom]);

  const highlightMessage = useCallback((messageId: string) => {
    setHighlightedMessageId(messageId);
    setTimeout(() => setHighlightedMessageId(null), 3000);
  }, []);

  // ============================================
  // EFFETS
  // ============================================

  // Observer pour détecter les nouveaux messages
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        setIsAtBottom(entry.isIntersecting);
        if (entry.isIntersecting) {
          setNewMessagesCount(0);
        }
      },
      {
        root: containerRef.current,
        threshold: 0.1,
        rootMargin: '0px 0px -50px 0px',
      }
    );

    const bottomElement = bottomRef.current;
    if (bottomElement) {
      observer.observe(bottomElement);
    }

    return () => {
      if (bottomElement) {
        observer.unobserve(bottomElement);
      }
    };
  }, []);

  // Observer pour le chargement infini
  useEffect(() => {
    const container = containerRef.current;
    if (!container || !onLoadMore) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const [entry] = entries;
        if (entry.isIntersecting && hasMoreMessages && !isLoadingMore) {
          onLoadMore();
        }
      },
      {
        root: container,
        threshold: 0.1,
        rootMargin: '100px 0px 0px 0px',
      }
    );

    // Observer le premier élément de la liste
    const firstMessage = container.querySelector('.message-item:first-child');
    if (firstMessage) {
      observer.observe(firstMessage);
    }

    return () => {
      observer.disconnect();
    };
  }, [messages, hasMoreMessages, isLoadingMore, onLoadMore]);

  // Filtrer les messages
  const filteredMessages = messages.filter((msg) => {
    // Filtre par type
    if (filterType !== 'all' && msg.type !== filterType) {
      return false;
    }

    // Filtre par recherche
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      return (
        msg.content.toLowerCase().includes(query) ||
        msg.senderName.toLowerCase().includes(query)
      );
    }

    return true;
  });

  // Grouper les messages par date
  const groupedMessages: { date: Date; messages: ChatMessageType[] }[] = [];
  filteredMessages.forEach((msg) => {
    const date = new Date(msg.timestamp);
    const dateKey = date.toDateString();
    const lastGroup = groupedMessages[groupedMessages.length - 1];

    if (lastGroup && new Date(lastGroup.date).toDateString() === dateKey) {
      lastGroup.messages.push(msg);
    } else {
      groupedMessages.push({ date: new Date(date), messages: [msg] });
    }
  });

  // ============================================
  // RENDU
  // ============================================

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner className="h-8 w-8" />
        <span className="ml-2 text-gray-600 dark:text-gray-400">
          Chargement des messages...
        </span>
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className={cn(
        'relative overflow-y-auto overflow-x-hidden scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-600',
        className
      )}
      style={{ maxHeight }}
      onScroll={handleScroll}
    >
      {/* Barre d'outils */}
      <div className="sticky top-0 z-10 bg-white dark:bg-gray-900 border-b border-gray-200 dark:border-gray-800 px-4 py-2">
        <div className="flex items-center justify-between gap-2">
          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-500 dark:text-gray-400">
              {filteredMessages.length} messages
            </span>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => setShowSearch(!showSearch)}
            >
              <Search className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => setShowFilter(!showFilter)}
            >
              <Filter className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={scrollToBottom}
            >
              <ArrowUp className="h-4 w-4 rotate-180" />
            </Button>
          </div>
        </div>

        {/* Barre de recherche */}
        <AnimatePresence>
          {showSearch && onSearchQueryChange && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-2"
            >
              <SearchBar
                value={searchQuery}
                onChange={onSearchQueryChange}
                onClose={() => {
                  setShowSearch(false);
                  onSearchQueryChange('');
                }}
              />
            </motion.div>
          )}
        </AnimatePresence>

        {/* Filtres */}
        <AnimatePresence>
          {showFilter && onFilterChange && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              className="mt-2"
            >
              <FilterButtons
                currentFilter={filterType}
                onFilterChange={onFilterChange}
              />
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Messages */}
      <div className="py-4">
        {isLoadingMore && (
          <div className="flex justify-center py-2">
            <Loader2 className="h-6 w-6 animate-spin text-gray-400" />
          </div>
        )}

        {filteredMessages.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-12 text-gray-500 dark:text-gray-400">
            <MessageSquare className="h-12 w-12 mb-4 opacity-50" />
            <p>{searchQuery ? 'Aucun résultat' : emptyMessage}</p>
          </div>
        ) : (
          groupedMessages.map((group, groupIndex) => (
            <div key={groupIndex}>
              {showDateDividers && (
                <MessageDateDivider date={group.date} />
              )}
              <div className="space-y-0.5">
                {group.messages.map((message, index) => {
                  const prevMessage = group.messages[index - 1];
                  const nextMessage = group.messages[index + 1];
                  const isFirstInGroup = !prevMessage || prevMessage.senderId !== message.senderId;
                  const isLastInGroup = !nextMessage || nextMessage.senderId !== message.senderId;

                  return (
                    <ChatMessage
                      key={message.id}
                      message={message}
                      isFirstInGroup={isFirstInGroup}
                      isLastInGroup={isLastInGroup}
                      showAvatar={showAvatars && isFirstInGroup}
                      showTime={showStatus && isLastInGroup}
                      showActions={showActions}
                      isHighlighted={message.id === highlightedMessageId}
                      onReply={onReply}
                      onEdit={onEdit}
                      onDelete={onDelete}
                      onPin={onPin}
                      onCopy={onCopy}
                      onReact={onReact}
                      onReport={onReport}
                      onUserClick={onUserClick}
                      className="message-item"
                    />
                  );
                })}
              </div>
            </div>
          ))
        )}
      </div>

      {/* Indicateur de nouveaux messages */}
      {newMessagesCount > 0 && (
        <NewMessageIndicator
          count={newMessagesCount}
          onClick={scrollToBottom}
        />
      )}

      <div ref={bottomRef} />
    </div>
  );
}

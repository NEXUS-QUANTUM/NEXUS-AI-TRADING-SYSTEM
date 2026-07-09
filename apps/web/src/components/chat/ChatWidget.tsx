/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { cn } from '@/utils/helpers';
import { Button } from '@/components/common/Button';
import { Avatar } from '@/components/common/Avatar';
import { Card } from '@/components/common/Card';
import { ChatRoom } from './ChatRoom';
import { ChatMessage } from './ChatMessage';
import { ChatInput } from './ChatInput';
import {
  MessageSquare,
  X,
  Minimize2,
  Maximize2,
  ChevronDown,
  ChevronUp,
  Bell,
  BellOff,
  Settings,
  UserPlus,
  Users,
  Search,
  MoreVertical,
  AlertCircle,
  CheckCircle,
  Clock,
  Loader2,
} from 'lucide-react';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useApi } from '@/hooks/useApi';
import { useAuth } from '@/hooks/useAuth';
import { motion, AnimatePresence } from 'framer-motion';

// ============================================
// TYPES
// ============================================

interface ChatWidgetProps {
  roomId?: string;
  defaultOpen?: boolean;
  position?: 'bottom-right' | 'bottom-left' | 'top-right' | 'top-left';
  size?: 'small' | 'medium' | 'large';
  showBadge?: boolean;
  unreadCount?: number;
  onOpen?: () => void;
  onClose?: () => void;
  onMinimize?: () => void;
  onMaximize?: () => void;
  className?: string;
}

// ============================================
// CONSTANTES
// ============================================

const POSITION_STYLES = {
  'bottom-right': 'bottom-4 right-4',
  'bottom-left': 'bottom-4 left-4',
  'top-right': 'top-4 right-4',
  'top-left': 'top-4 left-4',
};

const SIZE_STYLES = {
  small: 'w-80 h-96',
  medium: 'w-96 h-[500px]',
  large: 'w-[480px] h-[600px]',
};

const WIDGET_ICON_STYLES = {
  small: 'w-10 h-10',
  medium: 'w-12 h-12',
  large: 'w-14 h-14',
};

// ============================================
// COMPOSANT PRINCIPAL
// ============================================

export function ChatWidget({
  roomId = 'global',
  defaultOpen = false,
  position = 'bottom-right',
  size = 'medium',
  showBadge = true,
  unreadCount: externalUnreadCount = 0,
  onOpen,
  onClose,
  onMinimize,
  onMaximize,
  className = '',
}: ChatWidgetProps) {
  // ============================================
  // RÉFÉRENCES
  // ============================================
  const widgetRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // ============================================
  // ÉTATS
  // ============================================
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [isMinimized, setIsMinimized] = useState(false);
  const [isMaximized, setIsMaximized] = useState(false);
  const [unreadCount, setUnreadCount] = useState(externalUnreadCount);
  const [showNotification, setShowNotification] = useState(false);
  const [notificationMessage, setNotificationMessage] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const [dragOffset, setDragOffset] = useState({ x: 0, y: 0 });
  const [positionState, setPositionState] = useState(position);
  const [isMuted, setIsMuted] = useState(false);
  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<any>(null);

  // ============================================
  // HOOKS
  // ============================================
  const { user } = useAuth();
  const { get, post } = useApi();
  const { sendMessage, lastMessage: wsMessage, isConnected: wsConnected } = useWebSocket(
    `${process.env.NEXT_PUBLIC_WEBSOCKET_URL}/chat/${roomId}`
  );

  // ============================================
  // FONCTIONS
  // ============================================

  const toggleOpen = () => {
    if (isOpen) {
      setIsOpen(false);
      onClose?.();
    } else {
      setIsOpen(true);
      setUnreadCount(0);
      onOpen?.();
    }
  };

  const toggleMinimize = () => {
    setIsMinimized(!isMinimized);
    if (isMinimized) {
      onMaximize?.();
    } else {
      onMinimize?.();
    }
  };

  const toggleMaximize = () => {
    setIsMaximized(!isMaximized);
    if (isMaximized) {
      onMinimize?.();
    } else {
      onMaximize?.();
    }
  };

  const handleMouseDown = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!isMaximized) {
      setIsDragging(true);
      setDragOffset({
        x: e.clientX - widgetRef.current!.getBoundingClientRect().left,
        y: e.clientY - widgetRef.current!.getBoundingClientRect().top,
      });
    }
  };

  const handleMouseMove = useCallback((e: MouseEvent) => {
    if (isDragging && widgetRef.current) {
      const newX = e.clientX - dragOffset.x;
      const newY = e.clientY - dragOffset.y;

      // Limiter les positions aux bords de l'écran
      const maxX = window.innerWidth - widgetRef.current.offsetWidth;
      const maxY = window.innerHeight - widgetRef.current.offsetHeight;

      widgetRef.current.style.left = `${Math.max(0, Math.min(newX, maxX))}px`;
      widgetRef.current.style.top = `${Math.max(0, Math.min(newY, maxY))}px`;
      widgetRef.current.style.right = 'auto';
      widgetRef.current.style.bottom = 'auto';
    }
  }, [isDragging, dragOffset]);

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleEscape = useCallback((e: KeyboardEvent) => {
    if (e.key === 'Escape' && isOpen) {
      setIsOpen(false);
      onClose?.();
    }
  }, [isOpen, onClose]);

  const showTemporaryNotification = (message: string) => {
    setNotificationMessage(message);
    setShowNotification(true);
    setTimeout(() => {
      setShowNotification(false);
    }, 3000);
  };

  // ============================================
  // EFFETS
  // ============================================

  // Gestion des événements souris pour le drag
  useEffect(() => {
    if (isDragging) {
      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    }

    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, handleMouseMove, handleMouseUp]);

  // Gestion des raccourcis clavier
  useEffect(() => {
    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [handleEscape]);

  // Mise à jour de la connexion WebSocket
  useEffect(() => {
    setIsConnected(wsConnected);
  }, [wsConnected]);

  // Réception des messages WebSocket
  useEffect(() => {
    if (!wsMessage) return;

    try {
      const data = JSON.parse(wsMessage);
      if (data.type === 'message' && !isOpen) {
        setUnreadCount((prev) => prev + 1);
        showTemporaryNotification(`Nouveau message de ${data.data.senderName}`);
      }
      setLastMessage(data);
    } catch (error) {
      console.error('Erreur de parsing WebSocket:', error);
    }
  }, [wsMessage, isOpen]);

  // ============================================
  // RENDU
  // ============================================

  return (
    <>
      {/* Bouton flottant */}
      {!isOpen && (
        <motion.button
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', stiffness: 260, damping: 20 }}
          className={cn(
            'fixed z-50 rounded-full shadow-lg hover:shadow-xl transition-all duration-200',
            'bg-blue-600 hover:bg-blue-700 text-white',
            POSITION_STYLES[positionState],
            WIDGET_ICON_STYLES[size],
            className
          )}
          onClick={toggleOpen}
        >
          <div className="relative flex items-center justify-center w-full h-full">
            <MessageSquare className="h-6 w-6" />
            {showBadge && unreadCount > 0 && (
              <motion.span
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                className="absolute -top-1 -right-1 flex items-center justify-center min-w-[20px] h-5 px-1.5 rounded-full bg-red-500 text-white text-xs font-bold"
              >
                {unreadCount > 99 ? '99+' : unreadCount}
              </motion.span>
            )}
          </div>
        </motion.button>
      )}

      {/* Widget de chat */}
      <AnimatePresence>
        {isOpen && (
          <motion.div
            ref={widgetRef}
            initial={{ opacity: 0, scale: 0.9, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.9, y: 20 }}
            transition={{ type: 'spring', stiffness: 300, damping: 25 }}
            className={cn(
              'fixed z-50 rounded-xl shadow-2xl overflow-hidden',
              'bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800',
              POSITION_STYLES[positionState],
              isMaximized ? 'inset-4 w-auto h-auto' : SIZE_STYLES[size],
              isDragging && 'cursor-grabbing',
              className
            )}
            style={{
              ...(isDragging && {
                left: widgetRef.current?.style.left || 'auto',
                top: widgetRef.current?.style.top || 'auto',
              }),
            }}
          >
            {/* En-tête */}
            <div
              className={cn(
                'flex items-center justify-between px-4 py-3',
                'bg-blue-600 dark:bg-blue-700 text-white',
                !isMaximized && 'cursor-grab'
              )}
              onMouseDown={handleMouseDown}
            >
              <div className="flex items-center gap-2 min-w-0">
                <div className="relative flex-shrink-0">
                  <div className="w-2 h-2 rounded-full bg-green-400 animate-pulse" />
                </div>
                <span className="font-medium truncate">
                  Chat en direct
                </span>
                {isConnected && (
                  <span className="text-xs opacity-70 hidden sm:inline">
                    • Connecté
                  </span>
                )}
              </div>

              <div className="flex items-center gap-0.5">
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 w-8 p-0 text-white hover:bg-white/20"
                  onClick={() => setIsMuted(!isMuted)}
                >
                  {isMuted ? (
                    <BellOff className="h-4 w-4" />
                  ) : (
                    <Bell className="h-4 w-4" />
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 w-8 p-0 text-white hover:bg-white/20 hidden sm:flex"
                >
                  <Search className="h-4 w-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 w-8 p-0 text-white hover:bg-white/20"
                  onClick={toggleMinimize}
                >
                  {isMinimized ? (
                    <ChevronUp className="h-4 w-4" />
                  ) : (
                    <ChevronDown className="h-4 w-4" />
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 w-8 p-0 text-white hover:bg-white/20 hidden md:flex"
                  onClick={toggleMaximize}
                >
                  {isMaximized ? (
                    <Minimize2 className="h-4 w-4" />
                  ) : (
                    <Maximize2 className="h-4 w-4" />
                  )}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 w-8 p-0 text-white hover:bg-white/20"
                  onClick={toggleOpen}
                >
                  <X className="h-4 w-4" />
                </Button>
              </div>
            </div>

            {/* Contenu */}
            {!isMinimized && (
              <div className={cn(
                'flex flex-col',
                isMaximized ? 'h-[calc(100%-56px)]' : 'h-[calc(100%-56px)]'
              )}>
                {/* Chat Room */}
                <ChatRoom
                  roomId={roomId}
                  className="flex-1 min-h-0"
                  onUserClick={(userId) => {
                    console.log('User clicked:', userId);
                  }}
                />
              </div>
            )}

            {/* Notification toast */}
            <AnimatePresence>
              {showNotification && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: 20 }}
                  className="absolute bottom-20 left-4 right-4 p-3 rounded-lg bg-gray-900/90 text-white text-sm shadow-lg z-10"
                >
                  {notificationMessage}
                </motion.div>
              )}
            </AnimatePresence>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Overlay de chargement */}
      {!isConnected && isOpen && (
        <div className="fixed inset-0 z-40 bg-black/20 backdrop-blur-sm flex items-center justify-center pointer-events-none">
          <div className="bg-white dark:bg-gray-900 rounded-lg shadow-lg p-4 flex items-center gap-3 pointer-events-auto">
            <Loader2 className="h-5 w-5 animate-spin text-blue-500" />
            <span className="text-gray-700 dark:text-gray-300">
              Connexion en cours...
            </span>
          </div>
        </div>
      )}
    </>
  );
}

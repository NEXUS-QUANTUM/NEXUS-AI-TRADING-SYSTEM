/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { cn, formatDate, formatTime, formatRelativeTime } from '@/utils/helpers';
import { Avatar } from '@/components/common/Avatar';
import { Button } from '@/components/common/Button';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/common/Card';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/common/DropdownMenu';
import {
  CheckCircle,
  Clock,
  AlertCircle,
  XCircle,
  User,
  MessageSquare,
  Phone,
  Mail,
  MoreVertical,
  Settings,
  LogOut,
  Ban,
  Unlock,
  Crown,
  Shield,
  Star,
  StarOff,
  UserPlus,
  UserMinus,
  Edit,
  Eye,
  EyeOff,
  Moon,
  Sun,
  Smile,
  Frown,
  Meh,
  Zap,
  Coffee,
  Home,
  Briefcase,
  Laptop,
  Smartphone,
} from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';

// ============================================
// TYPES
// ============================================

interface UserStatusData {
  id: string;
  name: string;
  avatar?: string;
  status: 'online' | 'offline' | 'away' | 'busy';
  lastSeen?: Date;
  isTyping?: boolean;
  isAdmin?: boolean;
  isModerator?: boolean;
  isMuted?: boolean;
  isBanned?: boolean;
  isFavorite?: boolean;
  bio?: string;
  email?: string;
  phone?: string;
  currentActivity?: string;
  location?: string;
  timezone?: string;
  mood?: string;
}

interface UserStatusProps {
  user: UserStatusData;
  currentUserId?: string;
  showFullDetails?: boolean;
  showActions?: boolean;
  showAvatar?: boolean;
  showStatus?: boolean;
  showLastSeen?: boolean;
  showActivity?: boolean;
  showMood?: boolean;
  onUserClick?: (userId: string) => void;
  onMessage?: (userId: string) => void;
  onCall?: (userId: string) => void;
  onEmail?: (userId: string) => void;
  onFavorite?: (userId: string, isFavorite: boolean) => void;
  onMute?: (userId: string, isMuted: boolean) => void;
  onBan?: (userId: string, isBanned: boolean) => void;
  onMakeAdmin?: (userId: string, isAdmin: boolean) => void;
  onMakeModerator?: (userId: string, isModerator: boolean) => void;
  onRemove?: (userId: string) => void;
  onEditProfile?: (userId: string) => void;
  onViewProfile?: (userId: string) => void;
  onBlock?: (userId: string, isBlocked: boolean) => void;
  onReport?: (userId: string) => void;
  className?: string;
  size?: 'sm' | 'md' | 'lg' | 'xl';
  orientation?: 'horizontal' | 'vertical';
  animated?: boolean;
}

// ============================================
// CONSTANTES
// ============================================

const STATUS_CONFIG = {
  online: {
    label: 'En ligne',
    color: 'bg-green-500',
    icon: CheckCircle,
    ringColor: 'ring-green-500',
    bgColor: 'bg-green-50 dark:bg-green-900/20',
    textColor: 'text-green-700 dark:text-green-400',
    emoji: '🟢',
  },
  offline: {
    label: 'Hors ligne',
    color: 'bg-gray-400',
    icon: XCircle,
    ringColor: 'ring-gray-400',
    bgColor: 'bg-gray-50 dark:bg-gray-800/20',
    textColor: 'text-gray-500 dark:text-gray-400',
    emoji: '⚫',
  },
  away: {
    label: 'Absent',
    color: 'bg-yellow-500',
    icon: Clock,
    ringColor: 'ring-yellow-500',
    bgColor: 'bg-yellow-50 dark:bg-yellow-900/20',
    textColor: 'text-yellow-700 dark:text-yellow-400',
    emoji: '🟡',
  },
  busy: {
    label: 'Occupé',
    color: 'bg-red-500',
    icon: AlertCircle,
    ringColor: 'ring-red-500',
    bgColor: 'bg-red-50 dark:bg-red-900/20',
    textColor: 'text-red-700 dark:text-red-400',
    emoji: '🔴',
  },
};

const MOOD_ICONS = {
  happy: Smile,
  sad: Frown,
  neutral: Meh,
  energetic: Zap,
  tired: Coffee,
  working: Briefcase,
  relaxing: Home,
};

const MOOD_LABELS = {
  happy: 'Heureux',
  sad: 'Triste',
  neutral: 'Neutre',
  energetic: 'Énergique',
  tired: 'Fatigué',
  working: 'Au travail',
  relaxing: 'Détente',
};

const ACTIVITY_ICONS = {
  'working': Briefcase,
  'studying': Laptop,
  'gaming': Smartphone,
  'reading': Eye,
  'sleeping': Moon,
  'eating': Coffee,
  'traveling': Home,
};

// ============================================
// SOUS-COMPOSANTS
// ============================================

const StatusBadge = ({
  status,
  size = 'md',
}: {
  status: UserStatusData['status'];
  size?: 'sm' | 'md' | 'lg';
}) => {
  const config = STATUS_CONFIG[status];
  const sizes = {
    sm: 'w-2 h-2',
    md: 'w-3 h-3',
    lg: 'w-4 h-4',
  };

  return (
    <span className={cn('rounded-full', sizes[size], config.color)} />
  );
};

const ActivityIndicator = ({ isTyping }: { isTyping?: boolean }) => {
  if (!isTyping) return null;

  return (
    <span className="flex items-center gap-1 text-xs text-blue-500">
      <span className="flex gap-0.5">
        <span className="w-1 h-1 rounded-full bg-blue-500 animate-bounce" style={{ animationDelay: '0ms' }} />
        <span className="w-1 h-1 rounded-full bg-blue-500 animate-bounce" style={{ animationDelay: '150ms' }} />
        <span className="w-1 h-1 rounded-full bg-blue-500 animate-bounce" style={{ animationDelay: '300ms' }} />
      </span>
      Écrit...
    </span>
  );
};

// ============================================
// COMPOSANT PRINCIPAL
// ============================================

export function UserStatus({
  user,
  currentUserId,
  showFullDetails = false,
  showActions = true,
  showAvatar = true,
  showStatus = true,
  showLastSeen = true,
  showActivity = true,
  showMood = true,
  onUserClick,
  onMessage,
  onCall,
  onEmail,
  onFavorite,
  onMute,
  onBan,
  onMakeAdmin,
  onMakeModerator,
  onRemove,
  onEditProfile,
  onViewProfile,
  onBlock,
  onReport,
  className = '',
  size = 'md',
  orientation = 'horizontal',
  animated = true,
}: UserStatusProps) {
  // ============================================
  // ÉTATS
  // ============================================
  const [isHovered, setIsHovered] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isFavorite, setIsFavorite] = useState(user.isFavorite || false);
  const [isMuted, setIsMuted] = useState(user.isMuted || false);
  const [isBanned, setIsBanned] = useState(user.isBanned || false);
  const [isAdmin, setIsAdmin] = useState(user.isAdmin || false);
  const [isModerator, setIsModerator] = useState(user.isModerator || false);
  const [isBlocked, setIsBlocked] = useState(false);

  // ============================================
  // FONCTIONS
  // ============================================

  const status = user.status || 'offline';
  const config = STATUS_CONFIG[status];
  const StatusIcon = config.icon;

  const getLastSeen = useCallback(() => {
    if (!user.lastSeen) return 'Jamais vu';
    return formatRelativeTime(user.lastSeen);
  }, [user.lastSeen]);

  const getMoodIcon = () => {
    if (!user.mood) return null;
    const moodKey = user.mood as keyof typeof MOOD_ICONS;
    return MOOD_ICONS[moodKey] || null;
  };

  const getMoodLabel = () => {
    if (!user.mood) return null;
    const moodKey = user.mood as keyof typeof MOOD_LABELS;
    return MOOD_LABELS[moodKey] || user.mood;
  };

  const handleFavorite = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsFavorite(!isFavorite);
    onFavorite?.(user.id, !isFavorite);
  };

  const handleMute = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsMuted(!isMuted);
    onMute?.(user.id, !isMuted);
  };

  const handleBan = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsBanned(!isBanned);
    onBan?.(user.id, !isBanned);
  };

  const handleAdmin = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsAdmin(!isAdmin);
    onMakeAdmin?.(user.id, !isAdmin);
  };

  const handleModerator = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsModerator(!isModerator);
    onMakeModerator?.(user.id, !isModerator);
  };

  const handleBlock = (e: React.MouseEvent) => {
    e.stopPropagation();
    setIsBlocked(!isBlocked);
    onBlock?.(user.id, !isBlocked);
  };

  // ============================================
  // RENDU
  // ============================================

  const isOwn = user.id === currentUserId;
  const MoodIcon = getMoodIcon();
  const moodLabel = getMoodLabel();

  // Taille des avatars
  const avatarSizes = {
    sm: 'w-8 h-8',
    md: 'w-10 h-10',
    lg: 'w-12 h-12',
    xl: 'w-16 h-16',
  };

  // Taille des textes
  const textSizes = {
    sm: 'text-sm',
    md: 'text-base',
    lg: 'text-lg',
    xl: 'text-xl',
  };

  return (
    <motion.div
      initial={animated ? { opacity: 0, scale: 0.95 } : undefined}
      animate={animated ? { opacity: 1, scale: 1 } : undefined}
      transition={animated ? { duration: 0.2 } : undefined}
      className={cn(
        'relative group',
        orientation === 'horizontal' ? 'flex items-center gap-3' : 'flex flex-col items-center text-center',
        className
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
      onClick={() => {
        if (onUserClick) {
          onUserClick(user.id);
        }
        if (showFullDetails) {
          setIsExpanded(!isExpanded);
        }
      }}
    >
      {/* Avatar */}
      {showAvatar && (
        <div className="relative flex-shrink-0">
          <Avatar
            src={user.avatar}
            alt={user.name}
            className={cn(
              avatarSizes[size],
              'cursor-pointer transition-all duration-200',
              isHovered && 'ring-2 ring-blue-500 ring-offset-2',
              user.status === 'online' && 'ring-2 ring-green-500 ring-offset-2'
            )}
          />
          {showStatus && (
            <span
              className={cn(
                'absolute bottom-0 right-0 rounded-full border-2 border-white dark:border-gray-900',
                size === 'sm' ? 'w-2.5 h-2.5' :
                size === 'md' ? 'w-3 h-3' :
                size === 'lg' ? 'w-3.5 h-3.5' :
                'w-4 h-4',
                config.color
              )}
            />
          )}
          {user.isTyping && (
            <span className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-blue-500 border-2 border-white dark:border-gray-900 flex items-center justify-center">
              <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
            </span>
          )}
        </div>
      )}

      {/* Informations */}
      <div className="flex-1 min-w-0">
        <div className={cn('flex items-center gap-2', orientation === 'vertical' && 'flex-col')}>
          <div className="flex items-center gap-2 min-w-0">
            <span
              className={cn(
                'font-medium text-gray-900 dark:text-white truncate',
                textSizes[size]
              )}
            >
              {user.name}
            </span>
            {user.isAdmin && (
              <Crown className="h-4 w-4 text-blue-500 flex-shrink-0" />
            )}
            {user.isModerator && !user.isAdmin && (
              <Shield className="h-4 w-4 text-green-500 flex-shrink-0" />
            )}
            {isFavorite && (
              <Star className="h-4 w-4 text-yellow-500 fill-yellow-500 flex-shrink-0" />
            )}
            {isBlocked && (
              <Ban className="h-4 w-4 text-red-500 flex-shrink-0" />
            )}
          </div>

          {showStatus && (
            <div className={cn('flex items-center gap-2', textSizes[size === 'sm' ? 'sm' : 'md'])}>
              <span className={cn('text-xs', config.textColor)}>
                {config.label}
              </span>
              {showLastSeen && status === 'offline' && user.lastSeen && (
                <span className="text-xs text-gray-400">
                  • {getLastSeen()}
                </span>
              )}
              {user.isTyping && (
                <ActivityIndicator isTyping={true} />
              )}
            </div>
          )}
        </div>

        {/* Détails supplémentaires */}
        {showFullDetails && (isExpanded || isHovered) && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            className="mt-2 space-y-2"
          >
            {user.bio && (
              <p className="text-sm text-gray-600 dark:text-gray-400">{user.bio}</p>
            )}

            {showActivity && user.currentActivity && (
              <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                {ACTIVITY_ICONS[user.currentActivity as keyof typeof ACTIVITY_ICONS] && (
                  <span>
                    {React.createElement(ACTIVITY_ICONS[user.currentActivity as keyof typeof ACTIVITY_ICONS], { className: 'h-4 w-4' })}
                  </span>
                )}
                <span>{user.currentActivity}</span>
              </div>
            )}

            {showMood && MoodIcon && moodLabel && (
              <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                <MoodIcon className="h-4 w-4" />
                <span>{moodLabel}</span>
              </div>
            )}

            {user.location && (
              <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                <Home className="h-4 w-4" />
                <span>{user.location}</span>
              </div>
            )}

            {user.timezone && (
              <div className="flex items-center gap-2 text-sm text-gray-500 dark:text-gray-400">
                <Clock className="h-4 w-4" />
                <span>UTC {user.timezone}</span>
              </div>
            )}

            {!isOwn && (
              <div className="flex flex-wrap gap-1 mt-2">
                {onMessage && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      onMessage(user.id);
                    }}
                  >
                    <MessageSquare className="h-4 w-4 mr-1" />
                    Message
                  </Button>
                )}
                {onCall && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      onCall(user.id);
                    }}
                  >
                    <Phone className="h-4 w-4 mr-1" />
                    Appeler
                  </Button>
                )}
                {onEmail && user.email && (
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={(e) => {
                      e.stopPropagation();
                      onEmail(user.id);
                    }}
                  >
                    <Mail className="h-4 w-4 mr-1" />
                    Email
                  </Button>
                )}
              </div>
            )}
          </motion.div>
        )}
      </div>

      {/* Actions */}
      {showActions && !isOwn && (isHovered || isExpanded) && (
        <div className="flex items-center gap-1 flex-shrink-0">
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={handleFavorite}
          >
            {isFavorite ? (
              <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
            ) : (
              <Star className="h-4 w-4" />
            )}
          </Button>

          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0"
              >
                <MoreVertical className="h-4 w-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {onViewProfile && (
                <DropdownMenuItem onClick={() => onViewProfile(user.id)}>
                  <Eye className="h-4 w-4 mr-2" />
                  Voir le profil
                </DropdownMenuItem>
              )}
              {onEditProfile && isOwn && (
                <DropdownMenuItem onClick={() => onEditProfile(user.id)}>
                  <Edit className="h-4 w-4 mr-2" />
                  Modifier le profil
                </DropdownMenuItem>
              )}
              {onMute && (
                <DropdownMenuItem onClick={handleMute}>
                  {isMuted ? (
                    <>
                      <Unlock className="h-4 w-4 mr-2" />
                      Désactiver le muet
                    </>
                  ) : (
                    <>
                      <EyeOff className="h-4 w-4 mr-2" />
                      Mettre en muet
                    </>
                  )}
                </DropdownMenuItem>
              )}
              {onBan && (
                <DropdownMenuItem onClick={handleBan} className="text-red-600">
                  {isBanned ? (
                    <>
                      <Unlock className="h-4 w-4 mr-2" />
                      Lever le bannissement
                    </>
                  ) : (
                    <>
                      <Ban className="h-4 w-4 mr-2" />
                      Bannir
                    </>
                  )}
                </DropdownMenuItem>
              )}
              {onMakeAdmin && (
                <DropdownMenuItem onClick={handleAdmin}>
                  <Crown className="h-4 w-4 mr-2" />
                  {isAdmin ? 'Retirer Admin' : 'Faire Admin'}
                </DropdownMenuItem>
              )}
              {onMakeModerator && (
                <DropdownMenuItem onClick={handleModerator}>
                  <Shield className="h-4 w-4 mr-2" />
                  {isModerator ? 'Retirer Modérateur' : 'Faire Modérateur'}
                </DropdownMenuItem>
              )}
              {onBlock && (
                <DropdownMenuItem onClick={handleBlock} className="text-red-600">
                  {isBlocked ? (
                    <>
                      <Unlock className="h-4 w-4 mr-2" />
                      Débloquer
                    </>
                  ) : (
                    <>
                      <Ban className="h-4 w-4 mr-2" />
                      Bloquer
                    </>
                  )}
                </DropdownMenuItem>
              )}
              {onRemove && (
                <DropdownMenuItem onClick={() => onRemove(user.id)} className="text-red-600">
                  <UserMinus className="h-4 w-4 mr-2" />
                  Retirer
                </DropdownMenuItem>
              )}
              {onReport && (
                <DropdownMenuItem onClick={() => onReport(user.id)} className="text-red-600">
                  <AlertCircle className="h-4 w-4 mr-2" />
                  Signaler
                </DropdownMenuItem>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      )}
    </motion.div>
  );
}

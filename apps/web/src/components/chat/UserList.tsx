/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { cn, formatDate, formatTime } from '@/utils/helpers';
import { Avatar } from '@/components/common/Avatar';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Spinner } from '@/components/common/Spinner';
import { Card } from '@/components/common/Card';
import {
  Users,
  Search,
  Filter,
  X,
  MoreVertical,
  UserPlus,
  UserMinus,
  UserCheck,
  UserX,
  Crown,
  Shield,
  MessageSquare,
  Mail,
  Phone,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2,
  ChevronDown,
  ChevronRight,
  Star,
  StarOff,
  Ban,
  Unlock,
  Settings,
  LogOut,
  User,
} from 'lucide-react';
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
  isMuted?: boolean;
  isBanned?: boolean;
  joinedAt?: Date;
  lastMessage?: {
    content: string;
    timestamp: Date;
  };
  unreadCount?: number;
  isFavorite?: boolean;
  bio?: string;
  email?: string;
  phone?: string;
}

interface UserListProps {
  users: ChatUser[];
  currentUserId?: string;
  isLoading?: boolean;
  onUserClick?: (userId: string) => void;
  onUserHover?: (userId: string | null) => void;
  onInvite?: (userId: string) => void;
  onRemove?: (userId: string) => void;
  onMute?: (userId: string, isMuted: boolean) => void;
  onBan?: (userId: string, isBanned: boolean) => void;
  onMakeAdmin?: (userId: string, isAdmin: boolean) => void;
  onMakeModerator?: (userId: string, isModerator: boolean) => void;
  onFavorite?: (userId: string, isFavorite: boolean) => void;
  onMessage?: (userId: string) => void;
  className?: string;
  maxHeight?: string;
  showSearch?: boolean;
  showStatus?: boolean;
  showActions?: boolean;
  showLastMessage?: boolean;
  showUnreadCount?: boolean;
  showOnlineOnly?: boolean;
  filterRole?: 'all' | 'admin' | 'moderator' | 'user';
  sortBy?: 'name' | 'status' | 'lastActive' | 'unread';
  searchPlaceholder?: string;
  emptyMessage?: string;
}

// ============================================
// CONSTANTES
// ============================================

const STATUS_CONFIG = {
  online: { label: 'En ligne', color: 'bg-green-500', icon: CheckCircle },
  offline: { label: 'Hors ligne', color: 'bg-gray-400', icon: Clock },
  away: { label: 'Absent', color: 'bg-yellow-500', icon: Clock },
  busy: { label: 'Occupé', color: 'bg-red-500', icon: AlertCircle },
};

const STATUS_ORDER = { online: 0, away: 1, busy: 2, offline: 3 };

// ============================================
// SOUS-COMPOSANTS
// ============================================

const UserStatus = ({ status }: { status: ChatUser['status'] }) => {
  const config = STATUS_CONFIG[status];
  const Icon = config.icon;

  return (
    <div className="flex items-center gap-1.5">
      <span className={cn('w-2 h-2 rounded-full', config.color)} />
      <span className="text-xs text-gray-500 dark:text-gray-400">{config.label}</span>
    </div>
  );
};

const UserRoleBadge = ({ user }: { user: ChatUser }) => {
  if (user.isAdmin) {
    return (
      <span className="flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400">
        <Crown className="h-3 w-3" />
        Admin
      </span>
    );
  }
  if (user.isModerator) {
    return (
      <span className="flex items-center gap-0.5 px-1.5 py-0.5 rounded text-xs bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400">
        <Shield className="h-3 w-3" />
        Modérateur
      </span>
    );
  }
  return null;
};

const UserStatusIndicator = ({ user }: { user: ChatUser }) => {
  if (user.isBanned) {
    return (
      <span className="px-1.5 py-0.5 rounded text-xs bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400">
        Banni
      </span>
    );
  }
  if (user.isMuted) {
    return (
      <span className="px-1.5 py-0.5 rounded text-xs bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400">
        Muet
      </span>
    );
  }
  return <UserStatus status={user.status} />;
};

// ============================================
// COMPOSANT PRINCIPAL
// ============================================

export function UserList({
  users,
  currentUserId,
  isLoading = false,
  onUserClick,
  onUserHover,
  onInvite,
  onRemove,
  onMute,
  onBan,
  onMakeAdmin,
  onMakeModerator,
  onFavorite,
  onMessage,
  className = '',
  maxHeight = '100%',
  showSearch = true,
  showStatus = true,
  showActions = true,
  showLastMessage = true,
  showUnreadCount = true,
  showOnlineOnly = false,
  filterRole = 'all',
  sortBy = 'status',
  searchPlaceholder = 'Rechercher un utilisateur...',
  emptyMessage = 'Aucun utilisateur trouvé',
}: UserListProps) {
  // ============================================
  // ÉTATS
  // ============================================
  const [searchQuery, setSearchQuery] = useState('');
  const [hoveredUserId, setHoveredUserId] = useState<string | null>(null);
  const [selectedUserId, setSelectedUserId] = useState<string | null>(null);
  const [showActionsFor, setShowActionsFor] = useState<string | null>(null);
  const [expandedUsers, setExpandedUsers] = useState<Set<string>>(new Set());

  // ============================================
  // FONCTIONS
  // ============================================

  const toggleExpand = (userId: string) => {
    setExpandedUsers((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(userId)) {
        newSet.delete(userId);
      } else {
        newSet.add(userId);
      }
      return newSet;
    });
  };

  const getLastActive = (user: ChatUser) => {
    if (user.status === 'online') return 'En ligne';
    if (user.lastSeen) {
      const diff = Date.now() - user.lastSeen.getTime();
      if (diff < 60000) return 'Vu à l\'instant';
      if (diff < 3600000) return `Vu il y a ${Math.floor(diff / 60000)} min`;
      if (diff < 86400000) return `Vu aujourd'hui à ${formatTime(user.lastSeen)}`;
      return `Vu le ${formatDate(user.lastSeen)}`;
    }
    return 'Inconnu';
  };

  // ============================================
  // FILTRAGE ET TRI
  // ============================================

  const filteredUsers = useMemo(() => {
    let result = [...users];

    // Filtrer par recherche
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase().trim();
      result = result.filter((user) =>
        user.name.toLowerCase().includes(query) ||
        user.email?.toLowerCase().includes(query) ||
        user.bio?.toLowerCase().includes(query)
      );
    }

    // Filtrer par rôle
    if (filterRole !== 'all') {
      result = result.filter((user) => {
        if (filterRole === 'admin') return user.isAdmin;
        if (filterRole === 'moderator') return user.isModerator;
        if (filterRole === 'user') return !user.isAdmin && !user.isModerator;
        return true;
      });
    }

    // Filtrer en ligne uniquement
    if (showOnlineOnly) {
      result = result.filter((user) => user.status === 'online');
    }

    // Exclure l'utilisateur courant
    if (currentUserId) {
      result = result.filter((user) => user.id !== currentUserId);
    }

    // Trier
    result.sort((a, b) => {
      switch (sortBy) {
        case 'status':
          return STATUS_ORDER[a.status] - STATUS_ORDER[b.status];
        case 'name':
          return a.name.localeCompare(b.name);
        case 'lastActive':
          if (a.lastSeen && b.lastSeen) {
            return b.lastSeen.getTime() - a.lastSeen.getTime();
          }
          if (a.lastSeen) return -1;
          if (b.lastSeen) return 1;
          return 0;
        case 'unread':
          return (b.unreadCount || 0) - (a.unreadCount || 0);
        default:
          return 0;
      }
    });

    return result;
  }, [users, searchQuery, filterRole, showOnlineOnly, currentUserId, sortBy]);

  // ============================================
  // STATISTIQUES
  // ============================================

  const stats = useMemo(() => {
    const total = users.length;
    const online = users.filter((u) => u.status === 'online').length;
    const away = users.filter((u) => u.status === 'away').length;
    const busy = users.filter((u) => u.status === 'busy').length;
    const offline = users.filter((u) => u.status === 'offline').length;
    const admins = users.filter((u) => u.isAdmin).length;
    const moderators = users.filter((u) => u.isModerator).length;

    return { total, online, away, busy, offline, admins, moderators };
  }, [users]);

  // ============================================
  // RENDU
  // ============================================

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-full">
        <Spinner className="h-8 w-8" />
        <span className="ml-2 text-gray-600 dark:text-gray-400">
          Chargement des utilisateurs...
        </span>
      </div>
    );
  }

  return (
    <div className={cn('flex flex-col h-full', className)}>
      {/* En-tête */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-gray-200 dark:border-gray-800">
        <div className="flex items-center gap-2">
          <Users className="h-5 w-5 text-gray-500 dark:text-gray-400" />
          <span className="font-semibold text-gray-900 dark:text-white">
            Participants
          </span>
          <span className="text-sm text-gray-500 dark:text-gray-400">
            ({stats.total})
          </span>
        </div>
        <div className="flex items-center gap-1 text-xs text-gray-500 dark:text-gray-400">
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-green-500" />
            {stats.online}
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-yellow-500" />
            {stats.away}
          </span>
          <span className="flex items-center gap-1">
            <span className="w-2 h-2 rounded-full bg-red-500" />
            {stats.busy}
          </span>
        </div>
      </div>

      {/* Barre de recherche */}
      {showSearch && (
        <div className="px-4 py-2 border-b border-gray-200 dark:border-gray-800">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder={searchPlaceholder}
              className="w-full pl-9 pr-3 py-1.5 rounded-lg bg-gray-100 dark:bg-gray-800 text-sm outline-none placeholder:text-gray-400 focus:ring-2 focus:ring-blue-500"
            />
            {searchQuery && (
              <button
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                onClick={() => setSearchQuery('')}
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        </div>
      )}

      {/* Liste des utilisateurs */}
      <div
        className="flex-1 overflow-y-auto scrollbar-thin scrollbar-thumb-gray-300 dark:scrollbar-thumb-gray-600"
        style={{ maxHeight }}
      >
        {filteredUsers.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full py-12 text-gray-500 dark:text-gray-400">
            <Users className="h-12 w-12 mb-4 opacity-50" />
            <p>{searchQuery ? 'Aucun utilisateur trouvé' : emptyMessage}</p>
          </div>
        ) : (
          <div className="divide-y divide-gray-200 dark:divide-gray-800">
            {filteredUsers.map((user) => {
              const isHovered = hoveredUserId === user.id;
              const isSelected = selectedUserId === user.id;
              const isExpanded = expandedUsers.has(user.id);
              const showActionsMenu = showActionsFor === user.id;

              return (
                <motion.div
                  key={user.id}
                  initial={{ opacity: 0, y: 10 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                  className={cn(
                    'group relative hover:bg-gray-50 dark:hover:bg-gray-800/50 transition-colors',
                    isSelected && 'bg-blue-50 dark:bg-blue-900/20'
                  )}
                  onMouseEnter={() => {
                    setHoveredUserId(user.id);
                    onUserHover?.(user.id);
                  }}
                  onMouseLeave={() => {
                    setHoveredUserId(null);
                    onUserHover?.(null);
                  }}
                  onClick={() => {
                    setSelectedUserId(user.id);
                    onUserClick?.(user.id);
                  }}
                >
                  <div className="flex items-start gap-3 px-4 py-3 cursor-pointer">
                    {/* Avatar */}
                    <div className="relative flex-shrink-0">
                      <Avatar
                        src={user.avatar}
                        alt={user.name}
                        className="w-10 h-10"
                      />
                      {user.status === 'online' && (
                        <span className="absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full bg-green-500 border-2 border-white dark:border-gray-900" />
                      )}
                      {user.isTyping && (
                        <span className="absolute -bottom-1 -right-1 w-4 h-4 rounded-full bg-blue-500 border-2 border-white dark:border-gray-900 flex items-center justify-center">
                          <span className="w-1.5 h-1.5 rounded-full bg-white animate-pulse" />
                        </span>
                      )}
                    </div>

                    {/* Informations */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-900 dark:text-white truncate">
                          {user.name}
                        </span>
                        <UserRoleBadge user={user} />
                        {user.isFavorite && (
                          <Star className="h-3.5 w-3.5 text-yellow-500 fill-yellow-500 flex-shrink-0" />
                        )}
                      </div>

                      {showStatus && (
                        <div className="flex items-center gap-2 mt-0.5">
                          <UserStatusIndicator user={user} />
                          {user.status === 'offline' && user.lastSeen && (
                            <span className="text-xs text-gray-400">
                              • {getLastActive(user)}
                            </span>
                          )}
                        </div>
                      )}

                      {showLastMessage && user.lastMessage && (
                        <div className="mt-1 text-sm text-gray-500 dark:text-gray-400 truncate">
                          {user.lastMessage.content}
                        </div>
                      )}
                    </div>

                    {/* Unread count */}
                    {showUnreadCount && user.unreadCount && user.unreadCount > 0 && (
                      <span className="flex-shrink-0 px-2 py-0.5 rounded-full bg-blue-500 text-white text-xs font-medium">
                        {user.unreadCount}
                      </span>
                    )}

                    {/* Actions */}
                    {showActions && isHovered && (
                      <div className="flex items-center gap-1 flex-shrink-0">
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 w-7 p-0"
                          onClick={(e) => {
                            e.stopPropagation();
                            onMessage?.(user.id);
                          }}
                        >
                          <MessageSquare className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="h-7 w-7 p-0"
                          onClick={(e) => {
                            e.stopPropagation();
                            setShowActionsFor(showActionsMenu ? null : user.id);
                          }}
                        >
                          <MoreVertical className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    )}
                  </div>

                  {/* Menu d'actions */}
                  {showActionsMenu && (
                    <div className="absolute right-12 top-10 z-10 bg-white dark:bg-gray-800 rounded-lg shadow-lg border border-gray-200 dark:border-gray-700 py-1 min-w-[180px]">
                      {onInvite && (
                        <button
                          className="w-full px-4 py-2 text-sm text-left hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                          onClick={(e) => {
                            e.stopPropagation();
                            onInvite(user.id);
                            setShowActionsFor(null);
                          }}
                        >
                          <UserPlus className="h-4 w-4" />
                          Inviter
                        </button>
                      )}
                      {onRemove && (
                        <button
                          className="w-full px-4 py-2 text-sm text-left hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2 text-red-600"
                          onClick={(e) => {
                            e.stopPropagation();
                            onRemove(user.id);
                            setShowActionsFor(null);
                          }}
                        >
                          <UserMinus className="h-4 w-4" />
                          Retirer
                        </button>
                      )}
                      {onMute && (
                        <button
                          className="w-full px-4 py-2 text-sm text-left hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                          onClick={(e) => {
                            e.stopPropagation();
                            onMute(user.id, !user.isMuted);
                            setShowActionsFor(null);
                          }}
                        >
                          {user.isMuted ? (
                            <>
                              <Unlock className="h-4 w-4" />
                              Désactiver le muet
                            </>
                          ) : (
                            <>
                              <Ban className="h-4 w-4" />
                              Mettre en muet
                            </>
                          )}
                        </button>
                      )}
                      {onBan && (
                        <button
                          className="w-full px-4 py-2 text-sm text-left hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2 text-red-600"
                          onClick={(e) => {
                            e.stopPropagation();
                            onBan(user.id, !user.isBanned);
                            setShowActionsFor(null);
                          }}
                        >
                          {user.isBanned ? (
                            <>
                              <Unlock className="h-4 w-4" />
                              Lever le bannissement
                            </>
                          ) : (
                            <>
                              <Ban className="h-4 w-4" />
                              Bannir
                            </>
                          )}
                        </button>
                      )}
                      {onMakeAdmin && (
                        <button
                          className="w-full px-4 py-2 text-sm text-left hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                          onClick={(e) => {
                            e.stopPropagation();
                            onMakeAdmin(user.id, !user.isAdmin);
                            setShowActionsFor(null);
                          }}
                        >
                          <Crown className="h-4 w-4" />
                          {user.isAdmin ? 'Retirer Admin' : 'Faire Admin'}
                        </button>
                      )}
                      {onMakeModerator && (
                        <button
                          className="w-full px-4 py-2 text-sm text-left hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                          onClick={(e) => {
                            e.stopPropagation();
                            onMakeModerator(user.id, !user.isModerator);
                            setShowActionsFor(null);
                          }}
                        >
                          <Shield className="h-4 w-4" />
                          {user.isModerator ? 'Retirer Modérateur' : 'Faire Modérateur'}
                        </button>
                      )}
                      {onFavorite && (
                        <button
                          className="w-full px-4 py-2 text-sm text-left hover:bg-gray-100 dark:hover:bg-gray-700 flex items-center gap-2"
                          onClick={(e) => {
                            e.stopPropagation();
                            onFavorite(user.id, !user.isFavorite);
                            setShowActionsFor(null);
                          }}
                        >
                          {user.isFavorite ? (
                            <>
                              <StarOff className="h-4 w-4" />
                              Retirer des favoris
                            </>
                          ) : (
                            <>
                              <Star className="h-4 w-4" />
                              Ajouter aux favoris
                            </>
                          )}
                        </button>
                      )}
                    </div>
                  )}

                  {/* Détails étendus */}
                  {isExpanded && (
                    <div className="px-4 pb-3 text-sm">
                      <div className="grid grid-cols-2 gap-2 p-3 rounded-lg bg-gray-50 dark:bg-gray-800/50">
                        {user.email && (
                          <div>
                            <span className="text-gray-500 dark:text-gray-400">Email:</span>
                            <span className="ml-2 text-gray-700 dark:text-gray-300">{user.email}</span>
                          </div>
                        )}
                        {user.phone && (
                          <div>
                            <span className="text-gray-500 dark:text-gray-400">Téléphone:</span>
                            <span className="ml-2 text-gray-700 dark:text-gray-300">{user.phone}</span>
                          </div>
                        )}
                        {user.joinedAt && (
                          <div className="col-span-2">
                            <span className="text-gray-500 dark:text-gray-400">Membre depuis:</span>
                            <span className="ml-2 text-gray-700 dark:text-gray-300">
                              {formatDate(user.joinedAt)}
                            </span>
                          </div>
                        )}
                        {user.bio && (
                          <div className="col-span-2">
                            <span className="text-gray-500 dark:text-gray-400">Bio:</span>
                            <span className="ml-2 text-gray-700 dark:text-gray-300">{user.bio}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </motion.div>
              );
            })}
          </div>
        )}
      </div>

      {/* Pied de page avec statistiques */}
      <div className="px-4 py-2 border-t border-gray-200 dark:border-gray-800 text-xs text-gray-500 dark:text-gray-400">
        <div className="flex justify-between">
          <span>{stats.total} participants</span>
          <div className="flex gap-3">
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-green-500" />
              {stats.online}
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-yellow-500" />
              {stats.away}
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-red-500" />
              {stats.busy}
            </span>
            <span className="flex items-center gap-1">
              <span className="w-2 h-2 rounded-full bg-gray-400" />
              {stats.offline}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
}

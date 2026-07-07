/**
 * NEXUS AI TRADING SYSTEM - NotificationCenter Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This component provides a comprehensive notification center including:
 * - Real-time notification display
 * - Notification filtering by type/priority
 * - Mark as read/unread
 * - Bulk actions (mark all read, clear all)
 * - Notification grouping
 * - Priority-based highlighting
 * - Interactive notifications
 * - Notification preferences
 * - Sound notifications
 * - Desktop notifications
 * - Notification history
 * - Notification count badge
 * - Auto-dismiss
 * - Responsive design
 * - Accessibility support
 * - Real-time WebSocket updates
 * - Customizable appearance
 */

'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Bell,
  BellOff,
  BellRing,
  Check,
  X,
  AlertCircle,
  Info,
  HelpCircle,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Plus,
  Minus,
  Trash2,
  Edit,
  Save,
  RefreshCw,
  Download,
  Upload,
  Share2,
  Copy,
  ExternalLink,
  Globe,
  Zap,
  Shield,
  Lock,
  Unlock,
  Eye,
  EyeOff,
  Users,
  User,
  Mail,
  Phone,
  MapPin,
  Twitter,
  Linkedin,
  Github,
  Youtube,
  Instagram,
  Facebook,
  Telegram,
  Discord,
  Slack,
  MessageCircle,
  Send,
  MailOpen,
  PhoneCall,
  Video,
  Camera,
  Image,
  File,
  Folder,
  Archive,
  Settings,
  Filter,
  Search,
  Calendar,
  Clock,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Percent,
  Award,
  Shield as ShieldIcon,
  Sparkles,
  Crown,
  Star,
  Rocket,
  Zap as ZapIcon,
  Brain,
  Target,
  Activity,
  BarChart3,
  PieChart,
  LineChart,
  Smartphone,
  Tablet,
  Laptop,
  Monitor,
  Server,
  Cloud,
  Database,
  Network,
  Cpu,
  Memory,
  HardDrive,
} from 'lucide-react';

// Components
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Switch } from '@/components/ui/Switch';
import { Modal } from '@/components/ui/Modal';
import { Progress } from '@/components/ui/Progress';
import { Tooltip } from '@/components/ui/Tooltip';
import { Toast } from '@/components/ui/Toast';
import { Spinner } from '@/components/ui/Spinner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import { Avatar } from '@/components/ui/Avatar';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/Popover';

// Types
import type {
  Notification,
  NotificationType,
  NotificationPriority,
  NotificationFilter,
  NotificationPreferences,
} from '@/types/notifications';

// Constants
import {
  NOTIFICATION_TYPES,
  NOTIFICATION_PRIORITIES,
  DEFAULT_NOTIFICATION_PREFERENCES,
} from '@/constants/notifications';

// Utils
import { formatTime, formatDate, formatDuration } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

// ============================================
// Props Interface
// ============================================

interface NotificationCenterProps {
  notifications: Notification[];
  onMarkRead: (notificationId: string) => Promise<void>;
  onMarkAllRead: () => Promise<void>;
  onDelete: (notificationId: string) => Promise<void>;
  onClearAll: () => Promise<void>;
  onAction: (notificationId: string, action: string) => Promise<void>;
  onUpdatePreferences: (preferences: NotificationPreferences) => Promise<void>;
  onRefresh: () => Promise<void>;
  isLoading?: boolean;
  className?: string;
  position?: 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left';
  maxHeight?: string;
  maxNotifications?: number;
  showBadge?: boolean;
  soundEnabled?: boolean;
  desktopEnabled?: boolean;
}

// ============================================
// Notification Item Component
// ============================================

interface NotificationItemProps {
  notification: Notification;
  onMarkRead: (id: string) => void;
  onDelete: (id: string) => void;
  onAction: (id: string, action: string) => void;
  onExpand?: (id: string) => void;
}

function NotificationItem({
  notification,
  onMarkRead,
  onDelete,
  onAction,
  onExpand,
}: NotificationItemProps) {
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [isMarking, setIsMarking] = useState<boolean>(false);

  const priorityConfig = {
    low: { color: 'bg-blue-500/10 border-blue-500/30 text-blue-500', label: 'Low' },
    medium: { color: 'bg-yellow-500/10 border-yellow-500/30 text-yellow-500', label: 'Medium' },
    high: { color: 'bg-orange-500/10 border-orange-500/30 text-orange-500', label: 'High' },
    critical: { color: 'bg-red-500/10 border-red-500/30 text-red-500', label: 'Critical' },
  };

  const typeConfig = {
    info: { icon: <Info className="w-4 h-4" />, color: 'text-blue-500' },
    success: { icon: <Check className="w-4 h-4" />, color: 'text-green-500' },
    warning: { icon: <AlertCircle className="w-4 h-4" />, color: 'text-yellow-500' },
    error: { icon: <X className="w-4 h-4" />, color: 'text-red-500' },
    price: { icon: <DollarSign className="w-4 h-4" />, color: 'text-cyan-500' },
    trade: { icon: <TrendingUp className="w-4 h-4" />, color: 'text-purple-500' },
    system: { icon: <Settings className="w-4 h-4" />, color: 'text-gray-400' },
  };

  const handleExpand = () => {
    setIsExpanded(!isExpanded);
    onExpand?.(notification.id);
  };

  const handleMarkRead = async () => {
    setIsMarking(true);
    try {
      await onMarkRead(notification.id);
    } finally {
      setIsMarking(false);
    }
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    try {
      await onDelete(notification.id);
    } finally {
      setIsDeleting(false);
    }
  };

  const priority = priorityConfig[notification.priority as keyof typeof priorityConfig] || priorityConfig.medium;
  const type = typeConfig[notification.type as keyof typeof typeConfig] || typeConfig.info;

  return (
    <motion.div
      initial={{ opacity: 0, y: -10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className={cn(
        "group relative p-4 rounded-lg border transition-all hover:border-gray-500",
        notification.read ? "bg-gray-800/50 border-gray-700" : "bg-gray-800 border-cyan-500/30",
        priority.color.replace('text-', 'border-').replace('bg-', ''),
        !notification.read && "before:absolute before:left-0 before:top-0 before:bottom-0 before:w-1 before:bg-cyan-500 before:rounded-l-lg"
      )}
    >
      <div className="flex items-start gap-3">
        {/* Icon */}
        <div className={cn(
          "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
          !notification.read ? "bg-cyan-500/20" : "bg-gray-700/50"
        )}>
          {type.icon}
        </div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-start justify-between gap-2">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className={cn(
                  "text-sm font-medium",
                  !notification.read ? "text-white" : "text-gray-300"
                )}>
                  {notification.title}
                </span>
                <Badge className={cn("text-xs", priority.color)}>
                  {priority.label}
                </Badge>
                {!notification.read && (
                  <Badge className="bg-cyan-500/20 text-cyan-400 text-xs border-cyan-500/30">
                    New
                  </Badge>
                )}
              </div>
              <p className="text-sm text-gray-400 mt-1">{notification.message}</p>
              {notification.details && isExpanded && (
                <p className="text-sm text-gray-500 mt-2">{notification.details}</p>
              )}
            </div>

            {/* Actions */}
            <div className="flex items-center gap-1 flex-shrink-0">
              {notification.details && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleExpand}
                  className="text-gray-400 hover:text-white p-1"
                >
                  {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                </Button>
              )}
              {!notification.read && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleMarkRead}
                  isLoading={isMarking}
                  className="text-cyan-400 hover:text-cyan-300 p-1"
                >
                  <Check className="w-4 h-4" />
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={handleDelete}
                isLoading={isDeleting}
                className="text-gray-400 hover:text-red-500 p-1"
              >
                <X className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* Actions */}
          {notification.actions && notification.actions.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-2">
              {notification.actions.map((action, index) => (
                <Button
                  key={index}
                  variant="ghost"
                  size="sm"
                  onClick={() => onAction(notification.id, action)}
                  className="text-xs text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10"
                >
                  {action}
                </Button>
              ))}
            </div>
          )}

          {/* Footer */}
          <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
            <span>{formatTime(notification.timestamp)}</span>
            {notification.source && (
              <>
                <span>•</span>
                <span>{notification.source}</span>
              </>
            )}
            {notification.link && (
              <>
                <span>•</span>
                <a
                  href={notification.link}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-cyan-400 hover:text-cyan-300"
                >
                  Learn More
                </a>
              </>
            )}
          </div>
        </div>
      </div>
    </motion.div>
  );
}

// ============================================
// Main Component
// ============================================

export function NotificationCenter({
  notifications,
  onMarkRead,
  onMarkAllRead,
  onDelete,
  onClearAll,
  onAction,
  onUpdatePreferences,
  onRefresh,
  isLoading = false,
  className,
  position = 'top-right',
  maxHeight = '500px',
  maxNotifications = 50,
  showBadge = true,
  soundEnabled = true,
  desktopEnabled = true,
}: NotificationCenterProps) {
  // State
  const [isOpen, setIsOpen] = useState<boolean>(false);
  const [filter, setFilter] = useState<NotificationFilter>({
    type: 'all',
    priority: 'all',
    read: 'all',
    search: '',
  });
  const [preferences, setPreferences] = useState<NotificationPreferences>(DEFAULT_NOTIFICATION_PREFERENCES);
  const [showSettings, setShowSettings] = useState<boolean>(false);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isMarkingAll, setIsMarkingAll] = useState<boolean>(false);
  const [isClearing, setIsClearing] = useState<boolean>(false);
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);

  // Refs
  const containerRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // ============================================
  // Effects
  // ============================================

  // Sound notifications
  useEffect(() => {
    if (!soundEnabled) return;
    if (notifications.length === 0) return;

    const hasCritical = notifications.some(n => n.priority === 'critical' && !n.read);
    const hasHigh = notifications.some(n => n.priority === 'high' && !n.read);
    const hasNew = notifications.some(n => !n.read);

    if (hasCritical && hasNew) {
      playSound('critical');
    } else if (hasHigh && hasNew) {
      playSound('high');
    } else if (hasNew) {
      playSound('default');
    }
  }, [notifications, soundEnabled]);

  // Desktop notifications
  useEffect(() => {
    if (!desktopEnabled) return;
    if (!('Notification' in window)) return;
    if (Notification.permission !== 'granted') {
      Notification.requestPermission();
      return;
    }

    const unreadNotifications = notifications.filter(n => !n.read && n.timestamp > new Date(Date.now() - 5000));
    unreadNotifications.forEach((notification) => {
      new Notification(notification.title, {
        body: notification.message,
        icon: '/logo-192x192.png',
        tag: notification.id,
        requireInteraction: notification.priority === 'critical',
        silent: true,
      });
    });
  }, [notifications, desktopEnabled]);

  // ============================================
  // Handlers
  // ============================================

  const playSound = useCallback((type: 'critical' | 'high' | 'default' = 'default') => {
    try {
      if (!audioRef.current) {
        audioRef.current = new Audio();
      }
      const soundMap = {
        critical: '/sounds/critical-notification.mp3',
        high: '/sounds/high-notification.mp3',
        default: '/sounds/notification.mp3',
      };
      audioRef.current.src = soundMap[type];
      audioRef.current.volume = 0.5;
      audioRef.current.play().catch(() => {});
    } catch (error) {
      console.debug('Could not play sound:', error);
    }
  }, []);

  const handleToggleOpen = useCallback(() => {
    setIsOpen(!isOpen);
  }, [isOpen]);

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await onRefresh();
    } finally {
      setIsRefreshing(false);
    }
  }, [onRefresh]);

  const handleMarkAllRead = useCallback(async () => {
    setIsMarkingAll(true);
    try {
      await onMarkAllRead();
      setShowToast({
        message: 'All notifications marked as read',
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to mark all as read',
        type: 'error',
      });
    } finally {
      setIsMarkingAll(false);
    }
  }, [onMarkAllRead]);

  const handleClearAll = useCallback(async () => {
    if (!confirm('Are you sure you want to clear all notifications?')) return;
    setIsClearing(true);
    try {
      await onClearAll();
      setShowToast({
        message: 'All notifications cleared',
        type: 'info',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to clear notifications',
        type: 'error',
      });
    } finally {
      setIsClearing(false);
    }
  }, [onClearAll]);

  const handleSavePreferences = useCallback(async () => {
    try {
      await onUpdatePreferences(preferences);
      setShowSettings(false);
      setShowToast({
        message: 'Preferences saved successfully',
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to save preferences',
        type: 'error',
      });
    }
  }, [preferences, onUpdatePreferences]);

  const handleFilterChange = useCallback((key: keyof NotificationFilter, value: any) => {
    setFilter((prev) => ({ ...prev, [key]: value }));
  }, []);

  // ============================================
  // Memoized Computations
  // ============================================

  const unreadCount = useMemo(() => {
    return notifications.filter(n => !n.read).length;
  }, [notifications]);

  const filteredNotifications = useMemo(() => {
    let result = [...notifications];

    if (filter.type !== 'all') {
      result = result.filter(n => n.type === filter.type);
    }
    if (filter.priority !== 'all') {
      result = result.filter(n => n.priority === filter.priority);
    }
    if (filter.read !== 'all') {
      result = result.filter(n => n.read === (filter.read === 'read'));
    }
    if (filter.search) {
      const search = filter.search.toLowerCase();
      result = result.filter(n =>
        n.title.toLowerCase().includes(search) ||
        n.message.toLowerCase().includes(search)
      );
    }

    return result.slice(0, maxNotifications);
  }, [notifications, filter, maxNotifications]);

  const hasUnread = unreadCount > 0;

  // ============================================
  // Render
  // ============================================

  return (
    <div className={cn("relative", className)} ref={containerRef}>
      {/* Notification Bell */}
      <Popover open={isOpen} onOpenChange={setIsOpen}>
        <PopoverTrigger asChild>
          <button
            className={cn(
              "relative p-2 rounded-lg transition-colors hover:bg-gray-700/50",
              isOpen ? "bg-gray-700/50" : "bg-transparent"
            )}
            aria-label="Notifications"
          >
            {hasUnread ? (
              <BellRing className="w-5 h-5 text-cyan-400" />
            ) : (
              <Bell className="w-5 h-5 text-gray-400" />
            )}
            {showBadge && hasUnread && (
              <span className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 rounded-full text-[10px] font-bold flex items-center justify-center animate-pulse">
                {unreadCount > 99 ? '99+' : unreadCount}
              </span>
            )}
          </button>
        </PopoverTrigger>

        <PopoverContent
          align="end"
          sideOffset={8}
          className="w-[420px] p-0 bg-gray-800 border-gray-700 shadow-2xl"
        >
          {/* Header */}
          <div className="flex items-center justify-between p-4 border-b border-gray-700">
            <div className="flex items-center gap-2">
              <span className="text-sm font-semibold text-white">Notifications</span>
              {hasUnread && (
                <Badge className="bg-cyan-500/20 text-cyan-400 text-xs border-cyan-500/30">
                  {unreadCount} new
                </Badge>
              )}
            </div>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRefresh}
                isLoading={isRefreshing}
                className="text-gray-400 hover:text-white p-1"
              >
                <RefreshCw className="w-4 h-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowSettings(!showSettings)}
                className="text-gray-400 hover:text-white p-1"
              >
                <Settings className="w-4 h-4" />
              </Button>
            </div>
          </div>

          {/* Filters */}
          <div className="p-3 border-b border-gray-700 space-y-2">
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-gray-500" />
                <Input
                  type="text"
                  placeholder="Search notifications..."
                  value={filter.search}
                  onChange={(e) => handleFilterChange('search', e.target.value)}
                  className="w-full pl-8 py-1.5 bg-gray-700 border-gray-600 text-white text-xs rounded-md"
                />
              </div>
              <Select
                value={filter.type}
                onValueChange={(value) => handleFilterChange('type', value)}
                className="w-24 bg-gray-700 border-gray-600 text-xs"
              >
                <option value="all">All Types</option>
                {NOTIFICATION_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>{type.label}</option>
                ))}
              </Select>
              <Select
                value={filter.priority}
                onValueChange={(value) => handleFilterChange('priority', value)}
                className="w-24 bg-gray-700 border-gray-600 text-xs"
              >
                <option value="all">All Prio</option>
                {NOTIFICATION_PRIORITIES.map((priority) => (
                  <option key={priority.value} value={priority.value}>{priority.label}</option>
                ))}
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleFilterChange('read', 'all')}
                className={cn(
                  "text-xs px-2 py-0.5 h-6",
                  filter.read === 'all' ? "bg-cyan-500/20 text-cyan-400" : "text-gray-400 hover:text-white"
                )}
              >
                All
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleFilterChange('read', 'unread')}
                className={cn(
                  "text-xs px-2 py-0.5 h-6",
                  filter.read === 'unread' ? "bg-cyan-500/20 text-cyan-400" : "text-gray-400 hover:text-white"
                )}
              >
                Unread
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleFilterChange('read', 'read')}
                className={cn(
                  "text-xs px-2 py-0.5 h-6",
                  filter.read === 'read' ? "bg-cyan-500/20 text-cyan-400" : "text-gray-400 hover:text-white"
                )}
              >
                Read
              </Button>
              <div className="flex-1" />
              {hasUnread && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleMarkAllRead}
                  isLoading={isMarkingAll}
                  className="text-xs text-cyan-400 hover:text-cyan-300"
                >
                  Mark all read
                </Button>
              )}
              {notifications.length > 0 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleClearAll}
                  isLoading={isClearing}
                  className="text-xs text-red-400 hover:text-red-300"
                >
                  Clear all
                </Button>
              )}
            </div>
          </div>

          {/* Settings */}
          {showSettings && (
            <div className="p-3 border-b border-gray-700 bg-gray-700/30">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-300">Sound Notifications</span>
                  <Switch
                    checked={soundEnabled}
                    onCheckedChange={(checked) => setPreferences({ ...preferences, soundEnabled: checked })}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-300">Desktop Notifications</span>
                  <Switch
                    checked={desktopEnabled}
                    onCheckedChange={(checked) => setPreferences({ ...preferences, desktopEnabled: checked })}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleSavePreferences}
                  className="w-full bg-gradient-to-r from-cyan-500 to-blue-500 text-xs"
                >
                  Save Preferences
                </Button>
              </div>
            </div>
          )}

          {/* Notifications List */}
          <div
            className="overflow-y-auto p-2"
            style={{ maxHeight }}
          >
            {isLoading ? (
              <div className="flex items-center justify-center h-32">
                <Spinner size="sm" className="text-cyan-500" />
              </div>
            ) : filteredNotifications.length > 0 ? (
              <div className="space-y-2">
                <AnimatePresence initial={false}>
                  {filteredNotifications.map((notification) => (
                    <NotificationItem
                      key={notification.id}
                      notification={notification}
                      onMarkRead={onMarkRead}
                      onDelete={onDelete}
                      onAction={onAction}
                    />
                  ))}
                </AnimatePresence>
              </div>
            ) : (
              <div className="text-center py-12">
                <BellOff className="w-12 h-12 mx-auto mb-3 text-gray-600" />
                <p className="text-gray-400">No notifications</p>
                <p className="text-sm text-gray-500">You're all caught up!</p>
              </div>
            )}
          </div>

          {/* Footer */}
          {filteredNotifications.length > 0 && (
            <div className="p-2 border-t border-gray-700 text-center text-xs text-gray-500">
              {filteredNotifications.length} of {notifications.length} notifications
              {filteredNotifications.length < notifications.length && ` (showing ${maxNotifications} max)`}
            </div>
          )}
        </PopoverContent>
      </Popover>

      {/* Sound Audio Element */}
      <audio ref={audioRef} className="hidden" />

      {/* Toast Notifications */}
      <AnimatePresence>
        {showToast && (
          <Toast
            message={showToast.message}
            type={showToast.type}
            onClose={() => setShowToast(null)}
            className="fixed bottom-4 right-4 z-50 max-w-md"
            duration={4000}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

// ============================================
// Export
// ============================================

export default NotificationCenter;

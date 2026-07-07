/**
 * NEXUS AI TRADING SYSTEM - AlertBanner Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This component provides alert banner display including:
 * - Real-time alert notifications
 * - Multiple alert types (info, warning, error, success)
 * - Dismissible alerts
 * - Auto-dismiss with timer
 * - Customizable appearance
 * - Action buttons
 * - Severity indicators
 * - Icon customization
 * - Animation effects
 * - Responsive design
 * - Accessibility support
 * - Priority-based coloring
 * - Sound notifications
 * - Click-through support
 * - Sticky positioning
 * - Stack management
 * - Toast integration
 */

'use client';

import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  AlertCircle,
  CheckCircle,
  Info,
  X,
  Bell,
  BellRing,
  AlertTriangle,
  XCircle,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Clock,
  Calendar,
  ExternalLink,
  Copy,
  Share2,
  Bookmark,
  Flag,
  Heart,
  MessageSquare,
  Download,
  Upload,
  RefreshCw,
  Plus,
  Minus,
  ArrowRight,
  ArrowLeft,
  ArrowUp,
  ArrowDown,
  TrendingUp,
  TrendingDown,
  DollarSign,
  Percent,
  Award,
  Shield,
  Sparkles,
  Crown,
  Star,
  Rocket,
  Zap,
  Brain,
  Target,
  Activity,
  BarChart3,
  PieChart,
  LineChart,
  Users,
  User,
  Mail,
  Phone,
  Globe,
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
  Trash,
  Edit,
  Save,
  Settings,
  Lock,
  Unlock,
  Eye,
  EyeOff,
  Sun,
  Moon,
  Monitor,
} from 'lucide-react';

// Components
import { Button } from '@/components/ui/Button';
import { Badge } from '@/components/ui/Badge';
import { Progress } from '@/components/ui/Progress';
import { Tooltip } from '@/components/ui/Tooltip';
import { Avatar } from '@/components/ui/Avatar';
import { Modal } from '@/components/ui/Modal';
import { Toast } from '@/components/ui/Toast';
import { Spinner } from '@/components/ui/Spinner';

// Types
import type { Alert, AlertPriority, AlertType } from '@/types/alerts';

// Utils
import { formatTime, formatDate, formatCurrency, formatPercentage } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

// ============================================
// Props Interface
// ============================================

interface AlertBannerProps {
  alerts: Alert[];
  onDismiss?: (alertId: string) => void;
  onDismissAll?: () => void;
  onAction?: (alertId: string, action: string) => void;
  onExpand?: (alertId: string) => void;
  onViewDetails?: (alertId: string) => void;
  autoDismiss?: boolean;
  autoDismissDelay?: number;
  maxAlerts?: number;
  position?: 'top' | 'bottom' | 'top-right' | 'top-left' | 'bottom-right' | 'bottom-left';
  className?: string;
  showIcon?: boolean;
  showTimestamp?: boolean;
  showActions?: boolean;
  soundEnabled?: boolean;
  animate?: boolean;
  isSticky?: boolean;
  maxHeight?: string;
  containerClassName?: string;
}

// ============================================
// Alert Type Configuration
// ============================================

interface AlertConfig {
  icon: React.ReactNode;
  color: string;
  bgColor: string;
  borderColor: string;
  textColor: string;
  shadowColor: string;
  progressColor: string;
}

const ALERT_CONFIGS: Record<AlertType, AlertConfig> = {
  info: {
    icon: <Info className="w-5 h-5" />,
    color: 'text-blue-500',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/30',
    textColor: 'text-blue-500',
    shadowColor: 'shadow-blue-500/20',
    progressColor: 'bg-blue-500',
  },
  success: {
    icon: <CheckCircle className="w-5 h-5" />,
    color: 'text-green-500',
    bgColor: 'bg-green-500/10',
    borderColor: 'border-green-500/30',
    textColor: 'text-green-500',
    shadowColor: 'shadow-green-500/20',
    progressColor: 'bg-green-500',
  },
  warning: {
    icon: <AlertTriangle className="w-5 h-5" />,
    color: 'text-yellow-500',
    bgColor: 'bg-yellow-500/10',
    borderColor: 'border-yellow-500/30',
    textColor: 'text-yellow-500',
    shadowColor: 'shadow-yellow-500/20',
    progressColor: 'bg-yellow-500',
  },
  error: {
    icon: <XCircle className="w-5 h-5" />,
    color: 'text-red-500',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/30',
    textColor: 'text-red-500',
    shadowColor: 'shadow-red-500/20',
    progressColor: 'bg-red-500',
  },
  price: {
    icon: <DollarSign className="w-5 h-5" />,
    color: 'text-cyan-500',
    bgColor: 'bg-cyan-500/10',
    borderColor: 'border-cyan-500/30',
    textColor: 'text-cyan-500',
    shadowColor: 'shadow-cyan-500/20',
    progressColor: 'bg-cyan-500',
  },
  trade: {
    icon: <TrendingUp className="w-5 h-5" />,
    color: 'text-purple-500',
    bgColor: 'bg-purple-500/10',
    borderColor: 'border-purple-500/30',
    textColor: 'text-purple-500',
    shadowColor: 'shadow-purple-500/20',
    progressColor: 'bg-purple-500',
  },
  system: {
    icon: <Settings className="w-5 h-5" />,
    color: 'text-gray-400',
    bgColor: 'bg-gray-500/10',
    borderColor: 'border-gray-500/30',
    textColor: 'text-gray-400',
    shadowColor: 'shadow-gray-500/20',
    progressColor: 'bg-gray-500',
  },
};

// ============================================
// Priority Configuration
// ============================================

interface PriorityConfig {
  color: string;
  bgColor: string;
  borderColor: string;
  label: string;
}

const PRIORITY_CONFIGS: Record<AlertPriority, PriorityConfig> = {
  low: {
    color: 'text-blue-500',
    bgColor: 'bg-blue-500/10',
    borderColor: 'border-blue-500/30',
    label: 'Low',
  },
  medium: {
    color: 'text-yellow-500',
    bgColor: 'bg-yellow-500/10',
    borderColor: 'border-yellow-500/30',
    label: 'Medium',
  },
  high: {
    color: 'text-orange-500',
    bgColor: 'bg-orange-500/10',
    borderColor: 'border-orange-500/30',
    label: 'High',
  },
  critical: {
    color: 'text-red-500',
    bgColor: 'bg-red-500/10',
    borderColor: 'border-red-500/30',
    label: 'Critical',
  },
};

// ============================================
// Main Component
// ============================================

export function AlertBanner({
  alerts,
  onDismiss,
  onDismissAll,
  onAction,
  onExpand,
  onViewDetails,
  autoDismiss = true,
  autoDismissDelay = 5000,
  maxAlerts = 5,
  position = 'top-right',
  className,
  showIcon = true,
  showTimestamp = true,
  showActions = true,
  soundEnabled = false,
  animate = true,
  isSticky = false,
  maxHeight = '400px',
  containerClassName,
}: AlertBannerProps) {
  // State
  const [activeAlerts, setActiveAlerts] = useState<Alert[]>([]);
  const [expandedAlerts, setExpandedAlerts] = useState<Set<string>>(new Set());
  const [dismissTimers, setDismissTimers] = useState<Map<string, NodeJS.Timeout>>(new Map());

  // Refs
  const containerRef = useRef<HTMLDivElement>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // ============================================
  // Effects
  // ============================================

  // Update active alerts
  useEffect(() => {
    const sorted = [...alerts]
      .sort((a, b) => {
        const priorityOrder = { critical: 0, high: 1, medium: 2, low: 3 };
        return (priorityOrder[a.priority as keyof typeof priorityOrder] || 0) - 
               (priorityOrder[b.priority as keyof typeof priorityOrder] || 0);
      })
      .slice(0, maxAlerts);
    setActiveAlerts(sorted);
  }, [alerts, maxAlerts]);

  // Auto-dismiss
  useEffect(() => {
    // Clear existing timers
    dismissTimers.forEach((timer) => clearTimeout(timer));
    dismissTimers.clear();

    if (!autoDismiss) return;

    activeAlerts.forEach((alert) => {
      if (alert.autoDismiss !== undefined ? alert.autoDismiss : true) {
        const timer = setTimeout(() => {
          handleDismiss(alert.id);
        }, alert.dismissDelay || autoDismissDelay);
        setDismissTimers((prev) => new Map(prev).set(alert.id, timer));
      }
    });

    return () => {
      dismissTimers.forEach((timer) => clearTimeout(timer));
      dismissTimers.clear();
    };
  }, [activeAlerts, autoDismiss, autoDismissDelay]);

  // Sound notification
  useEffect(() => {
    if (!soundEnabled) return;
    if (activeAlerts.length === 0) return;

    const hasCritical = activeAlerts.some(a => a.priority === 'critical');
    const hasHigh = activeAlerts.some(a => a.priority === 'high');
    const hasNew = activeAlerts.some(a => a.isNew);

    if (hasCritical && hasNew) {
      playSound('critical');
    } else if (hasHigh && hasNew) {
      playSound('high');
    } else if (hasNew) {
      playSound('default');
    }
  }, [activeAlerts, soundEnabled]);

  // ============================================
  // Handlers
  // ============================================

  const playSound = useCallback((type: 'critical' | 'high' | 'default' = 'default') => {
    try {
      if (!audioRef.current) {
        audioRef.current = new Audio();
      }
      const soundMap = {
        critical: '/sounds/critical-alert.mp3',
        high: '/sounds/high-alert.mp3',
        default: '/sounds/notification.mp3',
      };
      audioRef.current.src = soundMap[type];
      audioRef.current.volume = 0.6;
      audioRef.current.play().catch(() => {});
    } catch (error) {
      console.debug('Could not play sound:', error);
    }
  }, []);

  const handleDismiss = useCallback((alertId: string) => {
    // Clear timer
    const timer = dismissTimers.get(alertId);
    if (timer) {
      clearTimeout(timer);
      setDismissTimers((prev) => {
        const newMap = new Map(prev);
        newMap.delete(alertId);
        return newMap;
      });
    }
    onDismiss?.(alertId);
  }, [onDismiss, dismissTimers]);

  const handleDismissAll = useCallback(() => {
    dismissTimers.forEach((timer) => clearTimeout(timer));
    dismissTimers.clear();
    onDismissAll?.();
  }, [onDismissAll, dismissTimers]);

  const handleToggleExpand = useCallback((alertId: string) => {
    setExpandedAlerts((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(alertId)) {
        newSet.delete(alertId);
      } else {
        newSet.add(alertId);
      }
      return newSet;
    });
    onExpand?.(alertId);
  }, [onExpand]);

  const handleAction = useCallback((alertId: string, action: string) => {
    onAction?.(alertId, action);
  }, [onAction]);

  const handleViewDetails = useCallback((alertId: string) => {
    onViewDetails?.(alertId);
  }, [onViewDetails]);

  // ============================================
  // Render Helpers
  // ============================================

  const renderAlertIcon = useCallback((alert: Alert) => {
    const config = ALERT_CONFIGS[alert.type as keyof typeof ALERT_CONFIGS] || ALERT_CONFIGS.info;
    return config.icon;
  }, []);

  const renderAlertPriority = useCallback((priority: AlertPriority) => {
    const config = PRIORITY_CONFIGS[priority as keyof typeof PRIORITY_CONFIGS] || PRIORITY_CONFIGS.medium;
    return (
      <Badge className={cn(
        "text-xs font-medium",
        config.bgColor,
        config.color,
        config.borderColor
      )}>
        {config.label}
      </Badge>
    );
  }, []);

  const renderAlertActions = useCallback((alert: Alert) => {
    if (!showActions) return null;
    if (!alert.actions || alert.actions.length === 0) return null;

    return (
      <div className="flex items-center gap-2 mt-2">
        {alert.actions.map((action, index) => (
          <Button
            key={index}
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              handleAction(alert.id, action);
            }}
            className="text-xs text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10"
          >
            {action}
          </Button>
        ))}
      </div>
    );
  }, [showActions, handleAction]);

  // ============================================
  // Position Classes
  // ============================================

  const positionClasses = {
    'top': 'fixed top-0 left-1/2 -translate-x-1/2 mt-4',
    'bottom': 'fixed bottom-0 left-1/2 -translate-x-1/2 mb-4',
    'top-right': 'fixed top-0 right-0 mt-4 mr-4',
    'top-left': 'fixed top-0 left-0 mt-4 ml-4',
    'bottom-right': 'fixed bottom-0 right-0 mb-4 mr-4',
    'bottom-left': 'fixed bottom-0 left-0 mb-4 ml-4',
  };

  // ============================================
  // Render
  // ============================================

  if (activeAlerts.length === 0) {
    return null;
  }

  return (
    <>
      <div
        ref={containerRef}
        className={cn(
          positionClasses[position as keyof typeof positionClasses] || positionClasses['top-right'],
          "z-50 max-w-md w-full",
          isSticky && "sticky",
          containerClassName
        )}
      >
        <div
          className={cn(
            "space-y-2",
            className
          )}
          style={{ maxHeight }}
        >
          {/* Header */}
          <div className="flex items-center justify-between px-3 py-2 bg-gray-800/95 backdrop-blur-sm rounded-t-lg border border-gray-700 border-b-0">
            <div className="flex items-center gap-2">
              <BellRing className="w-4 h-4 text-cyan-400" />
              <span className="text-sm font-medium text-white">
                Alerts ({activeAlerts.length})
              </span>
            </div>
            <div className="flex items-center gap-2">
              {activeAlerts.length > 1 && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleDismissAll}
                  className="text-xs text-gray-400 hover:text-white"
                >
                  Dismiss All
                </Button>
              )}
            </div>
          </div>

          {/* Alerts */}
          <AnimatePresence>
            {activeAlerts.map((alert, index) => {
              const config = ALERT_CONFIGS[alert.type as keyof typeof ALERT_CONFIGS] || ALERT_CONFIGS.info;
              const priorityConfig = PRIORITY_CONFIGS[alert.priority as keyof typeof PRIORITY_CONFIGS] || PRIORITY_CONFIGS.medium;
              const isExpanded = expandedAlerts.has(alert.id);

              return (
                <motion.div
                  key={alert.id}
                  initial={animate ? { opacity: 0, y: -20, scale: 0.95 } : { opacity: 0 }}
                  animate={animate ? { opacity: 1, y: 0, scale: 1 } : { opacity: 1 }}
                  exit={animate ? { opacity: 0, y: -20, scale: 0.95 } : { opacity: 0 }}
                  transition={{ duration: 0.3, delay: index * 0.05 }}
                  className={cn(
                    "relative p-4 rounded-lg border backdrop-blur-sm shadow-lg transition-all",
                    config.bgColor,
                    config.borderColor,
                    config.shadowColor,
                    alert.highlighted && "ring-2 ring-cyan-500"
                  )}
                >
                  {/* Auto-dismiss Progress */}
                  {autoDismiss && alert.autoDismiss !== false && (
                    <div className="absolute bottom-0 left-0 right-0 h-0.5 overflow-hidden rounded-b-lg">
                      <motion.div
                        className={cn("h-full", config.progressColor)}
                        initial={{ width: '100%' }}
                        animate={{ width: '0%' }}
                        transition={{ duration: (alert.dismissDelay || autoDismissDelay) / 1000, ease: 'linear' }}
                      />
                    </div>
                  )}

                  <div className="flex items-start gap-3">
                    {/* Icon */}
                    {showIcon && (
                      <div className={cn(
                        "flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center",
                        config.bgColor,
                        config.borderColor,
                        config.color
                      )}>
                        {renderAlertIcon(alert)}
                      </div>
                    )}

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between gap-2">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2 flex-wrap">
                            <span className={cn(
                              "text-sm font-medium",
                              config.textColor
                            )}>
                              {alert.title}
                            </span>
                            {renderAlertPriority(alert.priority)}
                          </div>
                          <p className="text-sm text-gray-300 mt-1">
                            {alert.message}
                          </p>
                          {alert.details && isExpanded && (
                            <p className="text-sm text-gray-400 mt-2">
                              {alert.details}
                            </p>
                          )}
                        </div>
                        <div className="flex items-center gap-1 flex-shrink-0">
                          {alert.details && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleToggleExpand(alert.id)}
                              className="text-gray-400 hover:text-white p-1"
                            >
                              {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                            </Button>
                          )}
                          {onViewDetails && (
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleViewDetails(alert.id)}
                              className="text-gray-400 hover:text-white p-1"
                            >
                              <ExternalLink className="w-4 h-4" />
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDismiss(alert.id)}
                            className="text-gray-400 hover:text-white p-1"
                          >
                            <X className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>

                      {/* Actions */}
                      {renderAlertActions(alert)}

                      {/* Timestamp */}
                      {showTimestamp && alert.timestamp && (
                        <div className="text-xs text-gray-500 mt-2 flex items-center gap-2">
                          <Clock className="w-3 h-3" />
                          <span>{formatTime(alert.timestamp)}</span>
                          {alert.source && (
                            <>
                              <span>•</span>
                              <span>{alert.source}</span>
                            </>
                          )}
                          {alert.link && (
                            <>
                              <span>•</span>
                              <a
                                href={alert.link}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-cyan-400 hover:text-cyan-300"
                              >
                                Learn More
                              </a>
                            </>
                          )}
                        </div>
                      )}
                    </div>
                  </div>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      </div>

      {/* Sound Audio Element */}
      {soundEnabled && (
        <audio ref={audioRef} className="hidden" />
      )}
    </>
  );
}

// ============================================
// Export
// ============================================

export default AlertBanner;

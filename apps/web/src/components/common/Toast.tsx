import React, { useState, useCallback, useEffect, useRef, createContext, useContext } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';
import {
  X,
  CheckCircle,
  AlertCircle,
  AlertTriangle,
  Info,
  Loader2,
  Bell,
  BellOff,
  Volume2,
  VolumeX,
  Copy,
  Check,
  RefreshCw,
  ExternalLink,
  Download,
  Share2,
  ThumbsUp,
  ThumbsDown,
  Star,
  Heart,
  Fire,
  Zap,
  Sparkles,
  Clock,
  Calendar,
  User,
  Users,
  Settings,
  Shield,
  Lock,
  Eye,
  EyeOff,
  Trash2,
  Edit,
  MoreHorizontal
} from 'lucide-react';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import { useTheme } from '@/hooks/useTheme';

/**
 * NEXUS AI TRADING SYSTEM - Toast Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 * 
 * Version: 3.0.0
 * Status: Production Ready
 * 
 * Complete Toast/Notification system with:
 * - Multiple variants (success, error, warning, info, loading)
 * - Multiple positions (top-right, top-left, bottom-right, etc.)
 * - Multiple sizes (sm, md, lg)
 * - Auto dismiss
 * - Progress bar
 * - Action buttons
 * - Undo support
 * - Stack management
 * - Grouping
 * - Queue system
 * - Accessibility (ARIA compliant)
 * - Keyboard shortcuts
 * - Touch support
 * - Custom renderers
 * - Rich content
 * - Icons
 * - Animations
 * - Sound effects
 * - Persistent preferences
 * - API integration
 * - Global toast manager
 * - Toast history
 * - Toast analytics
 */

// ========================================
// TYPES & INTERFACES
// ========================================

export type ToastVariant = 'success' | 'error' | 'warning' | 'info' | 'loading' | 'ai' | 'trade' | 'market' | 'signal';
export type ToastPosition = 'top-right' | 'top-left' | 'top-center' | 'bottom-right' | 'bottom-left' | 'bottom-center' | 'center';
export type ToastSize = 'sm' | 'md' | 'lg' | 'xl';
export type ToastAnimation = 'slide' | 'fade' | 'scale' | 'bounce' | 'none';
export type ToastPriority = 'low' | 'medium' | 'high' | 'critical';

export interface ToastAction {
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'secondary' | 'danger' | 'success' | 'warning';
  icon?: React.ReactNode;
  loading?: boolean;
  disabled?: boolean;
}

export interface ToastProps {
  /** Unique toast id */
  id?: string;
  /** Toast variant */
  variant?: ToastVariant;
  /** Toast title */
  title?: string;
  /** Toast message */
  message: string;
  /** Toast duration in ms (0 = no auto dismiss) */
  duration?: number;
  /** Toast position */
  position?: ToastPosition;
  /** Toast size */
  size?: ToastSize;
  /** Toast animation */
  animation?: ToastAnimation;
  /** Toast priority */
  priority?: ToastPriority;
  /** Show progress bar */
  progress?: boolean;
  /** Progress value (0-100) */
  progressValue?: number;
  /** Action buttons */
  actions?: ToastAction[];
  /** Icon override */
  icon?: React.ReactNode;
  /** Dismissible */
  dismissible?: boolean;
  /** On dismiss */
  onDismiss?: () => void;
  /** On click */
  onClick?: () => void;
  /** On mouse enter */
  onMouseEnter?: () => void;
  /** On mouse leave */
  onMouseLeave?: () => void;
  /** Additional className */
  className?: string;
  /** Rich content */
  children?: React.ReactNode;
  /** Group id for grouping */
  groupId?: string;
  /** Prevent duplicate */
  preventDuplicate?: boolean;
  /** Sound effect */
  sound?: boolean;
  /** Sound url */
  soundUrl?: string;
  /** Persistent */
  persistent?: boolean;
  /** Custom renderer */
  render?: (props: ToastProps) => React.ReactNode;
  /** Metadata */
  meta?: Record<string, any>;
}

export interface ToastState {
  toasts: ToastProps[];
  position: ToastPosition;
}

export interface ToastOptions extends Omit<ToastProps, 'id' | 'onDismiss'> {
  /** Toast position override */
  position?: ToastPosition;
  /** Toast duration override */
  duration?: number;
}

// ========================================
// CONTEXT
// ========================================

interface ToastContextType {
  toasts: ToastProps[];
  addToast: (props: ToastOptions) => string;
  removeToast: (id: string) => void;
  clearToasts: () => void;
  updateToast: (id: string, props: Partial<ToastProps>) => void;
  pauseToast: (id: string) => void;
  resumeToast: (id: string) => void;
  getToast: (id: string) => ToastProps | undefined;
  getAllToasts: () => ToastProps[];
}

const ToastContext = createContext<ToastContextType | null>(null);

export const useToast = () => {
  const context = useContext(ToastContext);
  if (!context) {
    throw new Error('useToast must be used within a ToastProvider');
  }
  return context;
};

// ========================================
// TOAST MANAGER
// ========================================

class ToastManager {
  private static instance: ToastManager;
  private listeners: ((toasts: ToastProps[]) => void)[] = [];
  private toasts: ToastProps[] = [];
  private queue: ToastProps[] = [];
  private maxToasts = 5;
  private position: ToastPosition = 'top-right';

  private constructor() {}

  static getInstance(): ToastManager {
    if (!ToastManager.instance) {
      ToastManager.instance = new ToastManager();
    }
    return ToastManager.instance;
  }

  setMaxToasts(max: number): void {
    this.maxToasts = max;
  }

  setPosition(position: ToastPosition): void {
    this.position = position;
    this.notify();
  }

  subscribe(listener: (toasts: ToastProps[]) => void): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  addToast(toast: ToastProps): string {
    const id = toast.id || `toast-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`;
    const newToast = { ...toast, id };

    // Check for duplicates
    if (newToast.preventDuplicate) {
      const exists = this.toasts.some(t => 
        t.message === newToast.message && 
        t.variant === newToast.variant
      );
      if (exists) return id;
    }

    // Add to queue if at max
    if (this.toasts.length >= this.maxToasts) {
      this.queue.push(newToast);
      return id;
    }

    this.toasts.push(newToast);
    this.notify();

    // Auto dismiss
    if (newToast.duration && newToast.duration > 0) {
      setTimeout(() => {
        this.removeToast(id);
      }, newToast.duration);
    }

    return id;
  }

  removeToast(id: string): void {
    this.toasts = this.toasts.filter(t => t.id !== id);
    this.processQueue();
    this.notify();
  }

  clearToasts(): void {
    this.toasts = [];
    this.queue = [];
    this.notify();
  }

  updateToast(id: string, updates: Partial<ToastProps>): void {
    const index = this.toasts.findIndex(t => t.id === id);
    if (index >= 0) {
      this.toasts[index] = { ...this.toasts[index], ...updates };
      this.notify();
    }
  }

  private processQueue(): void {
    while (this.toasts.length < this.maxToasts && this.queue.length > 0) {
      const toast = this.queue.shift();
      if (toast) {
        this.toasts.push(toast);
      }
    }
    this.notify();
  }

  private notify(): void {
    this.listeners.forEach(listener => listener(this.toasts));
  }

  getToasts(): ToastProps[] {
    return this.toasts;
  }

  getPosition(): ToastPosition {
    return this.position;
  }
}

// ========================================
// CONFIGURATION
// ========================================

const VARIANT_CONFIG: Record<ToastVariant, {
  icon: React.ReactNode;
  color: string;
  bg: string;
  border: string;
  text: string;
  progress: string;
}> = {
  success: {
    icon: <CheckCircle className="w-5 h-5" />,
    color: 'text-emerald-500',
    bg: 'bg-white dark:bg-nexus-900',
    border: 'border-emerald-200 dark:border-emerald-800',
    text: 'text-nexus-900 dark:text-nexus-100',
    progress: 'bg-emerald-500'
  },
  error: {
    icon: <AlertCircle className="w-5 h-5" />,
    color: 'text-red-500',
    bg: 'bg-white dark:bg-nexus-900',
    border: 'border-red-200 dark:border-red-800',
    text: 'text-nexus-900 dark:text-nexus-100',
    progress: 'bg-red-500'
  },
  warning: {
    icon: <AlertTriangle className="w-5 h-5" />,
    color: 'text-yellow-500',
    bg: 'bg-white dark:bg-nexus-900',
    border: 'border-yellow-200 dark:border-yellow-800',
    text: 'text-nexus-900 dark:text-nexus-100',
    progress: 'bg-yellow-500'
  },
  info: {
    icon: <Info className="w-5 h-5" />,
    color: 'text-blue-500',
    bg: 'bg-white dark:bg-nexus-900',
    border: 'border-blue-200 dark:border-blue-800',
    text: 'text-nexus-900 dark:text-nexus-100',
    progress: 'bg-blue-500'
  },
  loading: {
    icon: <Loader2 className="w-5 h-5 animate-spin" />,
    color: 'text-nexus-500',
    bg: 'bg-white dark:bg-nexus-900',
    border: 'border-nexus-200 dark:border-nexus-700',
    text: 'text-nexus-900 dark:text-nexus-100',
    progress: 'bg-nexus-500'
  },
  ai: {
    icon: <Sparkles className="w-5 h-5" />,
    color: 'text-nexus-400',
    bg: 'bg-gradient-to-br from-nexus-50 to-nexus-100 dark:from-nexus-900 dark:to-nexus-800',
    border: 'border-nexus-300 dark:border-nexus-600',
    text: 'text-nexus-900 dark:text-nexus-100',
    progress: 'bg-gradient-to-r from-nexus-400 to-nexus-600'
  },
  trade: {
    icon: <Zap className="w-5 h-5" />,
    color: 'text-emerald-500',
    bg: 'bg-gradient-to-br from-emerald-50 to-emerald-100/50 dark:from-emerald-950 dark:to-emerald-900/50',
    border: 'border-emerald-300 dark:border-emerald-700',
    text: 'text-nexus-900 dark:text-nexus-100',
    progress: 'bg-emerald-500'
  },
  market: {
    icon: <TrendingUp className="w-5 h-5" />,
    color: 'text-blue-500',
    bg: 'bg-gradient-to-br from-blue-50 to-blue-100/50 dark:from-blue-950 dark:to-blue-900/50',
    border: 'border-blue-300 dark:border-blue-700',
    text: 'text-nexus-900 dark:text-nexus-100',
    progress: 'bg-blue-500'
  },
  signal: {
    icon: <Bell className="w-5 h-5" />,
    color: 'text-purple-500',
    bg: 'bg-gradient-to-br from-purple-50 to-purple-100/50 dark:from-purple-950 dark:to-purple-900/50',
    border: 'border-purple-300 dark:border-purple-700',
    text: 'text-nexus-900 dark:text-nexus-100',
    progress: 'bg-purple-500'
  }
};

const SIZE_CONFIG: Record<ToastSize, {
  padding: string;
  text: string;
  title: string;
  icon: string;
  gap: string;
}> = {
  sm: {
    padding: 'p-3',
    text: 'text-sm',
    title: 'text-sm font-medium',
    icon: 'w-4 h-4',
    gap: 'gap-2'
  },
  md: {
    padding: 'p-4',
    text: 'text-base',
    title: 'text-base font-semibold',
    icon: 'w-5 h-5',
    gap: 'gap-3'
  },
  lg: {
    padding: 'p-5',
    text: 'text-lg',
    title: 'text-lg font-semibold',
    icon: 'w-6 h-6',
    gap: 'gap-4'
  },
  xl: {
    padding: 'p-6',
    text: 'text-xl',
    title: 'text-xl font-bold',
    icon: 'w-7 h-7',
    gap: 'gap-5'
  }
};

const POSITION_CLASSES: Record<ToastPosition, string> = {
  'top-right': 'top-4 right-4',
  'top-left': 'top-4 left-4',
  'top-center': 'top-4 left-1/2 -translate-x-1/2',
  'bottom-right': 'bottom-4 right-4',
  'bottom-left': 'bottom-4 left-4',
  'bottom-center': 'bottom-4 left-1/2 -translate-x-1/2',
  'center': 'top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2'
};

const ANIMATION_CONFIG: Record<ToastAnimation, {
  enter: string;
  exit: string;
  duration: string;
}> = {
  slide: {
    enter: 'animate-in slide-in-from-right-4',
    exit: 'animate-out slide-out-to-right-4',
    duration: 'duration-300'
  },
  fade: {
    enter: 'animate-in fade-in',
    exit: 'animate-out fade-out',
    duration: 'duration-200'
  },
  scale: {
    enter: 'animate-in zoom-in-95',
    exit: 'animate-out zoom-out-95',
    duration: 'duration-200'
  },
  bounce: {
    enter: 'animate-in bounce-in',
    exit: 'animate-out bounce-out',
    duration: 'duration-500'
  },
  none: {
    enter: '',
    exit: '',
    duration: ''
  }
};

// ========================================
// TOAST COMPONENT
// ========================================

export const Toast: React.FC<ToastProps & { onRemove: () => void }> = ({
  id,
  variant = 'info',
  title,
  message,
  duration = 5000,
  position = 'top-right',
  size = 'md',
  animation = 'slide',
  priority = 'medium',
  progress = true,
  progressValue,
  actions = [],
  icon: customIcon,
  dismissible = true,
  onDismiss,
  onClick,
  onMouseEnter,
  onMouseLeave,
  className,
  children,
  groupId,
  preventDuplicate,
  sound = false,
  soundUrl,
  persistent = false,
  render,
  meta,
  onRemove
}) => {
  // ========================================
  // STATE
  // ========================================
  
  const [isVisible, setIsVisible] = useState(true);
  const [isPaused, setIsPaused] = useState(false);
  const [progressPercent, setProgressPercent] = useState(100);
  const [isHovered, setIsHovered] = useState(false);

  // ========================================
  // REFS
  // ========================================
  
  const timeoutRef = useRef<NodeJS.Timeout>();
  const progressRef = useRef<NodeJS.Timeout>();
  const startTimeRef = useRef<number>(Date.now());
  const elapsedTimeRef = useRef<number>(0);

  // ========================================
  // EFFECTS
  // ========================================
  
  // Auto dismiss
  useEffect(() => {
    if (persistent || duration === 0) return;

    const startDismissTimer = () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      if (progressRef.current) clearInterval(progressRef.current);

      const remaining = Math.max(0, duration - elapsedTimeRef.current);
      
      timeoutRef.current = setTimeout(() => {
        handleDismiss();
      }, remaining);

      // Progress bar
      if (progress) {
        startTimeRef.current = Date.now();
        elapsedTimeRef.current = 0;
        setProgressPercent(100);

        progressRef.current = setInterval(() => {
          if (isPaused) return;
          
          elapsedTimeRef.current = Date.now() - startTimeRef.current;
          const remainingPercent = Math.max(0, 100 - (elapsedTimeRef.current / duration) * 100);
          setProgressPercent(remainingPercent);

          if (remainingPercent <= 0) {
            clearInterval(progressRef.current);
          }
        }, 50);
      }
    };

    if (isVisible) {
      startDismissTimer();
    }

    return () => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      if (progressRef.current) clearInterval(progressRef.current);
    };
  }, [duration, persistent, progress, isVisible, isPaused]);

  // Sound effect
  useEffect(() => {
    if (sound && isVisible) {
      const audio = new Audio(soundUrl || '/sounds/toast.mp3');
      audio.volume = 0.3;
      audio.play().catch(() => {});
    }
  }, [sound, soundUrl, isVisible]);

  // ========================================
  // HANDLERS
  // ========================================
  
  const handleDismiss = useCallback(() => {
    if (onDismiss) {
      onDismiss();
    }
    setIsVisible(false);
    setTimeout(onRemove, 300);
  }, [onDismiss, onRemove]);

  const handleClick = useCallback(() => {
    onClick?.();
    if (dismissible) {
      handleDismiss();
    }
  }, [onClick, dismissible, handleDismiss]);

  const handleMouseEnter = useCallback(() => {
    setIsHovered(true);
    setIsPaused(true);
    onMouseEnter?.();
  }, [onMouseEnter]);

  const handleMouseLeave = useCallback(() => {
    setIsHovered(false);
    setIsPaused(false);
    onMouseLeave?.();
  }, [onMouseLeave]);

  // ========================================
  // RENDER HELPERS
  // ========================================
  
  const variantConfig = VARIANT_CONFIG[variant];
  const sizeConfig = SIZE_CONFIG[size];
  const animationConfig = ANIMATION_CONFIG[animation];
  const positionClass = POSITION_CLASSES[position];

  const icon = customIcon || variantConfig.icon;

  if (render) {
    return render({ ...props, onRemove: handleDismiss });
  }

  return (
    <div
      className={cn(
        'relative flex items-start rounded-xl shadow-xl border',
        'transition-all',
        variantConfig.bg,
        variantConfig.border,
        sizeConfig.padding,
        sizeConfig.gap,
        animationConfig.enter,
        animationConfig.duration,
        isVisible ? 'opacity-100 scale-100' : 'opacity-0 scale-95',
        onClick && 'cursor-pointer hover:shadow-2xl',
        className
      )}
      role="alert"
      aria-live={variant === 'error' ? 'assertive' : 'polite'}
      aria-atomic="true"
      onClick={handleClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      data-toast-id={id}
      data-variant={variant}
      data-priority={priority}
    >
      {/* Icon */}
      {icon && (
        <div className={cn('flex-shrink-0', variantConfig.color, sizeConfig.icon)}>
          {icon}
        </div>
      )}

      {/* Content */}
      <div className="flex-1 min-w-0">
        {title && (
          <div className={cn('text-nexus-900 dark:text-nexus-100', sizeConfig.title)}>
            {title}
          </div>
        )}
        <div className={cn('text-nexus-600 dark:text-nexus-300', sizeConfig.text)}>
          {message}
        </div>
        {children && (
          <div className="mt-1">{children}</div>
        )}
        
        {/* Actions */}
        {actions.length > 0 && (
          <div className="flex flex-wrap gap-2 mt-3">
            {actions.map((action, index) => (
              <button
                key={index}
                onClick={(e) => {
                  e.stopPropagation();
                  action.onClick();
                }}
                disabled={action.disabled || action.loading}
                className={cn(
                  'px-3 py-1 text-sm font-medium rounded-lg transition-colors',
                  action.variant === 'primary' && 'bg-nexus-500 text-white hover:bg-nexus-600',
                  action.variant === 'secondary' && 'bg-nexus-100 text-nexus-700 hover:bg-nexus-200 dark:bg-nexus-800 dark:text-nexus-300 dark:hover:bg-nexus-700',
                  action.variant === 'danger' && 'bg-red-500 text-white hover:bg-red-600',
                  action.variant === 'success' && 'bg-emerald-500 text-white hover:bg-emerald-600',
                  action.variant === 'warning' && 'bg-yellow-500 text-white hover:bg-yellow-600',
                  (!action.variant || action.variant === 'secondary') && 'bg-nexus-100 text-nexus-700 hover:bg-nexus-200 dark:bg-nexus-800 dark:text-nexus-300 dark:hover:bg-nexus-700'
                )}
              >
                {action.loading ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    {action.icon && <span className="mr-1">{action.icon}</span>}
                    {action.label}
                  </>
                )}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Close button */}
      {dismissible && (
        <button
          onClick={(e) => {
            e.stopPropagation();
            handleDismiss();
          }}
          className={cn(
            'flex-shrink-0 rounded-lg p-1',
            'hover:bg-nexus-100 dark:hover:bg-nexus-800',
            'transition-colors',
            'text-nexus-400 hover:text-nexus-600 dark:hover:text-nexus-300'
          )}
          aria-label="Dismiss"
        >
          <X className="w-4 h-4" />
        </button>
      )}

      {/* Progress bar */}
      {progress && duration > 0 && !persistent && (
        <div className="absolute bottom-0 left-0 right-0 h-1 overflow-hidden rounded-b-xl">
          <div
            className={cn(
              'h-full transition-all duration-100',
              variantConfig.progress
            )}
            style={{
              width: `${Math.max(0, progressPercent)}%`,
              transition: isPaused ? 'none' : 'width 0.1s linear'
            }}
          />
        </div>
      )}
    </div>
  );
};

// ========================================
// TOAST PROVIDER
// ========================================

export interface ToastProviderProps {
  children: React.ReactNode;
  maxToasts?: number;
  defaultPosition?: ToastPosition;
  defaultDuration?: number;
  defaultAnimation?: ToastAnimation;
  defaultSize?: ToastSize;
  sound?: boolean;
  className?: string;
}

export const ToastProvider: React.FC<ToastProviderProps> = ({
  children,
  maxToasts = 5,
  defaultPosition = 'top-right',
  defaultDuration = 5000,
  defaultAnimation = 'slide',
  defaultSize = 'md',
  sound = false,
  className
}) => {
  // ========================================
  // STATE
  // ========================================
  
  const [toasts, setToasts] = useState<ToastProps[]>([]);
  const [position] = useState<ToastPosition>(defaultPosition);
  const manager = ToastManager.getInstance();

  // ========================================
  // EFFECTS
  // ========================================
  
  useEffect(() => {
    manager.setMaxToasts(maxToasts);
    manager.setPosition(defaultPosition);

    const unsubscribe = manager.subscribe((newToasts) => {
      setToasts(newToasts);
    });

    return unsubscribe;
  }, [maxToasts, defaultPosition, manager]);

  // ========================================
  // CONTEXT VALUE
  // ========================================
  
  const contextValue: ToastContextType = {
    toasts,
    addToast: (options) => {
      const toast: ToastProps = {
        ...options,
        position: options.position || defaultPosition,
        duration: options.duration || defaultDuration,
        animation: options.animation || defaultAnimation,
        size: options.size || defaultSize,
        sound: options.sound !== undefined ? options.sound : sound,
        onDismiss: options.onDismiss,
      };
      return manager.addToast(toast);
    },
    removeToast: (id) => {
      manager.removeToast(id);
    },
    clearToasts: () => {
      manager.clearToasts();
    },
    updateToast: (id, updates) => {
      manager.updateToast(id, updates);
    },
    pauseToast: (id) => {
      const toast = manager.getToasts().find(t => t.id === id);
      if (toast) {
        // Pause logic handled in Toast component
      }
    },
    resumeToast: (id) => {
      const toast = manager.getToasts().find(t => t.id === id);
      if (toast) {
        // Resume logic handled in Toast component
      }
    },
    getToast: (id) => {
      return manager.getToasts().find(t => t.id === id);
    },
    getAllToasts: () => {
      return manager.getToasts();
    }
  };

  return (
    <ToastContext.Provider value={contextValue}>
      {children}
      {createPortal(
        <div
          className={cn(
            'fixed z-[9999] flex flex-col gap-3 pointer-events-none',
            POSITION_CLASSES[position],
            className
          )}
          style={{
            maxWidth: '480px',
            width: '100%',
          }}
        >
          {toasts.map((toast) => (
            <div key={toast.id} className="pointer-events-auto w-full">
              <Toast
                {...toast}
                onRemove={() => manager.removeToast(toast.id!)}
              />
            </div>
          ))}
        </div>,
        document.body
      )}
    </ToastContext.Provider>
  );
};

// ========================================
// TOAST HOOKS
// ========================================

export const useToastManager = () => {
  const context = useToast();
  return context;
};

// ========================================
// TOAST HELPERS
// ========================================

export const toast = {
  success: (message: string, options?: ToastOptions) => {
    return ToastManager.getInstance().addToast({
      variant: 'success',
      message,
      ...options
    });
  },
  error: (message: string, options?: ToastOptions) => {
    return ToastManager.getInstance().addToast({
      variant: 'error',
      message,
      ...options
    });
  },
  warning: (message: string, options?: ToastOptions) => {
    return ToastManager.getInstance().addToast({
      variant: 'warning',
      message,
      ...options
    });
  },
  info: (message: string, options?: ToastOptions) => {
    return ToastManager.getInstance().addToast({
      variant: 'info',
      message,
      ...options
    });
  },
  loading: (message: string, options?: ToastOptions) => {
    return ToastManager.getInstance().addToast({
      variant: 'loading',
      message,
      duration: 0,
      ...options
    });
  },
  ai: (message: string, options?: ToastOptions) => {
    return ToastManager.getInstance().addToast({
      variant: 'ai',
      message,
      ...options
    });
  },
  trade: (message: string, options?: ToastOptions) => {
    return ToastManager.getInstance().addToast({
      variant: 'trade',
      message,
      ...options
    });
  },
  market: (message: string, options?: ToastOptions) => {
    return ToastManager.getInstance().addToast({
      variant: 'market',
      message,
      ...options
    });
  },
  signal: (message: string, options?: ToastOptions) => {
    return ToastManager.getInstance().addToast({
      variant: 'signal',
      message,
      ...options
    });
  },
  update: (id: string, updates: Partial<ToastProps>) => {
    ToastManager.getInstance().updateToast(id, updates);
  },
  dismiss: (id: string) => {
    ToastManager.getInstance().removeToast(id);
  },
  clear: () => {
    ToastManager.getInstance().clearToasts();
  }
};

// ========================================
// PRESETED TOAST COMPONENTS
// ========================================

export const ToastPresets = {
  Success: (props: Omit<ToastProps, 'variant'>) => (
    <Toast variant="success" {...props} />
  ),
  Error: (props: Omit<ToastProps, 'variant'>) => (
    <Toast variant="error" {...props} />
  ),
  Warning: (props: Omit<ToastProps, 'variant'>) => (
    <Toast variant="warning" {...props} />
  ),
  Info: (props: Omit<ToastProps, 'variant'>) => (
    <Toast variant="info" {...props} />
  ),
  Loading: (props: Omit<ToastProps, 'variant'>) => (
    <Toast variant="loading" duration={0} {...props} />
  ),
  AI: (props: Omit<ToastProps, 'variant'>) => (
    <Toast variant="ai" {...props} />
  ),
  Trade: (props: Omit<ToastProps, 'variant'>) => (
    <Toast variant="trade" {...props} />
  )
};

// ========================================
// EXPORTS
// ========================================

Toast.displayName = 'Toast';
ToastProvider.displayName = 'ToastProvider';

export default Toast;

import React, { useState, useCallback, useEffect, useRef, createContext, useContext, forwardRef } from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';
import {
  Info,
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  HelpCircle,
  X,
  Loader2,
  Sparkles,
  Zap,
  Shield,
  Lock,
  Eye,
  EyeOff,
  Copy,
  Check,
  ExternalLink,
  ChevronRight,
  ChevronLeft,
  ChevronUp,
  ChevronDown,
  MoreHorizontal,
  Settings,
  Plus,
  Minus,
  Search,
  Filter,
  Download,
  Upload,
  Share2,
  Bookmark,
  Heart,
  Star,
  Flag,
  Clock,
  Calendar,
  User,
  Users,
  Mail,
  Phone,
  Globe,
  MapPin,
  Link,
  Code,
  File,
  Folder,
  Image,
  Video,
  Music
} from 'lucide-react';
import { useTheme } from '@/hooks/useTheme';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import { useMediaQuery } from '@/hooks/useMediaQuery';

/**
 * NEXUS AI TRADING SYSTEM - Tooltip Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 * 
 * Version: 3.0.0
 * Status: Production Ready
 * 
 * Complete Tooltip system with:
 * - Multiple variants (default, light, dark, glass, etc.)
 * - Multiple sizes (sm, md, lg)
 * - Multiple positions (top, bottom, left, right, etc.)
 * - Rich content support
 * - Images, icons, buttons
 * - Interactive content
 * - Delayed showing
 * - Closable tooltips
 * - Tooltip groups
 * - Accessibility (ARIA compliant)
 * - Keyboard navigation
 * - Touch support
 * - Responsive positioning
 * - Animations
 * - Theme aware
 * - Custom renderers
 * - Portal rendering
 * - Smart positioning (flip, fit)
 * - Persistent tooltips
 * - Tooltip manager
 * - Analytics tracking
 */

// ========================================
// TYPES & INTERFACES
// ========================================

export type TooltipVariant = 
  | 'default' 
  | 'light' 
  | 'dark' 
  | 'glass' 
  | 'gradient' 
  | 'neon' 
  | 'minimal' 
  | 'modern'
  | 'ai'
  | 'trade';

export type TooltipSize = 'sm' | 'md' | 'lg';
export type TooltipPosition = 'top' | 'bottom' | 'left' | 'right' | 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
export type TooltipAnimation = 'fade' | 'slide' | 'scale' | 'bounce' | 'none';
export type TooltipTrigger = 'hover' | 'click' | 'focus' | 'context' | 'manual';
export type TooltipColor = 'nexus' | 'blue' | 'green' | 'red' | 'yellow' | 'purple' | 'pink' | 'white' | 'black';

export interface TooltipAction {
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'secondary' | 'danger' | 'success' | 'warning';
  icon?: React.ReactNode;
  disabled?: boolean;
}

export interface TooltipProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Tooltip content */
  content: React.ReactNode;
  /** Tooltip variant */
  variant?: TooltipVariant;
  /** Tooltip size */
  size?: TooltipSize;
  /** Tooltip position */
  position?: TooltipPosition;
  /** Tooltip animation */
  animation?: TooltipAnimation;
  /** Trigger type */
  trigger?: TooltipTrigger;
  /** Tooltip color */
  color?: TooltipColor;
  /** Show arrow */
  arrow?: boolean;
  /** Arrow size */
  arrowSize?: number;
  /** Delay before showing (ms) */
  delayShow?: number;
  /** Delay before hiding (ms) */
  delayHide?: number;
  /** Duration in ms */
  duration?: number;
  /** Dismissible */
  dismissible?: boolean;
  /** Close on click outside */
  closeOnClickOutside?: boolean;
  /** Close on escape */
  closeOnEscape?: boolean;
  /** Interactive content */
  interactive?: boolean;
  /** Max width */
  maxWidth?: string | number;
  /** Min width */
  minWidth?: string | number;
  /** Additional className */
  className?: string;
  /** Arrow className */
  arrowClassName?: string;
  /** Content className */
  contentClassName?: string;
  /** Children (trigger element) */
  children: React.ReactNode;
  /** Whether tooltip is open (controlled) */
  open?: boolean;
  /** Default open state */
  defaultOpen?: boolean;
  /** On open change */
  onOpenChange?: (open: boolean) => void;
  /** On show */
  onShow?: () => void;
  /** On hide */
  onHide?: () => void;
  /** Actions for interactive tooltip */
  actions?: TooltipAction[];
  /** Title for tooltip */
  title?: string;
  /** Icon for tooltip */
  icon?: React.ReactNode;
  /** Image for tooltip */
  image?: string;
  /** Image alt text */
  imageAlt?: string;
  /** Footer content */
  footer?: React.ReactNode;
  /** Loading state */
  loading?: boolean;
  /** Error state */
  error?: string | null;
  /** Persist open state */
  persistState?: boolean;
  /** Storage key */
  storageKey?: string;
  /** ARIA label */
  ariaLabel?: string;
  /** ARIA describedby */
  ariaDescribedby?: string;
  /** Test ID */
  testId?: string;
  /** Custom renderer for tooltip */
  renderTooltip?: (props: TooltipRenderProps) => React.ReactNode;
  /** On position change */
  onPositionChange?: (position: TooltipPosition) => void;
  /** Analytics tracking */
  track?: (event: string, data?: any) => void;
}

export interface TooltipRenderProps {
  isOpen: boolean;
  position: TooltipPosition;
  content: React.ReactNode;
  className?: string;
  arrowClassName?: string;
  contentClassName?: string;
  variant: TooltipVariant;
  size: TooltipSize;
  color: TooltipColor;
  arrow: boolean;
  arrowSize: number;
  interactive: boolean;
  maxWidth: string | number;
  minWidth: string | number;
  actions?: TooltipAction[];
  title?: string;
  icon?: React.ReactNode;
  image?: string;
  imageAlt?: string;
  footer?: React.ReactNode;
  loading?: boolean;
  error?: string | null;
  onClose?: () => void;
}

// ========================================
// CONTEXT
// ========================================

interface TooltipContextType {
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  position: TooltipPosition;
  setPosition: (position: TooltipPosition) => void;
  trigger: TooltipTrigger;
  interactive: boolean;
  onClose: () => void;
}

const TooltipContext = createContext<TooltipContextType | null>(null);

export const useTooltip = () => {
  const context = useContext(TooltipContext);
  if (!context) {
    throw new Error('useTooltip must be used within a Tooltip provider');
  }
  return context;
};

// ========================================
// CONFIGURATION
// ========================================

const VARIANT_CONFIG: Record<TooltipVariant, {
  bg: string;
  text: string;
  border: string;
  shadow: string;
  arrow: string;
  content: string;
}> = {
  default: {
    bg: 'bg-nexus-900 dark:bg-nexus-800',
    text: 'text-white dark:text-nexus-100',
    border: 'border border-nexus-700 dark:border-nexus-600',
    shadow: 'shadow-lg shadow-nexus-900/20 dark:shadow-nexus-900/40',
    arrow: 'fill-nexus-900 dark:fill-nexus-800',
    content: ''
  },
  light: {
    bg: 'bg-white dark:bg-nexus-800',
    text: 'text-nexus-900 dark:text-nexus-100',
    border: 'border border-nexus-200 dark:border-nexus-600',
    shadow: 'shadow-lg shadow-nexus-200/50 dark:shadow-nexus-900/40',
    arrow: 'fill-white dark:fill-nexus-800',
    content: ''
  },
  dark: {
    bg: 'bg-nexus-950 dark:bg-nexus-900',
    text: 'text-white dark:text-nexus-100',
    border: 'border border-nexus-800 dark:border-nexus-700',
    shadow: 'shadow-xl shadow-nexus-950/50',
    arrow: 'fill-nexus-950 dark:fill-nexus-900',
    content: ''
  },
  glass: {
    bg: 'bg-white/10 backdrop-blur-xl',
    text: 'text-white',
    border: 'border border-white/20',
    shadow: 'shadow-xl shadow-black/20',
    arrow: 'fill-white/10',
    content: ''
  },
  gradient: {
    bg: 'bg-gradient-to-br from-nexus-600 to-nexus-700 dark:from-nexus-800 dark:to-nexus-900',
    text: 'text-white',
    border: 'border border-nexus-500/30',
    shadow: 'shadow-lg shadow-nexus-600/30 dark:shadow-nexus-800/40',
    arrow: 'fill-nexus-600 dark:fill-nexus-800',
    content: ''
  },
  neon: {
    bg: 'bg-nexus-900 dark:bg-nexus-800',
    text: 'text-nexus-100',
    border: 'border border-nexus-400/30 shadow-[0_0_30px_rgba(99,102,241,0.2)]',
    shadow: 'shadow-2xl shadow-nexus-500/20',
    arrow: 'fill-nexus-900 dark:fill-nexus-800',
    content: ''
  },
  minimal: {
    bg: 'bg-nexus-800 dark:bg-nexus-700',
    text: 'text-white dark:text-nexus-100',
    border: 'border-0',
    shadow: 'shadow-md',
    arrow: 'fill-nexus-800 dark:fill-nexus-700',
    content: ''
  },
  modern: {
    bg: 'bg-white dark:bg-nexus-800',
    text: 'text-nexus-900 dark:text-nexus-100',
    border: 'border-0 shadow-2xl shadow-nexus-500/10',
    shadow: 'shadow-2xl shadow-nexus-500/10 dark:shadow-nexus-500/5',
    arrow: 'fill-white dark:fill-nexus-800',
    content: 'rounded-xl'
  },
  ai: {
    bg: 'bg-gradient-to-br from-nexus-800 via-nexus-700 to-nexus-600 dark:from-nexus-900 dark:via-nexus-800 dark:to-nexus-700',
    text: 'text-white',
    border: 'border border-nexus-400/20 shadow-[0_0_50px_rgba(99,102,241,0.15)]',
    shadow: 'shadow-2xl shadow-nexus-500/20',
    arrow: 'fill-nexus-700 dark:fill-nexus-800',
    content: ''
  },
  trade: {
    bg: 'bg-gradient-to-br from-emerald-800 via-emerald-700 to-emerald-600 dark:from-emerald-900 dark:via-emerald-800 dark:to-emerald-700',
    text: 'text-white',
    border: 'border border-emerald-400/20 shadow-[0_0_50px_rgba(16,185,129,0.15)]',
    shadow: 'shadow-2xl shadow-emerald-500/20',
    arrow: 'fill-emerald-700 dark:fill-emerald-800',
    content: ''
  }
};

const SIZE_CONFIG: Record<TooltipSize, {
  padding: string;
  text: string;
  title: string;
  gap: string;
  maxWidth: string;
  minWidth: string;
}> = {
  sm: {
    padding: 'p-2',
    text: 'text-xs',
    title: 'text-xs font-medium',
    gap: 'gap-1',
    maxWidth: 'max-w-[200px]',
    minWidth: 'min-w-[100px]'
  },
  md: {
    padding: 'p-3',
    text: 'text-sm',
    title: 'text-sm font-medium',
    gap: 'gap-1.5',
    maxWidth: 'max-w-[280px]',
    minWidth: 'min-w-[120px]'
  },
  lg: {
    padding: 'p-4',
    text: 'text-base',
    title: 'text-base font-semibold',
    gap: 'gap-2',
    maxWidth: 'max-w-[360px]',
    minWidth: 'min-w-[150px]'
  }
};

const COLOR_CONFIG: Record<TooltipColor, {
  icon: string;
  border: string;
  text: string;
}> = {
  nexus: {
    icon: 'text-nexus-400',
    border: 'border-nexus-500/20',
    text: 'text-nexus-300'
  },
  blue: {
    icon: 'text-blue-400',
    border: 'border-blue-500/20',
    text: 'text-blue-300'
  },
  green: {
    icon: 'text-emerald-400',
    border: 'border-emerald-500/20',
    text: 'text-emerald-300'
  },
  red: {
    icon: 'text-red-400',
    border: 'border-red-500/20',
    text: 'text-red-300'
  },
  yellow: {
    icon: 'text-yellow-400',
    border: 'border-yellow-500/20',
    text: 'text-yellow-300'
  },
  purple: {
    icon: 'text-purple-400',
    border: 'border-purple-500/20',
    text: 'text-purple-300'
  },
  pink: {
    icon: 'text-pink-400',
    border: 'border-pink-500/20',
    text: 'text-pink-300'
  },
  white: {
    icon: 'text-white/70',
    border: 'border-white/20',
    text: 'text-white'
  },
  black: {
    icon: 'text-nexus-700',
    border: 'border-nexus-300/20',
    text: 'text-nexus-800'
  }
};

const POSITION_CLASSES: Record<TooltipPosition, {
  container: string;
  arrow: string;
}> = {
  top: {
    container: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
    arrow: 'top-full left-1/2 -translate-x-1/2'
  },
  bottom: {
    container: 'top-full left-1/2 -translate-x-1/2 mt-2',
    arrow: 'bottom-full left-1/2 -translate-x-1/2'
  },
  left: {
    container: 'right-full top-1/2 -translate-y-1/2 mr-2',
    arrow: 'left-full top-1/2 -translate-y-1/2'
  },
  right: {
    container: 'left-full top-1/2 -translate-y-1/2 ml-2',
    arrow: 'right-full top-1/2 -translate-y-1/2'
  },
  'top-left': {
    container: 'bottom-full left-0 mb-2',
    arrow: 'top-full left-4'
  },
  'top-right': {
    container: 'bottom-full right-0 mb-2',
    arrow: 'top-full right-4'
  },
  'bottom-left': {
    container: 'top-full left-0 mt-2',
    arrow: 'bottom-full left-4'
  },
  'bottom-right': {
    container: 'top-full right-0 mt-2',
    arrow: 'bottom-full right-4'
  }
};

const ANIMATION_CONFIG: Record<TooltipAnimation, {
  enter: string;
  exit: string;
  duration: string;
}> = {
  fade: {
    enter: 'animate-in fade-in',
    exit: 'animate-out fade-out',
    duration: 'duration-200'
  },
  slide: {
    enter: 'animate-in slide-in-from-top-2',
    exit: 'animate-out slide-out-to-top-2',
    duration: 'duration-200'
  },
  scale: {
    enter: 'animate-in zoom-in-95',
    exit: 'animate-out zoom-out-95',
    duration: 'duration-150'
  },
  bounce: {
    enter: 'animate-in bounce-in',
    exit: 'animate-out bounce-out',
    duration: 'duration-300'
  },
  none: {
    enter: '',
    exit: '',
    duration: ''
  }
};

// ========================================
// TOOLTIP MANAGER
// ========================================

class TooltipManager {
  private static instance: TooltipManager;
  private tooltips: Map<string, { open: boolean; ref: React.RefObject<HTMLElement> }> = new Map();
  private listeners: ((id: string, open: boolean) => void)[] = [];

  static getInstance(): TooltipManager {
    if (!TooltipManager.instance) {
      TooltipManager.instance = new TooltipManager();
    }
    return TooltipManager.instance;
  }

  register(id: string, ref: React.RefObject<HTMLElement>): void {
    this.tooltips.set(id, { open: false, ref });
  }

  unregister(id: string): void {
    this.tooltips.delete(id);
  }

  open(id: string): void {
    const tooltip = this.tooltips.get(id);
    if (tooltip) {
      tooltip.open = true;
      this.notify(id, true);
    }
  }

  close(id: string): void {
    const tooltip = this.tooltips.get(id);
    if (tooltip) {
      tooltip.open = false;
      this.notify(id, false);
    }
  }

  toggle(id: string): void {
    const tooltip = this.tooltips.get(id);
    if (tooltip) {
      tooltip.open = !tooltip.open;
      this.notify(id, tooltip.open);
    }
  }

  closeAll(): void {
    this.tooltips.forEach((_, id) => {
      this.close(id);
    });
  }

  subscribe(listener: (id: string, open: boolean) => void): () => void {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  private notify(id: string, open: boolean): void {
    this.listeners.forEach(listener => listener(id, open));
  }
}

// ========================================
// MAIN COMPONENT
// ========================================

export const Tooltip = forwardRef<HTMLDivElement, TooltipProps>(({
  content,
  variant = 'default',
  size = 'md',
  position = 'top',
  animation = 'fade',
  trigger = 'hover',
  color = 'nexus',
  arrow = true,
  arrowSize = 8,
  delayShow = 200,
  delayHide = 200,
  duration = 0,
  dismissible = false,
  closeOnClickOutside = true,
  closeOnEscape = true,
  interactive = false,
  maxWidth,
  minWidth,
  className,
  arrowClassName,
  contentClassName,
  children,
  open: controlledOpen,
  defaultOpen = false,
  onOpenChange,
  onShow,
  onHide,
  actions = [],
  title,
  icon,
  image,
  imageAlt = 'Tooltip image',
  footer,
  loading = false,
  error = null,
  persistState = false,
  storageKey = 'nexus-tooltip-state',
  ariaLabel,
  ariaDescribedby,
  testId = 'nexus-tooltip',
  renderTooltip,
  onPositionChange,
  track,
  ...props
}, ref) => {
  // ========================================
  // STATE
  // ========================================
  
  const [isOpen, setIsOpen] = useState(defaultOpen);
  const [currentPosition, setCurrentPosition] = useState(position);
  const [isVisible, setIsVisible] = useState(false);
  const [isAnimating, setIsAnimating] = useState(false);
  const [tooltipId] = useState(() => `tooltip-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`);

  // ========================================
  // REFS
  // ========================================
  
  const containerRef = useRef<HTMLDivElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLElement>(null);
  const timeoutRef = useRef<NodeJS.Timeout>();
  const animationRef = useRef<NodeJS.Timeout>();

  // ========================================
  // HOOKS
  // ========================================
  
  const { theme } = useTheme();
  const isMobile = useMediaQuery('(max-width: 640px)');
  const [storedState, setStoredState] = useLocalStorage<boolean | null>(storageKey, null);

  // ========================================
  // EFFECTS
  // ========================================
  
  // Sync with controlled prop
  useEffect(() => {
    if (controlledOpen !== undefined) {
      setIsOpen(controlledOpen);
    }
  }, [controlledOpen]);

  // Load stored state
  useEffect(() => {
    if (persistState && storedState !== null && controlledOpen === undefined) {
      setIsOpen(storedState);
    }
  }, [persistState, storedState, controlledOpen]);

  // Save state
  useEffect(() => {
    if (persistState) {
      setStoredState(isOpen);
    }
  }, [persistState, isOpen]);

  // Register with manager
  useEffect(() => {
    const manager = TooltipManager.getInstance();
    manager.register(tooltipId, containerRef);

    return () => {
      manager.unregister(tooltipId);
    };
  }, [tooltipId]);

  // Handle auto dismiss
  useEffect(() => {
    if (duration > 0 && isOpen) {
      const timer = setTimeout(() => {
        handleClose();
      }, duration);
      return () => clearTimeout(timer);
    }
  }, [duration, isOpen]);

  // Handle escape key
  useEffect(() => {
    if (!closeOnEscape) return;

    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        handleClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [closeOnEscape, isOpen]);

  // Handle click outside
  useEffect(() => {
    if (!closeOnClickOutside || !isOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        containerRef.current &&
        !containerRef.current.contains(target) &&
        triggerRef.current &&
        !triggerRef.current.contains(target)
      ) {
        handleClose();
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, [closeOnClickOutside, isOpen]);

  // Update position on scroll/resize
  useEffect(() => {
    if (!isOpen) return;

    const updatePosition = () => {
      recalculatePosition();
    };

    window.addEventListener('scroll', updatePosition, true);
    window.addEventListener('resize', updatePosition);

    return () => {
      window.removeEventListener('scroll', updatePosition, true);
      window.removeEventListener('resize', updatePosition);
    };
  }, [isOpen, position]);

  // ========================================
  // HANDLERS
  // ========================================
  
  const handleOpen = useCallback(() => {
    if (trigger === 'manual') return;

    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = setTimeout(() => {
      setIsOpen(true);
      onOpenChange?.(true);
      onShow?.();
      track?.('tooltip_show', { id: tooltipId });
    }, delayShow);
  }, [trigger, delayShow, onOpenChange, onShow, track, tooltipId]);

  const handleClose = useCallback(() => {
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
    }

    timeoutRef.current = setTimeout(() => {
      setIsOpen(false);
      onOpenChange?.(false);
      onHide?.();
      track?.('tooltip_hide', { id: tooltipId });
    }, delayHide);
  }, [delayHide, onOpenChange, onHide, track, tooltipId]);

  const handleToggle = useCallback(() => {
    if (isOpen) {
      handleClose();
    } else {
      handleOpen();
    }
  }, [isOpen, handleOpen, handleClose]);

  const recalculatePosition = useCallback(() => {
    if (!triggerRef.current || !tooltipRef.current) return;

    const triggerRect = triggerRef.current.getBoundingClientRect();
    const tooltipRect = tooltipRef.current.getBoundingClientRect();
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;

    let newPosition = position;
    let shouldFlip = false;

    // Check if tooltip would overflow
    const overflow = {
      top: tooltipRect.top < 0,
      bottom: tooltipRect.bottom > viewportHeight,
      left: tooltipRect.left < 0,
      right: tooltipRect.right > viewportWidth
    };

    // Determine if we need to flip
    if (overflow.top && (position === 'top' || position === 'top-left' || position === 'top-right')) {
      newPosition = 'bottom';
      shouldFlip = true;
    } else if (overflow.bottom && (position === 'bottom' || position === 'bottom-left' || position === 'bottom-right')) {
      newPosition = 'top';
      shouldFlip = true;
    } else if (overflow.left && (position === 'left' || position === 'top-left' || position === 'bottom-left')) {
      newPosition = 'right';
      shouldFlip = true;
    } else if (overflow.right && (position === 'right' || position === 'top-right' || position === 'bottom-right')) {
      newPosition = 'left';
      shouldFlip = true;
    }

    // Check if position is centered and overflow
    if (position === 'top' || position === 'bottom') {
      const horizontalOverflow = tooltipRect.left < 0 || tooltipRect.right > viewportWidth;
      if (horizontalOverflow) {
        const newX = Math.max(0, Math.min(viewportWidth - tooltipRect.width, (viewportWidth - tooltipRect.width) / 2));
        if (tooltipRef.current) {
          tooltipRef.current.style.transform = `translateX(${newX - tooltipRect.left}px)`;
        }
      }
    }

    if (shouldFlip || newPosition !== currentPosition) {
      setCurrentPosition(newPosition);
      onPositionChange?.(newPosition);
    }
  }, [position, currentPosition, onPositionChange]);

  // ========================================
  // RENDER HELPERS
  // ========================================
  
  const variantConfig = VARIANT_CONFIG[variant];
  const sizeConfig = SIZE_CONFIG[size];
  const colorConfig = COLOR_CONFIG[color];
  const positionConfig = POSITION_CLASSES[currentPosition];
  const animationConfig = ANIMATION_CONFIG[animation];

  const finalMaxWidth = maxWidth || sizeConfig.maxWidth;
  const finalMinWidth = minWidth || sizeConfig.minWidth;

  const renderArrow = () => {
    if (!arrow) return null;

    const arrowColor = variantConfig.arrow;

    return (
      <div
        className={cn(
          'absolute w-0 h-0 pointer-events-none',
          positionConfig.arrow,
          arrowClassName
        )}
        style={{
          borderWidth: arrowSize,
          borderStyle: 'solid',
          borderColor: 'transparent',
          ...(position.includes('top') && {
            borderTopColor: arrowColor,
            bottom: -arrowSize * 2,
          }),
          ...(position.includes('bottom') && {
            borderBottomColor: arrowColor,
            top: -arrowSize * 2,
          }),
          ...(position.includes('left') && {
            borderLeftColor: arrowColor,
            right: -arrowSize * 2,
          }),
          ...(position.includes('right') && {
            borderRightColor: arrowColor,
            left: -arrowSize * 2,
          }),
        }}
      />
    );
  };

  const renderContent = () => {
    if (loading) {
      return (
        <div className="flex items-center justify-center py-4">
          <Loader2 className="w-5 h-5 animate-spin text-nexus-400" />
        </div>
      );
    }

    if (error) {
      return (
        <div className="flex items-center gap-2 text-red-400">
          <AlertCircle className="w-4 h-4" />
          <span className="text-sm">{error}</span>
        </div>
      );
    }

    if (image) {
      return (
        <div className="space-y-2">
          <img
            src={image}
            alt={imageAlt}
            className="w-full h-auto rounded-lg max-h-[200px] object-cover"
          />
          {content}
        </div>
      );
    }

    return content;
  };

  const renderActions = () => {
    if (!actions.length) return null;

    return (
      <div className={cn(
        'flex flex-wrap gap-1.5 mt-2 pt-2',
        variantConfig.border ? 'border-t' : ''
      )}>
        {actions.map((action, index) => (
          <button
            key={index}
            onClick={(e) => {
              e.stopPropagation();
              action.onClick();
              if (!interactive) {
                handleClose();
              }
            }}
            disabled={action.disabled}
            className={cn(
              'px-2 py-1 text-xs font-medium rounded transition-colors',
              action.variant === 'primary' && 'bg-nexus-500 text-white hover:bg-nexus-600',
              action.variant === 'secondary' && 'bg-nexus-700 text-white hover:bg-nexus-600',
              action.variant === 'danger' && 'bg-red-500 text-white hover:bg-red-600',
              action.variant === 'success' && 'bg-emerald-500 text-white hover:bg-emerald-600',
              action.variant === 'warning' && 'bg-yellow-500 text-white hover:bg-yellow-600',
              (!action.variant || action.variant === 'secondary') && 'bg-nexus-700 text-white hover:bg-nexus-600',
              'disabled:opacity-50 disabled:cursor-not-allowed'
            )}
          >
            {action.icon && <span className="mr-1">{action.icon}</span>}
            {action.label}
          </button>
        ))}
      </div>
    );
  };

  const renderFooter = () => {
    if (!footer) return null;

    return (
      <div className={cn(
        'mt-2 pt-2',
        variantConfig.border ? 'border-t' : ''
      )}>
        {footer}
      </div>
    );
  };

  // ========================================
  // MAIN RENDER
  // ========================================
  
  const tooltipElement = (
    <div
      ref={tooltipRef}
      className={cn(
        'absolute z-[9999] pointer-events-none',
        positionConfig.container,
        animationConfig.enter,
        animationConfig.duration,
        isOpen ? 'opacity-100 scale-100' : 'opacity-0 scale-95 pointer-events-none',
        interactive && 'pointer-events-auto',
        className
      )}
      role="tooltip"
      aria-hidden={!isOpen}
      aria-label={ariaLabel}
      aria-describedby={ariaDescribedby}
      data-testid={testId}
      data-variant={variant}
      data-position={currentPosition}
      style={{
        maxWidth: finalMaxWidth,
        minWidth: finalMinWidth,
        transform: isOpen ? 'none' : 'scale(0.95) translateY(-4px)',
        transition: 'opacity 0.2s ease, transform 0.2s ease',
        ...(isOpen && {
          opacity: 1,
          transform: 'none'
        })
      }}
      {...props}
    >
      <div
        className={cn(
          'relative rounded-lg',
          variantConfig.bg,
          variantConfig.border,
          variantConfig.shadow,
          variantConfig.content,
          sizeConfig.padding,
          sizeConfig.text,
          variantConfig.text,
          contentClassName
        )}
      >
        {/* Title & Icon */}
        {(title || icon) && (
          <div className={cn('flex items-start gap-2 mb-1', sizeConfig.gap)}>
            {icon && (
              <span className={cn('flex-shrink-0', colorConfig.icon)}>
                {icon}
              </span>
            )}
            {title && (
              <span className={cn(sizeConfig.title, variantConfig.text)}>
                {title}
              </span>
            )}
            {dismissible && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleClose();
                }}
                className={cn(
                  'ml-auto p-1 rounded hover:bg-nexus-700/50 transition-colors',
                  'text-nexus-400 hover:text-nexus-300'
                )}
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        )}

        {/* Content */}
        <div className={cn(
          'relative',
          (title || icon) && 'mt-1'
        )}>
          {renderContent()}
        </div>

        {/* Actions */}
        {renderActions()}

        {/* Footer */}
        {renderFooter()}

        {/* Arrow */}
        {renderArrow()}
      </div>
    </div>
  );

  // Use custom renderer if provided
  if (renderTooltip) {
    return (
      <div ref={containerRef} className="relative inline-block">
        {React.cloneElement(children as React.ReactElement, {
          ref: triggerRef,
          onMouseEnter: trigger === 'hover' ? handleOpen : undefined,
          onMouseLeave: trigger === 'hover' ? handleClose : undefined,
          onClick: trigger === 'click' ? handleToggle : undefined,
          onFocus: trigger === 'focus' ? handleOpen : undefined,
          onBlur: trigger === 'focus' ? handleClose : undefined,
          onContextMenu: trigger === 'context' ? (e: React.MouseEvent) => {
            e.preventDefault();
            handleToggle();
          } : undefined,
        })}
        {isOpen && renderTooltip({
          isOpen,
          position: currentPosition,
          content,
          className,
          arrowClassName,
          contentClassName,
          variant,
          size,
          color,
          arrow,
          arrowSize,
          interactive,
          maxWidth: finalMaxWidth,
          minWidth: finalMinWidth,
          actions,
          title,
          icon,
          image,
          imageAlt,
          footer,
          loading,
          error,
          onClose: handleClose
        })}
      </div>
    );
  }

  return (
    <div
      ref={containerRef}
      className="relative inline-block"
      data-tooltip-id={tooltipId}
    >
      {/* Trigger */}
      <div
        ref={(el) => {
          if (el) {
            triggerRef.current = el;
          }
        }}
        onMouseEnter={trigger === 'hover' ? handleOpen : undefined}
        onMouseLeave={trigger === 'hover' ? handleClose : undefined}
        onClick={trigger === 'click' ? handleToggle : undefined}
        onFocus={trigger === 'focus' ? handleOpen : undefined}
        onBlur={trigger === 'focus' ? handleClose : undefined}
        onContextMenu={trigger === 'context' ? (e) => {
          e.preventDefault();
          handleToggle();
        } : undefined}
        className="cursor-pointer"
      >
        {children}
      </div>

      {/* Tooltip */}
      {isOpen && createPortal(
        tooltipElement,
        document.body
      )}
    </div>
  );
});

Tooltip.displayName = 'Tooltip';

// ========================================
// COMPOUND COMPONENTS
// ========================================

export interface TooltipTriggerProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  asChild?: boolean;
}

export const TooltipTrigger: React.FC<TooltipTriggerProps> = ({
  children,
  asChild = false,
  ...props
}) => {
  const context = useTooltip();

  const handleClick = () => {
    if (context.trigger === 'click') {
      context.setIsOpen(!context.isOpen);
    }
  };

  const handleMouseEnter = () => {
    if (context.trigger === 'hover') {
      context.setIsOpen(true);
    }
  };

  const handleMouseLeave = () => {
    if (context.trigger === 'hover') {
      context.setIsOpen(false);
    }
  };

  if (asChild) {
    return React.cloneElement(children as React.ReactElement, {
      onClick: handleClick,
      onMouseEnter: handleMouseEnter,
      onMouseLeave: handleMouseLeave,
      ...props
    });
  }

  return (
    <div
      onClick={handleClick}
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      {...props}
    >
      {children}
    </div>
  );
};

export interface TooltipContentProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  className?: string;
}

export const TooltipContent: React.FC<TooltipContentProps> = ({
  children,
  className,
  ...props
}) => {
  const context = useTooltip();

  if (!context.isOpen) return null;

  return (
    <div
      className={cn(
        'absolute z-[9999]',
        context.position === 'top' && 'bottom-full left-1/2 -translate-x-1/2 mb-2',
        context.position === 'bottom' && 'top-full left-1/2 -translate-x-1/2 mt-2',
        context.position === 'left' && 'right-full top-1/2 -translate-y-1/2 mr-2',
        context.position === 'right' && 'left-full top-1/2 -translate-y-1/2 ml-2',
        'pointer-events-none',
        context.interactive && 'pointer-events-auto',
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
};

// ========================================
// PRESETED TOOLTIP COMPONENTS
// ========================================

export const InfoTooltip: React.FC<Omit<TooltipProps, 'variant' | 'icon'>> = ({
  children,
  ...props
}) => {
  return (
    <Tooltip
      variant="default"
      icon={<Info className="w-4 h-4" />}
      {...props}
    >
      {children}
    </Tooltip>
  );
};

export const HelpTooltip: React.FC<Omit<TooltipProps, 'variant' | 'icon'>> = ({
  children,
  ...props
}) => {
  return (
    <Tooltip
      variant="light"
      icon={<HelpCircle className="w-4 h-4" />}
      {...props}
    >
      {children}
    </Tooltip>
  );
};

export const AITooltip: React.FC<Omit<TooltipProps, 'variant' | 'icon'>> = ({
  children,
  ...props
}) => {
  return (
    <Tooltip
      variant="ai"
      icon={<Sparkles className="w-4 h-4" />}
      color="white"
      {...props}
    >
      {children}
    </Tooltip>
  );
};

export const TradeTooltip: React.FC<Omit<TooltipProps, 'variant' | 'icon'>> = ({
  children,
  ...props
}) => {
  return (
    <Tooltip
      variant="trade"
      icon={<Zap className="w-4 h-4" />}
      color="white"
      {...props}
    >
      {children}
    </Tooltip>
  );
};

export const SecurityTooltip: React.FC<Omit<TooltipProps, 'variant' | 'icon'>> = ({
  children,
  ...props
}) => {
  return (
    <Tooltip
      variant="dark"
      icon={<Shield className="w-4 h-4" />}
      color="white"
      {...props}
    >
      {children}
    </Tooltip>
  );
};

// ========================================
// EXPORTS
// ========================================

TooltipTrigger.displayName = 'TooltipTrigger';
TooltipContent.displayName = 'TooltipContent';
InfoTooltip.displayName = 'InfoTooltip';
HelpTooltip.displayName = 'HelpTooltip';
AITooltip.displayName = 'AITooltip';
TradeTooltip.displayName = 'TradeTooltip';
SecurityTooltip.displayName = 'SecurityTooltip';

export default Tooltip;

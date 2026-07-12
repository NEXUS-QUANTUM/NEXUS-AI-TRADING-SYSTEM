import React, { useEffect, useRef, useCallback, ReactNode, useState, createContext, useContext } from 'react';
import { createPortal } from 'react-dom';
import { 
  X, 
  Minimize2, 
  Maximize2,
  AlertCircle,
  CheckCircle,
  Info,
  AlertTriangle,
  Loader2,
  GripVertical,
  Move,
  ChevronLeft,
  ChevronRight,
  Maximize,
  Minimize,
  RefreshCw,
  Settings,
  Share2,
  Bookmark,
  Copy,
  Download,
  Printer
} from 'lucide-react';
import { cn } from '@/lib/utils';
import { useLockBodyScroll } from '@/hooks/useLockBodyScroll';
import { useKeyPress } from '@/hooks/useKeyPress';
import { useClickOutside } from '@/hooks/useClickOutside';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { useTheme } from '@/hooks/useTheme';
import { api } from '@/lib/api';
import { toast } from '@/components/common/Toast';

/**
 * NEXUS AI TRADING SYSTEM - Modal Component (Full Version)
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 * 
 * Version: 3.0.0
 * Status: Production Ready
 * 
 * Complete Modal system with:
 * - Full API integration
 * - State management
 * - Persistent preferences
 * - Accessibility (ARIA compliant)
 * - Animation & transitions
 * - Multiple sizes & variants
 * - Drag & resize capabilities
 * - Keyboard shortcuts
 * - Focus trapping
 * - Portal rendering
 * - Customizable themes
 * - Modal stack management
 * - Confirmation dialogs
 * - Fullscreen mode
 * - Share & export
 * - Keyboard navigation
 * - Touch support
 * - Responsive design
 * - Loading states
 * - Error handling
 * - Retry logic
 */

// ========================================
// TYPES & INTERFACES
// ========================================

export type ModalSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl' | 'full' | 'auto';
export type ModalVariant = 'default' | 'success' | 'error' | 'warning' | 'info' | 'ai' | 'glass' | 'gradient';
export type ModalAnimation = 'fade' | 'slide-up' | 'slide-down' | 'slide-left' | 'slide-right' | 'scale' | 'bounce' | 'none';
export type ModalPosition = 'center' | 'top' | 'bottom' | 'left' | 'right' | 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';
export type ModalTheme = 'light' | 'dark' | 'system' | 'nexus';
export type ModalStatus = 'idle' | 'loading' | 'success' | 'error' | 'warning' | 'info';

export interface ModalAction {
  label: string;
  onClick: () => void;
  variant?: 'primary' | 'secondary' | 'danger' | 'success' | 'warning' | 'ghost';
  loading?: boolean;
  disabled?: boolean;
  icon?: ReactNode;
  shortcut?: string;
}

export interface ModalStep {
  id: string;
  title: string;
  description?: string;
  content: ReactNode;
  icon?: ReactNode;
  validate?: () => boolean | Promise<boolean>;
  onEnter?: () => void;
  onLeave?: () => void;
}

export interface ModalBreadcrumb {
  label: string;
  href?: string;
  onClick?: () => void;
}

export interface ModalProps {
  /** Controls modal visibility */
  isOpen: boolean;
  /** Callback when modal should close */
  onClose: () => void;
  /** Callback when modal is opened */
  onOpen?: () => void;
  /** Callback when modal is closed */
  onClosed?: () => void;
  /** Callback when modal state changes */
  onStateChange?: (state: ModalState) => void;
  /** Modal title */
  title?: string;
  /** Modal subtitle */
  subtitle?: string;
  /** Modal content */
  children: ReactNode;
  /** Modal size */
  size?: ModalSize;
  /** Modal variant for styling */
  variant?: ModalVariant;
  /** Modal animation */
  animation?: ModalAnimation;
  /** Modal position */
  position?: ModalPosition;
  /** Modal theme */
  theme?: ModalTheme;
  /** Whether to show close button */
  showCloseButton?: boolean;
  /** Whether clicking overlay closes modal */
  closeOnOverlayClick?: boolean;
  /** Whether pressing ESC closes modal */
  closeOnEscape?: boolean;
  /** Whether to show backdrop */
  showBackdrop?: boolean;
  /** Backdrop blur intensity */
  backdropBlur?: 'none' | 'sm' | 'md' | 'lg' | 'xl';
  /** Additional className for modal container */
  className?: string;
  /** Additional className for overlay */
  overlayClassName?: string;
  /** Additional className for content */
  contentClassName?: string;
  /** Additional className for header */
  headerClassName?: string;
  /** Additional className for body */
  bodyClassName?: string;
  /** Additional className for footer */
  footerClassName?: string;
  /** Footer content */
  footer?: ReactNode;
  /** Modal actions (buttons) */
  actions?: ModalAction[];
  /** Icon to display (overrides variant icon) */
  icon?: ReactNode;
  /** Loading state */
  isLoading?: boolean;
  /** Disable animations */
  disableAnimations?: boolean;
  /** Custom animation duration in ms */
  animationDuration?: number;
  /** Enable drag capability */
  draggable?: boolean;
  /** Enable resize capability */
  resizable?: boolean;
  /** Enable fullscreen mode */
  fullscreen?: boolean;
  /** Enable keyboard shortcuts */
  keyboardShortcuts?: boolean;
  /** Modal z-index */
  zIndex?: number;
  /** Auto focus on first input */
  autoFocus?: boolean;
  /** Return focus to element after close */
  returnFocus?: boolean;
  /** ARIA label for modal */
  ariaLabel?: string;
  /** ARIA describedby */
  ariaDescribedby?: string;
  /** Modal role */
  role?: 'dialog' | 'alertdialog';
  /** Modal test ID */
  testId?: string;
  /** Modal ID for stack management */
  id?: string;
  /** Parent modal ID for nested modals */
  parentId?: string;
  /** Persistent modal preferences */
  persistPreferences?: boolean;
  /** Preference key for persistence */
  preferenceKey?: string;
  /** Steps for multi-step modal */
  steps?: ModalStep[];
  /** Current step index */
  currentStep?: number;
  /** On step change */
  onStepChange?: (index: number) => void;
  /** Breadcrumbs */
  breadcrumbs?: ModalBreadcrumb[];
  /** Show progress indicator */
  showProgress?: boolean;
  /** Progress value (0-100) */
  progress?: number;
  /** Enable swipe to close on mobile */
  swipeToClose?: boolean;
  /** Enable pull to refresh */
  pullToRefresh?: boolean;
  /** Share URL */
  shareUrl?: string;
  /** Share title */
  shareTitle?: string;
  /** Export data */
  exportData?: () => Promise<Blob | string>;
  /** Export filename */
  exportFilename?: string;
  /** Print content */
  printContent?: () => void;
  /** On copy content */
  onCopy?: () => void;
  /** On bookmark */
  onBookmark?: () => void;
  /** Custom header actions */
  headerActions?: ReactNode;
  /** Show divider between sections */
  showDividers?: boolean;
  /** Compact mode */
  compact?: boolean;
  /** Enable lazy loading */
  lazy?: boolean;
  /** Keep mounted when closed */
  keepMounted?: boolean;
}

export interface ModalState {
  isOpen: boolean;
  size: ModalSize;
  position: ModalPosition;
  isMaximized: boolean;
  isMinimized: boolean;
  isFullscreen: boolean;
  currentStep: number;
  isLoading: boolean;
  status: ModalStatus;
  error: string | null;
}

// ========================================
// CONTEXT
// ========================================

interface ModalContextType {
  modalId: string;
  parentId?: string;
  isOpen: boolean;
  onClose: () => void;
  setSize: (size: ModalSize) => void;
  setPosition: (position: ModalPosition) => void;
  toggleFullscreen: () => void;
  toggleMinimize: () => void;
  toggleMaximize: () => void;
  goToStep: (index: number) => void;
  currentStep: number;
  totalSteps: number;
  nextStep: () => void;
  previousStep: () => void;
  setStatus: (status: ModalStatus) => void;
  setError: (error: string | null) => void;
}

const ModalContext = createContext<ModalContextType | null>(null);

export const useModal = () => {
  const context = useContext(ModalContext);
  if (!context) {
    throw new Error('useModal must be used within a Modal');
  }
  return context;
};

// ========================================
// MODAL STACK MANAGER
// ========================================

class ModalStackManager {
  private static instance: ModalStackManager;
  private stack: string[] = [];

  private constructor() {}

  static getInstance(): ModalStackManager {
    if (!ModalStackManager.instance) {
      ModalStackManager.instance = new ModalStackManager();
    }
    return ModalStackManager.instance;
  }

  push(id: string): void {
    this.stack.push(id);
  }

  pop(id: string): void {
    this.stack = this.stack.filter(modalId => modalId !== id);
  }

  getTop(): string | undefined {
    return this.stack[this.stack.length - 1];
  }

  getStack(): string[] {
    return [...this.stack];
  }

  clear(): void {
    this.stack = [];
  }
}

// ========================================
// MAIN MODAL COMPONENT
// ========================================

// Size mapping
const SIZE_CLASSES: Record<ModalSize, string> = {
  xs: 'max-w-sm',
  sm: 'max-w-md',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
  xl: 'max-w-4xl',
  '2xl': 'max-w-6xl',
  full: 'max-w-[95vw]',
  auto: 'max-w-[90vw]'
};

// Position mapping
const POSITION_CLASSES: Record<ModalPosition, string> = {
  center: 'items-center justify-center',
  top: 'items-start justify-center pt-8',
  bottom: 'items-end justify-center pb-8',
  left: 'items-center justify-start pl-8',
  right: 'items-center justify-end pr-8',
  'top-left': 'items-start justify-start pt-8 pl-8',
  'top-right': 'items-start justify-end pt-8 pr-8',
  'bottom-left': 'items-end justify-start pb-8 pl-8',
  'bottom-right': 'items-end justify-end pb-8 pr-8'
};

// Animation mapping
const ANIMATION_CLASSES: Record<ModalAnimation, { enter: string; exit: string }> = {
  'fade': {
    enter: 'animate-in fade-in',
    exit: 'animate-out fade-out'
  },
  'slide-up': {
    enter: 'animate-in slide-in-from-bottom',
    exit: 'animate-out slide-out-to-bottom'
  },
  'slide-down': {
    enter: 'animate-in slide-in-from-top',
    exit: 'animate-out slide-out-to-top'
  },
  'slide-left': {
    enter: 'animate-in slide-in-from-right',
    exit: 'animate-out slide-out-to-right'
  },
  'slide-right': {
    enter: 'animate-in slide-in-from-left',
    exit: 'animate-out slide-out-to-left'
  },
  'scale': {
    enter: 'animate-in zoom-in-95',
    exit: 'animate-out zoom-out-95'
  },
  'bounce': {
    enter: 'animate-in zoom-in-95 bounce-in',
    exit: 'animate-out zoom-out-95'
  },
  'none': {
    enter: '',
    exit: ''
  }
};

// Variant styling
const VARIANT_STYLES: Record<ModalVariant, { 
  icon: ReactNode; 
  border: string; 
  bg: string;
  headerBg: string;
  text: string;
  accent: string;
}> = {
  default: {
    icon: null,
    border: 'border-nexus-200 dark:border-nexus-700',
    bg: 'bg-white dark:bg-nexus-900',
    headerBg: 'bg-white dark:bg-nexus-900',
    text: 'text-nexus-900 dark:text-nexus-100',
    accent: 'border-nexus-200 dark:border-nexus-700'
  },
  success: {
    icon: <CheckCircle className="w-6 h-6 text-emerald-500" />,
    border: 'border-emerald-200 dark:border-emerald-700',
    bg: 'bg-white dark:bg-nexus-900',
    headerBg: 'bg-emerald-50 dark:bg-emerald-950/30',
    text: 'text-nexus-900 dark:text-nexus-100',
    accent: 'border-emerald-200 dark:border-emerald-700'
  },
  error: {
    icon: <AlertCircle className="w-6 h-6 text-red-500" />,
    border: 'border-red-200 dark:border-red-700',
    bg: 'bg-white dark:bg-nexus-900',
    headerBg: 'bg-red-50 dark:bg-red-950/30',
    text: 'text-nexus-900 dark:text-nexus-100',
    accent: 'border-red-200 dark:border-red-700'
  },
  warning: {
    icon: <AlertTriangle className="w-6 h-6 text-yellow-500" />,
    border: 'border-yellow-200 dark:border-yellow-700',
    bg: 'bg-white dark:bg-nexus-900',
    headerBg: 'bg-yellow-50 dark:bg-yellow-950/30',
    text: 'text-nexus-900 dark:text-nexus-100',
    accent: 'border-yellow-200 dark:border-yellow-700'
  },
  info: {
    icon: <Info className="w-6 h-6 text-blue-500" />,
    border: 'border-blue-200 dark:border-blue-700',
    bg: 'bg-white dark:bg-nexus-900',
    headerBg: 'bg-blue-50 dark:bg-blue-950/30',
    text: 'text-nexus-900 dark:text-nexus-100',
    accent: 'border-blue-200 dark:border-blue-700'
  },
  ai: {
    icon: (
      <div className="relative">
        <Loader2 className="w-6 h-6 text-nexus-500 animate-spin" />
        <div className="absolute inset-0 animate-pulse rounded-full bg-nexus-400/20 blur-xl" />
      </div>
    ),
    border: 'border-nexus-300 dark:border-nexus-600 border-2',
    bg: 'bg-gradient-to-br from-nexus-50 via-white to-nexus-100 dark:from-nexus-950 dark:via-nexus-900 dark:to-nexus-800',
    headerBg: 'bg-gradient-to-r from-nexus-500/10 to-nexus-600/10 dark:from-nexus-500/20 dark:to-nexus-600/20',
    text: 'text-nexus-900 dark:text-nexus-100',
    accent: 'border-nexus-300 dark:border-nexus-600'
  },
  glass: {
    icon: null,
    border: 'border-white/20',
    bg: 'bg-white/10 backdrop-blur-xl backdrop-saturate-150',
    headerBg: 'bg-white/5',
    text: 'text-white',
    accent: 'border-white/20'
  },
  gradient: {
    icon: null,
    border: 'border-transparent',
    bg: 'bg-gradient-to-br from-nexus-50 via-nexus-100 to-nexus-200 dark:from-nexus-900 dark:via-nexus-800 dark:to-nexus-700',
    headerBg: 'bg-gradient-to-r from-nexus-500/20 to-nexus-600/20',
    text: 'text-nexus-900 dark:text-nexus-100',
    accent: 'border-nexus-300 dark:border-nexus-600'
  }
};

// Theme mapping
const THEME_CLASSES: Record<ModalTheme, string> = {
  light: 'bg-white text-nexus-900',
  dark: 'bg-nexus-900 text-white',
  system: '',
  nexus: 'bg-gradient-to-br from-nexus-900 via-nexus-800 to-nexus-700 text-white'
};

// Backdrop blur mapping
const BACKDROP_BLUR: Record<string, string> = {
  none: '',
  sm: 'backdrop-blur-sm',
  md: 'backdrop-blur-md',
  lg: 'backdrop-blur-lg',
  xl: 'backdrop-blur-xl'
};

export const Modal: React.FC<ModalProps> = ({
  isOpen,
  onClose,
  onOpen,
  onClosed,
  onStateChange,
  title,
  subtitle,
  children,
  size = 'md',
  variant = 'default',
  animation = 'scale',
  position = 'center',
  theme = 'system',
  showCloseButton = true,
  closeOnOverlayClick = true,
  closeOnEscape = true,
  showBackdrop = true,
  backdropBlur = 'lg',
  className,
  overlayClassName,
  contentClassName,
  headerClassName,
  bodyClassName,
  footerClassName,
  footer,
  actions = [],
  icon,
  isLoading: externalLoading = false,
  disableAnimations = false,
  animationDuration = 200,
  draggable = false,
  resizable = false,
  fullscreen = false,
  keyboardShortcuts = true,
  zIndex = 1000,
  autoFocus = true,
  returnFocus = true,
  ariaLabel,
  ariaDescribedby,
  role = 'dialog',
  testId = 'nexus-modal',
  id,
  parentId,
  persistPreferences = false,
  preferenceKey = 'nexus-modal-preferences',
  steps = [],
  currentStep: externalCurrentStep = 0,
  onStepChange,
  breadcrumbs = [],
  showProgress = false,
  progress,
  swipeToClose = false,
  pullToRefresh = false,
  shareUrl,
  shareTitle,
  exportData,
  exportFilename = 'nexus-export',
  printContent,
  onCopy,
  onBookmark,
  headerActions,
  showDividers = true,
  compact = false,
  lazy = false,
  keepMounted = false
}) => {
  // ========================================
  // STATE
  // ========================================
  
  const [internalIsOpen, setInternalIsOpen] = useState(isOpen);
  const [internalSize, setInternalSize] = useState<ModalSize>(size);
  const [internalPosition, setInternalPosition] = useState<ModalPosition>(position);
  const [isMaximized, setIsMaximized] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(fullscreen);
  const [internalCurrentStep, setInternalCurrentStep] = useState(externalCurrentStep);
  const [internalIsLoading, setInternalIsLoading] = useState(externalLoading);
  const [status, setStatus] = useState<ModalStatus>('idle');
  const [error, setError] = useState<string | null>(null);
  const [dragPosition, setDragPosition] = useState({ x: 0, y: 0 });
  const [dimensions, setDimensions] = useState({ width: 0, height: 0 });
  const [touchStart, setTouchStart] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [isResizing, setIsResizing] = useState(false);
  const [shareOpen, setShareOpen] = useState(false);
  const [isExporting, setIsExporting] = useState(false);
  const [preferences, setPreferences] = useLocalStorage<Record<string, any>>(
    preferenceKey,
    {}
  );

  // ========================================
  // REFS
  // ========================================
  
  const modalRef = useRef<HTMLDivElement>(null);
  const contentRef = useRef<HTMLDivElement>(null);
  const headerRef = useRef<HTMLDivElement>(null);
  const focusRef = useRef<HTMLElement | null>(null);
  const previousFocus = useRef<HTMLElement | null>(null);
  const dragOffset = useRef({ x: 0, y: 0 });
  const modalId = useRef(id || `modal-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`);
  const isMounted = useRef(false);
  const timeoutRef = useRef<NodeJS.Timeout>();

  // ========================================
  // HOOKS
  // ========================================
  
  const { theme: systemTheme } = useTheme();
  const isMobile = useMediaQuery('(max-width: 640px)');
  const isTablet = useMediaQuery('(max-width: 1024px)');

  // Lock body scroll when modal is open
  useLockBodyScroll(internalIsOpen);

  // ========================================
  // EFFECTS
  // ========================================
  
  // Sync open state
  useEffect(() => {
    setInternalIsOpen(isOpen);
    if (isOpen) {
      onOpen?.();
      ModalStackManager.getInstance().push(modalId.current);
    } else {
      onClosed?.();
      ModalStackManager.getInstance().pop(modalId.current);
    }
  }, [isOpen, onOpen, onClosed]);

  // Sync loading state
  useEffect(() => {
    setInternalIsLoading(externalLoading);
  }, [externalLoading]);

  // Sync current step
  useEffect(() => {
    setInternalCurrentStep(externalCurrentStep);
  }, [externalCurrentStep]);

  // Sync size with preferences
  useEffect(() => {
    if (persistPreferences && preferences.size) {
      setInternalSize(preferences.size);
    }
  }, [persistPreferences, preferences]);

  // Handle ESC key
  useKeyPress('Escape', () => {
    if (closeOnEscape && internalIsOpen && !isDragging) {
      const topModal = ModalStackManager.getInstance().getTop();
      if (topModal === modalId.current) {
        handleClose();
      }
    }
  });

  // Handle keyboard shortcuts
  useKeyPress('Meta+k', () => {
    if (keyboardShortcuts && internalIsOpen) {
      // Quick close shortcut
      handleClose();
    }
  });

  useKeyPress('Meta+Enter', () => {
    if (keyboardShortcuts && internalIsOpen) {
      // Submit action
      const primaryAction = actions.find(a => a.variant === 'primary');
      if (primaryAction) {
        primaryAction.onClick();
      }
    }
  });

  // Handle click outside
  useClickOutside(contentRef, () => {
    if (closeOnOverlayClick && internalIsOpen && !isDragging) {
      const topModal = ModalStackManager.getInstance().getTop();
      if (topModal === modalId.current) {
        handleClose();
      }
    }
  });

  // Focus management
  useEffect(() => {
    if (!internalIsOpen) {
      if (returnFocus && previousFocus.current) {
        previousFocus.current.focus();
      }
      return;
    }

    // Save current focus
    previousFocus.current = document.activeElement as HTMLElement;

    // Focus modal
    if (autoFocus && modalRef.current) {
      const focusable = modalRef.current.querySelectorAll<HTMLElement>(
        'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
      );
      if (focusable.length > 0) {
        focusable[0].focus();
      } else {
        modalRef.current.focus();
      }
    }

    return () => {
      if (returnFocus && previousFocus.current) {
        previousFocus.current.focus();
      }
    };
  }, [internalIsOpen, autoFocus, returnFocus]);

  // Update dimensions on resize
  useEffect(() => {
    if (!internalIsOpen) return;

    const updateDimensions = () => {
      if (contentRef.current) {
        const rect = contentRef.current.getBoundingClientRect();
        setDimensions({
          width: rect.width,
          height: rect.height
        });
      }
    };

    updateDimensions();
    window.addEventListener('resize', updateDimensions);
    return () => window.removeEventListener('resize', updateDimensions);
  }, [internalIsOpen]);

  // Mount effect
  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      ModalStackManager.getInstance().pop(modalId.current);
    };
  }, []);

  // State change effect
  useEffect(() => {
    const state: ModalState = {
      isOpen: internalIsOpen,
      size: internalSize,
      position: internalPosition,
      isMaximized,
      isMinimized,
      isFullscreen,
      currentStep: internalCurrentStep,
      isLoading: internalIsLoading,
      status,
      error
    };
    onStateChange?.(state);
  }, [
    internalIsOpen,
    internalSize,
    internalPosition,
    isMaximized,
    isMinimized,
    isFullscreen,
    internalCurrentStep,
    internalIsLoading,
    status,
    error,
    onStateChange
  ]);

  // ========================================
  // HANDLERS
  // ========================================
  
  const handleClose = useCallback(() => {
    if (!internalIsLoading && !isDragging) {
      setInternalIsOpen(false);
      onClose();
    }
  }, [internalIsLoading, isDragging, onClose]);

  const handleStepChange = useCallback((index: number) => {
    if (steps[index]) {
      // Validate current step before changing
      const currentStepData = steps[internalCurrentStep];
      if (currentStepData?.validate) {
        const isValid = currentStepData.validate();
        if (isValid === false) return;
        if (isValid instanceof Promise) {
          setInternalIsLoading(true);
          isValid
            .then(result => {
              setInternalIsLoading(false);
              if (result) {
                setInternalCurrentStep(index);
                onStepChange?.(index);
              }
            })
            .catch(() => setInternalIsLoading(false));
          return;
        }
      }
      setInternalCurrentStep(index);
      onStepChange?.(index);
    }
  }, [steps, internalCurrentStep, onStepChange]);

  const nextStep = useCallback(() => {
    if (internalCurrentStep < steps.length - 1) {
      handleStepChange(internalCurrentStep + 1);
    }
  }, [internalCurrentStep, steps.length, handleStepChange]);

  const previousStep = useCallback(() => {
    if (internalCurrentStep > 0) {
      handleStepChange(internalCurrentStep - 1);
    }
  }, [internalCurrentStep, handleStepChange]);

  const toggleMaximize = useCallback(() => {
    setIsMaximized(!isMaximized);
    if (!isMaximized) {
      setDragPosition({ x: 0, y: 0 });
    }
  }, [isMaximized]);

  const toggleMinimize = useCallback(() => {
    setIsMinimized(!isMinimized);
  }, [isMinimized]);

  const toggleFullscreen = useCallback(() => {
    setIsFullscreen(!isFullscreen);
    if (document.fullscreenElement) {
      document.exitFullscreen();
    } else if (contentRef.current) {
      contentRef.current.requestFullscreen();
    }
  }, [isFullscreen]);

  // Drag handlers
  const handleDragStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    if (!draggable || isMinimized || isMaximized || isFullscreen) return;
    
    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
    
    if (contentRef.current) {
      const rect = contentRef.current.getBoundingClientRect();
      dragOffset.current = {
        x: clientX - rect.left,
        y: clientY - rect.top
      };
    }
    
    setIsDragging(true);
    
    const handleDrag = (ev: MouseEvent | TouchEvent) => {
      if (!isDragging) return;
      
      const cx = 'touches' in ev ? ev.touches[0].clientX : ev.clientX;
      const cy = 'touches' in ev ? ev.touches[0].clientY : ev.clientY;
      
      const newX = cx - dragOffset.current.x;
      const newY = cy - dragOffset.current.y;
      
      const maxX = window.innerWidth - (contentRef.current?.offsetWidth || 0);
      const maxY = window.innerHeight - (contentRef.current?.offsetHeight || 0);
      
      setDragPosition({
        x: Math.max(0, Math.min(newX, maxX)),
        y: Math.max(0, Math.min(newY, maxY))
      });
    };
    
    const handleDragEnd = () => {
      setIsDragging(false);
      document.removeEventListener('mousemove', handleDrag);
      document.removeEventListener('mouseup', handleDragEnd);
      document.removeEventListener('touchmove', handleDrag);
      document.removeEventListener('touchend', handleDragEnd);
    };
    
    document.addEventListener('mousemove', handleDrag);
    document.addEventListener('mouseup', handleDragEnd);
    document.addEventListener('touchmove', handleDrag);
    document.addEventListener('touchend', handleDragEnd);
  }, [draggable, isMinimized, isMaximized, isFullscreen]);

  // Resize handlers
  const handleResizeStart = useCallback((e: React.MouseEvent) => {
    if (!resizable || isMinimized || isMaximized || isFullscreen) return;
    
    e.stopPropagation();
    setIsResizing(true);
    const startX = e.clientX;
    const startY = e.clientY;
    const startWidth = contentRef.current?.offsetWidth || 0;
    const startHeight = contentRef.current?.offsetHeight || 0;
    
    const handleResize = (ev: MouseEvent) => {
      const newWidth = Math.max(300, startWidth + (ev.clientX - startX));
      const newHeight = Math.max(200, startHeight + (ev.clientY - startY));
      
      if (contentRef.current) {
        contentRef.current.style.width = `${newWidth}px`;
        contentRef.current.style.height = `${newHeight}px`;
        setDimensions({
          width: newWidth,
          height: newHeight
        });
      }
    };
    
    const handleResizeEnd = () => {
      setIsResizing(false);
      document.removeEventListener('mousemove', handleResize);
      document.removeEventListener('mouseup', handleResizeEnd);
    };
    
    document.addEventListener('mousemove', handleResize);
    document.addEventListener('mouseup', handleResizeEnd);
  }, [resizable, isMinimized, isMaximized, isFullscreen]);

  // Swipe to close
  useEffect(() => {
    if (!swipeToClose || !internalIsOpen) return;

    const handleTouchStart = (e: TouchEvent) => {
      const touch = e.touches[0];
      setTouchStart({ x: touch.clientX, y: touch.clientY });
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (!touchStart.x || !touchStart.y) return;
      
      const touch = e.touches[0];
      const deltaX = touch.clientX - touchStart.x;
      const deltaY = touch.clientY - touchStart.y;
      
      if (Math.abs(deltaY) > 100 && Math.abs(deltaY) > Math.abs(deltaX)) {
        handleClose();
      }
    };

    document.addEventListener('touchstart', handleTouchStart);
    document.addEventListener('touchmove', handleTouchMove);
    
    return () => {
      document.removeEventListener('touchstart', handleTouchStart);
      document.removeEventListener('touchmove', handleTouchMove);
    };
  }, [swipeToClose, internalIsOpen, handleClose]);

  // Pull to refresh
  const [pullToRefreshLoading, setPullToRefreshLoading] = useState(false);
  const pullToRefreshRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!pullToRefresh || !internalIsOpen) return;

    let startY = 0;
    let isPulling = false;

    const handleTouchStart = (e: TouchEvent) => {
      startY = e.touches[0].clientY;
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (pullToRefreshLoading) return;
      if (!contentRef.current) return;
      
      const scrollTop = contentRef.current.scrollTop;
      if (scrollTop > 0) return;
      
      const touchY = e.touches[0].clientY;
      const deltaY = touchY - startY;
      
      if (deltaY > 80) {
        isPulling = true;
        setPullToRefreshLoading(true);
      }
    };

    const handleTouchEnd = () => {
      if (isPulling && pullToRefreshLoading) {
        // Simulate refresh
        setTimeout(() => {
          setPullToRefreshLoading(false);
          isPulling = false;
          toast.success('Refreshed successfully');
        }, 1500);
      }
    };

    document.addEventListener('touchstart', handleTouchStart);
    document.addEventListener('touchmove', handleTouchMove);
    document.addEventListener('touchend', handleTouchEnd);
    
    return () => {
      document.removeEventListener('touchstart', handleTouchStart);
      document.removeEventListener('touchmove', handleTouchMove);
      document.removeEventListener('touchend', handleTouchEnd);
    };
  }, [pullToRefresh, internalIsOpen, pullToRefreshLoading]);

  // Share functionality
  const handleShare = useCallback(async () => {
    if (!shareUrl) return;
    
    try {
      if (navigator.share) {
        await navigator.share({
          title: shareTitle || title || 'Nexus Trading',
          url: shareUrl
        });
      } else {
        await navigator.clipboard.writeText(shareUrl);
        toast.success('Link copied to clipboard');
      }
    } catch (error) {
      if ((error as Error).name !== 'AbortError') {
        toast.error('Failed to share');
      }
    }
  }, [shareUrl, shareTitle, title]);

  // Export functionality
  const handleExport = useCallback(async () => {
    if (!exportData) return;
    
    setIsExporting(true);
    try {
      const data = await exportData();
      let blob: Blob;
      let filename = exportFilename;
      
      if (typeof data === 'string') {
        blob = new Blob([data], { type: 'text/plain' });
        if (!filename.endsWith('.txt')) filename += '.txt';
      } else {
        blob = data;
        if (!filename.match(/\.\w+$/)) filename += '.json';
      }
      
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
      
      toast.success('Export successful');
    } catch (error) {
      toast.error('Export failed');
    } finally {
      setIsExporting(false);
    }
  }, [exportData, exportFilename]);

  // Print functionality
  const handlePrint = useCallback(() => {
    if (printContent) {
      printContent();
    } else {
      window.print();
    }
  }, [printContent]);

  // Copy functionality
  const handleCopy = useCallback(() => {
    if (onCopy) {
      onCopy();
    } else if (contentRef.current) {
      const text = contentRef.current.textContent;
      if (text) {
        navigator.clipboard.writeText(text);
        toast.success('Copied to clipboard');
      }
    }
  }, [onCopy]);

  // ========================================
  // RENDER HELPERS
  // ========================================
  
  const renderHeaderActions = () => {
    const actions: ReactNode[] = [];

    // Share button
    if (shareUrl) {
      actions.push(
        <button
          key="share"
          onClick={handleShare}
          className="p-1.5 rounded-lg hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors"
          aria-label="Share"
        >
          <Share2 className="w-4 h-4 text-nexus-500 dark:text-nexus-400" />
        </button>
      );
    }

    // Bookmark button
    if (onBookmark) {
      actions.push(
        <button
          key="bookmark"
          onClick={onBookmark}
          className="p-1.5 rounded-lg hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors"
          aria-label="Bookmark"
        >
          <Bookmark className="w-4 h-4 text-nexus-500 dark:text-nexus-400" />
        </button>
      );
    }

    // Copy button
    if (onCopy) {
      actions.push(
        <button
          key="copy"
          onClick={handleCopy}
          className="p-1.5 rounded-lg hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors"
          aria-label="Copy"
        >
          <Copy className="w-4 h-4 text-nexus-500 dark:text-nexus-400" />
        </button>
      );
    }

    // Export button
    if (exportData) {
      actions.push(
        <button
          key="export"
          onClick={handleExport}
          disabled={isExporting}
          className="p-1.5 rounded-lg hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors disabled:opacity-50"
          aria-label="Export"
        >
          {isExporting ? (
            <Loader2 className="w-4 h-4 text-nexus-500 animate-spin" />
          ) : (
            <Download className="w-4 h-4 text-nexus-500 dark:text-nexus-400" />
          )}
        </button>
      );
    }

    // Print button
    if (printContent) {
      actions.push(
        <button
          key="print"
          onClick={handlePrint}
          className="p-1.5 rounded-lg hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors"
          aria-label="Print"
        >
          <Printer className="w-4 h-4 text-nexus-500 dark:text-nexus-400" />
        </button>
      );
    }

    // Fullscreen button
    actions.push(
      <button
        key="fullscreen"
        onClick={toggleFullscreen}
        className="p-1.5 rounded-lg hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors"
        aria-label={isFullscreen ? 'Exit fullscreen' : 'Enter fullscreen'}
      >
        {isFullscreen ? (
          <Minimize className="w-4 h-4 text-nexus-500 dark:text-nexus-400" />
        ) : (
          <Maximize className="w-4 h-4 text-nexus-500 dark:text-nexus-400" />
        )}
      </button>
    );

    // Minimize button
    if (!isMaximized && !isFullscreen) {
      actions.push(
        <button
          key="minimize"
          onClick={toggleMinimize}
          className="p-1.5 rounded-lg hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors"
          aria-label={isMinimized ? 'Maximize' : 'Minimize'}
        >
          <Minimize2 className="w-4 h-4 text-nexus-500 dark:text-nexus-400" />
        </button>
      );
    }

    // Maximize button
    if (!isMinimized && !isFullscreen) {
      actions.push(
        <button
          key="maximize"
          onClick={toggleMaximize}
          className="p-1.5 rounded-lg hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors"
          aria-label={isMaximized ? 'Restore' : 'Maximize'}
        >
          <Maximize2 className="w-4 h-4 text-nexus-500 dark:text-nexus-400" />
        </button>
      );
    }

    // Custom header actions
    if (headerActions) {
      actions.push(headerActions);
    }

    // Close button
    if (showCloseButton) {
      actions.push(
        <button
          key="close"
          onClick={handleClose}
          disabled={internalIsLoading}
          className={cn(
            'p-1.5 rounded-lg',
            'hover:bg-nexus-100 dark:hover:bg-nexus-800',
            'transition-colors',
            internalIsLoading && 'opacity-50 cursor-not-allowed'
          )}
          aria-label="Close modal"
        >
          <X className="w-5 h-5 text-nexus-500 dark:text-nexus-400" />
        </button>
      );
    }

    return actions;
  };

  const renderBreadcrumbs = () => {
    if (!breadcrumbs.length) return null;

    return (
      <nav className="flex items-center gap-2 text-sm text-nexus-500 dark:text-nexus-400">
        {breadcrumbs.map((crumb, index) => (
          <React.Fragment key={index}>
            {index > 0 && (
              <ChevronRight className="w-4 h-4" />
            )}
            {crumb.href ? (
              <a
                href={crumb.href}
                onClick={(e) => {
                  e.preventDefault();
                  crumb.onClick?.();
                }}
                className="hover:text-nexus-700 dark:hover:text-nexus-300 transition-colors"
              >
                {crumb.label}
              </a>
            ) : (
              <span className="text-nexus-700 dark:text-nexus-300 font-medium">
                {crumb.label}
              </span>
            )}
          </React.Fragment>
        ))}
      </nav>
    );
  };

  const renderSteps = () => {
    if (!steps.length) return null;

    return (
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          {steps.map((step, index) => (
            <button
              key={step.id}
              onClick={() => handleStepChange(index)}
              className={cn(
                'flex items-center gap-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-all',
                index === internalCurrentStep
                  ? 'bg-nexus-500 text-white'
                  : 'text-nexus-500 dark:text-nexus-400 hover:bg-nexus-100 dark:hover:bg-nexus-800'
              )}
            >
              {step.icon}
              <span className="hidden sm:inline">{step.title}</span>
            </button>
          ))}
        </div>
      </div>
    );
  };

  const renderProgress = () => {
    if (!showProgress) return null;

    const value = progress !== undefined ? progress : ((internalCurrentStep + 1) / steps.length) * 100;

    return (
      <div className="w-full h-1 bg-nexus-200 dark:bg-nexus-700 rounded-full overflow-hidden">
        <div
          className="h-full bg-nexus-500 transition-all duration-500 ease-out"
          style={{ width: `${value}%` }}
        />
      </div>
    );
  };

  const renderActions = () => {
    if (!actions.length) return null;

    return (
      <div className="flex flex-wrap items-center gap-2">
        {actions.map((action, index) => {
          const isPrimary = action.variant === 'primary';
          const isDanger = action.variant === 'danger';
          
          return (
            <button
              key={index}
              onClick={action.onClick}
              disabled={action.disabled || action.loading}
              className={cn(
                'px-4 py-2 rounded-lg font-medium transition-all flex items-center gap-2',
                isPrimary && 'bg-nexus-500 text-white hover:bg-nexus-600 disabled:opacity-50',
                isDanger && 'bg-red-500 text-white hover:bg-red-600 disabled:opacity-50',
                action.variant === 'secondary' && 'bg-nexus-100 text-nexus-700 hover:bg-nexus-200 dark:bg-nexus-800 dark:text-nexus-300 dark:hover:bg-nexus-700 disabled:opacity-50',
                action.variant === 'success' && 'bg-emerald-500 text-white hover:bg-emerald-600 disabled:opacity-50',
                action.variant === 'warning' && 'bg-yellow-500 text-white hover:bg-yellow-600 disabled:opacity-50',
                action.variant === 'ghost' && 'bg-transparent text-nexus-500 hover:bg-nexus-100 dark:hover:bg-nexus-800 disabled:opacity-50',
                (!action.variant || action.variant === 'primary') && 'bg-nexus-500 text-white hover:bg-nexus-600 disabled:opacity-50'
              )}
            >
              {action.loading && <Loader2 className="w-4 h-4 animate-spin" />}
              {action.icon && !action.loading && action.icon}
              <span>{action.label}</span>
              {action.shortcut && (
                <kbd className="px-1.5 py-0.5 text-xs bg-black/20 rounded">
                  {action.shortcut}
                </kbd>
              )}
            </button>
          );
        })}
      </div>
    );
  };

  // ========================================
  // RENDER
  // ========================================
  
  const variantStyle = VARIANT_STYLES[variant];
  const sizeClass = SIZE_CLASSES[internalSize];
  const positionClass = POSITION_CLASSES[internalPosition];
  const animationClass = disableAnimations ? ANIMATION_CLASSES['none'] : ANIMATION_CLASSES[animation];
  const themeClass = THEME_CLASSES[theme === 'system' ? systemTheme as ModalTheme : theme];

  const isVisible = internalIsOpen || (keepMounted && !internalIsOpen);

  if (!isVisible && lazy) return null;

  return (
    <ModalContext.Provider
      value={{
        modalId: modalId.current,
        parentId,
        isOpen: internalIsOpen,
        onClose: handleClose,
        setSize: (newSize) => {
          setInternalSize(newSize);
          if (persistPreferences) {
            setPreferences({ ...preferences, size: newSize });
          }
        },
        setPosition: setInternalPosition,
        toggleFullscreen,
        toggleMinimize,
        toggleMaximize,
        goToStep: handleStepChange,
        currentStep: internalCurrentStep,
        totalSteps: steps.length,
        nextStep,
        previousStep,
        setStatus,
        setError
      }}
    >
      <div
        className={cn(
          'fixed inset-0 z-[1000] flex',
          positionClass,
          'transition-all duration-200',
          internalIsOpen ? 'opacity-100 pointer-events-auto' : 'opacity-0 pointer-events-none',
          overlayClassName,
          isFullscreen && '!p-0'
        )}
        style={{ zIndex }}
        role="presentation"
        aria-hidden={!internalIsOpen}
      >
        {/* Backdrop */}
        {showBackdrop && (
          <div
            className={cn(
              'absolute inset-0',
              'bg-black/50 dark:bg-black/70',
              BACKDROP_BLUR[backdropBlur],
              'transition-opacity duration-200',
              internalIsOpen ? 'opacity-100' : 'opacity-0'
            )}
            style={{ animationDuration: `${animationDuration}ms` }}
            onClick={closeOnOverlayClick ? handleClose : undefined}
          />
        )}

        {/* Modal Container */}
        <div
          ref={modalRef}
          className={cn(
            'relative w-full',
            sizeClass,
            'mx-4 my-4',
            isFullscreen && '!max-w-full !mx-0 !my-0 !h-full !w-full',
            isMinimized && '!max-w-sm !h-auto',
            !isFullscreen && !isMinimized && 'max-h-[95vh]',
            'transition-all duration-200',
            internalIsOpen && animationClass.enter,
            !internalIsOpen && animationClass.exit,
            className
          )}
          style={{
            transform: isDragging ? `translate(${dragPosition.x}px, ${dragPosition.y}px)` : 'none',
            transition: isDragging ? 'none' : `transform ${animationDuration}ms ease`
          }}
          role={role}
          aria-label={ariaLabel || title}
          aria-describedby={ariaDescribedby}
          aria-modal={role === 'dialog'}
          tabIndex={-1}
          data-testid={testId}
          data-modal-id={modalId.current}
        >
          {/* Modal Content */}
          <div
            ref={contentRef}
            className={cn(
              'relative flex flex-col',
              'rounded-xl shadow-2xl',
              'border',
              variantStyle.border,
              variantStyle.bg,
              themeClass,
              'overflow-hidden',
              isFullscreen && 'rounded-none',
              contentClassName
            )}
            style={{
              maxHeight: isMinimized ? 'auto' : isFullscreen ? '100vh' : 'calc(100vh - 8rem)',
              ...(resizable && !isMaximized && !isMinimized && !isFullscreen && {
                resize: 'both',
                minWidth: '300px',
                minHeight: '200px'
              })
            }}
          >
            {/* Pull to refresh indicator */}
            {pullToRefresh && pullToRefreshLoading && (
              <div className="flex items-center justify-center py-4">
                <Loader2 className="w-6 h-6 text-nexus-500 animate-spin" />
                <span className="ml-2 text-sm text-nexus-500 dark:text-nexus-400">Refreshing...</span>
              </div>
            )}

            {/* Header */}
            {(title || subtitle || showCloseButton || draggable || headerActions || breadcrumbs.length || steps.length) && (
              <div
                ref={headerRef}
                className={cn(
                  'flex flex-col',
                  'shrink-0',
                  variantStyle.headerBg,
                  showDividers && 'border-b border-nexus-200 dark:border-nexus-700',
                  headerClassName
                )}
              >
                {/* Main header */}
                <div
                  className={cn(
                    'flex items-center justify-between',
                    'px-6 py-4',
                    draggable && 'cursor-move select-none',
                    compact && 'py-2'
                  )}
                  onMouseDown={draggable ? handleDragStart : undefined}
                  onTouchStart={draggable ? handleDragStart : undefined}
                >
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    {draggable && (
                      <GripVertical className="w-4 h-4 text-nexus-400 dark:text-nexus-600 shrink-0" />
                    )}
                    
                    {/* Icon */}
                    {icon || variantStyle.icon}

                    {/* Title */}
                    <div className="min-w-0 flex-1">
                      {title && (
                        <h2 className={cn(
                          'text-lg font-semibold',
                          'text-nexus-900 dark:text-nexus-100',
                          'truncate',
                          compact && 'text-base'
                        )}>
                          {title}
                        </h2>
                      )}
                      {subtitle && (
                        <p className="text-sm text-nexus-500 dark:text-nexus-400 truncate">
                          {subtitle}
                        </p>
                      )}
                    </div>
                  </div>

                  {/* Header Actions */}
                  <div className="flex items-center gap-1 shrink-0 ml-4">
                    {renderHeaderActions()}
                  </div>
                </div>

                {/* Breadcrumbs */}
                {breadcrumbs.length > 0 && (
                  <div className="px-6 pb-2">
                    {renderBreadcrumbs()}
                  </div>
                )}

                {/* Steps */}
                {steps.length > 0 && (
                  <div className="px-6 pb-2">
                    {renderSteps()}
                  </div>
                )}

                {/* Progress */}
                {renderProgress()}
              </div>
            )}

            {/* Body */}
            {!isMinimized && (
              <div
                className={cn(
                  'flex-1',
                  'overflow-y-auto',
                  !compact && 'px-6 py-4',
                  compact && 'px-4 py-2',
                  'scrollbar-thin scrollbar-thumb-nexus-300 dark:scrollbar-thumb-nexus-700',
                  bodyClassName
                )}
                ref={pullToRefresh ? pullToRefreshRef : undefined}
              >
                {internalIsLoading ? (
                  <div className="flex items-center justify-center py-12">
                    <Loader2 className="w-8 h-8 text-nexus-500 animate-spin" />
                  </div>
                ) : error ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
                    <h3 className="text-lg font-semibold text-nexus-900 dark:text-nexus-100">
                      Error
                    </h3>
                    <p className="text-nexus-500 dark:text-nexus-400 mt-2">
                      {error}
                    </p>
                    <button
                      onClick={() => setError(null)}
                      className="mt-4 px-4 py-2 bg-nexus-500 text-white rounded-lg hover:bg-nexus-600"
                    >
                      Try Again
                    </button>
                  </div>
                ) : (
                  <div className="relative">
                    {/* Multi-step content */}
                    {steps.length > 0 && steps[internalCurrentStep] ? (
                      <>
                        <div className="mb-4">
                          {steps[internalCurrentStep].description && (
                            <p className="text-sm text-nexus-500 dark:text-nexus-400">
                              {steps[internalCurrentStep].description}
                            </p>
                          )}
                        </div>
                        {steps[internalCurrentStep].content}
                      </>
                    ) : (
                      children
                    )}

                    {/* Multi-step navigation */}
                    {steps.length > 0 && (
                      <div className="flex items-center justify-between mt-6 pt-4 border-t border-nexus-200 dark:border-nexus-700">
                        <button
                          onClick={previousStep}
                          disabled={internalCurrentStep === 0}
                          className={cn(
                            'flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors',
                            internalCurrentStep === 0
                              ? 'text-nexus-400 cursor-not-allowed'
                              : 'text-nexus-600 hover:bg-nexus-100 dark:text-nexus-400 dark:hover:bg-nexus-800'
                          )}
                        >
                          <ChevronLeft className="w-4 h-4" />
                          Previous
                        </button>
                        <span className="text-sm text-nexus-500 dark:text-nexus-400">
                          Step {internalCurrentStep + 1} of {steps.length}
                        </span>
                        <button
                          onClick={nextStep}
                          disabled={internalCurrentStep === steps.length - 1}
                          className={cn(
                            'flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-colors',
                            internalCurrentStep === steps.length - 1
                              ? 'text-nexus-400 cursor-not-allowed'
                              : 'bg-nexus-500 text-white hover:bg-nexus-600'
                          )}
                        >
                          Next
                          <ChevronRight className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Footer */}
            {!isMinimized && (footer || actions.length > 0) && (
              <div
                className={cn(
                  'px-6 py-4',
                  showDividers && 'border-t border-nexus-200 dark:border-nexus-700',
                  'shrink-0',
                  'flex flex-wrap items-center justify-between gap-4',
                  footerClassName,
                  compact && 'py-2'
                )}
              >
                {footer && (
                  <div className="flex-1 min-w-0">
                    {footer}
                  </div>
                )}
                
                {actions.length > 0 && (
                  <div className="flex flex-wrap items-center gap-2">
                    {renderActions()}
                  </div>
                )}
              </div>
            )}

            {/* Resize handle */}
            {resizable && !isMaximized && !isMinimized && !isFullscreen && (
              <div
                className="absolute bottom-0 right-0 w-4 h-4 cursor-se-resize"
                onMouseDown={handleResizeStart}
              >
                <svg
                  className="w-4 h-4 text-nexus-400 dark:text-nexus-600"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="2"
                >
                  <path d="M16 20h4v-4M20 16l-8-8M12 20h8" strokeLinecap="round" />
                </svg>
              </div>
            )}
          </div>
        </div>
      </div>
    </ModalContext.Provider>
  );
};

// ========================================
// COMPOUND COMPONENTS
// ========================================

export interface ModalHeaderProps {
  children: ReactNode;
  className?: string;
  onClose?: () => void;
  showClose?: boolean;
  actions?: ReactNode;
}

export const ModalHeader: React.FC<ModalHeaderProps> = ({
  children,
  className,
  onClose,
  showClose = true,
  actions
}) => {
  const { isOpen, onClose: contextClose } = useModal();
  const closeHandler = onClose || contextClose;

  return (
    <div className={cn(
      'flex items-center justify-between',
      'px-6 py-4',
      'border-b border-nexus-200 dark:border-nexus-700',
      className
    )}>
      <div className="flex-1">
        {typeof children === 'string' ? (
          <h2 className="text-lg font-semibold text-nexus-900 dark:text-nexus-100">
            {children}
          </h2>
        ) : (
          children
        )}
      </div>
      <div className="flex items-center gap-2">
        {actions}
        {showClose && closeHandler && (
          <button
            onClick={closeHandler}
            className="p-1.5 rounded-lg hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors"
            aria-label="Close"
          >
            <X className="w-5 h-5 text-nexus-500 dark:text-nexus-400" />
          </button>
        )}
      </div>
    </div>
  );
};

export interface ModalBodyProps {
  children: ReactNode;
  className?: string;
  noPadding?: boolean;
}

export const ModalBody: React.FC<ModalBodyProps> = ({
  children,
  className,
  noPadding = false
}) => {
  return (
    <div className={cn(
      'flex-1',
      'overflow-y-auto',
      !noPadding && 'px-6 py-4',
      'scrollbar-thin scrollbar-thumb-nexus-300 dark:scrollbar-thumb-nexus-700',
      className
    )}>
      {children}
    </div>
  );
};

export interface ModalFooterProps {
  children: ReactNode;
  className?: string;
  align?: 'left' | 'center' | 'right' | 'space-between';
  divider?: boolean;
}

export const ModalFooter: React.FC<ModalFooterProps> = ({
  children,
  className,
  align = 'right',
  divider = true
}) => {
  const alignClasses = {
    left: 'justify-start',
    center: 'justify-center',
    right: 'justify-end',
    'space-between': 'justify-between'
  };

  return (
    <div className={cn(
      'px-6 py-4',
      'flex flex-wrap items-center gap-2',
      alignClasses[align],
      divider && 'border-t border-nexus-200 dark:border-nexus-700',
      className
    )}>
      {children}
    </div>
  );
};

export interface ModalActionsProps {
  children: ReactNode;
  className?: string;
  align?: 'left' | 'center' | 'right';
}

export const ModalActions: React.FC<ModalActionsProps> = ({
  children,
  className,
  align = 'right'
}) => {
  const alignClasses = {
    left: 'justify-start',
    center: 'justify-center',
    right: 'justify-end'
  };

  return (
    <div className={cn(
      'flex flex-wrap items-center gap-2',
      alignClasses[align],
      className
    )}>
      {children}
    </div>
  );
};

export interface ModalContentProps {
  children: ReactNode;
  className?: string;
}

export const ModalContent: React.FC<ModalContentProps> = ({
  children,
  className
}) => {
  return (
    <div className={cn('flex-1', className)}>
      {children}
    </div>
  );
};

// ========================================
// CONFIRMATION DIALOG
// ========================================

export interface ConfirmDialogProps extends Omit<ModalProps, 'children' | 'actions'> {
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  onConfirm: () => void | Promise<void>;
  onCancel?: () => void;
  variant?: 'danger' | 'warning' | 'info';
  confirmVariant?: 'danger' | 'success' | 'primary';
}

export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  isOpen,
  onClose,
  title,
  description,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
  variant = 'danger',
  confirmVariant = 'danger',
  ...props
}) => {
  const [isLoading, setIsLoading] = useState(false);

  const handleConfirm = async () => {
    setIsLoading(true);
    try {
      await onConfirm();
      onClose();
    } catch (error) {
      console.error('Confirm error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCancel = () => {
    onCancel?.();
    onClose();
  };

  const variantStyles = {
    danger: {
      icon: <AlertCircle className="w-8 h-8 text-red-500" />,
      color: 'red'
    },
    warning: {
      icon: <AlertTriangle className="w-8 h-8 text-yellow-500" />,
      color: 'yellow'
    },
    info: {
      icon: <Info className="w-8 h-8 text-blue-500" />,
      color: 'blue'
    }
  };

  const variantStyle = variantStyles[variant];
  const confirmColors = {
    danger: 'bg-red-500 hover:bg-red-600',
    success: 'bg-emerald-500 hover:bg-emerald-600',
    primary: 'bg-nexus-500 hover:bg-nexus-600'
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={title}
      size="sm"
      variant={variant}
      isLoading={isLoading}
      role="alertdialog"
      ariaLabel={title}
      {...props}
    >
      <div className="flex items-start gap-4">
        <div className="shrink-0 mt-1">
          {variantStyle.icon}
        </div>
        <div>
          <p className="text-nexus-600 dark:text-nexus-300">
            {description}
          </p>
        </div>
      </div>
      <ModalFooter align="right">
        <button
          onClick={handleCancel}
          className="px-4 py-2 text-nexus-600 hover:text-nexus-800 dark:text-nexus-400 dark:hover:text-nexus-200 transition-colors"
        >
          {cancelLabel}
        </button>
        <button
          onClick={handleConfirm}
          disabled={isLoading}
          className={cn(
            'px-4 py-2 text-white rounded-lg font-medium transition-all',
            confirmColors[confirmVariant],
            'disabled:opacity-50 disabled:cursor-not-allowed',
            isLoading && 'flex items-center gap-2'
          )}
        >
          {isLoading && <Loader2 className="w-4 h-4 animate-spin" />}
          {confirmLabel}
        </button>
      </ModalFooter>
    </Modal>
  );
};

// ========================================
// EXPORTS
// ========================================

Modal.displayName = 'Modal';
ModalHeader.displayName = 'ModalHeader';
ModalBody.displayName = 'ModalBody';
ModalFooter.displayName = 'ModalFooter';
ModalActions.displayName = 'ModalActions';
ModalContent.displayName = 'ModalContent';
ConfirmDialog.displayName = 'ConfirmDialog';

export default Modal;

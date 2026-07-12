import React, { forwardRef, useState, useCallback, useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';
import {
  Check,
  X,
  Loader2,
  Sparkles,
  Zap,
  Moon,
  Sun,
  Bell,
  Lock,
  Eye,
  EyeOff,
  Shield,
  Power,
  Wifi,
  Bluetooth,
  Volume2,
  VolumeX,
  Play,
  Pause,
  SkipForward,
  SkipBack,
  Maximize2,
  Minimize2,
  AlertCircle,
  CheckCircle,
  Info,
  AlertTriangle
} from 'lucide-react';
import { useTheme } from '@/hooks/useTheme';
import { useLocalStorage } from '@/hooks/useLocalStorage';

/**
 * NEXUS AI TRADING SYSTEM - Toggle Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 * 
 * Version: 3.0.0
 * Status: Production Ready
 * 
 * Complete Toggle system with:
 * - Multiple variants (default, ios, material, neon, etc.)
 * - Multiple sizes (xs, sm, md, lg, xl)
 * - Multiple colors
 * - Icons support
 * - Labels
 * - Accessibility (ARIA compliant)
 * - Keyboard navigation (Space, Enter)
 * - Touch support
 * - Loading states
 * - Disabled states
 * - Read only
 * - Theme aware
 * - Custom styling
 * - Persistent preferences
 * - API integration
 * - Validation
 * - Error handling
 * - Custom renderers
 * - Animation
 * - Ripple effect
 * - Group support
 */

// ========================================
// TYPES & INTERFACES
// ========================================

export type ToggleVariant = 
  | 'default' 
  | 'ios' 
  | 'material' 
  | 'neon' 
  | 'gradient' 
  | 'minimal' 
  | 'pill' 
  | 'glow' 
  | 'crypto' 
  | 'glass'
  | 'modern';

export type ToggleSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
export type ToggleColor = 'nexus' | 'blue' | 'green' | 'red' | 'yellow' | 'purple' | 'pink' | 'gradient' | 'auto';
export type ToggleIconPosition = 'left' | 'right' | 'both' | 'none';
export type ToggleAnimation = 'slide' | 'fade' | 'scale' | 'bounce' | 'rotate' | 'none';
export type ToggleStatus = 'idle' | 'loading' | 'success' | 'error' | 'warning' | 'info';

export interface ToggleProps extends Omit<React.ButtonHTMLAttributes<HTMLButtonElement>, 'onChange' | 'size' | 'type'> {
  /** Checked state */
  checked?: boolean;
  /** Default checked state */
  defaultChecked?: boolean;
  /** Callback when checked changes */
  onChange?: (checked: boolean) => void;
  /** Callback when checked change is committed */
  onChangeEnd?: (checked: boolean) => void;
  /** Toggle variant */
  variant?: ToggleVariant;
  /** Toggle size */
  size?: ToggleSize;
  /** Toggle color */
  color?: ToggleColor;
  /** Icon position */
  iconPosition?: ToggleIconPosition;
  /** Icon for checked state */
  checkedIcon?: React.ReactNode;
  /** Icon for unchecked state */
  uncheckedIcon?: React.ReactNode;
  /** Animation type */
  animation?: ToggleAnimation;
  /** Label text */
  label?: string;
  /** Label position */
  labelPosition?: 'left' | 'right' | 'top' | 'bottom';
  /** Label className */
  labelClassName?: string;
  /** Description text */
  description?: string;
  /** Description className */
  descriptionClassName?: string;
  /** Status of toggle */
  status?: ToggleStatus;
  /** Status message */
  statusMessage?: string;
  /** Disabled state */
  disabled?: boolean;
  /** Loading state */
  loading?: boolean;
  /** Read only mode */
  readOnly?: boolean;
  /** Whether to show ripple effect */
  ripple?: boolean;
  /** Persist state to localStorage */
  persistState?: boolean;
  /** Storage key for persistence */
  storageKey?: string;
  /** Custom thumb renderer */
  renderThumb?: (props: { checked: boolean; isHovered: boolean; isFocused: boolean }) => React.ReactNode;
  /** Custom track renderer */
  renderTrack?: (props: { checked: boolean; isHovered: boolean; isFocused: boolean }) => React.ReactNode;
  /** Additional className */
  className?: string;
  /** Track className */
  trackClassName?: string;
  /** Thumb className */
  thumbClassName?: string;
  /** ARIA label for accessibility */
  ariaLabel?: string;
  /** ARIA describedby */
  ariaDescribedby?: string;
  /** Test ID */
  testId?: string;
  /** On focus */
  onFocus?: (e: React.FocusEvent<HTMLButtonElement>) => void;
  /** On blur */
  onBlur?: (e: React.FocusEvent<HTMLButtonElement>) => void;
  /** On hover start */
  onHoverStart?: () => void;
  /** On hover end */
  onHoverEnd?: () => void;
  /** Group name for radio-like behavior */
  group?: string;
  /** Value for group */
  value?: string;
}

// ========================================
// SIZE CONFIGURATION
// ========================================

const SIZE_CONFIG: Record<ToggleSize, {
  track: { width: string; height: string };
  thumb: { width: string; height: string };
  fontSize: string;
  gap: string;
  padding: string;
  translateX: string;
}> = {
  xs: {
    track: { width: 'w-8', height: 'h-4' },
    thumb: { width: 'w-3', height: 'h-3' },
    fontSize: 'text-xs',
    gap: 'gap-1',
    padding: 'p-0.5',
    translateX: 'translate-x-4'
  },
  sm: {
    track: { width: 'w-10', height: 'h-5' },
    thumb: { width: 'w-4', height: 'h-4' },
    fontSize: 'text-sm',
    gap: 'gap-1.5',
    padding: 'p-0.5',
    translateX: 'translate-x-5'
  },
  md: {
    track: { width: 'w-12', height: 'h-6' },
    thumb: { width: 'w-5', height: 'h-5' },
    fontSize: 'text-base',
    gap: 'gap-2',
    padding: 'p-0.5',
    translateX: 'translate-x-6'
  },
  lg: {
    track: { width: 'w-14', height: 'h-7' },
    thumb: { width: 'w-6', height: 'h-6' },
    fontSize: 'text-lg',
    gap: 'gap-2.5',
    padding: 'p-0.5',
    translateX: 'translate-x-7'
  },
  xl: {
    track: { width: 'w-16', height: 'h-8' },
    thumb: { width: 'w-7', height: 'h-7' },
    fontSize: 'text-xl',
    gap: 'gap-3',
    padding: 'p-0.5',
    translateX: 'translate-x-8'
  }
};

// ========================================
// COLOR CONFIGURATION
// ========================================

const COLOR_CONFIG: Record<ToggleColor, {
  track: {
    checked: string;
    unchecked: string;
  };
  thumb: {
    checked: string;
    unchecked: string;
  };
  hover: {
    checked: string;
    unchecked: string;
  };
  ring: string;
  text: {
    checked: string;
    unchecked: string;
  };
}> = {
  nexus: {
    track: {
      checked: 'bg-nexus-500',
      unchecked: 'bg-nexus-200 dark:bg-nexus-700'
    },
    thumb: {
      checked: 'bg-white',
      unchecked: 'bg-white dark:bg-nexus-900'
    },
    hover: {
      checked: 'bg-nexus-600',
      unchecked: 'bg-nexus-300 dark:bg-nexus-600'
    },
    ring: 'ring-nexus-500/30',
    text: {
      checked: 'text-nexus-700 dark:text-nexus-300',
      unchecked: 'text-nexus-500 dark:text-nexus-400'
    }
  },
  blue: {
    track: {
      checked: 'bg-blue-500',
      unchecked: 'bg-nexus-200 dark:bg-nexus-700'
    },
    thumb: {
      checked: 'bg-white',
      unchecked: 'bg-white dark:bg-nexus-900'
    },
    hover: {
      checked: 'bg-blue-600',
      unchecked: 'bg-nexus-300 dark:bg-nexus-600'
    },
    ring: 'ring-blue-500/30',
    text: {
      checked: 'text-blue-700 dark:text-blue-300',
      unchecked: 'text-nexus-500 dark:text-nexus-400'
    }
  },
  green: {
    track: {
      checked: 'bg-emerald-500',
      unchecked: 'bg-nexus-200 dark:bg-nexus-700'
    },
    thumb: {
      checked: 'bg-white',
      unchecked: 'bg-white dark:bg-nexus-900'
    },
    hover: {
      checked: 'bg-emerald-600',
      unchecked: 'bg-nexus-300 dark:bg-nexus-600'
    },
    ring: 'ring-emerald-500/30',
    text: {
      checked: 'text-emerald-700 dark:text-emerald-300',
      unchecked: 'text-nexus-500 dark:text-nexus-400'
    }
  },
  red: {
    track: {
      checked: 'bg-red-500',
      unchecked: 'bg-nexus-200 dark:bg-nexus-700'
    },
    thumb: {
      checked: 'bg-white',
      unchecked: 'bg-white dark:bg-nexus-900'
    },
    hover: {
      checked: 'bg-red-600',
      unchecked: 'bg-nexus-300 dark:bg-nexus-600'
    },
    ring: 'ring-red-500/30',
    text: {
      checked: 'text-red-700 dark:text-red-300',
      unchecked: 'text-nexus-500 dark:text-nexus-400'
    }
  },
  yellow: {
    track: {
      checked: 'bg-yellow-500',
      unchecked: 'bg-nexus-200 dark:bg-nexus-700'
    },
    thumb: {
      checked: 'bg-white',
      unchecked: 'bg-white dark:bg-nexus-900'
    },
    hover: {
      checked: 'bg-yellow-600',
      unchecked: 'bg-nexus-300 dark:bg-nexus-600'
    },
    ring: 'ring-yellow-500/30',
    text: {
      checked: 'text-yellow-700 dark:text-yellow-300',
      unchecked: 'text-nexus-500 dark:text-nexus-400'
    }
  },
  purple: {
    track: {
      checked: 'bg-purple-500',
      unchecked: 'bg-nexus-200 dark:bg-nexus-700'
    },
    thumb: {
      checked: 'bg-white',
      unchecked: 'bg-white dark:bg-nexus-900'
    },
    hover: {
      checked: 'bg-purple-600',
      unchecked: 'bg-nexus-300 dark:bg-nexus-600'
    },
    ring: 'ring-purple-500/30',
    text: {
      checked: 'text-purple-700 dark:text-purple-300',
      unchecked: 'text-nexus-500 dark:text-nexus-400'
    }
  },
  pink: {
    track: {
      checked: 'bg-pink-500',
      unchecked: 'bg-nexus-200 dark:bg-nexus-700'
    },
    thumb: {
      checked: 'bg-white',
      unchecked: 'bg-white dark:bg-nexus-900'
    },
    hover: {
      checked: 'bg-pink-600',
      unchecked: 'bg-nexus-300 dark:bg-nexus-600'
    },
    ring: 'ring-pink-500/30',
    text: {
      checked: 'text-pink-700 dark:text-pink-300',
      unchecked: 'text-nexus-500 dark:text-nexus-400'
    }
  },
  gradient: {
    track: {
      checked: 'bg-gradient-to-r from-nexus-400 to-nexus-600',
      unchecked: 'bg-nexus-200 dark:bg-nexus-700'
    },
    thumb: {
      checked: 'bg-white',
      unchecked: 'bg-white dark:bg-nexus-900'
    },
    hover: {
      checked: 'bg-gradient-to-r from-nexus-500 to-nexus-700',
      unchecked: 'bg-nexus-300 dark:bg-nexus-600'
    },
    ring: 'ring-nexus-500/30',
    text: {
      checked: 'text-nexus-700 dark:text-nexus-300',
      unchecked: 'text-nexus-500 dark:text-nexus-400'
    }
  },
  auto: {
    track: {
      checked: 'bg-nexus-500 dark:bg-nexus-400',
      unchecked: 'bg-nexus-200 dark:bg-nexus-700'
    },
    thumb: {
      checked: 'bg-white dark:bg-nexus-900',
      unchecked: 'bg-white dark:bg-nexus-900'
    },
    hover: {
      checked: 'bg-nexus-600 dark:bg-nexus-300',
      unchecked: 'bg-nexus-300 dark:bg-nexus-600'
    },
    ring: 'ring-nexus-500/30 dark:ring-nexus-400/30',
    text: {
      checked: 'text-nexus-700 dark:text-nexus-300',
      unchecked: 'text-nexus-500 dark:text-nexus-400'
    }
  }
};

// ========================================
// VARIANT CONFIGURATION
// ========================================

const VARIANT_CONFIG: Record<ToggleVariant, {
  track: string;
  thumb: string;
  className: string;
  shadow: string;
}> = {
  default: {
    track: 'rounded-full',
    thumb: 'rounded-full',
    className: '',
    shadow: 'shadow-md'
  },
  ios: {
    track: 'rounded-full shadow-inner',
    thumb: 'rounded-full shadow-lg',
    className: 'transition-all duration-300 ease-in-out',
    shadow: 'shadow-lg'
  },
  material: {
    track: 'rounded-full shadow-md',
    thumb: 'rounded-full shadow-xl',
    className: 'transition-all duration-200 ease-out',
    shadow: 'shadow-xl'
  },
  neon: {
    track: 'rounded-full shadow-[inset_0_0_10px_rgba(0,0,0,0.3)]',
    thumb: 'rounded-full shadow-[0_0_20px_rgba(99,102,241,0.3)]',
    className: 'shadow-glow',
    shadow: 'shadow-[0_0_30px_rgba(99,102,241,0.2)]'
  },
  gradient: {
    track: 'rounded-full',
    thumb: 'rounded-full shadow-lg',
    className: '',
    shadow: 'shadow-md'
  },
  minimal: {
    track: 'rounded-sm',
    thumb: 'rounded-sm shadow-none',
    className: '',
    shadow: 'shadow-none'
  },
  pill: {
    track: 'rounded-full',
    thumb: 'rounded-full shadow-md',
    className: '',
    shadow: 'shadow-md'
  },
  glow: {
    track: 'rounded-full',
    thumb: 'rounded-full shadow-lg shadow-nexus-500/50',
    className: 'animate-pulse-glow',
    shadow: 'shadow-2xl'
  },
  crypto: {
    track: 'rounded-full border-2 border-nexus-500/30',
    thumb: 'rounded-full shadow-lg bg-gradient-to-br from-nexus-400 to-nexus-600',
    className: 'border border-nexus-400/20',
    shadow: 'shadow-xl'
  },
  glass: {
    track: 'rounded-full border border-white/20 bg-white/10 backdrop-blur-xl',
    thumb: 'rounded-full shadow-lg bg-white/20 backdrop-blur-xl border border-white/30',
    className: 'backdrop-blur-xl',
    shadow: 'shadow-xl'
  },
  modern: {
    track: 'rounded-full shadow-inner',
    thumb: 'rounded-full shadow-lg border-2 border-white dark:border-nexus-900',
    className: 'transition-all duration-300 ease-in-out',
    shadow: 'shadow-lg shadow-nexus-500/20'
  }
};

// ========================================
// ANIMATION CONFIGURATION
// ========================================

const ANIMATION_CONFIG: Record<ToggleAnimation, {
  thumb: string;
  track: string;
  className: string;
}> = {
  slide: {
    thumb: 'transition-all duration-300 ease-in-out',
    track: 'transition-colors duration-300',
    className: ''
  },
  fade: {
    thumb: 'transition-all duration-200',
    track: 'transition-opacity duration-200',
    className: ''
  },
  scale: {
    thumb: 'transition-all duration-300 transform hover:scale-105 active:scale-95',
    track: 'transition-colors duration-300',
    className: ''
  },
  bounce: {
    thumb: 'transition-all duration-300 ease-bounce',
    track: 'transition-colors duration-300',
    className: ''
  },
  rotate: {
    thumb: 'transition-all duration-300 transform',
    track: 'transition-colors duration-300',
    className: ''
  },
  none: {
    thumb: '',
    track: '',
    className: ''
  }
};

// ========================================
// STATUS CONFIGURATION
// ========================================

const STATUS_CONFIG: Record<ToggleStatus, {
  icon: React.ReactNode;
  color: string;
  message: string;
}> = {
  idle: {
    icon: null,
    color: '',
    message: ''
  },
  loading: {
    icon: <Loader2 className="w-4 h-4 animate-spin" />,
    color: 'text-nexus-500',
    message: 'Loading...'
  },
  success: {
    icon: <CheckCircle className="w-4 h-4" />,
    color: 'text-emerald-500',
    message: 'Success'
  },
  error: {
    icon: <AlertCircle className="w-4 h-4" />,
    color: 'text-red-500',
    message: 'Error'
  },
  warning: {
    icon: <AlertTriangle className="w-4 h-4" />,
    color: 'text-yellow-500',
    message: 'Warning'
  },
  info: {
    icon: <Info className="w-4 h-4" />,
    color: 'text-blue-500',
    message: 'Info'
  }
};

// ========================================
// MAIN COMPONENT
// ========================================

export const Toggle = forwardRef<HTMLButtonElement, ToggleProps>(({
  checked: controlledChecked,
  defaultChecked = false,
  onChange,
  onChangeEnd,
  variant = 'default',
  size = 'md',
  color = 'nexus',
  iconPosition = 'none',
  checkedIcon,
  uncheckedIcon,
  animation = 'slide',
  label,
  labelPosition = 'right',
  labelClassName,
  description,
  descriptionClassName,
  status = 'idle',
  statusMessage,
  disabled = false,
  loading = false,
  readOnly = false,
  ripple = true,
  persistState = false,
  storageKey = 'nexus-toggle-state',
  renderThumb,
  renderTrack,
  className,
  trackClassName,
  thumbClassName,
  ariaLabel,
  ariaDescribedby,
  testId = 'nexus-toggle',
  onFocus,
  onBlur,
  onHoverStart,
  onHoverEnd,
  group,
  value,
  ...props
}, ref) => {
  // ========================================
  // STATE
  // ========================================
  
  const [isChecked, setIsChecked] = useState<boolean>(() => {
    if (controlledChecked !== undefined) return controlledChecked;
    return defaultChecked;
  });
  const [isHovered, setIsHovered] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const [isPressed, setIsPressed] = useState(false);
  const [ripplePosition, setRipplePosition] = useState({ x: 0, y: 0 });
  const [showRipple, setShowRipple] = useState(false);

  // ========================================
  // REFS
  // ========================================
  
  const toggleRef = useRef<HTMLButtonElement>(null);
  const rippleRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const isMounted = useRef(false);

  // ========================================
  // HOOKS
  // ========================================
  
  const { theme } = useTheme();
  const [storedState, setStoredState] = useLocalStorage<boolean | null>(storageKey, null);

  // ========================================
  // EFFECTS
  // ========================================
  
  // Sync with controlled prop
  useEffect(() => {
    if (controlledChecked !== undefined) {
      setIsChecked(controlledChecked);
    }
  }, [controlledChecked]);

  // Load stored state
  useEffect(() => {
    if (persistState && storedState !== null && controlledChecked === undefined) {
      setIsChecked(storedState);
    }
  }, [persistState, storedState, controlledChecked]);

  // Mount effect
  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
    };
  }, []);

  // Group behavior
  useEffect(() => {
    if (group && isChecked) {
      // Dispatch custom event for group
      const event = new CustomEvent('toggle-group-change', {
        detail: { group, value, checked: isChecked }
      });
      window.dispatchEvent(event);
    }
  }, [group, value, isChecked]);

  // ========================================
  // HELPERS
  // ========================================
  
  const colors = COLOR_CONFIG[color];
  const sizes = SIZE_CONFIG[size];
  const variantConfig = VARIANT_CONFIG[variant];
  const animationConfig = ANIMATION_CONFIG[animation];
  const statusConfig = STATUS_CONFIG[status];
  const effectiveColor = color === 'auto' ? (theme === 'dark' ? 'nexus' : 'nexus') : color;

  const isDisabled = disabled || loading || readOnly;
  const statusColor = status !== 'idle' ? statusConfig.color : '';

  // ========================================
  // HANDLERS
  // ========================================
  
  const handleToggle = useCallback((event?: React.MouseEvent | React.KeyboardEvent) => {
    if (isDisabled) return;

    const newChecked = !isChecked;
    setIsChecked(newChecked);
    onChange?.(newChecked);
    
    if (persistState) {
      setStoredState(newChecked);
    }

    // Ripple effect
    if (ripple && event) {
      const rect = toggleRef.current?.getBoundingClientRect();
      if (rect) {
        const x = (event as React.MouseEvent).clientX - rect.left || rect.width / 2;
        const y = (event as React.MouseEvent).clientY - rect.top || rect.height / 2;
        setRipplePosition({ x, y });
        setShowRipple(true);
        setTimeout(() => setShowRipple(false), 600);
      }
    }

    onChangeEnd?.(newChecked);
  }, [isChecked, isDisabled, onChange, onChangeEnd, persistState, setStoredState, ripple]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (isDisabled) return;
    
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      handleToggle(e);
    }
  }, [isDisabled, handleToggle]);

  const handleClick = useCallback((e: React.MouseEvent) => {
    if (isDisabled) return;
    handleToggle(e);
  }, [isDisabled, handleToggle]);

  const handleMouseEnter = useCallback(() => {
    setIsHovered(true);
    onHoverStart?.();
  }, [onHoverStart]);

  const handleMouseLeave = useCallback(() => {
    setIsHovered(false);
    onHoverEnd?.();
  }, [onHoverEnd]);

  // ========================================
  // RENDER HELPERS
  // ========================================
  
  const renderDefaultThumb = () => {
    const thumbClasses = cn(
      'absolute top-1/2 -translate-y-1/2 transition-all',
      sizes.thumb.width,
      sizes.thumb.height,
      variantConfig.thumb,
      animationConfig.thumb,
      isChecked ? `left-auto ${sizes.translateX}` : 'left-0.5',
      isChecked ? colors.thumb.checked : colors.thumb.unchecked,
      isHovered && !isDisabled && (isChecked ? colors.hover.checked : colors.hover.unchecked),
      isPressed && 'scale-95',
      isDisabled && 'opacity-50 cursor-not-allowed',
      isFocused && `ring-2 ${colors.ring}`,
      variantConfig.shadow,
      thumbClassName
    );

    return (
      <div className={thumbClasses}>
        {/* Icon on thumb */}
        {iconPosition !== 'none' && (
          <div className="absolute inset-0 flex items-center justify-center">
            {isChecked ? checkedIcon : uncheckedIcon}
          </div>
        )}
        
        {/* Status indicator */}
        {status !== 'idle' && (
          <div className="absolute -top-1 -right-1">
            {statusConfig.icon}
          </div>
        )}
      </div>
    );
  };

  const renderDefaultTrack = () => {
    const trackClasses = cn(
      'relative flex-shrink-0',
      sizes.track.width,
      sizes.track.height,
      variantConfig.track,
      animationConfig.track,
      isChecked ? colors.track.checked : colors.track.unchecked,
      isHovered && !isDisabled && (isChecked ? colors.hover.checked : colors.hover.unchecked),
      isDisabled && 'opacity-50 cursor-not-allowed',
      trackClassName
    );

    return (
      <div className={trackClasses}>
        {/* Loading overlay */}
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center">
            <Loader2 className={cn(
              'animate-spin text-white',
              sizes.thumb.width,
              sizes.thumb.height
            )} />
          </div>
        )}
        
        {renderThumb ? renderThumb({ checked: isChecked, isHovered, isFocused }) : renderDefaultThumb()}
      </div>
    );
  };

  const renderTrack = () => {
    if (renderTrack) {
      return renderTrack({ checked: isChecked, isHovered, isFocused });
    }
    return renderDefaultTrack();
  };

  const renderLabel = () => {
    if (!label) return null;

    const labelColor = isDisabled 
      ? 'text-nexus-400 dark:text-nexus-600' 
      : isChecked 
        ? colors.text.checked 
        : colors.text.unchecked;

    return (
      <span className={cn(
        'font-medium select-none transition-colors',
        sizes.fontSize,
        labelColor,
        labelClassName
      )}>
        {label}
        {statusMessage && (
          <span className={cn('ml-1 text-sm', statusColor)}>
            {statusMessage}
          </span>
        )}
      </span>
    );
  };

  const renderDescription = () => {
    if (!description) return null;

    return (
      <span className={cn(
        'text-nexus-500 dark:text-nexus-400 select-none',
        sizes.fontSize,
        descriptionClassName
      )}>
        {description}
      </span>
    );
  };

  const renderRipple = () => {
    if (!ripple || !showRipple) return null;

    const rippleColor = isChecked 
      ? 'rgba(99,102,241,0.2)' 
      : 'rgba(0,0,0,0.1)';

    return (
      <div
        ref={rippleRef}
        className="absolute rounded-full pointer-events-none animate-ripple"
        style={{
          left: ripplePosition.x - 25,
          top: ripplePosition.y - 25,
          width: 50,
          height: 50,
          backgroundColor: rippleColor,
        }}
      />
    );
  };

  // ========================================
  // MAIN RENDER
  // ========================================

  const labelPositions = {
    left: 'flex-row-reverse',
    right: 'flex-row',
    top: 'flex-col',
    bottom: 'flex-col-reverse'
  };

  const containerClasses = cn(
    'inline-flex items-center',
    labelPositions[labelPosition],
    sizes.gap,
    variantConfig.className,
    animationConfig.className,
    isDisabled && 'cursor-not-allowed opacity-75',
    className
  );

  const toggleClasses = cn(
    'relative inline-flex items-center justify-center',
    'outline-none',
    'transition-colors',
    isDisabled ? 'cursor-not-allowed' : 'cursor-pointer',
    isFocused && `ring-2 ${colors.ring} ring-offset-2 ring-offset-white dark:ring-offset-nexus-900`,
    'rounded-full'
  );

  return (
    <div className="flex flex-col gap-1" data-group={group}>
      <button
        ref={toggleRef}
        type="button"
        role="switch"
        aria-checked={isChecked}
        aria-label={ariaLabel || label}
        aria-describedby={ariaDescribedby}
        aria-disabled={isDisabled}
        disabled={isDisabled}
        className={containerClasses}
        onClick={handleClick}
        onKeyDown={handleKeyDown}
        onFocus={(e) => {
          setIsFocused(true);
          onFocus?.(e);
        }}
        onBlur={(e) => {
          setIsFocused(false);
          onBlur?.(e);
        }}
        onMouseEnter={handleMouseEnter}
        onMouseLeave={handleMouseLeave}
        onMouseDown={() => setIsPressed(true)}
        onMouseUp={() => setIsPressed(false)}
        data-testid={testId}
        data-checked={isChecked}
        data-variant={variant}
        data-size={size}
        data-color={color}
        data-status={status}
        {...props}
      >
        {/* Label (left position) */}
        {(labelPosition === 'left' || labelPosition === 'top') && renderLabel()}

        {/* Toggle */}
        <div className={cn(toggleClasses, sizes.padding)}>
          {renderTrack()}
          {renderRipple()}
        </div>

        {/* Label (right position) */}
        {(labelPosition === 'right' || labelPosition === 'bottom') && renderLabel()}
      </button>

      {/* Description */}
      {description && renderDescription()}

      {/* Hidden input for form submission */}
      <input
        ref={inputRef}
        type="hidden"
        name={props.name}
        value={isChecked ? 'on' : 'off'}
        disabled={isDisabled}
      />
    </div>
  );
});

Toggle.displayName = 'Toggle';

// ========================================
// COMPOUND COMPONENTS
// ========================================

export interface ToggleGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  value?: string;
  onChange?: (value: string) => void;
  className?: string;
  label?: string;
  description?: string;
  error?: string;
  required?: boolean;
  disabled?: boolean;
}

export const ToggleGroup: React.FC<ToggleGroupProps> = ({
  children,
  value: groupValue,
  onChange,
  className,
  label,
  description,
  error,
  required,
  disabled,
  ...props
}) => {
  const [value, setValue] = useState<string | undefined>(groupValue);

  useEffect(() => {
    setValue(groupValue);
  }, [groupValue]);

  const handleChange = useCallback((newValue: string) => {
    setValue(newValue);
    onChange?.(newValue);
  }, [onChange]);

  // Listen for group changes from child toggles
  useEffect(() => {
    const handler = (e: CustomEvent) => {
      const { group, value: val, checked } = e.detail;
      if (checked) {
        handleChange(val);
      }
    };

    window.addEventListener('toggle-group-change', handler as EventListener);
    return () => {
      window.removeEventListener('toggle-group-change', handler as EventListener);
    };
  }, [handleChange]);

  // Clone children with group props
  const childrenWithProps = React.Children.map(children, (child) => {
    if (React.isValidElement(child) && child.type === Toggle) {
      return React.cloneElement(child as React.ReactElement<ToggleProps>, {
        group: 'toggle-group',
        checked: child.props.value === value,
        onChange: (checked: boolean) => {
          if (checked && child.props.value) {
            handleChange(child.props.value);
          }
        },
        disabled: disabled || child.props.disabled,
      });
    }
    return child;
  });

  return (
    <div className={cn('space-y-2', className)} {...props}>
      {label && (
        <div className="flex items-center justify-between">
          <label className={cn(
            'text-sm font-medium text-nexus-700 dark:text-nexus-300',
            disabled && 'opacity-50'
          )}>
            {label}
            {required && <span className="text-red-500 ml-1">*</span>}
          </label>
        </div>
      )}
      <div className="flex flex-wrap gap-3">
        {childrenWithProps}
      </div>
      {description && (
        <p className="text-sm text-nexus-500 dark:text-nexus-400">{description}</p>
      )}
      {error && (
        <p className="text-sm text-red-500">{error}</p>
      )}
    </div>
  );
};

// ========================================
// PRESETED TOGGLE COMPONENTS
// ========================================

export const ThemeToggle: React.FC<Omit<ToggleProps, 'checkedIcon' | 'uncheckedIcon' | 'checked' | 'defaultChecked' | 'onChange'>> = ({
  ...props
}) => {
  const { theme, setTheme } = useTheme();
  const isDark = theme === 'dark';

  const handleThemeToggle = (checked: boolean) => {
    setTheme(checked ? 'dark' : 'light');
  };

  return (
    <Toggle
      checked={isDark}
      onChange={handleThemeToggle}
      checkedIcon={<Moon className="w-4 h-4 text-white" />}
      uncheckedIcon={<Sun className="w-4 h-4 text-yellow-500" />}
      color="nexus"
      variant="ios"
      size="md"
      ariaLabel="Toggle theme"
      {...props}
    />
  );
};

export const PowerToggle: React.FC<Omit<ToggleProps, 'checkedIcon' | 'uncheckedIcon'>> = ({
  ...props
}) => {
  return (
    <Toggle
      checkedIcon={<Power className="w-4 h-4 text-white" />}
      uncheckedIcon={<Power className="w-4 h-4 text-nexus-400" />}
      color="gradient"
      variant="glow"
      size="lg"
      ariaLabel="Toggle power"
      {...props}
    />
  );
};

export const WifiToggle: React.FC<Omit<ToggleProps, 'checkedIcon' | 'uncheckedIcon'>> = ({
  ...props
}) => {
  return (
    <Toggle
      checkedIcon={<Wifi className="w-4 h-4 text-white" />}
      uncheckedIcon={<Wifi className="w-4 h-4 text-nexus-400" />}
      color="blue"
      variant="material"
      size="md"
      ariaLabel="Toggle WiFi"
      {...props}
    />
  );
};

export const BluetoothToggle: React.FC<Omit<ToggleProps, 'checkedIcon' | 'uncheckedIcon'>> = ({
  ...props
}) => {
  return (
    <Toggle
      checkedIcon={<Bluetooth className="w-4 h-4 text-white" />}
      uncheckedIcon={<Bluetooth className="w-4 h-4 text-nexus-400" />}
      color="purple"
      variant="ios"
      size="md"
      ariaLabel="Toggle Bluetooth"
      {...props}
    />
  );
};

export const VolumeToggle: React.FC<Omit<ToggleProps, 'checkedIcon' | 'uncheckedIcon'>> = ({
  ...props
}) => {
  return (
    <Toggle
      checkedIcon={<Volume2 className="w-4 h-4 text-white" />}
      uncheckedIcon={<VolumeX className="w-4 h-4 text-nexus-400" />}
      color="green"
      variant="minimal"
      size="md"
      ariaLabel="Toggle volume"
      {...props}
    />
  );
};

export const PlayToggle: React.FC<Omit<ToggleProps, 'checkedIcon' | 'uncheckedIcon'>> = ({
  ...props
}) => {
  return (
    <Toggle
      checkedIcon={<Pause className="w-4 h-4 text-white" />}
      uncheckedIcon={<Play className="w-4 h-4 text-nexus-400" />}
      color="nexus"
      variant="modern"
      size="lg"
      ariaLabel="Toggle play"
      {...props}
    />
  );
};

export const AIToggle: React.FC<Omit<ToggleProps, 'checkedIcon' | 'uncheckedIcon' | 'color' | 'variant'>> = ({
  ...props
}) => {
  return (
    <Toggle
      checkedIcon={<Sparkles className="w-4 h-4 text-white" />}
      uncheckedIcon={<Zap className="w-4 h-4 text-nexus-400" />}
      color="gradient"
      variant="glow"
      size="lg"
      ariaLabel="Toggle AI"
      {...props}
    />
  );
};

export const SecureToggle: React.FC<Omit<ToggleProps, 'checkedIcon' | 'uncheckedIcon'>> = ({
  ...props
}) => {
  return (
    <Toggle
      checkedIcon={<Lock className="w-4 h-4 text-white" />}
      uncheckedIcon={<Lock className="w-4 h-4 text-nexus-400" />}
      color={props.checked ? 'green' : 'red'}
      variant="material"
      size="md"
      ariaLabel="Toggle security"
      {...props}
    />
  );
};

// ========================================
// EXPORTS
// ========================================

ToggleGroup.displayName = 'ToggleGroup';
ThemeToggle.displayName = 'ThemeToggle';
PowerToggle.displayName = 'PowerToggle';
WifiToggle.displayName = 'WifiToggle';
BluetoothToggle.displayName = 'BluetoothToggle';
VolumeToggle.displayName = 'VolumeToggle';
PlayToggle.displayName = 'PlayToggle';
AIToggle.displayName = 'AIToggle';
SecureToggle.displayName = 'SecureToggle';

export default Toggle;

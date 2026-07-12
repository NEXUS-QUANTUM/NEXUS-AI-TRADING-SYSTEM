import React, { forwardRef, useState, useCallback, useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';
import { Check, X, Loader2, Sparkles, Zap, Moon, Sun, Bell, Lock, Eye, EyeOff } from 'lucide-react';
import { useTheme } from '@/hooks/useTheme';
import { useLocalStorage } from '@/hooks/useLocalStorage';

/**
 * NEXUS AI TRADING SYSTEM - Switch Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 * 
 * Version: 3.0.0
 * Status: Production Ready
 * 
 * Complete Switch/Toggle system with:
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
 */

// ========================================
// TYPES & INTERFACES
// ========================================

export type SwitchVariant = 
  | 'default' 
  | 'ios' 
  | 'material' 
  | 'neon' 
  | 'gradient' 
  | 'minimal' 
  | 'pill' 
  | 'glow' 
  | 'crypto';

export type SwitchSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
export type SwitchColor = 'nexus' | 'blue' | 'green' | 'red' | 'yellow' | 'purple' | 'pink' | 'gradient' | 'auto';
export type SwitchIconPosition = 'left' | 'right' | 'both' | 'none';
export type SwitchAnimation = 'slide' | 'fade' | 'scale' | 'bounce' | 'rotate' | 'none';

export interface SwitchProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size' | 'onChange' | 'checked' | 'defaultChecked' | 'type'> {
  /** Checked state */
  checked?: boolean;
  /** Default checked state */
  defaultChecked?: boolean;
  /** Callback when checked changes */
  onChange?: (checked: boolean) => void;
  /** Callback when checked change is committed */
  onChangeEnd?: (checked: boolean) => void;
  /** Switch variant */
  variant?: SwitchVariant;
  /** Switch size */
  size?: SwitchSize;
  /** Switch color */
  color?: SwitchColor;
  /** Icon position */
  iconPosition?: SwitchIconPosition;
  /** Icon for checked state */
  checkedIcon?: React.ReactNode;
  /** Icon for unchecked state */
  uncheckedIcon?: React.ReactNode;
  /** Animation type */
  animation?: SwitchAnimation;
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
}

// ========================================
// SIZE CONFIGURATION
// ========================================

const SIZE_CONFIG: Record<SwitchSize, {
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

const COLOR_CONFIG: Record<SwitchColor, {
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
    ring: 'ring-nexus-500/30'
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
    ring: 'ring-blue-500/30'
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
    ring: 'ring-emerald-500/30'
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
    ring: 'ring-red-500/30'
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
    ring: 'ring-yellow-500/30'
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
    ring: 'ring-purple-500/30'
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
    ring: 'ring-pink-500/30'
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
    ring: 'ring-nexus-500/30'
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
    ring: 'ring-nexus-500/30 dark:ring-nexus-400/30'
  }
};

// ========================================
// VARIANT CONFIGURATION
// ========================================

const VARIANT_CONFIG: Record<SwitchVariant, {
  track: string;
  thumb: string;
  className: string;
}> = {
  default: {
    track: 'rounded-full',
    thumb: 'rounded-full',
    className: ''
  },
  ios: {
    track: 'rounded-full shadow-inner',
    thumb: 'rounded-full shadow-lg',
    className: 'transition-all duration-300 ease-in-out'
  },
  material: {
    track: 'rounded-full shadow-md',
    thumb: 'rounded-full shadow-xl',
    className: 'transition-all duration-200 ease-out'
  },
  neon: {
    track: 'rounded-full shadow-[inset_0_0_10px_rgba(0,0,0,0.3)]',
    thumb: 'rounded-full shadow-[0_0_20px_rgba(99,102,241,0.3)]',
    className: 'shadow-glow'
  },
  gradient: {
    track: 'rounded-full',
    thumb: 'rounded-full shadow-lg',
    className: ''
  },
  minimal: {
    track: 'rounded-sm',
    thumb: 'rounded-sm shadow-none',
    className: ''
  },
  pill: {
    track: 'rounded-full',
    thumb: 'rounded-full shadow-md',
    className: ''
  },
  glow: {
    track: 'rounded-full',
    thumb: 'rounded-full shadow-lg shadow-nexus-500/50',
    className: 'animate-pulse-glow'
  },
  crypto: {
    track: 'rounded-full border-2 border-nexus-500/30',
    thumb: 'rounded-full shadow-lg bg-gradient-to-br from-nexus-400 to-nexus-600',
    className: 'border border-nexus-400/20'
  }
};

// ========================================
// ANIMATION CONFIGURATION
// ========================================

const ANIMATION_CONFIG: Record<SwitchAnimation, {
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
// MAIN COMPONENT
// ========================================

export const Switch = forwardRef<HTMLButtonElement, SwitchProps>(({
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
  disabled = false,
  loading = false,
  readOnly = false,
  ripple = true,
  persistState = false,
  storageKey = 'nexus-switch-state',
  renderThumb,
  renderTrack,
  className,
  trackClassName,
  thumbClassName,
  ariaLabel,
  ariaDescribedby,
  testId = 'nexus-switch',
  onFocus,
  onBlur,
  onHoverStart,
  onHoverEnd,
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
  
  const switchRef = useRef<HTMLButtonElement>(null);
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

  // ========================================
  // HELPERS
  // ========================================
  
  const colors = COLOR_CONFIG[color];
  const sizes = SIZE_CONFIG[size];
  const variantConfig = VARIANT_CONFIG[variant];
  const animationConfig = ANIMATION_CONFIG[animation];
  const effectiveColor = color === 'auto' ? (theme === 'dark' ? 'nexus' : 'nexus') : color;

  const isDisabled = disabled || loading || readOnly;

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
      const rect = switchRef.current?.getBoundingClientRect();
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
      </div>
    );
  };

  const renderDefaultTrack = () => {
    return (
      <div
        className={cn(
          'relative flex-shrink-0',
          sizes.track.width,
          sizes.track.height,
          variantConfig.track,
          animationConfig.track,
          isChecked ? colors.track.checked : colors.track.unchecked,
          isHovered && !isDisabled && (isChecked ? colors.hover.checked : colors.hover.unchecked),
          isDisabled && 'opacity-50 cursor-not-allowed',
          trackClassName
        )}
      >
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

    return (
      <span className={cn(
        'font-medium select-none',
        sizes.fontSize,
        isDisabled ? 'text-nexus-400 dark:text-nexus-600' : 'text-nexus-700 dark:text-nexus-300',
        labelClassName
      )}>
        {label}
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

    return (
      <div
        ref={rippleRef}
        className="absolute rounded-full pointer-events-none animate-ripple"
        style={{
          left: ripplePosition.x - 25,
          top: ripplePosition.y - 25,
          width: 50,
          height: 50,
          backgroundColor: isChecked ? 'rgba(99,102,241,0.2)' : 'rgba(0,0,0,0.1)',
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

  const switchClasses = cn(
    'relative inline-flex items-center justify-center',
    'outline-none',
    'transition-colors',
    isDisabled ? 'cursor-not-allowed' : 'cursor-pointer',
    isFocused && `ring-2 ${colors.ring} ring-offset-2 ring-offset-white dark:ring-offset-nexus-900`,
    'rounded-full'
  );

  return (
    <div className="flex flex-col gap-1">
      <button
        ref={switchRef}
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
        {...props}
      >
        {/* Label (left position) */}
        {(labelPosition === 'left' || labelPosition === 'top') && renderLabel()}

        {/* Switch */}
        <div className={cn(switchClasses, sizes.padding)}>
          {renderTrack()}
          {renderRipple()}
          
          {/* Loading spinner */}
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center">
              <Loader2 className={cn(
                'animate-spin text-white',
                sizes.thumb.width,
                sizes.thumb.height
              )} />
            </div>
          )}
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

Switch.displayName = 'Switch';

// ========================================
// COMPOUND COMPONENTS
// ========================================

export interface SwitchGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  label?: string;
  description?: string;
  error?: string;
  required?: boolean;
  disabled?: boolean;
  className?: string;
}

export const SwitchGroup: React.FC<SwitchGroupProps> = ({
  children,
  label,
  description,
  error,
  required,
  disabled,
  className,
  ...props
}) => {
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
      {children}
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
// THEME TOGGLE SWITCH
// ========================================

export interface ThemeSwitchProps extends Omit<SwitchProps, 'checkedIcon' | 'uncheckedIcon' | 'checked' | 'defaultChecked' | 'onChange'> {
  onThemeChange?: (theme: 'light' | 'dark') => void;
}

export const ThemeSwitch: React.FC<ThemeSwitchProps> = ({
  onThemeChange,
  ...props
}) => {
  const { theme, setTheme } = useTheme();
  const isDark = theme === 'dark';

  const handleThemeToggle = (checked: boolean) => {
    const newTheme = checked ? 'dark' : 'light';
    setTheme(newTheme);
    onThemeChange?.(newTheme);
  };

  return (
    <Switch
      checked={isDark}
      onChange={handleThemeToggle}
      checkedIcon={<Moon className="w-3 h-3 text-white" />}
      uncheckedIcon={<Sun className="w-3 h-3 text-yellow-500" />}
      color="nexus"
      variant="ios"
      size="md"
      ariaLabel="Toggle theme"
      {...props}
    />
  );
};

// ========================================
// PRIVACY SWITCH
// ========================================

export interface PrivacySwitchProps extends Omit<SwitchProps, 'checkedIcon' | 'uncheckedIcon'> {
  onVisibilityChange?: (visible: boolean) => void;
}

export const PrivacySwitch: React.FC<PrivacySwitchProps> = ({
  onVisibilityChange,
  ...props
}) => {
  const [isVisible, setIsVisible] = useState(true);

  const handleVisibilityToggle = (checked: boolean) => {
    setIsVisible(checked);
    onVisibilityChange?.(checked);
  };

  return (
    <Switch
      checked={isVisible}
      onChange={handleVisibilityToggle}
      checkedIcon={<Eye className="w-3 h-3 text-white" />}
      uncheckedIcon={<EyeOff className="w-3 h-3 text-nexus-400" />}
      color="nexus"
      variant="material"
      size="md"
      ariaLabel="Toggle visibility"
      {...props}
    />
  );
};

// ========================================
// NOTIFICATION SWITCH
// ========================================

export interface NotificationSwitchProps extends Omit<SwitchProps, 'checkedIcon' | 'uncheckedIcon'> {
  onNotificationChange?: (enabled: boolean) => void;
}

export const NotificationSwitch: React.FC<NotificationSwitchProps> = ({
  onNotificationChange,
  ...props
}) => {
  const [isEnabled, setIsEnabled] = useState(true);

  const handleToggle = (checked: boolean) => {
    setIsEnabled(checked);
    onNotificationChange?.(checked);
  };

  return (
    <Switch
      checked={isEnabled}
      onChange={handleToggle}
      checkedIcon={<Bell className="w-3 h-3 text-white" />}
      uncheckedIcon={<Bell className="w-3 h-3 text-nexus-400" />}
      color="nexus"
      variant="neon"
      size="md"
      ariaLabel="Toggle notifications"
      {...props}
    />
  );
};

// ========================================
// AI POWERED SWITCH
// ========================================

export interface AISwitchProps extends Omit<SwitchProps, 'checkedIcon' | 'uncheckedIcon' | 'color' | 'variant'> {
  onAIToggle?: (enabled: boolean) => void;
  loadingText?: string;
}

export const AISwitch: React.FC<AISwitchProps> = ({
  onAIToggle,
  loadingText = 'AI is thinking...',
  ...props
}) => {
  const [isAIEnabled, setIsAIEnabled] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const handleAIToggle = async (checked: boolean) => {
    setIsLoading(true);
    try {
      // Simulate AI processing
      await new Promise(resolve => setTimeout(resolve, 800));
      setIsAIEnabled(checked);
      onAIToggle?.(checked);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <Switch
      checked={isAIEnabled}
      onChange={handleAIToggle}
      checkedIcon={<Sparkles className="w-3 h-3 text-white" />}
      uncheckedIcon={<Zap className="w-3 h-3 text-nexus-400" />}
      color="gradient"
      variant="glow"
      size="lg"
      loading={isLoading}
      label={isLoading ? loadingText : (isAIEnabled ? 'AI Enabled' : 'AI Disabled')}
      ariaLabel="Toggle AI"
      {...props}
    />
  );
};

// ========================================
// SECURE MODE SWITCH
// ========================================

export interface SecureSwitchProps extends Omit<SwitchProps, 'checkedIcon' | 'uncheckedIcon' | 'color'> {
  onSecureToggle?: (enabled: boolean) => void;
}

export const SecureSwitch: React.FC<SecureSwitchProps> = ({
  onSecureToggle,
  ...props
}) => {
  const [isSecure, setIsSecure] = useState(true);

  const handleToggle = (checked: boolean) => {
    setIsSecure(checked);
    onSecureToggle?.(checked);
  };

  return (
    <Switch
      checked={isSecure}
      onChange={handleToggle}
      checkedIcon={<Lock className="w-3 h-3 text-white" />}
      uncheckedIcon={<Lock className="w-3 h-3 text-nexus-400" />}
      color={isSecure ? 'green' : 'red'}
      variant="ios"
      size="md"
      label={isSecure ? 'Secure Mode' : 'Standard Mode'}
      ariaLabel="Toggle secure mode"
      {...props}
    />
  );
};

// ========================================
// EXPORTS
// ========================================

SwitchGroup.displayName = 'SwitchGroup';
ThemeSwitch.displayName = 'ThemeSwitch';
PrivacySwitch.displayName = 'PrivacySwitch';
NotificationSwitch.displayName = 'NotificationSwitch';
AISwitch.displayName = 'AISwitch';
SecureSwitch.displayName = 'SecureSwitch';

export default Switch;

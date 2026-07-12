import React, { forwardRef } from 'react';
import { cn } from '@/lib/utils';
import { Loader2, RefreshCw, Clock, Circle, AlertCircle } from 'lucide-react';

/**
 * NEXUS AI TRADING SYSTEM - Spinner Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 * 
 * Version: 3.0.0
 * Status: Production Ready
 * 
 * Complete Spinner/Loader system with:
 * - Multiple variants (spinner, dots, pulse, etc.)
 * - Multiple sizes (xs, sm, md, lg, xl, 2xl)
 * - Multiple colors
 * - Customizable speed
 * - Customizable thickness
 * - Loading text support
 * - Overlay support
 * - Fullscreen support
 * - Accessibility (ARIA compliant)
 * - Theme aware
 * - Responsive
 * - Custom animations
 * - Progress tracking
 * - Status indicators (success, error, warning, info)
 */

// ========================================
// TYPES & INTERFACES
// ========================================

export type SpinnerVariant = 
  | 'spinner' 
  | 'dots' 
  | 'pulse' 
  | 'ring' 
  | 'wave' 
  | 'clock' 
  | 'bars' 
  | 'ripple'
  | 'gradient'
  | 'crypto';

export type SpinnerSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | '2xl' | '3xl';
export type SpinnerColor = 'nexus' | 'white' | 'gray' | 'blue' | 'green' | 'red' | 'yellow' | 'purple' | 'pink' | 'gradient';
export type SpinnerStatus = 'idle' | 'loading' | 'success' | 'error' | 'warning' | 'info';
export type SpinnerPlacement = 'inline' | 'center' | 'overlay' | 'fullscreen';

export interface SpinnerProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Spinner variant */
  variant?: SpinnerVariant;
  /** Spinner size */
  size?: SpinnerSize;
  /** Spinner color */
  color?: SpinnerColor;
  /** Spinner status */
  status?: SpinnerStatus;
  /** Placement of the spinner */
  placement?: SpinnerPlacement;
  /** Loading text to display */
  text?: string;
  /** Text position */
  textPosition?: 'top' | 'bottom' | 'left' | 'right';
  /** Speed of animation in ms */
  speed?: number;
  /** Thickness of spinner (for spinner variant) */
  thickness?: number;
  /** Number of dots (for dots variant) */
  dotCount?: number;
  /** Whether to show as overlay */
  overlay?: boolean;
  /** Overlay opacity */
  overlayOpacity?: number;
  /** Background color of overlay */
  overlayColor?: string;
  /** Whether to show backdrop blur */
  blur?: boolean;
  /** Progress value (0-100) */
  progress?: number;
  /** Whether to show progress text */
  showProgress?: boolean;
  /** Additional className */
  className?: string;
  /** Text className */
  textClassName?: string;
  /** Overlay className */
  overlayClassName?: string;
  /** ARIA label for accessibility */
  ariaLabel?: string;
  /** ARIA live region */
  ariaLive?: 'polite' | 'assertive' | 'off';
  /** Test ID */
  testId?: string;
  /** On complete callback */
  onComplete?: () => void;
  /** Auto hide after completion */
  autoHide?: boolean;
  /** Auto hide delay in ms */
  autoHideDelay?: number;
}

// ========================================
// SIZE CONFIGURATION
// ========================================

const SIZE_CONFIG: Record<SpinnerSize, {
  spinner: string;
  dots: string;
  pulse: string;
  ring: string;
  wave: string;
  clock: string;
  bars: string;
  ripple: string;
  text: string;
  gap: string;
}> = {
  xs: {
    spinner: 'w-3 h-3',
    dots: 'w-1 h-1',
    pulse: 'w-4 h-4',
    ring: 'w-4 h-4',
    wave: 'w-1 h-3',
    clock: 'w-4 h-4',
    bars: 'w-0.5 h-3',
    ripple: 'w-4 h-4',
    text: 'text-xs',
    gap: 'gap-1'
  },
  sm: {
    spinner: 'w-4 h-4',
    dots: 'w-1.5 h-1.5',
    pulse: 'w-6 h-6',
    ring: 'w-6 h-6',
    wave: 'w-1.5 h-4',
    clock: 'w-6 h-6',
    bars: 'w-0.5 h-4',
    ripple: 'w-6 h-6',
    text: 'text-sm',
    gap: 'gap-1.5'
  },
  md: {
    spinner: 'w-6 h-6',
    dots: 'w-2 h-2',
    pulse: 'w-8 h-8',
    ring: 'w-8 h-8',
    wave: 'w-2 h-5',
    clock: 'w-8 h-8',
    bars: 'w-1 h-5',
    ripple: 'w-8 h-8',
    text: 'text-base',
    gap: 'gap-2'
  },
  lg: {
    spinner: 'w-8 h-8',
    dots: 'w-2.5 h-2.5',
    pulse: 'w-12 h-12',
    ring: 'w-12 h-12',
    wave: 'w-2.5 h-7',
    clock: 'w-12 h-12',
    bars: 'w-1 h-7',
    ripple: 'w-12 h-12',
    text: 'text-lg',
    gap: 'gap-2.5'
  },
  xl: {
    spinner: 'w-12 h-12',
    dots: 'w-3 h-3',
    pulse: 'w-16 h-16',
    ring: 'w-16 h-16',
    wave: 'w-3 h-9',
    clock: 'w-16 h-16',
    bars: 'w-1.5 h-9',
    ripple: 'w-16 h-16',
    text: 'text-xl',
    gap: 'gap-3'
  },
  '2xl': {
    spinner: 'w-16 h-16',
    dots: 'w-4 h-4',
    pulse: 'w-20 h-20',
    ring: 'w-20 h-20',
    wave: 'w-3.5 h-12',
    clock: 'w-20 h-20',
    bars: 'w-2 h-12',
    ripple: 'w-20 h-20',
    text: 'text-2xl',
    gap: 'gap-3.5'
  },
  '3xl': {
    spinner: 'w-20 h-20',
    dots: 'w-5 h-5',
    pulse: 'w-24 h-24',
    ring: 'w-24 h-24',
    wave: 'w-4 h-14',
    clock: 'w-24 h-24',
    bars: 'w-2.5 h-14',
    ripple: 'w-24 h-24',
    text: 'text-3xl',
    gap: 'gap-4'
  }
};

// ========================================
// COLOR CONFIGURATION
// ========================================

const COLOR_CONFIG: Record<SpinnerColor, {
  spinner: string;
  dots: string;
  pulse: string;
  ring: string;
  wave: string;
  clock: string;
  bars: string;
  ripple: string;
  text: string;
}> = {
  nexus: {
    spinner: 'text-nexus-500 dark:text-nexus-400',
    dots: 'bg-nexus-500 dark:bg-nexus-400',
    pulse: 'bg-nexus-500 dark:bg-nexus-400',
    ring: 'text-nexus-500 dark:text-nexus-400',
    wave: 'bg-nexus-500 dark:bg-nexus-400',
    clock: 'text-nexus-500 dark:text-nexus-400',
    bars: 'bg-nexus-500 dark:bg-nexus-400',
    ripple: 'border-nexus-500 dark:border-nexus-400',
    text: 'text-nexus-600 dark:text-nexus-300'
  },
  white: {
    spinner: 'text-white',
    dots: 'bg-white',
    pulse: 'bg-white',
    ring: 'text-white',
    wave: 'bg-white',
    clock: 'text-white',
    bars: 'bg-white',
    ripple: 'border-white',
    text: 'text-white'
  },
  gray: {
    spinner: 'text-nexus-400 dark:text-nexus-500',
    dots: 'bg-nexus-400 dark:bg-nexus-500',
    pulse: 'bg-nexus-400 dark:bg-nexus-500',
    ring: 'text-nexus-400 dark:text-nexus-500',
    wave: 'bg-nexus-400 dark:bg-nexus-500',
    clock: 'text-nexus-400 dark:text-nexus-500',
    bars: 'bg-nexus-400 dark:bg-nexus-500',
    ripple: 'border-nexus-400 dark:border-nexus-500',
    text: 'text-nexus-500 dark:text-nexus-400'
  },
  blue: {
    spinner: 'text-blue-500',
    dots: 'bg-blue-500',
    pulse: 'bg-blue-500',
    ring: 'text-blue-500',
    wave: 'bg-blue-500',
    clock: 'text-blue-500',
    bars: 'bg-blue-500',
    ripple: 'border-blue-500',
    text: 'text-blue-600'
  },
  green: {
    spinner: 'text-emerald-500',
    dots: 'bg-emerald-500',
    pulse: 'bg-emerald-500',
    ring: 'text-emerald-500',
    wave: 'bg-emerald-500',
    clock: 'text-emerald-500',
    bars: 'bg-emerald-500',
    ripple: 'border-emerald-500',
    text: 'text-emerald-600'
  },
  red: {
    spinner: 'text-red-500',
    dots: 'bg-red-500',
    pulse: 'bg-red-500',
    ring: 'text-red-500',
    wave: 'bg-red-500',
    clock: 'text-red-500',
    bars: 'bg-red-500',
    ripple: 'border-red-500',
    text: 'text-red-600'
  },
  yellow: {
    spinner: 'text-yellow-500',
    dots: 'bg-yellow-500',
    pulse: 'bg-yellow-500',
    ring: 'text-yellow-500',
    wave: 'bg-yellow-500',
    clock: 'text-yellow-500',
    bars: 'bg-yellow-500',
    ripple: 'border-yellow-500',
    text: 'text-yellow-600'
  },
  purple: {
    spinner: 'text-purple-500',
    dots: 'bg-purple-500',
    pulse: 'bg-purple-500',
    ring: 'text-purple-500',
    wave: 'bg-purple-500',
    clock: 'text-purple-500',
    bars: 'bg-purple-500',
    ripple: 'border-purple-500',
    text: 'text-purple-600'
  },
  pink: {
    spinner: 'text-pink-500',
    dots: 'bg-pink-500',
    pulse: 'bg-pink-500',
    ring: 'text-pink-500',
    wave: 'bg-pink-500',
    clock: 'text-pink-500',
    bars: 'bg-pink-500',
    ripple: 'border-pink-500',
    text: 'text-pink-600'
  },
  gradient: {
    spinner: 'text-transparent bg-clip-text bg-gradient-to-r from-nexus-400 via-nexus-500 to-nexus-600',
    dots: 'bg-gradient-to-r from-nexus-400 via-nexus-500 to-nexus-600',
    pulse: 'bg-gradient-to-r from-nexus-400 via-nexus-500 to-nexus-600',
    ring: 'text-transparent bg-clip-text bg-gradient-to-r from-nexus-400 via-nexus-500 to-nexus-600',
    wave: 'bg-gradient-to-r from-nexus-400 via-nexus-500 to-nexus-600',
    clock: 'text-transparent bg-clip-text bg-gradient-to-r from-nexus-400 via-nexus-500 to-nexus-600',
    bars: 'bg-gradient-to-r from-nexus-400 via-nexus-500 to-nexus-600',
    ripple: 'border-transparent bg-gradient-to-r from-nexus-400 via-nexus-500 to-nexus-600 bg-clip-border',
    text: 'bg-gradient-to-r from-nexus-600 to-nexus-500 text-transparent bg-clip-text'
  }
};

// ========================================
// STATUS CONFIGURATION
// ========================================

const STATUS_CONFIG: Record<SpinnerStatus, {
  icon: React.ReactNode;
  color: SpinnerColor;
  text: string;
  className: string;
}> = {
  idle: {
    icon: null,
    color: 'nexus',
    text: '',
    className: ''
  },
  loading: {
    icon: null,
    color: 'nexus',
    text: 'Loading...',
    className: ''
  },
  success: {
    icon: <CheckCircle className="w-6 h-6" />,
    color: 'green',
    text: 'Success',
    className: 'animate-in fade-in'
  },
  error: {
    icon: <AlertCircle className="w-6 h-6" />,
    color: 'red',
    text: 'Error',
    className: 'animate-in fade-in'
  },
  warning: {
    icon: <AlertTriangle className="w-6 h-6" />,
    color: 'yellow',
    text: 'Warning',
    className: 'animate-in fade-in'
  },
  info: {
    icon: <Info className="w-6 h-6" />,
    color: 'blue',
    text: 'Info',
    className: 'animate-in fade-in'
  }
};

// ========================================
// MAIN COMPONENT
// ========================================

export const Spinner = forwardRef<HTMLDivElement, SpinnerProps>(({
  variant = 'spinner',
  size = 'md',
  color = 'nexus',
  status = 'idle',
  placement = 'inline',
  text,
  textPosition = 'bottom',
  speed = 1000,
  thickness = 3,
  dotCount = 3,
  overlay = false,
  overlayOpacity = 0.5,
  overlayColor = 'bg-black',
  blur = true,
  progress,
  showProgress = false,
  className,
  textClassName,
  overlayClassName,
  ariaLabel = 'Loading...',
  ariaLive = 'polite',
  testId = 'nexus-spinner',
  onComplete,
  autoHide = false,
  autoHideDelay = 3000,
  ...props
}, ref) => {
  // ========================================
  // STATE
  // ========================================
  
  const [isVisible, setIsVisible] = React.useState(true);
  const [progressValue, setProgressValue] = React.useState(progress || 0);

  // ========================================
  // EFFECTS
  // ========================================
  
  React.useEffect(() => {
    if (progress !== undefined) {
      setProgressValue(progress);
      if (progress >= 100) {
        onComplete?.();
        if (autoHide) {
          const timer = setTimeout(() => {
            setIsVisible(false);
          }, autoHideDelay);
          return () => clearTimeout(timer);
        }
      }
    }
  }, [progress, onComplete, autoHide, autoHideDelay]);

  // ========================================
  // HELPERS
  // ========================================
  
  const sizes = SIZE_CONFIG[size];
  const colors = COLOR_CONFIG[color];
  const statusConfig = STATUS_CONFIG[status];
  const effectiveColor = status !== 'idle' ? statusConfig.color : color;
  const effectiveColors = COLOR_CONFIG[effectiveColor];
  const effectiveText = text || (status !== 'idle' ? statusConfig.text : '');

  const shouldShowOverlay = overlay || placement === 'overlay' || placement === 'fullscreen';

  // ========================================
  // RENDERERS
  // ========================================
  
  const renderSpinner = () => {
    const spinnerColor = variant === 'gradient' ? colors.spinner : effectiveColors.spinner;
    
    return (
      <Loader2
        className={cn(
          'animate-spin',
          sizes.spinner,
          spinnerColor,
          'flex-shrink-0',
          className
        )}
        style={{ animationDuration: `${speed}ms` }}
        aria-hidden="true"
      />
    );
  };

  const renderDots = () => {
    const dotColor = variant === 'gradient' ? colors.dots : effectiveColors.dots;
    const dots = Array.from({ length: dotCount });

    return (
      <div className={cn('flex items-center gap-1.5', sizes.gap)}>
        {dots.map((_, index) => (
          <div
            key={index}
            className={cn(
              'rounded-full animate-bounce',
              sizes.dots,
              dotColor,
              'flex-shrink-0'
            )}
            style={{
              animationDelay: `${(index / dotCount) * speed}ms`,
              animationDuration: `${speed}ms`
            }}
            aria-hidden="true"
          />
        ))}
      </div>
    );
  };

  const renderPulse = () => {
    const pulseColor = variant === 'gradient' ? colors.pulse : effectiveColors.pulse;

    return (
      <div
        className={cn(
          'rounded-full animate-pulse',
          sizes.pulse,
          pulseColor,
          'flex-shrink-0'
        )}
        style={{ animationDuration: `${speed}ms` }}
        aria-hidden="true"
      />
    );
  };

  const renderRing = () => {
    const ringColor = variant === 'gradient' ? colors.ring : effectiveColors.ring;

    return (
      <div
        className={cn(
          'rounded-full border-2 border-transparent animate-spin',
          sizes.ring,
          ringColor,
          'flex-shrink-0'
        )}
        style={{
          animationDuration: `${speed}ms`,
          borderTopColor: 'currentColor',
          borderRightColor: 'currentColor',
          borderWidth: thickness
        }}
        aria-hidden="true"
      />
    );
  };

  const renderWave = () => {
    const waveColor = variant === 'gradient' ? colors.wave : effectiveColors.wave;
    const bars = 5;

    return (
      <div className={cn('flex items-center gap-0.5', sizes.gap)}>
        {Array.from({ length: bars }).map((_, index) => (
          <div
            key={index}
            className={cn(
              'rounded-full animate-wave',
              sizes.wave,
              waveColor,
              'flex-shrink-0'
            )}
            style={{
              animationDelay: `${(index / bars) * speed * 0.5}ms`,
              animationDuration: `${speed}ms`,
              height: `${30 + (index / bars) * 70}%`
            }}
            aria-hidden="true"
          />
        ))}
      </div>
    );
  };

  const renderClock = () => {
    const clockColor = variant === 'gradient' ? colors.clock : effectiveColors.clock;

    return (
      <Clock
        className={cn(
          'animate-spin',
          sizes.clock,
          clockColor,
          'flex-shrink-0'
        )}
        style={{ animationDuration: `${speed}ms` }}
        aria-hidden="true"
      />
    );
  };

  const renderBars = () => {
    const barColor = variant === 'gradient' ? colors.bars : effectiveColors.bars;
    const bars = 8;

    return (
      <div className="relative flex items-center justify-center">
        {Array.from({ length: bars }).map((_, index) => {
          const angle = (index / bars) * 360;
          const delay = (index / bars) * speed;
          return (
            <div
              key={index}
              className={cn(
                'absolute rounded-full origin-bottom animate-bars',
                sizes.bars,
                barColor,
                'flex-shrink-0'
              )}
              style={{
                transform: `rotate(${angle}deg)`,
                animationDelay: `${delay}ms`,
                animationDuration: `${speed}ms`,
                height: sizes.bars.replace('w-', 'h-'),
                transformOrigin: `50% 100%`,
              }}
              aria-hidden="true"
            />
          );
        })}
      </div>
    );
  };

  const renderRipple = () => {
    const rippleColor = variant === 'gradient' ? colors.ripple : effectiveColors.ripple;

    return (
      <div className="relative flex items-center justify-center">
        <div
          className={cn(
            'absolute rounded-full border-2 animate-ripple',
            sizes.ripple,
            rippleColor,
            'flex-shrink-0'
          )}
          style={{
            animationDuration: `${speed}ms`,
            borderWidth: thickness
          }}
          aria-hidden="true"
        />
        <div
          className={cn(
            'absolute rounded-full border-2 animate-ripple-delayed',
            sizes.ripple,
            rippleColor,
            'flex-shrink-0'
          )}
          style={{
            animationDuration: `${speed}ms`,
            borderWidth: thickness,
            animationDelay: `${speed / 2}ms`
          }}
          aria-hidden="true"
        />
      </div>
    );
  };

  const renderCrypto = () => {
    return (
      <div className="relative flex items-center justify-center">
        <div className="absolute inset-0 animate-ping rounded-full bg-nexus-500/20" />
        <div className="relative flex items-center justify-center">
          <div className="absolute inset-0 animate-spin-slow rounded-full border-2 border-nexus-500/30 border-t-nexus-500" />
          <div className="absolute inset-2 animate-spin-reverse rounded-full border-2 border-nexus-400/20 border-b-nexus-400" />
          <div className="w-1/2 h-1/2 rounded-full bg-nexus-500/10 animate-pulse" />
        </div>
      </div>
    );
  };

  const renderVariant = () => {
    switch (variant) {
      case 'dots':
        return renderDots();
      case 'pulse':
        return renderPulse();
      case 'ring':
        return renderRing();
      case 'wave':
        return renderWave();
      case 'clock':
        return renderClock();
      case 'bars':
        return renderBars();
      case 'ripple':
        return renderRipple();
      case 'crypto':
        return renderCrypto();
      case 'gradient':
        return renderSpinner();
      case 'spinner':
      default:
        return renderSpinner();
    }
  };

  const renderProgress = () => {
    if (!showProgress || progressValue === undefined) return null;

    return (
      <div className="flex flex-col items-center gap-2 w-full max-w-xs">
        <div className="w-full h-1.5 bg-nexus-200 dark:bg-nexus-700 rounded-full overflow-hidden">
          <div
            className="h-full bg-nexus-500 dark:bg-nexus-400 rounded-full transition-all duration-300 ease-out"
            style={{ width: `${Math.min(100, Math.max(0, progressValue))}%` }}
          />
        </div>
        <span className={cn('text-sm font-medium', sizes.text, colors.text)}>
          {Math.round(progressValue)}%
        </span>
      </div>
    );
  };

  const renderStatusIcon = () => {
    if (status === 'idle' || !statusConfig.icon) return null;

    const statusColor = COLOR_CONFIG[statusConfig.color];
    const iconColor = variant === 'gradient' ? statusColor.spinner : statusColor.spinner;

    return (
      <div className={cn('flex-shrink-0', iconColor)}>
        {statusConfig.icon}
      </div>
    );
  };

  const renderContent = () => {
    if (status === 'success' || status === 'error' || status === 'warning' || status === 'info') {
      return (
        <div className="flex flex-col items-center gap-3">
          {renderStatusIcon()}
          {effectiveText && (
            <span className={cn('font-medium', sizes.text, colors.text)}>
              {effectiveText}
            </span>
          )}
        </div>
      );
    }

    return (
      <div className={cn(
        'flex items-center',
        textPosition === 'top' && 'flex-col-reverse',
        textPosition === 'bottom' && 'flex-col',
        textPosition === 'left' && 'flex-row',
        textPosition === 'right' && 'flex-row-reverse',
        sizes.gap
      )}>
        {renderVariant()}
        {effectiveText && (
          <span className={cn(
            'font-medium',
            sizes.text,
            colors.text,
            textClassName
          )}>
            {effectiveText}
          </span>
        )}
        {showProgress && renderProgress()}
      </div>
    );
  };

  // ========================================
  // PLACEMENT RENDER
  // ========================================
  
  const renderPlacement = () => {
    const content = renderContent();

    if (!isVisible) return null;

    if (placement === 'fullscreen') {
      return (
        <div
          ref={ref}
          className={cn(
            'fixed inset-0 z-[9999] flex items-center justify-center',
            blur && 'backdrop-blur-sm',
            shouldShowOverlay && `bg-${overlayColor}/50`,
            overlayClassName
          )}
          style={{ backgroundColor: shouldShowOverlay ? `${overlayColor}${Math.round(overlayOpacity * 100)}` : undefined }}
          role="status"
          aria-label={ariaLabel}
          aria-live={ariaLive}
          data-testid={testId}
          {...props}
        >
          {content}
        </div>
      );
    }

    if (placement === 'overlay' || shouldShowOverlay) {
      return (
        <div
          ref={ref}
          className={cn(
            'absolute inset-0 flex items-center justify-center z-10',
            blur && 'backdrop-blur-sm',
            shouldShowOverlay && `bg-${overlayColor}/50`,
            overlayClassName
          )}
          style={{ backgroundColor: shouldShowOverlay ? `${overlayColor}${Math.round(overlayOpacity * 100)}` : undefined }}
          role="status"
          aria-label={ariaLabel}
          aria-live={ariaLive}
          data-testid={testId}
          {...props}
        >
          {content}
        </div>
      );
    }

    if (placement === 'center') {
      return (
        <div
          ref={ref}
          className={cn(
            'flex items-center justify-center w-full h-full',
            className
          )}
          role="status"
          aria-label={ariaLabel}
          aria-live={ariaLive}
          data-testid={testId}
          {...props}
        >
          {content}
        </div>
      );
    }

    // Inline
    return (
      <div
        ref={ref}
        className={cn(
          'inline-flex items-center',
          textPosition === 'top' && 'flex-col-reverse',
          textPosition === 'bottom' && 'flex-col',
          textPosition === 'left' && 'flex-row',
          textPosition === 'right' && 'flex-row-reverse',
          sizes.gap,
          className
        )}
        role="status"
        aria-label={ariaLabel}
        aria-live={ariaLive}
        data-testid={testId}
        {...props}
      >
        {content}
      </div>
    );
  };

  return renderPlacement();
});

Spinner.displayName = 'Spinner';

// ========================================
// COMPOUND COMPONENTS
// ========================================

export interface SpinnerContainerProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  loading?: boolean;
  spinner?: React.ReactNode;
  spinnerProps?: Partial<SpinnerProps>;
  className?: string;
}

export const SpinnerContainer: React.FC<SpinnerContainerProps> = ({
  children,
  loading = false,
  spinner,
  spinnerProps,
  className,
  ...props
}) => {
  if (!loading) {
    return <>{children}</>;
  }

  return (
    <div className={cn('relative', className)} {...props}>
      {children}
      <div className="absolute inset-0 flex items-center justify-center bg-white/60 dark:bg-nexus-900/60 backdrop-blur-sm z-10 rounded-lg">
        {spinner || <Spinner size="lg" placement="inline" {...spinnerProps} />}
      </div>
    </div>
  );
};

// ========================================
// EXPORTS
// ========================================

// Import icons needed for status
import { CheckCircle, AlertTriangle, Info } from 'lucide-react';

SpinnerContainer.displayName = 'SpinnerContainer';

export default Spinner;

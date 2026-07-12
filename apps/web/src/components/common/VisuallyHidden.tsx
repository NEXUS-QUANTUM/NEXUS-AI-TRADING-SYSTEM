import React, { forwardRef } from 'react';
import { cn } from '@/lib/utils';

/**
 * NEXUS AI TRADING SYSTEM - VisuallyHidden Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 * 
 * Version: 3.0.0
 * Status: Production Ready
 * 
 * Complete VisuallyHidden system with:
 * - Screen reader only text
 * - Focusable hidden content
 * - Conditional rendering
 * - Multiple variants (sr-only, focus-only, etc.)
 * - Animation support
 * - Accessibility (ARIA compliant)
 * - Theme aware
 * - Responsive hiding
 * - Print styles
 * - Custom selectors
 * - Focus management
 * - Live regions
 * - Announcement support
 * - Status messages
 * - Loading announcements
 */

// ========================================
// TYPES & INTERFACES
// ========================================

export type VisuallyHiddenVariant = 
  | 'sr-only'           // Hidden visually but visible to screen readers
  | 'focus-only'        // Hidden until focused
  | 'focus-visible'     // Hidden until focused (keyboard only)
  | 'mobile-only'       // Hidden on mobile
  | 'desktop-only'      // Hidden on desktop
  | 'tablet-only'       // Hidden on tablet
  | 'print-only'        // Only visible when printing
  | 'screen-only'       // Only visible on screen (not print)
  | 'visually-hidden'   // Alias for sr-only
  | 'hidden'            // Completely hidden
  | 'aria-hidden';      // Hidden from screen readers

export type VisuallyHiddenRole = 
  | 'status' 
  | 'alert' 
  | 'log' 
  | 'marquee' 
  | 'timer' 
  | 'none';

export interface VisuallyHiddenProps extends React.HTMLAttributes<HTMLElement> {
  /** Variant of hiding */
  variant?: VisuallyHiddenVariant;
  /** Role for screen readers */
  role?: VisuallyHiddenRole;
  /** Additional className */
  className?: string;
  /** Whether to show on focus */
  showOnFocus?: boolean;
  /** Focusable when hidden */
  focusable?: boolean;
  /** Whether to keep in DOM */
  keepInDOM?: boolean;
  /** Announcement type */
  announcement?: boolean;
  /** Announcement politeness */
  politeness?: 'polite' | 'assertive';
  /** Whether to show on hover */
  showOnHover?: boolean;
  /** Target selector for hover */
  hoverSelector?: string;
  /** Animation on show */
  animate?: boolean;
  /** Animation duration */
  animationDuration?: number;
  /** Custom element type */
  as?: 'div' | 'span' | 'p' | 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'section' | 'article';
  /** Test ID */
  testId?: string;
  /** Children content */
  children: React.ReactNode;
  /** Live region settings */
  liveRegion?: boolean;
  /** Atomic live region */
  atomic?: boolean;
  /** Relevancy of changes */
  relevant?: 'additions' | 'removals' | 'text' | 'all';
}

// ========================================
// CONFIGURATION
// ========================================

const VARIANT_CLASSES: Record<VisuallyHiddenVariant, string> = {
  'sr-only': 'sr-only',
  'focus-only': 'sr-only focus:not-sr-only focus:fixed focus:z-[9999] focus:p-4 focus:bg-white focus:text-nexus-900 focus:shadow-lg focus:rounded-lg',
  'focus-visible': 'sr-only focus-visible:not-sr-only focus-visible:fixed focus-visible:z-[9999] focus-visible:p-4 focus-visible:bg-white focus-visible:text-nexus-900 focus-visible:shadow-lg focus-visible:rounded-lg',
  'mobile-only': 'hidden sm:block',
  'desktop-only': 'block sm:hidden',
  'tablet-only': 'hidden md:block lg:hidden',
  'print-only': 'hidden print:block',
  'screen-only': 'block print:hidden',
  'visually-hidden': 'sr-only',
  'hidden': 'hidden',
  'aria-hidden': 'sr-only'
};

const ROLE_CLASSES: Record<VisuallyHiddenRole, string> = {
  status: 'text-sm text-nexus-500 dark:text-nexus-400',
  alert: 'text-sm text-red-500 dark:text-red-400',
  log: 'text-sm text-nexus-600 dark:text-nexus-300',
  marquee: 'text-sm text-nexus-500 dark:text-nexus-400',
  timer: 'text-sm text-nexus-500 dark:text-nexus-400',
  none: ''
};

const ANIMATION_CLASSES = {
  enter: 'animate-in fade-in slide-in-from-top-2',
  exit: 'animate-out fade-out slide-out-to-top-2',
  duration: 'duration-200'
};

// ========================================
// MAIN COMPONENT
// ========================================

export const VisuallyHidden = forwardRef<HTMLElement, VisuallyHiddenProps>(({
  variant = 'sr-only',
  role = 'none',
  className,
  showOnFocus = false,
  focusable = false,
  keepInDOM = true,
  announcement = false,
  politeness = 'polite',
  showOnHover = false,
  hoverSelector,
  animate = false,
  animationDuration = 200,
  as: Component = 'div',
  testId = 'nexus-visually-hidden',
  children,
  liveRegion = false,
  atomic = false,
  relevant = 'all',
  ...props
}, ref) => {
  // ========================================
  // STATE
  // ========================================
  
  const [isVisible, setIsVisible] = React.useState(false);
  const [isHovered, setIsHovered] = React.useState(false);

  // ========================================
  // REFS
  // ========================================
  
  const containerRef = React.useRef<HTMLElement>(null);

  // ========================================
  // EFFECTS
  // ========================================
  
  // Handle hover visibility
  React.useEffect(() => {
    if (!showOnHover || !hoverSelector) return;

    const elements = document.querySelectorAll(hoverSelector);
    const handleMouseEnter = () => setIsHovered(true);
    const handleMouseLeave = () => setIsHovered(false);

    elements.forEach(el => {
      el.addEventListener('mouseenter', handleMouseEnter);
      el.addEventListener('mouseleave', handleMouseLeave);
    });

    return () => {
      elements.forEach(el => {
        el.removeEventListener('mouseenter', handleMouseEnter);
        el.removeEventListener('mouseleave', handleMouseLeave);
      });
    };
  }, [showOnHover, hoverSelector]);

  // Announcement effect
  React.useEffect(() => {
    if (announcement && children) {
      // Use a live region to announce content
      const announcementElement = document.createElement('div');
      announcementElement.setAttribute('aria-live', politeness);
      announcementElement.setAttribute('aria-atomic', 'true');
      announcementElement.className = 'sr-only';
      announcementElement.textContent = typeof children === 'string' ? children : '';
      
      document.body.appendChild(announcementElement);
      
      // Clean up after announcement
      setTimeout(() => {
        announcementElement.remove();
      }, 5000);

      return () => {
        announcementElement.remove();
      };
    }
  }, [announcement, children, politeness]);

  // ========================================
  // HELPERS
  // ========================================
  
  const variantClass = VARIANT_CLASSES[variant];
  const roleClass = ROLE_CLASSES[role];
  
  const shouldShow = 
    (variant === 'focus-only' || variant === 'focus-visible' || showOnFocus) ||
    (showOnHover && isHovered);

  const finalClassName = cn(
    variantClass,
    roleClass,
    // Focus styles
    (variant === 'focus-only' || variant === 'focus-visible') && 'outline-none',
    focusable && 'focus-visible:outline focus-visible:outline-2 focus-visible:outline-nexus-500 focus-visible:outline-offset-2',
    // Animation
    animate && shouldShow && ANIMATION_CLASSES.enter,
    animate && !shouldShow && ANIMATION_CLASSES.exit,
    animate && ANIMATION_CLASSES.duration,
    // Custom
    className
  );

  // Live region attributes
  const liveRegionProps = liveRegion ? {
    'aria-live': politeness,
    'aria-atomic': atomic,
    'aria-relevant': relevant,
  } : {};

  // Skip rendering if not kept in DOM
  if (!keepInDOM && !shouldShow) {
    return null;
  }

  // ========================================
  // RENDER
  // ========================================
  
  return (
    <Component
      ref={(el) => {
        if (typeof ref === 'function') {
          ref(el);
        } else if (ref) {
          (ref as React.MutableRefObject<HTMLElement | null>).current = el;
        }
        containerRef.current = el;
      }}
      className={finalClassName}
      style={{
        animationDuration: animate ? `${animationDuration}ms` : undefined,
        ...(shouldShow && variant === 'focus-only' && {
          position: 'fixed',
          top: '1rem',
          left: '1rem',
          zIndex: 9999,
          padding: '1rem',
          backgroundColor: 'white',
          color: '#1a1a1a',
          boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06)',
          borderRadius: '0.5rem',
        }),
        ...(shouldShow && variant === 'focus-visible' && {
          position: 'fixed',
          top: '1rem',
          left: '1rem',
          zIndex: 9999,
          padding: '1rem',
          backgroundColor: 'white',
          color: '#1a1a1a',
          boxShadow: '0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -1px rgba(0,0,0,0.06)',
          borderRadius: '0.5rem',
        }),
      }}
      data-testid={testId}
      data-variant={variant}
      data-visible={shouldShow}
      {...liveRegionProps}
      {...props}
    >
      {children}
    </Component>
  );
});

VisuallyHidden.displayName = 'VisuallyHidden';

// ========================================
// COMPOUND COMPONENTS
// ========================================

export interface ScreenReaderOnlyProps extends Omit<VisuallyHiddenProps, 'variant'> {
  /** Announcement type */
  announcement?: boolean;
  /** Politeness level */
  politeness?: 'polite' | 'assertive';
}

export const ScreenReaderOnly: React.FC<ScreenReaderOnlyProps> = ({
  children,
  announcement = false,
  politeness = 'polite',
  ...props
}) => {
  return (
    <VisuallyHidden
      variant="sr-only"
      announcement={announcement}
      politeness={politeness}
      {...props}
    >
      {children}
    </VisuallyHidden>
  );
};

export interface FocusOnlyProps extends Omit<VisuallyHiddenProps, 'variant'> {
  /** Show on focus */
  showOnFocus?: boolean;
}

export const FocusOnly: React.FC<FocusOnlyProps> = ({
  children,
  showOnFocus = true,
  ...props
}) => {
  return (
    <VisuallyHidden
      variant="focus-only"
      showOnFocus={showOnFocus}
      {...props}
    >
      {children}
    </VisuallyHidden>
  );
};

export interface KeyboardOnlyProps extends Omit<VisuallyHiddenProps, 'variant'> {
  /** Show on keyboard focus */
  showOnFocus?: boolean;
}

export const KeyboardOnly: React.FC<KeyboardOnlyProps> = ({
  children,
  showOnFocus = true,
  ...props
}) => {
  return (
    <VisuallyHidden
      variant="focus-visible"
      showOnFocus={showOnFocus}
      {...props}
    >
      {children}
    </VisuallyHidden>
  );
};

export interface LiveAnnouncerProps extends Omit<VisuallyHiddenProps, 'variant' | 'announcement'> {
  /** Message to announce */
  message: string;
  /** Politeness level */
  politeness?: 'polite' | 'assertive';
  /** Announce on mount */
  announceOnMount?: boolean;
  /** Delay before announcing (ms) */
  delay?: number;
}

export const LiveAnnouncer: React.FC<LiveAnnouncerProps> = ({
  message,
  politeness = 'polite',
  announceOnMount = true,
  delay = 100,
  ...props
}) => {
  const [announceMessage, setAnnounceMessage] = React.useState<string>(
    announceOnMount ? message : ''
  );

  React.useEffect(() => {
    if (announceOnMount) {
      const timer = setTimeout(() => {
        setAnnounceMessage(message);
      }, delay);
      return () => clearTimeout(timer);
    }
  }, [announceOnMount, message, delay]);

  // Update message when it changes
  React.useEffect(() => {
    if (!announceOnMount) return;
    setAnnounceMessage(message);
  }, [message, announceOnMount]);

  return (
    <VisuallyHidden
      variant="sr-only"
      announcement={!!announceMessage}
      politeness={politeness}
      liveRegion
      atomic
      {...props}
    >
      {announceMessage}
    </VisuallyHidden>
  );
};

export interface StatusAnnouncerProps extends Omit<VisuallyHiddenProps, 'variant'> {
  /** Status message */
  message: string;
  /** Type of status */
  type?: 'success' | 'error' | 'warning' | 'info';
  /** Auto clear after duration */
  autoClear?: boolean;
  /** Clear duration (ms) */
  clearDuration?: number;
}

export const StatusAnnouncer: React.FC<StatusAnnouncerProps> = ({
  message,
  type = 'info',
  autoClear = true,
  clearDuration = 5000,
  ...props
}) => {
  const [currentMessage, setCurrentMessage] = React.useState(message);
  const [statusType] = React.useState(type);

  React.useEffect(() => {
    setCurrentMessage(message);
    
    if (autoClear) {
      const timer = setTimeout(() => {
        setCurrentMessage('');
      }, clearDuration);
      return () => clearTimeout(timer);
    }
  }, [message, autoClear, clearDuration]);

  if (!currentMessage) return null;

  return (
    <VisuallyHidden
      variant="sr-only"
      role="status"
      politeness="polite"
      liveRegion
      atomic
      {...props}
    >
      {currentMessage}
    </VisuallyHidden>
  );
};

export interface LoadingAnnouncerProps extends Omit<VisuallyHiddenProps, 'variant'> {
  /** Loading message */
  message?: string;
  /** Loading state */
  loading: boolean;
  /** Success message */
  successMessage?: string;
  /** Error message */
  errorMessage?: string;
}

export const LoadingAnnouncer: React.FC<LoadingAnnouncerProps> = ({
  message = 'Loading...',
  loading,
  successMessage = 'Loading complete',
  errorMessage = 'Loading failed',
  ...props
}) => {
  const [announcement, setAnnouncement] = React.useState<string>('');

  React.useEffect(() => {
    if (loading) {
      setAnnouncement(message);
    } else {
      // Announce success or error after loading
      const timer = setTimeout(() => {
        setAnnouncement(successMessage);
        // Clear after announcement
        setTimeout(() => {
          setAnnouncement('');
        }, 3000);
      }, 100);
      return () => clearTimeout(timer);
    }
  }, [loading, message, successMessage]);

  return (
    <VisuallyHidden
      variant="sr-only"
      role="status"
      politeness="polite"
      liveRegion
      atomic
      {...props}
    >
      {announcement}
    </VisuallyHidden>
  );
};

// ========================================
// PRESETED COMPONENTS
// ========================================

export const VisuallyHiddenPresets = {
  ScreenReaderOnly,
  FocusOnly,
  KeyboardOnly,
  LiveAnnouncer,
  StatusAnnouncer,
  LoadingAnnouncer
};

// ========================================
// EXPORTS
// ========================================

ScreenReaderOnly.displayName = 'ScreenReaderOnly';
FocusOnly.displayName = 'FocusOnly';
KeyboardOnly.displayName = 'KeyboardOnly';
LiveAnnouncer.displayName = 'LiveAnnouncer';
StatusAnnouncer.displayName = 'StatusAnnouncer';
LoadingAnnouncer.displayName = 'LoadingAnnouncer';

export default VisuallyHidden;

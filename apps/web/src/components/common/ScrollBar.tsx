// apps/web/src/components/common/ScrollBar.tsx
'use client';

import React, {
  ReactNode,
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
  forwardRef,
  Ref,
  createContext,
  useContext,
  useId,
  UIEvent,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence, MotionConfig } from 'framer-motion';
import {
  ChevronUpIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  DoubleArrowUpIcon,
  DoubleArrowDownIcon,
  DoubleArrowLeftIcon,
  DoubleArrowRightIcon,
  GripHorizontalIcon,
  GripVerticalIcon,
} from '@radix-ui/react-icons';
import { Button } from '@/components/common/Button';
import { Tooltip } from '@/components/common/Tooltip';

// ============================================================================
// TYPES
// ============================================================================

export type ScrollBarOrientation = 'vertical' | 'horizontal';
export type ScrollBarSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
export type ScrollBarVariant = 'default' | 'minimal' | 'rounded' | 'outlined' | 'ghost' | 'gradient';
export type ScrollBarVisibility = 'auto' | 'always' | 'hover' | 'hidden';
export type ScrollBarPosition = 'inside' | 'outside' | 'overlay' | 'none';

export interface ScrollBarProps {
  // --- Contrôle ---
  /** Valeur de défilement (0-100) */
  value?: number;
  /** Valeur par défaut */
  defaultValue?: number;
  /** Valeur maximale */
  maxValue?: number;
  /** Callback lors du changement */
  onChange?: (value: number) => void;
  /** Callback lors du début du drag */
  onDragStart?: () => void;
  /** Callback lors de la fin du drag */
  onDragEnd?: () => void;

  // --- Apparence ---
  /** Orientation de la barre */
  orientation?: ScrollBarOrientation;
  /** Taille de la barre */
  size?: ScrollBarSize;
  /** Variante d'affichage */
  variant?: ScrollBarVariant;
  /** Visibilité */
  visibility?: ScrollBarVisibility;
  /** Position */
  position?: ScrollBarPosition;
  /** Couleur de la barre */
  barColor?: string;
  /** Couleur de la piste */
  trackColor?: string;
  /** Épaisseur de la barre */
  thickness?: number;
  /** Rayon de bordure */
  radius?: string | number;
  /** Longueur de la barre (pourcentage) */
  barLength?: number;
  /** Classes additionnelles */
  className?: string;
  /** Classes pour la piste */
  trackClassName?: string;
  /** Classes pour la barre */
  barClassName?: string;

  // --- Comportement ---
  /** Désactiver la barre */
  disabled?: boolean;
  /** Délai avant la disparition (ms) */
  hideDelay?: number;
  /** Désactiver l'animation */
  disableAnimation?: boolean;
  /** Désactiver le drag */
  disableDrag?: boolean;
  /** Désactiver les boutons */
  disableButtons?: boolean;
  /** Pas de défilement */
  step?: number;
  /** Pas de défilement rapide */
  largeStep?: number;
  /** Auto-hide */
  autoHide?: boolean;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ARIA describedby */
  ariaDescribedby?: string;
  /** ID */
  id?: string;

  // --- Avancé ---
  /** Container ref pour le calcul de taille */
  containerRef?: React.RefObject<HTMLElement>;
  /** Observer le container */
  observeContainer?: boolean;
  /** Callback lors du hover */
  onHover?: (hovered: boolean) => void;
  /** Callback lors du focus */
  onFocus?: (focused: boolean) => void;
}

// ============================================================================
// CONTEXT
// ============================================================================

interface ScrollBarContextType {
  orientation: ScrollBarOrientation;
  size: ScrollBarSize;
  variant: ScrollBarVariant;
  disabled: boolean;
  value: number;
  maxValue: number;
  onChange: (value: number) => void;
  isDragging: boolean;
}

const ScrollBarContext = createContext<ScrollBarContextType | null>(null);

export const useScrollBarContext = () => {
  const context = useContext(ScrollBarContext);
  if (!context) {
    throw new Error('useScrollBarContext must be used within a ScrollBar');
  }
  return context;
};

// ============================================================================
// COMPOSANTS INTERNES
// ============================================================================

// --- Boutons de navigation ---
interface NavButtonProps {
  direction: 'up' | 'down' | 'left' | 'right';
  onClick: () => void;
  disabled?: boolean;
  className?: string;
  icon?: ReactNode;
}

const NavButton: React.FC<NavButtonProps> = ({
  direction,
  onClick,
  disabled = false,
  className,
  icon,
}) => {
  const context = useScrollBarContext();
  const { size, variant } = context;

  const sizeMap = {
    xs: 'h-4 w-4 text-[10px]',
    sm: 'h-5 w-5 text-xs',
    md: 'h-6 w-6 text-sm',
    lg: 'h-7 w-7 text-base',
    xl: 'h-8 w-8 text-lg',
  };

  const variantClasses = {
    default: 'bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300',
    minimal: 'bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 dark:text-gray-500',
    rounded: 'bg-gray-100 hover:bg-gray-200 dark:bg-gray-800 dark:hover:bg-gray-700 text-gray-600 dark:text-gray-300 rounded-full',
    outlined: 'border border-gray-300 dark:border-gray-600 bg-transparent hover:bg-gray-50 dark:hover:bg-gray-800 text-gray-600 dark:text-gray-300',
    ghost: 'bg-transparent hover:bg-gray-100 dark:hover:bg-gray-800 text-gray-400 dark:text-gray-500',
    gradient: 'bg-gradient-to-b from-gray-100 to-gray-200 dark:from-gray-800 dark:to-gray-700 text-gray-600 dark:text-gray-300',
  };

  const defaultIcons = {
    up: <ChevronUpIcon className="h-3 w-3" />,
    down: <ChevronDownIcon className="h-3 w-3" />,
    left: <ChevronLeftIcon className="h-3 w-3" />,
    right: <ChevronRightIcon className="h-3 w-3" />,
  };

  const finalIcon = icon || defaultIcons[direction];

  return (
    <button
      className={cn(
        'flex items-center justify-center rounded transition-colors focus:outline-none focus:ring-2 focus:ring-brand-500/50 disabled:opacity-30 disabled:cursor-not-allowed',
        sizeMap[size],
        variantClasses[variant],
        className
      )}
      onClick={onClick}
      disabled={disabled}
      aria-label={`Défiler vers ${direction}`}
      type="button"
    >
      {finalIcon}
    </button>
  );
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const ScrollBar = forwardRef<HTMLDivElement, ScrollBarProps>(
  (props, ref) => {
    const {
      // Contrôle
      value: externalValue,
      defaultValue = 0,
      maxValue = 100,
      onChange,
      onDragStart,
      onDragEnd,

      // Apparence
      orientation = 'vertical',
      size = 'md',
      variant = 'default',
      visibility = 'auto',
      position = 'inside',
      barColor,
      trackColor,
      thickness,
      radius,
      barLength = 100,
      className,
      trackClassName,
      barClassName,

      // Comportement
      disabled = false,
      hideDelay = 1000,
      disableAnimation = false,
      disableDrag = false,
      disableButtons = false,
      step = 1,
      largeStep = 10,
      autoHide = true,

      // Accessibilité
      ariaLabel = 'Barre de défilement',
      ariaDescribedby,
      id,

      // Avancé
      containerRef: externalContainerRef,
      observeContainer = false,
      onHover,
      onFocus,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const containerRef = useRef<HTMLDivElement>(null);
    const trackRef = useRef<HTMLDivElement>(null);
    const barRef = useRef<HTMLDivElement>(null);
    const dragRef = useRef<{ startY: number; startX: number; value: number } | null>(null);
    const hideTimeoutRef = useRef<NodeJS.Timeout | null>(null);
    const uniqueId = useId();
    const scrollId = id || `nexus-scrollbar-${uniqueId}`;

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalValue, setInternalValue] = useState(defaultValue);
    const [isDragging, setIsDragging] = useState(false);
    const [isHovered, setIsHovered] = useState(false);
    const [isFocused, setIsFocused] = useState(false);
    const [isVisible, setIsVisible] = useState(true);
    const [trackSize, setTrackSize] = useState(0);
    const [barSize, setBarSize] = useState(0);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined ? externalValue : internalValue;
    const isControlled = externalValue !== undefined;
    const clampedValue = Math.max(0, Math.min(maxValue, value));
    const percentage = maxValue > 0 ? (clampedValue / maxValue) * 100 : 0;
    const isVertical = orientation === 'vertical';

    // ========================================================================
    // CALCUL DES TAILLES
    // ========================================================================

    const updateTrackSize = useCallback(() => {
      const track = trackRef.current;
      if (!track) return;

      const rect = track.getBoundingClientRect();
      const newSize = isVertical ? rect.height : rect.width;
      setTrackSize(newSize);

      // Calculer la taille de la barre
      const barLengthPercent = Math.min(100, (100 / (maxValue + 1)) * 100);
      const newBarSize = (barLengthPercent / 100) * newSize;
      setBarSize(Math.max(20, newBarSize));
    }, [isVertical, maxValue]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateValue = useCallback((newValue: number) => {
      const clamped = Math.max(0, Math.min(maxValue, newValue));

      if (isControlled) {
        if (onChange) onChange(clamped);
      } else {
        setInternalValue(clamped);
        if (onChange) onChange(clamped);
      }
    }, [isControlled, maxValue, onChange]);

    // ========================================================================
    // NAVIGATION
    // ========================================================================

    const stepUp = useCallback(() => updateValue(clampedValue + step), [clampedValue, step, updateValue]);
    const stepDown = useCallback(() => updateValue(clampedValue - step), [clampedValue, step, updateValue]);
    const stepLeft = useCallback(() => updateValue(clampedValue - step), [clampedValue, step, updateValue]);
    const stepRight = useCallback(() => updateValue(clampedValue + step), [clampedValue, step, updateValue]);

    const largeStepUp = useCallback(() => updateValue(clampedValue + largeStep), [clampedValue, largeStep, updateValue]);
    const largeStepDown = useCallback(() => updateValue(clampedValue - largeStep), [clampedValue, largeStep, updateValue]);
    const largeStepLeft = useCallback(() => updateValue(clampedValue - largeStep), [clampedValue, largeStep, updateValue]);
    const largeStepRight = useCallback(() => updateValue(clampedValue + largeStep), [clampedValue, largeStep, updateValue]);

    const goToStart = useCallback(() => updateValue(0), [updateValue]);
    const goToEnd = useCallback(() => updateValue(maxValue), [maxValue, updateValue]);

    // ========================================================================
    // DRAG
    // ========================================================================

    const handleDragStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
      if (disabled || disableDrag) return;

      const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
      const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;

      dragRef.current = {
        startY: clientY,
        startX: clientX,
        value: clampedValue,
      };

      setIsDragging(true);
      onDragStart?.();

      document.body.style.userSelect = 'none';
      document.body.style.cursor = isVertical ? 'ns-resize' : 'ew-resize';
    }, [disabled, disableDrag, clampedValue, isVertical, onDragStart]);

    const handleDragMove = useCallback((e: MouseEvent | TouchEvent) => {
      if (!dragRef.current || !trackRef.current) return;

      const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
      const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;

      const trackRect = trackRef.current.getBoundingClientRect();
      const trackSize = isVertical ? trackRect.height : trackRect.width;

      const delta = isVertical ? clientY - dragRef.current.startY : clientX - dragRef.current.startX;
      const deltaPercent = delta / trackSize;
      const deltaValue = deltaPercent * maxValue;

      const newValue = Math.max(0, Math.min(maxValue, dragRef.current.value + deltaValue));
      updateValue(newValue);
    }, [isVertical, maxValue, updateValue]);

    const handleDragEnd = useCallback(() => {
      dragRef.current = null;
      setIsDragging(false);
      onDragEnd?.();

      document.body.style.userSelect = '';
      document.body.style.cursor = '';
    }, [onDragEnd]);

    // ========================================================================
    // CLIC SUR LA PISTE
    // ========================================================================

    const handleTrackClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
      if (disabled || disableDrag) return;

      const track = trackRef.current;
      if (!track) return;

      const rect = track.getBoundingClientRect();
      const clickPos = isVertical ? e.clientY - rect.top : e.clientX - rect.left;
      const clickPercent = clickPos / (isVertical ? rect.height : rect.width);
      const newValue = clickPercent * maxValue;

      updateValue(newValue);
    }, [disabled, disableDrag, isVertical, maxValue, updateValue]);

    // ========================================================================
    // VISIBILITÉ
    // ========================================================================

    const showBar = useCallback(() => {
      setIsVisible(true);
      if (hideTimeoutRef.current) {
        clearTimeout(hideTimeoutRef.current);
        hideTimeoutRef.current = null;
      }
    }, []);

    const hideBar = useCallback(() => {
      if (autoHide && visibility === 'auto' && !isHovered && !isFocused && !isDragging) {
        hideTimeoutRef.current = setTimeout(() => {
          setIsVisible(false);
        }, hideDelay);
      }
    }, [autoHide, visibility, isHovered, isFocused, isDragging, hideDelay]);

    // ========================================================================
    // EFFETS
    // ========================================================================

    // Mise à jour de la taille
    useEffect(() => {
      updateTrackSize();

      if (observeContainer) {
        const container = externalContainerRef?.current || containerRef.current?.parentElement;
        if (container && typeof ResizeObserver !== 'undefined') {
          const observer = new ResizeObserver(updateTrackSize);
          observer.observe(container);
          return () => observer.disconnect();
        }
      }
    }, [updateTrackSize, observeContainer, externalContainerRef]);

    // Événements de drag globaux
    useEffect(() => {
      if (!isDragging) return;

      const handleMouseMove = (e: MouseEvent) => handleDragMove(e);
      const handleTouchMove = (e: TouchEvent) => handleDragMove(e);
      const handleEnd = () => handleDragEnd();

      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleEnd);
      window.addEventListener('touchmove', handleTouchMove, { passive: false });
      window.addEventListener('touchend', handleEnd);

      return () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleEnd);
        window.removeEventListener('touchmove', handleTouchMove);
        window.removeEventListener('touchend', handleEnd);
      };
    }, [isDragging, handleDragMove, handleDragEnd]);

    // Auto-hide
    useEffect(() => {
      if (visibility === 'always') {
        setIsVisible(true);
        return;
      }

      if (visibility === 'hidden') {
        setIsVisible(false);
        return;
      }

      if (isDragging || isHovered || isFocused) {
        showBar();
      } else {
        hideBar();
      }

      return () => {
        if (hideTimeoutRef.current) {
          clearTimeout(hideTimeoutRef.current);
        }
      };
    }, [visibility, isDragging, isHovered, isFocused, showBar, hideBar]);

    // ========================================================================
    // CONTEXT
    // ========================================================================

    const contextValue = useMemo<ScrollBarContextType>(
      () => ({
        orientation,
        size,
        variant,
        disabled,
        value: clampedValue,
        maxValue,
        onChange: updateValue,
        isDragging,
      }),
      [orientation, size, variant, disabled, clampedValue, maxValue, updateValue, isDragging]
    );

    // ========================================================================
    // STYLES
    // ========================================================================

    const sizeMap = {
      xs: { track: 'w-2 h-2', bar: 'w-1.5 h-1.5' },
      sm: { track: 'w-2.5 h-2.5', bar: 'w-2 h-2' },
      md: { track: 'w-3 h-3', bar: 'w-2.5 h-2.5' },
      lg: { track: 'w-4 h-4', bar: 'w-3 h-3' },
      xl: { track: 'w-5 h-5', bar: 'w-4 h-4' },
    };

    const variantClasses = {
      default: {
        track: 'bg-gray-200 dark:bg-gray-700',
        bar: 'bg-gray-400 hover:bg-gray-500 dark:bg-gray-500 dark:hover:bg-gray-400',
      },
      minimal: {
        track: 'bg-transparent',
        bar: 'bg-gray-300 hover:bg-gray-400 dark:bg-gray-600 dark:hover:bg-gray-500',
      },
      rounded: {
        track: 'bg-gray-200 dark:bg-gray-700 rounded-full',
        bar: 'bg-gray-400 hover:bg-gray-500 dark:bg-gray-500 dark:hover:bg-gray-400 rounded-full',
      },
      outlined: {
        track: 'border border-gray-300 dark:border-gray-600 bg-transparent',
        bar: 'bg-gray-400 hover:bg-gray-500 dark:bg-gray-500 dark:hover:bg-gray-400',
      },
      ghost: {
        track: 'bg-transparent',
        bar: 'bg-gray-300 hover:bg-gray-400 dark:bg-gray-700 dark:hover:bg-gray-600',
      },
      gradient: {
        track: 'bg-gray-200 dark:bg-gray-700',
        bar: 'bg-gradient-to-b from-gray-400 to-gray-500 dark:from-gray-500 dark:to-gray-400',
      },
    };

    const variantStyles = variantClasses[variant] || variantClasses.default;

    const trackStyles: React.CSSProperties = {
      ...(trackColor && { backgroundColor: trackColor }),
      ...(thickness && {
        [isVertical ? 'width' : 'height']: thickness,
      }),
      ...(radius && { borderRadius: radius }),
    };

    const barStyles: React.CSSProperties = {
      ...(barColor && { backgroundColor: barColor }),
      ...(thickness && {
        [isVertical ? 'width' : 'height']: thickness - 2,
      }),
      ...(radius && { borderRadius: radius }),
    };

    // Position de la barre
    const barPosition = isVertical
      ? { top: `${percentage}%` }
      : { left: `${percentage}%` };

    // Taille de la barre
    const barSizePercent = Math.min(100, Math.max(10, (barLength / 100) * 100));
    const barLengthStyle = isVertical
      ? { height: `${barSizePercent}%` }
      : { width: `${barSizePercent}%` };

    // ========================================================================
    // RENDU DES BOUTONS
    // ========================================================================

    const renderButtons = () => {
      if (disableButtons) return null;

      const navButtons = isVertical
        ? [
            { dir: 'up' as const, onClick: stepUp, icon: <ArrowUpIcon className="h-3 w-3" /> },
            { dir: 'down' as const, onClick: stepDown, icon: <ArrowDownIcon className="h-3 w-3" /> },
          ]
        : [
            { dir: 'left' as const, onClick: stepLeft, icon: <ArrowLeftIcon className="h-3 w-3" /> },
            { dir: 'right' as const, onClick: stepRight, icon: <ArrowRightIcon className="h-3 w-3" /> },
          ];

      return (
        <div
          className={cn(
            'flex',
            isVertical ? 'flex-col' : 'flex-row',
            isVertical ? 'gap-0.5' : 'gap-0.5'
          )}
        >
          {navButtons.map((btn) => (
            <NavButton
              key={btn.dir}
              direction={btn.dir}
              onClick={btn.onClick}
              disabled={disabled}
              icon={btn.icon}
            />
          ))}
        </div>
      );
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const isVisibleState = visibility === 'always' ? true : isVisible;
    const shouldRender = isVisibleState && !disabled;

    if (!shouldRender) {
      return (
        <div
          ref={ref}
          id={scrollId}
          className="hidden"
          aria-hidden="true"
        />
      );
    }

    return (
      <ScrollBarContext.Provider value={contextValue}>
        <div
          ref={(node) => {
            if (typeof ref === 'function') ref(node);
            else if (ref) ref.current = node;
            containerRef.current = node;
          }}
          id={scrollId}
          className={cn(
            'flex touch-none select-none transition-opacity duration-200',
            isVertical ? 'flex-col' : 'flex-row',
            position === 'inside' && isVertical && 'right-0 top-0 h-full',
            position === 'inside' && !isVertical && 'bottom-0 left-0 w-full',
            position === 'outside' && isVertical && '-right-1 top-0 h-full',
            position === 'outside' && !isVertical && '-bottom-1 left-0 w-full',
            position === 'overlay' && 'absolute pointer-events-none',
            position === 'none' && 'hidden',
            className
          )}
          style={{
            opacity: isVisibleState ? 1 : 0,
          }}
          onMouseEnter={() => {
            setIsHovered(true);
            onHover?.(true);
          }}
          onMouseLeave={() => {
            setIsHovered(false);
            onHover?.(false);
          }}
          onFocus={() => {
            setIsFocused(true);
            onFocus?.(true);
          }}
          onBlur={() => {
            setIsFocused(false);
            onFocus?.(false);
          }}
          role="scrollbar"
          aria-label={ariaLabel}
          aria-describedby={ariaDescribedby}
          aria-valuenow={clampedValue}
          aria-valuemin={0}
          aria-valuemax={maxValue}
          aria-orientation={orientation}
          tabIndex={disabled ? -1 : 0}
        >
          {/* Piste */}
          <div
            ref={trackRef}
            className={cn(
              'relative flex-1',
              sizeMap[size]?.track,
              variantStyles.track,
              position === 'overlay' && 'pointer-events-auto',
              trackClassName
            )}
            style={trackStyles}
            onClick={handleTrackClick}
          >
            {/* Barre */}
            <div
              ref={barRef}
              className={cn(
                'absolute transition-all',
                variantStyles.bar,
                sizeMap[size]?.bar,
                position === 'overlay' && 'pointer-events-auto',
                barClassName
              )}
              style={{
                ...barStyles,
                ...barPosition,
                ...barLengthStyle,
                ...(disableAnimation ? {} : {
                  transition: isDragging ? 'none' : 'top 0.15s ease, left 0.15s ease',
                }),
              }}
              onMouseDown={handleDragStart}
              onTouchStart={handleDragStart}
              role="slider"
              aria-orientation={orientation}
              aria-valuenow={clampedValue}
              aria-valuemin={0}
              aria-valuemax={maxValue}
              tabIndex={disabled || disableDrag ? -1 : 0}
            >
              {/* Grip pour l'accessibilité visuelle */}
              <div
                className={cn(
                  'absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity',
                  isVertical ? 'flex-col' : 'flex-row'
                )}
              >
                {isVertical ? (
                  <GripVerticalIcon className="h-3 w-3 text-white/50" />
                ) : (
                  <GripHorizontalIcon className="h-3 w-3 text-white/50" />
                )}
              </div>
            </div>
          </div>

          {/* Boutons de navigation */}
          {renderButtons()}
        </div>
      </ScrollBarContext.Provider>
    );
  }
);

ScrollBar.displayName = 'ScrollBar';

// ============================================================================
// SOUS-COMPOSANTS
// ============================================================================

// --- ScrollBar.Thumb ---
interface ScrollThumbProps {
  children?: ReactNode;
  className?: string;
}

export const ScrollThumb: React.FC<ScrollThumbProps> = ({
  children,
  className,
}) => {
  const context = useScrollBarContext();
  const { orientation, size, variant } = context;

  return (
    <div
      className={cn(
        'absolute',
        orientation === 'vertical'
          ? 'inset-x-0.5'
          : 'inset-y-0.5',
        className
      )}
    >
      {children}
    </div>
  );
};

// --- ScrollBar.Track ---
interface ScrollTrackProps {
  children?: ReactNode;
  className?: string;
}

export const ScrollTrack: React.FC<ScrollTrackProps> = ({
  children,
  className,
}) => {
  return (
    <div className={cn('relative flex-1', className)}>
      {children}
    </div>
  );
};

// ============================================================================
// HOOKS
// ============================================================================

export const useScrollBar = (initialValue = 0, maxValue = 100) => {
  const [value, setValue] = useState(initialValue);
  const [isDragging, setIsDragging] = useState(false);

  const onChange = useCallback((newValue: number) => {
    setValue(Math.max(0, Math.min(maxValue, newValue)));
  }, [maxValue]);

  const increment = useCallback((step = 1) => {
    setValue((prev) => Math.min(maxValue, prev + step));
  }, [maxValue]);

  const decrement = useCallback((step = 1) => {
    setValue((prev) => Math.max(0, prev - step));
  }, []);

  const goToStart = useCallback(() => setValue(0), []);
  const goToEnd = useCallback(() => setValue(maxValue), [maxValue]);

  return {
    value,
    maxValue,
    onChange,
    increment,
    decrement,
    goToStart,
    goToEnd,
    isDragging,
    percentage: maxValue > 0 ? (value / maxValue) * 100 : 0,
  };
};

// ============================================================================
// EXPORTS
// ============================================================================

export default Object.assign(ScrollBar, {
  Thumb: ScrollThumb,
  Track: ScrollTrack,
});

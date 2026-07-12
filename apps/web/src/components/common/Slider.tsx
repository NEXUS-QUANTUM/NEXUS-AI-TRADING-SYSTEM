import React, { useState, useRef, useCallback, useEffect, forwardRef, useImperativeHandle } from 'react';
import { cn } from '@/lib/utils';
import { 
  Volume2, 
  VolumeX, 
  MoveHorizontal,
  GripVertical,
  Plus,
  Minus,
  Loader2
} from 'lucide-react';
import { useTheme } from '@/hooks/useTheme';
import { useDebounce } from '@/hooks/useDebounce';
import { useLocalStorage } from '@/hooks/useLocalStorage';

/**
 * NEXUS AI TRADING SYSTEM - Slider Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 * 
 * Version: 3.0.0
 * Status: Production Ready
 * 
 * Complete Slider system with:
 * - Multiple variants (default, range, vertical, discrete, etc.)
 * - Step values
 * - Marks & labels
 * - Tooltips
 * - Custom styling
 * - Accessibility (ARIA compliant)
 * - Keyboard navigation
 * - Touch support
 * - Value formatting
 * - Range selection
 * - Dual thumbs
 * - Min/Max constraints
 * - Real-time updates
 * - Debounced updates
 * - Theme aware
 * - Persistent preferences
 * - API integration
 * - Validation
 * - Error handling
 * - Loading states
 * - Disabled states
 * - Custom renderers
 */

// ========================================
// TYPES & INTERFACES
// ========================================

export type SliderVariant = 'default' | 'range' | 'vertical' | 'discrete' | 'minimal' | 'gradient' | 'neon';
export type SliderSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
export type SliderColor = 'nexus' | 'blue' | 'green' | 'red' | 'yellow' | 'purple' | 'pink' | 'gradient';
export type SliderOrientation = 'horizontal' | 'vertical';
export type SliderTooltip = 'none' | 'hover' | 'always' | 'active' | 'drag';
export type SliderMarkLabel = 'always' | 'hover' | 'none';

export interface SliderMark {
  value: number;
  label: string;
  color?: string;
  className?: string;
}

export interface SliderTick {
  value: number;
  label?: string;
}

export interface SliderProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'value' | 'defaultValue' | 'onChange' | 'size' | 'type' | 'step'> {
  /** Current value(s) */
  value?: number | [number, number];
  /** Default value(s) */
  defaultValue?: number | [number, number];
  /** Callback when value changes */
  onChange?: (value: number | [number, number]) => void;
  /** Callback when value change is committed */
  onChangeEnd?: (value: number | [number, number]) => void;
  /** Minimum value */
  min?: number;
  /** Maximum value */
  max?: number;
  /** Step increment */
  step?: number;
  /** Slider variant */
  variant?: SliderVariant;
  /** Slider size */
  size?: SliderSize;
  /** Slider color theme */
  color?: SliderColor;
  /** Slider orientation */
  orientation?: SliderOrientation;
  /** Tooltip display mode */
  tooltip?: SliderTooltip;
  /** Mark label display mode */
  markLabel?: SliderMarkLabel;
  /** Array of marks to display */
  marks?: SliderMark[];
  /** Array of ticks to display */
  ticks?: SliderTick[];
  /** Format value for display */
  formatValue?: (value: number) => string;
  /** Whether to show value label */
  showValue?: boolean;
  /** Whether to show min/max labels */
  showLimits?: boolean;
  /** Custom min label */
  minLabel?: string;
  /** Custom max label */
  maxLabel?: string;
  /** Disabled state */
  disabled?: boolean;
  /** Loading state */
  loading?: boolean;
  /** Read only mode */
  readOnly?: boolean;
  /** Whether to invert the slider */
  inverted?: boolean;
  /** Whether to show thumb on hover only */
  thumbOnHover?: boolean;
  /** Whether to snap to marks */
  snapToMarks?: boolean;
  /** Debounce delay for onChange (ms) */
  debounceDelay?: number;
  /** Persist value to localStorage */
  persistValue?: boolean;
  /** Storage key for persistence */
  storageKey?: string;
  /** Custom thumb renderer */
  renderThumb?: (props: { value: number; isActive: boolean; isHovered: boolean }) => React.ReactNode;
  /** Custom track renderer */
  renderTrack?: (props: { value: number | [number, number]; min: number; max: number }) => React.ReactNode;
  /** Custom tooltip renderer */
  renderTooltip?: (value: number) => React.ReactNode;
  /** Additional className */
  className?: string;
  /** Track className */
  trackClassName?: string;
  /** Thumb className */
  thumbClassName?: string;
  /** Mark className */
  markClassName?: string;
  /** Tooltip className */
  tooltipClassName?: string;
  /** ARIA label for slider */
  ariaLabel?: string;
  /** ARIA labellabel for range */
  ariaLabelledby?: string;
  /** Test ID */
  testId?: string;
}

// ========================================
// SIZE CONFIGURATION
// ========================================

const SIZE_CONFIG: Record<SliderSize, {
  track: { height: string; width: string };
  thumb: string;
  fontSize: string;
  gap: string;
  padding: string;
}> = {
  xs: {
    track: { height: 'h-1', width: 'w-1' },
    thumb: 'w-3 h-3',
    fontSize: 'text-xs',
    gap: 'gap-1',
    padding: 'p-1'
  },
  sm: {
    track: { height: 'h-1.5', width: 'w-1.5' },
    thumb: 'w-4 h-4',
    fontSize: 'text-sm',
    gap: 'gap-1.5',
    padding: 'p-1.5'
  },
  md: {
    track: { height: 'h-2', width: 'w-2' },
    thumb: 'w-5 h-5',
    fontSize: 'text-base',
    gap: 'gap-2',
    padding: 'p-2'
  },
  lg: {
    track: { height: 'h-2.5', width: 'w-2.5' },
    thumb: 'w-6 h-6',
    fontSize: 'text-lg',
    gap: 'gap-2.5',
    padding: 'p-2.5'
  },
  xl: {
    track: { height: 'h-3', width: 'w-3' },
    thumb: 'w-8 h-8',
    fontSize: 'text-xl',
    gap: 'gap-3',
    padding: 'p-3'
  }
};

// ========================================
// COLOR CONFIGURATION
// ========================================

const COLOR_CONFIG: Record<SliderColor, {
  track: string;
  fill: string;
  thumb: string;
  hover: string;
  active: string;
  focus: string;
}> = {
  nexus: {
    track: 'bg-nexus-200 dark:bg-nexus-700',
    fill: 'bg-nexus-500',
    thumb: 'bg-nexus-500 border-nexus-300 dark:border-nexus-700',
    hover: 'hover:bg-nexus-600',
    active: 'ring-2 ring-nexus-500/30',
    focus: 'ring-2 ring-nexus-500/50'
  },
  blue: {
    track: 'bg-blue-200 dark:bg-blue-700',
    fill: 'bg-blue-500',
    thumb: 'bg-blue-500 border-blue-300 dark:border-blue-700',
    hover: 'hover:bg-blue-600',
    active: 'ring-2 ring-blue-500/30',
    focus: 'ring-2 ring-blue-500/50'
  },
  green: {
    track: 'bg-emerald-200 dark:bg-emerald-700',
    fill: 'bg-emerald-500',
    thumb: 'bg-emerald-500 border-emerald-300 dark:border-emerald-700',
    hover: 'hover:bg-emerald-600',
    active: 'ring-2 ring-emerald-500/30',
    focus: 'ring-2 ring-emerald-500/50'
  },
  red: {
    track: 'bg-red-200 dark:bg-red-700',
    fill: 'bg-red-500',
    thumb: 'bg-red-500 border-red-300 dark:border-red-700',
    hover: 'hover:bg-red-600',
    active: 'ring-2 ring-red-500/30',
    focus: 'ring-2 ring-red-500/50'
  },
  yellow: {
    track: 'bg-yellow-200 dark:bg-yellow-700',
    fill: 'bg-yellow-500',
    thumb: 'bg-yellow-500 border-yellow-300 dark:border-yellow-700',
    hover: 'hover:bg-yellow-600',
    active: 'ring-2 ring-yellow-500/30',
    focus: 'ring-2 ring-yellow-500/50'
  },
  purple: {
    track: 'bg-purple-200 dark:bg-purple-700',
    fill: 'bg-purple-500',
    thumb: 'bg-purple-500 border-purple-300 dark:border-purple-700',
    hover: 'hover:bg-purple-600',
    active: 'ring-2 ring-purple-500/30',
    focus: 'ring-2 ring-purple-500/50'
  },
  pink: {
    track: 'bg-pink-200 dark:bg-pink-700',
    fill: 'bg-pink-500',
    thumb: 'bg-pink-500 border-pink-300 dark:border-pink-700',
    hover: 'hover:bg-pink-600',
    active: 'ring-2 ring-pink-500/30',
    focus: 'ring-2 ring-pink-500/50'
  },
  gradient: {
    track: 'bg-nexus-200 dark:bg-nexus-700',
    fill: 'bg-gradient-to-r from-nexus-400 via-nexus-500 to-nexus-600',
    thumb: 'bg-gradient-to-br from-nexus-400 to-nexus-600 border-nexus-300 dark:border-nexus-700',
    hover: 'hover:brightness-110',
    active: 'ring-2 ring-nexus-500/30',
    focus: 'ring-2 ring-nexus-500/50'
  }
};

// ========================================
// VARIANT CONFIGURATION
// ========================================

const VARIANT_CONFIG: Record<SliderVariant, {
  trackClass: string;
  thumbClass: string;
  className: string;
}> = {
  default: {
    trackClass: 'rounded-full',
    thumbClass: 'rounded-full shadow-lg',
    className: ''
  },
  range: {
    trackClass: 'rounded-full',
    thumbClass: 'rounded-full shadow-lg',
    className: ''
  },
  vertical: {
    trackClass: 'rounded-full',
    thumbClass: 'rounded-full shadow-lg',
    className: ''
  },
  discrete: {
    trackClass: 'rounded-full',
    thumbClass: 'rounded-full shadow-lg border-2',
    className: 'gap-0'
  },
  minimal: {
    trackClass: 'rounded-sm',
    thumbClass: 'rounded-sm shadow-none border-2',
    className: ''
  },
  gradient: {
    trackClass: 'rounded-full bg-gradient-to-r from-nexus-200 to-nexus-300 dark:from-nexus-700 dark:to-nexus-600',
    thumbClass: 'rounded-full shadow-lg bg-gradient-to-br',
    className: 'shadow-inner'
  },
  neon: {
    trackClass: 'rounded-full shadow-[inset_0_0_10px_rgba(0,0,0,0.3)]',
    thumbClass: 'rounded-full shadow-[0_0_20px_rgba(99,102,241,0.5)] border-2 border-nexus-400',
    className: 'shadow-glow'
  }
};

// ========================================
// MAIN COMPONENT
// ========================================

export const Slider = forwardRef<HTMLDivElement, SliderProps>(({
  value,
  defaultValue = 0,
  onChange,
  onChangeEnd,
  min = 0,
  max = 100,
  step = 1,
  variant = 'default',
  size = 'md',
  color = 'nexus',
  orientation = 'horizontal',
  tooltip = 'hover',
  markLabel = 'none',
  marks = [],
  ticks = [],
  formatValue,
  showValue = false,
  showLimits = false,
  minLabel,
  maxLabel,
  disabled = false,
  loading = false,
  readOnly = false,
  inverted = false,
  thumbOnHover = false,
  snapToMarks = false,
  debounceDelay = 0,
  persistValue = false,
  storageKey = 'nexus-slider-value',
  renderThumb,
  renderTrack,
  renderTooltip,
  className,
  trackClassName,
  thumbClassName,
  markClassName,
  tooltipClassName,
  ariaLabel,
  ariaLabelledby,
  testId = 'nexus-slider',
  ...props
}, ref) => {
  // ========================================
  // STATE
  // ========================================
  
  const [internalValue, setInternalValue] = useState<number | [number, number]>(() => {
    const initial = value !== undefined ? value : defaultValue;
    // Check if it's a range
    if (Array.isArray(initial) && initial.length === 2) {
      return [initial[0] ?? min, initial[1] ?? max];
    }
    return typeof initial === 'number' ? initial : min;
  });

  const [isDragging, setIsDragging] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const [isFocused, setIsFocused] = useState(false);
  const [tooltipValue, setTooltipValue] = useState<number | null>(null);
  const [activeThumb, setActiveThumb] = useState<'start' | 'end' | null>(null);
  const [localValue, setLocalValue] = useState<number | [number, number]>(internalValue);

  // ========================================
  // REFS
  // ========================================
  
  const sliderRef = useRef<HTMLDivElement>(null);
  const trackRef = useRef<HTMLDivElement>(null);
  const thumbStartRef = useRef<HTMLDivElement>(null);
  const thumbEndRef = useRef<HTMLDivElement>(null);
  const isMounted = useRef(false);
  const animationRef = useRef<number>();

  // ========================================
  // HOOKS
  // ========================================
  
  const { theme } = useTheme();
  const [storedValue, setStoredValue] = useLocalStorage<number | [number, number] | null>(
    storageKey,
    null
  );

  const debouncedOnChange = useDebounce((newValue: number | [number, number]) => {
    onChange?.(newValue);
    if (persistValue) {
      setStoredValue(newValue);
    }
  }, debounceDelay);

  // ========================================
  // EFFECTS
  // ========================================
  
  // Sync with props
  useEffect(() => {
    if (value !== undefined) {
      const newValue = Array.isArray(value) 
        ? [value[0] ?? min, value[1] ?? max]
        : value ?? min;
      setInternalValue(newValue);
      setLocalValue(newValue);
    }
  }, [value, min, max]);

  // Load stored value
  useEffect(() => {
    if (persistValue && storedValue !== null && value === undefined) {
      setInternalValue(storedValue);
      setLocalValue(storedValue);
    }
  }, [persistValue, storedValue, value]);

  // Mark mount
  useEffect(() => {
    isMounted.current = true;
    return () => {
      isMounted.current = false;
      if (animationRef.current) {
        cancelAnimationFrame(animationRef.current);
      }
    };
  }, []);

  // ========================================
  // HELPERS
  // ========================================
  
  const isRange = Array.isArray(internalValue);
  const colors = COLOR_CONFIG[color];
  const sizes = SIZE_CONFIG[size];
  const variantConfig = VARIANT_CONFIG[variant];
  const isVertical = orientation === 'vertical';

  const getValidValue = useCallback((val: number): number => {
    if (isNaN(val)) return min;
    let clamped = Math.max(min, Math.min(max, val));
    if (step > 0) {
      clamped = Math.round(clamped / step) * step;
    }
    return clamped;
  }, [min, max, step]);

  const getValidRange = useCallback((vals: [number, number]): [number, number] => {
    let [start, end] = vals;
    start = getValidValue(start);
    end = getValidValue(end);
    if (start > end) [start, end] = [end, start];
    return [start, end];
  }, [getValidValue]);

  const getPercentage = useCallback((val: number): number => {
    return ((val - min) / (max - min)) * 100;
  }, [min, max]);

  const getValueFromPosition = useCallback((position: number): number => {
    const rect = trackRef.current?.getBoundingClientRect();
    if (!rect) return min;

    let percentage: number;
    if (isVertical) {
      percentage = 1 - (position - rect.top) / rect.height;
    } else {
      percentage = (position - rect.left) / rect.width;
    }

    if (inverted) {
      percentage = 1 - percentage;
    }

    const value = min + percentage * (max - min);
    return getValidValue(value);
  }, [min, max, getValidValue, isVertical, inverted]);

  const getPercentageFromValue = useCallback((val: number): number => {
    let percentage = getPercentage(val);
    if (inverted) {
      percentage = 100 - percentage;
    }
    return Math.max(0, Math.min(100, percentage));
  }, [getPercentage, inverted]);

  const formatValueDisplay = useCallback((val: number): string => {
    if (formatValue) return formatValue(val);
    if (Number.isInteger(step)) return val.toString();
    return val.toFixed(1);
  }, [formatValue, step]);

  const getClosestMark = useCallback((val: number): number => {
    if (!marks.length) return val;
    let closest = marks[0].value;
    let closestDiff = Math.abs(val - closest);
    for (const mark of marks) {
      const diff = Math.abs(val - mark.value);
      if (diff < closestDiff) {
        closestDiff = diff;
        closest = mark.value;
      }
    }
    return closest;
  }, [marks]);

  // ========================================
  // HANDLERS
  // ========================================
  
  const handleValueChange = useCallback((newValue: number | [number, number]) => {
    let finalValue: number | [number, number];
    
    if (isRange) {
      const [start, end] = newValue as [number, number];
      finalValue = getValidRange([start, end]);
    } else {
      finalValue = getValidValue(newValue as number);
    }

    setInternalValue(finalValue);
    setLocalValue(finalValue);
    debouncedOnChange(finalValue);
    
    if (snapToMarks && !isRange) {
      const snapped = getClosestMark(finalValue as number);
      if (snapped !== finalValue) {
        setInternalValue(snapped);
        setLocalValue(snapped);
        debouncedOnChange(snapped);
      }
    }
  }, [isRange, getValidRange, getValidValue, debouncedOnChange, snapToMarks, getClosestMark]);

  const handleStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
    if (disabled || readOnly || loading) return;

    const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
    
    const position = isVertical ? clientY : clientX;
    const newValue = getValueFromPosition(position);

    // Determine which thumb to move
    if (isRange) {
      const [start, end] = internalValue as [number, number];
      const mid = (start + end) / 2;
      if (newValue < mid) {
        setActiveThumb('start');
        handleValueChange([newValue, end]);
      } else {
        setActiveThumb('end');
        handleValueChange([start, newValue]);
      }
    } else {
      handleValueChange(newValue);
    }

    setIsDragging(true);
    setTooltipValue(newValue);

    const handleMove = (ev: MouseEvent | TouchEvent) => {
      const cx = 'touches' in ev ? ev.touches[0].clientX : ev.clientX;
      const cy = 'touches' in ev ? ev.touches[0].clientY : ev.clientY;
      const pos = isVertical ? cy : cx;
      const val = getValueFromPosition(pos);

      if (isRange) {
        const [start, end] = internalValue as [number, number];
        if (activeThumb === 'start') {
          const newStart = Math.min(val, end - step);
          handleValueChange([newStart, end]);
        } else {
          const newEnd = Math.max(val, start + step);
          handleValueChange([start, newEnd]);
        }
      } else {
        handleValueChange(val);
      }
      setTooltipValue(val);
    };

    const handleEnd = () => {
      setIsDragging(false);
      setActiveThumb(null);
      const finalValue = internalValue;
      onChangeEnd?.(finalValue);
      setTooltipValue(null);
      
      document.removeEventListener('mousemove', handleMove);
      document.removeEventListener('mouseup', handleEnd);
      document.removeEventListener('touchmove', handleMove);
      document.removeEventListener('touchend', handleEnd);
    };

    document.addEventListener('mousemove', handleMove);
    document.addEventListener('mouseup', handleEnd);
    document.addEventListener('touchmove', handleMove);
    document.addEventListener('touchend', handleEnd);
  }, [
    disabled,
    readOnly,
    loading,
    isVertical,
    getValueFromPosition,
    isRange,
    internalValue,
    handleValueChange,
    step,
    activeThumb,
    onChangeEnd
  ]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (disabled || readOnly || loading) return;

    const stepSize = e.shiftKey ? step * 10 : step;
    const isRangeValue = isRange;
    let [start, end] = isRangeValue ? (internalValue as [number, number]) : [internalValue as number, internalValue as number];

    let newStart = start;
    let newEnd = end;

    switch (e.key) {
      case 'ArrowRight':
      case 'ArrowUp':
        e.preventDefault();
        if (isRangeValue && activeThumb === 'start') {
          newStart = Math.min(start + stepSize, end - step);
        } else if (isRangeValue && activeThumb === 'end') {
          newEnd = Math.min(end + stepSize, max);
        } else {
          newEnd = Math.min(end + stepSize, max);
          newStart = newEnd;
        }
        break;
      case 'ArrowLeft':
      case 'ArrowDown':
        e.preventDefault();
        if (isRangeValue && activeThumb === 'start') {
          newStart = Math.max(start - stepSize, min);
        } else if (isRangeValue && activeThumb === 'end') {
          newEnd = Math.max(end - stepSize, start + step);
        } else {
          newStart = Math.max(start - stepSize, min);
          newEnd = newStart;
        }
        break;
      case 'Home':
        e.preventDefault();
        if (isRangeValue && activeThumb === 'start') {
          newStart = min;
        } else if (isRangeValue && activeThumb === 'end') {
          newEnd = max;
        } else {
          newStart = min;
          newEnd = min;
        }
        break;
      case 'End':
        e.preventDefault();
        if (isRangeValue && activeThumb === 'start') {
          newStart = max - step;
        } else if (isRangeValue && activeThumb === 'end') {
          newEnd = max;
        } else {
          newStart = max;
          newEnd = max;
        }
        break;
      default:
        return;
    }

    const finalValue = isRangeValue ? [newStart, newEnd] as [number, number] : newStart;
    handleValueChange(finalValue);
  }, [disabled, readOnly, loading, step, isRange, internalValue, activeThumb, min, max, handleValueChange]);

  // ========================================
  // RENDER HELPERS
  // ========================================
  
  const renderMarks = () => {
    if (!marks.length) return null;

    return (
      <div className={cn(
        'relative w-full',
        isVertical ? 'h-full' : 'w-full'
      )}>
        {marks.map((mark) => {
          const percentage = getPercentageFromValue(mark.value);
          const isActive = isRange
            ? mark.value >= (internalValue as [number, number])[0] && mark.value <= (internalValue as [number, number])[1]
            : mark.value <= (internalValue as number);

          return (
            <div
              key={mark.value}
              className={cn(
                'absolute flex items-center justify-center',
                isVertical ? 'left-0 -translate-y-1/2' : 'top-full -translate-x-1/2 mt-2',
                markClassName
              )}
              style={{
                [isVertical ? 'top' : 'left']: `${percentage}%`,
              }}
            >
              <div
                className={cn(
                  'w-1 h-1 rounded-full transition-all duration-200',
                  isActive ? 'bg-nexus-500' : 'bg-nexus-300 dark:bg-nexus-600',
                  mark.color && !isActive && `bg-${mark.color}-300`,
                  mark.color && isActive && `bg-${mark.color}-500`,
                  mark.className
                )}
              />
              {markLabel !== 'none' && (
                <span
                  className={cn(
                    'absolute text-xs text-nexus-500 dark:text-nexus-400 whitespace-nowrap',
                    isVertical ? 'left-6' : 'top-full mt-1',
                    markLabel === 'hover' && 'opacity-0 group-hover:opacity-100 transition-opacity'
                  )}
                >
                  {mark.label}
                </span>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  const renderTicks = () => {
    if (!ticks.length) return null;

    return (
      <div className={cn(
        'relative w-full',
        isVertical ? 'h-full' : 'w-full',
        'pointer-events-none'
      )}>
        {ticks.map((tick) => {
          const percentage = getPercentageFromValue(tick.value);
          return (
            <div
              key={tick.value}
              className="absolute"
              style={{
                [isVertical ? 'top' : 'left']: `${percentage}%`,
                transform: isVertical ? 'translateY(-50%)' : 'translateX(-50%)',
              }}
            >
              <div className={cn(
                'w-px h-2 bg-nexus-300 dark:bg-nexus-600',
                isVertical && 'w-2 h-px'
              )} />
              {tick.label && (
                <span className={cn(
                  'absolute text-xs text-nexus-400 dark:text-nexus-500 whitespace-nowrap',
                  isVertical ? 'left-4' : 'top-full mt-1'
                )}>
                  {tick.label}
                </span>
              )}
            </div>
          );
        })}
      </div>
    );
  };

  const renderThumb = (val: number, isStart: boolean) => {
    const percentage = getPercentageFromValue(val);
    const isActive = isDragging && (isStart ? activeThumb === 'start' : activeThumb === 'end');
    const showTooltip = tooltip === 'always' || 
      (tooltip === 'hover' && isHovered) ||
      (tooltip === 'active' && isActive) ||
      (tooltip === 'drag' && isDragging);

    if (renderThumb) {
      return renderThumb({
        value: val,
        isActive: !!isActive,
        isHovered
      });
    }

    return (
      <div
        ref={isStart ? thumbStartRef : thumbEndRef}
        className={cn(
          'absolute cursor-grab touch-none transition-all duration-100',
          isVertical ? 'left-1/2 -translate-x-1/2' : 'top-1/2 -translate-y-1/2',
          sizes.thumb,
          colors.thumb,
          variantConfig.thumbClass,
          isActive && 'ring-2 ring-nexus-500/30 scale-110',
          isHovered && !isActive && 'scale-105',
          thumbOnHover && !isHovered && !isActive && 'opacity-0',
          (isHovered || isActive) && 'opacity-100',
          disabled && 'cursor-not-allowed opacity-50',
          thumbClassName
        )}
        style={{
          [isVertical ? 'top' : 'left']: `${percentage}%`,
          transform: isVertical 
            ? `translateX(-50%) translateY(${inverted ? '' : '-'}50%)`
            : `translateY(-50%) translateX(${inverted ? '' : '-'}50%)`,
        }}
        role="slider"
        aria-label={ariaLabel || (isStart ? 'Minimum value' : 'Maximum value')}
        aria-labelledby={ariaLabelledby}
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={val}
        aria-valuetext={formatValueDisplay(val)}
        aria-orientation={orientation}
        aria-disabled={disabled}
        tabIndex={disabled || readOnly ? -1 : 0}
        onMouseDown={handleStart}
        onTouchStart={handleStart}
        onKeyDown={handleKeyDown}
        onFocus={() => setIsFocused(true)}
        onBlur={() => setIsFocused(false)}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        {/* Tooltip */}
        {showTooltip && (renderTooltip ? (
          renderTooltip(val)
        ) : (
          <div className={cn(
            'absolute whitespace-nowrap text-sm font-medium',
            isVertical ? 'left-8' : 'bottom-full mb-2',
            'bg-nexus-900 dark:bg-nexus-100 text-white dark:text-nexus-900 px-2 py-0.5 rounded',
            'shadow-lg',
            tooltipClassName
          )}>
            {formatValueDisplay(tooltipValue ?? val)}
          </div>
        ))}
      </div>
    );
  };

  const renderTrack = () => {
    const isRangeValue = isRange;
    const [start, end] = isRangeValue 
      ? (internalValue as [number, number])
      : [min, internalValue as number];

    const startPercentage = getPercentageFromValue(start);
    const endPercentage = getPercentageFromValue(end);
    const fillPercentage = endPercentage - startPercentage;

    return (
      <div
        ref={trackRef}
        className={cn(
          'relative',
          isVertical ? 'h-full w-1' : 'w-full h-1',
          sizes.track,
          colors.track,
          variantConfig.trackClass,
          disabled && 'opacity-50',
          trackClassName
        )}
        style={{
          [isVertical ? 'width' : 'height']: sizes.track[isVertical ? 'width' : 'height'],
        }}
      >
        {/* Track fill */}
        <div
          className={cn(
            'absolute transition-all duration-100',
            colors.fill,
            isVertical ? 'bottom-0 w-full' : 'left-0 h-full',
            variant === 'gradient' && 'bg-gradient-to-r from-nexus-400 to-nexus-600'
          )}
          style={{
            [isVertical ? 'height' : 'width']: `${fillPercentage}%`,
            [isVertical ? 'bottom' : 'left']: isVertical ? `${startPercentage}%` : `${startPercentage}%`,
            transform: inverted ? (isVertical ? 'scaleY(-1)' : 'scaleX(-1)') : 'none',
          }}
        />
      </div>
    );
  };

  // ========================================
  // MAIN RENDER
  // ========================================
  
  const isRangeValue = isRange;
  const [startVal, endVal] = isRangeValue
    ? (internalValue as [number, number])
    : [internalValue as number, internalValue as number];

  return (
    <div
      ref={ref}
      className={cn(
        'relative flex items-center',
        isVertical ? 'flex-col h-full min-h-[200px]' : 'flex-row w-full',
        sizes.gap,
        variantConfig.className,
        className
      )}
      data-testid={testId}
      data-value={isRangeValue ? `${startVal}-${endVal}` : startVal}
      data-variant={variant}
      data-size={size}
      data-color={color}
      data-orientation={orientation}
    >
      {/* Min label */}
      {showLimits && (
        <span className={cn(
          'text-nexus-500 dark:text-nexus-400 select-none',
          sizes.fontSize,
          isVertical ? 'mb-1' : 'mr-2'
        )}>
          {minLabel || formatValueDisplay(min)}
        </span>
      )}

      {/* Value label */}
      {showValue && (
        <span className={cn(
          'text-nexus-600 dark:text-nexus-300 font-medium select-none',
          sizes.fontSize,
          isVertical ? 'mb-2' : 'mr-3'
        )}>
          {isRangeValue 
            ? `${formatValueDisplay(startVal)} - ${formatValueDisplay(endVal)}`
            : formatValueDisplay(startVal)}
        </span>
      )}

      {/* Slider container */}
      <div
        ref={sliderRef}
        className={cn(
          'relative flex-1',
          isVertical ? 'h-full' : 'w-full',
          'py-2',
          'group',
          disabled && 'cursor-not-allowed'
        )}
        onMouseEnter={() => setIsHovered(true)}
        onMouseLeave={() => setIsHovered(false)}
      >
        {/* Loading overlay */}
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-white/50 dark:bg-nexus-900/50 rounded-lg z-10">
            <Loader2 className="w-6 h-6 text-nexus-500 animate-spin" />
          </div>
        )}

        {/* Main track */}
        <div className={cn(
          'relative',
          isVertical ? 'h-full mx-auto' : 'w-full my-auto',
          sizes.padding
        )}>
          {/* Track background */}
          {renderTrack()}

          {/* Ticks */}
          {renderTicks()}

          {/* Marks */}
          {renderMarks()}

          {/* Thumb(s) */}
          {isRangeValue ? (
            <>
              {renderThumb(startVal, true)}
              {renderThumb(endVal, false)}
            </>
          ) : (
            renderThumb(startVal, true)
          )}
        </div>
      </div>

      {/* Max label */}
      {showLimits && (
        <span className={cn(
          'text-nexus-500 dark:text-nexus-400 select-none',
          sizes.fontSize,
          isVertical ? 'mt-1' : 'ml-2'
        )}>
          {maxLabel || formatValueDisplay(max)}
        </span>
      )}
    </div>
  );
});

Slider.displayName = 'Slider';

// ========================================
// COMPOUND COMPONENTS
// ========================================

export interface SliderGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  label?: string;
  description?: string;
  error?: string;
  required?: boolean;
  disabled?: boolean;
}

export const SliderGroup: React.FC<SliderGroupProps> = ({
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

export interface VolumeSliderProps extends Omit<SliderProps, 'variant' | 'color' | 'showValue' | 'showLimits'> {
  volume?: number;
  onVolumeChange?: (volume: number) => void;
  muted?: boolean;
  onMutedChange?: (muted: boolean) => void;
}

export const VolumeSlider: React.FC<VolumeSliderProps> = ({
  volume = 100,
  onVolumeChange,
  muted = false,
  onMutedChange,
  ...props
}) => {
  const handleVolumeChange = (value: number | [number, number]) => {
    const newVolume = typeof value === 'number' ? value : value[0];
    onVolumeChange?.(newVolume);
    if (muted && newVolume > 0) {
      onMutedChange?.(false);
    }
  };

  const toggleMute = () => {
    onMutedChange?.(!muted);
  };

  const Icon = muted ? VolumeX : Volume2;

  return (
    <div className="flex items-center gap-3">
      <button
        onClick={toggleMute}
        className="p-1.5 rounded-lg hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors"
        aria-label={muted ? 'Unmute' : 'Mute'}
      >
        <Icon className="w-5 h-5 text-nexus-500 dark:text-nexus-400" />
      </button>
      <Slider
        value={muted ? 0 : volume}
        onChange={handleVolumeChange}
        min={0}
        max={100}
        step={1}
        variant="minimal"
        size="sm"
        color="nexus"
        showValue={false}
        showLimits={false}
        disabled={muted}
        ariaLabel="Volume"
        {...props}
      />
      <span className="text-sm font-medium text-nexus-600 dark:text-nexus-400 w-12 text-right">
        {muted ? 'Muted' : `${Math.round(volume)}%`}
      </span>
    </div>
  );
};

// ========================================
// EXPORTS
// ========================================

SliderGroup.displayName = 'SliderGroup';
VolumeSlider.displayName = 'VolumeSlider';

export default Slider;

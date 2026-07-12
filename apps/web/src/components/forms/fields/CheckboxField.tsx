import React, { useState, useCallback, useEffect, useRef, forwardRef } from 'react';
import { cn } from '@/lib/utils';
import {
  Check,
  Minus,
  Loader2,
  AlertCircle,
  CheckCircle,
  AlertTriangle,
  Info,
  X,
  Eye,
  EyeOff,
  HelpCircle,
  Lock,
  Unlock,
  Shield,
  Sparkles,
  Zap,
  Star,
  Heart,
  Flag,
  Clock,
  Calendar,
  Users,
  User,
  Briefcase,
  DollarSign,
  TrendingUp,
  TrendingDown,
  Activity,
  BarChart3,
  PieChart,
  LineChart,
  Wallet,
  Coins,
  Bitcoin,
  Ethereum,
  Bell,
  Settings,
  RefreshCw,
  Copy,
  Trash2,
  Edit,
  Plus,
  Minus as MinusIcon,
  ArrowUp,
  ArrowDown,
  ArrowLeft,
  ArrowRight,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  Menu,
  MoreHorizontal,
  MoreVertical,
  Search,
  Filter,
  Download,
  Upload,
  Share2,
  Bookmark,
  Link,
  ExternalLink,
  Globe,
  MapPin,
  Target,
  Compass,
  Rocket,
  Crown,
  Medal,
  Trophy,
  Award
} from 'lucide-react';
import { useTheme } from '@/hooks/useTheme';
import { useField } from '@/hooks/useField';
import { useValidation } from '@/hooks/useValidation';

/**
 * NEXUS AI TRADING SYSTEM - Checkbox Field Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 * 
 * Version: 3.0.0
 * Status: Production Ready
 * 
 * Complete Checkbox Field system with:
 * - Multiple variants (default, outlined, filled, etc.)
 * - Multiple sizes (sm, md, lg)
 * - Multiple colors (nexus, blue, green, red, etc.)
 * - Indeterminate state
 * - Label support
 * - Description/helper text
 * - Error state
 * - Loading state
 * - Disabled state
 * - Required validation
 * - Group support
 * - Accessibility (ARIA compliant)
 * - Keyboard navigation
 * - Touch support
 * - Theme aware
 * - Form integration
 * - API integration
 * - Custom validation
 * - Tooltip support
 * - Icon support
 * - Animation
 * - Ripple effect
 */

// ========================================
// TYPES & INTERFACES
// ========================================

export type CheckboxVariant = 'default' | 'outlined' | 'filled' | 'minimal' | 'glass' | 'modern' | 'neon' | 'gradient';
export type CheckboxSize = 'sm' | 'md' | 'lg' | 'xl';
export type CheckboxColor = 'nexus' | 'blue' | 'green' | 'red' | 'yellow' | 'purple' | 'pink' | 'gradient' | 'auto';
export type CheckboxStatus = 'idle' | 'loading' | 'success' | 'error' | 'warning' | 'info';
export type CheckboxShape = 'square' | 'rounded' | 'circle';
export type CheckboxLabelPosition = 'left' | 'right' | 'top' | 'bottom';

export interface CheckboxFieldProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, 'size' | 'type' | 'onChange'> {
  /** Field name */
  name: string;
  /** Field label */
  label?: React.ReactNode;
  /** Field description */
  description?: string;
  /** Error message */
  error?: string;
  /** Success message */
  success?: string;
  /** Warning message */
  warning?: string;
  /** Helper text */
  helper?: string;
  /** Checked state */
  checked?: boolean;
  /** Default checked state */
  defaultChecked?: boolean;
  /** Indeterminate state */
  indeterminate?: boolean;
  /** Value of the checkbox */
  value?: string | number;
  /** Checkbox variant */
  variant?: CheckboxVariant;
  /** Checkbox size */
  size?: CheckboxSize;
  /** Checkbox color */
  color?: CheckboxColor;
  /** Checkbox status */
  status?: CheckboxStatus;
  /** Checkbox shape */
  shape?: CheckboxShape;
  /** Label position */
  labelPosition?: CheckboxLabelPosition;
  /** Icon for checked state */
  checkedIcon?: React.ReactNode;
  /** Icon for unchecked state */
  uncheckedIcon?: React.ReactNode;
  /** Icon for indeterminate state */
  indeterminateIcon?: React.ReactNode;
  /** Custom checkbox renderer */
  renderCheckbox?: (props: { checked: boolean; indeterminate: boolean; disabled: boolean }) => React.ReactNode;
  /** Tooltip content */
  tooltip?: string;
  /** Ripple effect */
  ripple?: boolean;
  /** Show status icon */
  showStatusIcon?: boolean;
  /** On change callback */
  onChange?: (checked: boolean, value?: string | number) => void;
  /** On focus callback */
  onFocus?: (e: React.FocusEvent<HTMLInputElement>) => void;
  /** On blur callback */
  onBlur?: (e: React.FocusEvent<HTMLInputElement>) => void;
  /** Validation rules */
  validation?: any;
  /** Form field context */
  formContext?: any;
  /** Additional className */
  className?: string;
  /** Label className */
  labelClassName?: string;
  /** Checkbox className */
  checkboxClassName?: string;
  /** Helper className */
  helperClassName?: string;
  /** Error className */
  errorClassName?: string;
  /** ARIA label */
  ariaLabel?: string;
  /** ARIA describedby */
  ariaDescribedby?: string;
  /** Test ID */
  testId?: string;
}

// ========================================
// CONFIGURATION
// ========================================

const VARIANT_CONFIG: Record<CheckboxVariant, {
  container: string;
  checkbox: string;
  label: string;
  helper: string;
}> = {
  default: {
    container: 'space-y-2',
    checkbox: 'border-2 border-nexus-300 dark:border-nexus-600 bg-white dark:bg-nexus-900 text-nexus-500 focus:ring-2 focus:ring-nexus-500/20',
    label: 'text-nexus-700 dark:text-nexus-300',
    helper: 'text-nexus-500 dark:text-nexus-400'
  },
  outlined: {
    container: 'space-y-2',
    checkbox: 'border-2 border-nexus-300 dark:border-nexus-600 bg-transparent text-nexus-500 focus:ring-2 focus:ring-nexus-500/20',
    label: 'text-nexus-700 dark:text-nexus-300',
    helper: 'text-nexus-500 dark:text-nexus-400'
  },
  filled: {
    container: 'space-y-2',
    checkbox: 'border-0 bg-nexus-100 dark:bg-nexus-800 text-nexus-500 focus:ring-2 focus:ring-nexus-500/20',
    label: 'text-nexus-700 dark:text-nexus-300',
    helper: 'text-nexus-500 dark:text-nexus-400'
  },
  minimal: {
    container: 'space-y-2',
    checkbox: 'border-0 bg-transparent text-nexus-500 focus:ring-0',
    label: 'text-nexus-700 dark:text-nexus-300',
    helper: 'text-nexus-500 dark:text-nexus-400'
  },
  glass: {
    container: 'space-y-2',
    checkbox: 'border border-white/20 bg-white/10 backdrop-blur-xl text-white focus:ring-2 focus:ring-white/30',
    label: 'text-white/80',
    helper: 'text-white/50'
  },
  modern: {
    container: 'space-y-2',
    checkbox: 'border-2 border-nexus-200 dark:border-nexus-700 bg-white dark:bg-nexus-900 text-nexus-500 focus:ring-2 focus:ring-nexus-500/20 shadow-lg shadow-nexus-500/5',
    label: 'text-nexus-700 dark:text-nexus-300 font-medium',
    helper: 'text-nexus-500 dark:text-nexus-400'
  },
  neon: {
    container: 'space-y-2',
    checkbox: 'border border-nexus-500/30 bg-nexus-900/50 text-nexus-400 focus:ring-2 focus:ring-nexus-400/20 shadow-[0_0_30px_rgba(99,102,241,0.05)]',
    label: 'text-nexus-400',
    helper: 'text-nexus-500'
  },
  gradient: {
    container: 'space-y-2',
    checkbox: 'border-2 border-nexus-300 dark:border-nexus-600 bg-gradient-to-br from-nexus-50 to-nexus-100 dark:from-nexus-900 dark:to-nexus-800 text-nexus-500 focus:ring-2 focus:ring-nexus-500/20',
    label: 'text-nexus-700 dark:text-nexus-300',
    helper: 'text-nexus-500 dark:text-nexus-400'
  }
};

const SIZE_CONFIG: Record<CheckboxSize, {
  checkbox: string;
  label: string;
  helper: string;
  icon: string;
  gap: string;
  padding: string;
}> = {
  sm: {
    checkbox: 'w-4 h-4',
    label: 'text-sm',
    helper: 'text-xs',
    icon: 'w-2.5 h-2.5',
    gap: 'gap-1.5',
    padding: 'p-0.5'
  },
  md: {
    checkbox: 'w-5 h-5',
    label: 'text-base',
    helper: 'text-sm',
    icon: 'w-3 h-3',
    gap: 'gap-2',
    padding: 'p-0.5'
  },
  lg: {
    checkbox: 'w-6 h-6',
    label: 'text-lg',
    helper: 'text-base',
    icon: 'w-3.5 h-3.5',
    gap: 'gap-2.5',
    padding: 'p-1'
  },
  xl: {
    checkbox: 'w-7 h-7',
    label: 'text-xl',
    helper: 'text-lg',
    icon: 'w-4 h-4',
    gap: 'gap-3',
    padding: 'p-1'
  }
};

const COLOR_CONFIG: Record<CheckboxColor, {
  checked: string;
  unchecked: string;
  hover: string;
  ring: string;
  text: string;
}> = {
  nexus: {
    checked: 'bg-nexus-500 border-nexus-500',
    unchecked: 'border-nexus-300 dark:border-nexus-600',
    hover: 'hover:border-nexus-400 dark:hover:border-nexus-500',
    ring: 'ring-nexus-500/20',
    text: 'text-nexus-700 dark:text-nexus-300'
  },
  blue: {
    checked: 'bg-blue-500 border-blue-500',
    unchecked: 'border-nexus-300 dark:border-nexus-600',
    hover: 'hover:border-blue-400',
    ring: 'ring-blue-500/20',
    text: 'text-blue-700 dark:text-blue-300'
  },
  green: {
    checked: 'bg-emerald-500 border-emerald-500',
    unchecked: 'border-nexus-300 dark:border-nexus-600',
    hover: 'hover:border-emerald-400',
    ring: 'ring-emerald-500/20',
    text: 'text-emerald-700 dark:text-emerald-300'
  },
  red: {
    checked: 'bg-red-500 border-red-500',
    unchecked: 'border-nexus-300 dark:border-nexus-600',
    hover: 'hover:border-red-400',
    ring: 'ring-red-500/20',
    text: 'text-red-700 dark:text-red-300'
  },
  yellow: {
    checked: 'bg-yellow-500 border-yellow-500',
    unchecked: 'border-nexus-300 dark:border-nexus-600',
    hover: 'hover:border-yellow-400',
    ring: 'ring-yellow-500/20',
    text: 'text-yellow-700 dark:text-yellow-300'
  },
  purple: {
    checked: 'bg-purple-500 border-purple-500',
    unchecked: 'border-nexus-300 dark:border-nexus-600',
    hover: 'hover:border-purple-400',
    ring: 'ring-purple-500/20',
    text: 'text-purple-700 dark:text-purple-300'
  },
  pink: {
    checked: 'bg-pink-500 border-pink-500',
    unchecked: 'border-nexus-300 dark:border-nexus-600',
    hover: 'hover:border-pink-400',
    ring: 'ring-pink-500/20',
    text: 'text-pink-700 dark:text-pink-300'
  },
  gradient: {
    checked: 'bg-gradient-to-r from-nexus-400 to-nexus-600 border-nexus-500',
    unchecked: 'border-nexus-300 dark:border-nexus-600',
    hover: 'hover:border-nexus-400 dark:hover:border-nexus-500',
    ring: 'ring-nexus-500/20',
    text: 'text-nexus-700 dark:text-nexus-300'
  },
  auto: {
    checked: 'bg-nexus-500 dark:bg-nexus-400 border-nexus-500 dark:border-nexus-400',
    unchecked: 'border-nexus-300 dark:border-nexus-600',
    hover: 'hover:border-nexus-400 dark:hover:border-nexus-500',
    ring: 'ring-nexus-500/20 dark:ring-nexus-400/20',
    text: 'text-nexus-700 dark:text-nexus-300'
  }
};

const STATUS_CONFIG: Record<CheckboxStatus, {
  icon: React.ReactNode;
  color: string;
  text: string;
}> = {
  idle: {
    icon: null,
    color: '',
    text: ''
  },
  loading: {
    icon: <Loader2 className="w-3 h-3 animate-spin" />,
    color: 'text-nexus-500',
    text: 'Loading...'
  },
  success: {
    icon: <CheckCircle className="w-3 h-3" />,
    color: 'text-emerald-500',
    text: 'Success'
  },
  error: {
    icon: <AlertCircle className="w-3 h-3" />,
    color: 'text-red-500',
    text: 'Error'
  },
  warning: {
    icon: <AlertTriangle className="w-3 h-3" />,
    color: 'text-yellow-500',
    text: 'Warning'
  },
  info: {
    icon: <Info className="w-3 h-3" />,
    color: 'text-blue-500',
    text: 'Info'
  }
};

const SHAPE_CONFIG: Record<CheckboxShape, string> = {
  square: 'rounded',
  rounded: 'rounded-lg',
  circle: 'rounded-full'
};

// ========================================
// MAIN COMPONENT
// ========================================

export const CheckboxField = forwardRef<HTMLInputElement, CheckboxFieldProps>(({
  name,
  label,
  description,
  error,
  success,
  warning,
  helper,
  checked: controlledChecked,
  defaultChecked = false,
  indeterminate = false,
  value,
  variant = 'default',
  size = 'md',
  color = 'nexus',
  status = 'idle',
  shape = 'rounded',
  labelPosition = 'right',
  checkedIcon,
  uncheckedIcon,
  indeterminateIcon,
  renderCheckbox,
  tooltip,
  ripple = true,
  showStatusIcon = true,
  onChange,
  onFocus,
  onBlur,
  validation,
  formContext,
  className,
  labelClassName,
  checkboxClassName,
  helperClassName,
  errorClassName,
  ariaLabel,
  ariaDescribedby,
  testId = 'nexus-checkbox',
  disabled = false,
  required = false,
  ...props
}, ref) => {
  // ========================================
  // STATE
  // ========================================
  
  const [isChecked, setIsChecked] = useState<boolean>(
    controlledChecked !== undefined ? controlledChecked : defaultChecked
  );
  const [isIndeterminate, setIsIndeterminate] = useState<boolean>(indeterminate);
  const [isFocused, setIsFocused] = useState(false);
  const [isHovered, setIsHovered] = useState(false);
  const [showRipple, setShowRipple] = useState(false);
  const [ripplePosition, setRipplePosition] = useState({ x: 0, y: 0 });
  const [validationError, setValidationError] = useState<string | null>(null);

  // ========================================
  // REFS
  // ========================================
  
  const inputRef = useRef<HTMLInputElement>(null);
  const checkboxRef = useRef<HTMLDivElement>(null);

  // ========================================
  // HOOKS
  // ========================================
  
  const { theme } = useTheme();
  const { field, setFieldValue } = useField(name, formContext);
  const { validate } = useValidation(validation);

  // ========================================
  // EFFECTS
  // ========================================
  
  // Sync with controlled prop
  useEffect(() => {
    if (controlledChecked !== undefined) {
      setIsChecked(controlledChecked);
    }
  }, [controlledChecked]);

  // Sync indeterminate state
  useEffect(() => {
    setIsIndeterminate(indeterminate);
  }, [indeterminate]);

  // Update input element for indeterminate
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.indeterminate = isIndeterminate;
    }
  }, [isIndeterminate]);

  // Validation
  useEffect(() => {
    if (validation) {
      const result = validate(isChecked);
      if (typeof result === 'string') {
        setValidationError(result);
      } else if (result === false) {
        setValidationError('Invalid value');
      } else {
        setValidationError(null);
      }
    }
  }, [isChecked, validation, validate]);

  // Form context integration
  useEffect(() => {
    if (formContext) {
      setFieldValue(name, isChecked);
    }
  }, [isChecked, name, formContext, setFieldValue]);

  // ========================================
  // HANDLERS
  // ========================================
  
  const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const newChecked = e.target.checked;
    setIsChecked(newChecked);
    onChange?.(newChecked, value);
    
    if (formContext) {
      setFieldValue(name, newChecked);
    }
  }, [onChange, value, formContext, name, setFieldValue]);

  const handleFocus = useCallback((e: React.FocusEvent<HTMLInputElement>) => {
    setIsFocused(true);
    onFocus?.(e);
  }, [onFocus]);

  const handleBlur = useCallback((e: React.FocusEvent<HTMLInputElement>) => {
    setIsFocused(false);
    onBlur?.(e);
  }, [onBlur]);

  const handleRipple = useCallback((e: React.MouseEvent) => {
    if (!ripple || !checkboxRef.current) return;
    
    const rect = checkboxRef.current.getBoundingClientRect();
    const x = e.clientX - rect.left;
    const y = e.clientY - rect.top;
    
    setRipplePosition({ x, y });
    setShowRipple(true);
    setTimeout(() => setShowRipple(false), 600);
  }, [ripple]);

  // ========================================
  // HELPERS
  // ========================================
  
  const variantConfig = VARIANT_CONFIG[variant];
  const sizeConfig = SIZE_CONFIG[size];
  const colorConfig = COLOR_CONFIG[color];
  const shapeClass = SHAPE_CONFIG[shape];
  const statusConfig = STATUS_CONFIG[status];

  const isError = !!error || !!validationError;
  const hasStatus = status !== 'idle';

  const getCheckboxClasses = () => {
    return cn(
      'relative flex-shrink-0 transition-all duration-200',
      sizeConfig.checkbox,
      shapeClass,
      variantConfig.checkbox,
      colorConfig.unchecked,
      isChecked && colorConfig.checked,
      isIndeterminate && colorConfig.checked,
      isFocused && colorConfig.ring,
      isHovered && !isChecked && !isDisabled && colorConfig.hover,
      isDisabled && 'opacity-50 cursor-not-allowed',
      isError && 'border-red-500 ring-red-500/20',
      checkboxClassName
    );
  };

  const isDisabled = disabled || status === 'loading';

  // ========================================
  // RENDER HELPERS
  // ========================================
  
  const renderCheckboxIcon = () => {
    if (isIndeterminate) {
      return indeterminateIcon || <Minus className={cn('text-white', sizeConfig.icon)} />;
    }
    
    if (isChecked) {
      return checkedIcon || <Check className={cn('text-white', sizeConfig.icon)} />;
    }
    
    return uncheckedIcon || null;
  };

  const renderStatusIcon = () => {
    if (!showStatusIcon || !hasStatus) return null;
    return (
      <span className={cn('flex-shrink-0', statusConfig.color)}>
        {statusConfig.icon}
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
        className="absolute rounded-full pointer-events-none animate-ripple"
        style={{
          left: ripplePosition.x - 20,
          top: ripplePosition.y - 20,
          width: 40,
          height: 40,
          backgroundColor: rippleColor,
        }}
      />
    );
  };

  const renderLabel = () => {
    if (!label) return null;

    const labelColor = isDisabled 
      ? 'text-nexus-400 dark:text-nexus-600' 
      : isError 
        ? 'text-red-500' 
        : colorConfig.text;

    return (
      <label
        htmlFor={props.id || name}
        className={cn(
          'font-medium select-none cursor-pointer transition-colors',
          sizeConfig.label,
          labelColor,
          isDisabled && 'cursor-not-allowed',
          labelClassName
        )}
      >
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
    );
  };

  const renderHelper = () => {
    if (isError) {
      return (
        <p className={cn('text-red-500', sizeConfig.helper, errorClassName)}>
          {error || validationError}
        </p>
      );
    }

    if (warning) {
      return (
        <p className={cn('text-yellow-500', sizeConfig.helper)}>
          {warning}
        </p>
      );
    }

    if (success) {
      return (
        <p className={cn('text-emerald-500', sizeConfig.helper)}>
          {success}
        </p>
      );
    }

    if (helper) {
      return (
        <p className={cn(variantConfig.helper, sizeConfig.helper, helperClassName)}>
          {helper}
        </p>
      );
    }

    return null;
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

  if (renderCheckbox) {
    return (
      <div className={cn(variantConfig.container, className)}>
        <div className="flex items-center gap-2">
          {renderCheckbox({ checked: isChecked, indeterminate: isIndeterminate, disabled: isDisabled })}
          {renderLabel()}
        </div>
        {renderHelper()}
      </div>
    );
  }

  return (
    <div className={cn(variantConfig.container, className)} data-testid={testId}>
      {/* Main checkbox row */}
      <div className={cn('flex items-start', labelPositions[labelPosition], sizeConfig.gap)}>
        {/* Checkbox wrapper */}
        <div
          ref={checkboxRef}
          className="relative flex-shrink-0"
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
        >
          <input
            ref={(el) => {
              if (typeof ref === 'function') {
                ref(el);
              } else if (ref) {
                (ref as React.MutableRefObject<HTMLInputElement | null>).current = el;
              }
              inputRef.current = el;
            }}
            type="checkbox"
            id={props.id || name}
            name={name}
            checked={isChecked}
            defaultChecked={defaultChecked}
            value={value}
            onChange={handleChange}
            onFocus={handleFocus}
            onBlur={handleBlur}
            disabled={isDisabled}
            required={required}
            aria-label={ariaLabel || (typeof label === 'string' ? label : undefined)}
            aria-describedby={ariaDescribedby || (helper ? `${name}-helper` : undefined)}
            aria-invalid={isError}
            aria-disabled={isDisabled}
            className="sr-only"
            {...props}
          />

          {/* Custom checkbox */}
          <div
            className={getCheckboxClasses()}
            onClick={handleRipple}
            role="presentation"
          >
            {/* Check icon */}
            <div className="absolute inset-0 flex items-center justify-center">
              {renderCheckboxIcon()}
            </div>

            {/* Loading spinner */}
            {status === 'loading' && (
              <div className="absolute inset-0 flex items-center justify-center">
                <Loader2 className={cn('animate-spin text-white', sizeConfig.icon)} />
              </div>
            )}

            {/* Ripple effect */}
            {renderRipple()}
          </div>
        </div>

        {/* Label section */}
        <div className="flex-1 min-w-0 space-y-1">
          <div className="flex items-center gap-2">
            {renderLabel()}
            {renderStatusIcon()}
            {tooltip && (
              <span className="text-nexus-400 dark:text-nexus-500">
                <HelpCircle className="w-3.5 h-3.5" />
              </span>
            )}
          </div>

          {/* Description */}
          {description && (
            <p className={cn('text-nexus-500 dark:text-nexus-400', sizeConfig.helper)}>
              {description}
            </p>
          )}
        </div>
      </div>

      {/* Helper text */}
      {renderHelper()}
    </div>
  );
});

CheckboxField.displayName = 'CheckboxField';

// ========================================
// COMPOUND COMPONENTS
// ========================================

export interface CheckboxGroupProps extends React.HTMLAttributes<HTMLDivElement> {
  children: React.ReactNode;
  label?: string;
  description?: string;
  error?: string;
  required?: boolean;
  disabled?: boolean;
  className?: string;
}

export const CheckboxGroup: React.FC<CheckboxGroupProps> = ({
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
      <div className="space-y-3">
        {React.Children.map(children, (child) => {
          if (React.isValidElement(child) && child.type === CheckboxField) {
            return React.cloneElement(child as React.ReactElement<CheckboxFieldProps>, {
              disabled: disabled || child.props.disabled,
            });
          }
          return child;
        })}
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
// PRESETED CHECKBOX COMPONENTS
// ========================================

export const CheckboxPresets = {
  Default: (props: Omit<CheckboxFieldProps, 'variant'>) => (
    <CheckboxField variant="default" {...props} />
  ),
  Outlined: (props: Omit<CheckboxFieldProps, 'variant'>) => (
    <CheckboxField variant="outlined" {...props} />
  ),
  Filled: (props: Omit<CheckboxFieldProps, 'variant'>) => (
    <CheckboxField variant="filled" {...props} />
  ),
  Minimal: (props: Omit<CheckboxFieldProps, 'variant'>) => (
    <CheckboxField variant="minimal" {...props} />
  ),
  Glass: (props: Omit<CheckboxFieldProps, 'variant'>) => (
    <CheckboxField variant="glass" {...props} />
  ),
  Modern: (props: Omit<CheckboxFieldProps, 'variant'>) => (
    <CheckboxField variant="modern" {...props} />
  ),
  Neon: (props: Omit<CheckboxFieldProps, 'variant'>) => (
    <CheckboxField variant="neon" {...props} />
  ),
  Gradient: (props: Omit<CheckboxFieldProps, 'variant'>) => (
    <CheckboxField variant="gradient" {...props} />
  )
};

// ========================================
// EXPORTS
// ========================================

CheckboxGroup.displayName = 'CheckboxGroup';

export default CheckboxField;

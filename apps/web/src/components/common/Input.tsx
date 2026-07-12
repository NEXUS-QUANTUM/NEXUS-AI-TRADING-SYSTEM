/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import { cn } from '@/utils/helpers';
import { Eye, EyeOff, AlertCircle, CheckCircle, AlertTriangle, Info, X, Loader2 } from 'lucide-react';

// ============================================
// TYPES
// ============================================

export interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  asChild?: boolean;
  error?: string;
  success?: string;
  warning?: string;
  info?: string;
  label?: string;
  description?: string;
  icon?: React.ReactNode;
  iconPosition?: 'left' | 'right';
  clearable?: boolean;
  loading?: boolean;
  size?: 'sm' | 'md' | 'lg';
  variant?: 'default' | 'outline' | 'filled' | 'ghost' | 'glass';
  rounded?: 'none' | 'sm' | 'md' | 'lg' | 'full';
  fullWidth?: boolean;
  onClear?: () => void;
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  containerClassName?: string;
  inputClassName?: string;
}

// ============================================
// COMPOSANT
// ============================================

const Input = React.forwardRef<HTMLInputElement, InputProps>(
  (
    {
      className,
      type = 'text',
      error,
      success,
      warning,
      info,
      label,
      description,
      icon,
      iconPosition = 'left',
      clearable = false,
      loading = false,
      size = 'md',
      variant = 'default',
      rounded = 'md',
      fullWidth = true,
      onClear,
      leftIcon,
      rightIcon,
      containerClassName,
      inputClassName,
      disabled,
      required,
      readOnly,
      value,
      defaultValue,
      onChange,
      onFocus,
      onBlur,
      id,
      name,
      placeholder,
      autoComplete,
      autoFocus,
      ...props
    },
    ref
  ) => {
    // ============================================
    // RÉFÉRENCES
    // ============================================
    const inputRef = React.useRef<HTMLInputElement>(null);

    // ============================================
    // ÉTATS
    // ============================================
    const [isFocused, setIsFocused] = React.useState(false);
    const [showPassword, setShowPassword] = React.useState(false);
    const [internalValue, setInternalValue] = React.useState(value || defaultValue || '');
    const [isPassword, setIsPassword] = React.useState(type === 'password');

    // ============================================
    // EFFETS
    // ============================================
    React.useEffect(() => {
      if (value !== undefined) {
        setInternalValue(value);
      }
    }, [value]);

    React.useEffect(() => {
      setIsPassword(type === 'password');
    }, [type]);

    // ============================================
    // VARIANTES
    // ============================================

    const variantClasses = {
      default: 'border-gray-300 bg-white text-gray-900 placeholder:text-gray-400 dark:border-gray-600 dark:bg-gray-900 dark:text-gray-100 dark:placeholder:text-gray-500',
      outline: 'border-2 border-gray-300 bg-transparent text-gray-900 placeholder:text-gray-400 dark:border-gray-600 dark:text-gray-100 dark:placeholder:text-gray-500',
      filled: 'border-transparent bg-gray-100 text-gray-900 placeholder:text-gray-400 dark:bg-gray-800 dark:text-gray-100 dark:placeholder:text-gray-500',
      ghost: 'border-transparent bg-transparent text-gray-900 placeholder:text-gray-400 dark:text-gray-100 dark:placeholder:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800',
      glass: 'border border-white/20 bg-white/10 backdrop-blur-sm text-white placeholder:text-white/60',
    };

    const sizeClasses = {
      sm: 'h-8 px-3 text-xs',
      md: 'h-10 px-4 text-sm',
      lg: 'h-12 px-5 text-base',
    };

    const roundedClasses = {
      none: 'rounded-none',
      sm: 'rounded-sm',
      md: 'rounded-md',
      lg: 'rounded-lg',
      full: 'rounded-full',
    };

    const iconSizeClasses = {
      sm: 'h-3.5 w-3.5',
      md: 'h-4 w-4',
      lg: 'h-5 w-5',
    };

    const paddingIcon = {
      sm: {
        left: 'pl-8',
        right: 'pr-8',
      },
      md: {
        left: 'pl-9',
        right: 'pr-9',
      },
      lg: {
        left: 'pl-10',
        right: 'pr-10',
      },
    };

    // ============================================
    // GESTIONNAIRES
    // ============================================

    const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
      setInternalValue(e.target.value);
      onChange?.(e);
    };

    const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
      setIsFocused(true);
      onFocus?.(e);
    };

    const handleBlur = (e: React.FocusEvent<HTMLInputElement>) => {
      setIsFocused(false);
      onBlur?.(e);
    };

    const handleClear = () => {
      setInternalValue('');
      onClear?.();
      if (inputRef.current) {
        inputRef.current.focus();
        const event = new Event('input', { bubbles: true });
        inputRef.current.dispatchEvent(event);
      }
    };

    const togglePasswordVisibility = () => {
      setShowPassword(!showPassword);
    };

    // ============================================
    // STATUS
    // ============================================

    const getStatusIcon = () => {
      if (error) return <AlertCircle className={cn(iconSizeClasses[size], 'text-red-500')} />;
      if (success) return <CheckCircle className={cn(iconSizeClasses[size], 'text-green-500')} />;
      if (warning) return <AlertTriangle className={cn(iconSizeClasses[size], 'text-yellow-500')} />;
      if (info) return <Info className={cn(iconSizeClasses[size], 'text-blue-500')} />;
      return null;
    };

    const getStatusColor = () => {
      if (error) return 'border-red-500 ring-1 ring-red-500 focus:ring-red-500';
      if (success) return 'border-green-500 ring-1 ring-green-500 focus:ring-green-500';
      if (warning) return 'border-yellow-500 ring-1 ring-yellow-500 focus:ring-yellow-500';
      if (info) return 'border-blue-500 ring-1 ring-blue-500 focus:ring-blue-500';
      return '';
    };

    // ============================================
    // RENDU
    // ============================================

    const inputId = id || `input-${React.useId()}`;
    const hasLeftIcon = icon && iconPosition === 'left' || leftIcon;
    const hasRightIcon = icon && iconPosition === 'right' || rightIcon;
    const hasStatusIcon = !!(error || success || warning || info);
    const isClearable = clearable && internalValue && !disabled && !readOnly;

    return (
      <div className={cn('w-full', containerClassName)}>
        {/* Label */}
        {label && (
          <label
            htmlFor={inputId}
            className={cn(
              'mb-2 block text-sm font-medium',
              'text-gray-700 dark:text-gray-300',
              required && 'after:ml-0.5 after:text-red-500 after:content-["*"]'
            )}
          >
            {label}
          </label>
        )}

        <div className="relative">
          {/* Icône gauche */}
          {hasLeftIcon && (
            <div className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400">
              {leftIcon || icon}
            </div>
          )}

          {/* Input */}
          <input
            ref={inputRef}
            id={inputId}
            type={isPassword ? (showPassword ? 'text' : 'password') : type}
            value={internalValue}
            defaultValue={defaultValue}
            onChange={handleChange}
            onFocus={handleFocus}
            onBlur={handleBlur}
            disabled={disabled}
            readOnly={readOnly}
            required={required}
            placeholder={placeholder}
            autoComplete={autoComplete}
            autoFocus={autoFocus}
            className={cn(
              'w-full transition-all duration-200 outline-none',
              'disabled:cursor-not-allowed disabled:opacity-50',
              'read-only:cursor-default read-only:bg-gray-50 dark:read-only:bg-gray-800/50',
              variantClasses[variant],
              sizeClasses[size],
              roundedClasses[rounded],
              fullWidth && 'w-full',
              getStatusColor(),
              hasLeftIcon && paddingIcon[size].left,
              (hasRightIcon || hasStatusIcon || isClearable || isPassword) && paddingIcon[size].right,
              isFocused && 'ring-2 ring-blue-500 ring-offset-1',
              className
            )}
            {...props}
          />

          {/* État de chargement */}
          {loading && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              <Loader2 className={cn(iconSizeClasses[size], 'animate-spin text-gray-400')} />
            </div>
          )}

          {/* Mot de passe visible */}
          {isPassword && !loading && (
            <button
              type="button"
              onClick={togglePasswordVisibility}
              className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              tabIndex={-1}
            >
              {showPassword ? (
                <EyeOff className={iconSizeClasses[size]} />
              ) : (
                <Eye className={iconSizeClasses[size]} />
              )}
            </button>
          )}

          {/* Icône de statut */}
          {hasStatusIcon && !loading && !isPassword && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2">
              {getStatusIcon()}
            </div>
          )}

          {/* Bouton de nettoyage */}
          {isClearable && !loading && !isPassword && !hasStatusIcon && (
            <button
              type="button"
              onClick={handleClear}
              className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-0.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600 dark:hover:bg-gray-800 dark:hover:text-gray-300"
              tabIndex={-1}
            >
              <X className={iconSizeClasses[size]} />
            </button>
          )}

          {/* Icône droite */}
          {hasRightIcon && !loading && !isPassword && !hasStatusIcon && !isClearable && (
            <div className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400">
              {rightIcon || icon}
            </div>
          )}
        </div>

        {/* Description */}
        {description && !error && !success && !warning && !info && (
          <p className="mt-1.5 text-xs text-gray-500 dark:text-gray-400">
            {description}
          </p>
        )}

        {/* Message d'erreur */}
        {error && (
          <p className="mt-1.5 flex items-center gap-1.5 text-xs text-red-500">
            <AlertCircle className="h-3.5 w-3.5" />
            {error}
          </p>
        )}

        {/* Message de succès */}
        {success && !error && (
          <p className="mt-1.5 flex items-center gap-1.5 text-xs text-green-500">
            <CheckCircle className="h-3.5 w-3.5" />
            {success}
          </p>
        )}

        {/* Message d'avertissement */}
        {warning && !error && !success && (
          <p className="mt-1.5 flex items-center gap-1.5 text-xs text-yellow-500">
            <AlertTriangle className="h-3.5 w-3.5" />
            {warning}
          </p>
        )}

        {/* Message d'information */}
        {info && !error && !success && !warning && (
          <p className="mt-1.5 flex items-center gap-1.5 text-xs text-blue-500">
            <Info className="h-3.5 w-3.5" />
            {info}
          </p>
        )}
      </div>
    );
  }
);
Input.displayName = 'Input';

// ============================================
// EXPORTATIONS
// ============================================

export { Input };

export default Input;

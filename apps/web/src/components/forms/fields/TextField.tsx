// apps/web/src/components/forms/fields/TextField.tsx
'use client';

import React, {
  useState,
  useCallback,
  useRef,
  useEffect,
  forwardRef,
  Ref,
  useMemo,
  useImperativeHandle,
  ChangeEvent,
  FocusEvent,
  KeyboardEvent,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
  CheckIcon,
  ExclamationCircleIcon,
  EyeIcon,
  EyeSlashIcon,
  MagnifyingGlassIcon,
  PlusIcon,
  MinusIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import {
  CheckCircleIcon as CheckCircleSolid,
  ExclamationCircleIcon as ExclamationCircleSolid,
} from '@heroicons/react/24/solid';
import { Label } from '@/components/common/Label';
import { Badge } from '@/components/common/Badge';
import { Tooltip } from '@/components/common/Tooltip';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type TextFieldVariant = 'default' | 'outlined' | 'solid' | 'ghost' | 'minimal' | 'pill';
export type TextFieldSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
export type TextFieldStatus = 'default' | 'success' | 'error' | 'warning' | 'info';
export type TextFieldInputMode = 'text' | 'email' | 'tel' | 'url' | 'search' | 'numeric' | 'decimal' | 'none';
export type TextFieldAutocomplete = 'on' | 'off' | 'username' | 'email' | 'current-password' | 'new-password' | 'tel' | 'url' | 'bday' | 'bday-day' | 'bday-month' | 'bday-year' | 'sex' | 'name' | 'given-name' | 'additional-name' | 'family-name' | 'nickname' | 'organization' | 'street-address' | 'address-line1' | 'address-line2' | 'address-line3' | 'address-level4' | 'address-level3' | 'address-level2' | 'address-level1' | 'country' | 'country-name' | 'postal-code' | 'cc-name' | 'cc-given-name' | 'cc-additional-name' | 'cc-family-name' | 'cc-number' | 'cc-exp' | 'cc-exp-month' | 'cc-exp-year' | 'cc-csc' | 'cc-type' | 'transaction-currency' | 'transaction-amount' | 'language' | 'bday' | 'bday-day' | 'bday-month' | 'bday-year' | 'sex' | 'url' | 'photo';

export interface TextFieldProps {
  // --- Contrôle ---
  /** Valeur du champ */
  value?: string | null;
  /** Valeur par défaut */
  defaultValue?: string | null;
  /** Callback de changement */
  onChange?: (value: string | null) => void;
  /** Callback de blur */
  onBlur?: (value: string | null) => void;
  /** Callback de focus */
  onFocus?: () => void;
  /** Callback de validation */
  onValidate?: (valid: boolean, value: string | null) => void;

  // --- Apparence ---
  /** Libellé du champ */
  label?: string;
  /** Placeholder */
  placeholder?: string;
  /** Description */
  description?: string;
  /** Message d'erreur */
  error?: string;
  /** Message de succès */
  success?: string;
  /** Message d'information */
  info?: string;
  /** Variante d'affichage */
  variant?: TextFieldVariant;
  /** Taille du champ */
  size?: TextFieldSize;
  /** Statut du champ */
  status?: TextFieldStatus;
  /** Préfixe */
  prefix?: React.ReactNode;
  /** Suffixe */
  suffix?: React.ReactNode;
  /** Icône à gauche */
  leftIcon?: React.ReactNode;
  /** Icône à droite */
  rightIcon?: React.ReactNode;
  /** Afficher l'icône de validation */
  showValidationIcon?: boolean;
  /** Afficher le compteur de caractères */
  showCharCount?: boolean;
  /** Afficher le bouton d'effacement */
  showClearButton?: boolean;

  // --- Comportement ---
  /** Désactiver le champ */
  disabled?: boolean;
  /** Rendre le champ obligatoire */
  required?: boolean;
  /** Lecture seule */
  readOnly?: boolean;
  /** Auto-focus */
  autoFocus?: boolean;
  /** Auto-complétion */
  autoComplete?: TextFieldAutocomplete;
  /** Type d'input */
  inputMode?: TextFieldInputMode;
  /** Longueur maximale */
  maxLength?: number;
  /** Longueur minimale */
  minLength?: number;
  /** Pattern de validation */
  pattern?: string;
  /** Désactiver le trim */
  disableTrim?: boolean;
  /** Désactiver la validation en temps réel */
  disableRealtimeValidation?: boolean;
  /** Validation personnalisée */
  validateTextField?: (value: string | null) => boolean | string;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ARIA describedby */
  ariaDescribedby?: string;
  /** ID */
  id?: string;
  /** Nom du champ */
  name?: string;

  // --- Avancé ---
  /** Fonction de formatage personnalisée */
  customFormat?: (value: string | null) => string;
  /** Fonction de parsing personnalisée */
  customParse?: (value: string) => string | null;
  /** Ref */
  inputRef?: React.Ref<HTMLInputElement>;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const SIZE_MAP: Record<TextFieldSize, string> = {
  xs: 'h-7 text-xs px-2',
  sm: 'h-8 text-sm px-3',
  md: 'h-10 text-sm px-4',
  lg: 'h-12 text-base px-5',
  xl: 'h-14 text-lg px-6',
};

const VARIANT_MAP: Record<TextFieldVariant, string> = {
  default: 'bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600',
  outlined: 'bg-transparent border-2 border-gray-300 dark:border-gray-600',
  solid: 'bg-gray-100 dark:bg-gray-800 border border-transparent',
  ghost: 'bg-transparent border border-transparent hover:bg-gray-100 dark:hover:bg-gray-800',
  minimal: 'bg-transparent border-b-2 border-gray-300 dark:border-gray-600 rounded-none',
  pill: 'bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-full',
};

const STATUS_MAP: Record<TextFieldStatus, { border: string; ring: string; text: string }> = {
  default: {
    border: 'border-gray-300 dark:border-gray-600',
    ring: 'ring-brand-500',
    text: 'text-gray-900 dark:text-white',
  },
  success: {
    border: 'border-green-500 dark:border-green-400',
    ring: 'ring-green-500',
    text: 'text-green-700 dark:text-green-400',
  },
  error: {
    border: 'border-red-500 dark:border-red-400',
    ring: 'ring-red-500',
    text: 'text-red-700 dark:text-red-400',
  },
  warning: {
    border: 'border-yellow-500 dark:border-yellow-400',
    ring: 'ring-yellow-500',
    text: 'text-yellow-700 dark:text-yellow-400',
  },
  info: {
    border: 'border-blue-500 dark:border-blue-400',
    ring: 'ring-blue-500',
    text: 'text-blue-700 dark:text-blue-400',
  },
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const TextField = forwardRef<HTMLInputElement, TextFieldProps>(
  (props, ref) => {
    const {
      // Contrôle
      value: externalValue,
      defaultValue,
      onChange,
      onBlur,
      onFocus,
      onValidate,

      // Apparence
      label,
      placeholder,
      description,
      error,
      success,
      info,
      variant = 'default',
      size = 'md',
      status = 'default',
      prefix,
      suffix,
      leftIcon,
      rightIcon,
      showValidationIcon = true,
      showCharCount = true,
      showClearButton = true,

      // Comportement
      disabled = false,
      required = false,
      readOnly = false,
      autoFocus = false,
      autoComplete = 'on',
      inputMode = 'text',
      maxLength,
      minLength,
      pattern,
      disableTrim = false,
      disableRealtimeValidation = false,
      validateTextField: customValidate,

      // Accessibilité
      ariaLabel,
      ariaDescribedby,
      id,
      name,

      // Avancé
      customFormat,
      customParse,
      inputRef,
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const containerRef = useRef<HTMLDivElement>(null);
    const inputRefInternal = useRef<HTMLInputElement>(null);
    const prevValueRef = useRef<string | null>(null);

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalValue, setInternalValue] = useState<string | null>(
      defaultValue || null
    );
    const [displayValue, setDisplayValue] = useState<string>('');
    const [isFocused, setIsFocused] = useState(false);
    const [isValid, setIsValid] = useState(true);
    const [validationMessage, setValidationMessage] = useState<string>('');
    const [isHovered, setIsHovered] = useState(false);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined ? externalValue : internalValue;
    const isControlled = externalValue !== undefined;
    const hasValue = value && value.length > 0;

    const sizeStyles = SIZE_MAP[size] || SIZE_MAP.md;
    const variantStyles = VARIANT_MAP[variant] || VARIANT_MAP.default;
    const statusStyles = STATUS_MAP[status] || STATUS_MAP.default;

    // ========================================================================
    // FORMATAGE
    // ========================================================================

    const formatValue = useCallback((val: string | null): string => {
      if (customFormat) {
        return customFormat(val);
      }
      return val || '';
    }, [customFormat]);

    const parseValue = useCallback((val: string): string | null => {
      if (customParse) {
        return customParse(val);
      }
      return val || null;
    }, [customParse]);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validateValue = useCallback((val: string | null): { valid: boolean; message: string } => {
      if (customValidate) {
        const result = customValidate(val);
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        return { valid: true, message: '' };
      }

      if (!val || val.trim() === '') {
        if (required) {
          return { valid: false, message: 'Ce champ est requis' };
        }
        return { valid: true, message: '' };
      }

      const trimmed = disableTrim ? val : val.trim();

      if (minLength && trimmed.length < minLength) {
        return { valid: false, message: `Minimum ${minLength} caractères` };
      }

      if (maxLength && trimmed.length > maxLength) {
        return { valid: false, message: `Maximum ${maxLength} caractères` };
      }

      if (pattern) {
        const regex = new RegExp(pattern);
        if (!regex.test(trimmed)) {
          return { valid: false, message: 'Format invalide' };
        }
      }

      return { valid: true, message: '' };
    }, [customValidate, required, minLength, maxLength, pattern, disableTrim]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateValue = useCallback((val: string | null) => {
      const trimmed = val ? (disableTrim ? val : val.trim()) : null;
      const validation = validateValue(trimmed);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);

      if (!disableRealtimeValidation && onValidate) {
        onValidate(validation.valid, trimmed);
      }

      const formatted = formatValue(trimmed);

      if (isControlled) {
        if (onChange) onChange(trimmed);
      } else {
        setInternalValue(trimmed);
        if (onChange) onChange(trimmed);
      }

      setDisplayValue(formatted);

      if (debug) {
        console.log('TextField update:', { val: trimmed, isValid: validation.valid });
      }
    }, [
      validateValue,
      isControlled,
      onChange,
      onValidate,
      disableRealtimeValidation,
      formatValue,
      disableTrim,
      debug,
    ]);

    // ========================================================================
    // GESTIONNAIRES D'ÉVÉNEMENTS
    // ========================================================================

    const handleChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
      const rawValue = e.target.value;
      setDisplayValue(rawValue);

      if (!disableRealtimeValidation) {
        const parsed = parseValue(rawValue);
        const validation = validateValue(parsed);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        if (onValidate) onValidate(validation.valid, parsed);
      }

      if (!isFocused) {
        const parsed = parseValue(rawValue);
        updateValue(parsed);
      }
    }, [disableRealtimeValidation, parseValue, validateValue, onValidate, updateValue, isFocused]);

    const handleFocus = useCallback((e: FocusEvent<HTMLInputElement>) => {
      setIsFocused(true);
      if (onFocus) onFocus();

      // Sélectionner tout le texte
      setTimeout(() => {
        e.target.select();
      }, 10);
    }, [onFocus]);

    const handleBlur = useCallback(() => {
      setIsFocused(false);

      const parsed = parseValue(displayValue);
      const validation = validateValue(parsed);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);
      if (onValidate) onValidate(validation.valid, parsed);

      const formatted = formatValue(parsed);
      setDisplayValue(formatted);

      if (!isControlled) {
        setInternalValue(parsed);
      }
      if (onChange) onChange(parsed);
      if (onBlur) onBlur?.(parsed);

      if (debug) {
        console.log('TextField blur:', { parsed, formatted });
      }
    }, [
      displayValue,
      parseValue,
      validateValue,
      onValidate,
      formatValue,
      isControlled,
      onChange,
      onBlur,
      debug,
    ]);

    const handleKeyDown = useCallback((e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const parsed = parseValue(displayValue);
        if (parsed !== null) {
          updateValue(parsed);
        }
        inputRefInternal.current?.blur();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        setDisplayValue(formatValue(value));
        inputRefInternal.current?.blur();
      }
    }, [displayValue, parseValue, updateValue, formatValue, value]);

    // ========================================================================
    // EFFACEMENT
    // ========================================================================

    const handleClear = useCallback(() => {
      updateValue(null);
      setDisplayValue('');
      inputRefInternal.current?.focus();
    }, [updateValue]);

    // ========================================================================
    // SYNC AVEC LA VALEUR EXTERNE
    // ========================================================================

    useEffect(() => {
      if (externalValue !== undefined && externalValue !== prevValueRef.current) {
        prevValueRef.current = externalValue;
        const formatted = formatValue(externalValue);
        setDisplayValue(formatted);
        const validation = validateValue(externalValue);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
      }
    }, [externalValue, formatValue, validateValue]);

    // ========================================================================
    // INITIALISATION
    // ========================================================================

    useEffect(() => {
      if (defaultValue !== undefined && !isControlled) {
        const formatted = formatValue(defaultValue);
        setDisplayValue(formatted);
        updateValue(defaultValue);
      }
    }, [defaultValue, formatValue, updateValue, isControlled]);

    // ========================================================================
    // IMPERATIVE HANDLE
    // ========================================================================

    useImperativeHandle(ref, () => ({
      focus: () => inputRefInternal.current?.focus(),
      blur: () => inputRefInternal.current?.blur(),
      select: () => inputRefInternal.current?.select(),
      getValue: () => value,
      setValue: (val: string | null) => updateValue(val),
      clear: () => handleClear(),
      validate: () => {
        const validation = validateValue(value);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        return validation.valid;
      },
    } as any));

    // ========================================================================
    // RENDU
    // ========================================================================

    const hasError = !!error || !isValid || (required && !value);
    const isSuccess = !hasError && success && value;

    const showClear = showClearButton && hasValue && !disabled && !readOnly;

    return (
      <div ref={containerRef} className="relative space-y-1.5" id={id}>
        {/* Label */}
        {label && (
          <div className="flex items-center justify-between">
            <Label 
              htmlFor={id || name} 
              className="text-sm font-medium text-gray-700 dark:text-gray-300"
            >
              {label}
              {required && <span className="ml-1 text-red-500">*</span>}
            </Label>
            {showCharCount && maxLength && (
              <Badge variant="outline" size="xs" className="text-xs">
                {displayValue.length} / {maxLength}
              </Badge>
            )}
          </div>
        )}

        {/* Description */}
        {description && (
          <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
        )}

        {/* Champ de saisie */}
        <div className="relative">
          <div
            className={cn(
              'relative flex items-center rounded-lg transition-all',
              variantStyles,
              hasError 
                ? 'border-red-500 ring-2 ring-red-500/20 dark:border-red-400' 
                : isSuccess && !disabled
                ? 'border-green-500 ring-2 ring-green-500/20 dark:border-green-400'
                : isFocused
                ? `border-${statusStyles.ring} ring-2 ring-${statusStyles.ring}/20 dark:border-${statusStyles.ring}`
                : statusStyles.border,
              disabled && 'opacity-50 cursor-not-allowed bg-gray-50 dark:bg-gray-800/50',
              readOnly && 'cursor-default bg-gray-50 dark:bg-gray-800/50',
              sizeStyles
            )}
            onMouseEnter={() => setIsHovered(true)}
            onMouseLeave={() => setIsHovered(false)}
          >
            {/* Icône gauche */}
            {leftIcon && (
              <span className="flex-shrink-0 pl-2 text-gray-400">
                {leftIcon}
              </span>
            )}

            {/* Préfixe */}
            {prefix && (
              <span className="flex-shrink-0 pl-2 text-gray-500 dark:text-gray-400">
                {prefix}
              </span>
            )}

            <input
              ref={(node) => {
                inputRefInternal.current = node;
                if (inputRef) {
                  if (typeof inputRef === 'function') {
                    inputRef(node);
                  } else {
                    (inputRef as React.MutableRefObject<HTMLInputElement>).current = node;
                  }
                }
              }}
              id={id || name}
              type="text"
              className={cn(
                'w-full bg-transparent text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 outline-none',
                disabled && 'cursor-not-allowed',
                leftIcon && 'pl-1',
                prefix && 'pl-1',
                suffix && 'pr-1',
                rightIcon && 'pr-1'
              )}
              placeholder={placeholder}
              value={displayValue}
              onChange={handleChange}
              onFocus={handleFocus}
              onBlur={handleBlur}
              onKeyDown={handleKeyDown}
              disabled={disabled}
              readOnly={readOnly}
              autoFocus={autoFocus}
              autoComplete={autoComplete}
              inputMode={inputMode}
              maxLength={maxLength}
              minLength={minLength}
              pattern={pattern}
              required={required}
              aria-label={ariaLabel || label}
              aria-describedby={ariaDescribedby}
              aria-invalid={hasError}
              aria-required={required}
              name={name}
            />

            {/* Bouton d'effacement */}
            {showClear && (
              <button
                type="button"
                onClick={handleClear}
                className="flex-shrink-0 px-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
              >
                <XMarkIcon className="h-4 w-4" />
              </button>
            )}

            {/* Suffixe */}
            {suffix && (
              <span className="flex-shrink-0 pr-2 text-gray-500 dark:text-gray-400">
                {suffix}
              </span>
            )}

            {/* Icône droite */}
            {rightIcon && (
              <span className="flex-shrink-0 pr-2 text-gray-400">
                {rightIcon}
              </span>
            )}

            {/* Icône de validation */}
            {showValidationIcon && (
              <div className="flex-shrink-0 pr-2">
                {hasError && !disabled && (
                  <ExclamationCircleIcon className="h-4 w-4 text-red-500" />
                )}
                {isSuccess && !disabled && (
                  <CheckCircleIcon className="h-4 w-4 text-green-500" />
                )}
              </div>
            )}
          </div>

          {/* Statut */}
          <div className="mt-1 flex items-center gap-1.5 text-xs">
            {hasError && (
              <span className="text-red-600 dark:text-red-400">
                {error || validationMessage}
              </span>
            )}
            {success && !hasError && (
              <span className="text-green-600 dark:text-green-400">{success}</span>
            )}
            {info && !hasError && !success && (
              <span className="text-blue-600 dark:text-blue-400">{info}</span>
            )}
          </div>
        </div>
      </div>
    );
  }
);

TextField.displayName = 'TextField';

// ============================================================================
// EXPORTS
// ============================================================================

export default TextField;

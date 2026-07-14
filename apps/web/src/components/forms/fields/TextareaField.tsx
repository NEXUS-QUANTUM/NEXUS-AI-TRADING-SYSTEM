// apps/web/src/components/forms/fields/TextareaField.tsx
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
  ArrowsUpDownIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
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

export type TextareaVariant = 'default' | 'outlined' | 'solid' | 'ghost' | 'minimal' | 'pill';
export type TextareaSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
export type TextareaStatus = 'default' | 'success' | 'error' | 'warning' | 'info';
export type TextareaResize = 'none' | 'vertical' | 'horizontal' | 'both' | 'auto';

export interface TextareaFieldProps {
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
  variant?: TextareaVariant;
  /** Taille du champ */
  size?: TextareaSize;
  /** Statut du champ */
  status?: TextareaStatus;
  /** Hauteur minimale */
  minHeight?: number | string;
  /** Hauteur maximale */
  maxHeight?: number | string;
  /** Nombre de lignes */
  rows?: number;
  /** Comportement de redimensionnement */
  resize?: TextareaResize;
  /** Afficher l'icône de validation */
  showValidationIcon?: boolean;
  /** Afficher le compteur de caractères */
  showCharCount?: boolean;
  /** Afficher le compteur de mots */
  showWordCount?: boolean;
  /** Afficher le bouton d'effacement */
  showClearButton?: boolean;
  /** Afficher les contrôles de redimensionnement */
  showResizeControls?: boolean;
  /** Auto-agrandir */
  autoResize?: boolean;

  // --- Comportement ---
  /** Désactiver le champ */
  disabled?: boolean;
  /** Rendre le champ obligatoire */
  required?: boolean;
  /** Lecture seule */
  readOnly?: boolean;
  /** Auto-focus */
  autoFocus?: boolean;
  /** Longueur maximale */
  maxLength?: number;
  /** Longueur minimale */
  minLength?: number;
  /** Désactiver le trim */
  disableTrim?: boolean;
  /** Désactiver la validation en temps réel */
  disableRealtimeValidation?: boolean;
  /** Validation personnalisée */
  validateTextarea?: (value: string | null) => boolean | string;

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
  textareaRef?: React.Ref<HTMLTextAreaElement>;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const SIZE_MAP: Record<TextareaSize, { padding: string; fontSize: string }> = {
  xs: { padding: 'px-2 py-1', fontSize: 'text-xs' },
  sm: { padding: 'px-3 py-1.5', fontSize: 'text-sm' },
  md: { padding: 'px-4 py-2', fontSize: 'text-sm' },
  lg: { padding: 'px-5 py-2.5', fontSize: 'text-base' },
  xl: { padding: 'px-6 py-3', fontSize: 'text-lg' },
};

const VARIANT_MAP: Record<TextareaVariant, string> = {
  default: 'bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600',
  outlined: 'bg-transparent border-2 border-gray-300 dark:border-gray-600',
  solid: 'bg-gray-100 dark:bg-gray-800 border border-transparent',
  ghost: 'bg-transparent border border-transparent hover:bg-gray-100 dark:hover:bg-gray-800',
  minimal: 'bg-transparent border-b-2 border-gray-300 dark:border-gray-600 rounded-none',
  pill: 'bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-xl',
};

const STATUS_MAP: Record<TextareaStatus, { border: string; ring: string; text: string }> = {
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

const RESIZE_MAP: Record<TextareaResize, string> = {
  none: 'resize-none',
  vertical: 'resize-y',
  horizontal: 'resize-x',
  both: 'resize',
  auto: 'resize-none',
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const TextareaField = forwardRef<HTMLDivElement, TextareaFieldProps>(
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
      minHeight = 80,
      maxHeight = 400,
      rows = 3,
      resize = 'vertical',
      showValidationIcon = true,
      showCharCount = true,
      showWordCount = true,
      showClearButton = true,
      showResizeControls = true,
      autoResize = true,

      // Comportement
      disabled = false,
      required = false,
      readOnly = false,
      autoFocus = false,
      maxLength,
      minLength,
      disableTrim = false,
      disableRealtimeValidation = false,
      validateTextarea: customValidate,

      // Accessibilité
      ariaLabel,
      ariaDescribedby,
      id,
      name,

      // Avancé
      customFormat,
      customParse,
      textareaRef,
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const containerRef = useRef<HTMLDivElement>(null);
    const textareaRefInternal = useRef<HTMLTextAreaElement>(null);
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
    const [wordCount, setWordCount] = useState(0);
    const [charCount, setCharCount] = useState(0);
    const [isExpanded, setIsExpanded] = useState(false);
    const [currentHeight, setCurrentHeight] = useState<number | string>(minHeight);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined ? externalValue : internalValue;
    const isControlled = externalValue !== undefined;
    const hasValue = value && value.length > 0;

    const sizeStyles = SIZE_MAP[size] || SIZE_MAP.md;
    const variantStyles = VARIANT_MAP[variant] || VARIANT_MAP.default;
    const statusStyles = STATUS_MAP[status] || STATUS_MAP.default;
    const resizeStyles = RESIZE_MAP[resize] || RESIZE_MAP.vertical;

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

      return { valid: true, message: '' };
    }, [customValidate, required, minLength, maxLength, disableTrim]);

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

      // Mettre à jour les compteurs
      if (formatted) {
        const cleanText = formatted.replace(/<[^>]*>/g, '').trim();
        setCharCount(cleanText.length);
        setWordCount(cleanText.split(/\s+/).filter(w => w.length > 0).length);
      } else {
        setCharCount(0);
        setWordCount(0);
      }

      // Auto-resize
      if (autoResize && textareaRefInternal.current) {
        textareaRefInternal.current.style.height = 'auto';
        textareaRefInternal.current.style.height = `${Math.min(
          textareaRefInternal.current.scrollHeight,
          typeof maxHeight === 'number' ? maxHeight : Infinity
        )}px`;
      }

      if (debug) {
        console.log('TextareaField update:', { val: trimmed, isValid: validation.valid });
      }
    }, [
      validateValue,
      isControlled,
      onChange,
      onValidate,
      disableRealtimeValidation,
      formatValue,
      disableTrim,
      autoResize,
      maxHeight,
      debug,
    ]);

    // ========================================================================
    // GESTIONNAIRES D'ÉVÉNEMENTS
    // ========================================================================

    const handleChange = useCallback((e: ChangeEvent<HTMLTextAreaElement>) => {
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

      // Auto-resize
      if (autoResize) {
        e.target.style.height = 'auto';
        e.target.style.height = `${Math.min(
          e.target.scrollHeight,
          typeof maxHeight === 'number' ? maxHeight : Infinity
        )}px`;
      }
    }, [disableRealtimeValidation, parseValue, validateValue, onValidate, updateValue, isFocused, autoResize, maxHeight]);

    const handleFocus = useCallback((e: FocusEvent<HTMLTextAreaElement>) => {
      setIsFocused(true);
      if (onFocus) onFocus();
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
        console.log('TextareaField blur:', { parsed, formatted });
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

    const handleKeyDown = useCallback((e: KeyboardEvent<HTMLTextAreaElement>) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        setDisplayValue(formatValue(value));
        textareaRefInternal.current?.blur();
      }
    }, [formatValue, value]);

    // ========================================================================
    // EFFACEMENT
    // ========================================================================

    const handleClear = useCallback(() => {
      updateValue(null);
      setDisplayValue('');
      textareaRefInternal.current?.focus();
    }, [updateValue]);

    // ========================================================================
    // REDIMENSIONNEMENT
    // ========================================================================

    const toggleExpand = useCallback(() => {
      setIsExpanded(!isExpanded);
      if (textareaRefInternal.current) {
        if (!isExpanded) {
          textareaRefInternal.current.style.height = typeof maxHeight === 'number' ? `${maxHeight}px` : '400px';
        } else {
          textareaRefInternal.current.style.height = typeof minHeight === 'number' ? `${minHeight}px` : '80px';
        }
      }
    }, [isExpanded, maxHeight, minHeight]);

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
        
        // Mettre à jour les compteurs
        if (formatted) {
          const cleanText = formatted.replace(/<[^>]*>/g, '').trim();
          setCharCount(cleanText.length);
          setWordCount(cleanText.split(/\s+/).filter(w => w.length > 0).length);
        }
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
    // AUTO-RESIZE INITIAL
    // ========================================================================

    useEffect(() => {
      if (autoResize && textareaRefInternal.current && hasValue) {
        textareaRefInternal.current.style.height = 'auto';
        textareaRefInternal.current.style.height = `${Math.min(
          textareaRefInternal.current.scrollHeight,
          typeof maxHeight === 'number' ? maxHeight : Infinity
        )}px`;
      }
    }, [autoResize, hasValue, maxHeight]);

    // ========================================================================
    // IMPERATIVE HANDLE
    // ========================================================================

    useImperativeHandle(ref, () => ({
      focus: () => textareaRefInternal.current?.focus(),
      blur: () => textareaRefInternal.current?.blur(),
      select: () => textareaRefInternal.current?.select(),
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
            <div className="flex items-center gap-2">
              {showWordCount && (
                <Badge variant="outline" size="xs" className="text-xs">
                  {wordCount} mots
                </Badge>
              )}
              {showCharCount && maxLength && (
                <Badge variant="outline" size="xs" className="text-xs">
                  {charCount} / {maxLength}
                </Badge>
              )}
            </div>
          </div>
        )}

        {/* Description */}
        {description && (
          <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
        )}

        {/* Zone de texte */}
        <div className="relative">
          <textarea
            ref={(node) => {
              textareaRefInternal.current = node;
              if (textareaRef) {
                if (typeof textareaRef === 'function') {
                  textareaRef(node);
                } else {
                  (textareaRef as React.MutableRefObject<HTMLTextAreaElement>).current = node;
                }
              }
            }}
            id={id || name}
            className={cn(
              'w-full rounded-lg transition-all outline-none',
              variantStyles,
              sizeStyles.padding,
              sizeStyles.fontSize,
              resizeStyles,
              hasError 
                ? 'border-red-500 ring-2 ring-red-500/20 dark:border-red-400' 
                : isSuccess && !disabled
                ? 'border-green-500 ring-2 ring-green-500/20 dark:border-green-400'
                : isFocused
                ? `border-${statusStyles.ring} ring-2 ring-${statusStyles.ring}/20 dark:border-${statusStyles.ring}`
                : statusStyles.border,
              disabled && 'opacity-50 cursor-not-allowed bg-gray-50 dark:bg-gray-800/50',
              readOnly && 'cursor-default bg-gray-50 dark:bg-gray-800/50',
              !autoResize && `h-${rows * 6}`
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
            rows={rows}
            maxLength={maxLength}
            minLength={minLength}
            required={required}
            aria-label={ariaLabel || label}
            aria-describedby={ariaDescribedby}
            aria-invalid={hasError}
            aria-required={required}
            name={name}
            style={{
              minHeight: typeof minHeight === 'number' ? `${minHeight}px` : minHeight,
              maxHeight: typeof maxHeight === 'number' ? `${maxHeight}px` : maxHeight,
            }}
          />

          {/* Boutons flottants */}
          <div className="absolute bottom-2 right-2 flex items-center gap-1">
            {showClear && (
              <button
                type="button"
                onClick={handleClear}
                className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                disabled={disabled}
              >
                <XMarkIcon className="h-4 w-4" />
              </button>
            )}
            {showResizeControls && (
              <Tooltip content={isExpanded ? 'Réduire' : 'Agrandir'}>
                <button
                  type="button"
                  onClick={toggleExpand}
                  className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                  disabled={disabled}
                >
                  {isExpanded ? (
                    <ArrowsPointingInIcon className="h-4 w-4" />
                  ) : (
                    <ArrowsPointingOutIcon className="h-4 w-4" />
                  )}
                </button>
              </Tooltip>
            )}
            {showValidationIcon && (
              <>
                {hasError && !disabled && (
                  <ExclamationCircleIcon className="h-4 w-4 text-red-500" />
                )}
                {isSuccess && !disabled && (
                  <CheckCircleIcon className="h-4 w-4 text-green-500" />
                )}
              </>
            )}
          </div>
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
    );
  }
);

TextareaField.displayName = 'TextareaField';

// ============================================================================
// EXPORTS
// ============================================================================

export default TextareaField;

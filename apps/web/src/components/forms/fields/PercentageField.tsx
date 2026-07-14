// apps/web/src/components/forms/fields/PercentageField.tsx
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
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  PercentIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
  CheckIcon,
  ArrowPathIcon,
  ExclamationCircleIcon,
  PlusIcon,
  MinusIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  AdjustmentsHorizontalIcon,
  ArrowsUpDownIcon,
  CalculatorIcon,
} from '@heroicons/react/24/outline';
import {
  CheckCircleIcon as CheckCircleSolid,
  ExclamationCircleIcon as ExclamationCircleSolid,
} from '@heroicons/react/24/solid';
import { Label } from '@/components/common/Label';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Progress } from '@/components/common/Progress';
import { Slider } from '@/components/common/Slider';
import { Tooltip } from '@/components/common/Tooltip';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type PercentageDisplay = 'decimal' | 'percentage' | 'both';
export type PercentageRounding = 'none' | 'floor' | 'ceil' | 'round' | 'truncate';
export type PercentageFieldVariant = 'default' | 'compact' | 'minimal' | 'rounded' | 'outlined';
export type PercentageMode = 'normal' | 'slider' | 'both';

export interface PercentageFieldProps {
  // --- Contrôle ---
  /** Valeur du champ (en décimal, ex: 0.75 pour 75%) */
  value?: number | string | null;
  /** Valeur par défaut */
  defaultValue?: number | string | null;
  /** Callback de changement */
  onChange?: (value: number | null) => void;
  /** Callback de blur */
  onBlur?: () => void;
  /** Callback de focus */
  onFocus?: () => void;
  /** Callback de validation */
  onValidate?: (valid: boolean, value: number | null) => void;

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
  variant?: PercentageFieldVariant;
  /** Mode d'affichage */
  mode?: PercentageMode;
  /** Afficher l'icône de pourcentage */
  showIcon?: boolean;
  /** Afficher la barre de progression */
  showProgress?: boolean;
  /** Afficher les présets */
  showPresets?: boolean;
  /** Afficher l'icône de validation */
  showValidationIcon?: boolean;
  /** Afficher le formatage */
  showFormatting?: boolean;

  // --- Formatage ---
  /** Format d'affichage */
  displayFormat?: PercentageDisplay;
  /** Nombre de décimales */
  decimals?: number;
  /** Arrondi */
  rounding?: PercentageRounding;
  /** Séparateur décimal */
  decimalSeparator?: string;

  // --- Comportement ---
  /** Valeur minimale (en décimal) */
  min?: number;
  /** Valeur maximale (en décimal) */
  max?: number;
  /** Pas d'incrémentation (en décimal) */
  step?: number;
  /** Désactiver le champ */
  disabled?: boolean;
  /** Rendre le champ obligatoire */
  required?: boolean;
  /** Désactiver la validation en temps réel */
  disableRealtimeValidation?: boolean;
  /** Désactiver le formatage automatique */
  disableAutoFormat?: boolean;

  // --- Présets ---
  /** Présets en pourcentage (ex: [25, 50, 75, 100]) */
  presets?: number[];
  /** Libellés des présets */
  presetLabels?: string[];

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
  customFormat?: (value: number) => string;
  /** Fonction de parsing personnalisée */
  customParse?: (value: string) => number | null;
  /** Fonction de validation personnalisée */
  customValidate?: (value: number | null) => boolean | string;
  /** Ref */
  inputRef?: React.Ref<HTMLInputElement>;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const DEFAULT_MIN = 0;
const DEFAULT_MAX = 1;
const DEFAULT_STEP = 0.01;
const DEFAULT_DECIMALS = 0;
const DEFAULT_PRESETS = [0, 25, 50, 75, 100];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const PercentageField = forwardRef<HTMLInputElement, PercentageFieldProps>(
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
      placeholder = '0%',
      description,
      error,
      success,
      info,
      variant = 'default',
      mode = 'normal',
      showIcon = true,
      showProgress = true,
      showPresets = true,
      showValidationIcon = true,
      showFormatting = true,

      // Formatage
      displayFormat = 'both',
      decimals = DEFAULT_DECIMALS,
      rounding = 'round',
      decimalSeparator = '.',

      // Comportement
      min = DEFAULT_MIN,
      max = DEFAULT_MAX,
      step = DEFAULT_STEP,
      disabled = false,
      required = false,
      disableRealtimeValidation = false,
      disableAutoFormat = false,

      // Présets
      presets = DEFAULT_PRESETS,
      presetLabels,

      // Accessibilité
      ariaLabel,
      ariaDescribedby,
      id,
      name,

      // Avancé
      customFormat,
      customParse,
      customValidate,
      inputRef,
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const inputRefInternal = useRef<HTMLInputElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const prevValueRef = useRef<number | null>(null);

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalValue, setInternalValue] = useState<number | null>(
      defaultValue !== undefined && defaultValue !== null && defaultValue !== ''
        ? Number(defaultValue) 
        : null
    );
    const [displayValue, setDisplayValue] = useState<string>('');
    const [isFocused, setIsFocused] = useState(false);
    const [isValid, setIsValid] = useState(true);
    const [validationMessage, setValidationMessage] = useState<string>('');
    const [isHovered, setIsHovered] = useState(false);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined && externalValue !== null && externalValue !== ''
      ? Number(externalValue) 
      : internalValue;
    const isControlled = externalValue !== undefined;
    const numericValue = value !== null && !isNaN(value) ? value : null;
    const percentageValue = numericValue !== null ? numericValue * 100 : null;

    // ========================================================================
    // FORMATAGE
    // ========================================================================

    const formatPercentage = useCallback((num: number | null): string => {
      if (num === null || num === undefined || isNaN(num)) return '';

      if (customFormat) {
        return customFormat(num);
      }

      let number = num;
      const decimalsToUse = decimals;
      const factor = Math.pow(10, decimalsToUse);

      // Arrondi
      switch (rounding) {
        case 'floor':
          number = Math.floor(number * factor) / factor;
          break;
        case 'ceil':
          number = Math.ceil(number * factor) / factor;
          break;
        case 'truncate':
          number = Math.trunc(number * factor) / factor;
          break;
        default:
          number = Math.round(number * factor) / factor;
      }

      const percentValue = number * 100;
      let formatted = percentValue.toFixed(decimalsToUse);

      // Remplacer le séparateur décimal
      if (decimalSeparator !== '.') {
        formatted = formatted.replace('.', decimalSeparator);
      }

      const display = displayFormat === 'decimal' 
        ? number.toFixed(decimalsToUse)
        : displayFormat === 'percentage'
        ? formatted + '%'
        : `${number.toFixed(decimalsToUse)} (${formatted}%)`;

      return display;
    }, [customFormat, decimals, rounding, decimalSeparator, displayFormat]);

    const parsePercentage = useCallback((text: string): number | null => {
      if (!text || text.trim() === '') return null;

      if (customParse) {
        return customParse(text);
      }

      let cleaned = text.trim();

      // Retirer le symbole %
      if (cleaned.includes('%')) {
        cleaned = cleaned.replace(/%/g, '').trim();
        const num = parseFloat(cleaned);
        return isNaN(num) ? null : num / 100;
      }

      // Retirer les parenthèses (ex: "0.75 (75%)")
      if (cleaned.includes('(') && cleaned.includes(')')) {
        const match = cleaned.match(/\(([^)]+)\)/);
        if (match) {
          cleaned = match[1].replace(/%/g, '').trim();
          const num = parseFloat(cleaned);
          return isNaN(num) ? null : num / 100;
        }
      }

      // Remplacer le séparateur décimal
      if (decimalSeparator !== '.') {
        cleaned = cleaned.replace(new RegExp(`\\${decimalSeparator}`), '.');
      }

      const num = parseFloat(cleaned);
      if (isNaN(num)) return null;

      // Si la valeur est > 1, on suppose que c'est un pourcentage
      if (num > 1) {
        return num / 100;
      }

      return num;
    }, [customParse, decimalSeparator]);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validatePercentage = useCallback((num: number | null): { valid: boolean; message: string } => {
      if (customValidate) {
        const result = customValidate(num);
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        return { valid: true, message: '' };
      }

      if (num === null || num === undefined) {
        if (required) {
          return { valid: false, message: 'Ce champ est requis' };
        }
        return { valid: true, message: '' };
      }

      if (isNaN(num)) {
        return { valid: false, message: 'Veuillez entrer un nombre valide' };
      }

      if (num < min) {
        return { valid: false, message: `La valeur minimale est ${formatPercentage(min)}` };
      }

      if (num > max) {
        return { valid: false, message: `La valeur maximale est ${formatPercentage(max)}` };
      }

      return { valid: true, message: '' };
    }, [customValidate, required, min, max, formatPercentage]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateValue = useCallback((num: number | null) => {
      const clamped = num !== null ? Math.max(min, Math.min(max, num)) : null;
      const validation = validatePercentage(clamped);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);

      if (!disableRealtimeValidation && onValidate) {
        onValidate(validation.valid, clamped);
      }

      const finalValue = clamped !== null && !isNaN(clamped) ? clamped : null;

      if (isControlled) {
        if (onChange) onChange(finalValue);
      } else {
        setInternalValue(finalValue);
        if (onChange) onChange(finalValue);
      }

      if (!disableAutoFormat) {
        const formatted = formatPercentage(finalValue);
        setDisplayValue(formatted);
      }

      if (debug) {
        console.log('PercentageField update:', { num, clamped: finalValue, formatted: formatPercentage(finalValue), isValid: validation.valid });
      }
    }, [
      validatePercentage,
      min,
      max,
      isControlled,
      onChange,
      onValidate,
      disableRealtimeValidation,
      disableAutoFormat,
      formatPercentage,
      debug,
    ]);

    // ========================================================================
    // GESTIONNAIRES D'ÉVÉNEMENTS
    // ========================================================================

    const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
      const rawValue = e.target.value;
      setDisplayValue(rawValue);

      if (!disableRealtimeValidation) {
        const parsed = parsePercentage(rawValue);
        const validation = validatePercentage(parsed);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        if (onValidate) onValidate(validation.valid, parsed);
      }

      if (!isFocused) {
        const parsed = parsePercentage(rawValue);
        updateValue(parsed);
      }
    }, [disableRealtimeValidation, parsePercentage, validatePercentage, onValidate, updateValue, isFocused]);

    const handleFocus = useCallback(() => {
      setIsFocused(true);
      if (onFocus) onFocus();

      setTimeout(() => {
        inputRefInternal.current?.select();
      }, 10);
    }, [onFocus]);

    const handleBlur = useCallback(() => {
      setIsFocused(false);

      const parsed = parsePercentage(displayValue);
      const clamped = parsed !== null ? Math.max(min, Math.min(max, parsed)) : null;
      const validation = validatePercentage(clamped);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);
      if (onValidate) onValidate(validation.valid, clamped);

      if (!disableAutoFormat) {
        const formatted = formatPercentage(clamped);
        setDisplayValue(formatted);
      }

      if (!isControlled) {
        setInternalValue(clamped);
      }
      if (onChange) onChange(clamped);
      if (onBlur) onBlur();

      if (debug) {
        console.log('PercentageField blur:', { clamped, formatted: formatPercentage(clamped) });
      }
    }, [
      displayValue,
      parsePercentage,
      min,
      max,
      validatePercentage,
      onValidate,
      disableAutoFormat,
      formatPercentage,
      isControlled,
      onChange,
      onBlur,
      debug,
    ]);

    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
      const current = parsePercentage(displayValue) || 0;

      if (e.key === 'ArrowUp') {
        e.preventDefault();
        updateValue(current + step);
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        updateValue(current - step);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const parsed = parsePercentage(displayValue);
        if (parsed !== null) {
          updateValue(parsed);
        }
        inputRefInternal.current?.blur();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        const formatted = formatPercentage(value);
        setDisplayValue(formatted);
        inputRefInternal.current?.blur();
      }
    }, [displayValue, parsePercentage, updateValue, step, formatPercentage, value]);

    // ========================================================================
    // PRÉSÉLECTIONS
    // ========================================================================

    const handlePreset = useCallback((percent: number) => {
      updateValue(percent / 100);
    }, [updateValue]);

    // ========================================================================
    // SYNC AVEC LA VALEUR EXTERNE
    // ========================================================================

    useEffect(() => {
      if (externalValue !== undefined && externalValue !== null && externalValue !== '') {
        const num = Number(externalValue);
        if (!isNaN(num) && num !== prevValueRef.current) {
          prevValueRef.current = num;
          if (!disableAutoFormat) {
            const formatted = formatPercentage(num);
            setDisplayValue(formatted);
          }
        }
      } else if (externalValue === null || externalValue === '') {
        setDisplayValue('');
        prevValueRef.current = null;
      }
    }, [externalValue, formatPercentage, disableAutoFormat]);

    // ========================================================================
    // INITIALISATION
    // ========================================================================

    useEffect(() => {
      if (defaultValue !== undefined && defaultValue !== null && defaultValue !== '' && !isControlled) {
        const num = Number(defaultValue);
        if (!isNaN(num)) {
          const formatted = formatPercentage(num);
          setDisplayValue(formatted);
          updateValue(num);
        }
      }
    }, [defaultValue, formatPercentage, updateValue, isControlled]);

    // ========================================================================
    // IMPERATIVE HANDLE
    // ========================================================================

    useImperativeHandle(ref, () => ({
      focus: () => inputRefInternal.current?.focus(),
      blur: () => inputRefInternal.current?.blur(),
      select: () => inputRefInternal.current?.select(),
      getValue: () => numericValue,
      setValue: (val: number | null) => updateValue(val),
      validate: () => {
        const validation = validatePercentage(numericValue);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        return validation.valid;
      },
    } as any));

    // ========================================================================
    // RENDU DU SLIDER
    // ========================================================================

    const renderSlider = () => {
      if (mode !== 'slider' && mode !== 'both') return null;

      const minPercent = min * 100;
      const maxPercent = max * 100;
      const currentPercent = numericValue !== null ? numericValue * 100 : minPercent;

      return (
        <div className="mt-2">
          <Slider
            min={minPercent}
            max={maxPercent}
            step={step * 100}
            value={[currentPercent]}
            onValueChange={(values) => updateValue(values[0] / 100)}
            disabled={disabled}
          />
          {showProgress && (
            <div className="mt-1 flex justify-between text-xs text-gray-500 dark:text-gray-400">
              <span>{formatPercentage(min)}</span>
              <span>{formatPercentage(max)}</span>
            </div>
          )}
        </div>
      );
    };

    // ========================================================================
    // RENDU DES PRÉSÉLECTIONS
    // ========================================================================

    const renderPresets = () => {
      if (!showPresets) return null;

      const presetValues = presets.map(p => p / 100);
      const labels = presetLabels || presets.map(p => `${p}%`);

      return (
        <div className="mt-2 flex flex-wrap gap-1">
          {presetValues.map((preset, index) => (
            <button
              key={`preset-${index}`}
              type="button"
              className={cn(
                'rounded-lg border border-gray-200 dark:border-gray-700 px-2 py-0.5 text-xs transition-colors',
                'hover:bg-gray-100 dark:hover:bg-gray-800',
                disabled && 'opacity-50 cursor-not-allowed'
              )}
              onClick={() => handlePreset(preset * 100)}
              disabled={disabled}
            >
              {labels[index] || `${preset * 100}%`}
            </button>
          ))}
        </div>
      );
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const hasError = !!error || !isValid || (required && numericValue === null);
    const isSuccess = !hasError && success && numericValue !== null;
    const progressValue = numericValue !== null ? numericValue * 100 : 0;

    const variantClasses = {
      default: 'border-gray-300 dark:border-gray-600',
      compact: 'border-gray-300 dark:border-gray-600 h-8 text-xs',
      minimal: 'border-b-2 border-gray-300 dark:border-gray-600 rounded-none',
      rounded: 'border-gray-300 dark:border-gray-600 rounded-full',
      outlined: 'border-2 border-gray-300 dark:border-gray-600',
    };

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
            {showFormatting && numericValue !== null && (
              <Badge variant="outline" size="xs" className="text-xs">
                {Math.round(progressValue)}%
              </Badge>
            )}
          </div>
        )}

        {/* Champ de saisie */}
        <div className="relative">
          <div className={cn(
            'relative flex items-center rounded-lg border transition-all',
            hasError 
              ? 'border-red-500 ring-2 ring-red-500/20 dark:border-red-400' 
              : isSuccess && !disabled
              ? 'border-green-500 ring-2 ring-green-500/20 dark:border-green-400'
              : isFocused
              ? 'border-brand-500 ring-2 ring-brand-500/20 dark:border-brand-400'
              : variantClasses[variant],
            disabled && 'opacity-50 cursor-not-allowed bg-gray-50 dark:bg-gray-800/50'
          )}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
        >
          {showIcon && (
            <PercentIcon className="absolute left-3 h-4 w-4 text-gray-400" />
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
            inputMode="decimal"
            className={cn(
              'w-full bg-transparent px-3 py-2 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 outline-none',
              disabled && 'cursor-not-allowed',
              showIcon && 'pl-9',
              variant === 'compact' && 'h-8 text-xs',
              variant === 'rounded' && 'h-10 rounded-full'
            )}
            placeholder={placeholder}
            value={displayValue}
            onChange={handleChange}
            onFocus={handleFocus}
            onBlur={handleBlur}
            onKeyDown={handleKeyDown}
            disabled={disabled}
            required={required}
            aria-label={ariaLabel || label}
            aria-describedby={ariaDescribedby}
            aria-invalid={hasError}
            aria-required={required}
            name={name}
          />

          {/* Barre de progression de fond */}
          {showProgress && numericValue !== null && !isFocused && (
            <div 
              className="absolute inset-y-0 left-0 rounded-l-lg bg-brand-50 dark:bg-brand-900/20 transition-all duration-300"
              style={{ width: `${Math.min(100, progressValue)}%` }}
            />
          )}

          {/* Icône de validation */}
          <div className="relative z-10 flex items-center gap-0.5 pr-2">
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

        {/* Description */}
        {description && (
          <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
        )}

        {/* Slider */}
        {renderSlider()}

        {/* Présélections */}
        {renderPresets()}

        {/* Barre de progression */}
        {showProgress && numericValue !== null && (
          <Progress
            value={progressValue}
            className="h-1 mt-1"
            variant={
              progressValue < 30 ? 'error' :
              progressValue < 70 ? 'warning' :
              'success'
            }
          />
        )}
      </div>
    );
  }
);

PercentageField.displayName = 'PercentageField';

// ============================================================================
// EXPORTS
// ============================================================================

export default PercentageField;

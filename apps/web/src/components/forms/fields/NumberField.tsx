// apps/web/src/components/forms/fields/NumberField.tsx
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
  KeyboardEvent,
  ChangeEvent,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronUpIcon,
  ChevronDownIcon,
  PlusIcon,
  MinusIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
  ArrowPathIcon,
  CalculatorIcon,
  PercentIcon,
  CurrencyDollarIcon,
  AdjustmentsHorizontalIcon,
  ArrowsUpDownIcon,
} from '@heroicons/react/24/outline';
import {
  CheckCircleIcon as CheckCircleSolid,
  ExclamationCircleIcon as ExclamationCircleSolid,
} from '@heroicons/react/24/solid';
import { Label } from '@/components/common/Label';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Tooltip } from '@/components/common/Tooltip';
import { Slider } from '@/components/common/Slider';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type NumberFormat = 'decimal' | 'currency' | 'percentage' | 'scientific' | 'engineering' | 'compact' | 'custom';
export type NumberRounding = 'none' | 'floor' | 'ceil' | 'round' | 'truncate' | 'bankers';
export type NumberDisplay = 'input' | 'slider' | 'both';
export type NumberFieldVariant = 'default' | 'compact' | 'minimal' | 'rounded' | 'outlined';
export type NumberStepper = 'none' | 'buttons' | 'arrows' | 'both';

export interface NumberFieldProps {
  // --- Contrôle ---
  /** Valeur du champ */
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
  variant?: NumberFieldVariant;
  /** Mode d'affichage */
  displayMode?: NumberDisplay;
  /** Afficher les boutons de stepper */
  stepper?: NumberStepper;
  /** Afficher le slider */
  showSlider?: boolean;
  /** Afficher le formatage */
  showFormatting?: boolean;
  /** Afficher l'icône de validation */
  showValidationIcon?: boolean;
  /** Afficher les présets */
  showPresets?: boolean;

  // --- Formatage ---
  /** Format numérique */
  format?: NumberFormat;
  /** Devise (pour currency) */
  currency?: string;
  /** Nombre de décimales */
  decimals?: number;
  /** Séparateur de milliers */
  thousandsSeparator?: string;
  /** Séparateur décimal */
  decimalSeparator?: string;
  /** Préfixe */
  prefix?: string;
  /** Suffixe */
  suffix?: string;
  /** Arrondi */
  rounding?: NumberRounding;
  /** Arrondi à */
  roundTo?: number;

  // --- Comportement ---
  /** Valeur minimale */
  min?: number;
  /** Valeur maximale */
  max?: number;
  /** Pas d'incrémentation */
  step?: number;
  /** Désactiver le champ */
  disabled?: boolean;
  /** Rendre le champ obligatoire */
  required?: boolean;
  /** Autoriser les valeurs négatives */
  allowNegative?: boolean;
  /** Autoriser les valeurs nulles */
  allowNull?: boolean;
  /** Désactiver les décimales */
  allowDecimals?: boolean;
  /** Désactiver la validation en temps réel */
  disableRealtimeValidation?: boolean;
  /** Désactiver le formatage automatique */
  disableAutoFormat?: boolean;

  // --- Présets ---
  /** Valeurs présélectionnées */
  presets?: number[];
  /** Libellés des présets */
  presetLabels?: string[];
  /** Pourcentages présélectionnés */
  percentagePresets?: number[];

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

const DEFAULT_STEP = 1;
const DEFAULT_DECIMALS = 0;
const DEFAULT_MIN = -Infinity;
const DEFAULT_MAX = Infinity;

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const NumberField = forwardRef<HTMLInputElement, NumberFieldProps>(
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
      placeholder = '0',
      description,
      error,
      success,
      info,
      variant = 'default',
      displayMode = 'input',
      stepper = 'both',
      showSlider = false,
      showFormatting = true,
      showValidationIcon = true,
      showPresets = true,

      // Formatage
      format = 'decimal',
      currency = 'USD',
      decimals = DEFAULT_DECIMALS,
      thousandsSeparator = ' ',
      decimalSeparator = '.',
      prefix = '',
      suffix = '',
      rounding = 'round',
      roundTo,

      // Comportement
      min = DEFAULT_MIN,
      max = DEFAULT_MAX,
      step = DEFAULT_STEP,
      disabled = false,
      required = false,
      allowNegative = true,
      allowNull = true,
      allowDecimals = true,
      disableRealtimeValidation = false,
      disableAutoFormat = false,

      // Présets
      presets = [],
      presetLabels = [],
      percentagePresets = [25, 50, 75, 100],

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

    // ========================================================================
    // FORMATAGE
    // ========================================================================

    const formatNumber = useCallback((num: number | null): string => {
      if (num === null || num === undefined || isNaN(num)) return '';

      if (customFormat) {
        return customFormat(num);
      }

      let number = num;
      let formatted = '';

      // Arrondi
      const decimalsToUse = roundTo !== undefined ? Math.floor(roundTo) : decimals;
      const factor = Math.pow(10, decimalsToUse);

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
        case 'bankers':
          // Arrondi bancaire (au plus proche, .5 vers le pair)
          const rounded = Math.round(number * factor);
          const diff = Math.abs(rounded - number * factor);
          if (diff < 0.0001) {
            number = rounded / factor;
          } else {
            number = Math.round(number * factor) / factor;
          }
          break;
        default:
          number = Math.round(number * factor) / factor;
      }

      // Formatage selon le type
      switch (format) {
        case 'currency':
          formatted = new Intl.NumberFormat('fr-FR', {
            style: 'currency',
            currency: currency,
            minimumFractionDigits: decimalsToUse,
            maximumFractionDigits: decimalsToUse,
          }).format(number);
          break;

        case 'percentage':
          formatted = (number * 100).toFixed(decimalsToUse) + '%';
          break;

        case 'scientific':
          formatted = number.toExponential(decimalsToUse);
          break;

        case 'engineering':
          const exp = Math.floor(Math.log10(Math.abs(number)) / 3) * 3;
          const mantissa = number / Math.pow(10, exp);
          formatted = mantissa.toFixed(decimalsToUse) + 'e' + (exp >= 0 ? '+' : '') + exp;
          break;

        case 'compact':
          if (Math.abs(number) >= 1e9) {
            formatted = (number / 1e9).toFixed(1) + 'B';
          } else if (Math.abs(number) >= 1e6) {
            formatted = (number / 1e6).toFixed(1) + 'M';
          } else if (Math.abs(number) >= 1e3) {
            formatted = (number / 1e3).toFixed(1) + 'k';
          } else {
            formatted = number.toFixed(decimalsToUse);
          }
          break;

        default:
          // Decimal
          const parts = number.toFixed(decimalsToUse).split('.');
          if (thousandsSeparator !== ',') {
            parts[0] = parts[0].replace(/\B(?=(\d{3})+(?!\d))/g, thousandsSeparator);
          }
          if (decimalSeparator !== '.') {
            formatted = parts.join(decimalSeparator);
          } else {
            formatted = parts.join('.');
          }
      }

      // Ajouter préfixe/suffixe
      if (prefix && format !== 'currency') {
        formatted = prefix + formatted;
      }
      if (suffix && format !== 'percentage') {
        formatted = formatted + suffix;
      }

      return formatted;
    }, [
      customFormat,
      decimals,
      roundTo,
      rounding,
      format,
      currency,
      thousandsSeparator,
      decimalSeparator,
      prefix,
      suffix,
    ]);

    const parseNumber = useCallback((text: string): number | null => {
      if (!text || text.trim() === '') return null;

      if (customParse) {
        return customParse(text);
      }

      let cleaned = text.trim();

      // Retirer préfixe et suffixe
      if (prefix) cleaned = cleaned.replace(new RegExp(`^${prefix}`), '');
      if (suffix) cleaned = cleaned.replace(new RegExp(`${suffix}$`), '');

      // Retirer le symbole de pourcentage
      if (format === 'percentage') {
        cleaned = cleaned.replace(/%/g, '');
        const num = parseFloat(cleaned);
        return isNaN(num) ? null : num / 100;
      }

      // Retirer le symbole de devise
      if (format === 'currency') {
        cleaned = cleaned.replace(/[^0-9.,\-+]/g, '');
      }

      // Remplacer les séparateurs
      if (decimalSeparator !== '.') {
        cleaned = cleaned.replace(new RegExp(`\\${thousandsSeparator}`, 'g'), '')
                         .replace(new RegExp(`\\${decimalSeparator}`), '.');
      } else {
        cleaned = cleaned.replace(/,/g, '');
      }

      const num = parseFloat(cleaned);
      return isNaN(num) ? null : num;
    }, [customParse, prefix, suffix, format, thousandsSeparator, decimalSeparator]);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validateNumber = useCallback((num: number | null): { valid: boolean; message: string } => {
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

      if (!allowNegative && num < 0) {
        return { valid: false, message: 'Les valeurs négatives ne sont pas autorisées' };
      }

      if (min !== -Infinity && num < min) {
        return { valid: false, message: `La valeur minimale est ${formatNumber(min)}` };
      }

      if (max !== Infinity && num > max) {
        return { valid: false, message: `La valeur maximale est ${formatNumber(max)}` };
      }

      if (!allowDecimals && !Number.isInteger(num)) {
        return { valid: false, message: 'Les décimales ne sont pas autorisées' };
      }

      return { valid: true, message: '' };
    }, [
      customValidate,
      required,
      allowNegative,
      min,
      max,
      allowDecimals,
      formatNumber,
    ]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateValue = useCallback((num: number | null) => {
      const validation = validateNumber(num);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);

      if (!disableRealtimeValidation && onValidate) {
        onValidate(validation.valid, num);
      }

      const finalValue = num !== null && !isNaN(num) ? num : (allowNull ? null : 0);

      if (isControlled) {
        if (onChange) onChange(finalValue);
      } else {
        setInternalValue(finalValue);
        if (onChange) onChange(finalValue);
      }

      if (!disableAutoFormat) {
        const formatted = formatNumber(finalValue);
        setDisplayValue(formatted);
      }

      if (debug) {
        console.log('NumberField update:', { num, finalValue, formatted: formatNumber(finalValue), isValid: validation.valid });
      }
    }, [
      validateNumber,
      isControlled,
      onChange,
      onValidate,
      disableRealtimeValidation,
      disableAutoFormat,
      allowNull,
      formatNumber,
      debug,
    ]);

    // ========================================================================
    // GESTIONNAIRES D'ÉVÉNEMENTS
    // ========================================================================

    const handleChange = useCallback((e: ChangeEvent<HTMLInputElement>) => {
      const rawValue = e.target.value;
      setDisplayValue(rawValue);

      if (!disableRealtimeValidation) {
        const parsed = parseNumber(rawValue);
        const validation = validateNumber(parsed);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        if (onValidate) onValidate(validation.valid, parsed);
      }

      if (!isFocused) {
        const parsed = parseNumber(rawValue);
        updateValue(parsed);
      }
    }, [disableRealtimeValidation, parseNumber, validateNumber, onValidate, updateValue, isFocused]);

    const handleFocus = useCallback(() => {
      setIsFocused(true);
      if (onFocus) onFocus();

      // Sélectionner tout le texte
      setTimeout(() => {
        inputRefInternal.current?.select();
      }, 10);
    }, [onFocus]);

    const handleBlur = useCallback(() => {
      setIsFocused(false);

      const parsed = parseNumber(displayValue);
      const finalValue = parsed !== null && !isNaN(parsed) ? parsed : (allowNull ? null : 0);

      if (!disableAutoFormat) {
        const formatted = formatNumber(finalValue);
        setDisplayValue(formatted);
      }

      const validation = validateNumber(finalValue);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);
      if (onValidate) onValidate(validation.valid, finalValue);

      if (!isControlled) {
        setInternalValue(finalValue);
      }
      if (onChange) onChange(finalValue);
      if (onBlur) onBlur();

      if (debug) {
        console.log('NumberField blur:', { finalValue, formatted: formatNumber(finalValue) });
      }
    }, [
      displayValue,
      parseNumber,
      allowNull,
      disableAutoFormat,
      formatNumber,
      validateNumber,
      onValidate,
      isControlled,
      onChange,
      onBlur,
      debug,
    ]);

    const handleKeyDown = useCallback((e: KeyboardEvent<HTMLInputElement>) => {
      const current = parseNumber(displayValue) || 0;

      if (e.key === 'ArrowUp') {
        e.preventDefault();
        updateValue(current + step);
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        updateValue(current - step);
      } else if (e.key === 'Enter') {
        e.preventDefault();
        const parsed = parseNumber(displayValue);
        if (parsed !== null) {
          updateValue(parsed);
        }
        inputRefInternal.current?.blur();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        const formatted = formatNumber(value);
        setDisplayValue(formatted);
        inputRefInternal.current?.blur();
      }
    }, [displayValue, parseNumber, updateValue, step, formatNumber, value]);

    // ========================================================================
    // STEPPER
    // ========================================================================

    const increment = useCallback(() => {
      const current = numericValue || 0;
      const newValue = Math.min(max, current + step);
      updateValue(newValue);
    }, [numericValue, max, step, updateValue]);

    const decrement = useCallback(() => {
      const current = numericValue || 0;
      const newValue = Math.max(min, current - step);
      updateValue(newValue);
    }, [numericValue, min, step, updateValue]);

    // ========================================================================
    // PRÉSÉLECTIONS
    // ========================================================================

    const handlePreset = useCallback((preset: number) => {
      updateValue(preset);
    }, [updateValue]);

    const handlePercentagePreset = useCallback((percent: number) => {
      const current = numericValue || 0;
      const newValue = (current * percent) / 100;
      updateValue(newValue);
    }, [numericValue, updateValue]);

    // ========================================================================
    // SYNC AVEC LA VALEUR EXTERNE
    // ========================================================================

    useEffect(() => {
      if (externalValue !== undefined && externalValue !== null && externalValue !== '') {
        const num = Number(externalValue);
        if (!isNaN(num) && num !== prevValueRef.current) {
          prevValueRef.current = num;
          if (!disableAutoFormat) {
            const formatted = formatNumber(num);
            setDisplayValue(formatted);
          }
        }
      } else if (externalValue === null || externalValue === '') {
        setDisplayValue('');
        prevValueRef.current = null;
      }
    }, [externalValue, formatNumber, disableAutoFormat]);

    // ========================================================================
    // INITIALISATION
    // ========================================================================

    useEffect(() => {
      if (defaultValue !== undefined && defaultValue !== null && defaultValue !== '' && !isControlled) {
        const num = Number(defaultValue);
        if (!isNaN(num)) {
          const formatted = formatNumber(num);
          setDisplayValue(formatted);
          updateValue(num);
        }
      }
    }, [defaultValue, formatNumber, updateValue, isControlled]);

    // ========================================================================
    // IMPERATIVE HANDLE
    // ========================================================================

    useImperativeHandle(ref, () => ({
      focus: () => inputRefInternal.current?.focus(),
      blur: () => inputRefInternal.current?.blur(),
      select: () => inputRefInternal.current?.select(),
      getValue: () => numericValue,
      setValue: (val: number | null) => updateValue(val),
      increment,
      decrement,
      validate: () => {
        const validation = validateNumber(numericValue);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        return validation.valid;
      },
    } as any));

    // ========================================================================
    // RENDU DU SLIDER
    // ========================================================================

    const renderSlider = () => {
      if (!showSlider && displayMode !== 'both') return null;

      const hasMinMax = min !== -Infinity && max !== Infinity;
      if (!hasMinMax) return null;

      return (
        <div className="mt-2">
          <Slider
            min={min}
            max={max}
            step={step}
            value={[numericValue !== null ? numericValue : min]}
            onValueChange={(values) => updateValue(values[0])}
            disabled={disabled}
          />
        </div>
      );
    };

    // ========================================================================
    // RENDU DES PRÉSÉLECTIONS
    // ========================================================================

    const renderPresets = () => {
      if (!showPresets) return null;
      if (presets.length === 0 && percentagePresets.length === 0) return null;

      return (
        <div className="mt-2 flex flex-wrap gap-1">
          {presets.map((preset, index) => (
            <button
              key={`preset-${index}`}
              type="button"
              className="rounded-lg border border-gray-200 dark:border-gray-700 px-2 py-0.5 text-xs transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
              onClick={() => handlePreset(preset)}
              disabled={disabled}
            >
              {formatNumber(preset)}
            </button>
          ))}
          {percentagePresets.map((percent) => (
            <button
              key={`pct-${percent}`}
              type="button"
              className="rounded-lg border border-gray-200 dark:border-gray-700 px-2 py-0.5 text-xs transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
              onClick={() => handlePercentagePreset(percent)}
              disabled={disabled}
            >
              {percent}%
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

    const sizeClasses = {
      default: 'h-10 text-sm',
      compact: 'h-8 text-xs',
      minimal: 'h-9 text-sm',
      rounded: 'h-10 text-sm rounded-full',
      outlined: 'h-10 text-sm border-2',
    };

    const variantClasses = {
      default: 'border-gray-300 dark:border-gray-600',
      compact: 'border-gray-300 dark:border-gray-600',
      minimal: 'border-b-2 border-gray-300 dark:border-gray-600 rounded-none',
      rounded: 'border-gray-300 dark:border-gray-600 rounded-full',
      outlined: 'border-2 border-gray-300 dark:border-gray-600',
    };

    const showStepperButtons = stepper === 'buttons' || stepper === 'both';
    const showStepperArrows = stepper === 'arrows' || stepper === 'both';

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
            {showFormatting && format !== 'decimal' && (
              <Badge variant="outline" size="xs" className="text-xs">
                {format === 'currency' && currency}
                {format === 'percentage' && '%'}
                {format === 'scientific' && 'Sci'}
                {format === 'engineering' && 'Eng'}
                {format === 'compact' && 'Compact'}
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
            disabled && 'opacity-50 cursor-not-allowed bg-gray-50 dark:bg-gray-800/50',
            sizeClasses[variant]
          )}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
        >
          {/* Préfixe */}
          {prefix && format !== 'currency' && (
            <span className="flex-shrink-0 pl-3 text-gray-500 dark:text-gray-400">
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
            inputMode="decimal"
            className={cn(
              'w-full bg-transparent px-3 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 outline-none',
              disabled && 'cursor-not-allowed',
              prefix && 'pl-2'
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

          {/* Suffixe */}
          {suffix && format !== 'percentage' && (
            <span className="flex-shrink-0 pr-3 text-gray-500 dark:text-gray-400">
              {suffix}
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

          {/* Stepper - Boutons */}
          {showStepperButtons && !disabled && (
            <div className="flex flex-col border-l border-gray-200 dark:border-gray-700">
              <button
                type="button"
                className="flex h-1/2 w-6 items-center justify-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors rounded-tr-lg"
                onClick={increment}
                disabled={disabled || (numericValue !== null && numericValue >= max)}
              >
                <PlusIcon className="h-3 w-3" />
              </button>
              <button
                type="button"
                className="flex h-1/2 w-6 items-center justify-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors rounded-br-lg border-t border-gray-200 dark:border-gray-700"
                onClick={decrement}
                disabled={disabled || (numericValue !== null && numericValue <= min)}
              >
                <MinusIcon className="h-3 w-3" />
              </button>
            </div>
          )}

          {/* Stepper - Flèches */}
          {showStepperArrows && !showStepperButtons && !disabled && (
            <div className="flex flex-col border-l border-gray-200 dark:border-gray-700">
              <button
                type="button"
                className="flex h-1/2 w-6 items-center justify-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors rounded-tr-lg"
                onClick={increment}
                disabled={disabled || (numericValue !== null && numericValue >= max)}
              >
                <ChevronUpIcon className="h-3 w-3" />
              </button>
              <button
                type="button"
                className="flex h-1/2 w-6 items-center justify-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors rounded-br-lg border-t border-gray-200 dark:border-gray-700"
                onClick={decrement}
                disabled={disabled || (numericValue !== null && numericValue <= min)}
              >
                <ChevronDownIcon className="h-3 w-3" />
              </button>
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

        {/* Description */}
        {description && (
          <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
        )}

        {/* Slider */}
        {renderSlider()}

        {/* Présélections */}
        {renderPresets()}
      </div>
    );
  }
);

NumberField.displayName = 'NumberField';

// ============================================================================
// EXPORTS
// ============================================================================

export default NumberField;

// apps/web/src/components/forms/fields/SliderField.tsx
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
  PlusIcon,
  MinusIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
  CheckIcon,
  ExclamationCircleIcon,
  AdjustmentsHorizontalIcon,
} from '@heroicons/react/24/outline';
import {
  CheckCircleIcon as CheckCircleSolid,
  ExclamationCircleIcon as ExclamationCircleSolid,
} from '@heroicons/react/24/solid';
import { Label } from '@/components/common/Label';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Tooltip } from '@/components/common/Tooltip';
import { Slider as SliderComponent } from '@/components/common/Slider';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type SliderDisplay = 'slider' | 'input' | 'both';
export type SliderVariant = 'default' | 'compact' | 'minimal' | 'rounded' | 'outlined';
export type SliderMark = {
  value: number;
  label?: string;
  color?: string;
};

export interface SliderFieldProps {
  // --- Contrôle ---
  /** Valeur du champ (simple ou double) */
  value?: number | [number, number] | null;
  /** Valeur par défaut */
  defaultValue?: number | [number, number] | null;
  /** Callback de changement */
  onChange?: (value: number | [number, number] | null) => void;
  /** Callback de blur */
  onBlur?: () => void;
  /** Callback de focus */
  onFocus?: () => void;
  /** Callback de validation */
  onValidate?: (valid: boolean, value: number | [number, number] | null) => void;

  // --- Apparence ---
  /** Libellé du champ */
  label?: string;
  /** Description */
  description?: string;
  /** Message d'erreur */
  error?: string;
  /** Message de succès */
  success?: string;
  /** Message d'information */
  info?: string;
  /** Variante d'affichage */
  variant?: SliderVariant;
  /** Mode d'affichage */
  displayMode?: SliderDisplay;
  /** Afficher les marqueurs */
  showMarks?: boolean;
  /** Afficher les boutons de step */
  showStepper?: boolean;
  /** Afficher l'icône de validation */
  showValidationIcon?: boolean;
  /** Afficher les présets */
  showPresets?: boolean;
  /** Afficher la valeur */
  showValue?: boolean;

  // --- Valeurs ---
  /** Valeur minimale */
  min?: number;
  /** Valeur maximale */
  max?: number;
  /** Pas d'incrémentation */
  step?: number;
  /** Marqueurs */
  marks?: SliderMark[];
  /** Présets */
  presets?: (number | [number, number])[];
  /** Libellés des présets */
  presetLabels?: string[];
  /** Mode double */
  range?: boolean;

  // --- Comportement ---
  /** Désactiver le champ */
  disabled?: boolean;
  /** Rendre le champ obligatoire */
  required?: boolean;
  /** Désactiver les valeurs décimales */
  allowDecimals?: boolean;
  /** Désactiver la validation en temps réel */
  disableRealtimeValidation?: boolean;
  /** Permettre la valeur null */
  allowNull?: boolean;
  /** Désactiver les boutons de step */
  disableStepper?: boolean;

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
  /** Fonction de validation personnalisée */
  customValidate?: (value: number | [number, number] | null) => boolean | string;
  /** Fonction de formatage personnalisée */
  customFormat?: (value: number) => string;
  /** Ref */
  inputRef?: React.Ref<HTMLInputElement>;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const DEFAULT_MIN = 0;
const DEFAULT_MAX = 100;
const DEFAULT_STEP = 1;
const DEFAULT_VALUE = 50;
const DEFAULT_RANGE_VALUE: [number, number] = [25, 75];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const SliderField = forwardRef<HTMLDivElement, SliderFieldProps>(
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
      description,
      error,
      success,
      info,
      variant = 'default',
      displayMode = 'both',
      showMarks = true,
      showStepper = true,
      showValidationIcon = true,
      showPresets = true,
      showValue = true,

      // Valeurs
      min = DEFAULT_MIN,
      max = DEFAULT_MAX,
      step = DEFAULT_STEP,
      marks = [],
      presets = [],
      presetLabels = [],
      range = false,

      // Comportement
      disabled = false,
      required = false,
      allowDecimals = true,
      disableRealtimeValidation = false,
      allowNull = true,
      disableStepper = false,

      // Accessibilité
      ariaLabel,
      ariaDescribedby,
      id,
      name,

      // Avancé
      customValidate,
      customFormat,
      inputRef,
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const containerRef = useRef<HTMLDivElement>(null);
    const inputRefInternal = useRef<HTMLInputElement>(null);
    const prevValueRef = useRef<number | [number, number] | null>(null);

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalValue, setInternalValue] = useState<number | [number, number] | null>(
      defaultValue !== undefined ? defaultValue : (range ? DEFAULT_RANGE_VALUE : DEFAULT_VALUE)
    );
    const [isFocused, setIsFocused] = useState(false);
    const [isValid, setIsValid] = useState(true);
    const [validationMessage, setValidationMessage] = useState<string>('');
    const [isHovered, setIsHovered] = useState(false);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined ? externalValue : internalValue;
    const isControlled = externalValue !== undefined;
    const isRange = range;
    const isSingle = !isRange;

    const numericValue = isRange 
      ? (Array.isArray(value) ? value : [min, max])
      : (typeof value === 'number' ? value : DEFAULT_VALUE);

    const sliderValue = isRange 
      ? (Array.isArray(numericValue) ? numericValue : [min, max])
      : [typeof numericValue === 'number' ? numericValue : DEFAULT_VALUE];

    // ========================================================================
    // FORMATAGE
    // ========================================================================

    const formatValue = useCallback((num: number): string => {
      if (customFormat) {
        return customFormat(num);
      }
      
      const decimals = allowDecimals ? 2 : 0;
      return num.toFixed(decimals);
    }, [customFormat, allowDecimals]);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validateSlider = useCallback((val: number | [number, number] | null): { valid: boolean; message: string } => {
      if (customValidate) {
        const result = customValidate(val);
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        return { valid: true, message: '' };
      }

      if (val === null || val === undefined) {
        if (required) {
          return { valid: false, message: 'La valeur est requise' };
        }
        return { valid: true, message: '' };
      }

      if (isRange && Array.isArray(val)) {
        const [vMin, vMax] = val;
        if (isNaN(vMin) || isNaN(vMax)) {
          return { valid: false, message: 'Valeurs invalides' };
        }
        if (vMin < min) {
          return { valid: false, message: `La valeur minimale est ${formatValue(min)}` };
        }
        if (vMax > max) {
          return { valid: false, message: `La valeur maximale est ${formatValue(max)}` };
        }
        if (vMin > vMax) {
          return { valid: false, message: 'La valeur minimale ne peut pas être supérieure à la valeur maximale' };
        }
      } else if (typeof val === 'number') {
        if (isNaN(val)) {
          return { valid: false, message: 'Valeur invalide' };
        }
        if (val < min) {
          return { valid: false, message: `La valeur minimale est ${formatValue(min)}` };
        }
        if (val > max) {
          return { valid: false, message: `La valeur maximale est ${formatValue(max)}` };
        }
      } else {
        return { valid: false, message: 'Type de valeur invalide' };
      }

      return { valid: true, message: '' };
    }, [customValidate, required, isRange, min, max, formatValue]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateValue = useCallback((val: number | [number, number] | null) => {
      const validation = validateSlider(val);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);

      if (!disableRealtimeValidation && onValidate) {
        onValidate(validation.valid, val);
      }

      const finalValue = val !== null && !isNaN(Array.isArray(val) ? val[0] : val) 
        ? val 
        : (allowNull ? null : (isRange ? [min, max] : min));

      if (isControlled) {
        if (onChange) onChange(finalValue);
      } else {
        setInternalValue(finalValue);
        if (onChange) onChange(finalValue);
      }

      if (debug) {
        console.log('SliderField update:', { val: finalValue, isValid: validation.valid });
      }
    }, [
      validateSlider,
      isControlled,
      onChange,
      onValidate,
      disableRealtimeValidation,
      allowNull,
      isRange,
      min,
      max,
      debug,
    ]);

    // ========================================================================
    // GESTIONNAIRES D'ÉVÉNEMENTS
    // ========================================================================

    const handleSliderChange = useCallback((values: number[]) => {
      if (isRange) {
        updateValue([values[0], values[1]]);
      } else {
        updateValue(values[0]);
      }
    }, [isRange, updateValue]);

    const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
      const val = parseFloat(e.target.value);
      if (!isNaN(val)) {
        const clamped = Math.max(min, Math.min(max, val));
        updateValue(isRange ? [clamped, Array.isArray(numericValue) ? numericValue[1] : max] : clamped);
      }
    }, [isRange, numericValue, min, max, updateValue]);

    const handleFocus = useCallback(() => {
      setIsFocused(true);
      if (onFocus) onFocus();
    }, [onFocus]);

    const handleBlur = useCallback(() => {
      setIsFocused(false);
      if (onBlur) onBlur();
    }, [onBlur]);

    // ========================================================================
    // PRÉSÉLECTIONS
    // ========================================================================

    const handlePreset = useCallback((preset: number | [number, number]) => {
      updateValue(preset);
    }, [updateValue]);

    // ========================================================================
    // SYNC AVEC LA VALEUR EXTERNE
    // ========================================================================

    useEffect(() => {
      if (externalValue !== undefined && JSON.stringify(externalValue) !== JSON.stringify(prevValueRef.current)) {
        prevValueRef.current = externalValue;
        const validation = validateSlider(externalValue);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
      }
    }, [externalValue, validateSlider]);

    // ========================================================================
    // INITIALISATION
    // ========================================================================

    useEffect(() => {
      if (defaultValue !== undefined && !isControlled) {
        updateValue(defaultValue);
      }
    }, [defaultValue, updateValue, isControlled]);

    // ========================================================================
    // IMPERATIVE HANDLE
    // ========================================================================

    useImperativeHandle(ref, () => ({
      focus: () => containerRef.current?.focus(),
      blur: () => containerRef.current?.blur(),
      getValue: () => value,
      setValue: (val: number | [number, number] | null) => updateValue(val),
      validate: () => {
        const validation = validateSlider(value);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        return validation.valid;
      },
    } as any));

    // ========================================================================
    // RENDU
    // ========================================================================

    const hasError = !!error || !isValid || (required && (value === null || value === undefined));
    const isSuccess = !hasError && success && value !== null && value !== undefined;

    const displayValue = isRange 
      ? (Array.isArray(numericValue) ? `${formatValue(numericValue[0])} - ${formatValue(numericValue[1])}` : '')
      : (typeof numericValue === 'number' ? formatValue(numericValue) : '');

    const variantClasses = {
      default: 'border-gray-300 dark:border-gray-600',
      compact: 'border-gray-300 dark:border-gray-600 p-2',
      minimal: 'border-b-2 border-gray-300 dark:border-gray-600 rounded-none',
      rounded: 'border-gray-300 dark:border-gray-600 rounded-full',
      outlined: 'border-2 border-gray-300 dark:border-gray-600',
    };

    return (
      <div ref={containerRef} className="relative space-y-1.5" id={id}>
        {/* Label */}
        {label && (
          <div className="flex items-center justify-between">
            <Label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {label}
              {required && <span className="ml-1 text-red-500">*</span>}
            </Label>
            {showValue && (
              <Badge variant="outline" size="sm" className="font-mono">
                {displayValue}
              </Badge>
            )}
          </div>
        )}

        {/* Description */}
        {description && (
          <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
        )}

        {/* Slider */}
        <div className={cn(
          'relative rounded-lg border p-3 transition-all',
          hasError 
            ? 'border-red-500 ring-2 ring-red-500/20 dark:border-red-400' 
            : isSuccess && !disabled
            ? 'border-green-500 ring-2 ring-green-500/20 dark:border-green-400'
            : isFocused
            ? 'border-brand-500 ring-2 ring-brand-500/20 dark:border-brand-400'
            : variantClasses[variant],
          disabled && 'opacity-50 cursor-not-allowed bg-gray-50 dark:bg-gray-800/50'
        )}>
          <SliderComponent
            min={min}
            max={max}
            step={step}
            value={sliderValue}
            onValueChange={handleSliderChange}
            disabled={disabled}
            showMarks={showMarks}
            marks={marks}
            formatValue={formatValue}
            className="py-2"
          />

          {/* Inputs pour le mode input */}
          {displayMode !== 'slider' && (
            <div className="mt-3 flex items-center gap-3">
              {isRange ? (
                <>
                  <div className="flex-1">
                    <Label className="text-xs text-gray-500 dark:text-gray-400">Min</Label>
                    <input
                      type="number"
                      className={cn(
                        'w-full rounded-lg border px-3 py-1.5 text-sm transition-all',
                        'border-gray-300 dark:border-gray-600 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:focus:ring-brand-500/20',
                        disabled && 'opacity-50 cursor-not-allowed bg-gray-50 dark:bg-gray-800/50'
                      )}
                      value={Array.isArray(numericValue) ? numericValue[0] : min}
                      onChange={handleInputChange}
                      onFocus={handleFocus}
                      onBlur={handleBlur}
                      disabled={disabled}
                      min={min}
                      max={max}
                      step={step}
                    />
                  </div>
                  <span className="text-gray-400">→</span>
                  <div className="flex-1">
                    <Label className="text-xs text-gray-500 dark:text-gray-400">Max</Label>
                    <input
                      type="number"
                      className={cn(
                        'w-full rounded-lg border px-3 py-1.5 text-sm transition-all',
                        'border-gray-300 dark:border-gray-600 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:focus:ring-brand-500/20',
                        disabled && 'opacity-50 cursor-not-allowed bg-gray-50 dark:bg-gray-800/50'
                      )}
                      value={Array.isArray(numericValue) ? numericValue[1] : max}
                      onChange={handleInputChange}
                      onFocus={handleFocus}
                      onBlur={handleBlur}
                      disabled={disabled}
                      min={min}
                      max={max}
                      step={step}
                    />
                  </div>
                </>
              ) : (
                <div className="flex-1">
                  <input
                    type="number"
                    className={cn(
                      'w-full rounded-lg border px-3 py-1.5 text-sm transition-all',
                      'border-gray-300 dark:border-gray-600 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:focus:ring-brand-500/20',
                      disabled && 'opacity-50 cursor-not-allowed bg-gray-50 dark:bg-gray-800/50'
                    )}
                    value={typeof numericValue === 'number' ? numericValue : min}
                    onChange={handleInputChange}
                    onFocus={handleFocus}
                    onBlur={handleBlur}
                    disabled={disabled}
                    min={min}
                    max={max}
                    step={step}
                  />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Présets */}
        {showPresets && presets.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-1">
            {presets.map((preset, index) => (
              <button
                key={`preset-${index}`}
                type="button"
                className={cn(
                  'rounded-lg border border-gray-200 dark:border-gray-700 px-2 py-0.5 text-xs transition-colors',
                  'hover:bg-gray-100 dark:hover:bg-gray-800',
                  disabled && 'opacity-50 cursor-not-allowed'
                )}
                onClick={() => handlePreset(preset)}
                disabled={disabled}
              >
                {presetLabels[index] || (Array.isArray(preset) 
                  ? `${formatValue(preset[0])} - ${formatValue(preset[1])}` 
                  : formatValue(preset))}
              </button>
            ))}
          </div>
        )}

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

SliderField.displayName = 'SliderField';

// ============================================================================
// EXPORTS
// ============================================================================

export default SliderField;

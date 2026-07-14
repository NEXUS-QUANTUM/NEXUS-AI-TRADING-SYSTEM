// apps/web/src/components/forms/fields/RangeField.tsx
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
  ArrowsUpDownIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
  CheckIcon,
  ExclamationCircleIcon,
  PlusIcon,
  MinusIcon,
  ChevronDownIcon,
  ChevronUpIcon,
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
import { Slider } from '@/components/common/Slider';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type RangeValue = [number, number];
export type RangeVariant = 'default' | 'compact' | 'minimal' | 'rounded' | 'outlined';
export type RangeDisplay = 'slider' | 'inputs' | 'both';
export type RangeMark = {
  value: number;
  label?: string;
  color?: string;
};

export interface RangeFieldProps {
  // --- Contrôle ---
  /** Valeur du champ (min, max) */
  value?: RangeValue | null;
  /** Valeur par défaut */
  defaultValue?: RangeValue | null;
  /** Callback de changement */
  onChange?: (value: RangeValue | null) => void;
  /** Callback de blur */
  onBlur?: () => void;
  /** Callback de focus */
  onFocus?: () => void;
  /** Callback de validation */
  onValidate?: (valid: boolean, value: RangeValue | null) => void;

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
  variant?: RangeVariant;
  /** Mode d'affichage */
  displayMode?: RangeDisplay;
  /** Afficher les marqueurs */
  showMarks?: boolean;
  /** Afficher les boutons de step */
  showStepper?: boolean;
  /** Afficher l'icône de validation */
  showValidationIcon?: boolean;
  /** Afficher les présets */
  showPresets?: boolean;
  /** Afficher la distribution */
  showDistribution?: boolean;

  // --- Valeurs ---
  /** Valeur minimale */
  min?: number;
  /** Valeur maximale */
  max?: number;
  /** Pas d'incrémentation */
  step?: number;
  /** Marqueurs */
  marks?: RangeMark[];
  /** Présets */
  presets?: RangeValue[];
  /** Libellés des présets */
  presetLabels?: string[];

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
  customValidate?: (value: RangeValue | null) => boolean | string;
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
const DEFAULT_RANGE: RangeValue = [25, 75];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const RangeField = forwardRef<HTMLDivElement, RangeFieldProps>(
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
      showDistribution = true,

      // Valeurs
      min = DEFAULT_MIN,
      max = DEFAULT_MAX,
      step = DEFAULT_STEP,
      marks = [],
      presets = [],
      presetLabels = [],

      // Comportement
      disabled = false,
      required = false,
      allowDecimals = true,
      disableRealtimeValidation = false,
      allowNull = true,

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
    const minInputRef = useRef<HTMLInputElement>(null);
    const maxInputRef = useRef<HTMLInputElement>(null);
    const prevValueRef = useRef<RangeValue | null>(null);

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalValue, setInternalValue] = useState<RangeValue | null>(
      defaultValue || DEFAULT_RANGE
    );
    const [isFocused, setIsFocused] = useState(false);
    const [isValid, setIsValid] = useState(true);
    const [validationMessage, setValidationMessage] = useState<string>('');
    const [minDisplay, setMinDisplay] = useState<string>('');
    const [maxDisplay, setMaxDisplay] = useState<string>('');
    const [isDragging, setIsDragging] = useState(false);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined ? externalValue : internalValue;
    const isControlled = externalValue !== undefined;
    const rangeValue = value || [min, max];
    const [currentMin, currentMax] = rangeValue;

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

    const validateRange = useCallback((range: RangeValue | null): { valid: boolean; message: string } => {
      if (customValidate) {
        const result = customValidate(range);
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        return { valid: true, message: '' };
      }

      if (!range) {
        if (required) {
          return { valid: false, message: 'La plage est requise' };
        }
        return { valid: true, message: '' };
      }

      const [rMin, rMax] = range;

      if (isNaN(rMin) || isNaN(rMax)) {
        return { valid: false, message: 'Valeurs invalides' };
      }

      if (rMin < min) {
        return { valid: false, message: `La valeur minimale est ${formatValue(min)}` };
      }

      if (rMax > max) {
        return { valid: false, message: `La valeur maximale est ${formatValue(max)}` };
      }

      if (rMin > rMax) {
        return { valid: false, message: 'La valeur minimale ne peut pas être supérieure à la valeur maximale' };
      }

      return { valid: true, message: '' };
    }, [customValidate, required, min, max, formatValue]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateValue = useCallback((range: RangeValue | null) => {
      const validation = validateRange(range);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);

      if (!disableRealtimeValidation && onValidate) {
        onValidate(validation.valid, range);
      }

      const finalValue = range !== null && !isNaN(range[0]) && !isNaN(range[1]) 
        ? range 
        : (allowNull ? null : [min, max]);

      if (isControlled) {
        if (onChange) onChange(finalValue);
      } else {
        setInternalValue(finalValue);
        if (onChange) onChange(finalValue);
      }

      if (finalValue) {
        setMinDisplay(formatValue(finalValue[0]));
        setMaxDisplay(formatValue(finalValue[1]));
      }

      if (debug) {
        console.log('RangeField update:', { range: finalValue, isValid: validation.valid });
      }
    }, [
      validateRange,
      isControlled,
      onChange,
      onValidate,
      disableRealtimeValidation,
      allowNull,
      min,
      max,
      formatValue,
      debug,
    ]);

    // ========================================================================
    // GESTIONNAIRES DE CHAMPS
    // ========================================================================

    const handleMinChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
      const val = parseFloat(e.target.value);
      if (!isNaN(val)) {
        const newValue: RangeValue = [Math.min(val, currentMax), currentMax];
        updateValue(newValue);
      }
    }, [currentMax, updateValue]);

    const handleMaxChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
      const val = parseFloat(e.target.value);
      if (!isNaN(val)) {
        const newValue: RangeValue = [currentMin, Math.max(val, currentMin)];
        updateValue(newValue);
      }
    }, [currentMin, updateValue]);

    const handleSliderChange = useCallback((values: number[]) => {
      if (values.length === 2) {
        updateValue([values[0], values[1]]);
      }
    }, [updateValue]);

    // ========================================================================
    // GESTIONNAIRES D'ÉVÉNEMENTS
    // ========================================================================

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

    const handlePreset = useCallback((preset: RangeValue) => {
      updateValue(preset);
    }, [updateValue]);

    // ========================================================================
    // SYNC AVEC LA VALEUR EXTERNE
    // ========================================================================

    useEffect(() => {
      if (externalValue !== undefined) {
        const val = externalValue;
        if (JSON.stringify(val) !== JSON.stringify(prevValueRef.current)) {
          prevValueRef.current = val;
          if (val) {
            setMinDisplay(formatValue(val[0]));
            setMaxDisplay(formatValue(val[1]));
          }
          const validation = validateRange(val);
          setIsValid(validation.valid);
          setValidationMessage(validation.message);
        }
      }
    }, [externalValue, validateRange, formatValue]);

    // ========================================================================
    // INITIALISATION
    // ========================================================================

    useEffect(() => {
      if (defaultValue !== undefined && !isControlled) {
        const val = defaultValue;
        if (val) {
          setMinDisplay(formatValue(val[0]));
          setMaxDisplay(formatValue(val[1]));
        }
        updateValue(val);
      }
    }, [defaultValue, updateValue, isControlled, formatValue]);

    // ========================================================================
    // IMPERATIVE HANDLE
    // ========================================================================

    useImperativeHandle(ref, () => ({
      focus: () => containerRef.current?.focus(),
      blur: () => containerRef.current?.blur(),
      getValue: () => value,
      setValue: (val: RangeValue | null) => updateValue(val),
      setMin: (minVal: number) => {
        if (value) {
          updateValue([minVal, value[1]]);
        }
      },
      setMax: (maxVal: number) => {
        if (value) {
          updateValue([value[0], maxVal]);
        }
      },
      validate: () => {
        const validation = validateRange(value);
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

    const variantClasses = {
      default: 'border-gray-300 dark:border-gray-600',
      compact: 'border-gray-300 dark:border-gray-600',
      minimal: 'border-b-2 border-gray-300 dark:border-gray-600 rounded-none',
      rounded: 'border-gray-300 dark:border-gray-600 rounded-full',
      outlined: 'border-2 border-gray-300 dark:border-gray-600',
    };

    const showInputs = displayMode === 'inputs' || displayMode === 'both';
    const showSlider = displayMode === 'slider' || displayMode === 'both';

    return (
      <div ref={containerRef} className="relative space-y-1.5" id={id}>
        {/* Label */}
        {label && (
          <div className="flex items-center justify-between">
            <Label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {label}
              {required && <span className="ml-1 text-red-500">*</span>}
            </Label>
            {value && (
              <Badge variant="outline" size="sm" className="font-mono">
                {formatValue(value[0])} - {formatValue(value[1])}
              </Badge>
            )}
          </div>
        )}

        {/* Description */}
        {description && (
          <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
        )}

        {/* Slider */}
        {showSlider && (
          <div className="relative">
            <Slider
              min={min}
              max={max}
              step={step}
              value={value || [min, max]}
              onValueChange={handleSliderChange}
              disabled={disabled}
              showMarks={showMarks}
              marks={marks}
              formatValue={formatValue}
              className="py-2"
            />
          </div>
        )}

        {/* Inputs */}
        {showInputs && (
          <div className={cn(
            'flex items-center gap-3',
            variant === 'compact' && 'gap-2'
          )}>
            <div className="flex-1">
              <Label className="text-xs text-gray-500 dark:text-gray-400">Min</Label>
              <input
                ref={minInputRef}
                type="number"
                className={cn(
                  'w-full rounded-lg border px-3 py-2 text-sm transition-all',
                  hasError 
                    ? 'border-red-500 ring-2 ring-red-500/20 dark:border-red-400' 
                    : isSuccess && !disabled
                    ? 'border-green-500 ring-2 ring-green-500/20 dark:border-green-400'
                    : isFocused
                    ? 'border-brand-500 ring-2 ring-brand-500/20 dark:border-brand-400'
                    : 'border-gray-300 dark:border-gray-600',
                  disabled && 'opacity-50 cursor-not-allowed bg-gray-50 dark:bg-gray-800/50',
                  variant === 'compact' && 'h-8 text-xs',
                  variant === 'rounded' && 'rounded-full'
                )}
                value={value ? value[0] : ''}
                onChange={handleMinChange}
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
                ref={maxInputRef}
                type="number"
                className={cn(
                  'w-full rounded-lg border px-3 py-2 text-sm transition-all',
                  hasError 
                    ? 'border-red-500 ring-2 ring-red-500/20 dark:border-red-400' 
                    : isSuccess && !disabled
                    ? 'border-green-500 ring-2 ring-green-500/20 dark:border-green-400'
                    : isFocused
                    ? 'border-brand-500 ring-2 ring-brand-500/20 dark:border-brand-400'
                    : 'border-gray-300 dark:border-gray-600',
                  disabled && 'opacity-50 cursor-not-allowed bg-gray-50 dark:bg-gray-800/50',
                  variant === 'compact' && 'h-8 text-xs',
                  variant === 'rounded' && 'rounded-full'
                )}
                value={value ? value[1] : ''}
                onChange={handleMaxChange}
                onFocus={handleFocus}
                onBlur={handleBlur}
                disabled={disabled}
                min={min}
                max={max}
                step={step}
              />
            </div>
          </div>
        )}

        {/* Distribution */}
        {showDistribution && value && (
          <div className="mt-2 flex items-center gap-2">
            <div className="flex-1 h-1 bg-gray-200 dark:bg-gray-700 rounded-full overflow-hidden">
              <div
                className="h-full bg-brand-500 rounded-full"
                style={{
                  width: `${((value[1] - value[0]) / (max - min)) * 100}%`,
                  marginLeft: `${((value[0] - min) / (max - min)) * 100}%`,
                }}
              />
            </div>
            <Badge variant="outline" size="xs" className="font-mono">
              {formatValue(value[1] - value[0])}
            </Badge>
          </div>
        )}

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
                {presetLabels[index] || `${formatValue(preset[0])} - ${formatValue(preset[1])}`}
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

RangeField.displayName = 'RangeField';

// ============================================================================
// EXPORTS
// ============================================================================

export default RangeField;

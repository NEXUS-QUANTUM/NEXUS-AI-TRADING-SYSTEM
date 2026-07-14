// apps/web/src/components/forms/fields/TimeField.tsx
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
  ClockIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
  CheckIcon,
  ExclamationCircleIcon,
  SunIcon,
  MoonIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
} from '@heroicons/react/24/outline';
import {
  CheckCircleIcon as CheckCircleSolid,
  ExclamationCircleIcon as ExclamationCircleSolid,
} from '@heroicons/react/24/solid';
import { Label } from '@/components/common/Label';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Tooltip } from '@/components/common/Tooltip';
import { Popover } from '@/components/common/Popover';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type TimeFormat = '12h' | '24h';
export type TimeVariant = 'default' | 'compact' | 'minimal' | 'rounded' | 'outlined';
export type TimeSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
export type TimeStatus = 'default' | 'success' | 'error' | 'warning' | 'info';
export type TimeStep = 1 | 5 | 10 | 15 | 30;

export interface TimeFieldProps {
  // --- Contrôle ---
  /** Valeur du champ (format HH:mm ou HH:mm:ss) */
  value?: string | null;
  /** Valeur par défaut */
  defaultValue?: string | null;
  /** Callback de changement */
  onChange?: (value: string | null) => void;
  /** Callback de blur */
  onBlur?: () => void;
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
  variant?: TimeVariant;
  /** Taille du champ */
  size?: TimeSize;
  /** Statut du champ */
  status?: TimeStatus;
  /** Format de l'heure */
  format?: TimeFormat;
  /** Afficher le sélecteur visuel */
  showPicker?: boolean;
  /** Afficher les secondes */
  showSeconds?: boolean;
  /** Afficher l'icône de validation */
  showValidationIcon?: boolean;
  /** Afficher le bouton "Maintenant" */
  showNowButton?: boolean;
  /** Afficher le bouton d'effacement */
  showClearButton?: boolean;

  // --- Comportement ---
  /** Pas d'incrémentation (minutes) */
  step?: TimeStep;
  /** Heure minimale (HH:mm) */
  minTime?: string;
  /** Heure maximale (HH:mm) */
  maxTime?: string;
  /** Désactiver le champ */
  disabled?: boolean;
  /** Rendre le champ obligatoire */
  required?: boolean;
  /** Désactiver la validation en temps réel */
  disableRealtimeValidation?: boolean;
  /** Validation personnalisée */
  validateTime?: (value: string | null) => boolean | string;

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

const SIZE_MAP: Record<TimeSize, string> = {
  xs: 'h-7 text-xs px-2',
  sm: 'h-8 text-sm px-3',
  md: 'h-10 text-sm px-4',
  lg: 'h-12 text-base px-5',
  xl: 'h-14 text-lg px-6',
};

const VARIANT_MAP: Record<TimeVariant, string> = {
  default: 'bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600',
  compact: 'bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600',
  minimal: 'bg-transparent border-b-2 border-gray-300 dark:border-gray-600 rounded-none',
  rounded: 'bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-full',
  outlined: 'bg-transparent border-2 border-gray-300 dark:border-gray-600',
};

const STATUS_MAP: Record<TimeStatus, { border: string; ring: string; text: string }> = {
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

export const TimeField = forwardRef<HTMLDivElement, TimeFieldProps>(
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
      placeholder = 'HH:mm',
      description,
      error,
      success,
      info,
      variant = 'default',
      size = 'md',
      status = 'default',
      format = '24h',
      showPicker = true,
      showSeconds = false,
      showValidationIcon = true,
      showNowButton = true,
      showClearButton = true,

      // Comportement
      step = 5,
      minTime,
      maxTime,
      disabled = false,
      required = false,
      disableRealtimeValidation = false,
      validateTime: customValidate,

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
    const [isPickerOpen, setIsPickerOpen] = useState(false);
    const [selectedHour, setSelectedHour] = useState<number>(0);
    const [selectedMinute, setSelectedMinute] = useState<number>(0);
    const [selectedSecond, setSelectedSecond] = useState<number>(0);
    const [selectedPeriod, setSelectedPeriod] = useState<'AM' | 'PM'>('AM');

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined ? externalValue : internalValue;
    const isControlled = externalValue !== undefined;
    const hasValue = value && value.length > 0;

    const sizeStyles = SIZE_MAP[size] || SIZE_MAP.md;
    const variantStyles = VARIANT_MAP[variant] || VARIANT_MAP.default;
    const statusStyles = STATUS_MAP[status] || STATUS_MAP.default;
    const is24h = format === '24h';
    const hourFormat = is24h ? 'HH' : 'hh';
    const timePattern = is24h 
      ? (showSeconds ? /^([01]?[0-9]|2[0-3]):([0-5][0-9]):([0-5][0-9])$/ : /^([01]?[0-9]|2[0-3]):([0-5][0-9])$/)
      : (showSeconds ? /^(0?[1-9]|1[0-2]):([0-5][0-9]):([0-5][0-9])\s?(AM|PM)$/i : /^(0?[1-9]|1[0-2]):([0-5][0-9])\s?(AM|PM)$/i);

    // ========================================================================
    // FORMATAGE
    // ========================================================================

    const formatTime = useCallback((time: string | null): string => {
      if (customFormat) {
        return customFormat(time);
      }

      if (!time) return '';

      const parts = time.split(':');
      let hours = parseInt(parts[0]);
      const minutes = parts[1] || '00';
      const seconds = parts[2] || '00';

      if (is24h) {
        return `${hours.toString().padStart(2, '0')}:${minutes}${showSeconds ? `:${seconds}` : ''}`;
      } else {
        const period = hours >= 12 ? 'PM' : 'AM';
        const displayHours = hours % 12 || 12;
        return `${displayHours}:${minutes}${showSeconds ? `:${seconds}` : ''} ${period}`;
      }
    }, [customFormat, is24h, showSeconds]);

    const parseTime = useCallback((time: string): string | null => {
      if (customParse) {
        return customParse(time);
      }

      if (!time) return null;

      let clean = time.trim().toUpperCase();

      // Gérer le format 12h
      if (!is24h) {
        const match = clean.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?\s?(AM|PM)?$/);
        if (match) {
          let hours = parseInt(match[1]);
          const minutes = match[2];
          const seconds = match[3] || '00';
          const period = match[4] || (hours >= 12 ? 'PM' : 'AM');

          if (period === 'PM' && hours !== 12) hours += 12;
          if (period === 'AM' && hours === 12) hours = 0;

          return `${hours.toString().padStart(2, '0')}:${minutes}${showSeconds ? `:${seconds}` : ''}`;
        }
        return null;
      }

      // Format 24h
      const match = clean.match(/^(\d{1,2}):(\d{2})(?::(\d{2}))?$/);
      if (match) {
        const hours = parseInt(match[1]);
        const minutes = match[2];
        const seconds = match[3] || '00';
        if (hours < 0 || hours > 23 || parseInt(minutes) > 59 || (showSeconds && parseInt(seconds) > 59)) {
          return null;
        }
        return `${hours.toString().padStart(2, '0')}:${minutes}${showSeconds ? `:${seconds}` : ''}`;
      }

      return null;
    }, [customParse, is24h, showSeconds]);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validateTimeValue = useCallback((time: string | null): { valid: boolean; message: string } => {
      if (customValidate) {
        const result = customValidate(time);
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        return { valid: true, message: '' };
      }

      if (!time) {
        if (required) {
          return { valid: false, message: 'L\'heure est requise' };
        }
        return { valid: true, message: '' };
      }

      const parsed = parseTime(time);
      if (!parsed) {
        return { valid: false, message: 'Format d\'heure invalide' };
      }

      // Vérifier les limites
      if (minTime) {
        const minParsed = parseTime(minTime);
        if (minParsed && parsed < minParsed) {
          return { valid: false, message: `L'heure minimale est ${formatTime(minTime)}` };
        }
      }

      if (maxTime) {
        const maxParsed = parseTime(maxTime);
        if (maxParsed && parsed > maxParsed) {
          return { valid: false, message: `L'heure maximale est ${formatTime(maxTime)}` };
        }
      }

      return { valid: true, message: '' };
    }, [customValidate, required, parseTime, minTime, maxTime, formatTime]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateValue = useCallback((time: string | null) => {
      const parsed = time ? parseTime(time) : null;
      const validation = validateTimeValue(parsed);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);

      if (!disableRealtimeValidation && onValidate) {
        onValidate(validation.valid, parsed);
      }

      const formatted = parsed ? formatTime(parsed) : '';

      if (isControlled) {
        if (onChange) onChange(parsed);
      } else {
        setInternalValue(parsed);
        if (onChange) onChange(parsed);
      }

      setDisplayValue(formatted);

      // Mettre à jour l'état du picker
      if (parsed) {
        const parts = parsed.split(':');
        setSelectedHour(parseInt(parts[0]));
        setSelectedMinute(parseInt(parts[1]));
        if (showSeconds && parts[2]) {
          setSelectedSecond(parseInt(parts[2]));
        }
        if (!is24h) {
          setSelectedPeriod(parseInt(parts[0]) >= 12 ? 'PM' : 'AM');
        }
      }

      if (debug) {
        console.log('TimeField update:', { time: parsed, isValid: validation.valid });
      }
    }, [
      parseTime,
      validateTimeValue,
      isControlled,
      onChange,
      onValidate,
      disableRealtimeValidation,
      formatTime,
      is24h,
      showSeconds,
      debug,
    ]);

    // ========================================================================
    // GESTIONNAIRES D'ÉVÉNEMENTS
    // ========================================================================

    const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
      const rawValue = e.target.value;
      setDisplayValue(rawValue);

      if (!disableRealtimeValidation) {
        const parsed = parseTime(rawValue);
        const validation = validateTimeValue(parsed);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        if (onValidate) onValidate(validation.valid, parsed);
      }
    }, [disableRealtimeValidation, parseTime, validateTimeValue, onValidate]);

    const handleFocus = useCallback(() => {
      setIsFocused(true);
      if (onFocus) onFocus();
    }, [onFocus]);

    const handleBlur = useCallback(() => {
      setIsFocused(false);

      const parsed = parseTime(displayValue);
      const validation = validateTimeValue(parsed);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);
      if (onValidate) onValidate(validation.valid, parsed);

      if (parsed) {
        updateValue(parsed);
      } else if (!displayValue) {
        updateValue(null);
      } else {
        setDisplayValue(formatTime(value));
      }

      if (onBlur) onBlur();
    }, [
      displayValue,
      parseTime,
      validateTimeValue,
      onValidate,
      updateValue,
      formatTime,
      value,
      onBlur,
    ]);

    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const parsed = parseTime(displayValue);
        if (parsed) {
          updateValue(parsed);
        }
        inputRefInternal.current?.blur();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        setDisplayValue(formatTime(value));
        inputRefInternal.current?.blur();
      }
    }, [displayValue, parseTime, updateValue, formatTime, value]);

    // ========================================================================
    // PICKER
    // ========================================================================

    const incrementHour = useCallback(() => {
      const maxHour = is24h ? 23 : 12;
      const newHour = selectedHour >= maxHour ? 0 : selectedHour + 1;
      setSelectedHour(newHour);
      updatePickerValue(newHour, selectedMinute, selectedSecond);
    }, [selectedHour, selectedMinute, selectedSecond, is24h]);

    const decrementHour = useCallback(() => {
      const maxHour = is24h ? 23 : 12;
      const newHour = selectedHour <= 0 ? maxHour : selectedHour - 1;
      setSelectedHour(newHour);
      updatePickerValue(newHour, selectedMinute, selectedSecond);
    }, [selectedHour, selectedMinute, selectedSecond, is24h]);

    const incrementMinute = useCallback(() => {
      const newMinute = selectedMinute >= 59 ? 0 : selectedMinute + step;
      setSelectedMinute(newMinute);
      updatePickerValue(selectedHour, newMinute, selectedSecond);
    }, [selectedHour, selectedMinute, selectedSecond, step]);

    const decrementMinute = useCallback(() => {
      const newMinute = selectedMinute <= 0 ? 59 : selectedMinute - step;
      setSelectedMinute(newMinute);
      updatePickerValue(selectedHour, newMinute, selectedSecond);
    }, [selectedHour, selectedMinute, selectedSecond, step]);

    const incrementSecond = useCallback(() => {
      if (!showSeconds) return;
      const newSecond = selectedSecond >= 59 ? 0 : selectedSecond + 1;
      setSelectedSecond(newSecond);
      updatePickerValue(selectedHour, selectedMinute, newSecond);
    }, [selectedHour, selectedMinute, selectedSecond, showSeconds]);

    const decrementSecond = useCallback(() => {
      if (!showSeconds) return;
      const newSecond = selectedSecond <= 0 ? 59 : selectedSecond - 1;
      setSelectedSecond(newSecond);
      updatePickerValue(selectedHour, selectedMinute, newSecond);
    }, [selectedHour, selectedMinute, selectedSecond, showSeconds]);

    const togglePeriod = useCallback(() => {
      const newPeriod = selectedPeriod === 'AM' ? 'PM' : 'AM';
      setSelectedPeriod(newPeriod);
      const hour = newPeriod === 'PM' ? selectedHour + 12 : selectedHour;
      updatePickerValue(hour, selectedMinute, selectedSecond);
    }, [selectedPeriod, selectedHour, selectedMinute, selectedSecond]);

    const updatePickerValue = useCallback((hour: number, minute: number, second: number) => {
      const timeStr = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}${showSeconds ? `:${second.toString().padStart(2, '0')}` : ''}`;
      updateValue(timeStr);
    }, [showSeconds, updateValue]);

    const handleNow = useCallback(() => {
      const now = new Date();
      const hours = now.getHours();
      const minutes = now.getMinutes();
      const seconds = now.getSeconds();
      const timeStr = `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}${showSeconds ? `:${seconds.toString().padStart(2, '0')}` : ''}`;
      setSelectedHour(hours);
      setSelectedMinute(minutes);
      setSelectedSecond(seconds);
      if (!is24h) {
        setSelectedPeriod(hours >= 12 ? 'PM' : 'AM');
      }
      updateValue(timeStr);
      setIsPickerOpen(false);
    }, [is24h, showSeconds, updateValue]);

    const handleClear = useCallback(() => {
      updateValue(null);
      setDisplayValue('');
      setIsPickerOpen(false);
    }, [updateValue]);

    // ========================================================================
    // SYNC AVEC LA VALEUR EXTERNE
    // ========================================================================

    useEffect(() => {
      if (externalValue !== undefined && externalValue !== prevValueRef.current) {
        prevValueRef.current = externalValue;
        const formatted = formatTime(externalValue);
        setDisplayValue(formatted);
        const validation = validateTimeValue(externalValue);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        
        if (externalValue) {
          const parts = externalValue.split(':');
          setSelectedHour(parseInt(parts[0]));
          setSelectedMinute(parseInt(parts[1]));
          if (showSeconds && parts[2]) {
            setSelectedSecond(parseInt(parts[2]));
          }
          if (!is24h) {
            setSelectedPeriod(parseInt(parts[0]) >= 12 ? 'PM' : 'AM');
          }
        }
      }
    }, [externalValue, formatTime, validateTimeValue, is24h, showSeconds]);

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
      focus: () => inputRefInternal.current?.focus(),
      blur: () => inputRefInternal.current?.blur(),
      select: () => inputRefInternal.current?.select(),
      getValue: () => value,
      setValue: (val: string | null) => updateValue(val),
      clear: () => handleClear(),
      validate: () => {
        const validation = validateTimeValue(value);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        return validation.valid;
      },
    } as any));

    // ========================================================================
    // RENDU DU PICKER
    // ========================================================================

    const renderPicker = () => {
      if (!showPicker) return null;

      const hourDisplay = is24h ? selectedHour : (selectedHour % 12 || 12);

      return (
        <div className="p-4 min-w-[200px]">
          <div className="flex items-center justify-center gap-4">
            {/* Heures */}
            <div className="flex flex-col items-center">
              <button
                type="button"
                onClick={incrementHour}
                className="rounded p-1 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                disabled={disabled}
              >
                <ChevronUpIcon className="h-4 w-4" />
              </button>
              <span className="text-2xl font-mono font-medium w-12 text-center">
                {hourDisplay.toString().padStart(2, '0')}
              </span>
              <button
                type="button"
                onClick={decrementHour}
                className="rounded p-1 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                disabled={disabled}
              >
                <ChevronDownIcon className="h-4 w-4" />
              </button>
            </div>

            <span className="text-2xl font-mono font-medium">:</span>

            {/* Minutes */}
            <div className="flex flex-col items-center">
              <button
                type="button"
                onClick={incrementMinute}
                className="rounded p-1 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                disabled={disabled}
              >
                <ChevronUpIcon className="h-4 w-4" />
              </button>
              <span className="text-2xl font-mono font-medium w-12 text-center">
                {selectedMinute.toString().padStart(2, '0')}
              </span>
              <button
                type="button"
                onClick={decrementMinute}
                className="rounded p-1 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                disabled={disabled}
              >
                <ChevronDownIcon className="h-4 w-4" />
              </button>
            </div>

            {/* Secondes */}
            {showSeconds && (
              <>
                <span className="text-2xl font-mono font-medium">:</span>
                <div className="flex flex-col items-center">
                  <button
                    type="button"
                    onClick={incrementSecond}
                    className="rounded p-1 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                    disabled={disabled}
                  >
                    <ChevronUpIcon className="h-4 w-4" />
                  </button>
                  <span className="text-2xl font-mono font-medium w-12 text-center">
                    {selectedSecond.toString().padStart(2, '0')}
                  </span>
                  <button
                    type="button"
                    onClick={decrementSecond}
                    className="rounded p-1 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                    disabled={disabled}
                  >
                    <ChevronDownIcon className="h-4 w-4" />
                  </button>
                </div>
              </>
            )}

            {/* AM/PM */}
            {!is24h && (
              <div className="flex flex-col gap-1 ml-2">
                <button
                  type="button"
                  className={cn(
                    'rounded px-2 py-1 text-sm font-medium transition-colors',
                    selectedPeriod === 'AM'
                      ? 'bg-brand-500 text-white'
                      : 'bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700'
                  )}
                  onClick={() => {
                    if (selectedPeriod === 'PM') togglePeriod();
                  }}
                  disabled={disabled}
                >
                  AM
                </button>
                <button
                  type="button"
                  className={cn(
                    'rounded px-2 py-1 text-sm font-medium transition-colors',
                    selectedPeriod === 'PM'
                      ? 'bg-brand-500 text-white'
                      : 'bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700'
                  )}
                  onClick={() => {
                    if (selectedPeriod === 'AM') togglePeriod();
                  }}
                  disabled={disabled}
                >
                  PM
                </button>
              </div>
            )}
          </div>

          {/* Boutons d'action */}
          <div className="mt-4 flex gap-2">
            {showNowButton && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="flex-1"
                onClick={handleNow}
                disabled={disabled}
              >
                Maintenant
              </Button>
            )}
            {showClearButton && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="flex-1"
                onClick={handleClear}
                disabled={disabled}
              >
                Effacer
              </Button>
            )}
          </div>
        </div>
      );
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const hasError = !!error || !isValid || (required && !value);
    const isSuccess = !hasError && success && value;

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
            {value && (
              <Badge variant="outline" size="xs">
                {format === '12h' ? '12h' : '24h'}
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
          <div className={cn(
            'relative flex items-center rounded-lg border transition-all',
            hasError 
              ? 'border-red-500 ring-2 ring-red-500/20 dark:border-red-400' 
              : isSuccess && !disabled
              ? 'border-green-500 ring-2 ring-green-500/20 dark:border-green-400'
              : isFocused
              ? `border-${statusStyles.ring} ring-2 ring-${statusStyles.ring}/20 dark:border-${statusStyles.ring}`
              : statusStyles.border,
            disabled && 'opacity-50 cursor-not-allowed bg-gray-50 dark:bg-gray-800/50',
            variantStyles,
            sizeStyles
          )}>
            <ClockIcon className="absolute left-3 h-4 w-4 text-gray-400" />

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
                'w-full bg-transparent pl-9 pr-10 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 outline-none',
                disabled && 'cursor-not-allowed',
                variant === 'rounded' && 'rounded-full'
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

            {/* Boutons */}
            <div className="absolute right-2 flex items-center gap-0.5">
              {showPicker && !disabled && (
                <Popover
                  open={isPickerOpen}
                  onOpenChange={setIsPickerOpen}
                  trigger={
                    <button
                      type="button"
                      className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                      onClick={() => setIsPickerOpen(!isPickerOpen)}
                    >
                      <ClockIcon className="h-4 w-4" />
                    </button>
                  }
                  placement="bottom-end"
                  className="z-50"
                >
                  {renderPicker()}
                </Popover>
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
      </div>
    );
  }
);

TimeField.displayName = 'TimeField';

// ============================================================================
// EXPORTS
// ============================================================================

export default TimeField;

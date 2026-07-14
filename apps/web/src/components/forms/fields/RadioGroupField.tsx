// apps/web/src/components/forms/fields/RadioGroupField.tsx
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
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
  CheckIcon,
  ExclamationCircleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
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

export type RadioOption = {
  /** Valeur de l'option */
  value: string;
  /** Libellé de l'option */
  label: string;
  /** Description de l'option */
  description?: string;
  /** Icône de l'option */
  icon?: React.ReactNode;
  /** Désactiver l'option */
  disabled?: boolean;
  /** Classes additionnelles */
  className?: string;
};

export type RadioVariant = 'default' | 'card' | 'pill' | 'button' | 'minimal' | 'outlined';
export type RadioSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
export type RadioColor = 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'brand' | 'neutral';
export type RadioDirection = 'horizontal' | 'vertical';
export type RadioAlignment = 'start' | 'center' | 'end' | 'stretch';

export interface RadioGroupFieldProps {
  // --- Contrôle ---
  /** Valeur sélectionnée */
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

  // --- Options ---
  /** Options du radio group */
  options: RadioOption[];
  /** Nom du groupe (pour l'accessibilité) */
  name?: string;

  // --- Apparence ---
  /** Libellé du champ */
  label?: string;
  /** Description du champ */
  description?: string;
  /** Message d'erreur */
  error?: string;
  /** Message de succès */
  success?: string;
  /** Message d'information */
  info?: string;
  /** Variante d'affichage */
  variant?: RadioVariant;
  /** Taille des radios */
  size?: RadioSize;
  /** Couleur du thème */
  color?: RadioColor;
  /** Direction du groupe */
  direction?: RadioDirection;
  /** Alignement des options */
  alignment?: RadioAlignment;
  /** Afficher les descriptions */
  showDescriptions?: boolean;
  /** Afficher les icônes */
  showIcons?: boolean;
  /** Afficher l'icône de validation */
  showValidationIcon?: boolean;
  /** Afficher le nombre d'options sélectionnées */
  showCount?: boolean;

  // --- Comportement ---
  /** Désactiver tout le groupe */
  disabled?: boolean;
  /** Rendre le groupe obligatoire */
  required?: boolean;
  /** Permettre la désélection */
  allowDeselect?: boolean;
  /** Désactiver l'animation */
  disableAnimation?: boolean;
  /** Désactiver la validation en temps réel */
  disableRealtimeValidation?: boolean;

  // --- Layout ---
  /** Espacement entre les options */
  gap?: string | number;
  /** Padding des options */
  padding?: string | number;
  /** Nombre de colonnes (pour horizontal) */
  columns?: number;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ARIA describedby */
  ariaDescribedby?: string;
  /** ID */
  id?: string;

  // --- Avancé ---
  /** Fonction de validation personnalisée */
  customValidate?: (value: string | null) => boolean | string;
  /** Ref */
  inputRef?: React.Ref<HTMLInputElement>;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const SIZE_MAP: Record<RadioSize, { radio: string; label: string; padding: string; gap: string }> = {
  xs: {
    radio: 'h-3 w-3',
    label: 'text-xs',
    padding: 'px-2 py-1',
    gap: 'gap-1.5',
  },
  sm: {
    radio: 'h-4 w-4',
    label: 'text-sm',
    padding: 'px-3 py-1.5',
    gap: 'gap-2',
  },
  md: {
    radio: 'h-5 w-5',
    label: 'text-sm',
    padding: 'px-4 py-2',
    gap: 'gap-2.5',
  },
  lg: {
    radio: 'h-6 w-6',
    label: 'text-base',
    padding: 'px-5 py-2.5',
    gap: 'gap-3',
  },
  xl: {
    radio: 'h-7 w-7',
    label: 'text-lg',
    padding: 'px-6 py-3',
    gap: 'gap-3.5',
  },
};

const COLOR_MAP: Record<RadioColor, { ring: string; bg: string; border: string; text: string }> = {
  primary: {
    ring: 'ring-brand-500 dark:ring-brand-400',
    bg: 'bg-brand-500 dark:bg-brand-400',
    border: 'border-brand-500 dark:border-brand-400',
    text: 'text-brand-700 dark:text-brand-400',
  },
  success: {
    ring: 'ring-green-500 dark:ring-green-400',
    bg: 'bg-green-500 dark:bg-green-400',
    border: 'border-green-500 dark:border-green-400',
    text: 'text-green-700 dark:text-green-400',
  },
  warning: {
    ring: 'ring-yellow-500 dark:ring-yellow-400',
    bg: 'bg-yellow-500 dark:bg-yellow-400',
    border: 'border-yellow-500 dark:border-yellow-400',
    text: 'text-yellow-700 dark:text-yellow-400',
  },
  danger: {
    ring: 'ring-red-500 dark:ring-red-400',
    bg: 'bg-red-500 dark:bg-red-400',
    border: 'border-red-500 dark:border-red-400',
    text: 'text-red-700 dark:text-red-400',
  },
  info: {
    ring: 'ring-blue-500 dark:ring-blue-400',
    bg: 'bg-blue-500 dark:bg-blue-400',
    border: 'border-blue-500 dark:border-blue-400',
    text: 'text-blue-700 dark:text-blue-400',
  },
  brand: {
    ring: 'ring-brand-500 dark:ring-brand-400',
    bg: 'bg-brand-500 dark:bg-brand-400',
    border: 'border-brand-500 dark:border-brand-400',
    text: 'text-brand-700 dark:text-brand-400',
  },
  neutral: {
    ring: 'ring-gray-500 dark:ring-gray-400',
    bg: 'bg-gray-500 dark:bg-gray-400',
    border: 'border-gray-500 dark:border-gray-400',
    text: 'text-gray-700 dark:text-gray-400',
  },
};

const VARIANT_STYLES: Record<RadioVariant, string> = {
  default: '',
  card: 'rounded-xl border-2 p-4 shadow-sm hover:shadow-md transition-shadow',
  pill: 'rounded-full',
  button: 'rounded-lg font-medium transition-colors',
  minimal: 'border-b-2 rounded-none',
  outlined: 'border-2 rounded-lg',
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const RadioGroupField = forwardRef<HTMLDivElement, RadioGroupFieldProps>(
  (props, ref) => {
    const {
      // Contrôle
      value: externalValue,
      defaultValue,
      onChange,
      onBlur,
      onFocus,
      onValidate,

      // Options
      options,
      name: externalName,

      // Apparence
      label,
      description,
      error,
      success,
      info,
      variant = 'default',
      size = 'md',
      color = 'brand',
      direction = 'vertical',
      alignment = 'start',
      showDescriptions = true,
      showIcons = true,
      showValidationIcon = true,
      showCount = true,

      // Comportement
      disabled = false,
      required = false,
      allowDeselect = false,
      disableAnimation = false,
      disableRealtimeValidation = false,

      // Layout
      gap = 4,
      padding = 12,
      columns,

      // Accessibilité
      ariaLabel,
      ariaDescribedby,
      id,

      // Avancé
      customValidate,
      inputRef,
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const containerRef = useRef<HTMLDivElement>(null);
    const uniqueId = React.useId();
    const groupId = id || `nexus-radio-group-${uniqueId}`;
    const name = externalName || groupId;

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
    const [isFocused, setIsFocused] = useState(false);
    const [isValid, setIsValid] = useState(true);
    const [validationMessage, setValidationMessage] = useState<string>('');
    const [isHovered, setIsHovered] = useState(false);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined ? externalValue : internalValue;
    const isControlled = externalValue !== undefined;
    const selectedOption = options.find((opt) => opt.value === value);
    const sizeStyles = SIZE_MAP[size] || SIZE_MAP.md;
    const colorStyles = COLOR_MAP[color] || COLOR_MAP.brand;

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

      if (!val) {
        if (required) {
          return { valid: false, message: 'Veuillez sélectionner une option' };
        }
        return { valid: true, message: '' };
      }

      const optionExists = options.some((opt) => opt.value === val);
      if (!optionExists) {
        return { valid: false, message: 'Option invalide' };
      }

      return { valid: true, message: '' };
    }, [customValidate, required, options]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateValue = useCallback((val: string | null) => {
      let finalValue = val;

      // Permettre la désélection
      if (allowDeselect && value === val) {
        finalValue = null;
      }

      const validation = validateValue(finalValue);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);

      if (!disableRealtimeValidation && onValidate) {
        onValidate(validation.valid, finalValue);
      }

      if (isControlled) {
        if (onChange) onChange(finalValue);
      } else {
        setInternalValue(finalValue);
        if (onChange) onChange(finalValue);
      }

      if (debug) {
        console.log('RadioGroupField update:', { value: finalValue, isValid: validation.valid });
      }
    }, [
      allowDeselect,
      value,
      validateValue,
      isControlled,
      onChange,
      onValidate,
      disableRealtimeValidation,
      debug,
    ]);

    // ========================================================================
    // GESTIONNAIRES D'ÉVÉNEMENTS
    // ========================================================================

    const handleSelect = useCallback((optionValue: string) => {
      if (disabled) return;
      updateValue(optionValue);
    }, [disabled, updateValue]);

    const handleFocus = useCallback(() => {
      setIsFocused(true);
      if (onFocus) onFocus();
    }, [onFocus]);

    const handleBlur = useCallback(() => {
      setIsFocused(false);
      if (onBlur) onBlur();
    }, [onBlur]);

    // ========================================================================
    // SYNC AVEC LA VALEUR EXTERNE
    // ========================================================================

    useEffect(() => {
      if (externalValue !== undefined) {
        const validation = validateValue(externalValue);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
      }
    }, [externalValue, validateValue]);

    // ========================================================================
    // IMPERATIVE HANDLE
    // ========================================================================

    useImperativeHandle(ref, () => ({
      focus: () => containerRef.current?.focus(),
      blur: () => containerRef.current?.blur(),
      getValue: () => value,
      setValue: (val: string | null) => updateValue(val),
      validate: () => {
        const validation = validateValue(value);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        return validation.valid;
      },
    } as any));

    // ========================================================================
    // RENDU D'UNE OPTION
    // ========================================================================

    const renderOption = (option: RadioOption, index: number) => {
      const isSelected = option.value === value;
      const isDisabled = option.disabled || disabled;

      const isCard = variant === 'card';
      const isPill = variant === 'pill';
      const isButton = variant === 'button';
      const isMinimal = variant === 'minimal';
      const isOutlined = variant === 'outlined';

      return (
        <motion.label
          key={option.value}
          initial={!disableAnimation ? { opacity: 0, y: -10 } : {}}
          animate={!disableAnimation ? { opacity: 1, y: 0 } : {}}
          transition={{ delay: index * 0.05 }}
          className={cn(
            'relative flex cursor-pointer items-center transition-all',
            isDisabled && 'opacity-50 cursor-not-allowed',
            isCard && 'w-full',
            isPill && 'rounded-full',
            isButton && 'justify-center',
            isMinimal && 'border-b-2',
            isOutlined && 'border-2',
            alignment === 'center' && 'justify-center',
            alignment === 'end' && 'justify-end',
            alignment === 'stretch' && 'w-full',
            sizeStyles.padding,
            sizeStyles.gap,
            isCard && isSelected && `border-${color} bg-${color}-50 dark:bg-${color}-900/20`,
            isCard && !isSelected && 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600',
            isCard && 'rounded-xl border-2 shadow-sm hover:shadow-md transition-shadow',
            isPill && isSelected && `bg-${color}-100 dark:bg-${color}-900/30 text-${color}-700 dark:text-${color}-400`,
            isPill && !isSelected && 'hover:bg-gray-100 dark:hover:bg-gray-800',
            isButton && isSelected && `${colorStyles.bg} text-white shadow-md`,
            isButton && !isSelected && 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700',
            isMinimal && isSelected && `border-${color}-500 text-${color}-700 dark:text-${color}-400`,
            isMinimal && !isSelected && 'border-transparent hover:border-gray-300 dark:hover:border-gray-600',
            isOutlined && isSelected && `border-${color}-500 bg-${color}-50 dark:bg-${color}-900/20`,
            isOutlined && !isSelected && 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600',
            option.className
          )}
          onMouseEnter={() => setIsHovered(true)}
          onMouseLeave={() => setIsHovered(false)}
        >
          <input
            type="radio"
            name={name}
            value={option.value}
            checked={isSelected}
            onChange={() => handleSelect(option.value)}
            onFocus={handleFocus}
            onBlur={handleBlur}
            disabled={isDisabled}
            className="sr-only"
          />

          {/* Radio circle */}
          {!isButton && !isCard && (
            <div
              className={cn(
                'flex-shrink-0 rounded-full border-2 transition-all',
                sizeStyles.radio,
                isSelected ? `${colorStyles.border} ${colorStyles.bg}` : 'border-gray-300 dark:border-gray-600',
                isDisabled && 'border-gray-300 dark:border-gray-700'
              )}
            >
              <div
                className={cn(
                  'h-full w-full rounded-full transition-transform',
                  isSelected ? 'scale-100' : 'scale-0',
                  'bg-white dark:bg-gray-900'
                )}
              />
            </div>
          )}

          {/* Contenu */}
          <div className="flex-1 min-w-0">
            <div className={cn(
              'flex items-center gap-2',
              isButton && 'justify-center'
            )}>
              {showIcons && option.icon && (
                <span className="flex-shrink-0 text-gray-400">
                  {option.icon}
                </span>
              )}
              <span className={cn(
                'font-medium',
                isSelected && !isButton && !isPill && colorStyles.text,
                isButton && 'text-white',
                sizeStyles.label
              )}>
                {option.label}
              </span>
              {isSelected && !isButton && (
                <CheckIcon className={cn('h-4 w-4 text-brand-500', isPill && 'text-brand-700 dark:text-brand-400')} />
              )}
            </div>
            {showDescriptions && option.description && (
              <p className={cn(
                'text-gray-500 dark:text-gray-400',
                isButton && 'text-gray-300',
                sizeStyles.label,
                'mt-0.5'
              )}>
                {option.description}
              </p>
            )}
          </div>
        </motion.label>
      );
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const hasError = !!error || !isValid || (required && !value);
    const isSuccess = !hasError && success && value;

    const gridCols = columns && columns > 1 ? `grid-cols-${Math.min(columns, 4)}` : '';

    return (
      <div
        ref={containerRef}
        id={groupId}
        className="relative space-y-1.5"
        role="radiogroup"
        aria-label={ariaLabel || label}
        aria-describedby={ariaDescribedby}
        aria-required={required}
        aria-disabled={disabled}
        aria-invalid={!isValid}
      >
        {/* Label */}
        {label && (
          <div className="flex items-center justify-between">
            <Label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {label}
              {required && <span className="ml-1 text-red-500">*</span>}
            </Label>
            {showCount && options.length > 0 && (
              <Badge variant="outline" size="sm">
                {value ? '1 sélectionné' : 'Aucune sélection'}
              </Badge>
            )}
          </div>
        )}

        {/* Description */}
        {description && (
          <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
        )}

        {/* Options */}
        <div
          className={cn(
            'flex',
            direction === 'horizontal' ? 'flex-wrap items-center' : 'flex-col',
            direction === 'horizontal' && `gap-${gap}`,
            direction === 'vertical' && `gap-${gap}`,
            columns && columns > 1 && `grid ${gridCols}`,
            variant === 'card' && 'grid grid-cols-1 sm:grid-cols-2 gap-3'
          )}
          style={{
            gap: typeof gap === 'number' ? `${gap}px` : gap,
          }}
        >
          {options.map((option, index) => renderOption(option, index))}
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

RadioGroupField.displayName = 'RadioGroupField';

// ============================================================================
// EXPORTS
// ============================================================================

export default RadioGroupField;

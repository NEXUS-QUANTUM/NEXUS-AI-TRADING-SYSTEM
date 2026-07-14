// apps/web/src/components/forms/fields/ToggleField.tsx
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
  CheckIcon,
  XMarkIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ExclamationCircleIcon,
  SunIcon,
  MoonIcon,
  BellIcon,
  BellSlashIcon,
  EyeIcon,
  EyeSlashIcon,
  LockClosedIcon,
  LockOpenIcon,
  WifiIcon,
  WifiSlashIcon,
  BluetoothIcon,
  BluetoothSlashIcon,
  VolumeUpIcon,
  VolumeOffIcon,
  MicrophoneIcon,
  MicrophoneSlashIcon,
  CameraIcon,
  CameraSlashIcon,
  HeartIcon,
  HeartSlashIcon,
  StarIcon,
  StarSlashIcon,
  FlagIcon,
  FlagSlashIcon,
  UserIcon,
  UserSlashIcon,
  KeyIcon,
  KeySlashIcon,
} from '@heroicons/react/24/outline';
import {
  CheckIcon as CheckSolid,
  XMarkIcon as XMarkSolid,
} from '@heroicons/react/24/solid';
import { Label } from '@/components/common/Label';
import { Badge } from '@/components/common/Badge';
import { Tooltip } from '@/components/common/Tooltip';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type ToggleVariant = 'default' | 'success' | 'danger' | 'warning' | 'info' | 'brand' | 'dark' | 'light';
export type ToggleSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
export type ToggleLabelPosition = 'left' | 'right' | 'top' | 'bottom' | 'none';
export type ToggleAnimation = 'slide' | 'fade' | 'scale' | 'bounce' | 'none';
export type ToggleVariantStyle = 'switch' | 'button' | 'pill' | 'square' | 'rounded';

export interface ToggleFieldProps {
  // --- Contrôle ---
  /** Valeur du toggle */
  checked?: boolean;
  /** Valeur par défaut */
  defaultChecked?: boolean;
  /** Callback de changement */
  onChange?: (checked: boolean) => void;
  /** Callback de blur */
  onBlur?: () => void;
  /** Callback de focus */
  onFocus?: () => void;
  /** Callback de validation */
  onValidate?: (valid: boolean, checked: boolean) => void;

  // --- Apparence ---
  /** Libellé du toggle */
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
  variant?: ToggleVariant;
  /** Taille du toggle */
  size?: ToggleSize;
  /** Position du label */
  labelPosition?: ToggleLabelPosition;
  /** Animation du toggle */
  animation?: ToggleAnimation;
  /** Style du toggle */
  style?: ToggleVariantStyle;
  /** Icône quand activé */
  checkedIcon?: React.ReactNode;
  /** Icône quand désactivé */
  uncheckedIcon?: React.ReactNode;
  /** Couleur de fond quand activé */
  checkedColor?: string;
  /** Couleur de fond quand désactivé */
  uncheckedColor?: string;
  /** Couleur du thumb */
  thumbColor?: string;

  // --- Comportement ---
  /** Désactiver le toggle */
  disabled?: boolean;
  /** Rendre le toggle obligatoire */
  required?: boolean;
  /** Désactiver la validation en temps réel */
  disableRealtimeValidation?: boolean;
  /** Validation personnalisée */
  validateToggle?: (checked: boolean) => boolean | string;

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
  /** Ref */
  inputRef?: React.Ref<HTMLInputElement>;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const SIZE_MAP: Record<ToggleSize, { toggle: string; thumb: string; label: string; gap: string }> = {
  xs: {
    toggle: 'h-4 w-7',
    thumb: 'h-2.5 w-2.5',
    label: 'text-xs',
    gap: 'gap-1.5',
  },
  sm: {
    toggle: 'h-5 w-9',
    thumb: 'h-3.5 w-3.5',
    label: 'text-sm',
    gap: 'gap-2',
  },
  md: {
    toggle: 'h-6 w-11',
    thumb: 'h-4.5 w-4.5',
    label: 'text-sm',
    gap: 'gap-2.5',
  },
  lg: {
    toggle: 'h-7 w-13',
    thumb: 'h-5.5 w-5.5',
    label: 'text-base',
    gap: 'gap-3',
  },
  xl: {
    toggle: 'h-8 w-15',
    thumb: 'h-6.5 w-6.5',
    label: 'text-lg',
    gap: 'gap-3.5',
  },
};

const VARIANT_MAP: Record<ToggleVariant, { checked: string; unchecked: string; thumb: string }> = {
  default: {
    checked: 'bg-brand-500',
    unchecked: 'bg-gray-300 dark:bg-gray-600',
    thumb: 'bg-white',
  },
  success: {
    checked: 'bg-green-500',
    unchecked: 'bg-gray-300 dark:bg-gray-600',
    thumb: 'bg-white',
  },
  danger: {
    checked: 'bg-red-500',
    unchecked: 'bg-gray-300 dark:bg-gray-600',
    thumb: 'bg-white',
  },
  warning: {
    checked: 'bg-yellow-500',
    unchecked: 'bg-gray-300 dark:bg-gray-600',
    thumb: 'bg-white',
  },
  info: {
    checked: 'bg-blue-500',
    unchecked: 'bg-gray-300 dark:bg-gray-600',
    thumb: 'bg-white',
  },
  brand: {
    checked: 'bg-brand-600',
    unchecked: 'bg-gray-300 dark:bg-gray-600',
    thumb: 'bg-white',
  },
  dark: {
    checked: 'bg-gray-800 dark:bg-gray-200',
    unchecked: 'bg-gray-300 dark:bg-gray-600',
    thumb: 'bg-white dark:bg-gray-900',
  },
  light: {
    checked: 'bg-gray-200 dark:bg-gray-700',
    unchecked: 'bg-gray-300 dark:bg-gray-600',
    thumb: 'bg-white dark:bg-gray-900',
  },
};

const STYLE_MAP: Record<ToggleVariantStyle, { toggle: string; thumb: string }> = {
  switch: {
    toggle: 'rounded-full',
    thumb: 'rounded-full',
  },
  button: {
    toggle: 'rounded-lg',
    thumb: 'rounded-lg',
  },
  pill: {
    toggle: 'rounded-full',
    thumb: 'rounded-full',
  },
  square: {
    toggle: 'rounded-none',
    thumb: 'rounded-none',
  },
  rounded: {
    toggle: 'rounded-xl',
    thumb: 'rounded-lg',
  },
};

const ICON_SIZE_MAP: Record<ToggleSize, string> = {
  xs: 'h-2 w-2',
  sm: 'h-2.5 w-2.5',
  md: 'h-3 w-3',
  lg: 'h-3.5 w-3.5',
  xl: 'h-4 w-4',
};

const ANIMATION_MAP: Record<ToggleAnimation, { duration: number; type: string }> = {
  slide: { duration: 0.2, type: 'spring' },
  fade: { duration: 0.3, type: 'tween' },
  scale: { duration: 0.3, type: 'spring' },
  bounce: { duration: 0.4, type: 'spring' },
  none: { duration: 0, type: 'tween' },
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const ToggleField = forwardRef<HTMLDivElement, ToggleFieldProps>(
  (props, ref) => {
    const {
      // Contrôle
      checked: externalChecked,
      defaultChecked = false,
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
      size = 'md',
      labelPosition = 'right',
      animation = 'slide',
      style = 'switch',
      checkedIcon,
      uncheckedIcon,
      checkedColor,
      uncheckedColor,
      thumbColor,

      // Comportement
      disabled = false,
      required = false,
      disableRealtimeValidation = false,
      validateToggle: customValidate,

      // Accessibilité
      ariaLabel,
      ariaDescribedby,
      id,
      name,

      // Avancé
      inputRef,
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const containerRef = useRef<HTMLDivElement>(null);
    const inputRefInternal = useRef<HTMLInputElement>(null);
    const prevCheckedRef = useRef<boolean>(false);

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalChecked, setInternalChecked] = useState<boolean>(defaultChecked);
    const [isFocused, setIsFocused] = useState(false);
    const [isValid, setIsValid] = useState(true);
    const [validationMessage, setValidationMessage] = useState<string>('');

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const checked = externalChecked !== undefined ? externalChecked : internalChecked;
    const isControlled = externalChecked !== undefined;
    const sizeStyles = SIZE_MAP[size] || SIZE_MAP.md;
    const variantStyles = VARIANT_MAP[variant] || VARIANT_MAP.default;
    const styleStyles = STYLE_MAP[style] || STYLE_MAP.switch;
    const iconSize = ICON_SIZE_MAP[size] || ICON_SIZE_MAP.md;
    const animationConfig = ANIMATION_MAP[animation] || ANIMATION_MAP.slide;

    const hasError = !!error || !isValid || (required && checked === undefined);
    const isSuccess = !hasError && success;

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validateToggle = useCallback((val: boolean): { valid: boolean; message: string } => {
      if (customValidate) {
        const result = customValidate(val);
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        return { valid: true, message: '' };
      }

      if (required && val === undefined) {
        return { valid: false, message: 'Ce champ est requis' };
      }

      return { valid: true, message: '' };
    }, [customValidate, required]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateChecked = useCallback((val: boolean) => {
      const validation = validateToggle(val);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);

      if (!disableRealtimeValidation && onValidate) {
        onValidate(validation.valid, val);
      }

      if (isControlled) {
        if (onChange) onChange(val);
      } else {
        setInternalChecked(val);
        if (onChange) onChange(val);
      }

      if (debug) {
        console.log('ToggleField update:', { checked: val, isValid: validation.valid });
      }
    }, [
      validateToggle,
      isControlled,
      onChange,
      onValidate,
      disableRealtimeValidation,
      debug,
    ]);

    // ========================================================================
    // GESTIONNAIRES D'ÉVÉNEMENTS
    // ========================================================================

    const handleToggle = useCallback(() => {
      if (disabled) return;
      updateChecked(!checked);
    }, [disabled, checked, updateChecked]);

    const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
      if (disabled) return;
      if (e.key === ' ' || e.key === 'Enter') {
        e.preventDefault();
        handleToggle();
      }
    }, [disabled, handleToggle]);

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
      if (externalChecked !== undefined && externalChecked !== prevCheckedRef.current) {
        prevCheckedRef.current = externalChecked;
        const validation = validateToggle(externalChecked);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
      }
    }, [externalChecked, validateToggle]);

    // ========================================================================
    // INITIALISATION
    // ========================================================================

    useEffect(() => {
      if (defaultChecked && !isControlled) {
        const validation = validateToggle(defaultChecked);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
      }
    }, [defaultChecked, isControlled, validateToggle]);

    // ========================================================================
    // IMPERATIVE HANDLE
    // ========================================================================

    useImperativeHandle(ref, () => ({
      focus: () => containerRef.current?.focus(),
      blur: () => containerRef.current?.blur(),
      getValue: () => checked,
      setValue: (val: boolean) => updateChecked(val),
      toggle: () => handleToggle(),
      validate: () => {
        const validation = validateToggle(checked);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        return validation.valid;
      },
    } as any));

    // ========================================================================
    // RENDU
    // ========================================================================

    const renderToggle = () => {
      const checkedBg = checkedColor || variantStyles.checked;
      const uncheckedBg = uncheckedColor || variantStyles.unchecked;
      const thumbBg = thumbColor || variantStyles.thumb;

      return (
        <button
          ref={inputRefInternal as any}
          type="button"
          className={cn(
            'relative inline-flex flex-shrink-0 cursor-pointer items-center transition-colors focus:outline-none focus:ring-2 focus:ring-offset-2',
            styleStyles.toggle,
            sizeStyles.toggle,
            checked ? checkedBg : uncheckedBg,
            hasError && 'ring-2 ring-red-500 ring-offset-2 dark:ring-red-400',
            disabled && 'opacity-50 cursor-not-allowed',
            isFocused && 'ring-2 ring-brand-500 ring-offset-2 dark:ring-brand-400'
          )}
          onClick={handleToggle}
          onKeyDown={handleKeyDown}
          onFocus={handleFocus}
          onBlur={handleBlur}
          disabled={disabled}
          role="switch"
          aria-checked={checked}
          aria-label={ariaLabel || label}
          aria-describedby={ariaDescribedby}
          aria-required={required}
          aria-invalid={hasError}
          tabIndex={disabled ? -1 : 0}
        >
          <input
            type="checkbox"
            className="sr-only"
            checked={checked}
            onChange={() => {}}
            disabled={disabled}
            required={required}
            name={name}
            id={id}
          />

          <motion.span
            className={cn(
              'pointer-events-none shadow-sm transition-all',
              styleStyles.thumb,
              sizeStyles.thumb,
              thumbBg
            )}
            initial={false}
            animate={{
              x: checked 
                ? `calc(${sizeStyles.toggle.replace('h-', '').replace('w-', '').split(' ')[1] || '11'}px - ${sizeStyles.thumb.replace('h-', '').replace('w-', '').split(' ')[1] || '4.5'}px)`
                : 0,
              scale: animation === 'scale' ? (checked ? 1.2 : 1) : 1,
              rotate: animation === 'bounce' ? (checked ? 10 : -10) : 0,
            }}
            transition={{
              duration: animationConfig.duration / 1000,
              type: animationConfig.type as any,
            }}
          >
            {/* Icônes */}
            <div className="flex h-full w-full items-center justify-center">
              {checked ? (
                checkedIcon || <CheckIcon className={cn('text-white', iconSize)} />
              ) : (
                uncheckedIcon || <XMarkIcon className={cn('text-gray-400', iconSize)} />
              )}
            </div>
          </motion.span>
        </button>
      );
    };

    // ========================================================================
    // RENDU DU LABEL
    // ========================================================================

    const renderLabel = () => {
      if (!label && !description) return null;

      return (
        <div className="flex-1 min-w-0">
          {label && (
            <Label className={cn(
              'font-medium text-gray-700 dark:text-gray-300',
              sizeStyles.label,
              disabled && 'opacity-50 cursor-not-allowed'
            )}>
              {label}
              {required && <span className="ml-1 text-red-500">*</span>}
            </Label>
          )}
          {description && (
            <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
          )}
        </div>
      );
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const labelPositions = {
      left: 'flex-row-reverse',
      right: 'flex-row',
      top: 'flex-col',
      bottom: 'flex-col-reverse',
      none: 'flex-row',
    };

    const labelGaps = {
      left: 'gap-3',
      right: 'gap-3',
      top: 'gap-2',
      bottom: 'gap-2',
      none: '',
    };

    return (
      <div
        ref={containerRef}
        id={id}
        className={cn(
          'relative inline-flex items-start',
          labelPositions[labelPosition],
          labelGaps[labelPosition],
          disabled && 'cursor-not-allowed'
        )}
        role="group"
        aria-label={ariaLabel || label}
        aria-describedby={ariaDescribedby}
      >
        {/* Toggle */}
        <div className="flex-shrink-0">
          {renderToggle()}
        </div>

        {/* Label */}
        {labelPosition !== 'none' && (
          <div className="flex-1 min-w-0">
            {renderLabel()}
          </div>
        )}

        {/* Statut */}
        <div className="mt-1 flex items-center gap-1.5 text-xs w-full">
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

ToggleField.displayName = 'ToggleField';

// ============================================================================
// EXPORTS
// ============================================================================

export default ToggleField;

// apps/web/src/components/common/RadioGroup.tsx
'use client';

import React, {
  ReactNode,
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
  forwardRef,
  Ref,
  createContext,
  useContext,
  useId,
  ChangeEvent,
  FocusEvent,
  KeyboardEvent,
  Children,
  isValidElement,
  cloneElement,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CheckCircleIcon,
  ExclamationCircleIcon,
  InformationCircleIcon,
  XCircleIcon,
  CheckIcon,
  MinusIcon,
  QuestionMarkCircleIcon,
  ExclamationTriangleIcon,
} from '@heroicons/react/24/outline';
import {
  CheckCircleIcon as CheckCircleSolid,
  ExclamationCircleIcon as ExclamationCircleSolid,
  InformationCircleIcon as InformationCircleSolid,
  XCircleIcon as XCircleSolid,
} from '@heroicons/react/24/solid';
import { Label } from '@/components/common/Label';
import { Tooltip } from '@/components/common/Tooltip';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Separator } from '@/components/common/Separator';

// ============================================================================
// TYPES
// ============================================================================

export type RadioVariant = 'default' | 'outlined' | 'solid' | 'card' | 'pill' | 'minimal' | 'button';

export type RadioSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';

export type RadioColor = 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'brand';

export type RadioDirection = 'horizontal' | 'vertical';

export type RadioAlignment = 'start' | 'center' | 'end' | 'stretch';

export type RadioStatus = 'default' | 'success' | 'error' | 'warning' | 'info';

export interface RadioOption {
  /** Valeur de l'option */
  value: string;
  /** Libellé de l'option */
  label: ReactNode;
  /** Description de l'option */
  description?: ReactNode;
  /** Icône de l'option */
  icon?: ReactNode;
  /** Icône sélectionnée */
  selectedIcon?: ReactNode;
  /** Désactiver l'option */
  disabled?: boolean;
  /** Statut de l'option */
  status?: RadioStatus;
  /** Message d'erreur */
  error?: string;
  /** Message de succès */
  success?: string;
  /** Message d'information */
  info?: string;
  /** Message d'avertissement */
  warning?: string;
  /** Classes additionnelles */
  className?: string;
  /** Données additionnelles */
  data?: any;
}

export interface RadioGroupProps {
  // --- Contrôle ---
  /** Valeur sélectionnée */
  value?: string;
  /** Valeur par défaut */
  defaultValue?: string;
  /** Callback lors du changement */
  onChange?: (value: string) => void;
  /** Callback lors de la sélection */
  onSelect?: (value: string, option: RadioOption) => void;

  // --- Options ---
  /** Options du groupe */
  options: RadioOption[];
  /** Nom du groupe (pour l'accessibilité) */
  name?: string;

  // --- Apparence ---
  /** Variante d'affichage */
  variant?: RadioVariant;
  /** Taille des radio */
  size?: RadioSize;
  /** Couleur du thème */
  color?: RadioColor;
  /** Direction du groupe */
  direction?: RadioDirection;
  /** Alignement des options */
  alignment?: RadioAlignment;
  /** Classes additionnelles */
  className?: string;
  /** Classes pour le conteneur */
  containerClassName?: string;
  /** Classes pour chaque option */
  optionClassName?: string;
  /** Classes pour le label */
  labelClassName?: string;
  /** Classes pour la description */
  descriptionClassName?: string;
  /** Classes pour l'icône */
  iconClassName?: string;

  // --- Comportement ---
  /** Désactiver tout le groupe */
  disabled?: boolean;
  /** Rendre le groupe obligatoire */
  required?: boolean;
  /** Afficher les messages de statut */
  showStatus?: boolean;
  /** Afficher les icônes de statut */
  showStatusIcon?: boolean;
  /** Afficher les descriptions */
  showDescriptions?: boolean;
  /** Afficher les icônes */
  showIcons?: boolean;
  /** Permettre la désélection */
  allowDeselect?: boolean;
  /** Désactiver l'animation */
  disableAnimation?: boolean;

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

  // --- États ---
  /** État de chargement */
  isLoading?: boolean;
  /** État d'erreur général */
  error?: string;
  /** Message d'information */
  info?: string;
  /** Message de succès */
  success?: string;
  /** Message d'avertissement */
  warning?: string;

  // --- Avancé ---
  /** Fonction de validation personnalisée */
  validate?: (value: string) => boolean | string;
  /** Callback de validation */
  onValidate?: (isValid: boolean, value: string) => void;
  /** Ref du champ */
  inputRef?: React.Ref<HTMLInputElement>;
  /** Afficher le focus visuel */
  showFocusRing?: boolean;
}

// ============================================================================
// CONTEXT
// ============================================================================

interface RadioGroupContextType {
  value: string | null;
  setValue: (value: string) => void;
  name: string;
  variant: RadioVariant;
  size: RadioSize;
  color: RadioColor;
  direction: RadioDirection;
  alignment: RadioAlignment;
  disabled: boolean;
  required: boolean;
  showStatus: boolean;
  showStatusIcon: boolean;
  showDescriptions: boolean;
  showIcons: boolean;
  disableAnimation: boolean;
  isLoading: boolean;
  gap: string | number;
  padding: string | number;
  columns: number;
  showFocusRing: boolean;
  optionClassName?: string;
  labelClassName?: string;
  descriptionClassName?: string;
  iconClassName?: string;
  registerOption: (value: string) => void;
  unregisterOption: (value: string) => void;
}

const RadioGroupContext = createContext<RadioGroupContextType | null>(null);

export const useRadioGroupContext = () => {
  const context = useContext(RadioGroupContext);
  if (!context) {
    throw new Error('useRadioGroupContext must be used within a RadioGroup');
  }
  return context;
};

// ============================================================================
// COMPOSANTS INTERNES
// ============================================================================

// --- Radio Option ---
interface RadioOptionProps {
  option: RadioOption;
  index: number;
  isSelected: boolean;
  isDisabled: boolean;
  onChange: (value: string) => void;
  className?: string;
}

const RadioOptionComponent: React.FC<RadioOptionProps> = ({
  option,
  index,
  isSelected,
  isDisabled,
  onChange,
  className,
}) => {
  const context = useRadioGroupContext();
  const {
    variant,
    size,
    color,
    direction,
    alignment,
    disabled: groupDisabled,
    showStatus,
    showStatusIcon,
    showDescriptions,
    showIcons,
    disableAnimation,
    gap,
    padding,
    showFocusRing,
    optionClassName,
    labelClassName,
    descriptionClassName,
    iconClassName,
  } = context;

  const inputRef = useRef<HTMLInputElement>(null);
  const optionId = useId();

  const isOptionDisabled = isDisabled || groupDisabled || option.disabled;
  const hasStatus = showStatus && (option.status || option.error || option.success || option.warning || option.info);
  const statusType = option.status || 
    (option.error ? 'error' : 
     option.success ? 'success' : 
     option.warning ? 'warning' : 
     option.info ? 'info' : undefined);

  // Statistiques de la variante
  const sizeMap = {
    xs: { radio: 'h-3 w-3', label: 'text-xs', padding: 'px-2 py-1', gap: 'gap-1.5' },
    sm: { radio: 'h-4 w-4', label: 'text-sm', padding: 'px-3 py-1.5', gap: 'gap-2' },
    md: { radio: 'h-5 w-5', label: 'text-sm', padding: 'px-4 py-2', gap: 'gap-2.5' },
    lg: { radio: 'h-6 w-6', label: 'text-base', padding: 'px-5 py-2.5', gap: 'gap-3' },
    xl: { radio: 'h-7 w-7', label: 'text-lg', padding: 'px-6 py-3', gap: 'gap-3.5' },
  };

  const colorMap = {
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
    neutral: {
      ring: 'ring-gray-500 dark:ring-gray-400',
      bg: 'bg-gray-500 dark:bg-gray-400',
      border: 'border-gray-500 dark:border-gray-400',
      text: 'text-gray-700 dark:text-gray-400',
    },
    brand: {
      ring: 'ring-brand-500 dark:ring-brand-400',
      bg: 'bg-brand-500 dark:bg-brand-400',
      border: 'border-brand-500 dark:border-brand-400',
      text: 'text-brand-700 dark:text-brand-400',
    },
  };

  const colorStyle = colorMap[color] || colorMap.brand;

  const variantClasses = {
    default: {
      container: cn(
        'flex items-center rounded-lg transition-colors cursor-pointer',
        !isOptionDisabled && 'hover:bg-gray-50 dark:hover:bg-gray-800/50',
        isSelected && 'bg-gray-50 dark:bg-gray-800/50',
        isOptionDisabled && 'opacity-50 cursor-not-allowed'
      ),
      radio: cn(
        'flex-shrink-0 rounded-full border-2 transition-all',
        sizeMap[size].radio,
        isSelected ? `${colorStyle.border} border-2` : 'border-gray-300 dark:border-gray-600',
        isOptionDisabled && 'border-gray-300 dark:border-gray-700'
      ),
      dot: cn(
        'rounded-full transition-transform',
        isSelected ? 'scale-100' : 'scale-0',
        colorStyle.bg
      ),
    },
    outlined: {
      container: cn(
        'flex items-center rounded-lg border-2 transition-all cursor-pointer',
        isSelected 
          ? `${colorStyle.border} bg-transparent` 
          : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600',
        isOptionDisabled && 'opacity-50 cursor-not-allowed'
      ),
      radio: cn(
        'flex-shrink-0 rounded-full border-2 transition-all',
        sizeMap[size].radio,
        isSelected ? `${colorStyle.border} bg-transparent` : 'border-gray-300 dark:border-gray-600'
      ),
      dot: cn(
        'rounded-full transition-transform',
        isSelected ? 'scale-100' : 'scale-0',
        colorStyle.bg
      ),
    },
    solid: {
      container: cn(
        'flex items-center rounded-lg transition-all cursor-pointer',
        isSelected 
          ? `${colorStyle.bg} text-white dark:text-white` 
          : 'bg-gray-100 dark:bg-gray-800 hover:bg-gray-200 dark:hover:bg-gray-700',
        isOptionDisabled && 'opacity-50 cursor-not-allowed'
      ),
      radio: cn(
        'flex-shrink-0 rounded-full border-2 transition-all',
        sizeMap[size].radio,
        isSelected ? 'border-white' : 'border-gray-400 dark:border-gray-500',
        isSelected && 'bg-white/20'
      ),
      dot: cn(
        'rounded-full transition-transform',
        isSelected ? 'scale-100' : 'scale-0',
        'bg-white'
      ),
    },
    card: {
      container: cn(
        'flex flex-col rounded-xl border-2 transition-all cursor-pointer p-4',
        isSelected 
          ? `${colorStyle.border} bg-gray-50 dark:bg-gray-800/50 shadow-md` 
          : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600 hover:shadow-sm',
        isOptionDisabled && 'opacity-50 cursor-not-allowed'
      ),
      radio: cn(
        'flex-shrink-0 rounded-full border-2 transition-all',
        sizeMap[size].radio,
        isSelected ? `${colorStyle.border}` : 'border-gray-300 dark:border-gray-600'
      ),
      dot: cn(
        'rounded-full transition-transform',
        isSelected ? 'scale-100' : 'scale-0',
        colorStyle.bg
      ),
    },
    pill: {
      container: cn(
        'flex items-center rounded-full transition-all cursor-pointer',
        !isOptionDisabled && 'hover:bg-gray-50 dark:hover:bg-gray-800/50',
        isSelected && 'bg-gray-50 dark:bg-gray-800/50',
        isOptionDisabled && 'opacity-50 cursor-not-allowed'
      ),
      radio: cn(
        'flex-shrink-0 rounded-full border-2 transition-all',
        sizeMap[size].radio,
        isSelected ? `${colorStyle.border}` : 'border-gray-300 dark:border-gray-600'
      ),
      dot: cn(
        'rounded-full transition-transform',
        isSelected ? 'scale-100' : 'scale-0',
        colorStyle.bg
      ),
    },
    minimal: {
      container: cn(
        'flex items-center transition-colors cursor-pointer border-b-2',
        isSelected 
          ? `${colorStyle.border} border-b-2` 
          : 'border-transparent hover:border-gray-300 dark:hover:border-gray-600',
        isOptionDisabled && 'opacity-50 cursor-not-allowed'
      ),
      radio: cn(
        'flex-shrink-0 rounded-full border-2 transition-all',
        sizeMap[size].radio,
        isSelected ? `${colorStyle.border}` : 'border-gray-300 dark:border-gray-600'
      ),
      dot: cn(
        'rounded-full transition-transform',
        isSelected ? 'scale-100' : 'scale-0',
        colorStyle.bg
      ),
    },
    button: {
      container: cn(
        'flex items-center justify-center rounded-lg transition-all cursor-pointer font-medium',
        isSelected 
          ? `${colorStyle.bg} text-white dark:text-white shadow-md` 
          : 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-300 hover:bg-gray-200 dark:hover:bg-gray-700',
        isOptionDisabled && 'opacity-50 cursor-not-allowed'
      ),
      radio: cn(
        'flex-shrink-0 rounded-full border-2 transition-all',
        sizeMap[size].radio,
        isSelected ? 'border-white' : 'border-gray-400 dark:border-gray-500',
        isSelected && 'bg-white/20'
      ),
      dot: cn(
        'rounded-full transition-transform',
        isSelected ? 'scale-100' : 'scale-0',
        'bg-white'
      ),
    },
  };

  const variantStyle = variantClasses[variant] || variantClasses.default;

  // Rendu de l'icône de statut
  const renderStatusIcon = () => {
    if (!showStatusIcon) return null;

    const iconMap = {
      success: <CheckCircleIcon className="h-4 w-4 text-green-500" />,
      error: <XCircleIcon className="h-4 w-4 text-red-500" />,
      warning: <ExclamationTriangleIcon className="h-4 w-4 text-yellow-500" />,
      info: <InformationCircleIcon className="h-4 w-4 text-blue-500" />,
    };

    if (option.error) return iconMap.error;
    if (option.success) return iconMap.success;
    if (option.warning) return iconMap.warning;
    if (option.info) return iconMap.info;
    if (statusType) return iconMap[statusType as keyof typeof iconMap];

    return null;
  };

  // Rendu du message de statut
  const renderStatusMessage = () => {
    if (!showStatus) return null;

    const message = option.error || option.success || option.warning || option.info;
    if (!message) return null;

    const statusColors = {
      error: 'text-red-600 dark:text-red-400',
      success: 'text-green-600 dark:text-green-400',
      warning: 'text-yellow-600 dark:text-yellow-400',
      info: 'text-blue-600 dark:text-blue-400',
    };

    const color = option.error ? 'error' :
                  option.success ? 'success' :
                  option.warning ? 'warning' :
                  option.info ? 'info' : 'info';

    return (
      <span className={cn('text-xs mt-1', statusColors[color])}>
        {message}
      </span>
    );
  };

  // Gestion des événements
  const handleChange = () => {
    if (!isOptionDisabled) {
      onChange(option.value);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      handleChange();
    }
  };

  // Animation du dot
  const dotAnimation = disableAnimation ? {} : {
    initial: { scale: 0 },
    animate: { scale: isSelected ? 1 : 0 },
    transition: { type: 'spring', stiffness: 300, damping: 20 }
  };

  // Rendu du contenu principal
  const renderContent = () => {
    if (variant === 'card') {
      return (
        <div className="flex w-full items-center gap-3">
          <div className={variantStyle.radio}>
            <motion.div {...dotAnimation} className={cn('h-full w-full p-[2px]', variantStyle.dot)} />
          </div>
          <div className="flex-1 min-w-0">
            <div className={cn('font-medium', labelClassName)}>
              {option.label}
            </div>
            {showDescriptions && option.description && (
              <div className={cn('text-sm text-gray-500 dark:text-gray-400', descriptionClassName)}>
                {option.description}
              </div>
            )}
            {renderStatusMessage()}
          </div>
          {option.icon && (
            <span className={cn('text-gray-400', iconClassName)}>
              {option.icon}
            </span>
          )}
          {renderStatusIcon()}
          {isSelected && (
            <CheckIcon className="h-5 w-5 text-brand-500" />
          )}
        </div>
      );
    }

    return (
      <>
        <div className={variantStyle.radio}>
          <motion.div {...dotAnimation} className={cn('h-full w-full p-[2px]', variantStyle.dot)} />
        </div>
        <div className="flex-1 min-w-0">
          <div className={cn('font-medium', labelClassName)}>
            {option.label}
          </div>
          {showDescriptions && option.description && (
            <div className={cn('text-sm text-gray-500 dark:text-gray-400', descriptionClassName)}>
              {option.description}
            </div>
          )}
          {renderStatusMessage()}
        </div>
        {showIcons && option.icon && (
          <span className={cn('text-gray-400', iconClassName)}>
            {isSelected && option.selectedIcon ? option.selectedIcon : option.icon}
          </span>
        )}
        {renderStatusIcon()}
      </>
    );
  };

  return (
    <label
      className={cn(
        variantStyle.container,
        sizeMap[size].padding,
        sizeMap[size].gap,
        variant === 'card' && 'w-full',
        alignment === 'center' && 'justify-center',
        alignment === 'end' && 'justify-end',
        alignment === 'stretch' && 'w-full justify-between',
        optionClassName,
        className
      )}
      style={{
        gap: typeof gap === 'number' ? `${gap}px` : gap,
        padding: typeof padding === 'number' ? `${padding}px` : padding,
      }}
      onKeyDown={handleKeyDown}
      tabIndex={isOptionDisabled ? -1 : 0}
      role="radio"
      aria-checked={isSelected}
      aria-disabled={isOptionDisabled}
      aria-labelledby={`${optionId}-label`}
    >
      <input
        ref={inputRef}
        type="radio"
        name={context.name}
        value={option.value}
        checked={isSelected}
        onChange={handleChange}
        disabled={isOptionDisabled}
        className="sr-only"
        id={optionId}
        aria-describedby={ariaDescribedby}
        tabIndex={-1}
      />
      <div className="flex items-center gap-2 w-full">
        {renderContent()}
      </div>
    </label>
  );
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const RadioGroup = forwardRef<HTMLDivElement, RadioGroupProps>(
  (props, ref) => {
    const {
      // Contrôle
      value: externalValue,
      defaultValue,
      onChange,
      onSelect,

      // Options
      options,
      name: externalName,

      // Apparence
      variant = 'default',
      size = 'md',
      color = 'brand',
      direction = 'vertical',
      alignment = 'start',
      className,
      containerClassName,
      optionClassName,
      labelClassName,
      descriptionClassName,
      iconClassName,

      // Comportement
      disabled = false,
      required = false,
      showStatus = true,
      showStatusIcon = true,
      showDescriptions = true,
      showIcons = true,
      allowDeselect = false,
      disableAnimation = false,

      // Layout
      gap = 4,
      padding = 12,
      columns,

      // Accessibilité
      ariaLabel,
      ariaDescribedby,
      id,

      // États
      isLoading = false,
      error,
      info,
      success,
      warning,

      // Avancé
      validate,
      onValidate,
      inputRef,
      showFocusRing = true,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const containerRef = useRef<HTMLDivElement>(null);
    const uniqueId = useId();
    const groupId = id || `nexus-radio-group-${uniqueId}`;
    const name = externalName || groupId;

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalValue, setInternalValue] = useState<string | null>(defaultValue || null);
    const [registeredOptions, setRegisteredOptions] = useState<Set<string>>(new Set());
    const [isValid, setIsValid] = useState(true);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined ? externalValue : internalValue;
    const isControlled = externalValue !== undefined;
    const selectedOption = options.find((opt) => opt.value === value);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    useEffect(() => {
      if (!validate) return;

      const result = validate(value || '');
      const valid = typeof result === 'string' ? false : result;
      setIsValid(valid);
      if (onValidate) onValidate(valid, value || '');
    }, [value, validate, onValidate]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const setValue = useCallback((newValue: string) => {
      let finalValue = newValue;

      // Permettre la désélection
      if (allowDeselect && value === newValue) {
        finalValue = '';
      }

      if (isControlled) {
        if (onChange) onChange(finalValue);
      } else {
        setInternalValue(finalValue || null);
        if (onChange) onChange(finalValue);
      }

      // Appeler onSelect
      const selectedOpt = options.find((opt) => opt.value === finalValue);
      if (selectedOpt && onSelect) {
        onSelect(finalValue, selectedOpt);
      }
    }, [isControlled, onChange, onSelect, options, value, allowDeselect]);

    // ========================================================================
    // ENREGISTREMENT DES OPTIONS
    // ========================================================================

    const registerOption = useCallback((optionValue: string) => {
      setRegisteredOptions((prev) => new Set([...prev, optionValue]));
    }, []);

    const unregisterOption = useCallback((optionValue: string) => {
      setRegisteredOptions((prev) => {
        const next = new Set(prev);
        next.delete(optionValue);
        return next;
      });
    }, []);

    // ========================================================================
    // CONTEXT
    // ========================================================================

    const contextValue = useMemo<RadioGroupContextType>(
      () => ({
        value: value || null,
        setValue,
        name,
        variant,
        size,
        color,
        direction,
        alignment,
        disabled,
        required,
        showStatus,
        showStatusIcon,
        showDescriptions,
        showIcons,
        disableAnimation,
        isLoading,
        gap,
        padding,
        columns: columns || 1,
        showFocusRing,
        optionClassName,
        labelClassName,
        descriptionClassName,
        iconClassName,
        registerOption,
        unregisterOption,
      }),
      [
        value,
        setValue,
        name,
        variant,
        size,
        color,
        direction,
        alignment,
        disabled,
        required,
        showStatus,
        showStatusIcon,
        showDescriptions,
        showIcons,
        disableAnimation,
        isLoading,
        gap,
        padding,
        columns,
        showFocusRing,
        optionClassName,
        labelClassName,
        descriptionClassName,
        iconClassName,
        registerOption,
        unregisterOption,
      ]
    );

    // ========================================================================
    // GESTION DU STATUT GLOBAL
    // ========================================================================

    const globalStatus = error || warning || success || info;
    const globalStatusType = error ? 'error' : warning ? 'warning' : success ? 'success' : info ? 'info' : null;

    const renderGlobalStatus = () => {
      if (!globalStatus) return null;

      const statusIcons = {
        error: <XCircleIcon className="h-5 w-5" />,
        warning: <ExclamationTriangleIcon className="h-5 w-5" />,
        success: <CheckCircleIcon className="h-5 w-5" />,
        info: <InformationCircleIcon className="h-5 w-5" />,
      };

      const statusColors = {
        error: 'text-red-600 dark:text-red-400',
        warning: 'text-yellow-600 dark:text-yellow-400',
        success: 'text-green-600 dark:text-green-400',
        info: 'text-blue-600 dark:text-blue-400',
      };

      return (
        <div className={cn('mt-2 flex items-center gap-2 text-sm', statusColors[globalStatusType as keyof typeof statusColors])}>
          {showStatusIcon && statusIcons[globalStatusType as keyof typeof statusIcons]}
          <span>{globalStatus}</span>
        </div>
      );
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const gridCols = columns && columns > 1 ? `grid-cols-${Math.min(columns, 4)}` : '';

    return (
      <RadioGroupContext.Provider value={contextValue}>
        <div
          ref={ref}
          id={groupId}
          className={cn('space-y-2', containerClassName)}
          role="radiogroup"
          aria-label={ariaLabel || 'Groupe de sélection'}
          aria-describedby={ariaDescribedby}
          aria-required={required}
          aria-disabled={disabled}
          aria-invalid={!isValid}
        >
          <div
            ref={containerRef}
            className={cn(
              'flex',
              direction === 'horizontal' ? 'flex-wrap items-center' : 'flex-col',
              direction === 'horizontal' && `gap-${gap}`,
              direction === 'vertical' && `gap-${gap}`,
              columns && columns > 1 && `grid grid-cols-${columns}`,
              className
            )}
            style={{
              gap: typeof gap === 'number' ? `${gap}px` : gap,
            }}
          >
            {options.map((option, index) => {
              const isSelected = option.value === value;
              const isOptionDisabled = option.disabled || disabled;

              return (
                <RadioOptionComponent
                  key={option.value}
                  option={option}
                  index={index}
                  isSelected={!!isSelected}
                  isDisabled={!!isOptionDisabled}
                  onChange={setValue}
                  className={optionClassName}
                />
              );
            })}
          </div>

          {/* Statut global */}
          {renderGlobalStatus()}

          {/* Compteur d'options sélectionnées */}
          {!disabled && options.length > 0 && (
            <div className="text-xs text-gray-500 dark:text-gray-400">
              {value ? `Option sélectionnée : ${selectedOption?.label || value}` : 'Aucune option sélectionnée'}
            </div>
          )}
        </div>
      </RadioGroupContext.Provider>
    );
  }
);

RadioGroup.displayName = 'RadioGroup';

// ============================================================================
// SOUS-COMPOSANTS
// ============================================================================

// --- RadioGroup.Item ---
interface RadioGroupItemProps {
  value: string;
  children: ReactNode;
  disabled?: boolean;
  className?: string;
}

export const RadioGroupItem: React.FC<RadioGroupItemProps> = ({
  value,
  children,
  disabled = false,
  className,
}) => {
  const context = useRadioGroupContext();
  const isSelected = context.value === value;
  const isDisabled = disabled || context.disabled;

  const handleClick = () => {
    if (!isDisabled) {
      context.setValue(value);
    }
  };

  return (
    <div
      className={cn(
        'cursor-pointer transition-colors',
        isSelected && 'bg-brand-50 dark:bg-brand-900/20',
        isDisabled && 'opacity-50 cursor-not-allowed',
        className
      )}
      onClick={handleClick}
      role="radio"
      aria-checked={isSelected}
      aria-disabled={isDisabled}
    >
      {children}
    </div>
  );
};

// ============================================================================
// HOOKS
// ============================================================================

export const useRadioGroup = (defaultValue?: string) => {
  const [value, setValue] = useState<string | null>(defaultValue || null);

  const onChange = useCallback((newValue: string) => {
    setValue(newValue);
  }, []);

  const reset = useCallback(() => {
    setValue(null);
  }, []);

  return {
    value,
    setValue,
    onChange,
    reset,
    isSelected: (optionValue: string) => value === optionValue,
  };
};

// ============================================================================
// EXPORTS
// ============================================================================

export default Object.assign(RadioGroup, {
  Item: RadioGroupItem,
});

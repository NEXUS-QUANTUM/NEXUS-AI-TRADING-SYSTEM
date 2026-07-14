// apps/web/src/components/forms/fields/SelectField.tsx
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
  ChevronDownIcon,
  ChevronUpIcon,
  CheckIcon,
  XMarkIcon,
  MagnifyingGlassIcon,
  PlusIcon,
  MinusIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ExclamationCircleIcon,
  CheckCircleIcon,
  ArrowPathIcon,
} from '@heroicons/react/24/outline';
import {
  CheckIcon as CheckSolid,
  ChevronDownIcon as ChevronDownSolid,
} from '@heroicons/react/24/solid';
import { Label } from '@/components/common/Label';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Tooltip } from '@/components/common/Tooltip';
import { ScrollArea } from '@/components/common/ScrollArea';
import { Input } from '@/components/common/Input';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type SelectOption = {
  /** Valeur de l'option */
  value: string;
  /** Libellé de l'option */
  label: string;
  /** Description de l'option */
  description?: string;
  /** Icône de l'option */
  icon?: React.ReactNode;
  /** Groupe de l'option */
  group?: string;
  /** Désactiver l'option */
  disabled?: boolean;
  /** Données additionnelles */
  data?: any;
  /** Classes additionnelles */
  className?: string;
};

export type SelectGroup = {
  /** Identifiant du groupe */
  id: string;
  /** Libellé du groupe */
  label: string;
  /** Icône du groupe */
  icon?: React.ReactNode;
  /** Options du groupe */
  options: SelectOption[];
};

export type SelectVariant = 'default' | 'outlined' | 'solid' | 'ghost' | 'minimal' | 'pill';
export type SelectSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
export type SelectColor = 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'brand';
export type SelectStatus = 'default' | 'success' | 'error' | 'warning' | 'info';
export type SelectPlacement = 'bottom' | 'top' | 'bottom-start' | 'bottom-end' | 'top-start' | 'top-end';

export interface SelectFieldProps {
  // --- Contrôle ---
  /** Valeur sélectionnée */
  value?: string | string[] | null;
  /** Valeur par défaut */
  defaultValue?: string | string[] | null;
  /** Callback de changement */
  onChange?: (value: string | string[] | null) => void;
  /** Callback de sélection */
  onSelect?: (option: SelectOption) => void;
  /** Callback de blur */
  onBlur?: () => void;
  /** Callback de focus */
  onFocus?: () => void;
  /** Callback de validation */
  onValidate?: (valid: boolean, value: string | string[] | null) => void;

  // --- Options ---
  /** Options du sélecteur */
  options?: SelectOption[];
  /** Groupes d'options */
  groups?: SelectGroup[];
  /** Options chargées de manière asynchrone */
  loadOptions?: (input: string) => Promise<SelectOption[]>;

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
  variant?: SelectVariant;
  /** Taille du sélecteur */
  size?: SelectSize;
  /** Couleur du thème */
  color?: SelectColor;
  /** Statut du sélecteur */
  status?: SelectStatus;
  /** Position du menu */
  placement?: SelectPlacement;
  /** Afficher l'icône de validation */
  showValidationIcon?: boolean;
  /** Afficher le compteur (multi) */
  showCounter?: boolean;
  /** Afficher les badges (multi) */
  showBadges?: boolean;

  // --- Comportement ---
  /** Mode multi-sélection */
  multi?: boolean;
  /** Recherche dans les options */
  searchable?: boolean;
  /** Placeholder de la recherche */
  searchPlaceholder?: string;
  /** Désactiver le champ */
  disabled?: boolean;
  /** Rendre le champ obligatoire */
  required?: boolean;
  /** Nombre maximal d'options sélectionnées (multi) */
  maxSelected?: number;
  /** Nombre minimal d'options sélectionnées (multi) */
  minSelected?: number;
  /** Désactiver la fermeture automatique */
  closeOnSelect?: boolean;
  /** Désactiver la validation en temps réel */
  disableRealtimeValidation?: boolean;
  /** Validation personnalisée */
  validateSelect?: (value: string | string[] | null) => boolean | string;

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
  /** Fonction de rendu personnalisée des options */
  renderOption?: (option: SelectOption, isSelected: boolean, isHighlighted: boolean) => React.ReactNode;
  /** Fonction de rendu personnalisée des groupes */
  renderGroup?: (group: SelectGroup) => React.ReactNode;
  /** Fonction de rendu personnalisée de la valeur sélectionnée */
  renderValue?: (selected: SelectOption[]) => React.ReactNode;
  /** Ref */
  inputRef?: React.Ref<HTMLInputElement>;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const SIZE_MAP: Record<SelectSize, { trigger: string; option: string; icon: string }> = {
  xs: {
    trigger: 'h-7 text-xs px-2',
    option: 'text-xs py-1 px-2',
    icon: 'h-3 w-3',
  },
  sm: {
    trigger: 'h-8 text-sm px-3',
    option: 'text-sm py-1.5 px-3',
    icon: 'h-3.5 w-3.5',
  },
  md: {
    trigger: 'h-10 text-sm px-4',
    option: 'text-sm py-2 px-4',
    icon: 'h-4 w-4',
  },
  lg: {
    trigger: 'h-12 text-base px-5',
    option: 'text-base py-2.5 px-5',
    icon: 'h-5 w-5',
  },
  xl: {
    trigger: 'h-14 text-lg px-6',
    option: 'text-lg py-3 px-6',
    icon: 'h-6 w-6',
  },
};

const VARIANT_MAP: Record<SelectVariant, string> = {
  default: 'bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600',
  outlined: 'bg-transparent border-2 border-gray-300 dark:border-gray-600',
  solid: 'bg-gray-100 dark:bg-gray-800 border border-transparent',
  ghost: 'bg-transparent border border-transparent hover:bg-gray-100 dark:hover:bg-gray-800',
  minimal: 'bg-transparent border-b-2 border-gray-300 dark:border-gray-600 rounded-none',
  pill: 'bg-white dark:bg-gray-900 border border-gray-300 dark:border-gray-600 rounded-full',
};

const STATUS_MAP: Record<SelectStatus, { border: string; text: string; icon: React.ReactNode }> = {
  default: {
    border: 'border-gray-300 dark:border-gray-600',
    text: 'text-gray-900 dark:text-white',
    icon: null,
  },
  success: {
    border: 'border-green-500 dark:border-green-400',
    text: 'text-green-700 dark:text-green-400',
    icon: <CheckCircleIcon className="h-4 w-4" />,
  },
  error: {
    border: 'border-red-500 dark:border-red-400',
    text: 'text-red-700 dark:text-red-400',
    icon: <ExclamationCircleIcon className="h-4 w-4" />,
  },
  warning: {
    border: 'border-yellow-500 dark:border-yellow-400',
    text: 'text-yellow-700 dark:text-yellow-400',
    icon: <ExclamationTriangleIcon className="h-4 w-4" />,
  },
  info: {
    border: 'border-blue-500 dark:border-blue-400',
    text: 'text-blue-700 dark:text-blue-400',
    icon: <InformationCircleIcon className="h-4 w-4" />,
  },
};

const COLOR_MAP: Record<SelectColor, { bg: string; hover: string; focus: string }> = {
  primary: {
    bg: 'bg-brand-500',
    hover: 'hover:bg-brand-600',
    focus: 'ring-brand-500',
  },
  success: {
    bg: 'bg-green-500',
    hover: 'hover:bg-green-600',
    focus: 'ring-green-500',
  },
  warning: {
    bg: 'bg-yellow-500',
    hover: 'hover:bg-yellow-600',
    focus: 'ring-yellow-500',
  },
  danger: {
    bg: 'bg-red-500',
    hover: 'hover:bg-red-600',
    focus: 'ring-red-500',
  },
  info: {
    bg: 'bg-blue-500',
    hover: 'hover:bg-blue-600',
    focus: 'ring-blue-500',
  },
  neutral: {
    bg: 'bg-gray-500',
    hover: 'hover:bg-gray-600',
    focus: 'ring-gray-500',
  },
  brand: {
    bg: 'bg-brand-500',
    hover: 'hover:bg-brand-600',
    focus: 'ring-brand-500',
  },
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const SelectField = forwardRef<HTMLDivElement, SelectFieldProps>(
  (props, ref) => {
    const {
      // Contrôle
      value: externalValue,
      defaultValue,
      onChange,
      onSelect,
      onBlur,
      onFocus,
      onValidate,

      // Options
      options = [],
      groups = [],
      loadOptions,

      // Apparence
      label,
      placeholder = 'Sélectionner...',
      description,
      error,
      success,
      info,
      variant = 'default',
      size = 'md',
      color = 'brand',
      status = 'default',
      placement = 'bottom',
      showValidationIcon = true,
      showCounter = true,
      showBadges = true,

      // Comportement
      multi = false,
      searchable = false,
      searchPlaceholder = 'Rechercher...',
      disabled = false,
      required = false,
      maxSelected,
      minSelected,
      closeOnSelect = true,
      disableRealtimeValidation = false,
      validateSelect: customValidate,

      // Accessibilité
      ariaLabel,
      ariaDescribedby,
      id,
      name,

      // Avancé
      renderOption,
      renderGroup,
      renderValue,
      inputRef,
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const containerRef = useRef<HTMLDivElement>(null);
    const triggerRef = useRef<HTMLButtonElement>(null);
    const searchInputRef = useRef<HTMLInputElement>(null);
    const prevValueRef = useRef<string | string[] | null>(null);

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalValue, setInternalValue] = useState<string | string[] | null>(
      defaultValue || (multi ? [] : null)
    );
    const [isOpen, setIsOpen] = useState(false);
    const [isFocused, setIsFocused] = useState(false);
    const [isValid, setIsValid] = useState(true);
    const [validationMessage, setValidationMessage] = useState<string>('');
    const [searchValue, setSearchValue] = useState('');
    const [highlightedIndex, setHighlightedIndex] = useState(0);
    const [isLoadingOptions, setIsLoadingOptions] = useState(false);
    const [loadedOptions, setLoadedOptions] = useState<SelectOption[]>([]);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined ? externalValue : internalValue;
    const isControlled = externalValue !== undefined;
    const isMulti = multi;

    const allOptions = useMemo(() => {
      if (groups.length > 0) {
        return groups.flatMap((g) => g.options);
      }
      return [...options, ...loadedOptions];
    }, [options, groups, loadedOptions]);

    const selectedOptions = useMemo(() => {
      const values = Array.isArray(value) ? value : [value];
      return allOptions.filter((opt) => values.includes(opt.value));
    }, [value, allOptions]);

    const filteredOptions = useMemo(() => {
      if (!searchValue) return allOptions;
      const query = searchValue.toLowerCase();
      return allOptions.filter((opt) => {
        const label = opt.label.toLowerCase();
        const desc = opt.description ? opt.description.toLowerCase() : '';
        return label.includes(query) || desc.includes(query);
      });
    }, [allOptions, searchValue]);

    const sizeStyles = SIZE_MAP[size] || SIZE_MAP.md;
    const variantStyles = VARIANT_MAP[variant] || VARIANT_MAP.default;
    const statusStyles = STATUS_MAP[status] || STATUS_MAP.default;
    const colorStyles = COLOR_MAP[color] || COLOR_MAP.brand;

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validateValue = useCallback((val: string | string[] | null): { valid: boolean; message: string } => {
      if (customValidate) {
        const result = customValidate(val);
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        return { valid: true, message: '' };
      }

      const values = Array.isArray(val) ? val : (val ? [val] : []);

      if (values.length === 0) {
        if (required) {
          return { valid: false, message: 'Veuillez sélectionner une option' };
        }
        return { valid: true, message: '' };
      }

      if (isMulti) {
        if (minSelected && values.length < minSelected) {
          return { valid: false, message: `Sélectionnez au moins ${minSelected} option${minSelected > 1 ? 's' : ''}` };
        }
        if (maxSelected && values.length > maxSelected) {
          return { valid: false, message: `Sélectionnez au maximum ${maxSelected} option${maxSelected > 1 ? 's' : ''}` };
        }
      }

      // Vérifier que toutes les valeurs existent
      for (const v of values) {
        const exists = allOptions.some((opt) => opt.value === v);
        if (!exists) {
          return { valid: false, message: `Option "${v}" invalide` };
        }
      }

      return { valid: true, message: '' };
    }, [customValidate, required, isMulti, minSelected, maxSelected, allOptions]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateValue = useCallback((val: string | string[] | null) => {
      const validation = validateValue(val);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);

      if (!disableRealtimeValidation && onValidate) {
        onValidate(validation.valid, val);
      }

      if (isControlled) {
        if (onChange) onChange(val);
      } else {
        setInternalValue(val);
        if (onChange) onChange(val);
      }

      if (debug) {
        console.log('SelectField update:', { val, isValid: validation.valid });
      }
    }, [
      validateValue,
      isControlled,
      onChange,
      onValidate,
      disableRealtimeValidation,
      debug,
    ]);

    // ========================================================================
    // GESTION DE LA SÉLECTION
    // ========================================================================

    const selectOption = useCallback((option: SelectOption) => {
      if (option.disabled) return;

      if (isMulti) {
        const currentValues = Array.isArray(value) ? value : [];
        if (maxSelected && currentValues.length >= maxSelected) {
          toast({
            title: 'Limite atteinte',
            description: `Vous ne pouvez pas sélectionner plus de ${maxSelected} options`,
            variant: 'destructive',
          });
          return;
        }

        const newValues = currentValues.includes(option.value)
          ? currentValues.filter((v) => v !== option.value)
          : [...currentValues, option.value];

        updateValue(newValues);
        onSelect?.(option);
      } else {
        updateValue(option.value);
        onSelect?.(option);
        if (closeOnSelect) setIsOpen(false);
      }
    }, [isMulti, value, maxSelected, updateValue, onSelect, closeOnSelect, toast]);

    const removeOption = useCallback((optionValue: string) => {
      if (!isMulti) return;

      const currentValues = Array.isArray(value) ? value : [];
      const newValues = currentValues.filter((v) => v !== optionValue);
      updateValue(newValues);
    }, [isMulti, value, updateValue]);

    const clearAll = useCallback(() => {
      if (isMulti) {
        updateValue([]);
      } else {
        updateValue(null);
      }
    }, [isMulti, updateValue]);

    // ========================================================================
    // GESTIONNAIRES D'ÉVÉNEMENTS
    // ========================================================================

    const handleTriggerClick = useCallback(() => {
      if (disabled) return;
      setIsOpen(!isOpen);
      if (!isOpen && searchable) {
        setTimeout(() => searchInputRef.current?.focus(), 100);
      }
    }, [disabled, isOpen, searchable]);

    const handleTriggerKeyDown = useCallback((e: React.KeyboardEvent) => {
      if (disabled) return;

      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        setIsOpen(!isOpen);
      } else if (e.key === 'Escape') {
        setIsOpen(false);
      } else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
        e.preventDefault();
        if (!isOpen) {
          setIsOpen(true);
        } else {
          const direction = e.key === 'ArrowDown' ? 1 : -1;
          const totalItems = filteredOptions.length;
          if (totalItems > 0) {
            setHighlightedIndex((prev) => {
              const newIndex = prev + direction;
              if (newIndex < 0) return totalItems - 1;
              if (newIndex >= totalItems) return 0;
              return newIndex;
            });
          }
        }
      }
    }, [disabled, isOpen, filteredOptions]);

    const handleOptionKeyDown = useCallback((e: React.KeyboardEvent, option: SelectOption) => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        selectOption(option);
      }
    }, [selectOption]);

    const handleSearchChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
      setSearchValue(e.target.value);
      setHighlightedIndex(0);
    }, []);

    const handleFocus = useCallback(() => {
      setIsFocused(true);
      if (onFocus) onFocus();
    }, [onFocus]);

    const handleBlur = useCallback(() => {
      setIsFocused(false);
      setTimeout(() => setIsOpen(false), 200);
      if (onBlur) onBlur();
    }, [onBlur]);

    // ========================================================================
    // CHARGEMENT ASYNCHRONE
    // ========================================================================

    useEffect(() => {
      if (!loadOptions || !isOpen) return;

      const load = async () => {
        setIsLoadingOptions(true);
        try {
          const result = await loadOptions(searchValue);
          setLoadedOptions(result);
        } catch (error) {
          console.error('Erreur de chargement:', error);
        } finally {
          setIsLoadingOptions(false);
        }
      };

      const timer = setTimeout(load, 300);
      return () => clearTimeout(timer);
    }, [loadOptions, isOpen, searchValue]);

    // ========================================================================
    // SYNC AVEC LA VALEUR EXTERNE
    // ========================================================================

    useEffect(() => {
      if (externalValue !== undefined && JSON.stringify(externalValue) !== JSON.stringify(prevValueRef.current)) {
        prevValueRef.current = externalValue;
        const validation = validateValue(externalValue);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
      }
    }, [externalValue, validateValue]);

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
      focus: () => triggerRef.current?.focus(),
      blur: () => triggerRef.current?.blur(),
      getValue: () => value,
      setValue: (val: string | string[] | null) => updateValue(val),
      open: () => setIsOpen(true),
      close: () => setIsOpen(false),
      toggle: () => setIsOpen(!isOpen),
      clear: () => clearAll(),
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

    const hasError = !!error || !isValid || (required && (!value || (Array.isArray(value) && value.length === 0)));
    const isSuccess = !hasError && success && value && (Array.isArray(value) ? value.length > 0 : true);

    const displayOptions = groups.length > 0 ? groups : [{ id: 'default', label: '', options: filteredOptions }];

    return (
      <div ref={containerRef} className="relative space-y-1.5" id={id}>
        {/* Label */}
        {label && (
          <div className="flex items-center justify-between">
            <Label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {label}
              {required && <span className="ml-1 text-red-500">*</span>}
            </Label>
            {showCounter && isMulti && selectedOptions.length > 0 && (
              <Badge variant="outline" size="sm">
                {selectedOptions.length} sélectionné{selectedOptions.length > 1 ? 's' : ''}
                {maxSelected && ` / ${maxSelected}`}
              </Badge>
            )}
          </div>
        )}

        {/* Description */}
        {description && (
          <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
        )}

        {/* Trigger */}
        <div className="relative">
          <button
            ref={triggerRef}
            type="button"
            className={cn(
              'relative flex w-full cursor-pointer items-center gap-2 rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-offset-2',
              variantStyles,
              statusStyles.border,
              isOpen && `ring-2 ring-${colorStyles.focus} ring-offset-2`,
              hasError && 'border-red-500 ring-2 ring-red-500/20 dark:border-red-400',
              isSuccess && 'border-green-500 ring-2 ring-green-500/20 dark:border-green-400',
              disabled && 'opacity-50 cursor-not-allowed',
              sizeStyles.trigger
            )}
            onClick={handleTriggerClick}
            onKeyDown={handleTriggerKeyDown}
            onFocus={handleFocus}
            onBlur={handleBlur}
            disabled={disabled}
            aria-expanded={isOpen}
            aria-haspopup="listbox"
            aria-label={ariaLabel || label}
            aria-invalid={hasError}
            aria-required={required}
          >
            <div className="flex-1 min-w-0 flex items-center gap-2">
              {isMulti && showBadges && selectedOptions.length > 0 ? (
                <div className="flex flex-wrap gap-1">
                  {selectedOptions.slice(0, 3).map((opt) => (
                    <Badge
                      key={opt.value}
                      variant="primary"
                      size="sm"
                      className="flex items-center gap-0.5"
                    >
                      {opt.label}
                      <button
                        type="button"
                        className="ml-0.5 rounded-full hover:bg-brand-600/20"
                        onClick={(e) => {
                          e.stopPropagation();
                          removeOption(opt.value);
                        }}
                      >
                        <XMarkIcon className="h-3 w-3" />
                      </button>
                    </Badge>
                  ))}
                  {selectedOptions.length > 3 && (
                    <Badge variant="outline" size="sm">
                      +{selectedOptions.length - 3}
                    </Badge>
                  )}
                </div>
              ) : (
                <span className={cn(
                  'truncate',
                  selectedOptions.length === 0 && 'text-gray-400 dark:text-gray-500'
                )}>
                  {selectedOptions.length > 0 ? selectedOptions[0].label : placeholder}
                </span>
              )}
            </div>

            <div className="flex items-center gap-1 flex-shrink-0">
              {statusStyles.icon}
              {isOpen ? (
                <ChevronUpIcon className="h-4 w-4 text-gray-400" />
              ) : (
                <ChevronDownIcon className="h-4 w-4 text-gray-400" />
              )}
            </div>
          </button>

          {/* Menu */}
          <AnimatePresence>
            {isOpen && !disabled && (
              <motion.div
                initial={{ opacity: 0, y: -10, scale: 0.95 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -10, scale: 0.95 }}
                transition={{ duration: 0.15 }}
                className={cn(
                  'absolute z-50 mt-1 w-full min-w-[200px] overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-lg',
                  placement === 'top' && 'bottom-full mb-1',
                  placement === 'top-start' && 'bottom-full mb-1 left-0',
                  placement === 'top-end' && 'bottom-full mb-1 right-0',
                  placement === 'bottom' && 'top-full mt-1',
                  placement === 'bottom-start' && 'top-full mt-1 left-0',
                  placement === 'bottom-end' && 'top-full mt-1 right-0'
                )}
                style={{
                  maxHeight: 300,
                }}
              >
                {/* Recherche */}
                {searchable && (
                  <div className="sticky top-0 z-10 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-2">
                    <Input
                      ref={searchInputRef}
                      type="text"
                      value={searchValue}
                      onChange={handleSearchChange}
                      placeholder={searchPlaceholder}
                      className="h-8 text-sm"
                      prefix={<MagnifyingGlassIcon className="h-4 w-4 text-gray-400" />}
                      autoFocus
                    />
                  </div>
                )}

                {/* Options */}
                <ScrollArea className="max-h-[250px]">
                  <div className="p-1">
                    {isLoadingOptions ? (
                      <div className="flex items-center justify-center py-8">
                        <ArrowPathIcon className="h-6 w-6 animate-spin text-gray-400" />
                      </div>
                    ) : filteredOptions.length === 0 ? (
                      <div className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">
                        Aucune option trouvée
                      </div>
                    ) : (
                      displayOptions.map((group) => {
                        const groupOptions = group.options;
                        if (groupOptions.length === 0) return null;

                        return (
                          <div key={group.id} className="space-y-0.5">
                            {group.label && renderGroup ? (
                              renderGroup(group)
                            ) : group.label && (
                              <div className="px-3 py-1.5 text-xs font-medium text-gray-500 dark:text-gray-400">
                                {group.label}
                              </div>
                            )}
                            {groupOptions.map((option) => {
                              const isSelected = selectedOptions.some((o) => o.value === option.value);
                              const isHighlighted = filteredOptions.indexOf(option) === highlightedIndex;

                              if (renderOption) {
                                return renderOption(option, isSelected, isHighlighted);
                              }

                              return (
                                <button
                                  key={option.value}
                                  type="button"
                                  className={cn(
                                    'flex w-full cursor-pointer items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors',
                                    isSelected && 'bg-brand-50 dark:bg-brand-900/30 text-brand-700 dark:text-brand-400',
                                    isHighlighted && 'bg-gray-50 dark:bg-gray-800/50',
                                    option.disabled && 'opacity-50 cursor-not-allowed',
                                    option.className
                                  )}
                                  onClick={() => selectOption(option)}
                                  onKeyDown={(e) => handleOptionKeyDown(e, option)}
                                  disabled={option.disabled}
                                  role="option"
                                  aria-selected={isSelected}
                                  aria-disabled={option.disabled}
                                >
                                  {option.icon && (
                                    <span className="flex-shrink-0 text-gray-400">
                                      {option.icon}
                                    </span>
                                  )}
                                  <div className="flex-1 min-w-0">
                                    <div className="font-medium">{option.label}</div>
                                    {option.description && (
                                      <div className="text-xs text-gray-500 dark:text-gray-400">
                                        {option.description}
                                      </div>
                                    )}
                                  </div>
                                  {isSelected && (
                                    <CheckIcon className="h-4 w-4 text-brand-500" />
                                  )}
                                </button>
                              );
                            })}
                          </div>
                        );
                      })
                    )}
                  </div>
                </ScrollArea>
              </motion.div>
            )}
          </AnimatePresence>

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

SelectField.displayName = 'SelectField';

// ============================================================================
// EXPORTS
// ============================================================================

export default SelectField;

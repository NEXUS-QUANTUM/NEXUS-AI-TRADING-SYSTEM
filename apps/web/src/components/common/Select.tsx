// apps/web/src/components/common/Select.tsx
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
  KeyboardEvent,
  FocusEvent,
  Children,
  isValidElement,
  cloneElement,
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
import { Input } from '@/components/common/Input';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Tooltip } from '@/components/common/Tooltip';
import { ScrollArea } from '@/components/common/ScrollArea';
import { Separator } from '@/components/common/Separator';

// ============================================================================
// TYPES
// ============================================================================

export type SelectVariant = 'default' | 'outlined' | 'solid' | 'ghost' | 'minimal' | 'pill';
export type SelectSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
export type SelectColor = 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'neutral' | 'brand';
export type SelectStatus = 'default' | 'success' | 'error' | 'warning' | 'info';
export type SelectPlacement = 'bottom' | 'top' | 'bottom-start' | 'bottom-end' | 'top-start' | 'top-end';

export interface SelectOption {
  /** Valeur de l'option */
  value: string;
  /** Libellé de l'option */
  label: ReactNode;
  /** Description de l'option */
  description?: ReactNode;
  /** Icône de l'option */
  icon?: ReactNode;
  /** Groupe de l'option */
  group?: string;
  /** Désactiver l'option */
  disabled?: boolean;
  /** Statut de l'option */
  status?: SelectStatus;
  /** Données additionnelles */
  data?: any;
  /** Classes additionnelles */
  className?: string;
}

export interface SelectGroup {
  /** Identifiant du groupe */
  id: string;
  /** Libellé du groupe */
  label: string;
  /** Icône du groupe */
  icon?: ReactNode;
  /** Options du groupe */
  options: SelectOption[];
}

export interface SelectProps {
  // --- Contrôle ---
  /** Valeur sélectionnée */
  value?: string | string[];
  /** Valeur par défaut */
  defaultValue?: string | string[];
  /** Callback lors du changement */
  onChange?: (value: string | string[]) => void;
  /** Callback lors de la sélection */
  onSelect?: (option: SelectOption) => void;
  /** Callback lors du blur */
  onBlur?: () => void;
  /** Callback lors du focus */
  onFocus?: () => void;

  // --- Options ---
  /** Options du sélecteur */
  options?: SelectOption[];
  /** Groupes d'options */
  groups?: SelectGroup[];
  /** Options chargées de manière asynchrone */
  loadOptions?: (input: string) => Promise<SelectOption[]>;

  // --- Apparence ---
  /** Variante d'affichage */
  variant?: SelectVariant;
  /** Taille du sélecteur */
  size?: SelectSize;
  /** Couleur du thème */
  color?: SelectColor;
  /** Statut du sélecteur */
  status?: SelectStatus;
  /** Position du menu déroulant */
  placement?: SelectPlacement;
  /** Classes additionnelles */
  className?: string;
  /** Classes pour le conteneur */
  containerClassName?: string;
  /** Classes pour le trigger */
  triggerClassName?: string;
  /** Classes pour le menu */
  menuClassName?: string;
  /** Classes pour les options */
  optionClassName?: string;
  /** Classes pour le label */
  labelClassName?: string;
  /** Classes pour le placeholder */
  placeholderClassName?: string;

  // --- Comportement ---
  /** Mode multi-sélection */
  multi?: boolean;
  /** Recherche dans les options */
  searchable?: boolean;
  /** Placeholder du champ */
  placeholder?: string;
  /** Placeholder de la recherche */
  searchPlaceholder?: string;
  /** Désactiver le sélecteur */
  disabled?: boolean;
  /** Rendre le sélecteur obligatoire */
  required?: boolean;
  /** Chargement en cours */
  isLoading?: boolean;
  /** Message d'erreur */
  error?: string;
  /** Message de succès */
  success?: string;
  /** Message d'information */
  info?: string;
  /** Message d'avertissement */
  warning?: string;
  /** Nombre maximal d'options sélectionnées (multi) */
  maxSelected?: number;
  /** Nombre minimal d'options sélectionnées (multi) */
  minSelected?: number;
  /** Désactiver la fermeture automatique */
  closeOnSelect?: boolean;
  /** Désactiver la fermeture automatique en multi */
  closeOnSelectMulti?: boolean;

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
  renderOption?: (option: SelectOption, isSelected: boolean, isHighlighted: boolean) => ReactNode;
  /** Fonction de rendu personnalisée des groupes */
  renderGroup?: (group: SelectGroup) => ReactNode;
  /** Fonction de rendu personnalisée de la valeur sélectionnée */
  renderValue?: (selected: SelectOption[]) => ReactNode;
  /** Fonction de validation personnalisée */
  validate?: (value: string | string[]) => boolean | string;
  /** Callback de validation */
  onValidate?: (isValid: boolean, value: string | string[]) => void;
  /** Ref du champ */
  inputRef?: React.Ref<HTMLInputElement>;
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

const STATUS_MAP: Record<SelectStatus, { border: string; text: string; icon: ReactNode }> = {
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
// CONTEXT
// ============================================================================

interface SelectContextType {
  value: string | string[];
  isMulti: boolean;
  isOpen: boolean;
  setIsOpen: (open: boolean) => void;
  selectedOptions: SelectOption[];
  highlightedIndex: number;
  setHighlightedIndex: (index: number) => void;
  selectOption: (option: SelectOption) => void;
  removeOption: (value: string) => void;
  toggleOption: (option: SelectOption) => void;
  isOptionSelected: (option: SelectOption) => boolean;
  isOptionDisabled: (option: SelectOption) => boolean;
  isOptionHighlighted: (index: number) => boolean;
  getOptionProps: (option: SelectOption, index: number) => any;
  variant: SelectVariant;
  size: SelectSize;
  color: SelectColor;
  status: SelectStatus;
  disabled: boolean;
  isLoading: boolean;
  searchValue: string;
  setSearchValue: (value: string) => void;
  filteredOptions: SelectOption[];
  menuId: string;
  triggerId: string;
}

const SelectContext = createContext<SelectContextType | null>(null);

export const useSelectContext = () => {
  const context = useContext(SelectContext);
  if (!context) {
    throw new Error('useSelectContext must be used within a Select');
  }
  return context;
};

// ============================================================================
// COMPOSANTS INTERNES
// ============================================================================

// --- OptionItem ---
interface OptionItemProps {
  option: SelectOption;
  index: number;
  className?: string;
}

const OptionItem: React.FC<OptionItemProps> = ({ option, index, className }) => {
  const context = useSelectContext();
  const {
    isMulti,
    isOptionSelected,
    isOptionDisabled,
    isOptionHighlighted,
    selectOption,
    toggleOption,
    size,
    variant,
    optionClassName,
    renderOption,
  } = context;

  const isSelected = isOptionSelected(option);
  const isDisabled = isOptionDisabled(option);
  const isHighlighted = isOptionHighlighted(index);
  const sizeStyles = SIZE_MAP[size] || SIZE_MAP.md;

  const handleClick = () => {
    if (isDisabled) return;
    if (isMulti) {
      toggleOption(option);
    } else {
      selectOption(option);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      handleClick();
    }
  };

  if (renderOption) {
    return renderOption(option, isSelected, isHighlighted);
  }

  const variantStyles = {
    default: cn(
      'hover:bg-gray-100 dark:hover:bg-gray-800',
      isSelected && 'bg-brand-50 dark:bg-brand-900/30 text-brand-700 dark:text-brand-400',
      isHighlighted && 'bg-gray-50 dark:bg-gray-800/50'
    ),
    outlined: cn(
      'hover:bg-gray-50 dark:hover:bg-gray-800',
      isSelected && 'border-brand-500 bg-brand-50 dark:bg-brand-900/30 text-brand-700 dark:text-brand-400',
      isHighlighted && 'border-gray-300 dark:border-gray-600'
    ),
    solid: cn(
      'hover:bg-gray-200 dark:hover:bg-gray-700',
      isSelected && 'bg-brand-500 text-white dark:bg-brand-600',
      isHighlighted && 'bg-gray-200 dark:bg-gray-700'
    ),
    ghost: cn(
      'hover:bg-gray-100 dark:hover:bg-gray-800',
      isSelected && 'bg-brand-50 dark:bg-brand-900/30 text-brand-700 dark:text-brand-400',
      isHighlighted && 'bg-gray-50 dark:bg-gray-800/50'
    ),
    minimal: cn(
      'hover:bg-gray-50 dark:hover:bg-gray-800',
      isSelected && 'border-b-2 border-brand-500 text-brand-700 dark:text-brand-400',
      isHighlighted && 'bg-gray-50 dark:bg-gray-800/50'
    ),
    pill: cn(
      'hover:bg-gray-100 dark:hover:bg-gray-800',
      isSelected && 'bg-brand-50 dark:bg-brand-900/30 text-brand-700 dark:text-brand-400',
      isHighlighted && 'bg-gray-50 dark:bg-gray-800/50'
    ),
  };

  return (
    <div
      className={cn(
        'flex cursor-pointer items-center gap-3 transition-colors',
        sizeStyles.option,
        variantStyles[variant] || variantStyles.default,
        isDisabled && 'opacity-50 cursor-not-allowed',
        optionClassName,
        className
      )}
      onClick={handleClick}
      onKeyDown={handleKeyDown}
      role="option"
      aria-selected={isSelected}
      aria-disabled={isDisabled}
      data-value={option.value}
      tabIndex={isDisabled ? -1 : 0}
    >
      {option.icon && (
        <span className="flex-shrink-0 text-gray-400">
          {option.icon}
        </span>
      )}
      <div className="flex-1 min-w-0">
        <div className={cn('font-medium', isSelected && 'text-brand-700 dark:text-brand-400')}>
          {option.label}
        </div>
        {option.description && (
          <div className="text-sm text-gray-500 dark:text-gray-400">
            {option.description}
          </div>
        )}
      </div>
      {isSelected && (
        <CheckIcon className={cn('flex-shrink-0 text-brand-500', sizeStyles.icon)} />
      )}
    </div>
  );
};

// --- SelectTrigger ---
interface SelectTriggerProps {
  className?: string;
}

const SelectTrigger: React.FC<SelectTriggerProps> = ({ className }) => {
  const context = useSelectContext();
  const {
    isOpen,
    setIsOpen,
    selectedOptions,
    isMulti,
    placeholder,
    disabled,
    isLoading,
    size,
    variant,
    status,
    color,
    error,
    triggerClassName,
    placeholderClassName,
    triggerId,
  } = context;

  const sizeStyles = SIZE_MAP[size] || SIZE_MAP.md;
  const statusStyles = STATUS_MAP[status] || STATUS_MAP.default;
  const colorStyles = COLOR_MAP[color] || COLOR_MAP.brand;
  const variantStyles = VARIANT_MAP[variant] || VARIANT_MAP.default;

  const hasSelected = selectedOptions.length > 0;

  const toggleOpen = (e: React.MouseEvent) => {
    e.stopPropagation();
    if (disabled || isLoading) return;
    setIsOpen(!isOpen);
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if (disabled || isLoading) return;
    if (e.key === ' ' || e.key === 'Enter') {
      e.preventDefault();
      setIsOpen(!isOpen);
    }
  };

  // Rendu des valeurs sélectionnées
  const renderSelectedValues = () => {
    if (!hasSelected) {
      return (
        <span className={cn('text-gray-400 dark:text-gray-500', placeholderClassName)}>
          {placeholder || 'Sélectionner...'}
        </span>
      );
    }

    if (isMulti) {
      return (
        <div className="flex flex-wrap gap-1">
          {selectedOptions.map((option) => (
            <Badge
              key={option.value}
              variant="primary"
              size="sm"
              className="flex items-center gap-1"
            >
              {option.label}
              <button
                className="ml-0.5 rounded-full hover:bg-brand-600/20"
                onClick={(e) => {
                  e.stopPropagation();
                  context.removeOption(option.value);
                }}
                type="button"
              >
                <XMarkIcon className="h-3 w-3" />
              </button>
            </Badge>
          ))}
        </div>
      );
    }

    return (
      <span className="truncate">
        {selectedOptions[0]?.label}
      </span>
    );
  };

  return (
    <div
      id={triggerId}
      className={cn(
        'relative flex cursor-pointer items-center justify-between rounded-lg transition-all focus:outline-none focus:ring-2 focus:ring-offset-2',
        variantStyles,
        statusStyles.border,
        isOpen && `ring-2 ring-${colorStyles.focus} ring-offset-2`,
        disabled && 'opacity-50 cursor-not-allowed',
        isLoading && 'cursor-wait',
        sizeStyles.trigger,
        triggerClassName,
        className
      )}
      onClick={toggleOpen}
      onKeyDown={handleKeyDown}
      role="combobox"
      aria-expanded={isOpen}
      aria-haspopup="listbox"
      aria-controls={context.menuId}
      aria-disabled={disabled}
      aria-invalid={!!error}
      tabIndex={disabled ? -1 : 0}
    >
      <div className="flex-1 min-w-0 flex items-center gap-2">
        {renderSelectedValues()}
      </div>

      <div className="flex items-center gap-1 flex-shrink-0">
        {isLoading && (
          <ArrowPathIcon className="h-4 w-4 animate-spin text-gray-400" />
        )}
        {statusStyles.icon}
        {isOpen ? (
          <ChevronUpIcon className="h-4 w-4 text-gray-400" />
        ) : (
          <ChevronDownIcon className="h-4 w-4 text-gray-400" />
        )}
      </div>
    </div>
  );
};

// --- SelectMenu ---
const SelectMenu: React.FC = () => {
  const context = useSelectContext();
  const {
    isOpen,
    setIsOpen,
    filteredOptions,
    highlightedIndex,
    setHighlightedIndex,
    selectOption,
    isMulti,
    size,
    menuClassName,
    menuId,
    isLoading,
    searchValue,
    setSearchValue,
    searchable,
    searchPlaceholder,
    closeOnSelect,
    closeOnSelectMulti,
    disabled,
  } = context;

  const menuRef = useRef<HTMLDivElement>(null);
  const optionRefs = useRef<(HTMLDivElement | null)[]>([]);

  // Gestion du clavier
  const handleKeyDown = useCallback((e: KeyboardEvent<HTMLDivElement>) => {
    const totalItems = filteredOptions.length;
    if (totalItems === 0) return;

    let newIndex = highlightedIndex;

    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault();
        newIndex = (highlightedIndex + 1) % totalItems;
        break;
      case 'ArrowUp':
        e.preventDefault();
        newIndex = (highlightedIndex - 1 + totalItems) % totalItems;
        break;
      case ' ':
      case 'Enter':
        e.preventDefault();
        if (highlightedIndex >= 0 && highlightedIndex < totalItems) {
          const option = filteredOptions[highlightedIndex];
          if (!option.disabled) {
            selectOption(option);
            if (!isMulti && closeOnSelect) {
              setIsOpen(false);
            }
          }
        }
        break;
      case 'Escape':
        e.preventDefault();
        setIsOpen(false);
        break;
      default:
        // Recherche par caractère
        if (e.key.length === 1 && !searchable) {
          const char = e.key.toLowerCase();
          const foundIndex = filteredOptions.findIndex(
            (opt, idx) => 
              idx > highlightedIndex &&
              String(opt.label).toLowerCase().startsWith(char)
          );
          if (foundIndex !== -1) {
            setHighlightedIndex(foundIndex);
          }
        }
        break;
    }

    if (newIndex !== highlightedIndex) {
      setHighlightedIndex(newIndex);
      // Scroll vers l'élément
      const element = optionRefs.current[newIndex];
      if (element) {
        element.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [filteredOptions, highlightedIndex, setHighlightedIndex, selectOption, isMulti, closeOnSelect, setIsOpen, searchable]);

  // Fermeture au clic extérieur
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      const target = e.target as Node;
      if (
        menuRef.current &&
        !menuRef.current.contains(target) &&
        !document.getElementById(context.triggerId)?.contains(target)
      ) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside);
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen, setIsOpen, context.triggerId]);

  // Reset de la recherche à l'ouverture
  useEffect(() => {
    if (!isOpen && searchable) {
      setSearchValue('');
    }
  }, [isOpen, searchable, setSearchValue]);

  if (!isOpen) return null;

  return (
    <div
      ref={menuRef}
      id={menuId}
      className={cn(
        'absolute z-50 mt-1 w-full min-w-[200px] overflow-hidden rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-lg',
        menuClassName
      )}
      role="listbox"
      aria-multiselectable={isMulti}
      onKeyDown={handleKeyDown}
    >
      {/* Recherche */}
      {searchable && (
        <div className="sticky top-0 z-10 border-b border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-2">
          <div className="relative">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-gray-400" />
            <Input
              type="text"
              value={searchValue}
              onChange={(e) => setSearchValue(e.target.value)}
              placeholder={searchPlaceholder || 'Rechercher...'}
              className="pl-9"
              size={size === 'xs' || size === 'sm' ? 'sm' : 'md'}
              autoFocus
              onClick={(e) => e.stopPropagation()}
            />
          </div>
        </div>
      )}

      {/* Options */}
      <ScrollArea className="max-h-60">
        <div className="p-1">
          {isLoading ? (
            <div className="flex items-center justify-center py-8">
              <ArrowPathIcon className="h-6 w-6 animate-spin text-gray-400" />
            </div>
          ) : filteredOptions.length === 0 ? (
            <div className="py-8 text-center text-sm text-gray-500 dark:text-gray-400">
              Aucune option trouvée
            </div>
          ) : (
            filteredOptions.map((option, index) => (
              <OptionItem
                key={option.value}
                option={option}
                index={index}
                ref={(el) => (optionRefs.current[index] = el)}
              />
            ))
          )}
        </div>
      </ScrollArea>
    </div>
  );
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const Select = forwardRef<HTMLDivElement, SelectProps>(
  (props, ref) => {
    const {
      // Contrôle
      value: externalValue,
      defaultValue,
      onChange,
      onSelect,
      onBlur,
      onFocus,

      // Options
      options = [],
      groups = [],
      loadOptions,

      // Apparence
      variant = 'default',
      size = 'md',
      color = 'brand',
      status = 'default',
      placement = 'bottom',
      className,
      containerClassName,
      triggerClassName,
      menuClassName,
      optionClassName,
      labelClassName,
      placeholderClassName,

      // Comportement
      multi = false,
      searchable = false,
      placeholder = 'Sélectionner...',
      searchPlaceholder = 'Rechercher...',
      disabled = false,
      required = false,
      isLoading = false,
      error,
      success,
      info,
      warning,
      maxSelected,
      minSelected,
      closeOnSelect = true,
      closeOnSelectMulti = false,

      // Accessibilité
      ariaLabel,
      ariaDescribedby,
      id,
      name,

      // Avancé
      renderOption,
      renderGroup,
      renderValue,
      validate,
      onValidate,
      inputRef,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const containerRef = useRef<HTMLDivElement>(null);
    const triggerRef = useRef<HTMLDivElement>(null);
    const menuRef = useRef<HTMLDivElement>(null);
    const inputRefLocal = useRef<HTMLInputElement>(null);
    const uniqueId = useId();
    const selectId = id || `nexus-select-${uniqueId}`;
    const triggerId = `${selectId}-trigger`;
    const menuId = `${selectId}-menu`;

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [isOpen, setIsOpen] = useState(false);
    const [internalValue, setInternalValue] = useState<string | string[]>(
      defaultValue || (multi ? [] : '')
    );
    const [highlightedIndex, setHighlightedIndex] = useState(0);
    const [searchValue, setSearchValue] = useState('');
    const [filteredOptions, setFilteredOptions] = useState<SelectOption[]>([]);
    const [loadedOptions, setLoadedOptions] = useState<SelectOption[]>([]);
    const [isLoadingOptions, setIsLoadingOptions] = useState(false);

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

    // ========================================================================
    // FILTRAGE DES OPTIONS
    // ========================================================================

    useEffect(() => {
      const filterOptions = (opts: SelectOption[]) => {
        if (!searchValue) return opts;
        const query = searchValue.toLowerCase();
        return opts.filter((opt) => {
          const label = String(opt.label).toLowerCase();
          const desc = opt.description ? String(opt.description).toLowerCase() : '';
          return label.includes(query) || desc.includes(query);
        });
      };

      // Filtrer en conservant les groupes
      if (groups.length > 0) {
        const filteredGroups = groups
          .map((group) => ({
            ...group,
            options: filterOptions(group.options),
          }))
          .filter((group) => group.options.length > 0);
        
        const flatFiltered = filteredGroups.flatMap((g) => g.options);
        setFilteredOptions(flatFiltered);
      } else {
        setFilteredOptions(filterOptions(allOptions));
      }
    }, [searchValue, allOptions, groups]);

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
          console.error('Erreur de chargement des options:', error);
        } finally {
          setIsLoadingOptions(false);
        }
      };

      const timer = setTimeout(load, 300);
      return () => clearTimeout(timer);
    }, [loadOptions, isOpen, searchValue]);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    useEffect(() => {
      if (!validate) return;

      const result = validate(value);
      const isValid = typeof result === 'string' ? false : result;
      if (onValidate) onValidate(isValid, value);
    }, [value, validate, onValidate]);

    // ========================================================================
    // SÉLECTION
    // ========================================================================

    const selectOption = useCallback((option: SelectOption) => {
      if (option.disabled) return;

      if (isMulti) {
        const currentValues = Array.isArray(value) ? value : [];
        if (maxSelected && currentValues.length >= maxSelected) return;
        
        const newValues = currentValues.includes(option.value)
          ? currentValues.filter((v) => v !== option.value)
          : [...currentValues, option.value];
        
        if (isControlled) {
          if (onChange) onChange(newValues);
        } else {
          setInternalValue(newValues);
          if (onChange) onChange(newValues);
        }
        onSelect?.(option);
      } else {
        if (isControlled) {
          if (onChange) onChange(option.value);
        } else {
          setInternalValue(option.value);
          if (onChange) onChange(option.value);
        }
        onSelect?.(option);
        
        if (closeOnSelect) {
          setIsOpen(false);
        }
      }
    }, [isMulti, value, isControlled, onChange, onSelect, maxSelected, closeOnSelect]);

    const removeOption = useCallback((optionValue: string) => {
      if (!isMulti) return;
      
      const currentValues = Array.isArray(value) ? value : [];
      const newValues = currentValues.filter((v) => v !== optionValue);
      
      if (isControlled) {
        if (onChange) onChange(newValues);
      } else {
        setInternalValue(newValues);
        if (onChange) onChange(newValues);
      }
    }, [isMulti, value, isControlled, onChange]);

    const toggleOption = useCallback((option: SelectOption) => {
      if (option.disabled) return;
      
      if (isMulti) {
        const currentValues = Array.isArray(value) ? value : [];
        if (currentValues.includes(option.value)) {
          removeOption(option.value);
        } else {
          selectOption(option);
        }
      } else {
        selectOption(option);
      }
    }, [isMulti, value, selectOption, removeOption]);

    const isOptionSelected = useCallback((option: SelectOption) => {
      if (isMulti) {
        return Array.isArray(value) && value.includes(option.value);
      }
      return value === option.value;
    }, [isMulti, value]);

    const isOptionDisabled = useCallback((option: SelectOption) => {
      if (option.disabled) return true;
      if (disabled) return true;
      
      if (isMulti && maxSelected) {
        const currentValues = Array.isArray(value) ? value : [];
        if (currentValues.length >= maxSelected && !currentValues.includes(option.value)) {
          return true;
        }
      }
      return false;
    }, [disabled, isMulti, maxSelected, value]);

    const isOptionHighlighted = useCallback((index: number) => {
      return index === highlightedIndex;
    }, [highlightedIndex]);

    // ========================================================================
    // CONTEXT
    // ========================================================================

    const contextValue = useMemo<SelectContextType>(
      () => ({
        value,
        isMulti,
        isOpen,
        setIsOpen,
        selectedOptions,
        highlightedIndex,
        setHighlightedIndex,
        selectOption,
        removeOption,
        toggleOption,
        isOptionSelected,
        isOptionDisabled,
        isOptionHighlighted,
        getOptionProps: (option: SelectOption, index: number) => ({
          onClick: () => toggleOption(option),
          'aria-selected': isOptionSelected(option),
          'aria-disabled': isOptionDisabled(option),
        }),
        variant,
        size,
        color,
        status,
        disabled,
        isLoading: isLoading || isLoadingOptions,
        searchValue,
        setSearchValue,
        filteredOptions,
        menuId,
        triggerId,
        // Rendu personnalisé
        renderOption,
        placeholder,
        error,
        triggerClassName,
        placeholderClassName,
        menuClassName,
        optionClassName,
        labelClassName,
        closeOnSelect,
        closeOnSelectMulti,
      }),
      [
        value,
        isMulti,
        isOpen,
        setIsOpen,
        selectedOptions,
        highlightedIndex,
        setHighlightedIndex,
        selectOption,
        removeOption,
        toggleOption,
        isOptionSelected,
        isOptionDisabled,
        isOptionHighlighted,
        variant,
        size,
        color,
        status,
        disabled,
        isLoading,
        isLoadingOptions,
        searchValue,
        setSearchValue,
        filteredOptions,
        menuId,
        triggerId,
        renderOption,
        placeholder,
        error,
        triggerClassName,
        placeholderClassName,
        menuClassName,
        optionClassName,
        labelClassName,
        closeOnSelect,
        closeOnSelectMulti,
      ]
    );

    // ========================================================================
    // RENDU
    // ========================================================================

    const statusMessages = error || success || warning || info;
    const statusType = error ? 'error' : success ? 'success' : warning ? 'warning' : info ? 'info' : null;

    return (
      <SelectContext.Provider value={contextValue}>
        <div
          ref={(node) => {
            if (typeof ref === 'function') ref(node);
            else if (ref) ref.current = node;
            containerRef.current = node;
          }}
          id={selectId}
          className={cn('relative', containerClassName)}
          aria-label={ariaLabel}
          aria-describedby={ariaDescribedby}
        >
          {/* Champ caché pour les formulaires */}
          {name && (
            <input
              ref={inputRef || inputRefLocal}
              type="hidden"
              name={name}
              value={Array.isArray(value) ? value.join(',') : value}
              required={required}
            />
          )}

          {/* Trigger */}
          <SelectTrigger className={className} />

          {/* Menu déroulant */}
          <div
            className={cn(
              'absolute left-0 w-full min-w-[200px]',
              placement === 'top' && 'bottom-full mb-1',
              placement === 'top-start' && 'bottom-full mb-1 left-0',
              placement === 'top-end' && 'bottom-full mb-1 right-0',
              placement === 'bottom' && 'top-full mt-1',
              placement === 'bottom-start' && 'top-full mt-1 left-0',
              placement === 'bottom-end' && 'top-full mt-1 right-0'
            )}
          >
            <SelectMenu />
          </div>

          {/* Message de statut */}
          {statusMessages && (
            <div className="mt-1 flex items-center gap-1 text-sm">
              {statusType && STATUS_MAP[statusType as SelectStatus]?.icon}
              <span
                className={cn(
                  statusType === 'error' && 'text-red-600 dark:text-red-400',
                  statusType === 'success' && 'text-green-600 dark:text-green-400',
                  statusType === 'warning' && 'text-yellow-600 dark:text-yellow-400',
                  statusType === 'info' && 'text-blue-600 dark:text-blue-400'
                )}
              >
                {statusMessages}
              </span>
            </div>
          )}

          {/* Compteur de sélection */}
          {isMulti && selectedOptions.length > 0 && (
            <div className="mt-1 text-xs text-gray-500 dark:text-gray-400">
              {selectedOptions.length} sélectionné{selectedOptions.length > 1 ? 's' : ''}
              {maxSelected && ` / ${maxSelected} max`}
            </div>
          )}
        </div>
      </SelectContext.Provider>
    );
  }
);

Select.displayName = 'Select';

// ============================================================================
// SOUS-COMPOSANTS
// ============================================================================

// --- Select.Option ---
interface SelectOptionProps {
  value: string;
  children: ReactNode;
  className?: string;
  disabled?: boolean;
}

export const SelectOption: React.FC<SelectOptionProps> = ({
  value,
  children,
  className,
  disabled = false,
}) => {
  const context = useSelectContext();
  const isSelected = context.isOptionSelected({ value, label: children } as SelectOption);
  const isDisabled = disabled || context.disabled;

  return (
    <div
      className={cn(
        'flex cursor-pointer items-center gap-2 px-3 py-2 transition-colors',
        isSelected && 'bg-brand-50 dark:bg-brand-900/30',
        isDisabled && 'opacity-50 cursor-not-allowed',
        className
      )}
      onClick={() => {
        if (!isDisabled) {
          context.selectOption({ value, label: children } as SelectOption);
        }
      }}
      role="option"
      aria-selected={isSelected}
      aria-disabled={isDisabled}
    >
      <span className="flex-1">{children}</span>
      {isSelected && <CheckIcon className="h-4 w-4 text-brand-500" />}
    </div>
  );
};

// ============================================================================
// HOOKS
// ============================================================================

export const useSelect = (defaultValue?: string | string[]) => {
  const [value, setValue] = useState<string | string[]>(defaultValue || '');

  const onChange = useCallback((newValue: string | string[]) => {
    setValue(newValue);
  }, []);

  const select = useCallback((optionValue: string) => {
    if (Array.isArray(value)) {
      setValue([...value, optionValue]);
    } else {
      setValue(optionValue);
    }
  }, [value]);

  const deselect = useCallback((optionValue: string) => {
    if (Array.isArray(value)) {
      setValue(value.filter((v) => v !== optionValue));
    } else {
      setValue('');
    }
  }, [value]);

  const toggle = useCallback((optionValue: string) => {
    if (Array.isArray(value)) {
      if (value.includes(optionValue)) {
        setValue(value.filter((v) => v !== optionValue));
      } else {
        setValue([...value, optionValue]);
      }
    } else {
      setValue(value === optionValue ? '' : optionValue);
    }
  }, [value]);

  const clear = useCallback(() => {
    setValue(Array.isArray(value) ? [] : '');
  }, [value]);

  const isSelected = useCallback((optionValue: string) => {
    if (Array.isArray(value)) {
      return value.includes(optionValue);
    }
    return value === optionValue;
  }, [value]);

  return {
    value,
    setValue,
    onChange,
    select,
    deselect,
    toggle,
    clear,
    isSelected,
    isMulti: Array.isArray(value),
  };
};

// ============================================================================
// EXPORTS
// ============================================================================

export default Object.assign(Select, {
  Option: SelectOption,
});

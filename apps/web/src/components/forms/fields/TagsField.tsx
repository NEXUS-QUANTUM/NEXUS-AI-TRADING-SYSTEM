// apps/web/src/components/forms/fields/TagsField.tsx
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
  TagIcon,
  XMarkIcon,
  PlusIcon,
  CheckIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ExclamationCircleIcon,
  CheckCircleIcon,
  MagnifyingGlassIcon,
  ArrowPathIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline';
import { Label } from '@/components/common/Label';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Tooltip } from '@/components/common/Tooltip';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type Tag = {
  /** Identifiant unique du tag */
  id: string;
  /** Libellé du tag */
  label: string;
  /** Couleur du tag */
  color?: string;
  /** Données additionnelles */
  data?: any;
};

export type TagVariant = 'default' | 'outlined' | 'solid' | 'rounded' | 'pill' | 'minimal';
export type TagSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl';
export type TagColor = 'default' | 'primary' | 'success' | 'warning' | 'danger' | 'info' | 'brand' | 'neutral';
export type TagSource = 'input' | 'suggestion' | 'external' | 'auto';

export interface TagsFieldProps {
  // --- Contrôle ---
  /** Valeur du champ (tags) */
  value?: Tag[] | null;
  /** Valeur par défaut */
  defaultValue?: Tag[] | null;
  /** Callback de changement */
  onChange?: (tags: Tag[] | null) => void;
  /** Callback de blur */
  onBlur?: () => void;
  /** Callback de focus */
  onFocus?: () => void;
  /** Callback de validation */
  onValidate?: (valid: boolean, tags: Tag[] | null) => void;

  // --- Options ---
  /** Suggestions de tags */
  suggestions?: Tag[];
  /** Charger des suggestions de manière asynchrone */
  loadSuggestions?: (input: string) => Promise<Tag[]>;

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
  variant?: TagVariant;
  /** Taille des tags */
  size?: TagSize;
  /** Couleur des tags */
  color?: TagColor;
  /** Afficher le compteur */
  showCounter?: boolean;
  /** Afficher les suggestions */
  showSuggestions?: boolean;
  /** Afficher l'icône de validation */
  showValidationIcon?: boolean;

  // --- Comportement ---
  /** Désactiver le champ */
  disabled?: boolean;
  /** Rendre le champ obligatoire */
  required?: boolean;
  /** Nombre maximum de tags */
  maxTags?: number;
  /** Nombre minimum de tags */
  minTags?: number;
  /** Longueur maximale d'un tag */
  maxTagLength?: number;
  /** Longueur minimale d'un tag */
  minTagLength?: number;
  /** Séparateur pour l'ajout rapide */
  separator?: string;
  /** Désactiver les doublons */
  allowDuplicates?: boolean;
  /** Désactiver les tags vides */
  allowEmpty?: boolean;
  /** Désactiver la validation en temps réel */
  disableRealtimeValidation?: boolean;
  /** Validation personnalisée */
  validateTags?: (tags: Tag[] | null) => boolean | string;
  /** Validation personnalisée d'un tag */
  validateTag?: (tag: string) => boolean | string;

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
  customFormat?: (tag: string) => string;
  /** Fonction de parsing personnalisée */
  customParse?: (tag: string) => Tag | null;
  /** Ref */
  inputRef?: React.Ref<HTMLInputElement>;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const TAG_COLORS: Record<TagColor, { bg: string; text: string; border: string; hover: string }> = {
  default: {
    bg: 'bg-gray-100 dark:bg-gray-800',
    text: 'text-gray-700 dark:text-gray-300',
    border: 'border-gray-200 dark:border-gray-700',
    hover: 'hover:bg-gray-200 dark:hover:bg-gray-700',
  },
  primary: {
    bg: 'bg-brand-100 dark:bg-brand-900/30',
    text: 'text-brand-700 dark:text-brand-400',
    border: 'border-brand-200 dark:border-brand-800',
    hover: 'hover:bg-brand-200 dark:hover:bg-brand-900/40',
  },
  success: {
    bg: 'bg-green-100 dark:bg-green-900/30',
    text: 'text-green-700 dark:text-green-400',
    border: 'border-green-200 dark:border-green-800',
    hover: 'hover:bg-green-200 dark:hover:bg-green-900/40',
  },
  warning: {
    bg: 'bg-yellow-100 dark:bg-yellow-900/30',
    text: 'text-yellow-700 dark:text-yellow-400',
    border: 'border-yellow-200 dark:border-yellow-800',
    hover: 'hover:bg-yellow-200 dark:hover:bg-yellow-900/40',
  },
  danger: {
    bg: 'bg-red-100 dark:bg-red-900/30',
    text: 'text-red-700 dark:text-red-400',
    border: 'border-red-200 dark:border-red-800',
    hover: 'hover:bg-red-200 dark:hover:bg-red-900/40',
  },
  info: {
    bg: 'bg-blue-100 dark:bg-blue-900/30',
    text: 'text-blue-700 dark:text-blue-400',
    border: 'border-blue-200 dark:border-blue-800',
    hover: 'hover:bg-blue-200 dark:hover:bg-blue-900/40',
  },
  brand: {
    bg: 'bg-brand-100 dark:bg-brand-900/30',
    text: 'text-brand-700 dark:text-brand-400',
    border: 'border-brand-200 dark:border-brand-800',
    hover: 'hover:bg-brand-200 dark:hover:bg-brand-900/40',
  },
  neutral: {
    bg: 'bg-gray-100 dark:bg-gray-800',
    text: 'text-gray-700 dark:text-gray-300',
    border: 'border-gray-200 dark:border-gray-700',
    hover: 'hover:bg-gray-200 dark:hover:bg-gray-700',
  },
};

const SIZE_MAP: Record<TagSize, { tag: string; input: string; icon: string }> = {
  xs: {
    tag: 'text-xs px-1.5 py-0.5',
    input: 'h-7 text-xs',
    icon: 'h-2.5 w-2.5',
  },
  sm: {
    tag: 'text-sm px-2 py-0.5',
    input: 'h-8 text-sm',
    icon: 'h-3 w-3',
  },
  md: {
    tag: 'text-sm px-2.5 py-1',
    input: 'h-10 text-sm',
    icon: 'h-3.5 w-3.5',
  },
  lg: {
    tag: 'text-base px-3 py-1.5',
    input: 'h-12 text-base',
    icon: 'h-4 w-4',
  },
  xl: {
    tag: 'text-lg px-4 py-2',
    input: 'h-14 text-lg',
    icon: 'h-5 w-5',
  },
};

const VARIANT_MAP: Record<TagVariant, string> = {
  default: 'rounded-md border',
  outlined: 'rounded-md border-2',
  solid: 'rounded-md border-0',
  rounded: 'rounded-full border',
  pill: 'rounded-full border',
  minimal: 'rounded-md border-0 bg-transparent',
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const TagsField = forwardRef<HTMLDivElement, TagsFieldProps>(
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
      suggestions: externalSuggestions = [],
      loadSuggestions,

      // Apparence
      label,
      placeholder = 'Ajouter un tag...',
      description,
      error,
      success,
      info,
      variant = 'default',
      size = 'md',
      color = 'brand',
      showCounter = true,
      showSuggestions = true,
      showValidationIcon = true,

      // Comportement
      disabled = false,
      required = false,
      maxTags,
      minTags,
      maxTagLength = 50,
      minTagLength = 1,
      separator = ',',
      allowDuplicates = false,
      allowEmpty = false,
      disableRealtimeValidation = false,
      validateTags: customValidateTags,
      validateTag: customValidateTag,

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
    const prevValueRef = useRef<Tag[] | null>(null);

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalValue, setInternalValue] = useState<Tag[] | null>(
      defaultValue || []
    );
    const [inputValue, setInputValue] = useState('');
    const [isFocused, setIsFocused] = useState(false);
    const [isValid, setIsValid] = useState(true);
    const [validationMessage, setValidationMessage] = useState<string>('');
    const [suggestions, setSuggestions] = useState<Tag[]>(externalSuggestions);
    const [showSuggestionsList, setShowSuggestionsList] = useState(false);
    const [isLoadingSuggestions, setIsLoadingSuggestions] = useState(false);
    const [filteredSuggestions, setFilteredSuggestions] = useState<Tag[]>([]);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined ? externalValue : internalValue;
    const isControlled = externalValue !== undefined;
    const tags = value || [];
    const tagCount = tags.length;

    const colorStyles = TAG_COLORS[color] || TAG_COLORS.brand;
    const sizeStyles = SIZE_MAP[size] || SIZE_MAP.md;
    const variantStyles = VARIANT_MAP[variant] || VARIANT_MAP.default;

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validateTagsList = useCallback((tagList: Tag[] | null): { valid: boolean; message: string } => {
      if (customValidateTags) {
        const result = customValidateTags(tagList);
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        return { valid: true, message: '' };
      }

      if (!tagList || tagList.length === 0) {
        if (required) {
          return { valid: false, message: 'Au moins un tag est requis' };
        }
        return { valid: true, message: '' };
      }

      if (minTags && tagList.length < minTags) {
        return { valid: false, message: `Minimum ${minTags} tag${minTags > 1 ? 's' : ''} requis` };
      }

      if (maxTags && tagList.length > maxTags) {
        return { valid: false, message: `Maximum ${maxTags} tag${maxTags > 1 ? 's' : ''} autorisé${maxTags > 1 ? 's' : ''}` };
      }

      // Vérifier les doublons
      if (!allowDuplicates) {
        const labels = tagList.map(t => t.label.toLowerCase());
        const uniqueLabels = new Set(labels);
        if (labels.length !== uniqueLabels.size) {
          return { valid: false, message: 'Les tags en double ne sont pas autorisés' };
        }
      }

      return { valid: true, message: '' };
    }, [customValidateTags, required, minTags, maxTags, allowDuplicates]);

    const validateSingleTag = useCallback((tag: string): { valid: boolean; message: string } => {
      if (customValidateTag) {
        const result = customValidateTag(tag);
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        return { valid: true, message: '' };
      }

      const trimmed = tag.trim();
      if (!trimmed) {
        if (!allowEmpty) {
          return { valid: false, message: 'Le tag ne peut pas être vide' };
        }
        return { valid: true, message: '' };
      }

      if (trimmed.length < minTagLength) {
        return { valid: false, message: `Le tag doit contenir au moins ${minTagLength} caractère${minTagLength > 1 ? 's' : ''}` };
      }

      if (trimmed.length > maxTagLength) {
        return { valid: false, message: `Le tag ne doit pas dépasser ${maxTagLength} caractères` };
      }

      // Vérifier les doublons
      if (!allowDuplicates) {
        const exists = tags.some(t => t.label.toLowerCase() === trimmed.toLowerCase());
        if (exists) {
          return { valid: false, message: 'Ce tag existe déjà' };
        }
      }

      return { valid: true, message: '' };
    }, [customValidateTag, allowEmpty, minTagLength, maxTagLength, allowDuplicates, tags]);

    // ========================================================================
    // GÉNÉRATION D'ID
    // ========================================================================

    const generateId = useCallback(() => {
      return `tag-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    }, []);

    // ========================================================================
    // CRÉATION DE TAG
    // ========================================================================

    const createTag = useCallback((label: string): Tag => {
      const trimmed = label.trim();
      return {
        id: generateId(),
        label: customFormat ? customFormat(trimmed) : trimmed,
        color: color,
      };
    }, [generateId, customFormat, color]);

    // ========================================================================
    // AJOUT DE TAG
    // ========================================================================

    const addTag = useCallback((tag: string | Tag) => {
      let newTag: Tag;

      if (typeof tag === 'string') {
        const validation = validateSingleTag(tag);
        if (!validation.valid) {
          toast({
            title: 'Erreur de validation',
            description: validation.message,
            variant: 'destructive',
          });
          return;
        }
        newTag = createTag(tag);
      } else {
        newTag = tag;
      }

      // Vérifier les doublons
      if (!allowDuplicates) {
        const exists = tags.some(t => t.label.toLowerCase() === newTag.label.toLowerCase());
        if (exists) {
          toast({
            title: 'Tag en double',
            description: 'Ce tag existe déjà',
            variant: 'default',
          });
          return;
        }
      }

      // Vérifier la limite maximale
      if (maxTags && tags.length >= maxTags) {
        toast({
          title: 'Limite atteinte',
          description: `Maximum ${maxTags} tag${maxTags > 1 ? 's' : ''} autorisé${maxTags > 1 ? 's' : ''}`,
          variant: 'destructive',
        });
        return;
      }

      const newTags = [...tags, newTag];
      const validation = validateTagsList(newTags);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);

      if (!disableRealtimeValidation && onValidate) {
        onValidate(validation.valid, newTags);
      }

      if (isControlled) {
        if (onChange) onChange(newTags);
      } else {
        setInternalValue(newTags);
        if (onChange) onChange(newTags);
      }

      setInputValue('');
      setShowSuggestionsList(false);

      if (debug) {
        console.log('TagsField addTag:', { newTag, tags: newTags });
      }
    }, [
      validateSingleTag,
      createTag,
      allowDuplicates,
      tags,
      maxTags,
      validateTagsList,
      isControlled,
      onChange,
      onValidate,
      disableRealtimeValidation,
      debug,
      toast,
    ]);

    // ========================================================================
    // SUPPRESSION DE TAG
    // ========================================================================

    const removeTag = useCallback((tagId: string) => {
      const newTags = tags.filter(t => t.id !== tagId);
      const validation = validateTagsList(newTags);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);

      if (!disableRealtimeValidation && onValidate) {
        onValidate(validation.valid, newTags);
      }

      if (isControlled) {
        if (onChange) onChange(newTags);
      } else {
        setInternalValue(newTags);
        if (onChange) onChange(newTags);
      }

      if (debug) {
        console.log('TagsField removeTag:', { tagId, tags: newTags });
      }
    }, [
      tags,
      validateTagsList,
      isControlled,
      onChange,
      onValidate,
      disableRealtimeValidation,
      debug,
    ]);

    // ========================================================================
    // GESTIONNAIRES D'ÉVÉNEMENTS
    // ========================================================================

    const handleInputChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
      const value = e.target.value;
      setInputValue(value);

      // Détecter le séparateur
      if (separator && value.includes(separator)) {
        const parts = value.split(separator);
        const lastPart = parts.pop() || '';
        const newTags = parts.filter(p => p.trim());
        newTags.forEach(tag => addTag(tag.trim()));
        setInputValue(lastPart);
        return;
      }

      // Suggestions
      if (showSuggestions && value.length > 0) {
        const filtered = suggestions.filter(s => 
          s.label.toLowerCase().includes(value.toLowerCase())
        );
        setFilteredSuggestions(filtered.slice(0, 5));
        setShowSuggestionsList(filtered.length > 0);
      } else {
        setShowSuggestionsList(false);
      }

      // Chargement asynchrone
      if (loadSuggestions && value.length > 1) {
        const timer = setTimeout(async () => {
          setIsLoadingSuggestions(true);
          try {
            const results = await loadSuggestions(value);
            setFilteredSuggestions(results.slice(0, 5));
            setShowSuggestionsList(results.length > 0);
          } catch (error) {
            console.error('Erreur de chargement:', error);
          } finally {
            setIsLoadingSuggestions(false);
          }
        }, 300);
        return () => clearTimeout(timer);
      }
    }, [separator, addTag, showSuggestions, suggestions, loadSuggestions]);

    const handleInputKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        if (inputValue.trim()) {
          addTag(inputValue.trim());
        }
      } else if (e.key === 'Backspace' && !inputValue && tags.length > 0) {
        e.preventDefault();
        const lastTag = tags[tags.length - 1];
        if (lastTag) removeTag(lastTag.id);
      } else if (e.key === 'Escape') {
        e.preventDefault();
        setShowSuggestionsList(false);
        inputRefInternal.current?.blur();
      }
    }, [inputValue, addTag, tags, removeTag]);

    const handleInputFocus = useCallback(() => {
      setIsFocused(true);
      if (onFocus) onFocus();
    }, [onFocus]);

    const handleInputBlur = useCallback(() => {
      setIsFocused(false);
      if (inputValue.trim()) {
        addTag(inputValue.trim());
      }
      setTimeout(() => setShowSuggestionsList(false), 200);
      if (onBlur) onBlur();
    }, [inputValue, addTag, onBlur]);

    // ========================================================================
    // SYNC AVEC LA VALEUR EXTERNE
    // ========================================================================

    useEffect(() => {
      if (externalValue !== undefined && JSON.stringify(externalValue) !== JSON.stringify(prevValueRef.current)) {
        prevValueRef.current = externalValue;
        const validation = validateTagsList(externalValue);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
      }
    }, [externalValue, validateTagsList]);

    // ========================================================================
    // INITIALISATION
    // ========================================================================

    useEffect(() => {
      if (defaultValue !== undefined && !isControlled) {
        const validation = validateTagsList(defaultValue);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
      }
    }, [defaultValue, isControlled, validateTagsList]);

    // ========================================================================
    // IMPERATIVE HANDLE
    // ========================================================================

    useImperativeHandle(ref, () => ({
      focus: () => inputRefInternal.current?.focus(),
      blur: () => inputRefInternal.current?.blur(),
      getValue: () => value,
      setValue: (tags: Tag[] | null) => {
        if (isControlled) {
          if (onChange) onChange(tags);
        } else {
          setInternalValue(tags);
          if (onChange) onChange(tags);
        }
      },
      addTag: (tag: string | Tag) => addTag(tag),
      removeTag: (tagId: string) => removeTag(tagId),
      clear: () => {
        if (isControlled) {
          if (onChange) onChange([]);
        } else {
          setInternalValue([]);
          if (onChange) onChange([]);
        }
      },
      validate: () => {
        const validation = validateTagsList(value);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        return validation.valid;
      },
    } as any));

    // ========================================================================
    // RENDU
    // ========================================================================

    const hasError = !!error || !isValid || (required && tagCount === 0);
    const isSuccess = !hasError && success && tagCount > 0;

    return (
      <div ref={containerRef} className="relative space-y-1.5" id={id}>
        {/* Label */}
        {label && (
          <div className="flex items-center justify-between">
            <Label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {label}
              {required && <span className="ml-1 text-red-500">*</span>}
            </Label>
            {showCounter && (
              <Badge variant="outline" size="sm">
                {tagCount} {maxTags && `/ ${maxTags}`}
              </Badge>
            )}
          </div>
        )}

        {/* Description */}
        {description && (
          <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
        )}

        {/* Tags + Input */}
        <div className={cn(
          'relative flex flex-wrap items-center gap-1.5 rounded-lg border p-2 transition-all',
          hasError 
            ? 'border-red-500 ring-2 ring-red-500/20 dark:border-red-400' 
            : isSuccess && !disabled
            ? 'border-green-500 ring-2 ring-green-500/20 dark:border-green-400'
            : isFocused
            ? 'border-brand-500 ring-2 ring-brand-500/20 dark:border-brand-400'
            : 'border-gray-300 dark:border-gray-600',
          disabled && 'opacity-50 cursor-not-allowed bg-gray-50 dark:bg-gray-800/50',
          variantStyles
        )}>
          {/* Tags existants */}
          {tags.map((tag) => (
            <motion.div
              key={tag.id}
              initial={{ scale: 0 }}
              animate={{ scale: 1 }}
              exit={{ scale: 0 }}
              className={cn(
                'flex items-center gap-0.5 font-medium',
                colorStyles.bg,
                colorStyles.text,
                colorStyles.border,
                colorStyles.hover,
                variantStyles,
                sizeStyles.tag
              )}
            >
              <TagIcon className={cn('flex-shrink-0', sizeStyles.icon)} />
              <span>{tag.label}</span>
              {!disabled && (
                <button
                  type="button"
                  onClick={() => removeTag(tag.id)}
                  className={cn(
                    'rounded-full p-0.5 transition-colors hover:bg-black/10 dark:hover:bg-white/10',
                    sizeStyles.icon
                  )}
                >
                  <XMarkIcon className={cn('h-3 w-3', sizeStyles.icon)} />
                </button>
              )}
            </motion.div>
          ))}

          {/* Input */}
          {!disabled && (
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
              type="text"
              className={cn(
                'flex-1 min-w-[80px] bg-transparent outline-none placeholder-gray-400 dark:placeholder-gray-500',
                sizeStyles.input,
                disabled && 'cursor-not-allowed'
              )}
              placeholder={tagCount === 0 ? placeholder : ''}
              value={inputValue}
              onChange={handleInputChange}
              onKeyDown={handleInputKeyDown}
              onFocus={handleInputFocus}
              onBlur={handleInputBlur}
              disabled={disabled}
              aria-label={ariaLabel || label}
              aria-describedby={ariaDescribedby}
              aria-invalid={hasError}
              aria-required={required}
              name={name}
            />
          )}

          {/* Icône de validation */}
          {showValidationIcon && (
            <div className="flex-shrink-0">
              {hasError && !disabled && (
                <ExclamationCircleIcon className="h-4 w-4 text-red-500" />
              )}
              {isSuccess && !disabled && (
                <CheckCircleIcon className="h-4 w-4 text-green-500" />
              )}
            </div>
          )}
        </div>

        {/* Suggestions */}
        {showSuggestions && showSuggestionsList && !disabled && (
          <div className="absolute z-10 mt-1 w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-lg">
            <div className="p-1">
              {isLoadingSuggestions ? (
                <div className="flex items-center justify-center py-4">
                  <ArrowPathIcon className="h-5 w-5 animate-spin text-gray-400" />
                </div>
              ) : (
                filteredSuggestions.map((suggestion) => (
                  <button
                    key={suggestion.id}
                    type="button"
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
                    onClick={() => addTag(suggestion)}
                  >
                    <TagIcon className="h-4 w-4 text-gray-400" />
                    <span className="flex-1 text-left">{suggestion.label}</span>
                    <PlusIcon className="h-3 w-3 text-gray-400" />
                  </button>
                ))
              )}
            </div>
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

TagsField.displayName = 'TagsField';

// ============================================================================
// EXPORTS
// ============================================================================

export default TagsField;

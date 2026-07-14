// apps/web/src/components/forms/fields/PhoneField.tsx
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
  PhoneIcon,
  DevicePhoneMobileIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
  CheckIcon,
  ArrowPathIcon,
  ExclamationCircleIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  GlobeAltIcon,
  ClipboardIcon,
  DocumentDuplicateIcon,
  PlusIcon,
  MinusIcon,
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

export type PhoneCountry = {
  code: string;
  name: string;
  dialCode: string;
  flag: string;
  mask: string;
  example: string;
  minLength: number;
  maxLength: number;
};

export type PhoneFieldVariant = 'default' | 'compact' | 'minimal' | 'rounded' | 'outlined';
export type PhoneFormat = 'international' | 'national' | 'e164' | 'rfc3966';
export type PhoneValidationLevel = 'basic' | 'standard' | 'strict' | 'custom';

export interface PhoneFieldProps {
  // --- Contrôle ---
  /** Valeur du champ */
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
  variant?: PhoneFieldVariant;
  /** Afficher le sélecteur de pays */
  showCountrySelector?: boolean;
  /** Afficher l'icône de validation */
  showValidationIcon?: boolean;
  /** Afficher le formatage */
  showFormatting?: boolean;
  /** Afficher le bouton de copie */
  showCopyButton?: boolean;

  // --- Comportement ---
  /** Pays par défaut */
  defaultCountry?: string;
  /** Pays autorisés */
  allowedCountries?: string[];
  /** Désactiver le champ */
  disabled?: boolean;
  /** Rendre le champ obligatoire */
  required?: boolean;
  /** Validation personnalisée */
  validatePhone?: (phone: string) => boolean | string;
  /** Niveau de validation */
  validationLevel?: PhoneValidationLevel;
  /** Format de sortie */
  outputFormat?: PhoneFormat;
  /** Désactiver la validation en temps réel */
  disableRealtimeValidation?: boolean;
  /** Désactiver le trim */
  disableTrim?: boolean;

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
  customFormat?: (phone: string, country: PhoneCountry) => string;
  /** Fonction de parsing personnalisée */
  customParse?: (value: string) => string | null;
  /** Fonction de validation personnalisée */
  customValidate?: (phone: string | null) => boolean | string;
  /** Ref */
  inputRef?: React.Ref<HTMLInputElement>;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

export const COUNTRIES: Record<string, PhoneCountry> = {
  FR: {
    code: 'FR',
    name: 'France',
    dialCode: '+33',
    flag: '🇫🇷',
    mask: '0[1-9] XX XX XX XX',
    example: '06 12 34 56 78',
    minLength: 10,
    maxLength: 10,
  },
  BE: {
    code: 'BE',
    name: 'Belgique',
    dialCode: '+32',
    flag: '🇧🇪',
    mask: '0 XXX XX XX XX',
    example: '04 12 34 56 78',
    minLength: 9,
    maxLength: 10,
  },
  CH: {
    code: 'CH',
    name: 'Suisse',
    dialCode: '+41',
    flag: '🇨🇭',
    mask: '0XX XXX XX XX',
    example: '079 123 45 67',
    minLength: 9,
    maxLength: 10,
  },
  CA: {
    code: 'CA',
    name: 'Canada',
    dialCode: '+1',
    flag: '🇨🇦',
    mask: '(XXX) XXX-XXXX',
    example: '(514) 123-4567',
    minLength: 10,
    maxLength: 10,
  },
  US: {
    code: 'US',
    name: 'États-Unis',
    dialCode: '+1',
    flag: '🇺🇸',
    mask: '(XXX) XXX-XXXX',
    example: '(212) 555-1234',
    minLength: 10,
    maxLength: 10,
  },
  GB: {
    code: 'GB',
    name: 'Royaume-Uni',
    dialCode: '+44',
    flag: '🇬🇧',
    mask: '0XXX XXX XXXX',
    example: '07400 123456',
    minLength: 10,
    maxLength: 11,
  },
  DE: {
    code: 'DE',
    name: 'Allemagne',
    dialCode: '+49',
    flag: '🇩🇪',
    mask: '0XXX XXX XXXX',
    example: '0151 234 5678',
    minLength: 10,
    maxLength: 11,
  },
  ES: {
    code: 'ES',
    name: 'Espagne',
    dialCode: '+34',
    flag: '🇪🇸',
    mask: 'XXX XXX XXX',
    example: '612 345 678',
    minLength: 9,
    maxLength: 9,
  },
  IT: {
    code: 'IT',
    name: 'Italie',
    dialCode: '+39',
    flag: '🇮🇹',
    mask: 'XXX XXX XXXX',
    example: '312 345 6789',
    minLength: 9,
    maxLength: 10,
  },
  PT: {
    code: 'PT',
    name: 'Portugal',
    dialCode: '+351',
    flag: '🇵🇹',
    mask: 'XXX XXX XXX',
    example: '912 345 678',
    minLength: 9,
    maxLength: 9,
  },
  NL: {
    code: 'NL',
    name: 'Pays-Bas',
    dialCode: '+31',
    flag: '🇳🇱',
    mask: '0X XXX XXX XX',
    example: '06 123 456 78',
    minLength: 10,
    maxLength: 10,
  },
  LU: {
    code: 'LU',
    name: 'Luxembourg',
    dialCode: '+352',
    flag: '🇱🇺',
    mask: 'XXX XXX XXX',
    example: '621 123 456',
    minLength: 9,
    maxLength: 9,
  },
};

const DEFAULT_COUNTRY = 'FR';
const PHONE_REGEX = /^[+\d\s\-\(\)\.]{6,}$/;
const DIGITS_ONLY = /[^\d]/g;

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const PhoneField = forwardRef<HTMLInputElement, PhoneFieldProps>(
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
      placeholder = '06 12 34 56 78',
      description,
      error,
      success,
      info,
      variant = 'default',
      showCountrySelector = true,
      showValidationIcon = true,
      showFormatting = true,
      showCopyButton = true,

      // Comportement
      defaultCountry = DEFAULT_COUNTRY,
      allowedCountries,
      disabled = false,
      required = false,
      validatePhone: customValidatePhone,
      validationLevel = 'standard',
      outputFormat = 'international',
      disableRealtimeValidation = false,
      disableTrim = false,

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
    const [selectedCountry, setSelectedCountry] = useState<PhoneCountry>(
      COUNTRIES[defaultCountry] || COUNTRIES[DEFAULT_COUNTRY]
    );
    const [countrySearch, setCountrySearch] = useState('');

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined ? externalValue : internalValue;
    const isControlled = externalValue !== undefined;
    const hasValue = value && value.length > 0;
    const countryList = allowedCountries 
      ? Object.keys(COUNTRIES)
          .filter(code => allowedCountries.includes(code))
          .map(code => COUNTRIES[code])
      : Object.values(COUNTRIES);

    // ========================================================================
    // FORMATAGE
    // ========================================================================

    const formatPhone = useCallback((phone: string | null, country: PhoneCountry): string => {
      if (!phone) return '';

      if (customFormat) {
        return customFormat(phone, country);
      }

      let cleaned = phone.replace(DIGITS_ONLY, '');

      // Formatage selon le pays
      if (country.code === 'FR' || country.code === 'BE') {
        if (cleaned.length >= 10) {
          // Format: 0X XX XX XX XX
          return `${cleaned.slice(0, 2)} ${cleaned.slice(2, 4)} ${cleaned.slice(4, 6)} ${cleaned.slice(6, 8)} ${cleaned.slice(8, 10)}`;
        }
      } else if (country.code === 'US' || country.code === 'CA') {
        if (cleaned.length === 10) {
          // Format: (XXX) XXX-XXXX
          return `(${cleaned.slice(0, 3)}) ${cleaned.slice(3, 6)}-${cleaned.slice(6, 10)}`;
        }
      } else if (country.code === 'GB') {
        if (cleaned.length >= 11) {
          // Format: 0XXX XXX XXXX
          return `${cleaned.slice(0, 4)} ${cleaned.slice(4, 7)} ${cleaned.slice(7, 11)}`;
        }
      } else if (country.code === 'DE') {
        if (cleaned.length >= 11) {
          // Format: 0XXX XXX XXXX
          return `${cleaned.slice(0, 4)} ${cleaned.slice(4, 7)} ${cleaned.slice(7, 11)}`;
        }
      } else if (country.code === 'ES' || country.code === 'PT' || country.code === 'LU') {
        if (cleaned.length >= 9) {
          // Format: XXX XXX XXX
          return `${cleaned.slice(0, 3)} ${cleaned.slice(3, 6)} ${cleaned.slice(6, 9)}`;
        }
      } else if (country.code === 'IT') {
        if (cleaned.length >= 10) {
          // Format: XXX XXX XXXX
          return `${cleaned.slice(0, 3)} ${cleaned.slice(3, 6)} ${cleaned.slice(6, 10)}`;
        }
      } else if (country.code === 'NL') {
        if (cleaned.length >= 10) {
          // Format: 0X XXX XXX XX
          return `${cleaned.slice(0, 2)} ${cleaned.slice(2, 5)} ${cleaned.slice(5, 8)} ${cleaned.slice(8, 10)}`;
        }
      } else if (country.code === 'CH') {
        if (cleaned.length >= 10) {
          // Format: 0XX XXX XX XX
          return `${cleaned.slice(0, 3)} ${cleaned.slice(3, 6)} ${cleaned.slice(6, 8)} ${cleaned.slice(8, 10)}`;
        }
      }

      return phone;
    }, [customFormat]);

    const parsePhone = useCallback((text: string): string | null => {
      if (!text || text.trim() === '') return null;

      if (customParse) {
        return customParse(text);
      }

      // Nettoyer le texte
      let cleaned = text.trim();
      
      // Retirer le code du pays si présent
      if (cleaned.startsWith(selectedCountry.dialCode)) {
        cleaned = cleaned.replace(selectedCountry.dialCode, '');
      }

      // Garder uniquement les chiffres
      cleaned = cleaned.replace(DIGITS_ONLY, '');

      // Vérifier la longueur minimale
      if (cleaned.length < selectedCountry.minLength) {
        return null;
      }

      // Tronquer si trop long
      if (cleaned.length > selectedCountry.maxLength) {
        cleaned = cleaned.slice(0, selectedCountry.maxLength);
      }

      return cleaned;
    }, [customParse, selectedCountry]);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validatePhoneNumber = useCallback((phone: string | null): { valid: boolean; message: string } => {
      if (customValidate) {
        const result = customValidate(phone);
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        return { valid: true, message: '' };
      }

      if (customValidatePhone) {
        const result = customValidatePhone(phone || '');
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        return { valid: true, message: '' };
      }

      if (!phone) {
        if (required) {
          return { valid: false, message: 'Le numéro de téléphone est requis' };
        }
        return { valid: true, message: '' };
      }

      const cleaned = phone.replace(DIGITS_ONLY, '');

      // Validation basique
      if (cleaned.length < selectedCountry.minLength) {
        return { valid: false, message: `Le numéro doit contenir au moins ${selectedCountry.minLength} chiffres` };
      }

      if (cleaned.length > selectedCountry.maxLength) {
        return { valid: false, message: `Le numéro ne doit pas dépasser ${selectedCountry.maxLength} chiffres` };
      }

      // Validation standard
      if (validationLevel === 'standard' || validationLevel === 'strict') {
        // Vérifier que le numéro commence par un préfixe valide
        const validPrefixes = ['0', '1', '2', '3', '4', '5', '6', '7', '8', '9'];
        if (!validPrefixes.includes(cleaned[0])) {
          return { valid: false, message: 'Le numéro commence par un préfixe invalide' };
        }

        // Vérifier les préfixes spécifiques par pays
        if (selectedCountry.code === 'FR') {
          const validPrefixes = ['06', '07', '08', '09', '01', '02', '03', '04', '05'];
          if (!validPrefixes.some(p => cleaned.startsWith(p))) {
            return { valid: false, message: 'Préfixe invalide pour la France' };
          }
        }
      }

      // Validation stricte
      if (validationLevel === 'strict') {
        // Vérifier l'indicatif régional
        if (selectedCountry.code === 'US' || selectedCountry.code === 'CA') {
          if (!['201', '202', '203', '204', '205', '206', '207', '208', '209'].some(p => cleaned.startsWith(p))) {
            return { valid: false, message: 'Indicatif régional invalide' };
          }
        }
      }

      return { valid: true, message: '' };
    }, [
      customValidate,
      customValidatePhone,
      required,
      selectedCountry,
      validationLevel,
    ]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateValue = useCallback((phone: string | null) => {
      const trimmed = phone ? (disableTrim ? phone : phone.trim()) : null;
      const validation = validatePhoneNumber(trimmed);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);

      if (!disableRealtimeValidation && onValidate) {
        onValidate(validation.valid, trimmed);
      }

      if (isControlled) {
        if (onChange) onChange(trimmed);
      } else {
        setInternalValue(trimmed);
        if (onChange) onChange(trimmed);
      }

      if (showFormatting) {
        const formatted = formatPhone(trimmed, selectedCountry);
        setDisplayValue(formatted);
      } else {
        setDisplayValue(trimmed || '');
      }

      if (debug) {
        console.log('PhoneField update:', { phone: trimmed, isValid: validation.valid });
      }
    }, [
      validatePhoneNumber,
      isControlled,
      onChange,
      onValidate,
      disableRealtimeValidation,
      showFormatting,
      formatPhone,
      selectedCountry,
      disableTrim,
      debug,
    ]);

    // ========================================================================
    // GESTIONNAIRES D'ÉVÉNEMENTS
    // ========================================================================

    const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
      const rawValue = e.target.value;
      setDisplayValue(rawValue);

      if (!disableRealtimeValidation) {
        const parsed = parsePhone(rawValue);
        const validation = validatePhoneNumber(parsed);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        if (onValidate) onValidate(validation.valid, parsed);
      }

      if (!isFocused) {
        const parsed = parsePhone(rawValue);
        updateValue(parsed);
      }
    }, [disableRealtimeValidation, parsePhone, validatePhoneNumber, onValidate, updateValue, isFocused]);

    const handleFocus = useCallback(() => {
      setIsFocused(true);
      if (onFocus) onFocus();

      setTimeout(() => {
        inputRefInternal.current?.select();
      }, 10);
    }, [onFocus]);

    const handleBlur = useCallback(() => {
      setIsFocused(false);

      const parsed = parsePhone(displayValue);
      const validation = validatePhoneNumber(parsed);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);
      if (onValidate) onValidate(validation.valid, parsed);

      if (parsed) {
        updateValue(parsed);
      } else if (!displayValue) {
        updateValue(null);
      } else {
        setDisplayValue(formatPhone(value, selectedCountry));
      }

      if (onBlur) onBlur();
    }, [
      displayValue,
      parsePhone,
      validatePhoneNumber,
      onValidate,
      updateValue,
      formatPhone,
      value,
      selectedCountry,
      onBlur,
    ]);

    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const parsed = parsePhone(displayValue);
        if (parsed) {
          updateValue(parsed);
        }
        inputRefInternal.current?.blur();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        setDisplayValue(formatPhone(value, selectedCountry));
        inputRefInternal.current?.blur();
      }
    }, [displayValue, parsePhone, updateValue, formatPhone, value, selectedCountry]);

    // ========================================================================
    // CHANGEMENT DE PAYS
    // ========================================================================

    const handleCountryChange = useCallback((country: PhoneCountry) => {
      setSelectedCountry(country);
      
      // Re-formater le numéro avec le nouveau pays
      if (value) {
        const formatted = formatPhone(value, country);
        setDisplayValue(formatted);
      }

      if (debug) {
        console.log('PhoneField country changed:', country.code);
      }
    }, [value, formatPhone, debug]);

    // ========================================================================
    // COPIE
    // ========================================================================

    const handleCopy = useCallback(() => {
      if (value) {
        navigator.clipboard.writeText(value);
        toast({
          title: 'Copié',
          description: 'Le numéro a été copié dans le presse-papier',
          duration: 2000,
        });
      }
    }, [value, toast]);

    // ========================================================================
    // SYNC AVEC LA VALEUR EXTERNE
    // ========================================================================

    useEffect(() => {
      if (externalValue !== undefined && externalValue !== prevValueRef.current) {
        prevValueRef.current = externalValue;
        if (showFormatting) {
          const formatted = formatPhone(externalValue, selectedCountry);
          setDisplayValue(formatted);
        } else {
          setDisplayValue(externalValue || '');
        }
        if (externalValue) {
          const validation = validatePhoneNumber(externalValue);
          setIsValid(validation.valid);
          setValidationMessage(validation.message);
        }
      }
    }, [externalValue, validatePhoneNumber, formatPhone, selectedCountry, showFormatting]);

    // ========================================================================
    // INITIALISATION
    // ========================================================================

    useEffect(() => {
      if (defaultValue !== undefined && !isControlled) {
        const val = defaultValue;
        if (showFormatting) {
          const formatted = formatPhone(val, selectedCountry);
          setDisplayValue(formatted);
        } else {
          setDisplayValue(val || '');
        }
        if (val) {
          const validation = validatePhoneNumber(val);
          setIsValid(validation.valid);
          setValidationMessage(validation.message);
        }
        updateValue(val);
      }
    }, [defaultValue, updateValue, isControlled, validatePhoneNumber, formatPhone, selectedCountry, showFormatting]);

    // ========================================================================
    // IMPERATIVE HANDLE
    // ========================================================================

    useImperativeHandle(ref, () => ({
      focus: () => inputRefInternal.current?.focus(),
      blur: () => inputRefInternal.current?.blur(),
      select: () => inputRefInternal.current?.select(),
      getValue: () => value,
      setValue: (val: string | null) => updateValue(val),
      getCountry: () => selectedCountry,
      setCountry: (countryCode: string) => {
        const country = COUNTRIES[countryCode];
        if (country) handleCountryChange(country);
      },
      validate: () => {
        const validation = validatePhoneNumber(value);
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
      compact: 'border-gray-300 dark:border-gray-600 h-8 text-xs',
      minimal: 'border-b-2 border-gray-300 dark:border-gray-600 rounded-none',
      rounded: 'border-gray-300 dark:border-gray-600 rounded-full',
      outlined: 'border-2 border-gray-300 dark:border-gray-600',
    };

    const filteredCountries = countrySearch
      ? countryList.filter(c => 
          c.name.toLowerCase().includes(countrySearch.toLowerCase()) ||
          c.dialCode.includes(countrySearch) ||
          c.code.toLowerCase().includes(countrySearch.toLowerCase())
        )
      : countryList;

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
            {showFormatting && value && (
              <Badge variant="outline" size="xs" className="text-xs">
                {selectedCountry.code}
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
            disabled && 'opacity-50 cursor-not-allowed bg-gray-50 dark:bg-gray-800/50'
          )}>
            {/* Sélecteur de pays */}
            {showCountrySelector && !disabled && (
              <div className="flex-shrink-0 pl-2">
                <Popover
                  trigger={
                    <button
                      type="button"
                      className="flex items-center gap-1 rounded-lg px-2 py-1 text-sm font-medium hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                      disabled={disabled}
                    >
                      <span className="text-lg">{selectedCountry.flag}</span>
                      <span className="text-xs">{selectedCountry.dialCode}</span>
                      <ChevronDownIcon className="h-3 w-3 text-gray-400" />
                    </button>
                  }
                  placement="bottom-start"
                  size="sm"
                >
                  <div className="p-2 min-w-[200px]">
                    <div className="relative mb-2">
                      <input
                        type="text"
                        placeholder="Rechercher un pays..."
                        value={countrySearch}
                        onChange={(e) => setCountrySearch(e.target.value)}
                        className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800 px-3 py-1.5 text-sm focus:border-brand-500 focus:outline-none"
                      />
                    </div>
                    <div className="max-h-48 overflow-y-auto space-y-0.5">
                      {filteredCountries.map((country) => (
                        <button
                          key={country.code}
                          type="button"
                          className={cn(
                            'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors',
                            selectedCountry.code === country.code
                              ? 'bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-400'
                              : 'hover:bg-gray-100 dark:hover:bg-gray-800'
                          )}
                          onClick={() => {
                            handleCountryChange(country);
                            setCountrySearch('');
                          }}
                        >
                          <span className="text-lg">{country.flag}</span>
                          <span className="flex-1 text-left">{country.name}</span>
                          <span className="text-xs text-gray-400">{country.dialCode}</span>
                          {selectedCountry.code === country.code && (
                            <CheckIcon className="h-4 w-4 text-brand-500" />
                          )}
                        </button>
                      ))}
                    </div>
                  </div>
                </Popover>
              </div>
            )}

            {/* Affichage du préfixe si non sélectionnable */}
            {!showCountrySelector && (
              <span className="flex-shrink-0 pl-3 text-sm text-gray-500 dark:text-gray-400">
                {selectedCountry.dialCode}
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
              type="tel"
              className={cn(
                'w-full bg-transparent px-3 py-2 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 outline-none',
                disabled && 'cursor-not-allowed',
                showCountrySelector ? 'pl-2' : 'pl-1',
                variant === 'compact' && 'h-8 text-xs',
                variant === 'rounded' && 'h-10 rounded-full'
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
              autoComplete="tel"
            />

            {/* Actions */}
            <div className="flex items-center gap-0.5 pr-2">
              {showCopyButton && value && !disabled && (
                <Tooltip content="Copier">
                  <button
                    type="button"
                    onClick={handleCopy}
                    className="rounded p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                  >
                    <DocumentDuplicateIcon className="h-4 w-4" />
                  </button>
                </Tooltip>
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
            {value && !hasError && !disabled && (
              <Badge variant="outline" size="xs" className="ml-auto">
                {value.length} chiffres
              </Badge>
            )}
          </div>
        </div>

        {/* Description */}
        {description && (
          <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
        )}

        {/* Exemple de format */}
        {showFormatting && selectedCountry.example && !disabled && (
          <p className="text-xs text-gray-400 dark:text-gray-500">
            Ex: {selectedCountry.example}
          </p>
        )}
      </div>
    );
  }
);

PhoneField.displayName = 'PhoneField';

// ============================================================================
// EXPORTS
// ============================================================================

export default PhoneField;

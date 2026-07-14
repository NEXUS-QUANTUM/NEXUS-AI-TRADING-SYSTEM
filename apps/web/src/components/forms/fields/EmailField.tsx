// apps/web/src/components/forms/fields/EmailField.tsx
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
  EnvelopeIcon,
  AtSymbolIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
  CheckIcon,
  ArrowPathIcon,
  UserIcon,
  BuildingOfficeIcon,
  GlobeAltIcon,
  PlusIcon,
  MinusIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ClipboardIcon,
  ShieldCheckIcon,
  ExclamationCircleIcon,
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

export type EmailValidationLevel = 'basic' | 'standard' | 'strict' | 'custom';
export type EmailSuggestion = {
  email: string;
  domain: string;
  confidence: number;
  reason?: string;
};

export interface EmailFieldProps {
  // --- Contrôle ---
  /** Valeur du champ (email simple ou multiple) */
  value?: string | string[] | null;
  /** Valeur par défaut */
  defaultValue?: string | string[] | null;
  /** Callback de changement */
  onChange?: (value: string | string[] | null) => void;
  /** Callback de blur */
  onBlur?: () => void;
  /** Callback de focus */
  onFocus?: () => void;
  /** Callback de validation */
  onValidate?: (valid: boolean, value: string | string[] | null) => void;

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
  /** Afficher l'icône de validation */
  showValidationIcon?: boolean;
  /** Afficher les suggestions */
  showSuggestions?: boolean;
  /** Afficher le compteur d'emails (multi) */
  showEmailCount?: boolean;
  /** Afficher les badges des emails (multi) */
  showEmailBadges?: boolean;

  // --- Comportement ---
  /** Mode multi-emails */
  multi?: boolean;
  /** Séparateur pour les emails multiples */
  separator?: string;
  /** Désactiver le champ */
  disabled?: boolean;
  /** Rendre le champ obligatoire */
  required?: boolean;
  /** Nombre maximum d'emails (multi) */
  maxEmails?: number;
  /** Nombre minimum d'emails (multi) */
  minEmails?: number;
  /** Domaines autorisés */
  allowedDomains?: string[];
  /** Domaines bloqués */
  blockedDomains?: string[];
  /** Validation personnalisée */
  validateEmail?: (email: string) => boolean | string;
  /** Niveau de validation */
  validationLevel?: EmailValidationLevel;
  /** Désactiver la validation en temps réel */
  disableRealtimeValidation?: boolean;
  /** Désactiver les doublons */
  allowDuplicates?: boolean;
  /** Désactiver le trim */
  disableTrim?: boolean;

  // --- Suggestions ---
  /** Domaines de suggestion */
  suggestionDomains?: string[];
  /** Nombre maximum de suggestions */
  maxSuggestions?: number;
  /** Callback de suggestion personnalisée */
  customSuggestions?: (input: string) => EmailSuggestion[];

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
  customFormat?: (email: string) => string;
  /** Fonction de parsing personnalisée */
  customParse?: (value: string) => string | string[] | null;
  /** Ref */
  inputRef?: React.Ref<HTMLInputElement>;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const COMMON_DOMAINS = [
  'gmail.com',
  'yahoo.com',
  'hotmail.com',
  'outlook.com',
  'live.com',
  'icloud.com',
  'me.com',
  'mac.com',
  'protonmail.com',
  'mail.com',
  'aol.com',
  'fastmail.com',
  'gmx.com',
  'hey.com',
  'tutanota.com',
  'zoho.com',
  'yandex.com',
];

const TYPOS: Record<string, string> = {
  'gmial.com': 'gmail.com',
  'gmal.com': 'gmail.com',
  'gamil.com': 'gmail.com',
  'gmail.co': 'gmail.com',
  'gmail.cm': 'gmail.com',
  'yahoo.co': 'yahoo.com',
  'yaho.com': 'yahoo.com',
  'yhoo.com': 'yahoo.com',
  'hotmail.co': 'hotmail.com',
  'hotmai.com': 'hotmail.com',
  'hotmil.com': 'hotmail.com',
  'outlook.co': 'outlook.com',
  'outlok.com': 'outlook.com',
  'lve.com': 'live.com',
  'icloud.co': 'icloud.com',
  'protonmail.co': 'protonmail.com',
  'proton.me': 'protonmail.com',
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const EmailField = forwardRef<HTMLInputElement, EmailFieldProps>(
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
      placeholder = 'email@exemple.com',
      description,
      error,
      success,
      info,
      showValidationIcon = true,
      showSuggestions = true,
      showEmailCount = true,
      showEmailBadges = true,

      // Comportement
      multi = false,
      separator = ',',
      disabled = false,
      required = false,
      maxEmails = 10,
      minEmails = 0,
      allowedDomains = [],
      blockedDomains = [],
      validateEmail: customValidateEmail,
      validationLevel = 'standard',
      disableRealtimeValidation = false,
      allowDuplicates = false,
      disableTrim = false,

      // Suggestions
      suggestionDomains = COMMON_DOMAINS,
      maxSuggestions = 5,
      customSuggestions,

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

    const inputRefInternal = useRef<HTMLInputElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);
    const prevValueRef = useRef<string | string[] | null>(null);
    const suggestionTimeoutRef = useRef<NodeJS.Timeout | null>(null);

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalValue, setInternalValue] = useState<string | string[] | null>(
      defaultValue || (multi ? [] : '')
    );
    const [displayValue, setDisplayValue] = useState<string>('');
    const [isFocused, setIsFocused] = useState(false);
    const [isValid, setIsValid] = useState(true);
    const [validationMessage, setValidationMessage] = useState<string>('');
    const [suggestions, setSuggestions] = useState<EmailSuggestion[]>([]);
    const [showSuggestionsList, setShowSuggestionsList] = useState(false);
    const [isTyping, setIsTyping] = useState(false);
    const [emailCount, setEmailCount] = useState(0);
    const [duplicates, setDuplicates] = useState<string[]>([]);
    const [isEmailValid, setIsEmailValid] = useState(false);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined ? externalValue : internalValue;
    const isControlled = externalValue !== undefined;
    const isMulti = multi;
    const emails = isMulti ? (Array.isArray(value) ? value : []) : (value ? [String(value)] : []);
    const emailCountValue = emails.length;

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validateEmail = useCallback((email: string): { valid: boolean; message: string } => {
      // Validation personnalisée
      if (customValidateEmail) {
        const result = customValidateEmail(email);
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        return { valid: true, message: '' };
      }

      const trimmed = disableTrim ? email : email.trim();
      if (!trimmed) {
        return { valid: false, message: 'L\'email est requis' };
      }

      // Validation basique
      const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
      if (!emailRegex.test(trimmed)) {
        return { valid: false, message: 'Format d\'email invalide' };
      }

      const [localPart, domain] = trimmed.split('@');

      // Validation standard
      if (validationLevel === 'standard' || validationLevel === 'strict') {
        // Longueur maximale
        if (trimmed.length > 254) {
          return { valid: false, message: 'L\'email est trop long' };
        }
        if (localPart.length > 64) {
          return { valid: false, message: 'La partie locale est trop longue' };
        }
        if (domain.length > 255) {
          return { valid: false, message: 'Le domaine est trop long' };
        }

        // Caractères spéciaux
        if (/[<>()\[\]\\:;@,]/.test(localPart)) {
          return { valid: false, message: 'Caractères spéciaux non autorisés dans la partie locale' };
        }
      }

      // Validation stricte
      if (validationLevel === 'strict') {
        // Pas de points consécutifs
        if (localPart.includes('..')) {
          return { valid: false, message: 'Points consécutifs non autorisés' };
        }
        // Pas de point en début ou fin
        if (localPart.startsWith('.') || localPart.endsWith('.')) {
          return { valid: false, message: 'Le point en début ou fin de la partie locale n\'est pas autorisé' };
        }
        // Domaine valide
        if (!domain.includes('.') || domain.endsWith('.') || domain.startsWith('.')) {
          return { valid: false, message: 'Domaine invalide' };
        }
      }

      // Domaines autorisés
      if (allowedDomains.length > 0 && !allowedDomains.includes(domain)) {
        return { valid: false, message: `Domaine non autorisé. Domaines autorisés: ${allowedDomains.join(', ')}` };
      }

      // Domaines bloqués
      if (blockedDomains.length > 0 && blockedDomains.includes(domain)) {
        return { valid: false, message: `Domaine bloqué: ${domain}` };
      }

      return { valid: true, message: '' };
    }, [customValidateEmail, validationLevel, allowedDomains, blockedDomains, disableTrim]);

    const validateEmails = useCallback((emailList: string[]): { valid: boolean; messages: string[] } => {
      const messages: string[] = [];
      let allValid = true;

      // Vérifier le nombre minimum
      if (emailList.length < minEmails) {
        messages.push(`Minimum ${minEmails} email${minEmails > 1 ? 's' : ''} requis`);
        allValid = false;
      }

      // Vérifier le nombre maximum
      if (emailList.length > maxEmails) {
        messages.push(`Maximum ${maxEmails} email${maxEmails > 1 ? 's' : ''} autorisé${maxEmails > 1 ? 's' : ''}`);
        allValid = false;
      }

      // Vérifier les doublons
      if (!allowDuplicates) {
        const seen = new Set<string>();
        const duplicateList: string[] = [];
        for (const email of emailList) {
          const normalized = email.toLowerCase().trim();
          if (seen.has(normalized)) {
            duplicateList.push(email);
          }
          seen.add(normalized);
        }
        if (duplicateList.length > 0) {
          messages.push(`Emails en double: ${duplicateList.join(', ')}`);
          allValid = false;
          setDuplicates(duplicateList);
        } else {
          setDuplicates([]);
        }
      }

      // Valider chaque email
      for (const email of emailList) {
        const result = validateEmail(email);
        if (!result.valid) {
          messages.push(`${email}: ${result.message}`);
          allValid = false;
        }
      }

      return { valid: allValid, messages };
    }, [minEmails, maxEmails, allowDuplicates, validateEmail]);

    // ========================================================================
    // SUGGESTIONS
    // ========================================================================

    const getSuggestions = useCallback((input: string): EmailSuggestion[] => {
      if (customSuggestions) {
        return customSuggestions(input);
      }

      if (!input || !input.includes('@')) {
        return [];
      }

      const trimmed = disableTrim ? input : input.trim();
      const [localPart, domain] = trimmed.split('@');

      if (!localPart || !domain) {
        return [];
      }

      const suggestions: EmailSuggestion[] = [];

      // Suggestions de domaines
      const searchDomains = suggestionDomains.filter(d => 
        d.startsWith(domain.toLowerCase()) || 
        domain.toLowerCase().startsWith(d) ||
        TYPOS[domain.toLowerCase()]
      );

      for (const sugDomain of searchDomains) {
        const correctedDomain = TYPOS[domain.toLowerCase()] || sugDomain;
        if (correctedDomain !== domain) {
          suggestions.push({
            email: `${localPart}@${correctedDomain}`,
            domain: correctedDomain,
            confidence: 0.9,
            reason: `Domaine corrigé: ${domain} → ${correctedDomain}`,
          });
        } else if (sugDomain !== domain) {
          suggestions.push({
            email: `${localPart}@${sugDomain}`,
            domain: sugDomain,
            confidence: 0.7,
            reason: `Domaine suggéré: ${sugDomain}`,
          });
        }
      }

      // Suggestions basées sur les typographies
      if (domain.includes('.')) {
        const parts = domain.split('.');
        if (parts.length > 1 && parts[parts.length - 1].length === 1) {
          const corrected = `${parts.slice(0, -1).join('.')}.${parts[parts.length - 1]}${parts[parts.length - 1]}`;
          suggestions.push({
            email: `${localPart}@${corrected}`,
            domain: corrected,
            confidence: 0.6,
            reason: `Extension corrigée: .${parts[parts.length - 1]} → .${parts[parts.length - 1]}${parts[parts.length - 1]}`,
          });
        }
      }

      return suggestions.slice(0, maxSuggestions);
    }, [customSuggestions, suggestionDomains, maxSuggestions, disableTrim]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateValue = useCallback((newValue: string | string[] | null) => {
      const emailList = isMulti 
        ? (Array.isArray(newValue) ? newValue : [])
        : (newValue ? [String(newValue)] : []);

      // Validation
      const validation = validateEmails(emailList);
      const isEmailValid = validation.valid;
      setIsValid(isEmailValid);
      setValidationMessage(validation.messages.join('; '));
      setEmailCount(emailList.length);

      if (!disableRealtimeValidation && onValidate) {
        onValidate(isEmailValid, newValue);
      }

      // Mise à jour
      if (isControlled) {
        if (onChange) onChange(newValue);
      } else {
        setInternalValue(newValue);
        if (onChange) onChange(newValue);
      }

      // Formatage pour affichage
      if (isMulti) {
        setDisplayValue(emailList.join(separator));
      } else {
        setDisplayValue(emailList[0] || '');
      }

      if (debug) {
        console.log('EmailField update:', { newValue, emailList, isValid: isEmailValid });
      }
    }, [
      isMulti,
      separator,
      validateEmails,
      isControlled,
      onChange,
      onValidate,
      disableRealtimeValidation,
      debug,
    ]);

    // ========================================================================
    // GESTIONNAIRES D'ÉVÉNEMENTS
    // ========================================================================

    const handleChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
      const rawValue = e.target.value;
      setDisplayValue(rawValue);
      setIsTyping(true);

      if (isMulti) {
        const emails = rawValue.split(separator).map(e => e.trim()).filter(e => e);
        const validation = validateEmails(emails);
        setIsValid(validation.valid);
        setValidationMessage(validation.messages.join('; '));
        setEmailCount(emails.length);
        if (onValidate) onValidate(validation.valid, emails);
        if (!disableRealtimeValidation) {
          updateValue(emails);
        }
      } else {
        if (!disableRealtimeValidation) {
          const validation = validateEmail(rawValue);
          setIsValid(validation.valid);
          setValidationMessage(validation.message);
          if (onValidate) onValidate(validation.valid, rawValue);
        }
      }

      // Suggestions
      if (showSuggestions && rawValue.includes('@')) {
        if (suggestionTimeoutRef.current) {
          clearTimeout(suggestionTimeoutRef.current);
        }
        suggestionTimeoutRef.current = setTimeout(() => {
          const sugg = getSuggestions(rawValue);
          setSuggestions(sugg);
          setShowSuggestionsList(sugg.length > 0);
        }, 300);
      } else {
        setShowSuggestionsList(false);
      }
    }, [
      isMulti,
      separator,
      validateEmails,
      validateEmail,
      onValidate,
      disableRealtimeValidation,
      showSuggestions,
      getSuggestions,
      updateValue,
    ]);

    const handleFocus = useCallback(() => {
      setIsFocused(true);
      if (onFocus) onFocus();
    }, [onFocus]);

    const handleBlur = useCallback(() => {
      setIsFocused(false);
      setIsTyping(false);

      if (isMulti) {
        const rawValue = displayValue;
        const emails = rawValue.split(separator).map(e => e.trim()).filter(e => e);
        const validation = validateEmails(emails);
        setIsValid(validation.valid);
        setValidationMessage(validation.messages.join('; '));
        if (onValidate) onValidate(validation.valid, emails);
        updateValue(emails);
      } else {
        const trimmed = disableTrim ? displayValue : displayValue.trim();
        const validation = validateEmail(trimmed);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        if (onValidate) onValidate(validation.valid, trimmed);
        if (trimmed) {
          updateValue(trimmed);
        } else {
          updateValue(null);
        }
      }

      // Cacher les suggestions
      setTimeout(() => setShowSuggestionsList(false), 200);

      if (onBlur) onBlur();
    }, [
      isMulti,
      displayValue,
      separator,
      validateEmails,
      validateEmail,
      onValidate,
      updateValue,
      disableTrim,
      onBlur,
    ]);

    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        if (isMulti) {
          // Ajouter l'email en cours
          const rawValue = displayValue.trim();
          if (rawValue) {
            const currentEmails = isMulti ? (Array.isArray(value) ? value : []) : [];
            const newEmails = [...currentEmails, rawValue];
            updateValue(newEmails);
            setDisplayValue('');
          }
        } else {
          inputRefInternal.current?.blur();
        }
      } else if (e.key === 'Escape') {
        e.preventDefault();
        inputRefInternal.current?.blur();
      } else if (e.key === 'Backspace' && isMulti && displayValue === '') {
        // Supprimer le dernier email
        const currentEmails = isMulti ? (Array.isArray(value) ? value : []) : [];
        if (currentEmails.length > 0) {
          const newEmails = currentEmails.slice(0, -1);
          updateValue(newEmails);
        }
      }
    }, [isMulti, displayValue, value, updateValue]);

    // ========================================================================
    // GESTION DES SUGGESTIONS
    // ========================================================================

    const handleSuggestionClick = useCallback((suggestion: EmailSuggestion) => {
      if (isMulti) {
        const currentEmails = Array.isArray(value) ? value : [];
        const newEmails = [...currentEmails, suggestion.email];
        updateValue(newEmails);
        setDisplayValue('');
      } else {
        updateValue(suggestion.email);
        setDisplayValue(suggestion.email);
      }
      setShowSuggestionsList(false);
      inputRefInternal.current?.focus();

      toast({
        title: 'Email suggéré',
        description: suggestion.reason || `Email ${suggestion.email} utilisé`,
        duration: 2000,
      });
    }, [isMulti, value, updateValue, toast]);

    // ========================================================================
    // SUPPRESSION D'EMAIL (multi)
    // ========================================================================

    const handleRemoveEmail = useCallback((emailToRemove: string) => {
      if (!isMulti) return;
      const currentEmails = Array.isArray(value) ? value : [];
      const newEmails = currentEmails.filter(e => e !== emailToRemove);
      updateValue(newEmails);
    }, [isMulti, value, updateValue]);

    // ========================================================================
    // SYNC AVEC LA VALEUR EXTERNE
    // ========================================================================

    useEffect(() => {
      if (externalValue !== undefined) {
        const val = externalValue;
        if (JSON.stringify(val) !== JSON.stringify(prevValueRef.current)) {
          prevValueRef.current = val;
          if (isMulti) {
            const emails = Array.isArray(val) ? val : [];
            setDisplayValue(emails.join(separator));
            setEmailCount(emails.length);
          } else {
            setDisplayValue(val ? String(val) : '');
          }
        }
      }
    }, [externalValue, isMulti, separator]);

    // ========================================================================
    // INITIALISATION
    // ========================================================================

    useEffect(() => {
      if (defaultValue !== undefined && !isControlled) {
        if (isMulti) {
          const emails = Array.isArray(defaultValue) ? defaultValue : [];
          setDisplayValue(emails.join(separator));
          setEmailCount(emails.length);
          updateValue(emails);
        } else {
          const email = defaultValue ? String(defaultValue) : '';
          setDisplayValue(email);
          updateValue(email);
        }
      }
    }, [defaultValue, isMulti, separator, updateValue, isControlled]);

    // ========================================================================
    // IMPERATIVE HANDLE
    // ========================================================================

    useImperativeHandle(ref, () => ({
      focus: () => inputRefInternal.current?.focus(),
      blur: () => inputRefInternal.current?.blur(),
      select: () => inputRefInternal.current?.select(),
      getValue: () => value,
      setValue: (val: string | string[] | null) => updateValue(val),
      addEmail: (email: string) => {
        if (isMulti) {
          const current = Array.isArray(value) ? value : [];
          updateValue([...current, email]);
        } else {
          updateValue(email);
        }
      },
      removeEmail: (email: string) => {
        if (isMulti) {
          const current = Array.isArray(value) ? value : [];
          updateValue(current.filter(e => e !== email));
        }
      },
      validate: () => {
        const emails = isMulti ? (Array.isArray(value) ? value : []) : (value ? [String(value)] : []);
        const validation = validateEmails(emails);
        setIsValid(validation.valid);
        setValidationMessage(validation.messages.join('; '));
        return validation.valid;
      },
    } as any));

    // ========================================================================
    // RENDU
    // ========================================================================

    const hasError = !!error || !isValid || (required && emailCount === 0);
    const isSuccess = !hasError && success && value && (isMulti ? (Array.isArray(value) && value.length > 0) : !!value);

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
            {showEmailCount && isMulti && (
              <Badge variant="outline" size="sm">
                {emailCount} / {maxEmails}
              </Badge>
            )}
          </div>
        )}

        {/* Champ de saisie */}
        <div className="relative">
          <div className={cn(
            'relative flex flex-wrap items-center gap-1 rounded-lg border transition-all',
            hasError 
              ? 'border-red-500 ring-2 ring-red-500/20 dark:border-red-400' 
              : isSuccess && !disabled
              ? 'border-green-500 ring-2 ring-green-500/20 dark:border-green-400'
              : isFocused
              ? 'border-brand-500 ring-2 ring-brand-500/20 dark:border-brand-400'
              : 'border-gray-300 dark:border-gray-600',
            disabled && 'opacity-50 cursor-not-allowed bg-gray-50 dark:bg-gray-800/50',
            isMulti && 'min-h-[42px] p-1'
          )}>
            {/* Badges des emails (multi) */}
            {isMulti && showEmailBadges && Array.isArray(value) && value.map((email) => (
              <Badge
                key={email}
                variant="primary"
                className="flex items-center gap-1 ml-1 my-0.5"
              >
                <EnvelopeIcon className="h-3 w-3" />
                {email}
                <button
                  type="button"
                  onClick={() => handleRemoveEmail(email)}
                  className="ml-0.5 rounded-full hover:bg-brand-600/20 p-0.5"
                  disabled={disabled}
                >
                  <XMarkIcon className="h-3 w-3" />
                </button>
              </Badge>
            ))}

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
              inputMode="email"
              className={cn(
                'flex-1 bg-transparent px-2 py-2 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 outline-none min-w-[120px]',
                disabled && 'cursor-not-allowed',
                isMulti && 'py-1.5'
              )}
              placeholder={isMulti && Array.isArray(value) && value.length > 0 ? '' : placeholder}
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
              autoComplete="email"
            />

            {/* Icônes */}
            <div className="flex items-center gap-1 pr-2">
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

          {/* Suggestions */}
          {showSuggestions && showSuggestionsList && suggestions.length > 0 && !disabled && (
            <Popover
              open={showSuggestionsList}
              onOpenChange={setShowSuggestionsList}
              trigger={<div className="hidden" />}
              placement="bottom-start"
              className="z-50"
            >
              <div className="rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-lg p-1 min-w-[200px]">
                <div className="px-3 py-1.5 text-xs font-medium text-gray-500 dark:text-gray-400">
                  Suggestions
                </div>
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion.email}
                    type="button"
                    className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
                    onClick={() => handleSuggestionClick(suggestion)}
                  >
                    <EnvelopeIcon className="h-4 w-4 text-gray-400" />
                    <span className="flex-1 text-left">{suggestion.email}</span>
                    <span className="text-xs text-gray-400">
                      {Math.round(suggestion.confidence * 100)}%
                    </span>
                    {suggestion.reason && (
                      <Tooltip content={suggestion.reason}>
                        <InformationCircleIcon className="h-3 w-3 text-gray-400" />
                      </Tooltip>
                    )}
                  </button>
                ))}
              </div>
            </Popover>
          )}

          {/* Statut */}
          <div className="mt-1 flex items-center gap-1.5 text-xs flex-wrap">
            {hasError && (
              <span className="text-red-600 dark:text-red-400">
                {error || validationMessage || 'Email invalide'}
              </span>
            )}
            {success && !hasError && (
              <span className="text-green-600 dark:text-green-400">{success}</span>
            )}
            {info && !hasError && !success && (
              <span className="text-blue-600 dark:text-blue-400">{info}</span>
            )}
            {duplicates.length > 0 && !hasError && (
              <span className="text-yellow-600 dark:text-yellow-400">
                Doublons: {duplicates.join(', ')}
              </span>
            )}
          </div>
        </div>

        {/* Description */}
        {description && (
          <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
        )}

        {/* Domaines autorisés */}
        {allowedDomains.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {allowedDomains.map((domain) => (
              <Badge key={domain} variant="outline" size="xs" className="text-xs">
                @{domain}
              </Badge>
            ))}
          </div>
        )}
      </div>
    );
  }
);

EmailField.displayName = 'EmailField';

// ============================================================================
// EXPORTS
// ============================================================================

export default EmailField;

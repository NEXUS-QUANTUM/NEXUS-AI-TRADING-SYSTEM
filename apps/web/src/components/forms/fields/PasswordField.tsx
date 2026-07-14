// apps/web/src/components/forms/fields/PasswordField.tsx
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
  EyeIcon,
  EyeSlashIcon,
  LockClosedIcon,
  KeyIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  XMarkIcon,
  CheckIcon,
  ArrowPathIcon,
  ShieldCheckIcon,
  ExclamationCircleIcon,
  FingerPrintIcon,
  ClipboardIcon,
  DocumentDuplicateIcon,
  ArrowPathIcon as RefreshIcon,
  PlusIcon,
  MinusIcon,
  ChevronDownIcon,
  ChevronUpIcon,
} from '@heroicons/react/24/outline';
import {
  CheckCircleIcon as CheckCircleSolid,
  ExclamationCircleIcon as ExclamationCircleSolid,
} from '@heroicons/react/24/solid';
import { Label } from '@/components/common/Label';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Progress } from '@/components/common/Progress';
import { Tooltip } from '@/components/common/Tooltip';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type PasswordStrength = 'none' | 'weak' | 'medium' | 'strong' | 'very-strong';
export type PasswordValidationLevel = 'basic' | 'standard' | 'strict' | 'custom';
export type PasswordFieldVariant = 'default' | 'compact' | 'minimal' | 'rounded' | 'outlined';
export type PasswordVisibility = 'toggle' | 'reveal' | 'hidden' | 'always';

export interface PasswordFieldProps {
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
  variant?: PasswordFieldVariant;
  /** Afficher l'indicateur de force */
  showStrength?: boolean;
  /** Afficher les exigences */
  showRequirements?: boolean;
  /** Afficher l'icône de validation */
  showValidationIcon?: boolean;
  /** Afficher le générateur */
  showGenerator?: boolean;
  /** Afficher le bouton de copie */
  showCopyButton?: boolean;

  // --- Comportement ---
  /** Visibilité du mot de passe */
  visibility?: PasswordVisibility;
  /** Désactiver le champ */
  disabled?: boolean;
  /** Rendre le champ obligatoire */
  required?: boolean;
  /** Longueur minimale */
  minLength?: number;
  /** Longueur maximale */
  maxLength?: number;
  /** Exiger une majuscule */
  requireUppercase?: boolean;
  /** Exiger une minuscule */
  requireLowercase?: boolean;
  /** Exiger un chiffre */
  requireNumber?: boolean;
  /** Exiger un caractère spécial */
  requireSpecial?: boolean;
  /** Exiger un caractère spécial */
  specialCharacters?: string;
  /** Désactiver la validation en temps réel */
  disableRealtimeValidation?: boolean;
  /** Niveau de validation */
  validationLevel?: PasswordValidationLevel;
  /** Validation personnalisée */
  validatePassword?: (password: string) => boolean | string;

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
  customFormat?: (password: string) => string;
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

const DEFAULT_MIN_LENGTH = 8;
const DEFAULT_MAX_LENGTH = 128;
const SPECIAL_CHARACTERS = '!@#$%^&*()_+-=[]{}|;:,.<>?';

const STRENGTH_LABELS: Record<PasswordStrength, { label: string; color: string; score: number }> = {
  'none': { label: 'Non défini', color: 'bg-gray-200 dark:bg-gray-700', score: 0 },
  'weak': { label: 'Faible', color: 'bg-red-500', score: 25 },
  'medium': { label: 'Moyen', color: 'bg-yellow-500', score: 50 },
  'strong': { label: 'Fort', color: 'bg-green-500', score: 75 },
  'very-strong': { label: 'Très fort', color: 'bg-emerald-500', score: 100 },
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const PasswordField = forwardRef<HTMLInputElement, PasswordFieldProps>(
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
      label = 'Mot de passe',
      placeholder = 'Entrez votre mot de passe',
      description,
      error,
      success,
      info,
      variant = 'default',
      showStrength = true,
      showRequirements = true,
      showValidationIcon = true,
      showGenerator = true,
      showCopyButton = true,

      // Comportement
      visibility = 'toggle',
      disabled = false,
      required = false,
      minLength = DEFAULT_MIN_LENGTH,
      maxLength = DEFAULT_MAX_LENGTH,
      requireUppercase = true,
      requireLowercase = true,
      requireNumber = true,
      requireSpecial = true,
      specialCharacters = SPECIAL_CHARACTERS,
      disableRealtimeValidation = false,
      validationLevel = 'standard',
      validatePassword: customValidatePassword,

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
    const [isVisible, setIsVisible] = useState(visibility === 'always');
    const [strength, setStrength] = useState<PasswordStrength>('none');
    const [requirements, setRequirements] = useState({
      length: false,
      uppercase: false,
      lowercase: false,
      number: false,
      special: false,
    });
    const [generatedPassword, setGeneratedPassword] = useState<string | null>(null);
    const [isGenerating, setIsGenerating] = useState(false);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const value = externalValue !== undefined ? externalValue : internalValue;
    const isControlled = externalValue !== undefined;
    const hasValue = value && value.length > 0;

    // ========================================================================
    // CALCUL DE LA FORCE
    // ========================================================================

    const calculateStrength = useCallback((password: string): PasswordStrength => {
      if (!password) return 'none';

      let score = 0;
      const checks = {
        length: password.length >= minLength,
        uppercase: /[A-Z]/.test(password),
        lowercase: /[a-z]/.test(password),
        number: /[0-9]/.test(password),
        special: new RegExp(`[${specialCharacters.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}]`).test(password),
      };

      // Mettre à jour les exigences
      setRequirements(checks);

      // Score
      if (checks.length) score += 20;
      if (password.length >= minLength + 4) score += 10;
      if (checks.uppercase) score += 15;
      if (checks.lowercase) score += 15;
      if (checks.number) score += 15;
      if (checks.special) score += 25;

      // Bonus pour la longueur
      if (password.length >= 16) score += 10;
      if (password.length >= 24) score += 10;

      // Pénalité pour les motifs courants
      if (/(.)\1{2,}/.test(password)) score -= 10;
      if (/^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$/.test(password)) score += 10;

      // Déterminer le niveau
      if (score >= 90) return 'very-strong';
      if (score >= 70) return 'strong';
      if (score >= 45) return 'medium';
      if (score >= 20) return 'weak';
      return 'none';
    }, [minLength, specialCharacters]);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validatePassword = useCallback((password: string | null): { valid: boolean; message: string } => {
      if (customValidatePassword) {
        const result = customValidatePassword(password || '');
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        return { valid: true, message: '' };
      }

      if (!password) {
        if (required) {
          return { valid: false, message: 'Le mot de passe est requis' };
        }
        return { valid: true, message: '' };
      }

      // Validation basique
      if (password.length < minLength) {
        return { valid: false, message: `Le mot de passe doit contenir au moins ${minLength} caractères` };
      }

      if (password.length > maxLength) {
        return { valid: false, message: `Le mot de passe ne doit pas dépasser ${maxLength} caractères` };
      }

      // Validation standard
      if (validationLevel === 'standard' || validationLevel === 'strict') {
        if (requireUppercase && !/[A-Z]/.test(password)) {
          return { valid: false, message: 'Le mot de passe doit contenir au moins une majuscule' };
        }
        if (requireLowercase && !/[a-z]/.test(password)) {
          return { valid: false, message: 'Le mot de passe doit contenir au moins une minuscule' };
        }
        if (requireNumber && !/[0-9]/.test(password)) {
          return { valid: false, message: 'Le mot de passe doit contenir au moins un chiffre' };
        }
        if (requireSpecial && !new RegExp(`[${specialCharacters.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}]`).test(password)) {
          return { valid: false, message: 'Le mot de passe doit contenir au moins un caractère spécial' };
        }
      }

      // Validation stricte
      if (validationLevel === 'strict') {
        // Pas d'espaces
        if (/\s/.test(password)) {
          return { valid: false, message: 'Le mot de passe ne doit pas contenir d\'espaces' };
        }
        // Pas de motifs courants
        const commonPatterns = ['123456', 'password', 'qwerty', 'azerty', 'admin', 'letmein'];
        if (commonPatterns.some(pattern => password.toLowerCase().includes(pattern))) {
          return { valid: false, message: 'Le mot de passe contient un motif trop commun' };
        }
        // Pas de répétition excessive
        if (/(.)\1{4,}/.test(password)) {
          return { valid: false, message: 'Le mot de passe contient trop de caractères identiques consécutifs' };
        }
      }

      return { valid: true, message: '' };
    }, [
      customValidatePassword,
      required,
      minLength,
      maxLength,
      validationLevel,
      requireUppercase,
      requireLowercase,
      requireNumber,
      requireSpecial,
      specialCharacters,
    ]);

    // ========================================================================
    // GÉNÉRATEUR DE MOT DE PASSE
    // ========================================================================

    const generatePassword = useCallback(() => {
      const length = Math.max(minLength, 16);
      const charset = {
        lowercase: 'abcdefghijklmnopqrstuvwxyz',
        uppercase: 'ABCDEFGHIJKLMNOPQRSTUVWXYZ',
        numbers: '0123456789',
        special: specialCharacters,
      };

      let password = '';
      const allChars = charset.lowercase + charset.uppercase + charset.numbers + charset.special;

      // S'assurer qu'au moins un de chaque type est présent
      if (requireLowercase) password += charset.lowercase[Math.floor(Math.random() * charset.lowercase.length)];
      if (requireUppercase) password += charset.uppercase[Math.floor(Math.random() * charset.uppercase.length)];
      if (requireNumber) password += charset.numbers[Math.floor(Math.random() * charset.numbers.length)];
      if (requireSpecial) password += charset.special[Math.floor(Math.random() * charset.special.length)];

      // Remplir le reste
      for (let i = password.length; i < length; i++) {
        password += allChars[Math.floor(Math.random() * allChars.length)];
      }

      // Mélanger
      password = password.split('').sort(() => Math.random() - 0.5).join('');

      return password;
    }, [minLength, requireLowercase, requireUppercase, requireNumber, requireSpecial, specialCharacters]);

    const handleGenerate = useCallback(() => {
      setIsGenerating(true);
      setTimeout(() => {
        const newPassword = generatePassword();
        setGeneratedPassword(newPassword);
        updateValue(newPassword);
        setIsGenerating(false);
        toast({
          title: 'Mot de passe généré',
          description: 'Un mot de passe sécurisé a été créé',
          duration: 3000,
        });
      }, 300);
    }, [generatePassword, updateValue, toast]);

    const handleCopy = useCallback(() => {
      if (value) {
        navigator.clipboard.writeText(value);
        toast({
          title: 'Copié',
          description: 'Le mot de passe a été copié dans le presse-papier',
          duration: 2000,
        });
      }
    }, [value, toast]);

    // ========================================================================
    // MISE À JOUR DE LA VALEUR
    // ========================================================================

    const updateValue = useCallback((newValue: string | null) => {
      const validation = validatePassword(newValue);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);

      if (showStrength && newValue) {
        setStrength(calculateStrength(newValue));
      } else {
        setStrength('none');
      }

      if (!disableRealtimeValidation && onValidate) {
        onValidate(validation.valid, newValue);
      }

      if (isControlled) {
        if (onChange) onChange(newValue);
      } else {
        setInternalValue(newValue);
        if (onChange) onChange(newValue);
      }

      setDisplayValue(newValue || '');

      if (debug) {
        console.log('PasswordField update:', { newValue, isValid: validation.valid });
      }
    }, [
      validatePassword,
      showStrength,
      calculateStrength,
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

      if (!disableRealtimeValidation) {
        const validation = validatePassword(rawValue);
        setIsValid(validation.valid);
        setValidationMessage(validation.message);
        if (onValidate) onValidate(validation.valid, rawValue);
      }

      if (showStrength && rawValue) {
        setStrength(calculateStrength(rawValue));
      } else {
        setStrength('none');
      }
    }, [disableRealtimeValidation, validatePassword, onValidate, showStrength, calculateStrength]);

    const handleFocus = useCallback(() => {
      setIsFocused(true);
      if (onFocus) onFocus();
    }, [onFocus]);

    const handleBlur = useCallback(() => {
      setIsFocused(false);

      const trimmed = displayValue.trim();
      const validation = validatePassword(trimmed);
      setIsValid(validation.valid);
      setValidationMessage(validation.message);
      if (onValidate) onValidate(validation.valid, trimmed);

      if (validation.valid && trimmed) {
        updateValue(trimmed);
      } else if (!trimmed) {
        updateValue(null);
      } else {
        setDisplayValue(value || '');
      }

      if (onBlur) onBlur();
    }, [displayValue, validatePassword, onValidate, updateValue, value, onBlur]);

    const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const trimmed = displayValue.trim();
        const validation = validatePassword(trimmed);
        if (validation.valid) {
          updateValue(trimmed);
        }
        inputRefInternal.current?.blur();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        setDisplayValue(value || '');
        inputRefInternal.current?.blur();
      }
    }, [displayValue, validatePassword, updateValue, value]);

    const toggleVisibility = useCallback(() => {
      if (visibility === 'toggle') {
        setIsVisible(!isVisible);
      }
    }, [isVisible, visibility]);

    // ========================================================================
    // SYNC AVEC LA VALEUR EXTERNE
    // ========================================================================

    useEffect(() => {
      if (externalValue !== undefined && externalValue !== prevValueRef.current) {
        prevValueRef.current = externalValue;
        setDisplayValue(externalValue || '');
        if (externalValue) {
          const validation = validatePassword(externalValue);
          setIsValid(validation.valid);
          setValidationMessage(validation.message);
          if (showStrength) {
            setStrength(calculateStrength(externalValue));
          }
        } else {
          setStrength('none');
        }
      }
    }, [externalValue, validatePassword, showStrength, calculateStrength]);

    // ========================================================================
    // INITIALISATION
    // ========================================================================

    useEffect(() => {
      if (defaultValue !== undefined && !isControlled) {
        const val = defaultValue;
        setDisplayValue(val || '');
        if (val) {
          const validation = validatePassword(val);
          setIsValid(validation.valid);
          setValidationMessage(validation.message);
          if (showStrength) {
            setStrength(calculateStrength(val));
          }
        }
        updateValue(val);
      }
    }, [defaultValue, updateValue, isControlled, validatePassword, showStrength, calculateStrength]);

    // ========================================================================
    // IMPERATIVE HANDLE
    // ========================================================================

    useImperativeHandle(ref, () => ({
      focus: () => inputRefInternal.current?.focus(),
      blur: () => inputRefInternal.current?.blur(),
      select: () => inputRefInternal.current?.select(),
      getValue: () => value,
      setValue: (val: string | null) => updateValue(val),
      generate: () => handleGenerate(),
      validate: () => {
        const validation = validatePassword(displayValue);
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
    const strengthInfo = STRENGTH_LABELS[strength] || STRENGTH_LABELS.none;

    const variantClasses = {
      default: 'border-gray-300 dark:border-gray-600',
      compact: 'border-gray-300 dark:border-gray-600 h-8 text-xs',
      minimal: 'border-b-2 border-gray-300 dark:border-gray-600 rounded-none',
      rounded: 'border-gray-300 dark:border-gray-600 rounded-full',
      outlined: 'border-2 border-gray-300 dark:border-gray-600',
    };

    const showPassword = visibility === 'always' || (visibility === 'toggle' && isVisible);

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
            {showStrength && value && (
              <Badge 
                variant="outline" 
                size="sm" 
                className={cn(
                  'text-xs',
                  strength === 'weak' && 'text-red-500 border-red-200 dark:border-red-800',
                  strength === 'medium' && 'text-yellow-500 border-yellow-200 dark:border-yellow-800',
                  strength === 'strong' && 'text-green-500 border-green-200 dark:border-green-800',
                  strength === 'very-strong' && 'text-emerald-500 border-emerald-200 dark:border-emerald-800'
                )}
              >
                {strengthInfo.label}
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
            <LockClosedIcon className="absolute left-3 h-4 w-4 text-gray-400" />

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
              type={showPassword ? 'text' : 'password'}
              className={cn(
                'w-full bg-transparent pl-9 pr-12 py-2 text-gray-900 dark:text-white placeholder-gray-400 dark:placeholder-gray-500 outline-none',
                disabled && 'cursor-not-allowed',
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
              autoComplete="current-password"
              maxLength={maxLength}
            />

            {/* Actions */}
            <div className="absolute right-1 flex items-center gap-0.5">
              {showGenerator && !disabled && (
                <Tooltip content="Générer un mot de passe">
                  <button
                    type="button"
                    onClick={handleGenerate}
                    className="rounded p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                    disabled={isGenerating}
                  >
                    <RefreshIcon className={cn('h-4 w-4', isGenerating && 'animate-spin')} />
                  </button>
                </Tooltip>
              )}

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

              {visibility === 'toggle' && !disabled && (
                <Tooltip content={isVisible ? 'Masquer' : 'Afficher'}>
                  <button
                    type="button"
                    onClick={toggleVisibility}
                    className="rounded p-1.5 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                  >
                    {isVisible ? (
                      <EyeSlashIcon className="h-4 w-4" />
                    ) : (
                      <EyeIcon className="h-4 w-4" />
                    )}
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
          </div>
        </div>

        {/* Indicateur de force */}
        {showStrength && value && (
          <div className="space-y-1">
            <Progress
              value={strengthInfo.score}
              className="h-1"
              variant={
                strength === 'weak' ? 'error' :
                strength === 'medium' ? 'warning' :
                strength === 'strong' ? 'success' :
                'default'
              }
            />
          </div>
        )}

        {/* Exigences */}
        {showRequirements && value && (
          <div className="mt-1 grid grid-cols-1 gap-0.5 text-xs sm:grid-cols-2">
            <div className={cn(
              'flex items-center gap-1',
              requirements.length ? 'text-green-600 dark:text-green-400' : 'text-gray-400 dark:text-gray-500'
            )}>
              {requirements.length ? (
                <CheckIcon className="h-3 w-3" />
              ) : (
                <MinusIcon className="h-3 w-3" />
              )}
              <span>{minLength}+ caractères</span>
            </div>
            {requireUppercase && (
              <div className={cn(
                'flex items-center gap-1',
                requirements.uppercase ? 'text-green-600 dark:text-green-400' : 'text-gray-400 dark:text-gray-500'
              )}>
                {requirements.uppercase ? (
                  <CheckIcon className="h-3 w-3" />
                ) : (
                  <MinusIcon className="h-3 w-3" />
                )}
                <span>Une majuscule</span>
              </div>
            )}
            {requireLowercase && (
              <div className={cn(
                'flex items-center gap-1',
                requirements.lowercase ? 'text-green-600 dark:text-green-400' : 'text-gray-400 dark:text-gray-500'
              )}>
                {requirements.lowercase ? (
                  <CheckIcon className="h-3 w-3" />
                ) : (
                  <MinusIcon className="h-3 w-3" />
                )}
                <span>Une minuscule</span>
              </div>
            )}
            {requireNumber && (
              <div className={cn(
                'flex items-center gap-1',
                requirements.number ? 'text-green-600 dark:text-green-400' : 'text-gray-400 dark:text-gray-500'
              )}>
                {requirements.number ? (
                  <CheckIcon className="h-3 w-3" />
                ) : (
                  <MinusIcon className="h-3 w-3" />
                )}
                <span>Un chiffre</span>
              </div>
            )}
            {requireSpecial && (
              <div className={cn(
                'flex items-center gap-1',
                requirements.special ? 'text-green-600 dark:text-green-400' : 'text-gray-400 dark:text-gray-500'
              )}>
                {requirements.special ? (
                  <CheckIcon className="h-3 w-3" />
                ) : (
                  <MinusIcon className="h-3 w-3" />
                )}
                <span>Caractère spécial</span>
              </div>
            )}
          </div>
        )}

        {/* Description */}
        {description && (
          <p className="text-xs text-gray-500 dark:text-gray-400">{description}</p>
        )}
      </div>
    );
  }
);

PasswordField.displayName = 'PasswordField';

// ============================================================================
// EXPORTS
// ============================================================================

export default PasswordField;

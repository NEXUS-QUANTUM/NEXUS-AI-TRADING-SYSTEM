// apps/web/src/components/forms/hooks/useFormValidation.ts
'use client';

import {
  useState,
  useCallback,
  useRef,
  useEffect,
  useMemo,
} from 'react';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type ValidationRule<T = any> = {
  /** Si le champ est requis */
  required?: boolean | ((values: any) => boolean);
  /** Message d'erreur pour requis */
  requiredMessage?: string;
  /** Longueur minimale (pour les chaînes) */
  minLength?: number | ((values: any) => number);
  /** Message d'erreur pour minLength */
  minLengthMessage?: string;
  /** Longueur maximale (pour les chaînes) */
  maxLength?: number | ((values: any) => number);
  /** Message d'erreur pour maxLength */
  maxLengthMessage?: string;
  /** Valeur minimale (pour les nombres) */
  min?: number | ((values: any) => number);
  /** Message d'erreur pour min */
  minMessage?: string;
  /** Valeur maximale (pour les nombres) */
  max?: number | ((values: any) => number);
  /** Message d'erreur pour max */
  maxMessage?: string;
  /** Pattern regex */
  pattern?: RegExp | ((values: any) => RegExp);
  /** Message d'erreur pour pattern */
  patternMessage?: string;
  /** Validation personnalisée */
  custom?: (value: any, values: any) => boolean | string | Promise<boolean | string>;
  /** Dépendances pour la validation */
  dependsOn?: string[];
  /** Validation asynchrone */
  async?: (value: any, values: any) => Promise<boolean | string>;
  /** Message pour validation asynchrone */
  asyncMessage?: string;
  /** Délai de débounce pour validation asynchrone (ms) */
  asyncDebounce?: number;
};

export type FieldValidation<T = any> = {
  /** Règles de validation */
  rules?: ValidationRule<T>;
  /** Label du champ (pour les messages) */
  label?: string;
  /** Désactiver la validation */
  disabled?: boolean;
};

export type FormValidationConfig<T extends Record<string, any> = Record<string, any>> = {
  /** Configuration des champs */
  fields: {
    [K in keyof T]?: FieldValidation<T[K]>;
  };
  /** Validation globale du formulaire */
  validate?: (values: T) => Partial<Record<keyof T, string>> | Promise<Partial<Record<keyof T, string>>>;
  /** Mode de validation */
  mode?: 'onChange' | 'onBlur' | 'onSubmit' | 'onTouched' | 'manual';
  /** Désactiver la validation automatique */
  disableAutoValidation?: boolean;
  /** Délai de débounce (ms) */
  debounceDelay?: number;
  /** Callback de validation */
  onValidate?: (isValid: boolean, errors: Partial<Record<keyof T, string>>) => void;
};

export type UseFormValidationReturn<T extends Record<string, any> = Record<string, any>> = {
  /** Erreurs du formulaire */
  errors: Partial<Record<keyof T, string>>;
  /** Est-ce que le formulaire est valide */
  isValid: boolean;
  /** Est-ce que la validation est en cours */
  isValidating: boolean;
  /** Est-ce que le formulaire a été validé */
  isValidated: boolean;
  /** Champ en cours de validation */
  validatingField: keyof T | null;
  /** Valider le formulaire */
  validate: (values?: T) => Promise<boolean>;
  /** Valider un champ spécifique */
  validateField: <K extends keyof T>(field: K, value: T[K], allValues?: T) => Promise<boolean>;
  /** Réinitialiser les erreurs */
  reset: () => void;
  /** Effacer les erreurs d'un champ */
  clearFieldError: <K extends keyof T>(field: K) => void;
  /** Définir les erreurs manuellement */
  setErrors: (errors: Partial<Record<keyof T, string>>) => void;
  /** Ajouter une erreur à un champ */
  setFieldError: <K extends keyof T>(field: K, error: string) => void;
  /** Obtenir les erreurs d'un champ */
  getFieldError: <K extends keyof T>(field: K) => string | undefined;
  /** Écouter les changements de validation */
  onValidationChange: (callback: (isValid: boolean, errors: Partial<Record<keyof T, string>>) => void) => () => void;
  /** Mode débogage */
  debug: () => void;
};

// ============================================================================
// CONSTANTES
// ============================================================================

const DEFAULT_DEBOUNCE_DELAY = 300;
const DEFAULT_MODE = 'onChange';

// ============================================================================
// HOOK PRINCIPAL
// ============================================================================

export function useFormValidation<T extends Record<string, any> = Record<string, any>>(
  config: FormValidationConfig<T>
): UseFormValidationReturn<T> {
  const {
    fields = {},
    validate: customValidate,
    mode = DEFAULT_MODE,
    disableAutoValidation = false,
    debounceDelay = DEFAULT_DEBOUNCE_DELAY,
    onValidate,
  } = config;

  // ========================================================================
  // TOAST
  // ========================================================================

  const { toast } = useToast();

  // ========================================================================
  // RÉFÉRENCES
  // ========================================================================

  const isMountedRef = useRef(true);
  const debounceTimerRef = useRef<Record<string, NodeJS.Timeout | null>>({});
  const asyncTimerRef = useRef<Record<string, NodeJS.Timeout | null>>({});
  const validationCallbacksRef = useRef<((isValid: boolean, errors: Partial<Record<keyof T, string>>) => void)[]>([]);
  const currentValuesRef = useRef<T>({} as T);
  const pendingValidationsRef = useRef<Record<string, Promise<boolean>>>({});

  // ========================================================================
  // ÉTATS
  // ========================================================================

  const [errors, setErrors] = useState<Partial<Record<keyof T, string>>>({});
  const [isValid, setIsValid] = useState<boolean>(true);
  const [isValidating, setIsValidating] = useState<boolean>(false);
  const [isValidated, setIsValidated] = useState<boolean>(false);
  const [validatingField, setValidatingField] = useState<keyof T | null>(null);

  // ========================================================================
  // VALIDATION D'UN CHAMP
  // ========================================================================

  const validateValue = useCallback(async (
    value: any,
    rules: ValidationRule,
    allValues: T,
    fieldName: string,
    label?: string
  ): Promise<string | undefined> => {
    const fieldLabel = label || fieldName;

    // Required
    if (rules.required) {
      const isRequired = typeof rules.required === 'function' 
        ? rules.required(allValues) 
        : rules.required;
      
      if (isRequired) {
        if (value === undefined || value === null || value === '') {
          return rules.requiredMessage || `Le champ "${fieldLabel}" est requis`;
        }
        if (Array.isArray(value) && value.length === 0) {
          return rules.requiredMessage || `Le champ "${fieldLabel}" est requis`;
        }
      }
    }

    // MinLength (string)
    if (typeof value === 'string') {
      const minLength = typeof rules.minLength === 'function'
        ? rules.minLength(allValues)
        : rules.minLength;
      
      if (minLength !== undefined && value.length < minLength) {
        return rules.minLengthMessage || `Le champ "${fieldLabel}" doit contenir au moins ${minLength} caractères`;
      }

      const maxLength = typeof rules.maxLength === 'function'
        ? rules.maxLength(allValues)
        : rules.maxLength;
      
      if (maxLength !== undefined && value.length > maxLength) {
        return rules.maxLengthMessage || `Le champ "${fieldLabel}" ne doit pas dépasser ${maxLength} caractères`;
      }
    }

    // Min / Max (number)
    if (typeof value === 'number') {
      const min = typeof rules.min === 'function'
        ? rules.min(allValues)
        : rules.min;
      
      if (min !== undefined && value < min) {
        return rules.minMessage || `La valeur minimale pour "${fieldLabel}" est ${min}`;
      }

      const max = typeof rules.max === 'function'
        ? rules.max(allValues)
        : rules.max;
      
      if (max !== undefined && value > max) {
        return rules.maxMessage || `La valeur maximale pour "${fieldLabel}" est ${max}`;
      }
    }

    // Pattern
    if (typeof value === 'string') {
      const pattern = typeof rules.pattern === 'function'
        ? rules.pattern(allValues)
        : rules.pattern;
      
      if (pattern && !pattern.test(value)) {
        return rules.patternMessage || `Le champ "${fieldLabel}" a un format invalide`;
      }
    }

    // Custom validation (synchrone)
    if (rules.custom) {
      const result = rules.custom(value, allValues);
      if (typeof result === 'string') {
        return result;
      }
      if (result === false) {
        return `Le champ "${fieldLabel}" est invalide`;
      }
    }

    // Async validation
    if (rules.async) {
      const debounce = rules.asyncDebounce || debounceDelay;
      
      return new Promise<string | undefined>((resolve) => {
        if (asyncTimerRef.current[fieldName]) {
          clearTimeout(asyncTimerRef.current[fieldName]!);
        }

        asyncTimerRef.current[fieldName] = setTimeout(async () => {
          try {
            const result = await rules.async!(value, allValues);
            if (typeof result === 'string') {
              resolve(result);
            } else if (result === false) {
              resolve(rules.asyncMessage || `Le champ "${fieldLabel}" est invalide`);
            } else {
              resolve(undefined);
            }
          } catch (error) {
            resolve(error instanceof Error ? error.message : 'Erreur de validation');
          } finally {
            asyncTimerRef.current[fieldName] = null;
          }
        }, debounce);
      });
    }

    return undefined;
  }, [debounceDelay]);

  // ========================================================================
  // VALIDATION D'UN CHAMP SPÉCIFIQUE
  // ========================================================================

  const validateField = useCallback(async <K extends keyof T>(
    field: K,
    value: T[K],
    allValues: T = currentValuesRef.current
  ): Promise<boolean> => {
    const fieldConfig = fields[field];
    if (!fieldConfig || fieldConfig.disabled) {
      return true;
    }

    const rules = fieldConfig.rules || {};
    const label = fieldConfig.label;

    setValidatingField(field);
    setIsValidating(true);

    try {
      const error = await validateValue(value, rules, allValues, field as string, label);
      
      setErrors(prev => {
        const newErrors = { ...prev };
        if (error) {
          newErrors[field] = error;
        } else {
          delete newErrors[field];
        }
        return newErrors;
      });

      return !error;

    } finally {
      setValidatingField(null);
      setIsValidating(false);
    }
  }, [fields, validateValue]);

  // ========================================================================
  // VALIDATION DU FORMULAIRE COMPLET
  // ========================================================================

  const validate = useCallback(async (values?: T): Promise<boolean> => {
    const currentValues = values || currentValuesRef.current;
    currentValuesRef.current = currentValues;

    setIsValidating(true);
    const newErrors: Partial<Record<keyof T, string>> = {};

    try {
      // Validation personnalisée globale
      if (customValidate) {
        const customErrors = await customValidate(currentValues);
        Object.assign(newErrors, customErrors);
      }

      // Validation des champs
      const fieldPromises = Object.keys(fields)
        .filter(field => !fields[field]?.disabled)
        .map(async (field) => {
          const fieldKey = field as keyof T;
          const value = currentValues[fieldKey];
          const fieldConfig = fields[fieldKey];
          const rules = fieldConfig?.rules || {};
          const label = fieldConfig?.label;

          // Vérifier les dépendances
          if (rules.dependsOn) {
            const allDependenciesMet = rules.dependsOn.every(dep => {
              const depValue = currentValues[dep as keyof T];
              return depValue !== undefined && depValue !== null && depValue !== '';
            });
            if (!allDependenciesMet) {
              return;
            }
          }

          const error = await validateValue(value, rules, currentValues, field as string, label);
          if (error) {
            newErrors[fieldKey] = error;
          }
        });

      await Promise.all(fieldPromises);

      setErrors(newErrors);
      const isValid = Object.keys(newErrors).length === 0;
      setIsValid(isValid);
      setIsValidated(true);

      if (onValidate) {
        onValidate(isValid, newErrors);
      }

      // Notifier les callbacks
      validationCallbacksRef.current.forEach(callback => {
        callback(isValid, newErrors);
      });

      return isValid;

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Erreur de validation';
      toast({
        title: 'Erreur de validation',
        description: errorMessage,
        variant: 'destructive',
      });
      return false;

    } finally {
      setIsValidating(false);
    }
  }, [customValidate, fields, validateValue, onValidate, toast]);

  // ========================================================================
  // RÉINITIALISATION
  // ========================================================================

  const reset = useCallback(() => {
    setErrors({});
    setIsValid(true);
    setIsValidated(false);
    setIsValidating(false);
    setValidatingField(null);
    currentValuesRef.current = {} as T;

    // Nettoyer les timers
    Object.keys(debounceTimerRef.current).forEach(key => {
      if (debounceTimerRef.current[key]) {
        clearTimeout(debounceTimerRef.current[key]!);
        debounceTimerRef.current[key] = null;
      }
    });
    Object.keys(asyncTimerRef.current).forEach(key => {
      if (asyncTimerRef.current[key]) {
        clearTimeout(asyncTimerRef.current[key]!);
        asyncTimerRef.current[key] = null;
      }
    });
  }, []);

  // ========================================================================
  // GESTION DES ERREURS
  // ========================================================================

  const clearFieldError = useCallback(<K extends keyof T>(field: K) => {
    setErrors(prev => {
      const newErrors = { ...prev };
      delete newErrors[field];
      return newErrors;
    });
  }, []);

  const setErrors = useCallback((newErrors: Partial<Record<keyof T, string>>) => {
    setErrors(newErrors);
    const isValid = Object.keys(newErrors).length === 0;
    setIsValid(isValid);
  }, []);

  const setFieldError = useCallback(<K extends keyof T>(field: K, error: string) => {
    setErrors(prev => ({ ...prev, [field]: error }));
    setIsValid(false);
  }, []);

  const getFieldError = useCallback(<K extends keyof T>(field: K): string | undefined => {
    return errors[field];
  }, [errors]);

  // ========================================================================
  // OBSERVABILITÉ
  // ========================================================================

  const onValidationChange = useCallback((
    callback: (isValid: boolean, errors: Partial<Record<keyof T, string>>) => void
  ): (() => void) => {
    validationCallbacksRef.current.push(callback);
    return () => {
      validationCallbacksRef.current = validationCallbacksRef.current.filter(cb => cb !== callback);
    };
  }, []);

  // ========================================================================
  // DÉBOGAGE
  // ========================================================================

  const debug = useCallback(() => {
    console.group('🔍 Form Validation Debug');
    console.log('Errors:', errors);
    console.log('Is Valid:', isValid);
    console.log('Is Validating:', isValidating);
    console.log('Is Validated:', isValidated);
    console.log('Validating Field:', validatingField);
    console.log('Fields Config:', fields);
    console.groupEnd();
  }, [errors, isValid, isValidating, isValidated, validatingField, fields]);

  // ========================================================================
  // CLEANUP
  // ========================================================================

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      Object.values(debounceTimerRef.current).forEach(timer => {
        if (timer) clearTimeout(timer);
      });
      Object.values(asyncTimerRef.current).forEach(timer => {
        if (timer) clearTimeout(timer);
      });
    };
  }, []);

  // ========================================================================
  // RETOUR
  // ========================================================================

  return {
    errors,
    isValid,
    isValidating,
    isValidated,
    validatingField,
    validate,
    validateField,
    reset,
    clearFieldError,
    setErrors,
    setFieldError,
    getFieldError,
    onValidationChange,
    debug,
  };
}

// ============================================================================
// EXPORTS
// ============================================================================

export default useFormValidation;

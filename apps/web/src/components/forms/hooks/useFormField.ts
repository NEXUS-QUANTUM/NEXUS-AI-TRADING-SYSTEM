// apps/web/src/components/forms/hooks/useFormField.ts
'use client';

import {
  useState,
  useCallback,
  useRef,
  useEffect,
  useMemo,
  useId,
} from 'react';
import { useFormContext } from '@/components/forms/FormContext';

// ============================================================================
// TYPES
// ============================================================================

export type FieldValidationRule = {
  /** Si le champ est requis */
  required?: boolean;
  /** Message d'erreur pour requis */
  requiredMessage?: string;
  /** Longueur minimale (pour les chaînes) */
  minLength?: number;
  /** Message d'erreur pour minLength */
  minLengthMessage?: string;
  /** Longueur maximale (pour les chaînes) */
  maxLength?: number;
  /** Message d'erreur pour maxLength */
  maxLengthMessage?: string;
  /** Valeur minimale (pour les nombres) */
  min?: number;
  /** Message d'erreur pour min */
  minMessage?: string;
  /** Valeur maximale (pour les nombres) */
  max?: number;
  /** Message d'erreur pour max */
  maxMessage?: string;
  /** Pattern regex */
  pattern?: RegExp;
  /** Message d'erreur pour pattern */
  patternMessage?: string;
  /** Validation personnalisée */
  custom?: (value: any, allValues?: Record<string, any>) => boolean | string;
  /** Dépendances pour la validation */
  dependsOn?: string[];
};

export type FieldValidationResult = {
  /** Est-ce que le champ est valide */
  valid: boolean;
  /** Message d'erreur si invalide */
  message?: string;
};

export type UseFormFieldOptions<T = any> = {
  /** Nom du champ (chemin) */
  name: string;
  /** Valeur initiale */
  initialValue?: T;
  /** Règles de validation */
  rules?: FieldValidationRule;
  /** Désactiver le champ */
  disabled?: boolean;
  /** Rendre le champ obligatoire */
  required?: boolean;
  /** Label du champ */
  label?: string;
  /** Placeholder du champ */
  placeholder?: string;
  /** Description du champ */
  description?: string;
  /** Mode de validation */
  validationMode?: 'onChange' | 'onBlur' | 'onSubmit' | 'onTouched';
  /** Désactiver la validation automatique */
  disableAutoValidation?: boolean;
  /** Délai de débounce (ms) */
  debounceDelay?: number;
  /** Transformateur de valeur (avant validation) */
  transform?: (value: T) => T;
  /** Formateur de valeur (pour l'affichage) */
  format?: (value: T) => string;
  /** Parseur de valeur (pour la saisie) */
  parse?: (value: string) => T;
};

export type UseFormFieldReturn<T = any> = {
  /** Nom du champ */
  name: string;
  /** Valeur du champ */
  value: T;
  /** Définir la valeur du champ */
  setValue: (value: T) => void;
  /** Réinitialiser la valeur du champ */
  reset: () => void;
  /** Erreur du champ */
  error: string | undefined;
  /** Est-ce que le champ a été touché */
  touched: boolean;
  /** Marquer le champ comme touché */
  setTouched: (touched?: boolean) => void;
  /** Est-ce que le champ est valide */
  isValid: boolean;
  /** Est-ce que le champ est désactivé */
  isDisabled: boolean;
  /** Est-ce que le champ est obligatoire */
  isRequired: boolean;
  /** Est-ce que le champ est en cours de validation */
  isValidating: boolean;
  /** Est-ce que le champ est en focus */
  isFocused: boolean;
  /** Est-ce que le champ est hover */
  isHovered: boolean;
  /** ID du champ */
  id: string;
  /** ID de l'erreur */
  errorId: string;
  /** ID de la description */
  descriptionId: string;
  /** Validations */
  validate: () => Promise<boolean>;
  /** Gestionnaire de changement */
  onChange: (value: T | React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => void;
  /** Gestionnaire de blur */
  onBlur: () => void;
  /** Gestionnaire de focus */
  onFocus: () => void;
  /** Gestionnaire de mouse enter */
  onMouseEnter: () => void;
  /** Gestionnaire de mouse leave */
  onMouseLeave: () => void;
  /** Props pour l'input */
  getInputProps: () => {
    id: string;
    name: string;
    value: T;
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
    onBlur: () => void;
    onFocus: () => void;
    disabled: boolean;
    required: boolean;
    'aria-invalid': boolean;
    'aria-describedby': string;
  };
  /** Props pour le label */
  getLabelProps: () => {
    htmlFor: string;
    children: string | undefined;
  };
  /** Props pour le message d'erreur */
  getErrorProps: () => {
    id: string;
    role: 'alert';
    children: string | undefined;
  };
  /** Props pour la description */
  getDescriptionProps: () => {
    id: string;
    children: string | undefined;
  };
  /** Effectuer une action au montage */
  onMount: (callback: () => void) => void;
  /** Effectuer une action au démontage */
  onUnmount: (callback: () => void) => void;
  /** Mode débogage */
  debug: () => void;
};

// ============================================================================
// CONSTANTES
// ============================================================================

const DEFAULT_DEBOUNCE_DELAY = 300;
const DEFAULT_VALIDATION_MODE = 'onChange';

// ============================================================================
// HOOK PRINCIPAL
// ============================================================================

export function useFormField<T = any>(
  options: UseFormFieldOptions<T>
): UseFormFieldReturn<T> {
  const {
    name,
    initialValue = null as T,
    rules = {},
    disabled = false,
    required = false,
    label,
    placeholder,
    description,
    validationMode = DEFAULT_VALIDATION_MODE,
    disableAutoValidation = false,
    debounceDelay = DEFAULT_DEBOUNCE_DELAY,
    transform,
    format,
    parse,
  } = options;

  // ========================================================================
  // IDs
  // ========================================================================

  const uniqueId = useId();
  const fieldId = `field-${name}-${uniqueId}`;
  const errorId = `${fieldId}-error`;
  const descriptionId = `${fieldId}-description`;

  // ========================================================================
  // RÉFÉRENCES
  // ========================================================================

  const inputRef = useRef<HTMLInputElement>(null);
  const isMountedRef = useRef(true);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const mountCallbacksRef = useRef<(() => void)[]>([]);
  const unmountCallbacksRef = useRef<(() => void)[]>([]);
  const initialValueRef = useRef<T>(initialValue);

  // ========================================================================
  // CONTEXT (si disponible)
  // ========================================================================

  let formContext: any = null;
  try {
    formContext = useFormContext();
  } catch {
    // Pas de contexte, utiliser le state local
  }

  // ========================================================================
  // ÉTATS LOCAUX
  // ========================================================================

  const [internalValue, setInternalValue] = useState<T>(initialValue);
  const [localError, setLocalError] = useState<string | undefined>(undefined);
  const [touched, setTouchedState] = useState<boolean>(false);
  const [isFocused, setIsFocused] = useState<boolean>(false);
  const [isHovered, setIsHovered] = useState<boolean>(false);
  const [isValidating, setIsValidating] = useState<boolean>(false);
  const [isValid, setIsValid] = useState<boolean>(true);

  // ========================================================================
  // VALEUR
  // ========================================================================

  const value = formContext?.getValue(name) ?? internalValue;
  const setValue = useCallback(
    (newValue: T) => {
      const transformed = transform ? transform(newValue) : newValue;
      if (formContext) {
        formContext.setValue(name, transformed);
      } else {
        setInternalValue(transformed);
      }
    },
    [formContext, name, transform]
  );

  const reset = useCallback(() => {
    setValue(initialValueRef.current);
    if (formContext) {
      formContext.clearFieldError(name);
    } else {
      setLocalError(undefined);
    }
    setTouchedState(false);
  }, [setValue, formContext, name]);

  // ========================================================================
  // VALIDATION
  // ========================================================================

  const validateValue = useCallback(
    (val: T, allValues?: Record<string, any>): FieldValidationResult => {
      // Required
      if (rules.required) {
        if (val === undefined || val === null || val === '') {
          return {
            valid: false,
            message: rules.requiredMessage || 'Ce champ est requis',
          };
        }
        if (Array.isArray(val) && val.length === 0) {
          return {
            valid: false,
            message: rules.requiredMessage || 'Ce champ est requis',
          };
        }
      }

      // MinLength (string)
      if (typeof val === 'string' && rules.minLength) {
        if (val.length < rules.minLength) {
          return {
            valid: false,
            message: rules.minLengthMessage || `Minimum ${rules.minLength} caractères`,
          };
        }
      }

      // MaxLength (string)
      if (typeof val === 'string' && rules.maxLength) {
        if (val.length > rules.maxLength) {
          return {
            valid: false,
            message: rules.maxLengthMessage || `Maximum ${rules.maxLength} caractères`,
          };
        }
      }

      // Min (number)
      if (typeof val === 'number' && rules.min !== undefined) {
        if (val < rules.min) {
          return {
            valid: false,
            message: rules.minMessage || `Valeur minimale: ${rules.min}`,
          };
        }
      }

      // Max (number)
      if (typeof val === 'number' && rules.max !== undefined) {
        if (val > rules.max) {
          return {
            valid: false,
            message: rules.maxMessage || `Valeur maximale: ${rules.max}`,
          };
        }
      }

      // Pattern
      if (typeof val === 'string' && rules.pattern) {
        if (!rules.pattern.test(val)) {
          return {
            valid: false,
            message: rules.patternMessage || 'Format invalide',
          };
        }
      }

      // Custom validation
      if (rules.custom) {
        const result = rules.custom(val, allValues);
        if (typeof result === 'string') {
          return { valid: false, message: result };
        }
        if (result === false) {
          return { valid: false, message: 'Valeur invalide' };
        }
      }

      return { valid: true };
    },
    [rules]
  );

  const validate = useCallback(async (): Promise<boolean> => {
    setIsValidating(true);

    const allValues = formContext?.getValues() ?? {};
    const result = validateValue(value, allValues);

    if (formContext) {
      formContext.setFieldError(name, result.valid ? undefined : result.message);
    } else {
      setLocalError(result.valid ? undefined : result.message);
    }

    setIsValid(result.valid);
    setIsValidating(false);

    return result.valid;
  }, [formContext, name, value, validateValue]);

  // ========================================================================
  // DÉCLENCHEMENT DE VALIDATION
  // ========================================================================

  const triggerValidation = useCallback(() => {
    if (disableAutoValidation) return;

    if (debounceDelay > 0) {
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      debounceTimerRef.current = setTimeout(() => {
        if (isMountedRef.current) {
          validate();
        }
      }, debounceDelay);
    } else {
      validate();
    }
  }, [disableAutoValidation, debounceDelay, validate]);

  // ========================================================================
  // GESTIONNAIRES D'ÉVÉNEMENTS
  // ========================================================================

  const onChange = useCallback(
    (newValue: T | React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
      let finalValue: T;
      if (typeof newValue === 'object' && newValue !== null && 'target' in newValue) {
        const target = newValue.target;
        if (target.type === 'checkbox' && 'checked' in target) {
          finalValue = (target.checked ? target.value : '') as T;
        } else if (target.type === 'file' && 'files' in target) {
          finalValue = target.files as unknown as T;
        } else {
          finalValue = target.value as T;
        }
      } else {
        finalValue = newValue as T;
      }

      const parsed = parse ? parse(finalValue as unknown as string) : finalValue;
      setValue(parsed);

      // Validation automatique
      if (validationMode === 'onChange' || validationMode === 'onTouched') {
        triggerValidation();
      }
    },
    [parse, setValue, validationMode, triggerValidation]
  );

  const onBlur = useCallback(() => {
    setIsFocused(false);
    setTouchedState(true);

    if (formContext) {
      formContext.setTouched(name, true);
    }

    // Validation automatique
    if (validationMode === 'onBlur' || validationMode === 'onTouched') {
      triggerValidation();
    }
  }, [formContext, name, validationMode, triggerValidation]);

  const onFocus = useCallback(() => {
    setIsFocused(true);
  }, []);

  const onMouseEnter = useCallback(() => {
    setIsHovered(true);
  }, []);

  const onMouseLeave = useCallback(() => {
    setIsHovered(false);
  }, []);

  // ========================================================================
  // PROPS POUR L'INPUT
  // ========================================================================

  const getInputProps = useCallback(() => {
    const error = formContext?.errors?.[name] ?? localError;
    const isDisabled = disabled || formContext?.disabled || false;
    const isRequired = required || formContext?.required || false;

    return {
      id: fieldId,
      name,
      value: format ? format(value) : value,
      onChange: (e: React.ChangeEvent<HTMLInputElement>) => {
        const val = parse ? parse(e.target.value) : (e.target.value as T);
        onChange(val);
      },
      onBlur,
      onFocus,
      disabled: isDisabled,
      required: isRequired,
      'aria-invalid': !!error,
      'aria-describedby': error ? errorId : description ? descriptionId : undefined,
    };
  }, [
    fieldId,
    name,
    value,
    format,
    parse,
    onChange,
    onBlur,
    onFocus,
    disabled,
    required,
    localError,
    description,
    errorId,
    descriptionId,
    formContext,
  ]);

  const getLabelProps = useCallback(() => ({
    htmlFor: fieldId,
    children: label,
  }), [fieldId, label]);

  const getErrorProps = useCallback(() => {
    const error = formContext?.errors?.[name] ?? localError;
    return {
      id: errorId,
      role: 'alert' as const,
      children: error,
    };
  }, [errorId, localError, formContext, name]);

  const getDescriptionProps = useCallback(() => ({
    id: descriptionId,
    children: description,
  }), [descriptionId, description]);

  // ========================================================================
  // SYNC AVEC LE CONTEXTE
  // ========================================================================

  useEffect(() => {
    if (formContext) {
      const unsubscribe = formContext.registerField(name, {
        value,
        setValue,
        validate,
        reset,
      });
      return unsubscribe;
    }
  }, [formContext, name, value, setValue, validate, reset]);

  // ========================================================================
  // INITIALISATION
  // ========================================================================

  useEffect(() => {
    if (initialValue !== undefined && !formContext) {
      setValue(initialValue);
    }
  }, [initialValue, setValue, formContext]);

  // ========================================================================
  // VALIDATION AU MONTAGE
  // ========================================================================

  useEffect(() => {
    if (!disableAutoValidation && validationMode !== 'onSubmit') {
      validate();
    }
  }, []);

  // ========================================================================
  // CALLBACKS DE CYCLE DE VIE
  // ========================================================================

  const onMount = useCallback((callback: () => void) => {
    mountCallbacksRef.current.push(callback);
    if (isMountedRef.current) {
      callback();
    }
  }, []);

  const onUnmount = useCallback((callback: () => void) => {
    unmountCallbacksRef.current.push(callback);
    return () => {
      callback();
    };
  }, []);

  // ========================================================================
  // CLEANUP
  // ========================================================================

  useEffect(() => {
    isMountedRef.current = true;
    mountCallbacksRef.current.forEach((callback) => callback());

    return () => {
      isMountedRef.current = false;
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
      unmountCallbacksRef.current.forEach((callback) => callback());
    };
  }, []);

  // ========================================================================
  // DÉBOGAGE
  // ========================================================================

  const debug = useCallback(() => {
    console.group(`🔍 Field Debug: ${name}`);
    console.log('Value:', value);
    console.log('Error:', localError || formContext?.errors?.[name]);
    console.log('Touched:', touched || formContext?.touched?.[name]);
    console.log('Valid:', isValid);
    console.log('Focused:', isFocused);
    console.log('Hovered:', isHovered);
    console.log('Disabled:', disabled || formContext?.disabled);
    console.log('Required:', required || formContext?.required);
    console.log('Validating:', isValidating);
    console.groupEnd();
  }, [name, value, localError, touched, isValid, isFocused, isHovered, disabled, required, isValidating, formContext]);

  // ========================================================================
  // RETOUR
  // ========================================================================

  const error = formContext?.errors?.[name] ?? localError;
  const isTouched = formContext?.touched?.[name] ?? touched;
  const isDisabled = disabled || formContext?.disabled || false;
  const isRequired = required || formContext?.required || false;

  return {
    name,
    value,
    setValue,
    reset,
    error,
    touched: isTouched,
    setTouched: (touched?: boolean) => {
      setTouchedState(touched ?? true);
      if (formContext) {
        formContext.setTouched(name, touched ?? true);
      }
    },
    isValid,
    isDisabled,
    isRequired,
    isValidating,
    isFocused,
    isHovered,
    id: fieldId,
    errorId,
    descriptionId,
    validate,
    onChange,
    onBlur,
    onFocus,
    onMouseEnter,
    onMouseLeave,
    getInputProps,
    getLabelProps,
    getErrorProps,
    getDescriptionProps,
    onMount,
    onUnmount,
    debug,
  };
}

// ============================================================================
// EXPORTS
// ============================================================================

export default useFormField;

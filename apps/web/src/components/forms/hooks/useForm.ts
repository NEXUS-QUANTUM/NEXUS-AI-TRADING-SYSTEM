// apps/web/src/components/forms/hooks/useForm.ts
'use client';

import {
  useState,
  useCallback,
  useRef,
  useEffect,
  useMemo,
  useReducer,
  useImperativeHandle,
} from 'react';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type FormStatus = 'idle' | 'submitting' | 'success' | 'error' | 'validation-error';

export type ValidationRule<T = any> = {
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
  custom?: (value: T, formValues: Record<string, any>) => boolean | string;
  /** Dépendances pour la validation */
  dependsOn?: string[];
};

export type FieldConfig<T = any> = {
  /** Valeur initiale */
  initialValue?: T;
  /** Règles de validation */
  rules?: ValidationRule<T>;
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
  /** Mapping des erreurs */
  errorMap?: Record<string, string>;
};

export type FormConfig<T extends Record<string, any> = Record<string, any>> = {
  /** Valeurs initiales du formulaire */
  initialValues?: T;
  /** Configuration des champs */
  fields?: Partial<Record<keyof T, FieldConfig>>;
  /** Callback de validation personnalisée */
  validate?: (values: T) => Partial<Record<keyof T, string>>;
  /** Callback de soumission */
  onSubmit?: (values: T) => void | Promise<void>;
  /** Callback de succès */
  onSuccess?: (values: T) => void;
  /** Callback d'erreur */
  onError?: (error: string, values: T) => void;
  /** Mode de validation */
  validationMode?: 'onChange' | 'onBlur' | 'onSubmit' | 'onTouched';
  /** Désactiver la validation automatique */
  disableAutoValidation?: boolean;
  /** Désactiver la soumission automatique */
  disableAutoSubmit?: boolean;
  /** Délai de débounce (ms) */
  debounceDelay?: number;
};

export type FormState<T extends Record<string, any> = Record<string, any>> = {
  /** Valeurs du formulaire */
  values: T;
  /** Erreurs du formulaire */
  errors: Partial<Record<keyof T, string>>;
  /** Champs touchés */
  touched: Partial<Record<keyof T, boolean>>;
  /** Statut du formulaire */
  status: FormStatus;
  /** Messages d'erreur globaux */
  globalErrors: string[];
  /** Est-ce que le formulaire est valide */
  isValid: boolean;
  /** Est-ce que le formulaire est en cours de soumission */
  isSubmitting: boolean;
  /** Est-ce que le formulaire a été soumis */
  isSubmitted: boolean;
  /** Est-ce que le formulaire a été modifié */
  isDirty: boolean;
  /** Nombre de champs valides */
  validFields: number;
  /** Nombre de champs invalides */
  invalidFields: number;
  /** Nombre de champs touchés */
  touchedFields: number;
};

export type FormActions<T extends Record<string, any> = Record<string, any>> = {
  /** Mettre à jour la valeur d'un champ */
  setValue: <K extends keyof T>(field: K, value: T[K]) => void;
  /** Mettre à jour plusieurs valeurs */
  setValues: (values: Partial<T>) => void;
  /** Réinitialiser le formulaire */
  reset: () => void;
  /** Réinitialiser à des valeurs spécifiques */
  resetTo: (values: T) => void;
  /** Valider le formulaire */
  validate: () => boolean;
  /** Valider un champ spécifique */
  validateField: <K extends keyof T>(field: K) => boolean;
  /** Marquer un champ comme touché */
  setTouched: <K extends keyof T>(field: K, touched?: boolean) => void;
  /** Marquer tous les champs comme touchés */
  setAllTouched: () => void;
  /** Effacer les erreurs */
  clearErrors: () => void;
  /** Effacer les erreurs d'un champ */
  clearFieldError: <K extends keyof T>(field: K) => void;
  /** Soumettre le formulaire */
  submit: () => Promise<void>;
  /** Définir des erreurs globales */
  setGlobalErrors: (errors: string[]) => void;
  /** Ajouter une erreur globale */
  addGlobalError: (error: string) => void;
  /** Effacer les erreurs globales */
  clearGlobalErrors: () => void;
  /** Réinitialiser le statut */
  resetStatus: () => void;
};

export type UseFormReturn<T extends Record<string, any> = Record<string, any>> = FormState<T> &
  FormActions<T> & {
    /** Ref du formulaire */
    formRef: React.RefObject<HTMLFormElement>;
    /** Gestionnaire de soumission */
    handleSubmit: (e?: React.FormEvent) => Promise<void>;
    /** Gestionnaire de changement de champ */
    handleChange: <K extends keyof T>(
      field: K
    ) => (value: T[K] | React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => void;
    /** Gestionnaire de blur */
    handleBlur: <K extends keyof T>(field: K) => () => void;
    /** Gestionnaire de focus */
    handleFocus: <K extends keyof T>(field: K) => () => void;
    /** Enregistrer un champ */
    register: <K extends keyof T>(
      field: K,
      options?: {
        required?: boolean;
        validate?: (value: T[K]) => boolean | string;
      }
    ) => {
      name: K;
      value: T[K];
      onChange: (value: T[K]) => void;
      onBlur: () => void;
      onFocus: () => void;
      error: string | undefined;
      touched: boolean | undefined;
      required: boolean;
    };
    /** Fonction de débogage */
    debug: () => void;
  };

// ============================================================================
// CONSTANTES
// ============================================================================

const DEFAULT_VALIDATION_MODE = 'onChange';

// ============================================================================
// REDUCER
// ============================================================================

type FormAction<T extends Record<string, any>> =
  | { type: 'SET_VALUE'; field: keyof T; value: any }
  | { type: 'SET_VALUES'; values: Partial<T> }
  | { type: 'SET_ERRORS'; errors: Partial<Record<keyof T, string>> }
  | { type: 'SET_FIELD_ERROR'; field: keyof T; error: string | undefined }
  | { type: 'SET_TOUCHED'; field: keyof T; touched: boolean }
  | { type: 'SET_ALL_TOUCHED' }
  | { type: 'RESET'; values: T }
  | { type: 'SET_STATUS'; status: FormStatus }
  | { type: 'SET_GLOBAL_ERRORS'; errors: string[] }
  | { type: 'ADD_GLOBAL_ERROR'; error: string }
  | { type: 'CLEAR_GLOBAL_ERRORS' }
  | { type: 'CLEAR_ERRORS' }
  | { type: 'CLEAR_FIELD_ERROR'; field: keyof T }
  | { type: 'RESET_STATUS' }
  | { type: 'SET_SUBMITTING'; isSubmitting: boolean }
  | { type: 'SET_SUBMITTED'; isSubmitted: boolean }
  | { type: 'SET_DIRTY'; isDirty: boolean };

function formReducer<T extends Record<string, any>>(
  state: FormState<T>,
  action: FormAction<T>
): FormState<T> {
  switch (action.type) {
    case 'SET_VALUE': {
      const newValues = { ...state.values, [action.field]: action.value };
      const isDirty = true;
      return { ...state, values: newValues, isDirty };
    }

    case 'SET_VALUES': {
      const newValues = { ...state.values, ...action.values };
      const isDirty = true;
      return { ...state, values: newValues, isDirty };
    }

    case 'SET_ERRORS': {
      const errors = action.errors;
      const validFields = Object.keys(state.values).filter(
        (key) => !errors[key]
      ).length;
      const invalidFields = Object.keys(state.values).length - validFields;
      const isValid = invalidFields === 0;
      return {
        ...state,
        errors,
        validFields,
        invalidFields,
        isValid,
      };
    }

    case 'SET_FIELD_ERROR': {
      const newErrors = { ...state.errors };
      if (action.error) {
        newErrors[action.field] = action.error;
      } else {
        delete newErrors[action.field];
      }
      const validFields = Object.keys(state.values).filter(
        (key) => !newErrors[key]
      ).length;
      const invalidFields = Object.keys(state.values).length - validFields;
      const isValid = invalidFields === 0;
      return {
        ...state,
        errors: newErrors,
        validFields,
        invalidFields,
        isValid,
      };
    }

    case 'SET_TOUCHED': {
      const newTouched = { ...state.touched, [action.field]: action.touched };
      const touchedFields = Object.values(newTouched).filter(Boolean).length;
      return {
        ...state,
        touched: newTouched,
        touchedFields,
      };
    }

    case 'SET_ALL_TOUCHED': {
      const newTouched = Object.keys(state.values).reduce(
        (acc, key) => ({ ...acc, [key]: true }),
        {} as Record<keyof T, boolean>
      );
      return {
        ...state,
        touched: newTouched,
        touchedFields: Object.keys(state.values).length,
      };
    }

    case 'RESET': {
      const values = action.values;
      const errors = {} as Partial<Record<keyof T, string>>;
      const touched = {} as Partial<Record<keyof T, boolean>>;
      const validFields = Object.keys(values).length;
      return {
        ...state,
        values,
        errors,
        touched,
        globalErrors: [],
        isValid: true,
        isDirty: false,
        isSubmitted: false,
        isSubmitting: false,
        status: 'idle',
        validFields,
        invalidFields: 0,
        touchedFields: 0,
      };
    }

    case 'SET_STATUS': {
      return { ...state, status: action.status };
    }

    case 'SET_GLOBAL_ERRORS': {
      return { ...state, globalErrors: action.errors };
    }

    case 'ADD_GLOBAL_ERROR': {
      return {
        ...state,
        globalErrors: [...state.globalErrors, action.error],
      };
    }

    case 'CLEAR_GLOBAL_ERRORS': {
      return { ...state, globalErrors: [] };
    }

    case 'CLEAR_ERRORS': {
      const errors = {} as Partial<Record<keyof T, string>>;
      const validFields = Object.keys(state.values).length;
      return {
        ...state,
        errors,
        validFields,
        invalidFields: 0,
        isValid: true,
      };
    }

    case 'CLEAR_FIELD_ERROR': {
      const newErrors = { ...state.errors };
      delete newErrors[action.field];
      const validFields = Object.keys(state.values).filter(
        (key) => !newErrors[key]
      ).length;
      const invalidFields = Object.keys(state.values).length - validFields;
      const isValid = invalidFields === 0;
      return {
        ...state,
        errors: newErrors,
        validFields,
        invalidFields,
        isValid,
      };
    }

    case 'RESET_STATUS': {
      return {
        ...state,
        status: 'idle',
        isSubmitting: false,
        isSubmitted: false,
        globalErrors: [],
      };
    }

    case 'SET_SUBMITTING': {
      return {
        ...state,
        isSubmitting: action.isSubmitting,
        status: action.isSubmitting ? 'submitting' : state.status,
      };
    }

    case 'SET_SUBMITTED': {
      return {
        ...state,
        isSubmitted: action.isSubmitted,
        status: action.isSubmitted ? 'success' : state.status,
      };
    }

    case 'SET_DIRTY': {
      return { ...state, isDirty: action.isDirty };
    }

    default:
      return state;
  }
}

// ============================================================================
// HOOK PRINCIPAL
// ============================================================================

export function useForm<T extends Record<string, any> = Record<string, any>>(
  config: FormConfig<T> = {}
): UseFormReturn<T> {
  const {
    initialValues = {} as T,
    fields = {},
    validate: customValidate,
    onSubmit,
    onSuccess,
    onError,
    validationMode = DEFAULT_VALIDATION_MODE,
    disableAutoValidation = false,
    disableAutoSubmit = false,
    debounceDelay = 300,
  } = config;

  // ========================================================================
  // TOAST
  // ========================================================================

  const { toast } = useToast();

  // ========================================================================
  // RÉFÉRENCES
  // ========================================================================

  const formRef = useRef<HTMLFormElement>(null);
  const isMountedRef = useRef(true);
  const debounceTimerRef = useRef<NodeJS.Timeout | null>(null);
  const initialValuesRef = useRef<T>(initialValues);

  // ========================================================================
  // STATE
  // ========================================================================

  const [state, dispatch] = useReducer(formReducer<T>, {
    values: initialValues,
    errors: {} as Partial<Record<keyof T, string>>,
    touched: {} as Partial<Record<keyof T, boolean>>,
    status: 'idle',
    globalErrors: [],
    isValid: true,
    isSubmitting: false,
    isSubmitted: false,
    isDirty: false,
    validFields: Object.keys(initialValues).length,
    invalidFields: 0,
    touchedFields: 0,
  });

  // ========================================================================
  // VALIDATION
  // ========================================================================

  const getFieldRules = useCallback(
    <K extends keyof T>(field: K): ValidationRule => {
      const fieldConfig = fields[field] as FieldConfig | undefined;
      return fieldConfig?.rules || {};
    },
    [fields]
  );

  const validateField = useCallback(
    <K extends keyof T>(field: K): boolean => {
      const value = state.values[field];
      const rules = getFieldRules(field);
      const error = validateValue(value, rules, state.values, field as string);

      if (error) {
        dispatch({ type: 'SET_FIELD_ERROR', field, error });
        return false;
      } else {
        dispatch({ type: 'SET_FIELD_ERROR', field, error: undefined });
        return true;
      }
    },
    [state.values, getFieldRules]
  );

  const validateAll = useCallback((): boolean => {
    const errors: Partial<Record<keyof T, string>> = {};
    let isValid = true;

    // Validation personnalisée
    if (customValidate) {
      const customErrors = customValidate(state.values);
      Object.entries(customErrors).forEach(([key, error]) => {
        if (error) {
          errors[key as keyof T] = error;
          isValid = false;
        }
      });
    }

    // Validation des champs
    Object.keys(state.values).forEach((key) => {
      const field = key as keyof T;
      const value = state.values[field];
      const rules = getFieldRules(field);
      const error = validateValue(value, rules, state.values, field as string);

      if (error) {
        errors[field] = error;
        isValid = false;
      }
    });

    dispatch({ type: 'SET_ERRORS', errors });
    return isValid;
  }, [state.values, customValidate, getFieldRules]);

  const validateValue = (
    value: any,
    rules: ValidationRule,
    allValues: T,
    fieldName: string
  ): string | undefined => {
    // Required
    if (rules.required) {
      if (value === undefined || value === null || value === '') {
        return rules.requiredMessage || 'Ce champ est requis';
      }
      if (Array.isArray(value) && value.length === 0) {
        return rules.requiredMessage || 'Ce champ est requis';
      }
    }

    // MinLength (string)
    if (typeof value === 'string' && rules.minLength) {
      if (value.length < rules.minLength) {
        return rules.minLengthMessage || `Minimum ${rules.minLength} caractères`;
      }
    }

    // MaxLength (string)
    if (typeof value === 'string' && rules.maxLength) {
      if (value.length > rules.maxLength) {
        return rules.maxLengthMessage || `Maximum ${rules.maxLength} caractères`;
      }
    }

    // Min (number)
    if (typeof value === 'number' && rules.min !== undefined) {
      if (value < rules.min) {
        return rules.minMessage || `Valeur minimale: ${rules.min}`;
      }
    }

    // Max (number)
    if (typeof value === 'number' && rules.max !== undefined) {
      if (value > rules.max) {
        return rules.maxMessage || `Valeur maximale: ${rules.max}`;
      }
    }

    // Pattern
    if (typeof value === 'string' && rules.pattern) {
      if (!rules.pattern.test(value)) {
        return rules.patternMessage || 'Format invalide';
      }
    }

    // Custom validation
    if (rules.custom) {
      const result = rules.custom(value, allValues);
      if (typeof result === 'string') {
        return result;
      }
      if (result === false) {
        return 'Valeur invalide';
      }
    }

    return undefined;
  };

  // ========================================================================
  // ACTIONS
  // ========================================================================

  const setValue = useCallback(
    <K extends keyof T>(field: K, value: T[K]) => {
      dispatch({ type: 'SET_VALUE', field, value });

      // Validation automatique
      if (
        !disableAutoValidation &&
        (validationMode === 'onChange' ||
          (validationMode === 'onTouched' && state.touched[field]))
      ) {
        if (debounceDelay > 0) {
          if (debounceTimerRef.current) {
            clearTimeout(debounceTimerRef.current);
          }
          debounceTimerRef.current = setTimeout(() => {
            if (isMountedRef.current) {
              validateField(field);
            }
          }, debounceDelay);
        } else {
          validateField(field);
        }
      }
    },
    [
      disableAutoValidation,
      validationMode,
      state.touched,
      debounceDelay,
      validateField,
    ]
  );

  const setValues = useCallback((values: Partial<T>) => {
    dispatch({ type: 'SET_VALUES', values });

    // Validation automatique
    if (!disableAutoValidation && validationMode === 'onChange') {
      if (debounceDelay > 0) {
        if (debounceTimerRef.current) {
          clearTimeout(debounceTimerRef.current);
        }
        debounceTimerRef.current = setTimeout(() => {
          if (isMountedRef.current) {
            validateAll();
          }
        }, debounceDelay);
      } else {
        validateAll();
      }
    }
  }, [disableAutoValidation, validationMode, debounceDelay, validateAll]);

  const reset = useCallback(() => {
    dispatch({ type: 'RESET', values: initialValuesRef.current });
    dispatch({ type: 'CLEAR_GLOBAL_ERRORS' });
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
  }, []);

  const resetTo = useCallback((values: T) => {
    initialValuesRef.current = values;
    dispatch({ type: 'RESET', values });
    dispatch({ type: 'CLEAR_GLOBAL_ERRORS' });
    if (debounceTimerRef.current) {
      clearTimeout(debounceTimerRef.current);
    }
  }, []);

  const setTouched = useCallback(
    <K extends keyof T>(field: K, touched: boolean = true) => {
      dispatch({ type: 'SET_TOUCHED', field, touched });

      // Validation automatique
      if (!disableAutoValidation && validationMode === 'onTouched' && touched) {
        validateField(field);
      }
    },
    [disableAutoValidation, validationMode, validateField]
  );

  const setAllTouched = useCallback(() => {
    dispatch({ type: 'SET_ALL_TOUCHED' });

    // Validation automatique
    if (!disableAutoValidation && validationMode === 'onTouched') {
      validateAll();
    }
  }, [disableAutoValidation, validationMode, validateAll]);

  const clearErrors = useCallback(() => {
    dispatch({ type: 'CLEAR_ERRORS' });
  }, []);

  const clearFieldError = useCallback(<K extends keyof T>(field: K) => {
    dispatch({ type: 'CLEAR_FIELD_ERROR', field });
  }, []);

  const setGlobalErrors = useCallback((errors: string[]) => {
    dispatch({ type: 'SET_GLOBAL_ERRORS', errors });
  }, []);

  const addGlobalError = useCallback((error: string) => {
    dispatch({ type: 'ADD_GLOBAL_ERROR', error });
  }, []);

  const clearGlobalErrors = useCallback(() => {
    dispatch({ type: 'CLEAR_GLOBAL_ERRORS' });
  }, []);

  const resetStatus = useCallback(() => {
    dispatch({ type: 'RESET_STATUS' });
  }, []);

  const validate = useCallback((): boolean => {
    const isValid = validateAll();
    if (!isValid) {
      setAllTouched();
    }
    return isValid;
  }, [validateAll, setAllTouched]);

  // ========================================================================
  // SOUMISSION
  // ========================================================================

  const submit = useCallback(async (): Promise<void> => {
    if (state.isSubmitting) return;

    // Valider
    const isValid = validate();
    if (!isValid) {
      dispatch({ type: 'SET_STATUS', status: 'validation-error' });
      toast({
        title: 'Erreur de validation',
        description: 'Veuillez corriger les erreurs du formulaire',
        variant: 'destructive',
      });
      return;
    }

    dispatch({ type: 'SET_SUBMITTING', isSubmitting: true });

    try {
      if (onSubmit) {
        await onSubmit(state.values);
      }

      dispatch({ type: 'SET_SUBMITTED', isSubmitted: true });
      dispatch({ type: 'SET_STATUS', status: 'success' });

      if (onSuccess) {
        onSuccess(state.values);
      }

      toast({
        title: 'Succès',
        description: 'Le formulaire a été soumis avec succès',
        variant: 'success',
      });

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Erreur de soumission';
      dispatch({ type: 'SET_STATUS', status: 'error' });
      addGlobalError(errorMessage);

      if (onError) {
        onError(errorMessage, state.values);
      }

      toast({
        title: 'Erreur',
        description: errorMessage,
        variant: 'destructive',
      });

    } finally {
      dispatch({ type: 'SET_SUBMITTING', isSubmitting: false });
    }
  }, [
    state.isSubmitting,
    state.values,
    validate,
    onSubmit,
    onSuccess,
    onError,
    addGlobalError,
    toast,
  ]);

  const handleSubmit = useCallback(
    async (e?: React.FormEvent): Promise<void> => {
      if (e) {
        e.preventDefault();
      }
      await submit();
    },
    [submit]
  );

  // ========================================================================
  // GESTIONNAIRES D'ÉVÉNEMENTS
  // ========================================================================

  const handleChange = useCallback(
    <K extends keyof T>(
      field: K
    ): ((value: T[K] | React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => void) => {
      return (value: T[K] | React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
        let finalValue: T[K];
        if (typeof value === 'object' && value !== null && 'target' in value) {
          const target = value.target;
          if (target.type === 'checkbox' && 'checked' in target) {
            finalValue = (target.checked ? target.value : '') as T[K];
          } else {
            finalValue = target.value as T[K];
          }
        } else {
          finalValue = value as T[K];
        }
        setValue(field, finalValue);
      };
    },
    [setValue]
  );

  const handleBlur = useCallback(
    <K extends keyof T>(field: K): (() => void) => {
      return () => {
        setTouched(field, true);
        if (validationMode === 'onBlur') {
          validateField(field);
        }
      };
    },
    [setTouched, validationMode, validateField]
  );

  const handleFocus = useCallback(
    <K extends keyof T>(field: K): (() => void) => {
      return () => {
        // Rien de spécial à faire, mais maintenu pour la cohérence
      };
    },
    []
  );

  // ========================================================================
  // REGISTER
  // ========================================================================

  const register = useCallback(
    <K extends keyof T>(
      field: K,
      options?: {
        required?: boolean;
        validate?: (value: T[K]) => boolean | string;
      }
    ) => {
      const fieldConfig = fields[field] as FieldConfig | undefined;
      const isRequired = options?.required || fieldConfig?.required || false;
      const value = state.values[field];
      const error = state.errors[field];
      const touched = state.touched[field];

      return {
        name: field,
        value,
        onChange: setValue.bind(null, field),
        onBlur: handleBlur(field),
        onFocus: handleFocus(field),
        error,
        touched,
        required: isRequired,
      };
    },
    [fields, state.values, state.errors, state.touched, setValue, handleBlur, handleFocus]
  );

  // ========================================================================
  // DÉBOGAGE
  // ========================================================================

  const debug = useCallback(() => {
    console.group('🔍 Form Debug');
    console.log('Values:', state.values);
    console.log('Errors:', state.errors);
    console.log('Touched:', state.touched);
    console.log('Status:', state.status);
    console.log('isValid:', state.isValid);
    console.log('isDirty:', state.isDirty);
    console.log('isSubmitting:', state.isSubmitting);
    console.log('isSubmitted:', state.isSubmitted);
    console.log('Global Errors:', state.globalErrors);
    console.log('Valid Fields:', state.validFields);
    console.log('Invalid Fields:', state.invalidFields);
    console.log('Touched Fields:', state.touchedFields);
    console.groupEnd();
  }, [state]);

  // ========================================================================
  // EFFETS
  // ========================================================================

  // Nettoyage des timers
  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
      }
    };
  }, []);

  // ========================================================================
  // RETOUR
  // ========================================================================

  return {
    // State
    values: state.values,
    errors: state.errors,
    touched: state.touched,
    status: state.status,
    globalErrors: state.globalErrors,
    isValid: state.isValid,
    isSubmitting: state.isSubmitting,
    isSubmitted: state.isSubmitted,
    isDirty: state.isDirty,
    validFields: state.validFields,
    invalidFields: state.invalidFields,
    touchedFields: state.touchedFields,

    // Actions
    setValue,
    setValues,
    reset,
    resetTo,
    validate,
    validateField,
    setTouched,
    setAllTouched,
    clearErrors,
    clearFieldError,
    setGlobalErrors,
    addGlobalError,
    clearGlobalErrors,
    resetStatus,
    submit,

    // Handlers
    formRef,
    handleSubmit,
    handleChange,
    handleBlur,
    handleFocus,
    register,

    // Debug
    debug,
  };
}

// ============================================================================
// EXPORTS
// ============================================================================

export default useForm;

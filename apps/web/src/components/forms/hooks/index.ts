// apps/web/src/components/forms/hooks/index.ts

// ============================================================================
// EXPORTS PRINCIPAUX - HOOKS DE FORMULAIRE
// ============================================================================

// --- Hook principal de formulaire ---
export { default as useForm } from './useForm';
export type {
  UseFormReturn,
  FormState,
  FormActions,
  FormConfig,
  FieldConfig,
  ValidationRule,
  FormStatus,
} from './useForm';

// --- Hook de champ de formulaire ---
export { default as useFormField } from './useFormField';
export type {
  UseFormFieldOptions,
  UseFormFieldReturn,
  FieldValidationRule,
  FieldValidationResult,
} from './useFormField';

// --- Hook de soumission de formulaire ---
export { default as useFormSubmit } from './useFormSubmit';
export type {
  UseFormSubmitReturn,
  SubmitOptions,
  SubmitStatus,
  SubmitRetryConfig,
} from './useFormSubmit';

// --- Hook de validation de formulaire ---
export { default as useFormValidation } from './useFormValidation';
export type {
  UseFormValidationReturn,
  FormValidationConfig,
  FieldValidation,
  ValidationRule as FormValidationRule,
} from './useFormValidation';

// --- Hook de wizard de formulaire ---
export { default as useFormWizard } from './useFormWizard';
export type {
  UseFormWizardReturn,
  WizardConfig,
  WizardStep,
  WizardNavigation,
} from './useFormWizard';

// ============================================================================
// EXPORTS DE TYPE - TYPES GÉNÉRIQUES
// ============================================================================

export type FormHookName = 
  | 'useForm'
  | 'useFormField'
  | 'useFormSubmit'
  | 'useFormValidation'
  | 'useFormWizard';

export type FormHookReturnMap = {
  useForm: UseFormReturn;
  useFormField: UseFormFieldReturn;
  useFormSubmit: UseFormSubmitReturn;
  useFormValidation: UseFormValidationReturn;
  useFormWizard: UseFormWizardReturn;
};

export type FormHookConfigMap = {
  useForm: FormConfig;
  useFormField: UseFormFieldOptions;
  useFormSubmit: SubmitOptions;
  useFormValidation: FormValidationConfig;
  useFormWizard: WizardConfig;
};

/**
 * Type générique pour obtenir le retour d'un hook spécifique
 */
export type FormHookReturn<T extends FormHookName> = FormHookReturnMap[T];

/**
 * Type générique pour obtenir la configuration d'un hook spécifique
 */
export type FormHookConfig<T extends FormHookName> = FormHookConfigMap[T];

// ============================================================================
// CONSTANTES - CONFIGURATIONS PAR DÉFAUT
// ============================================================================

export const DEFAULT_FORM_CONFIG = {
  // Validation
  validationMode: 'onChange' as const,
  debounceDelay: 300,
  
  // Soumission
  maxRetries: 3,
  retryDelay: 1000,
  timeout: 30000,
  
  // Wizard
  navigationMode: 'linear' as const,
  saveDebounce: 500,
} as const;

// ============================================================================
// UTILITAIRES - CRÉATEURS DE HOOKS
// ============================================================================

import { useForm } from './useForm';
import { useFormField } from './useFormField';
import { useFormSubmit } from './useFormSubmit';
import { useFormValidation } from './useFormValidation';
import { useFormWizard } from './useFormWizard';

/**
 * Créer un formulaire avec toutes ses fonctionnalités
 */
export const createForm = <T extends Record<string, any>>(
  config: FormConfig<T>
) => {
  const form = useForm<T>(config);
  
  return {
    ...form,
    // Ajouter des méthodes utilitaires
    getValues: () => form.values,
    setValues: form.setValues,
    reset: form.reset,
    submit: form.submit,
    validate: form.validate,
    register: form.register,
    handleSubmit: form.handleSubmit,
    debug: form.debug,
  };
};

/**
 * Créer un hook de champ personnalisé
 */
export const createFieldHook = <T = any>(
  defaultOptions?: Partial<UseFormFieldOptions<T>>
) => {
  return (options: UseFormFieldOptions<T>) => {
    return useFormField<T>({
      ...defaultOptions,
      ...options,
    });
  };
};

/**
 * Créer un hook de soumission personnalisé
 */
export const createSubmitHook = <T = any>(
  defaultOptions?: Partial<SubmitOptions<T>>
) => {
  return (options?: Partial<SubmitOptions<T>>) => {
    return useFormSubmit<T>({
      ...defaultOptions,
      ...options,
    });
  };
};

/**
 * Créer un hook de validation personnalisé
 */
export const createValidationHook = <T extends Record<string, any>>(
  defaultConfig?: Partial<FormValidationConfig<T>>
) => {
  return (config: FormValidationConfig<T>) => {
    return useFormValidation<T>({
      ...defaultConfig,
      ...config,
    });
  };
};

// ============================================================================
// UTILITAIRES - COMBINAISON DE HOOKS
// ============================================================================

/**
 * Combiner useForm et useFormValidation
 */
export const useFormWithValidation = <T extends Record<string, any>>(
  config: FormConfig<T> & { validation?: FormValidationConfig<T> }
) => {
  const form = useForm<T>(config);
  const validation = useFormValidation<T>({
    fields: config.fields || {},
    mode: config.validationMode || 'onChange',
    debounceDelay: config.debounceDelay || 300,
    ...config.validation,
  });

  // Lier la validation au formulaire
  const validateAndSubmit = async () => {
    const isValid = await validation.validate(form.values);
    if (isValid) {
      await form.submit();
    }
    return isValid;
  };

  return {
    ...form,
    ...validation,
    validateAndSubmit,
    // Surcharger handleSubmit pour inclure la validation
    handleSubmit: async (e?: React.FormEvent) => {
      if (e) e.preventDefault();
      await validateAndSubmit();
    },
    // Surcharger setValue pour déclencher la validation
    setValue: <K extends keyof T>(field: K, value: T[K]) => {
      form.setValue(field, value);
      if (config.validationMode !== 'onSubmit') {
        validation.validateField(field, value, form.values);
      }
    },
  };
};

/**
 * Combiner useForm et useFormWizard
 */
export const useFormWizardWithForm = <T extends Record<string, any>>(
  formConfig: FormConfig<T>,
  wizardConfig: WizardConfig & { initialData?: T }
) => {
  const form = useForm<T>(formConfig);
  const wizard = useFormWizard<T>({
    ...wizardConfig,
    initialData: formConfig.initialValues,
  });

  // Synchroniser les données
  const setValues = (values: Partial<T>) => {
    form.setValues(values);
    wizard.setValues(values);
  };

  const setFieldValue = <K extends keyof T>(field: K, value: T[K]) => {
    form.setFieldValue(field, value);
    wizard.setFieldValue(field, value);
  };

  const reset = () => {
    form.reset();
    wizard.reset();
  };

  // Surcharger next pour valider avant de changer d'étape
  const next = async () => {
    const isValid = await wizard.validateStep();
    if (isValid) {
      await wizard.navigation.next();
    }
    return isValid;
  };

  return {
    ...form,
    ...wizard,
    setValues,
    setFieldValue,
    reset,
    next,
    // Surcharger les méthodes de navigation pour inclure la validation
    navigation: {
      ...wizard.navigation,
      next,
    },
  };
};

// ============================================================================
// EXPORTATION PAR DÉFAUT - TOUS LES HOOKS
// ============================================================================

/**
 * Exportation groupée de tous les hooks de formulaire
 */
const FormHooks = {
  useForm,
  useFormField,
  useFormSubmit,
  useFormValidation,
  useFormWizard,
  // Utilitaires
  createForm,
  createFieldHook,
  createSubmitHook,
  createValidationHook,
  useFormWithValidation,
  useFormWizardWithForm,
};

export default FormHooks;

// ============================================================================
// TYPES DÉRIVÉS POUR UNE UTILISATION FACILE
// ============================================================================

/**
 * Type pour un hook de formulaire générique
 */
export type AnyFormHook = (...args: any[]) => any;

/**
 * Type pour un hook de formulaire avec ses arguments
 */
export type FormHookWithArgs<T extends AnyFormHook> = {
  hook: T;
  args: Parameters<T>;
};

/**
 * Type pour un hook de formulaire avec son retour
 */
export type FormHookWithReturn<T extends AnyFormHook> = {
  hook: T;
  return: ReturnType<T>;
};

// ============================================================================
// UTILITAIRES - GESTION DES ERREURS
// ============================================================================

export const formatValidationErrors = (
  errors: Record<string, string>
): string[] => {
  return Object.values(errors).filter(Boolean);
};

export const getFirstErrorMessage = (
  errors: Record<string, string>
): string | undefined => {
  const messages = Object.values(errors).filter(Boolean);
  return messages.length > 0 ? messages[0] : undefined;
};

export const hasValidationErrors = (
  errors: Record<string, string>
): boolean => {
  return Object.values(errors).some(error => error && error.length > 0);
};

// ============================================================================
// UTILITAIRES - SÉCURITÉ
// ============================================================================

export const sanitizeFormData = <T extends Record<string, any>>(
  data: T,
  sensitiveFields: (keyof T)[] = []
): Partial<T> => {
  const sanitized = { ...data };
  sensitiveFields.forEach(field => {
    delete sanitized[field];
  });
  return sanitized;
};

export const maskSensitiveData = <T extends Record<string, any>>(
  data: T,
  sensitiveFields: (keyof T)[] = []
): T => {
  const masked = { ...data };
  sensitiveFields.forEach(field => {
    if (masked[field] !== undefined && masked[field] !== null) {
      const value = String(masked[field]);
      masked[field] = '*'.repeat(Math.min(value.length, 8)) as any;
    }
  });
  return masked;
};

// ============================================================================
// UTILITAIRES - PERFORMANCE
// ============================================================================

export const debounceFormValidation = <T extends (...args: any[]) => any>(
  fn: T,
  delay: number = 300
): T => {
  let timeoutId: NodeJS.Timeout | null = null;
  
  return ((...args: Parameters<T>) => {
    if (timeoutId) {
      clearTimeout(timeoutId);
    }
    timeoutId = setTimeout(() => {
      fn(...args);
      timeoutId = null;
    }, delay);
  }) as T;
};

export const throttleFormSubmission = <T extends (...args: any[]) => any>(
  fn: T,
  limit: number = 1000
): T => {
  let inThrottle = false;
  
  return ((...args: Parameters<T>) => {
    if (!inThrottle) {
      fn(...args);
      inThrottle = true;
      setTimeout(() => {
        inThrottle = false;
      }, limit);
    }
  }) as T;
};

// ============================================================================
// EXPORTATION DES TYPES DE CONFIGURATION
// ============================================================================

export type {
  FormStatus,
  ValidationRule,
  FieldConfig,
  FormConfig,
  UseFormReturn,
  FormState,
  FormActions,
} from './useForm';

export type {
  UseFormFieldOptions,
  UseFormFieldReturn,
  FieldValidationRule,
  FieldValidationResult,
} from './useFormField';

export type {
  UseFormSubmitReturn,
  SubmitOptions,
  SubmitStatus as SubmitStatusType,
  SubmitRetryConfig,
} from './useFormSubmit';

export type {
  UseFormValidationReturn,
  FormValidationConfig,
  FieldValidation as FieldValidationType,
} from './useFormValidation';

export type {
  UseFormWizardReturn,
  WizardConfig as WizardConfigType,
  WizardStep as WizardStepType,
  WizardNavigation as WizardNavigationType,
} from './useFormWizard';

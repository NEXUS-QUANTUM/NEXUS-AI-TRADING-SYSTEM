// apps/web/src/components/forms/hooks/useFormWizard.ts
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

export type WizardStep = {
  /** Identifiant unique de l'étape */
  id: string;
  /** Titre de l'étape */
  title: string;
  /** Description de l'étape */
  description?: string;
  /** Icône de l'étape */
  icon?: React.ReactNode;
  /** Statut de l'étape */
  status?: 'idle' | 'active' | 'completed' | 'error' | 'skipped';
  /** Champs requis pour cette étape */
  fields?: string[];
  /** Validation personnalisée pour cette étape */
  validate?: (values: any) => boolean | string | Promise<boolean | string>;
  /** Callback avant de quitter l'étape */
  onLeave?: (values: any) => boolean | Promise<boolean>;
  /** Callback avant d'entrer dans l'étape */
  onEnter?: (values: any) => void | Promise<void>;
  /** Callback après avoir quitté l'étape */
  onLeaveComplete?: (values: any) => void;
  /** Callback après être entré dans l'étape */
  onEnterComplete?: (values: any) => void;
  /** Désactiver l'étape */
  disabled?: boolean;
  /** Rendre l'étape optionnelle */
  optional?: boolean;
};

export type WizardConfig = {
  /** Étapes du wizard */
  steps: WizardStep[];
  /** Étape initiale (id) */
  initialStep?: string;
  /** Mode de navigation */
  navigationMode?: 'linear' | 'free' | 'conditional';
  /** Sauvegarder la progression */
  saveProgress?: boolean;
  /** Clé de sauvegarde (localStorage) */
  saveKey?: string;
  /** Persister les données entre les sessions */
  persistData?: boolean;
  /** Délai de sauvegarde (ms) */
  saveDebounce?: number;
  /** Callback de changement d'étape */
  onStepChange?: (stepId: string, direction: 'next' | 'prev' | 'jump') => void;
  /** Callback de fin du wizard */
  onComplete?: (values: any) => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de validation d'étape */
  onStepValidate?: (stepId: string, values: any) => boolean | string | Promise<boolean | string>;
};

export type WizardNavigation = {
  /** Aller à l'étape suivante */
  next: () => Promise<boolean>;
  /** Revenir à l'étape précédente */
  previous: () => Promise<boolean>;
  /** Aller à une étape spécifique */
  goTo: (stepId: string) => Promise<boolean>;
  /** Aller à la première étape */
  goToFirst: () => Promise<boolean>;
  /** Aller à la dernière étape */
  goToLast: () => Promise<boolean>;
  /** Revenir en arrière de N étapes */
  goBack: (steps: number) => Promise<boolean>;
  /** Avancer de N étapes */
  goForward: (steps: number) => Promise<boolean>;
  /** Sauter l'étape courante (si optionnelle) */
  skip: () => Promise<boolean>;
  /** Terminer le wizard */
  complete: () => Promise<void>;
  /** Annuler le wizard */
  cancel: () => void;
  /** Est-ce que la navigation est possible */
  canNavigate: (direction: 'next' | 'prev') => boolean;
  /** Est-ce que l'étape est accessible */
  isStepAccessible: (stepId: string) => boolean;
};

export type UseFormWizardReturn<T = any> = {
  /** Données du formulaire */
  values: T;
  /** Mettre à jour les données */
  setValues: (values: Partial<T>) => void;
  /** Mettre à jour un champ spécifique */
  setFieldValue: <K extends keyof T>(field: K, value: T[K]) => void;
  /** Réinitialiser les données */
  reset: () => void;
  /** Charger des données */
  load: (data: T) => void;
  /** Étape courante */
  currentStep: WizardStep;
  /** Index de l'étape courante */
  currentStepIndex: number;
  /** Étapes du wizard */
  steps: WizardStep[];
  /** Statut des étapes */
  stepStatus: Record<string, 'idle' | 'active' | 'completed' | 'error' | 'skipped'>;
  /** Navigation */
  navigation: WizardNavigation;
  /** Est-ce que le wizard est terminé */
  isComplete: boolean;
  /** Est-ce que le wizard est en cours */
  isInProgress: boolean;
  /** Progression (0-100) */
  progress: number;
  /** Est-ce que l'étape courante est valide */
  isStepValid: boolean;
  /** Est-ce que l'étape courante est la première */
  isFirstStep: boolean;
  /** Est-ce que l'étape courante est la dernière */
  isLastStep: boolean;
  /** Est-ce que l'étape courante est optionnelle */
  isStepOptional: boolean;
  /** Erreurs de validation */
  errors: Record<string, string>;
  /** Valider l'étape courante */
  validateStep: () => Promise<boolean>;
  /** Valider toutes les étapes */
  validateAll: () => Promise<boolean>;
  /** Sauvegarder la progression */
  saveProgress: () => void;
  /** Charger la progression sauvegardée */
  loadProgress: () => T | null;
  /** Effacer la progression sauvegardée */
  clearProgress: () => void;
  /** Mode débogage */
  debug: () => void;
  /** Événements */
  on: (event: 'stepChange' | 'complete' | 'cancel' | 'error', callback: (data: any) => void) => () => void;
};

// ============================================================================
// CONSTANTES
// ============================================================================

const DEFAULT_SAVE_DEBOUNCE = 500;
const DEFAULT_NAVIGATION_MODE = 'linear';

// ============================================================================
// HOOK PRINCIPAL
// ============================================================================

export function useFormWizard<T extends Record<string, any> = Record<string, any>>(
  config: WizardConfig & { initialData?: T }
): UseFormWizardReturn<T> {
  const {
    steps,
    initialStep,
    initialData = {} as T,
    navigationMode = DEFAULT_NAVIGATION_MODE,
    saveProgress: enableSaveProgress = false,
    saveKey = 'wizard_progress',
    persistData = false,
    saveDebounce = DEFAULT_SAVE_DEBOUNCE,
    onStepChange,
    onComplete,
    onCancel,
    onStepValidate,
  } = config;

  // ========================================================================
  // TOAST
  // ========================================================================

  const { toast } = useToast();

  // ========================================================================
  // RÉFÉRENCES
  // ========================================================================

  const saveTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isMountedRef = useRef(true);
  const eventListenersRef = useRef<Record<string, ((data: any) => void)[]>>({
    stepChange: [],
    complete: [],
    cancel: [],
    error: [],
  });
  const initialStepRef = useRef<string>(initialStep || steps[0]?.id || '');
  const initialDataRef = useRef<T>(initialData);

  // ========================================================================
  // ÉTATS
  // ========================================================================

  const [values, setValuesState] = useState<T>(() => {
    // Charger les données sauvegardées
    if (persistData && enableSaveProgress) {
      const saved = loadProgressFromStorage();
      if (saved) {
        return { ...initialDataRef.current, ...saved };
      }
    }
    return initialDataRef.current;
  });

  const [currentStepId, setCurrentStepId] = useState<string>(initialStepRef.current);
  const [stepStatus, setStepStatus] = useState<Record<string, 'idle' | 'active' | 'completed' | 'error' | 'skipped'>>(() => {
    const status: Record<string, any> = {};
    steps.forEach((step, index) => {
      status[step.id] = index === 0 ? 'active' : 'idle';
    });
    return status;
  });
  const [isComplete, setIsComplete] = useState(false);
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [isValidating, setIsValidating] = useState(false);

  // ========================================================================
  // DÉRIVÉS
  // ========================================================================

  const currentStepIndex = steps.findIndex(s => s.id === currentStepId);
  const currentStep = steps[currentStepIndex] || steps[0];
  const isFirstStep = currentStepIndex === 0;
  const isLastStep = currentStepIndex === steps.length - 1;
  const isStepOptional = currentStep?.optional || false;
  const progress = steps.length > 0 ? ((currentStepIndex + 1) / steps.length) * 100 : 0;
  const isInProgress = !isComplete && currentStepIndex < steps.length;

  // ========================================================================
  // SAUVEGARDE
  // ========================================================================

  const saveProgressToStorage = useCallback((data: T) => {
    if (!enableSaveProgress || typeof window === 'undefined') return;

    try {
      const saveData = {
        values: data,
        currentStep: currentStepId,
        stepStatus,
        timestamp: Date.now(),
      };
      localStorage.setItem(saveKey, JSON.stringify(saveData));
    } catch (error) {
      console.error('Erreur de sauvegarde:', error);
    }
  }, [enableSaveProgress, saveKey, currentStepId, stepStatus]);

  const loadProgressFromStorage = useCallback((): T | null => {
    if (!enableSaveProgress || typeof window === 'undefined') return null;

    try {
      const saved = localStorage.getItem(saveKey);
      if (!saved) return null;

      const parsed = JSON.parse(saved);
      // Vérifier si les données sont encore valides
      if (parsed.values && parsed.currentStep) {
        // Vérifier si l'étape existe toujours
        const stepExists = steps.some(s => s.id === parsed.currentStep);
        if (stepExists) {
          return parsed.values;
        }
      }
      return null;
    } catch (error) {
      console.error('Erreur de chargement:', error);
      return null;
    }
  }, [enableSaveProgress, saveKey, steps]);

  const saveProgress = useCallback(() => {
    if (enableSaveProgress) {
      saveProgressToStorage(values);
    }
  }, [enableSaveProgress, saveProgressToStorage, values]);

  const loadProgress = useCallback((): T | null => {
    return loadProgressFromStorage();
  }, [loadProgressFromStorage]);

  const clearProgress = useCallback(() => {
    if (typeof window !== 'undefined') {
      try {
        localStorage.removeItem(saveKey);
      } catch (error) {
        console.error('Erreur de suppression:', error);
      }
    }
  }, [saveKey]);

  // ========================================================================
  // SAUVEGARDE AUTOMATIQUE
  // ========================================================================

  useEffect(() => {
    if (enableSaveProgress && saveDebounce > 0) {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
      saveTimerRef.current = setTimeout(() => {
        saveProgressToStorage(values);
      }, saveDebounce);
    }

    return () => {
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
    };
  }, [values, enableSaveProgress, saveDebounce, saveProgressToStorage]);

  // ========================================================================
  // VALIDATION
  // ========================================================================

  const validateStep = useCallback(async (stepId?: string): Promise<boolean> => {
    const targetStepId = stepId || currentStepId;
    const step = steps.find(s => s.id === targetStepId);
    if (!step) return true;

    setIsValidating(true);

    try {
      // Validation personnalisée de l'étape
      if (onStepValidate) {
        const result = await onStepValidate(targetStepId, values);
        if (typeof result === 'string') {
          setErrors(prev => ({ ...prev, [targetStepId]: result }));
          setIsValidating(false);
          return false;
        }
        if (result === false) {
          setErrors(prev => ({ ...prev, [targetStepId]: 'Étape invalide' }));
          setIsValidating(false);
          return false;
        }
      }

      // Validation via la fonction validate de l'étape
      if (step.validate) {
        const result = await step.validate(values);
        if (typeof result === 'string') {
          setErrors(prev => ({ ...prev, [targetStepId]: result }));
          setIsValidating(false);
          return false;
        }
        if (result === false) {
          setErrors(prev => ({ ...prev, [targetStepId]: 'Étape invalide' }));
          setIsValidating(false);
          return false;
        }
      }

      // Supprimer l'erreur si valide
      setErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[targetStepId];
        return newErrors;
      });

      return true;

    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Erreur de validation';
      setErrors(prev => ({ ...prev, [targetStepId]: errorMessage }));
      return false;

    } finally {
      setIsValidating(false);
    }
  }, [currentStepId, steps, values, onStepValidate]);

  const validateAll = useCallback(async (): Promise<boolean> => {
    let allValid = true;

    for (const step of steps) {
      const isValid = await validateStep(step.id);
      if (!isValid) {
        allValid = false;
        break;
      }
    }

    return allValid;
  }, [steps, validateStep]);

  // ========================================================================
  // NAVIGATION
  // ========================================================================

  const navigateTo = useCallback(async (stepId: string, direction: 'next' | 'prev' | 'jump' = 'jump'): Promise<boolean> => {
    const targetIndex = steps.findIndex(s => s.id === stepId);
    if (targetIndex === -1) return false;

    const targetStep = steps[targetIndex];
    if (targetStep.disabled) return false;

    // Vérifier si l'étape est accessible en mode linéaire
    if (navigationMode === 'linear') {
      // Ne pas sauter d'étapes en mode linéaire
      if (direction === 'jump' && Math.abs(targetIndex - currentStepIndex) > 1) {
        // Si c'est un saut, vérifier que toutes les étapes intermédiaires sont complétées
        const start = Math.min(currentStepIndex, targetIndex);
        const end = Math.max(currentStepIndex, targetIndex);
        for (let i = start; i <= end; i++) {
          if (i !== currentStepIndex && stepStatus[steps[i].id] !== 'completed') {
            toast({
              title: 'Navigation impossible',
              description: 'Veuillez compléter les étapes intermédiaires',
              variant: 'destructive',
            });
            return false;
          }
        }
      }
    }

    // Émettre l'événement de changement d'étape
    eventListenersRef.current.stepChange.forEach(callback => {
      callback({ stepId, direction, currentStep: targetStep });
    });

    // Mettre à jour le statut des étapes
    setStepStatus(prev => {
      const newStatus = { ...prev };
      // Marquer l'étape précédente comme complétée
      if (direction === 'next') {
        newStatus[currentStepId] = 'completed';
      }
      // Marquer la nouvelle étape comme active
      newStatus[stepId] = 'active';
      return newStatus;
    });

    setCurrentStepId(stepId);

    if (onStepChange) {
      onStepChange(stepId, direction);
    }

    return true;
  }, [steps, currentStepIndex, currentStepId, navigationMode, stepStatus, onStepChange, toast]);

  const next = useCallback(async (): Promise<boolean> => {
    if (isLastStep) return false;

    // Valider l'étape courante avant de passer à la suivante
    const isValid = await validateStep();
    if (!isValid) {
      toast({
        title: 'Erreur de validation',
        description: 'Veuillez corriger les erreurs avant de continuer',
        variant: 'destructive',
      });
      return false;
    }

    // Vérifier si l'étape courante peut être quittée
    if (currentStep.onLeave) {
      const canLeave = await currentStep.onLeave(values);
      if (!canLeave) return false;
    }

    const nextIndex = currentStepIndex + 1;
    if (nextIndex >= steps.length) return false;

    const nextStep = steps[nextIndex];
    if (nextStep.disabled) {
      // Sauter les étapes désactivées
      return navigateTo(steps[Math.min(nextIndex + 1, steps.length - 1)].id, 'next');
    }

    // Appeler onEnter de l'étape suivante
    if (nextStep.onEnter) {
      await nextStep.onEnter(values);
    }

    const success = await navigateTo(nextStep.id, 'next');

    if (success && nextStep.onEnterComplete) {
      nextStep.onEnterComplete(values);
    }

    if (currentStep.onLeaveComplete) {
      currentStep.onLeaveComplete(values);
    }

    return success;
  }, [isLastStep, validateStep, currentStep, currentStepIndex, steps, values, navigateTo]);

  const previous = useCallback(async (): Promise<boolean> => {
    if (isFirstStep) return false;

    const prevIndex = currentStepIndex - 1;
    if (prevIndex < 0) return false;

    const prevStep = steps[prevIndex];
    if (prevStep.disabled) {
      return navigateTo(steps[Math.max(prevIndex - 1, 0)].id, 'prev');
    }

    return navigateTo(prevStep.id, 'prev');
  }, [isFirstStep, currentStepIndex, steps, navigateTo]);

  const goTo = useCallback(async (stepId: string): Promise<boolean> => {
    const targetIndex = steps.findIndex(s => s.id === stepId);
    if (targetIndex === -1) return false;

    // Vérifier si l'étape est accessible
    if (!isStepAccessible(stepId)) {
      toast({
        title: 'Étape inaccessible',
        description: 'Cette étape n\'est pas encore accessible',
        variant: 'destructive',
      });
      return false;
    }

    // Valider l'étape courante
    if (targetIndex > currentStepIndex) {
      const isValid = await validateStep();
      if (!isValid) {
        toast({
          title: 'Erreur de validation',
          description: 'Veuillez corriger les erreurs avant de continuer',
          variant: 'destructive',
        });
        return false;
      }
    }

    return navigateTo(stepId, 'jump');
  }, [steps, currentStepIndex, isStepAccessible, validateStep, navigateTo, toast]);

  const goToFirst = useCallback(async (): Promise<boolean> => {
    return goTo(steps[0].id);
  }, [goTo, steps]);

  const goToLast = useCallback(async (): Promise<boolean> => {
    return goTo(steps[steps.length - 1].id);
  }, [goTo, steps]);

  const goBack = useCallback(async (stepsCount: number): Promise<boolean> => {
    const targetIndex = Math.max(0, currentStepIndex - stepsCount);
    return goTo(steps[targetIndex].id);
  }, [currentStepIndex, goTo, steps]);

  const goForward = useCallback(async (stepsCount: number): Promise<boolean> => {
    const targetIndex = Math.min(steps.length - 1, currentStepIndex + stepsCount);
    return goTo(steps[targetIndex].id);
  }, [currentStepIndex, goTo, steps]);

  const skip = useCallback(async (): Promise<boolean> => {
    if (!isStepOptional) {
      toast({
        title: 'Étape obligatoire',
        description: 'Cette étape ne peut pas être sautée',
        variant: 'destructive',
      });
      return false;
    }

    setStepStatus(prev => ({ ...prev, [currentStepId]: 'skipped' }));
    return next();
  }, [isStepOptional, currentStepId, next, toast]);

  const complete = useCallback(async (): Promise<void> => {
    // Valider toutes les étapes
    const isValid = await validateAll();
    if (!isValid) {
      toast({
        title: 'Erreur de validation',
        description: 'Toutes les étapes doivent être valides pour terminer',
        variant: 'destructive',
      });
      return;
    }

    // Vérifier que toutes les étapes obligatoires sont complétées
    const hasIncompleteSteps = steps.some(step => 
      !step.optional && stepStatus[step.id] !== 'completed' && stepStatus[step.id] !== 'skipped'
    );

    if (hasIncompleteSteps) {
      toast({
        title: 'Étapes incomplètes',
        description: 'Veuillez compléter toutes les étapes obligatoires',
        variant: 'destructive',
      });
      return;
    }

    setIsComplete(true);

    // Émettre l'événement de completion
    eventListenersRef.current.complete.forEach(callback => {
      callback(values);
    });

    if (onComplete) {
      onComplete(values);
    }

    toast({
      title: 'Félicitations !',
      description: 'Le formulaire a été complété avec succès',
      variant: 'success',
    });

    // Effacer la progression sauvegardée
    clearProgress();
  }, [validateAll, steps, stepStatus, values, onComplete, clearProgress, toast]);

  const cancel = useCallback(() => {
    // Émettre l'événement d'annulation
    eventListenersRef.current.cancel.forEach(callback => {
      callback();
    });

    if (onCancel) {
      onCancel();
    }

    clearProgress();
  }, [onCancel, clearProgress]);

  // ========================================================================
  // ACCESSIBILITÉ
  // ========================================================================

  const canNavigate = useCallback((direction: 'next' | 'prev'): boolean => {
    if (direction === 'next') {
      return !isLastStep && !isComplete;
    } else {
      return !isFirstStep && !isComplete;
    }
  }, [isLastStep, isFirstStep, isComplete]);

  const isStepAccessible = useCallback((stepId: string): boolean => {
    const targetIndex = steps.findIndex(s => s.id === stepId);
    if (targetIndex === -1) return false;

    const step = steps[targetIndex];
    if (step.disabled) return false;

    // En mode linéaire, seules les étapes précédentes ou l'étape courante sont accessibles
    if (navigationMode === 'linear') {
      if (targetIndex > currentStepIndex) {
        // Vérifier si toutes les étapes précédentes sont complétées
        for (let i = 0; i < targetIndex; i++) {
          if (stepStatus[steps[i].id] !== 'completed') {
            return false;
          }
        }
        return true;
      }
      return targetIndex <= currentStepIndex;
    }

    // En mode libre, toutes les étapes non désactivées sont accessibles
    return true;
  }, [steps, currentStepIndex, navigationMode, stepStatus]);

  // ========================================================================
  // DONNÉES
  // ========================================================================

  const setValues = useCallback((newValues: Partial<T>) => {
    setValuesState(prev => ({ ...prev, ...newValues }));
  }, []);

  const setFieldValue = useCallback(<K extends keyof T>(field: K, value: T[K]) => {
    setValuesState(prev => ({ ...prev, [field]: value }));
  }, []);

  const reset = useCallback(() => {
    setValuesState(initialDataRef.current);
    setCurrentStepId(initialStepRef.current);
    setStepStatus(() => {
      const status: Record<string, any> = {};
      steps.forEach((step, index) => {
        status[step.id] = index === 0 ? 'active' : 'idle';
      });
      return status;
    });
    setIsComplete(false);
    setErrors({});
    clearProgress();
  }, [steps, clearProgress]);

  const load = useCallback((data: T) => {
    setValuesState(data);
  }, []);

  // ========================================================================
  // ÉVÉNEMENTS
  // ========================================================================

  const on = useCallback((event: 'stepChange' | 'complete' | 'cancel' | 'error', callback: (data: any) => void) => {
    eventListenersRef.current[event].push(callback);
    return () => {
      eventListenersRef.current[event] = eventListenersRef.current[event].filter(cb => cb !== callback);
    };
  }, []);

  // ========================================================================
  // DÉBOGAGE
  // ========================================================================

  const debug = useCallback(() => {
    console.group('🔍 Form Wizard Debug');
    console.log('Current Step:', currentStepId, currentStep);
    console.log('Step Index:', currentStepIndex);
    console.log('Steps:', steps);
    console.log('Step Status:', stepStatus);
    console.log('Values:', values);
    console.log('Errors:', errors);
    console.log('Is Complete:', isComplete);
    console.log('Is Validating:', isValidating);
    console.log('Progress:', progress);
    console.log('Is First Step:', isFirstStep);
    console.log('Is Last Step:', isLastStep);
    console.log('Is Step Optional:', isStepOptional);
    console.groupEnd();
  }, [currentStepId, currentStep, currentStepIndex, steps, stepStatus, values, errors, isComplete, isValidating, progress, isFirstStep, isLastStep, isStepOptional]);

  // ========================================================================
  // NAVIGATION OBJECT
  // ========================================================================

  const navigation: WizardNavigation = {
    next,
    previous,
    goTo,
    goToFirst,
    goToLast,
    goBack,
    goForward,
    skip,
    complete,
    cancel,
    canNavigate,
    isStepAccessible,
  };

  // ========================================================================
  // EFFETS
  // ========================================================================

  // Charger la progression sauvegardée au montage
  useEffect(() => {
    if (persistData && enableSaveProgress) {
      const saved = loadProgressFromStorage();
      if (saved) {
        // Trouver l'étape sauvegardée
        const savedStep = steps.find(s => s.id === currentStepId);
        if (savedStep) {
          // Garder l'étape sauvegardée
        }
      }
    }
  }, [persistData, enableSaveProgress, loadProgressFromStorage, steps, currentStepId]);

  // ========================================================================
  // CLEANUP
  // ========================================================================

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (saveTimerRef.current) {
        clearTimeout(saveTimerRef.current);
      }
    };
  }, []);

  // ========================================================================
  // RETOUR
  // ========================================================================

  return {
    values,
    setValues,
    setFieldValue,
    reset,
    load,
    currentStep,
    currentStepIndex,
    steps,
    stepStatus,
    navigation,
    isComplete,
    isInProgress,
    progress,
    isStepValid: errors[currentStepId] === undefined,
    isFirstStep,
    isLastStep,
    isStepOptional,
    errors,
    validateStep,
    validateAll,
    saveProgress,
    loadProgress,
    clearProgress,
    debug,
    on,
  };
}

// ============================================================================
// EXPORTS
// ============================================================================

export default useFormWizard;

// apps/web/src/components/forms/hooks/useFormSubmit.ts
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

export type SubmitStatus = 'idle' | 'submitting' | 'success' | 'error' | 'validation-error';

export type SubmitRetryConfig = {
  /** Nombre maximum de tentatives */
  maxRetries?: number;
  /** Délai entre les tentatives (ms) */
  retryDelay?: number;
  /** Stratégie de retry */
  strategy?: 'fixed' | 'exponential' | 'linear';
  /** Conditions de retry */
  shouldRetry?: (error: any) => boolean;
};

export type SubmitOptions<T = any> = {
  /** Données à soumettre */
  data: T;
  /** Callback de soumission */
  onSubmit: (data: T) => Promise<any>;
  /** Callback de succès */
  onSuccess?: (result: any, data: T) => void;
  /** Callback d'erreur */
  onError?: (error: any, data: T) => void;
  /** Callback de validation */
  onValidate?: (data: T) => boolean | Promise<boolean> | string | Promise<string>;
  /** Configuration de retry */
  retry?: SubmitRetryConfig;
  /** Désactiver la notification de succès */
  disableSuccessToast?: boolean;
  /** Désactiver la notification d'erreur */
  disableErrorToast?: boolean;
  /** Message de succès personnalisé */
  successMessage?: string;
  /** Message d'erreur personnalisé */
  errorMessage?: string;
  /** Timeout de la requête (ms) */
  timeout?: number;
  /** Abort controller */
  signal?: AbortSignal;
};

export type UseFormSubmitReturn<T = any> = {
  /** Statut de la soumission */
  status: SubmitStatus;
  /** Est-ce que le formulaire est en cours de soumission */
  isSubmitting: boolean;
  /** Est-ce que la soumission a réussi */
  isSuccess: boolean;
  /** Est-ce que la soumission a échoué */
  isError: boolean;
  /** Est-ce que la soumission est en validation */
  isValidating: boolean;
  /** Erreur de soumission */
  error: any;
  /** Résultat de la soumission */
  result: any;
  /** Nombre de tentatives */
  attempts: number;
  /** Nombre maximum de tentatives */
  maxRetries: number;
  /** Temps écoulé (ms) */
  elapsedTime: number;
  /** Soumettre le formulaire */
  submit: (options?: Partial<SubmitOptions<T>>) => Promise<any>;
  /** Réinitialiser l'état */
  reset: () => void;
  /** Annuler la soumission */
  cancel: () => void;
  /** Retenter la soumission */
  retry: () => Promise<any>;
  /** Abort controller */
  abortController: AbortController | null;
};

// ============================================================================
// CONSTANTES
// ============================================================================

const DEFAULT_MAX_RETRIES = 3;
const DEFAULT_RETRY_DELAY = 1000;
const DEFAULT_TIMEOUT = 30000;
const DEFAULT_SUCCESS_MESSAGE = 'Soumission réussie';
const DEFAULT_ERROR_MESSAGE = 'Erreur lors de la soumission';

// ============================================================================
// HOOK PRINCIPAL
// ============================================================================

export function useFormSubmit<T = any>(
  defaultOptions?: Partial<SubmitOptions<T>>
): UseFormSubmitReturn<T> {
  const {
    onSubmit: defaultOnSubmit,
    onSuccess: defaultOnSuccess,
    onError: defaultOnError,
    onValidate: defaultOnValidate,
    retry: defaultRetry = {},
    disableSuccessToast: defaultDisableSuccessToast = false,
    disableErrorToast: defaultDisableErrorToast = false,
    successMessage: defaultSuccessMessage = DEFAULT_SUCCESS_MESSAGE,
    errorMessage: defaultErrorMessage = DEFAULT_ERROR_MESSAGE,
    timeout: defaultTimeout = DEFAULT_TIMEOUT,
  } = defaultOptions || {};

  // ========================================================================
  // TOAST
  // ========================================================================

  const { toast } = useToast();

  // ========================================================================
  // RÉFÉRENCES
  // ========================================================================

  const abortControllerRef = useRef<AbortController | null>(null);
  const timeoutRef = useRef<NodeJS.Timeout | null>(null);
  const retryTimerRef = useRef<NodeJS.Timeout | null>(null);
  const isMountedRef = useRef(true);
  const currentDataRef = useRef<T | null>(null);
  const currentOptionsRef = useRef<SubmitOptions<T> | null>(null);

  // ========================================================================
  // ÉTATS
  // ========================================================================

  const [status, setStatus] = useState<SubmitStatus>('idle');
  const [error, setError] = useState<any>(null);
  const [result, setResult] = useState<any>(null);
  const [attempts, setAttempts] = useState<number>(0);
  const [elapsedTime, setElapsedTime] = useState<number>(0);
  const [startTime, setStartTime] = useState<number>(0);
  const [isCancelled, setIsCancelled] = useState<boolean>(false);

  // ========================================================================
  // DÉRIVÉS
  // ========================================================================

  const isSubmitting = status === 'submitting';
  const isSuccess = status === 'success';
  const isError = status === 'error';
  const isValidating = status === 'validation-error';

  const maxRetries = defaultRetry.maxRetries ?? DEFAULT_MAX_RETRIES;
  const retryDelay = defaultRetry.retryDelay ?? DEFAULT_RETRY_DELAY;
  const retryStrategy = defaultRetry.strategy ?? 'fixed';
  const shouldRetry = defaultRetry.shouldRetry;

  // ========================================================================
  // CALCUL DU DÉLAI DE RETRY
  // ========================================================================

  const getRetryDelay = useCallback((attempt: number): number => {
    switch (retryStrategy) {
      case 'exponential':
        return retryDelay * Math.pow(2, attempt - 1);
      case 'linear':
        return retryDelay * attempt;
      case 'fixed':
      default:
        return retryDelay;
    }
  }, [retryStrategy, retryDelay]);

  // ========================================================================
  // SOUMISSION
  // ========================================================================

  const submit = useCallback(async (options?: Partial<SubmitOptions<T>>): Promise<any> => {
    // Fusionner les options
    const mergedOptions: SubmitOptions<T> = {
      data: (options?.data ?? currentOptionsRef.current?.data ?? {}) as T,
      onSubmit: options?.onSubmit ?? defaultOnSubmit,
      onSuccess: options?.onSuccess ?? defaultOnSuccess,
      onError: options?.onError ?? defaultOnError,
      onValidate: options?.onValidate ?? defaultOnValidate,
      retry: { ...defaultRetry, ...options?.retry },
      disableSuccessToast: options?.disableSuccessToast ?? defaultDisableSuccessToast,
      disableErrorToast: options?.disableErrorToast ?? defaultDisableErrorToast,
      successMessage: options?.successMessage ?? defaultSuccessMessage,
      errorMessage: options?.errorMessage ?? defaultErrorMessage,
      timeout: options?.timeout ?? defaultTimeout,
      signal: options?.signal,
    };

    const { data, onSubmit, onSuccess, onError, onValidate } = mergedOptions;

    // Sauvegarder les options
    currentOptionsRef.current = mergedOptions;
    currentDataRef.current = data;

    // Annuler la soumission précédente
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }

    // Créer un nouvel AbortController
    const abortController = new AbortController();
    abortControllerRef.current = abortController;
    const signal = mergedOptions.signal || abortController.signal;

    // Réinitialiser l'état
    setIsCancelled(false);
    setError(null);
    setResult(null);
    setAttempts(0);
    setElapsedTime(0);
    setStartTime(Date.now());
    setStatus('submitting');

    // Validation
    if (onValidate) {
      try {
        const validationResult = await onValidate(data);
        if (typeof validationResult === 'string') {
          setStatus('validation-error');
          setError(validationResult);
          if (!mergedOptions.disableErrorToast) {
            toast({
              title: 'Erreur de validation',
              description: validationResult,
              variant: 'destructive',
            });
          }
          throw new Error(validationResult);
        }
        if (validationResult === false) {
          const msg = 'Validation échouée';
          setStatus('validation-error');
          setError(msg);
          if (!mergedOptions.disableErrorToast) {
            toast({
              title: 'Erreur de validation',
              description: msg,
              variant: 'destructive',
            });
          }
          throw new Error(msg);
        }
      } catch (err) {
        if (err instanceof Error && err.message !== 'Validation échouée') {
          throw err;
        }
        return;
      }
    }

    // Timeout
    if (mergedOptions.timeout && mergedOptions.timeout > 0) {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      timeoutRef.current = setTimeout(() => {
        abortController.abort();
        const error = new Error('La requête a expiré');
        setStatus('error');
        setError(error);
        if (!mergedOptions.disableErrorToast) {
          toast({
            title: 'Erreur',
            description: error.message,
            variant: 'destructive',
          });
        }
        if (onError) {
          onError(error, data);
        }
      }, mergedOptions.timeout);
    }

    // Fonction de soumission avec retry
    const performSubmit = async (attempt: number): Promise<any> => {
      if (signal.aborted) {
        throw new Error('Soumission annulée');
      }

      try {
        // Mettre à jour le statut
        setStatus('submitting');
        setAttempts(attempt);

        const startAttemptTime = Date.now();
        const result = await onSubmit(data);
        const endAttemptTime = Date.now();

        // Succès
        setStatus('success');
        setResult(result);
        setElapsedTime(endAttemptTime - startTime);

        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
        }

        if (!mergedOptions.disableSuccessToast) {
          toast({
            title: 'Succès',
            description: mergedOptions.successMessage || DEFAULT_SUCCESS_MESSAGE,
            variant: 'success',
          });
        }

        if (onSuccess) {
          onSuccess(result, data);
        }

        return result;

      } catch (err) {
        // Vérifier si c'est une erreur d'annulation
        if (signal.aborted || err?.name === 'AbortError') {
          setStatus('idle');
          setError(null);
          throw err;
        }

        // Vérifier si on doit retenter
        const shouldRetryNow = shouldRetry ? shouldRetry(err) : true;
        const isLastAttempt = attempt >= maxRetries;

        if (!isLastAttempt && shouldRetryNow) {
          const delay = getRetryDelay(attempt + 1);
          await new Promise((resolve) => {
            retryTimerRef.current = setTimeout(resolve, delay);
          });
          return performSubmit(attempt + 1);
        }

        // Erreur finale
        setStatus('error');
        setError(err);
        setElapsedTime(Date.now() - startTime);

        if (timeoutRef.current) {
          clearTimeout(timeoutRef.current);
        }

        if (!mergedOptions.disableErrorToast) {
          toast({
            title: 'Erreur',
            description: mergedOptions.errorMessage || err?.message || DEFAULT_ERROR_MESSAGE,
            variant: 'destructive',
          });
        }

        if (onError) {
          onError(err, data);
        }

        throw err;
      }
    };

    try {
      return await performSubmit(1);
    } catch (err) {
      if (err instanceof Error && err.message === 'Soumission annulée') {
        // Annulation gérée silencieusement
        return;
      }
      throw err;
    }
  }, [
    defaultOnSubmit,
    defaultOnSuccess,
    defaultOnError,
    defaultOnValidate,
    defaultRetry,
    defaultDisableSuccessToast,
    defaultDisableErrorToast,
    defaultSuccessMessage,
    defaultErrorMessage,
    defaultTimeout,
    toast,
    maxRetries,
    getRetryDelay,
    shouldRetry,
    startTime,
  ]);

  // ========================================================================
  // RETRY
  // ========================================================================

  const retry = useCallback(async (): Promise<any> => {
    if (!currentDataRef.current || !currentOptionsRef.current) {
      throw new Error('Aucune soumission à retenter');
    }

    setStatus('idle');
    setError(null);
    setResult(null);
    setAttempts(0);
    setElapsedTime(0);
    setIsCancelled(false);

    return submit(currentOptionsRef.current);
  }, [submit]);

  // ========================================================================
  // RÉINITIALISATION
  // ========================================================================

  const reset = useCallback(() => {
    setStatus('idle');
    setError(null);
    setResult(null);
    setAttempts(0);
    setElapsedTime(0);
    setIsCancelled(false);
    currentDataRef.current = null;
    currentOptionsRef.current = null;

    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  // ========================================================================
  // ANNULATION
  // ========================================================================

  const cancel = useCallback(() => {
    setIsCancelled(true);
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
    if (retryTimerRef.current) {
      clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
    setStatus('idle');
    setError(null);
  }, []);

  // ========================================================================
  // CLEANUP
  // ========================================================================

  useEffect(() => {
    isMountedRef.current = true;
    return () => {
      isMountedRef.current = false;
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current);
      }
      if (retryTimerRef.current) {
        clearTimeout(retryTimerRef.current);
      }
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, []);

  // ========================================================================
  // RETOUR
  // ========================================================================

  return {
    status,
    isSubmitting,
    isSuccess,
    isError,
    isValidating,
    error,
    result,
    attempts,
    maxRetries,
    elapsedTime,
    submit,
    reset,
    cancel,
    retry,
    abortController: abortControllerRef.current,
  };
}

// ============================================================================
// EXPORTS
// ============================================================================

export default useFormSubmit;

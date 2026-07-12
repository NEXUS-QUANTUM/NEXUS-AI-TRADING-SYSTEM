// apps/web/src/components/forms/auth/VerifyEmailForm.tsx
'use client';

import React, {
  useState,
  useCallback,
  useRef,
  useEffect,
  forwardRef,
  Ref,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  EnvelopeIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ArrowPathIcon,
  KeyIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  CheckIcon,
  XMarkIcon,
  ClockIcon,
  ExclamationCircleIcon,
  DocumentTextIcon,
  ClipboardDocumentIcon,
  ShieldCheckIcon,
  AtSymbolIcon,
  UserIcon,
  DevicePhoneMobileIcon,
  EnvelopeOpenIcon,
  PaperAirplaneIcon,
  SparklesIcon,
  RocketLaunchIcon,
  GiftIcon,
  StarIcon,
  HeartIcon,
} from '@heroicons/react/24/outline';
import {
  CheckCircleIcon as CheckCircleSolid,
  ExclamationCircleIcon as ExclamationCircleSolid,
} from '@heroicons/react/24/solid';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Separator } from '@/components/common/Separator';
import { Progress } from '@/components/common/Progress';
import { Tooltip } from '@/components/common/Tooltip';
import { useToast } from '@/hooks/useToast';
import { useAuth } from '@/hooks/useAuth';

// ============================================================================
// TYPES
// ============================================================================

export type VerifyEmailStep = 'code' | 'success' | 'error';

export interface VerifyEmailFormData {
  /** Email à vérifier */
  email: string;
  /** Code de vérification */
  code: string;
  /** User ID (optionnel) */
  userId?: string;
}

export interface VerifyEmailFormProps {
  // --- Contrôle ---
  /** Email initial */
  initialEmail?: string;
  /** Code initial */
  initialCode?: string;
  /** Étape initiale */
  initialStep?: VerifyEmailStep;
  /** Données initiales */
  initialData?: Partial<VerifyEmailFormData>;
  /** Callback de soumission */
  onSubmit?: (data: VerifyEmailFormData) => void | Promise<void>;
  /** Callback de succès */
  onSuccess?: (data: VerifyEmailFormData) => void;
  /** Callback d'erreur */
  onError?: (error: string) => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de changement d'étape */
  onStepChange?: (step: VerifyEmailStep) => void;
  /** Callback pour renvoyer le code */
  onResend?: (email: string) => void | Promise<void>;

  // --- Apparence ---
  /** Titre du formulaire */
  title?: string;
  /** Sous-titre */
  subtitle?: string;
  /** Classes additionnelles */
  className?: string;
  /** Variante de la carte */
  variant?: 'default' | 'glass' | 'solid' | 'outlined';
  /** Taille du formulaire */
  size?: 'sm' | 'md' | 'lg';
  /** Afficher le logo */
  showLogo?: boolean;
  /** Afficher le compteur de temps */
  showTimer?: boolean;

  // --- Configuration ---
  /** Délai de renvoi du code (secondes) */
  resendCooldown?: number;
  /** Nombre maximum de tentatives */
  maxAttempts?: number;
  /** Longueur du code */
  codeLength?: number;
  /** Délai d'expiration du code (secondes) */
  codeExpiry?: number;
  /** URL de redirection après succès */
  redirectUrl?: string;
  /** Auto-redirection après succès */
  autoRedirect?: boolean;
  /** Délai avant redirection (secondes) */
  redirectDelay?: number;

  // --- États ---
  /** État de chargement */
  isLoading?: boolean;
  /** État d'erreur */
  error?: string | null;
  /** Message de succès */
  success?: string | null;
  /** Désactiver le formulaire */
  disabled?: boolean;
  /** Email déjà vérifié */
  isVerified?: boolean;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ID */
  id?: string;

  // --- Avancé ---
  /** Callback de validation de l'email */
  validateEmail?: (email: string) => boolean | string;
  /** Callback de validation du code */
  validateCode?: (code: string) => boolean | string;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const DEFAULT_CODE_LENGTH = 6;
const DEFAULT_RESEND_COOLDOWN = 60;
const DEFAULT_MAX_ATTEMPTS = 5;
const DEFAULT_CODE_EXPIRY = 300;
const DEFAULT_REDIRECT_DELAY = 3;

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const VerifyEmailForm = forwardRef<HTMLDivElement, VerifyEmailFormProps>(
  (props, ref) => {
    const {
      // Contrôle
      initialEmail = '',
      initialCode = '',
      initialStep = 'code',
      initialData = {},
      onSubmit,
      onSuccess,
      onError,
      onCancel,
      onStepChange,
      onResend,

      // Apparence
      title = 'Vérifier votre email',
      subtitle = 'Un code de vérification a été envoyé à votre adresse email',
      className,
      variant = 'default',
      size = 'md',
      showLogo = true,
      showTimer = true,

      // Configuration
      resendCooldown = DEFAULT_RESEND_COOLDOWN,
      maxAttempts = DEFAULT_MAX_ATTEMPTS,
      codeLength = DEFAULT_CODE_LENGTH,
      codeExpiry = DEFAULT_CODE_EXPIRY,
      redirectUrl = '/dashboard',
      autoRedirect = true,
      redirectDelay = DEFAULT_REDIRECT_DELAY,

      // États
      isLoading = false,
      error = null,
      success = null,
      disabled = false,
      isVerified = false,

      // Accessibilité
      ariaLabel = 'Formulaire de vérification email',
      id,

      // Avancé
      validateEmail: externalValidateEmail,
      validateCode: externalValidateCode,
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const formRef = useRef<HTMLFormElement>(null);
    const codeInputRef = useRef<HTMLInputElement>(null);
    const emailInputRef = useRef<HTMLInputElement>(null);
    const timerRef = useRef<NodeJS.Timeout | null>(null);
    const redirectTimerRef = useRef<NodeJS.Timeout | null>(null);

    // ========================================================================
    // HOOKS
    // ========================================================================

    const { toast } = useToast();
    const { verifyEmail, resendVerification, user } = useAuth();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [step, setStep] = useState<VerifyEmailStep>(initialStep);
    const [formData, setFormData] = useState<VerifyEmailFormData>({
      email: initialEmail || user?.email || '',
      code: initialCode,
      userId: user?.id,
      ...initialData,
    });
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [attempts, setAttempts] = useState(0);
    const [isLocked, setIsLocked] = useState(false);
    const [resendCooldownLeft, setResendCooldownLeft] = useState(0);
    const [isResending, setIsResending] = useState(false);
    const [timeRemaining, setTimeRemaining] = useState(codeExpiry);
    const [codeProgress, setCodeProgress] = useState(100);
    const [isEmailValid, setIsEmailValid] = useState(false);
    const [showResendSuccess, setShowResendSuccess] = useState(false);
    const [redirectCountdown, setRedirectCountdown] = useState(redirectDelay);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validateEmail = useCallback((email: string): boolean | string => {
      if (externalValidateEmail) {
        return externalValidateEmail(email);
      }
      const emailRegex = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
      if (!email) return 'L\'email est requis';
      if (!emailRegex.test(email)) return 'Veuillez entrer un email valide';
      return true;
    }, [externalValidateEmail]);

    const validateCode = useCallback((code: string): boolean | string => {
      if (externalValidateCode) {
        return externalValidateCode(code);
      }
      if (!code) return 'Le code est requis';
      if (!/^\d{6}$/.test(code)) return 'Le code doit contenir 6 chiffres';
      return true;
    }, [externalValidateCode]);

    // ========================================================================
    // GESTIONNAIRES DE CHAMPS
    // ========================================================================

    const handleFieldChange = useCallback(<K extends keyof VerifyEmailFormData>(
      field: K,
      value: VerifyEmailFormData[K]
    ) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
      setFormErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });

      if (field === 'email') {
        const result = validateEmail(value as string);
        setIsEmailValid(typeof result === 'boolean' && result);
      }
    }, [validateEmail]);

    // ========================================================================
    // VALIDATION DU FORMULAIRE
    // ========================================================================

    const validateStep = useCallback((): boolean => {
      const errors: Record<string, string> = {};
      let isValid = true;

      if (step === 'code') {
        const codeResult = validateCode(formData.code);
        if (typeof codeResult === 'string') {
          errors.code = codeResult;
          isValid = false;
        }
        if (!formData.email) {
          errors.email = 'L\'email est requis';
          isValid = false;
        }
      }

      setFormErrors(errors);
      return isValid;
    }, [step, formData, validateCode]);

    // ========================================================================
    // SOUMISSION
    // ========================================================================

    const handleSubmit = useCallback(async (e: React.FormEvent) => {
      e.preventDefault();

      if (isSubmitting || isLoading || disabled || isLocked || isVerified) return;

      if (!validateStep()) {
        toast({
          title: 'Erreur de validation',
          description: 'Veuillez corriger les erreurs du formulaire',
          variant: 'destructive',
        });
        return;
      }

      if (attempts >= maxAttempts) {
        setIsLocked(true);
        toast({
          title: 'Trop de tentatives',
          description: 'Compte temporairement verrouillé. Veuillez réessayer plus tard.',
          variant: 'destructive',
        });
        return;
      }

      setIsSubmitting(true);
      setAttempts((prev) => prev + 1);

      try {
        // Vérification du code
        const result = await verifyEmail({
          email: formData.email,
          code: formData.code,
          userId: formData.userId,
        });

        if (result.success) {
          setStep('success');
          if (onStepChange) onStepChange('success');
          if (onSuccess) onSuccess(formData);

          toast({
            title: 'Email vérifié',
            description: 'Votre adresse email a été vérifiée avec succès',
            variant: 'success',
          });

          if (debug) {
            console.log('Email vérifié:', formData.email);
          }

          // Auto-redirection
          if (autoRedirect && redirectUrl) {
            redirectTimerRef.current = setInterval(() => {
              setRedirectCountdown((prev) => {
                if (prev <= 1) {
                  if (redirectTimerRef.current) clearInterval(redirectTimerRef.current);
                  window.location.href = redirectUrl;
                  return 0;
                }
                return prev - 1;
              });
            }, 1000);
          }
        } else {
          throw new Error(result.message || 'Code invalide');
        }

      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Erreur de vérification';
        if (onError) onError(errorMessage);
        
        // Vérifier si l'erreur est liée à l'expiration du code
        if (errorMessage.includes('expiré')) {
          setFormErrors((prev) => ({ ...prev, code: 'Le code a expiré. Veuillez en demander un nouveau.' }));
        }

        toast({
          title: 'Erreur',
          description: errorMessage,
          variant: 'destructive',
        });
        if (debug) console.error('Erreur de vérification:', err);
      } finally {
        setIsSubmitting(false);
      }
    }, [
      isSubmitting,
      isLoading,
      disabled,
      isLocked,
      isVerified,
      validateStep,
      attempts,
      maxAttempts,
      formData,
      verifyEmail,
      onSuccess,
      onError,
      onStepChange,
      autoRedirect,
      redirectUrl,
      toast,
      debug,
    ]);

    // ========================================================================
    // RENVOI DU CODE
    // ========================================================================

    const handleResend = useCallback(async () => {
      if (isResending || resendCooldownLeft > 0 || isLocked || isVerified) return;

      if (!formData.email) {
        toast({
          title: 'Email requis',
          description: 'Veuillez entrer votre adresse email',
          variant: 'destructive',
        });
        emailInputRef.current?.focus();
        return;
      }

      const emailResult = validateEmail(formData.email);
      if (typeof emailResult === 'string') {
        toast({
          title: 'Email invalide',
          description: emailResult,
          variant: 'destructive',
        });
        emailInputRef.current?.focus();
        return;
      }

      setIsResending(true);
      try {
        if (onResend) {
          await onResend(formData.email);
        } else {
          await resendVerification(formData.email);
        }

        setResendCooldownLeft(resendCooldown);
        setTimeRemaining(codeExpiry);
        setCodeProgress(100);
        setShowResendSuccess(true);

        if (timerRef.current) {
          clearInterval(timerRef.current);
        }

        // Timer de cooldown
        timerRef.current = setInterval(() => {
          setResendCooldownLeft((prev) => {
            if (prev <= 1) {
              if (timerRef.current) clearInterval(timerRef.current);
              return 0;
            }
            return prev - 1;
          });
        }, 1000);

        // Timer d'expiration du code
        const expiryTimer = setInterval(() => {
          setTimeRemaining((prev) => {
            const newTime = prev - 1;
            setCodeProgress((newTime / codeExpiry) * 100);
            if (newTime <= 0) {
              clearInterval(expiryTimer);
              setFormErrors((prev) => ({ ...prev, code: 'Le code a expiré' }));
              return 0;
            }
            return newTime;
          });
        }, 1000);

        toast({
          title: 'Code renvoyé',
          description: 'Un nouveau code a été envoyé à votre adresse email',
          duration: 4000,
          variant: 'success',
        });

        // Réinitialiser le champ code
        handleFieldChange('code', '');

        // Focus sur le champ code
        setTimeout(() => codeInputRef.current?.focus(), 100);

        setTimeout(() => setShowResendSuccess(false), 5000);

      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Erreur lors du renvoi';
        toast({
          title: 'Erreur',
          description: errorMessage,
          variant: 'destructive',
        });
      } finally {
        setIsResending(false);
      }
    }, [
      isResending,
      resendCooldownLeft,
      isLocked,
      isVerified,
      formData.email,
      validateEmail,
      onResend,
      resendVerification,
      resendCooldown,
      codeExpiry,
      handleFieldChange,
      toast,
    ]);

    // ========================================================================
    // TIMER D'EXPIRATION DU CODE
    // ========================================================================

    useEffect(() => {
      if (step === 'code' && formData.code) {
        const timer = setInterval(() => {
          setTimeRemaining((prev) => {
            const newTime = prev - 1;
            setCodeProgress((newTime / codeExpiry) * 100);
            if (newTime <= 0) {
              clearInterval(timer);
              setFormErrors((prev) => ({ ...prev, code: 'Le code a expiré' }));
              return 0;
            }
            return newTime;
          });
        }, 1000);

        return () => clearInterval(timer);
      }
    }, [step, formData.code, codeExpiry]);

    // ========================================================================
    // AUTO-VALIDATION SI DÉJÀ VÉRIFIÉ
    // ========================================================================

    useEffect(() => {
      if (isVerified) {
        setStep('success');
        if (onStepChange) onStepChange('success');
      }
    }, [isVerified, onStepChange]);

    // ========================================================================
    // CLEANUP
    // ========================================================================

    useEffect(() => {
      return () => {
        if (timerRef.current) {
          clearInterval(timerRef.current);
        }
        if (redirectTimerRef.current) {
          clearInterval(redirectTimerRef.current);
        }
      };
    }, []);

    // ========================================================================
    // RENDU
    // ========================================================================

    // --- Rendu du logo ---
    const renderLogo = () => {
      if (!showLogo) return null;

      return (
        <div className="flex justify-center mb-6">
          <div className="h-16 w-16 rounded-full bg-brand-500 flex items-center justify-center">
            <EnvelopeOpenIcon className="h-8 w-8 text-white" />
          </div>
        </div>
      );
    };

    // --- Rendu de l'étape Code ---
    const renderCodeStep = () => (
      <div className="space-y-4">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-brand-100 dark:bg-brand-900/30">
            <KeyIcon className="h-8 w-8 text-brand-600 dark:text-brand-400" />
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {formData.email ? (
              <>Un code de vérification a été envoyé à <strong>{formData.email}</strong></>
            ) : (
              <>Entrez votre email pour recevoir un code de vérification</>
            )}
          </p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            Veuillez vérifier votre boîte de réception (et vos spams)
          </p>
        </div>

        {!formData.email && (
          <div className="space-y-2">
            <label htmlFor="email" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Email <span className="text-red-500">*</span>
            </label>
            <Input
              ref={emailInputRef}
              id="email"
              type="email"
              placeholder="exemple@email.com"
              value={formData.email}
              onChange={(e) => handleFieldChange('email', e.target.value)}
              error={formErrors.email}
              disabled={disabled || isSubmitting || isLoading || isLocked || isVerified}
              autoFocus
              className="h-11"
              prefix={<AtSymbolIcon className="h-4 w-4 text-gray-400" />}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleResend();
                }
              }}
            />
          </div>
        )}

        <div className="space-y-2">
          <label htmlFor="code" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Code de vérification <span className="text-red-500">*</span>
          </label>
          <div className="relative">
            <Input
              ref={codeInputRef}
              id="code"
              type="text"
              placeholder="000000"
              value={formData.code}
              onChange={(e) => handleFieldChange('code', e.target.value)}
              error={formErrors.code}
              disabled={disabled || isSubmitting || isLoading || isLocked || isVerified}
              className="h-11 text-center text-lg font-mono tracking-widest"
              maxLength={codeLength}
              prefix={<KeyIcon className="h-4 w-4 text-gray-400" />}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  handleSubmit(e);
                }
              }}
            />
          </div>
          {formErrors.code && (
            <p className="text-sm text-red-600 dark:text-red-400">{formErrors.code}</p>
          )}
        </div>

        {/* Timer de progression */}
        {showTimer && formData.code && timeRemaining > 0 && (
          <div className="space-y-1">
            <div className="flex items-center justify-between text-xs text-gray-500 dark:text-gray-400">
              <span>Temps restant</span>
              <span>{Math.floor(timeRemaining / 60)}:{(timeRemaining % 60).toString().padStart(2, '0')}</span>
            </div>
            <Progress
              value={codeProgress}
              className="h-1"
              variant={codeProgress < 30 ? 'error' : codeProgress < 60 ? 'warning' : 'default'}
            />
          </div>
        )}

        <div className="flex flex-col gap-2">
          <div className="flex items-center justify-between text-sm">
            <button
              type="button"
              onClick={handleResend}
              disabled={isResending || resendCooldownLeft > 0 || isLocked || isVerified}
              className={cn(
                'text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300 transition-colors',
                (isResending || resendCooldownLeft > 0 || isLocked || isVerified) && 'opacity-50 cursor-not-allowed'
              )}
            >
              {isResending ? (
                <>
                  <ArrowPathIcon className="inline h-3 w-3 animate-spin mr-1" />
                  Envoi en cours...
                </>
              ) : resendCooldownLeft > 0 ? (
                `Renvoyer dans ${resendCooldownLeft}s`
              ) : isVerified ? (
                'Email déjà vérifié'
              ) : (
                'Renvoyer le code'
              )}
            </button>
            {onCancel && (
              <button
                type="button"
                onClick={onCancel}
                className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 transition-colors"
              >
                Annuler
              </button>
            )}
          </div>

          {showResendSuccess && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="flex items-center gap-2 text-sm text-green-600 dark:text-green-400"
            >
              <CheckCircleIcon className="h-4 w-4" />
              <span>Code renvoyé avec succès !</span>
            </motion.div>
          )}
        </div>

        {attempts > 0 && attempts < maxAttempts && !isLocked && (
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Tentatives restantes: {maxAttempts - attempts}
          </p>
        )}

        {isLocked && (
          <div className="flex items-center gap-2 rounded-lg bg-red-50 dark:bg-red-900/20 p-3 text-sm text-red-600 dark:text-red-400">
            <ClockIcon className="h-5 w-5 flex-shrink-0" />
            <span>
              Compte temporairement verrouillé. Veuillez réessayer plus tard.
            </span>
          </div>
        )}
      </div>
    );

    // --- Rendu de l'étape Success ---
    const renderSuccessStep = () => (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
          <CheckCircleIcon className="h-10 w-10 text-green-600 dark:text-green-400" />
        </div>
        <h3 className="mt-4 text-xl font-semibold text-gray-900 dark:text-white">
          {isVerified ? 'Email déjà vérifié !' : 'Email vérifié !'}
        </h3>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
          {isVerified 
            ? 'Votre adresse email a déjà été vérifiée.'
            : 'Votre adresse email a été vérifiée avec succès.'
          }
        </p>

        {autoRedirect && redirectUrl && (
          <div className="mt-4 w-full">
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Redirection vers le tableau de bord dans {redirectCountdown} secondes...
            </p>
            <Progress
              value={((redirectDelay - redirectCountdown) / redirectDelay) * 100}
              className="mt-2 h-1"
            />
          </div>
        )}

        <div className="mt-6 flex gap-3">
          <Button
            type="button"
            variant="primary"
            onClick={() => {
              if (redirectUrl) {
                window.location.href = redirectUrl;
              } else if (onCancel) {
                onCancel();
              }
            }}
          >
            {redirectUrl ? 'Accéder au tableau de bord' : 'Terminé'}
            <ArrowRightIcon className="ml-2 h-4 w-4" />
          </Button>
        </div>
      </div>
    );

    // --- Rendu de l'état verrouillé ---
    const renderLockedState = () => (
      <div className="mt-4 flex items-center gap-2 rounded-lg bg-red-50 dark:bg-red-900/20 p-3 text-sm text-red-600 dark:text-red-400">
        <ClockIcon className="h-5 w-5 flex-shrink-0" />
        <span>
          Compte temporairement verrouillé. Veuillez réessayer plus tard.
        </span>
      </div>
    );

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const isLockedScreen = isLocked;

    return (
      <Card
        ref={ref}
        id={id}
        className={cn(
          'w-full max-w-md mx-auto overflow-hidden',
          variant === 'glass' && 'bg-white/80 backdrop-blur-xl dark:bg-gray-900/80',
          variant === 'solid' && 'bg-white dark:bg-gray-900',
          variant === 'outlined' && 'border-2 border-gray-200 dark:border-gray-700 bg-transparent',
          className
        )}
        aria-label={ariaLabel}
      >
        {/* Header */}
        <CardHeader className="border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <CardTitle>{title}</CardTitle>
            {step !== 'success' && onCancel && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={onCancel}
                disabled={isSubmitting || isLoading}
              >
                Annuler
              </Button>
            )}
          </div>
          {subtitle && step === 'code' && (
            <p className="text-sm text-gray-500 dark:text-gray-400 text-center">
              {subtitle}
            </p>
          )}
          {step === 'code' && (
            <div className="flex justify-center mt-3">
              <Badge variant={isVerified ? 'success' : 'outline'} size="sm">
                {isVerified ? '✓ Vérifié' : 'En attente de vérification'}
              </Badge>
            </div>
          )}
        </CardHeader>

        {/* Logo */}
        {renderLogo()}

        {/* Contenu */}
        <CardContent className="p-6">
          <form ref={formRef} onSubmit={handleSubmit} noValidate>
            {/* Erreur globale */}
            {formErrors._form && (
              <div className="mb-4 flex items-start gap-2 rounded-lg bg-red-50 dark:bg-red-900/20 p-3 text-sm text-red-600 dark:text-red-400">
                <ExclamationTriangleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />
                <span>{formErrors._form}</span>
              </div>
            )}

            {/* Erreur externe */}
            {error && (
              <div className="mb-4 flex items-start gap-2 rounded-lg bg-red-50 dark:bg-red-900/20 p-3 text-sm text-red-600 dark:text-red-400">
                <ExclamationCircleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {/* Succès */}
            {success && step !== 'success' && (
              <div className="mb-4 flex items-start gap-2 rounded-lg bg-green-50 dark:bg-green-900/20 p-3 text-sm text-green-600 dark:text-green-400">
                <CheckCircleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />
                <span>{success}</span>
              </div>
            )}

            {/* Contenu de l'étape */}
            <AnimatePresence mode="wait">
              <motion.div
                key={step}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
              >
                {step === 'code' && renderCodeStep()}
                {step === 'success' && renderSuccessStep()}
              </motion.div>
            </AnimatePresence>

            {/* Compte verrouillé */}
            {isLockedScreen && renderLockedState()}
          </form>
        </CardContent>

        {/* Footer */}
        {step === 'code' && !isLockedScreen && !isVerified && (
          <CardFooter className="flex flex-col gap-3 border-t border-gray-200 dark:border-gray-700 p-6">
            <Button
              type="submit"
              variant="primary"
              className="w-full"
              onClick={handleSubmit}
              disabled={
                isSubmitting ||
                isLoading ||
                disabled ||
                isLockedScreen ||
                isVerified ||
                !formData.code
              }
              isLoading={isSubmitting || isLoading}
            >
              {isSubmitting ? 'Vérification...' : 'Vérifier l\'email'}
              <ArrowRightIcon className="ml-2 h-4 w-4" />
            </Button>

            {onCancel && (
              <Button
                type="button"
                variant="ghost"
                className="w-full"
                onClick={onCancel}
                disabled={isSubmitting || isLoading}
              >
                Annuler
              </Button>
            )}
          </CardFooter>
        )}

        {/* Footer succès */}
        {step === 'success' && (
          <CardFooter className="border-t border-gray-200 dark:border-gray-700 p-6">
            <Button
              type="button"
              variant="primary"
              className="w-full"
              onClick={() => {
                if (redirectUrl) {
                  window.location.href = redirectUrl;
                } else if (onCancel) {
                  onCancel();
                }
              }}
            >
              {redirectUrl ? 'Accéder au tableau de bord' : 'Terminé'}
            </Button>
          </CardFooter>
        )}
      </Card>
    );
  }
);

VerifyEmailForm.displayName = 'VerifyEmailForm';

export default VerifyEmailForm;

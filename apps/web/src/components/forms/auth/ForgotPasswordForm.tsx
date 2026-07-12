// apps/web/src/components/forms/auth/ForgotPasswordForm.tsx
'use client';

import React, {
  useState,
  useCallback,
  forwardRef,
  Ref,
  useRef,
  useEffect,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  EnvelopeIcon,
  ArrowLeftIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ArrowPathIcon,
  ShieldCheckIcon,
  KeyIcon,
  UserIcon,
  LockClosedIcon,
  EyeIcon,
  EyeSlashIcon,
  EnvelopeOpenIcon,
  PaperAirplaneIcon,
  ClockIcon,
  DevicePhoneMobileIcon,
  AtSymbolIcon,
} from '@heroicons/react/24/outline';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Separator } from '@/components/common/Separator';
import { Progress } from '@/components/common/Progress';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type ForgotPasswordStep = 'email' | 'verification' | 'confirmation' | 'success';

export interface ForgotPasswordFormData {
  /** Email de l'utilisateur */
  email: string;
  /** Code de vérification (si nécessaire) */
  verificationCode?: string;
  /** Nouveau mot de passe (si réinitialisation directe) */
  newPassword?: string;
  /** Confirmation du nouveau mot de passe */
  confirmPassword?: string;
}

export interface ForgotPasswordFormProps {
  // --- Contrôle ---
  /** Étape initiale */
  initialStep?: ForgotPasswordStep;
  /** Données initiales */
  initialData?: Partial<ForgotPasswordFormData>;
  /** Callback de soumission */
  onSubmit?: (data: ForgotPasswordFormData) => void | Promise<void>;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de retour */
  onBack?: () => void;
  /** Callback de changement d'étape */
  onStepChange?: (step: ForgotPasswordStep) => void;

  // --- Apparence ---
  /** Titre du formulaire */
  title?: string;
  /** Sous-titre du formulaire */
  subtitle?: string;
  /** Classes additionnelles */
  className?: string;
  /** Variante de la carte */
  variant?: 'default' | 'glass' | 'solid' | 'outlined';
  /** Taille du formulaire */
  size?: 'sm' | 'md' | 'lg';

  // --- États ---
  /** État de chargement */
  isLoading?: boolean;
  /** État d'erreur */
  error?: string | null;
  /** Message de succès */
  success?: string | null;
  /** Désactiver le formulaire */
  disabled?: boolean;

  // --- Configuration ---
  /** Méthode de vérification */
  verificationMethod?: 'email' | 'sms' | 'authenticator';
  /** Demander un code de vérification */
  requireVerification?: boolean;
  /** Demander un nouveau mot de passe */
  requireNewPassword?: boolean;
  /** Délai de renvoi du code (secondes) */
  resendCooldown?: number;
  /** Nombre maximum de tentatives */
  maxAttempts?: number;
  /** URL de redirection après succès */
  redirectUrl?: string;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ID */
  id?: string;

  // --- Avancé ---
  /** Callback de validation de l'email */
  validateEmail?: (email: string) => boolean | string;
  /** Callback de validation du mot de passe */
  validatePassword?: (password: string) => boolean | string;
  /** Callback de validation du code */
  validateCode?: (code: string) => boolean | string;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const ForgotPasswordForm = forwardRef<HTMLDivElement, ForgotPasswordFormProps>(
  (props, ref) => {
    const {
      // Contrôle
      initialStep = 'email',
      initialData = {},
      onSubmit,
      onCancel,
      onBack,
      onStepChange,

      // Apparence
      title = 'Mot de passe oublié',
      subtitle = 'Entrez votre email pour recevoir un lien de réinitialisation',
      className,
      variant = 'default',
      size = 'md',

      // États
      isLoading = false,
      error = null,
      success = null,
      disabled = false,

      // Configuration
      verificationMethod = 'email',
      requireVerification = true,
      requireNewPassword = true,
      resendCooldown = 60,
      maxAttempts = 3,
      redirectUrl = '/login',

      // Accessibilité
      ariaLabel = 'Formulaire de réinitialisation de mot de passe',
      id,

      // Avancé
      validateEmail: externalValidateEmail,
      validatePassword: externalValidatePassword,
      validateCode: externalValidateCode,
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const formRef = useRef<HTMLFormElement>(null);
    const emailInputRef = useRef<HTMLInputElement>(null);
    const codeInputRef = useRef<HTMLInputElement>(null);
    const passwordInputRef = useRef<HTMLInputElement>(null);
    const confirmPasswordInputRef = useRef<HTMLInputElement>(null);
    const timerRef = useRef<NodeJS.Timeout | null>(null);
    const attemptCountRef = useRef(0);

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [step, setStep] = useState<ForgotPasswordStep>(initialStep);
    const [formData, setFormData] = useState<ForgotPasswordFormData>({
      email: '',
      verificationCode: '',
      newPassword: '',
      confirmPassword: '',
      ...initialData,
    });
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [isResending, setIsResending] = useState(false);
    const [resendCooldown, setResendCooldown] = useState(0);
    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [attempts, setAttempts] = useState(0);
    const [isLocked, setIsLocked] = useState(false);
    const [emailSent, setEmailSent] = useState(false);
    const [passwordStrength, setPasswordStrength] = useState(0);

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

    const validatePassword = useCallback((password: string): boolean | string => {
      if (externalValidatePassword) {
        return externalValidatePassword(password);
      }

      if (!password) return 'Le mot de passe est requis';
      if (password.length < 8) return 'Le mot de passe doit contenir au moins 8 caractères';
      if (!/[A-Z]/.test(password)) return 'Le mot de passe doit contenir au moins une majuscule';
      if (!/[a-z]/.test(password)) return 'Le mot de passe doit contenir au moins une minuscule';
      if (!/[0-9]/.test(password)) return 'Le mot de passe doit contenir au moins un chiffre';
      if (!/[!@#$%^&*(),.?":{}|<>]/.test(password)) {
        return 'Le mot de passe doit contenir au moins un caractère spécial';
      }
      return true;
    }, [externalValidatePassword]);

    const validateCode = useCallback((code: string): boolean | string => {
      if (externalValidateCode) {
        return externalValidateCode(code);
      }

      if (!code) return 'Le code de vérification est requis';
      if (!/^\d{6}$/.test(code)) return 'Le code doit contenir 6 chiffres';
      return true;
    }, [externalValidateCode]);

    const validateConfirmPassword = useCallback((password: string, confirm: string): boolean | string => {
      if (!confirm) return 'Veuillez confirmer le mot de passe';
      if (password !== confirm) return 'Les mots de passe ne correspondent pas';
      return true;
    }, []);

    // ========================================================================
    // CALCUL DE LA FORCE DU MOT DE PASSE
    // ========================================================================

    const calculatePasswordStrength = useCallback((password: string): number => {
      if (!password) return 0;

      let score = 0;
      if (password.length >= 8) score += 20;
      if (password.length >= 12) score += 10;
      if (/[A-Z]/.test(password)) score += 15;
      if (/[a-z]/.test(password)) score += 15;
      if (/[0-9]/.test(password)) score += 15;
      if (/[!@#$%^&*(),.?":{}|<>]/.test(password)) score += 25;
      
      return Math.min(100, score);
    }, []);

    // ========================================================================
    // GESTIONNAIRES DE CHAMPS
    // ========================================================================

    const handleFieldChange = useCallback(<K extends keyof ForgotPasswordFormData>(
      field: K,
      value: ForgotPasswordFormData[K]
    ) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
      
      // Effacer l'erreur du champ
      setFormErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });

      // Calculer la force du mot de passe
      if (field === 'newPassword' && typeof value === 'string') {
        setPasswordStrength(calculatePasswordStrength(value));
      }

      // Valider la confirmation en temps réel
      if (field === 'confirmPassword' || field === 'newPassword') {
        const password = field === 'newPassword' ? value : formData.newPassword;
        const confirm = field === 'confirmPassword' ? value : formData.confirmPassword;
        if (password && confirm) {
          const result = validateConfirmPassword(
            password as string,
            confirm as string
          );
          if (typeof result === 'string') {
            setFormErrors((prev) => ({ ...prev, confirmPassword: result }));
          } else {
            setFormErrors((prev) => {
              const newErrors = { ...prev };
              delete newErrors.confirmPassword;
              return newErrors;
            });
          }
        }
      }
    }, [formData, validateConfirmPassword, calculatePasswordStrength]);

    // ========================================================================
    // RENVOI DU CODE
    // ========================================================================

    const handleResend = useCallback(async () => {
      if (isResending || resendCooldown > 0 || isLocked) return;

      setIsResending(true);
      try {
        // Simuler l'envoi du code
        await new Promise((resolve) => setTimeout(resolve, 1000));

        setResendCooldown(resendCooldown);
        
        toast({
          title: 'Code renvoyé',
          description: 'Un nouveau code de vérification vous a été envoyé',
          duration: 4000,
        });

        // Démarrer le compte à rebours
        if (timerRef.current) {
          clearInterval(timerRef.current);
        }

        timerRef.current = setInterval(() => {
          setResendCooldown((prev) => {
            if (prev <= 1) {
              if (timerRef.current) clearInterval(timerRef.current);
              return 0;
            }
            return prev - 1;
          });
        }, 1000);

      } catch (err) {
        toast({
          title: 'Erreur',
          description: 'Impossible de renvoyer le code. Veuillez réessayer.',
          variant: 'destructive',
        });
      } finally {
        setIsResending(false);
      }
    }, [isResending, resendCooldown, isLocked, toast]);

    // ========================================================================
    // VALIDATION DU FORMULAIRE
    // ========================================================================

    const validateStep = useCallback((): boolean => {
      const errors: Record<string, string> = {};
      let isValid = true;

      if (step === 'email') {
        const emailResult = validateEmail(formData.email);
        if (typeof emailResult === 'string') {
          errors.email = emailResult;
          isValid = false;
        }
      }

      if (step === 'verification') {
        const codeResult = validateCode(formData.verificationCode || '');
        if (typeof codeResult === 'string') {
          errors.verificationCode = codeResult;
          isValid = false;
        }
      }

      if (step === 'confirmation') {
        const passwordResult = validatePassword(formData.newPassword || '');
        if (typeof passwordResult === 'string') {
          errors.newPassword = passwordResult;
          isValid = false;
        }

        const confirmResult = validateConfirmPassword(
          formData.newPassword || '',
          formData.confirmPassword || ''
        );
        if (typeof confirmResult === 'string') {
          errors.confirmPassword = confirmResult;
          isValid = false;
        }
      }

      setFormErrors(errors);
      return isValid;
    }, [
      step,
      formData,
      validateEmail,
      validateCode,
      validatePassword,
      validateConfirmPassword,
    ]);

    // ========================================================================
    // NAVIGATION ENTRE LES ÉTAPES
    // ========================================================================

    const goToStep = useCallback((newStep: ForgotPasswordStep) => {
      setStep(newStep);
      if (onStepChange) onStepChange(newStep);

      // Focus sur le premier champ
      setTimeout(() => {
        switch (newStep) {
          case 'email':
            emailInputRef.current?.focus();
            break;
          case 'verification':
            codeInputRef.current?.focus();
            break;
          case 'confirmation':
            passwordInputRef.current?.focus();
            break;
          default:
            break;
        }
      }, 100);
    }, [onStepChange]);

    const handleBack = useCallback(() => {
      if (step === 'email') {
        if (onBack) onBack();
        return;
      }

      // Revenir à l'étape précédente
      const stepOrder: ForgotPasswordStep[] = ['email', 'verification', 'confirmation', 'success'];
      const currentIndex = stepOrder.indexOf(step);
      if (currentIndex > 0) {
        goToStep(stepOrder[currentIndex - 1]);
      }
    }, [step, goToStep, onBack]);

    // ========================================================================
    // SOUMISSION
    // ========================================================================

    const handleSubmit = useCallback(async (e: React.FormEvent) => {
      e.preventDefault();

      if (isSubmitting || isLoading || disabled || isLocked) return;

      // Validation
      if (!validateStep()) {
        toast({
          title: 'Erreur de validation',
          description: 'Veuillez corriger les erreurs du formulaire',
          variant: 'destructive',
        });
        return;
      }

      // Vérifier les tentatives
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
        if (onSubmit) {
          await onSubmit(formData);
        }

        // Si c'est la dernière étape, aller à la confirmation
        if (step === 'confirmation') {
          goToStep('success');
        } else if (step === 'email' && requireVerification) {
          goToStep('verification');
          setEmailSent(true);
          // Démarrer le compte à rebours pour le renvoi
          setResendCooldown(resendCooldown);
          if (timerRef.current) {
            clearInterval(timerRef.current);
          }
          timerRef.current = setInterval(() => {
            setResendCooldown((prev) => {
              if (prev <= 1) {
                if (timerRef.current) clearInterval(timerRef.current);
                return 0;
              }
              return prev - 1;
            });
          }, 1000);
        } else if (step === 'verification' && requireNewPassword) {
          goToStep('confirmation');
        } else {
          goToStep('success');
        }

        toast({
          title: 'Succès',
          description: step === 'confirmation' 
            ? 'Votre mot de passe a été réinitialisé avec succès' 
            : step === 'email' 
            ? 'Un email de réinitialisation vous a été envoyé' 
            : 'Code vérifié avec succès',
          variant: 'success',
        });

        if (debug) {
          console.log('Formulaire soumis:', formData);
        }

      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Une erreur est survenue';
        toast({
          title: 'Erreur',
          description: errorMessage,
          variant: 'destructive',
        });
        if (debug) console.error('Erreur de soumission:', err);
      } finally {
        setIsSubmitting(false);
      }
    }, [
      isSubmitting,
      isLoading,
      disabled,
      isLocked,
      validateStep,
      attempts,
      maxAttempts,
      formData,
      step,
      requireVerification,
      requireNewPassword,
      resendCooldown,
      onSubmit,
      goToStep,
      toast,
      debug,
    ]);

    // ========================================================================
    // CLEANUP
    // ========================================================================

    useEffect(() => {
      return () => {
        if (timerRef.current) {
          clearInterval(timerRef.current);
        }
      };
    }, []);

    // ========================================================================
    // RENDU
    // ========================================================================

    // --- Rendu de l'étape Email ---
    const renderEmailStep = () => (
      <div className="space-y-4">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-brand-100 dark:bg-brand-900/30">
            <EnvelopeIcon className="h-8 w-8 text-brand-600 dark:text-brand-400" />
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Entrez votre adresse email pour recevoir un lien de réinitialisation
          </p>
        </div>

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
            disabled={disabled || isSubmitting || isLoading || isLocked}
            autoFocus
            className="h-11"
            prefix={<AtSymbolIcon className="h-4 w-4 text-gray-400" />}
          />
        </div>

        {attempts > 0 && attempts < maxAttempts && (
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Tentatives restantes: {maxAttempts - attempts}
          </p>
        )}
      </div>
    );

    // --- Rendu de l'étape Vérification ---
    const renderVerificationStep = () => (
      <div className="space-y-4">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-blue-100 dark:bg-blue-900/30">
            <ShieldCheckIcon className="h-8 w-8 text-blue-600 dark:text-blue-400" />
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Un code de vérification a été envoyé à <strong>{formData.email}</strong>
          </p>
        </div>

        <div className="space-y-2">
          <label htmlFor="verificationCode" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Code de vérification <span className="text-red-500">*</span>
          </label>
          <Input
            ref={codeInputRef}
            id="verificationCode"
            type="text"
            placeholder="000000"
            value={formData.verificationCode || ''}
            onChange={(e) => handleFieldChange('verificationCode', e.target.value)}
            error={formErrors.verificationCode}
            disabled={disabled || isSubmitting || isLoading || isLocked}
            autoFocus
            className="h-11 text-center text-lg font-mono tracking-widest"
            maxLength={6}
            prefix={<KeyIcon className="h-4 w-4 text-gray-400" />}
          />
        </div>

        <div className="flex items-center justify-between text-sm">
          <button
            type="button"
            onClick={handleResend}
            disabled={isResending || resendCooldown > 0 || isLocked}
            className={cn(
              'text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300 transition-colors',
              (isResending || resendCooldown > 0 || isLocked) && 'opacity-50 cursor-not-allowed'
            )}
          >
            {isResending ? (
              <>
                <ArrowPathIcon className="inline h-3 w-3 animate-spin mr-1" />
                Envoi en cours...
              </>
            ) : resendCooldown > 0 ? (
              `Renvoyer dans ${resendCooldown}s`
            ) : (
              'Renvoyer le code'
            )}
          </button>
        </div>
      </div>
    );

    // --- Rendu de l'étape Confirmation (nouveau mot de passe) ---
    const renderConfirmationStep = () => (
      <div className="space-y-4">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
            <LockClosedIcon className="h-8 w-8 text-green-600 dark:text-green-400" />
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Choisissez un nouveau mot de passe sécurisé
          </p>
        </div>

        <div className="space-y-2">
          <label htmlFor="newPassword" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Nouveau mot de passe <span className="text-red-500">*</span>
          </label>
          <Input
            ref={passwordInputRef}
            id="newPassword"
            type={showPassword ? 'text' : 'password'}
            placeholder="Nouveau mot de passe"
            value={formData.newPassword || ''}
            onChange={(e) => handleFieldChange('newPassword', e.target.value)}
            error={formErrors.newPassword}
            disabled={disabled || isSubmitting || isLoading || isLocked}
            autoFocus
            className="h-11"
            suffix={
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                {showPassword ? (
                  <EyeSlashIcon className="h-4 w-4" />
                ) : (
                  <EyeIcon className="h-4 w-4" />
                )}
              </button>
            }
          />
          {formData.newPassword && (
            <div className="space-y-1">
              <Progress
                value={passwordStrength}
                className="h-1"
                variant={
                  passwordStrength >= 80 ? 'success' :
                  passwordStrength >= 60 ? 'warning' :
                  'error'
                }
              />
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Force: {passwordStrength >= 80 ? 'Fort' : passwordStrength >= 60 ? 'Moyen' : 'Faible'}
              </p>
            </div>
          )}
        </div>

        <div className="space-y-2">
          <label htmlFor="confirmPassword" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Confirmer le mot de passe <span className="text-red-500">*</span>
          </label>
          <Input
            ref={confirmPasswordInputRef}
            id="confirmPassword"
            type={showConfirmPassword ? 'text' : 'password'}
            placeholder="Confirmer le mot de passe"
            value={formData.confirmPassword || ''}
            onChange={(e) => handleFieldChange('confirmPassword', e.target.value)}
            error={formErrors.confirmPassword}
            disabled={disabled || isSubmitting || isLoading || isLocked}
            className="h-11"
            suffix={
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                {showConfirmPassword ? (
                  <EyeSlashIcon className="h-4 w-4" />
                ) : (
                  <EyeIcon className="h-4 w-4" />
                )}
              </button>
            }
          />
        </div>

        <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-3 text-xs text-gray-500 dark:text-gray-400">
          <p className="font-medium">Exigences du mot de passe:</p>
          <ul className="mt-1 list-disc pl-4 space-y-0.5">
            <li className={formData.newPassword && formData.newPassword.length >= 8 ? 'text-green-600 dark:text-green-400' : ''}>
              Au moins 8 caractères
            </li>
            <li className={formData.newPassword && /[A-Z]/.test(formData.newPassword) ? 'text-green-600 dark:text-green-400' : ''}>
              Au moins une majuscule
            </li>
            <li className={formData.newPassword && /[a-z]/.test(formData.newPassword) ? 'text-green-600 dark:text-green-400' : ''}>
              Au moins une minuscule
            </li>
            <li className={formData.newPassword && /[0-9]/.test(formData.newPassword) ? 'text-green-600 dark:text-green-400' : ''}>
              Au moins un chiffre
            </li>
            <li className={formData.newPassword && /[!@#$%^&*(),.?":{}|<>]/.test(formData.newPassword) ? 'text-green-600 dark:text-green-400' : ''}>
              Au moins un caractère spécial
            </li>
          </ul>
        </div>
      </div>
    );

    // --- Rendu de l'étape Succès ---
    const renderSuccessStep = () => (
      <div className="space-y-4 text-center">
        <div className="flex flex-col items-center">
          <div className="flex h-20 w-20 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
            <CheckCircleIcon className="h-10 w-10 text-green-600 dark:text-green-400" />
          </div>
          <h3 className="mt-4 text-xl font-semibold text-gray-900 dark:text-white">
            Mot de passe réinitialisé !
          </h3>
          <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
            Votre mot de passe a été réinitialisé avec succès.
            Vous pouvez maintenant vous connecter avec votre nouveau mot de passe.
          </p>
        </div>

        {redirectUrl && (
          <Button
            variant="primary"
            className="w-full"
            onClick={() => {
              window.location.href = redirectUrl;
            }}
          >
            Se connecter
          </Button>
        )}
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
          <div className="flex items-center gap-2">
            {step !== 'email' && step !== 'success' && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleBack}
                disabled={isSubmitting || isLoading}
                className="h-8 w-8 p-0"
                aria-label="Retour"
              >
                <ArrowLeftIcon className="h-4 w-4" />
              </Button>
            )}
            <CardTitle className="flex-1 text-center">{title}</CardTitle>
          </div>
          {subtitle && step === 'email' && (
            <p className="text-sm text-gray-500 dark:text-gray-400 text-center">
              {subtitle}
            </p>
          )}
          {step !== 'email' && step !== 'success' && (
            <div className="flex justify-center mt-2">
              <div className="flex items-center gap-2">
                <Badge
                  variant={step === 'email' ? 'primary' : 'outline'}
                  size="sm"
                >
                  1. Email
                </Badge>
                {requireVerification && (
                  <>
                    <div className="h-px w-4 bg-gray-300 dark:bg-gray-600" />
                    <Badge
                      variant={step === 'verification' ? 'primary' : 'outline'}
                      size="sm"
                    >
                      2. Vérification
                    </Badge>
                  </>
                )}
                {requireNewPassword && (
                  <>
                    <div className="h-px w-4 bg-gray-300 dark:bg-gray-600" />
                    <Badge
                      variant={step === 'confirmation' ? 'primary' : 'outline'}
                      size="sm"
                    >
                      3. Nouveau mot de passe
                    </Badge>
                  </>
                )}
              </div>
            </div>
          )}
        </CardHeader>

        {/* Contenu */}
        <CardContent className="p-6">
          <form ref={formRef} onSubmit={handleSubmit} noValidate>
            {/* Erreur globale */}
            {error && (
              <div className="mb-4 flex items-start gap-2 rounded-lg bg-red-50 dark:bg-red-900/20 p-3 text-sm text-red-600 dark:text-red-400">
                <ExclamationTriangleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />
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
                {step === 'email' && renderEmailStep()}
                {step === 'verification' && renderVerificationStep()}
                {step === 'confirmation' && renderConfirmationStep()}
                {step === 'success' && renderSuccessStep()}
              </motion.div>
            </AnimatePresence>

            {/* Compte verrouillé */}
            {isLockedScreen && (
              <div className="mt-4 flex items-center gap-2 rounded-lg bg-red-50 dark:bg-red-900/20 p-3 text-sm text-red-600 dark:text-red-400">
                <ClockIcon className="h-5 w-5 flex-shrink-0" />
                <span>
                  Compte temporairement verrouillé. Veuillez réessayer dans quelques minutes.
                </span>
              </div>
            )}
          </form>
        </CardContent>

        {/* Footer */}
        {step !== 'success' && (
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
                isLockedScreen
              }
              isLoading={isSubmitting || isLoading}
            >
              {step === 'email' && 'Envoyer le lien de réinitialisation'}
              {step === 'verification' && 'Vérifier le code'}
              {step === 'confirmation' && 'Réinitialiser le mot de passe'}
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

            {step === 'email' && onBack && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="w-full text-gray-500"
                onClick={onBack}
              >
                <ArrowLeftIcon className="mr-2 h-4 w-4" />
                Retour à la connexion
              </Button>
            )}
          </CardFooter>
        )}

        {/* Footer succès */}
        {step === 'success' && onCancel && (
          <CardFooter className="border-t border-gray-200 dark:border-gray-700 p-6">
            <Button
              type="button"
              variant="ghost"
              className="w-full"
              onClick={onCancel}
            >
              Fermer
            </Button>
          </CardFooter>
        )}
      </Card>
    );
  }
);

ForgotPasswordForm.displayName = 'ForgotPasswordForm';

export default ForgotPasswordForm;

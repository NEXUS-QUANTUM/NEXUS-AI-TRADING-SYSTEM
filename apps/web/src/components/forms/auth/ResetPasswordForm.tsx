// apps/web/src/components/forms/auth/ResetPasswordForm.tsx
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
  LockClosedIcon,
  EyeIcon,
  EyeSlashIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ArrowPathIcon,
  ShieldCheckIcon,
  KeyIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  CheckIcon,
  XMarkIcon,
  ClockIcon,
  ExclamationCircleIcon,
  DocumentTextIcon,
  ClipboardDocumentIcon,
} from '@heroicons/react/24/outline';
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

export type ResetPasswordStep = 'token' | 'password' | 'success';

export interface ResetPasswordFormData {
  /** Token de réinitialisation */
  token: string;
  /** Nouveau mot de passe */
  newPassword: string;
  /** Confirmation du nouveau mot de passe */
  confirmPassword: string;
  /** Email (optionnel, pour validation) */
  email?: string;
}

export interface ResetPasswordFormProps {
  // --- Contrôle ---
  /** Token initial (depuis l'URL) */
  initialToken?: string;
  /** Email initial (depuis l'URL) */
  initialEmail?: string;
  /** Étape initiale */
  initialStep?: ResetPasswordStep;
  /** Données initiales */
  initialData?: Partial<ResetPasswordFormData>;
  /** Callback de soumission */
  onSubmit?: (data: ResetPasswordFormData) => void | Promise<void>;
  /** Callback de succès */
  onSuccess?: (data: ResetPasswordFormData) => void;
  /** Callback d'erreur */
  onError?: (error: string) => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de changement d'étape */
  onStepChange?: (step: ResetPasswordStep) => void;
  /** Callback pour renvoyer le token */
  onResendToken?: (email: string) => void | Promise<void>;

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

  // --- Configuration ---
  /** Exiger la validation de l'email */
  requireEmailValidation?: boolean;
  /** Délai d'expiration du token (secondes) */
  tokenExpiry?: number;
  /** Nombre maximum de tentatives */
  maxAttempts?: number;
  /** URL de redirection après succès */
  redirectUrl?: string;
  /** Afficher le compteur de temps restant */
  showTimer?: boolean;

  // --- États ---
  /** État de chargement */
  isLoading?: boolean;
  /** État d'erreur */
  error?: string | null;
  /** Message de succès */
  success?: string | null;
  /** Désactiver le formulaire */
  disabled?: boolean;
  /** Token valide */
  isValidToken?: boolean;
  /** Validation du token en cours */
  isValidatingToken?: boolean;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ID */
  id?: string;

  // --- Avancé ---
  /** Callback de validation du token */
  validateToken?: (token: string) => boolean | string;
  /** Callback de validation du mot de passe */
  validatePassword?: (password: string) => boolean | string;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const ResetPasswordForm = forwardRef<HTMLDivElement, ResetPasswordFormProps>(
  (props, ref) => {
    const {
      // Contrôle
      initialToken = '',
      initialEmail = '',
      initialStep = 'token',
      initialData = {},
      onSubmit,
      onSuccess,
      onError,
      onCancel,
      onStepChange,
      onResendToken,

      // Apparence
      title = 'Réinitialiser le mot de passe',
      subtitle = 'Entrez le nouveau mot de passe pour votre compte',
      className,
      variant = 'default',
      size = 'md',

      // Configuration
      requireEmailValidation = true,
      tokenExpiry = 3600, // 1 heure
      maxAttempts = 5,
      redirectUrl = '/login',
      showTimer = true,

      // États
      isLoading = false,
      error = null,
      success = null,
      disabled = false,
      isValidToken = false,
      isValidatingToken = false,

      // Accessibilité
      ariaLabel = 'Formulaire de réinitialisation de mot de passe',
      id,

      // Avancé
      validateToken: externalValidateToken,
      validatePassword: externalValidatePassword,
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const formRef = useRef<HTMLFormElement>(null);
    const tokenInputRef = useRef<HTMLInputElement>(null);
    const passwordInputRef = useRef<HTMLInputElement>(null);
    const confirmPasswordInputRef = useRef<HTMLInputElement>(null);
    const timerRef = useRef<NodeJS.Timeout | null>(null);

    // ========================================================================
    // HOOKS
    // ========================================================================

    const { toast } = useToast();
    const { resetPassword, verifyResetToken } = useAuth();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [step, setStep] = useState<ResetPasswordStep>(initialStep);
    const [formData, setFormData] = useState<ResetPasswordFormData>({
      token: initialToken,
      email: initialEmail,
      newPassword: '',
      confirmPassword: '',
      ...initialData,
    });
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [passwordStrength, setPasswordStrength] = useState(0);
    const [attempts, setAttempts] = useState(0);
    const [isLocked, setIsLocked] = useState(false);
    const [timeRemaining, setTimeRemaining] = useState(tokenExpiry);
    const [isTokenValid, setIsTokenValid] = useState(isValidToken);
    const [isValidating, setIsValidating] = useState(isValidatingToken);
    const [tokenError, setTokenError] = useState<string | null>(null);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validateToken = useCallback((token: string): boolean | string => {
      if (externalValidateToken) {
        return externalValidateToken(token);
      }
      if (!token) return 'Le token de réinitialisation est requis';
      if (token.length < 20) return 'Token invalide';
      return true;
    }, [externalValidateToken]);

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

    const handleFieldChange = useCallback(<K extends keyof ResetPasswordFormData>(
      field: K,
      value: ResetPasswordFormData[K]
    ) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
      setFormErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });

      if (field === 'newPassword') {
        setPasswordStrength(calculatePasswordStrength(value as string));
        if (formData.confirmPassword) {
          const result = validateConfirmPassword(value as string, formData.confirmPassword);
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

      if (field === 'confirmPassword') {
        const result = validateConfirmPassword(formData.newPassword, value as string);
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
    }, [formData]);

    // ========================================================================
    // VALIDATION DU TOKEN
    // ========================================================================

    const verifyToken = useCallback(async () => {
      if (!formData.token) {
        setTokenError('Token requis');
        return;
      }

      const tokenResult = validateToken(formData.token);
      if (typeof tokenResult === 'string') {
        setTokenError(tokenResult);
        return;
      }

      setIsValidating(true);
      setTokenError(null);

      try {
        const result = await verifyResetToken(formData.token);
        if (result.valid) {
          setIsTokenValid(true);
          setStep('password');
          if (onStepChange) onStepChange('password');
          toast({
            title: 'Token valide',
            description: 'Vous pouvez maintenant réinitialiser votre mot de passe',
            duration: 3000,
          });
        } else {
          setTokenError(result.message || 'Token invalide ou expiré');
          setIsTokenValid(false);
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Erreur de vérification du token';
        setTokenError(errorMessage);
        if (onError) onError(errorMessage);
      } finally {
        setIsValidating(false);
      }
    }, [formData.token, validateToken, verifyResetToken, onStepChange, onError, toast]);

    // ========================================================================
    // VALIDATION DU FORMULAIRE
    // ========================================================================

    const validateStep = useCallback((): boolean => {
      const errors: Record<string, string> = {};
      let isValid = true;

      if (step === 'token') {
        const tokenResult = validateToken(formData.token);
        if (typeof tokenResult === 'string') {
          errors.token = tokenResult;
          isValid = false;
        }
        if (requireEmailValidation && !formData.email) {
          errors.email = 'L\'email est requis pour la vérification';
          isValid = false;
        }
      }

      if (step === 'password') {
        const passwordResult = validatePassword(formData.newPassword);
        if (typeof passwordResult === 'string') {
          errors.newPassword = passwordResult;
          isValid = false;
        }
        const confirmResult = validateConfirmPassword(formData.newPassword, formData.confirmPassword);
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
      validateToken,
      validatePassword,
      validateConfirmPassword,
      requireEmailValidation,
    ]);

    // ========================================================================
    // SOUMISSION
    // ========================================================================

    const handleSubmit = useCallback(async (e: React.FormEvent) => {
      e.preventDefault();

      if (isSubmitting || isLoading || disabled || isLocked) return;

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
        if (step === 'token') {
          // Vérifier le token
          await verifyToken();
          return;
        }

        // Réinitialisation du mot de passe
        const resetData = {
          token: formData.token,
          newPassword: formData.newPassword,
          email: formData.email,
        };

        if (onSubmit) {
          await onSubmit(resetData);
        }

        await resetPassword(resetData);

        setStep('success');
        if (onStepChange) onStepChange('success');
        if (onSuccess) onSuccess(resetData);

        toast({
          title: 'Mot de passe réinitialisé',
          description: 'Votre mot de passe a été modifié avec succès',
          variant: 'success',
        });

        if (debug) {
          console.log('Mot de passe réinitialisé avec succès');
        }

        // Redirection
        if (redirectUrl) {
          setTimeout(() => {
            window.location.href = redirectUrl;
          }, 2000);
        }

      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Erreur de réinitialisation';
        if (onError) onError(errorMessage);
        toast({
          title: 'Erreur',
          description: errorMessage,
          variant: 'destructive',
        });
        if (debug) console.error('Erreur de réinitialisation:', err);
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
      step,
      formData,
      verifyToken,
      resetPassword,
      onSubmit,
      onSuccess,
      onError,
      onStepChange,
      redirectUrl,
      toast,
      debug,
    ]);

    // ========================================================================
    // RENVOI DU TOKEN
    // ========================================================================

    const handleResendToken = useCallback(async () => {
      if (isSubmitting || isLoading || isLocked) return;

      if (!formData.email) {
        toast({
          title: 'Email requis',
          description: 'Veuillez entrer votre email pour renvoyer le token',
          variant: 'destructive',
        });
        return;
      }

      setIsSubmitting(true);
      try {
        if (onResendToken) {
          await onResendToken(formData.email);
        }
        toast({
          title: 'Token renvoyé',
          description: 'Un nouveau lien de réinitialisation vous a été envoyé par email',
          duration: 4000,
        });
        // Réinitialiser le timer
        setTimeRemaining(tokenExpiry);
        if (timerRef.current) {
          clearInterval(timerRef.current);
        }
        timerRef.current = setInterval(() => {
          setTimeRemaining((prev) => {
            if (prev <= 1) {
              if (timerRef.current) clearInterval(timerRef.current);
              return 0;
            }
            return prev - 1;
          });
        }, 1000);
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Erreur lors du renvoi';
        toast({
          title: 'Erreur',
          description: errorMessage,
          variant: 'destructive',
        });
      } finally {
        setIsSubmitting(false);
      }
    }, [isSubmitting, isLoading, isLocked, formData.email, onResendToken, tokenExpiry, toast]);

    // ========================================================================
    // TIMER
    // ========================================================================

    useEffect(() => {
      if (step === 'token' && showTimer) {
        timerRef.current = setInterval(() => {
          setTimeRemaining((prev) => {
            if (prev <= 1) {
              if (timerRef.current) clearInterval(timerRef.current);
              return 0;
            }
            return prev - 1;
          });
        }, 1000);
      }

      return () => {
        if (timerRef.current) {
          clearInterval(timerRef.current);
        }
      };
    }, [step, showTimer]);

    // ========================================================================
    // RENDU
    // ========================================================================

    // --- Rendu de l'étape Token ---
    const renderTokenStep = () => (
      <div className="space-y-4">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-brand-100 dark:bg-brand-900/30">
            <KeyIcon className="h-8 w-8 text-brand-600 dark:text-brand-400" />
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Entrez le token de réinitialisation reçu par email
          </p>
          {showTimer && timeRemaining > 0 && (
            <div className="mt-2 flex items-center justify-center gap-2 text-xs text-gray-500 dark:text-gray-400">
              <ClockIcon className="h-4 w-4" />
              <span>Temps restant: {Math.floor(timeRemaining / 60)}m {timeRemaining % 60}s</span>
            </div>
          )}
        </div>

        <div className="space-y-2">
          <label htmlFor="token" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Token de réinitialisation <span className="text-red-500">*</span>
          </label>
          <Input
            ref={tokenInputRef}
            id="token"
            type="text"
            placeholder="ex: eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            value={formData.token}
            onChange={(e) => handleFieldChange('token', e.target.value)}
            error={tokenError || formErrors.token}
            disabled={disabled || isSubmitting || isLoading || isLocked || isValidating}
            autoFocus
            className="h-11 font-mono text-sm"
            prefix={<KeyIcon className="h-4 w-4 text-gray-400" />}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handleSubmit(e);
              }
            }}
          />
          {tokenError && (
            <p className="text-sm text-red-600 dark:text-red-400">{tokenError}</p>
          )}
        </div>

        {requireEmailValidation && (
          <div className="space-y-2">
            <label htmlFor="email" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Email <span className="text-red-500">*</span>
            </label>
            <Input
              id="email"
              type="email"
              placeholder="exemple@email.com"
              value={formData.email || ''}
              onChange={(e) => handleFieldChange('email', e.target.value)}
              error={formErrors.email}
              disabled={disabled || isSubmitting || isLoading || isLocked}
              className="h-11"
            />
          </div>
        )}

        <div className="flex items-center justify-between text-sm">
          <button
            type="button"
            onClick={handleResendToken}
            disabled={isSubmitting || isLoading || isLocked || !formData.email}
            className={cn(
              'text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300 transition-colors',
              (isSubmitting || isLoading || isLocked || !formData.email) && 'opacity-50 cursor-not-allowed'
            )}
          >
            {isSubmitting ? (
              <>
                <ArrowPathIcon className="inline h-3 w-3 animate-spin mr-1" />
                Envoi en cours...
              </>
            ) : (
              'Renvoyer le token'
            )}
          </button>
          {onCancel && (
            <button
              type="button"
              onClick={onCancel}
              className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 transition-colors"
            >
              Retour à la connexion
            </button>
          )}
        </div>

        {attempts > 0 && attempts < maxAttempts && !isLocked && (
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Tentatives restantes: {maxAttempts - attempts}
          </p>
        )}
      </div>
    );

    // --- Rendu de l'étape Password ---
    const renderPasswordStep = () => (
      <div className="space-y-4">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
            <ShieldCheckIcon className="h-8 w-8 text-green-600 dark:text-green-400" />
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
            value={formData.newPassword}
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
            value={formData.confirmPassword}
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

        <button
          type="button"
          onClick={() => setStep('token')}
          className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 transition-colors"
        >
          <ArrowLeftIcon className="inline h-3 w-3 mr-1" />
          Retour
        </button>
      </div>
    );

    // --- Rendu de l'étape Success ---
    const renderSuccessStep = () => (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
          <CheckCircleIcon className="h-10 w-10 text-green-600 dark:text-green-400" />
        </div>
        <h3 className="mt-4 text-xl font-semibold text-gray-900 dark:text-white">
          Mot de passe réinitialisé !
        </h3>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
          Votre mot de passe a été modifié avec succès.
          Vous pouvez maintenant vous connecter avec votre nouveau mot de passe.
        </p>
        <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
          Redirection vers la page de connexion...
        </p>
        <Progress value={100} className="mt-4 w-32 h-1" />
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
    const showStepIndicator = step !== 'success';

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
            {onCancel && step !== 'success' && (
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
          {subtitle && step === 'token' && (
            <p className="text-sm text-gray-500 dark:text-gray-400">{subtitle}</p>
          )}
          {showStepIndicator && (
            <div className="flex items-center justify-center gap-2 mt-3">
              <Badge variant={step === 'token' ? 'primary' : 'outline'} size="sm">
                1. Token
              </Badge>
              <div className="h-px w-4 bg-gray-300 dark:bg-gray-600" />
              <Badge variant={step === 'password' ? 'primary' : 'outline'} size="sm">
                2. Nouveau mot de passe
              </Badge>
            </div>
          )}
        </CardHeader>

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
                {step === 'token' && renderTokenStep()}
                {step === 'password' && renderPasswordStep()}
                {step === 'success' && renderSuccessStep()}
              </motion.div>
            </AnimatePresence>

            {/* Compte verrouillé */}
            {isLockedScreen && renderLockedState()}
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
                isLockedScreen ||
                (step === 'token' && isValidating)
              }
              isLoading={isSubmitting || isLoading || isValidating}
            >
              {step === 'token' && (isValidating ? 'Vérification...' : 'Vérifier le token')}
              {step === 'password' && 'Réinitialiser le mot de passe'}
            </Button>

            {step === 'password' && onCancel && (
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
                window.location.href = redirectUrl;
              }}
            >
              Se connecter
            </Button>
          </CardFooter>
        )}
      </Card>
    );
  }
);

ResetPasswordForm.displayName = 'ResetPasswordForm';

export default ResetPasswordForm;

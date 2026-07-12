// apps/web/src/components/forms/auth/LoginForm.tsx
'use client';

import React, {
  useState,
  useCallback,
  useRef,
  useEffect,
  forwardRef,
  Ref,
  useMemo,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  EnvelopeIcon,
  LockClosedIcon,
  EyeIcon,
  EyeSlashIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ArrowPathIcon,
  ShieldCheckIcon,
  KeyIcon,
  UserIcon,
  DevicePhoneMobileIcon,
  AtSymbolIcon,
  FingerPrintIcon,
  QrCodeIcon,
  Cog6ToothIcon,
  GlobeAltIcon,
  ComputerDesktopIcon,
  SunIcon,
  MoonIcon,
  WifiIcon,
  SignalIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline';
import {
  CheckCircleIcon as CheckCircleSolid,
  ExclamationCircleIcon as ExclamationCircleSolid,
} from '@heroicons/react/24/solid';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Checkbox } from '@/components/common/Checkbox';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Separator } from '@/components/common/Separator';
import { Progress } from '@/components/common/Progress';
import { Tooltip } from '@/components/common/Tooltip';
import { useToast } from '@/hooks/useToast';
import { useAuth } from '@/hooks/useAuth';
import { useTheme } from 'next-themes';

// ============================================================================
// TYPES
// ============================================================================

export type LoginStep = 'credentials' | '2fa' | 'loading' | 'success' | 'error';

export interface LoginFormData {
  /** Email de l'utilisateur */
  email: string;
  /** Mot de passe */
  password: string;
  /** Se souvenir de moi */
  rememberMe?: boolean;
  /** Code 2FA */
  twoFactorCode?: string;
  /** Code de récupération */
  recoveryCode?: string;
}

export interface LoginFormProps {
  // --- Contrôle ---
  /** Étape initiale */
  initialStep?: LoginStep;
  /** Données initiales */
  initialData?: Partial<LoginFormData>;
  /** Callback de soumission */
  onSubmit?: (data: LoginFormData) => void | Promise<void>;
  /** Callback de succès */
  onSuccess?: (data: LoginFormData) => void;
  /** Callback d'erreur */
  onError?: (error: string) => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de changement d'étape */
  onStepChange?: (step: LoginStep) => void;

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
  /** Afficher le logo */
  showLogo?: boolean;
  /** Afficher les options sociales */
  showSocialLogin?: boolean;
  /** Afficher l'option "Mot de passe oublié" */
  showForgotPassword?: boolean;
  /** Afficher l'option "S'enregistrer" */
  showRegister?: boolean;
  /** Afficher le thème toggle */
  showThemeToggle?: boolean;

  // --- Social Login ---
  /** Fournisseurs sociaux disponibles */
  socialProviders?: ('google' | 'github' | 'apple' | 'facebook' | 'twitter')[];
  /** Callback pour les providers sociaux */
  onSocialLogin?: (provider: string) => void;

  // --- États ---
  /** État de chargement */
  isLoading?: boolean;
  /** État d'erreur */
  error?: string | null;
  /** Désactiver le formulaire */
  disabled?: boolean;

  // --- Configuration ---
  /** Exiger la 2FA */
  requireTwoFactor?: boolean;
  /** Méthodes 2FA disponibles */
  twoFactorMethods?: ('authenticator' | 'sms' | 'email' | 'recovery')[];
  /** Délai de verrouillage (secondes) */
  lockDuration?: number;
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
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const SOCIAL_ICONS = {
  google: (
    <svg className="h-5 w-5" viewBox="0 0 24 24">
      <path
        fill="#4285F4"
        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"
      />
      <path
        fill="#34A853"
        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
      />
      <path
        fill="#FBBC05"
        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
      />
      <path
        fill="#EA4335"
        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
      />
    </svg>
  ),
  github: (
    <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
      <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.468-2.38 1.235-3.22-.123-.3-.535-1.52.117-3.16 0 0 1.008-.322 3.3 1.23.96-.267 1.98-.399 3-.399s2.04.132 3 .399c2.292-1.552 3.3-1.23 3.3-1.23.653 1.64.24 2.86.118 3.16.768.84 1.233 1.91 1.233 3.22 0 4.61-2.804 5.62-5.476 5.92.43.37.824 1.102.824 2.22 0 1.602-.015 2.894-.015 3.287 0 .322.216.694.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
    </svg>
  ),
  apple: (
    <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
      <path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z" />
    </svg>
  ),
  facebook: (
    <svg className="h-5 w-5" fill="#1877F2" viewBox="0 0 24 24">
      <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
    </svg>
  ),
  twitter: (
    <svg className="h-5 w-5" fill="#1DA1F2" viewBox="0 0 24 24">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  ),
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const LoginForm = forwardRef<HTMLDivElement, LoginFormProps>(
  (props, ref) => {
    const {
      // Contrôle
      initialStep = 'credentials',
      initialData = {},
      onSubmit,
      onSuccess,
      onError,
      onCancel,
      onStepChange,

      // Apparence
      title = 'Connexion',
      subtitle = 'Accédez à votre compte Nexus Trading IA',
      className,
      variant = 'default',
      size = 'md',
      showLogo = true,
      showSocialLogin = true,
      showForgotPassword = true,
      showRegister = true,
      showThemeToggle = true,

      // Social Login
      socialProviders = ['google', 'github', 'apple'],
      onSocialLogin,

      // États
      isLoading = false,
      error = null,
      disabled = false,

      // Configuration
      requireTwoFactor = false,
      twoFactorMethods = ['authenticator', 'sms', 'email', 'recovery'],
      lockDuration = 300,
      maxAttempts = 5,
      redirectUrl = '/dashboard',

      // Accessibilité
      ariaLabel = 'Formulaire de connexion',
      id,

      // Avancé
      validateEmail: externalValidateEmail,
      validatePassword: externalValidatePassword,
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const formRef = useRef<HTMLFormElement>(null);
    const emailInputRef = useRef<HTMLInputElement>(null);
    const passwordInputRef = useRef<HTMLInputElement>(null);
    const twoFactorInputRef = useRef<HTMLInputElement>(null);
    const timerRef = useRef<NodeJS.Timeout | null>(null);

    // ========================================================================
    // HOOKS
    // ========================================================================

    const { toast } = useToast();
    const { signIn, signInWith2FA, user } = useAuth();
    const { resolvedTheme, setTheme } = useTheme();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [step, setStep] = useState<LoginStep>(initialStep);
    const [formData, setFormData] = useState<LoginFormData>({
      email: '',
      password: '',
      rememberMe: false,
      twoFactorCode: '',
      recoveryCode: '',
      ...initialData,
    });
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [showPassword, setShowPassword] = useState(false);
    const [attempts, setAttempts] = useState(0);
    const [isLocked, setIsLocked] = useState(false);
    const [lockTimer, setLockTimer] = useState(0);
    const [rememberMe, setRememberMe] = useState(false);
    const [twoFactorMethod, setTwoFactorMethod] = useState<string>('authenticator');

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
      return true;
    }, [externalValidatePassword]);

    const validateTwoFactorCode = useCallback((code: string): boolean | string => {
      if (!code) return 'Le code 2FA est requis';
      if (!/^\d{6}$/.test(code)) return 'Le code doit contenir 6 chiffres';
      return true;
    }, []);

    // ========================================================================
    // GESTIONNAIRES DE CHAMPS
    // ========================================================================

    const handleFieldChange = useCallback(<K extends keyof LoginFormData>(
      field: K,
      value: LoginFormData[K]
    ) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
      
      // Effacer l'erreur du champ
      setFormErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }, []);

    // ========================================================================
    // VALIDATION DU FORMULAIRE
    // ========================================================================

    const validateStep = useCallback((): boolean => {
      const errors: Record<string, string> = {};
      let isValid = true;

      if (step === 'credentials') {
        const emailResult = validateEmail(formData.email);
        if (typeof emailResult === 'string') {
          errors.email = emailResult;
          isValid = false;
        }

        const passwordResult = validatePassword(formData.password);
        if (typeof passwordResult === 'string') {
          errors.password = passwordResult;
          isValid = false;
        }
      }

      if (step === '2fa') {
        const codeResult = validateTwoFactorCode(formData.twoFactorCode || '');
        if (typeof codeResult === 'string') {
          errors.twoFactorCode = codeResult;
          isValid = false;
        }
      }

      setFormErrors(errors);
      return isValid;
    }, [
      step,
      formData,
      validateEmail,
      validatePassword,
      validateTwoFactorCode,
    ]);

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
        setLockTimer(lockDuration);
        
        // Démarrer le compte à rebours
        if (timerRef.current) {
          clearInterval(timerRef.current);
        }
        timerRef.current = setInterval(() => {
          setLockTimer((prev) => {
            if (prev <= 1) {
              if (timerRef.current) clearInterval(timerRef.current);
              setIsLocked(false);
              return 0;
            }
            return prev - 1;
          });
        }, 1000);

        toast({
          title: 'Compte verrouillé',
          description: `Trop de tentatives. Veuillez réessayer dans ${lockDuration} secondes.`,
          variant: 'destructive',
        });
        return;
      }

      setIsSubmitting(true);
      setStep('loading');

      try {
        let loginResult;

        if (step === '2fa' && requireTwoFactor) {
          // Connexion avec 2FA
          loginResult = await signInWith2FA({
            email: formData.email,
            code: formData.twoFactorCode || '',
            method: twoFactorMethod,
          });
        } else {
          // Connexion standard
          loginResult = await signIn({
            email: formData.email,
            password: formData.password,
            rememberMe: formData.rememberMe,
          });
        }

        // Callback externe
        if (onSubmit) {
          await onSubmit(formData);
        }

        // Vérifier si la 2FA est requise
        if (requireTwoFactor && loginResult?.requires2FA) {
          setStep('2fa');
          setIsSubmitting(false);
          toast({
            title: 'Vérification 2FA requise',
            description: 'Entrez votre code d\'authentification',
            duration: 4000,
          });
          return;
        }

        // Succès
        setStep('success');
        if (onSuccess) onSuccess(formData);
        
        toast({
          title: 'Connexion réussie',
          description: 'Bienvenue sur Nexus Trading IA',
          variant: 'success',
        });

        if (debug) {
          console.log('Connexion réussie:', formData.email);
        }

        // Redirection
        if (redirectUrl) {
          setTimeout(() => {
            window.location.href = redirectUrl;
          }, 1500);
        }

      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Identifiants incorrects';
        setAttempts((prev) => prev + 1);
        
        // Gestion des erreurs
        if (errorMessage.includes('2FA') || errorMessage.includes('code')) {
          setStep('2fa');
        } else {
          setStep('credentials');
        }

        setFormErrors((prev) => ({ ...prev, _form: errorMessage }));
        
        if (onError) onError(errorMessage);
        
        toast({
          title: 'Erreur de connexion',
          description: errorMessage,
          variant: 'destructive',
        });

        if (debug) console.error('Erreur de connexion:', err);
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
      lockDuration,
      step,
      formData,
      requireTwoFactor,
      twoFactorMethod,
      onSubmit,
      onSuccess,
      onError,
      signIn,
      signInWith2FA,
      redirectUrl,
      toast,
      debug,
    ]);

    // ========================================================================
    // MOT DE PASSE OUBLIÉ
    // ========================================================================

    const handleForgotPassword = useCallback(() => {
      // Navigation vers la page de réinitialisation
      // ou ouverture d'un modal
      toast({
        title: 'Réinitialisation du mot de passe',
        description: 'Un lien de réinitialisation va vous être envoyé',
        duration: 4000,
      });
    }, [toast]);

    // ========================================================================
    // SOCIAL LOGIN
    // ========================================================================

    const handleSocialLogin = useCallback(async (provider: string) => {
      if (isSubmitting || isLoading || disabled) return;

      setIsSubmitting(true);

      try {
        if (onSocialLogin) {
          await onSocialLogin(provider);
        }

        toast({
          title: `Connexion avec ${provider}`,
          description: 'Redirection en cours...',
          duration: 3000,
        });

      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Erreur de connexion sociale';
        toast({
          title: 'Erreur',
          description: errorMessage,
          variant: 'destructive',
        });
      } finally {
        setIsSubmitting(false);
      }
    }, [isSubmitting, isLoading, disabled, onSocialLogin, toast]);

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

    // --- Rendu du logo ---
    const renderLogo = () => {
      if (!showLogo) return null;

      return (
        <div className="flex justify-center mb-6">
          <div className="h-16 w-16 rounded-full bg-brand-500 flex items-center justify-center">
            <span className="text-2xl font-bold text-white">N</span>
          </div>
        </div>
      );
    };

    // --- Rendu des options sociales ---
    const renderSocialLogin = () => {
      if (!showSocialLogin || socialProviders.length === 0) return null;

      return (
        <div className="space-y-3">
          <div className="flex items-center gap-3">
            <Separator className="flex-1" />
            <span className="text-xs text-gray-500 dark:text-gray-400">ou continuer avec</span>
            <Separator className="flex-1" />
          </div>

          <div className="flex justify-center gap-2">
            {socialProviders.map((provider) => (
              <Tooltip key={provider} content={`Se connecter avec ${provider}`}>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="h-10 w-10 p-0 rounded-full"
                  onClick={() => handleSocialLogin(provider)}
                  disabled={isSubmitting || isLoading || disabled}
                >
                  {SOCIAL_ICONS[provider] || provider.charAt(0).toUpperCase()}
                </Button>
              </Tooltip>
            ))}
          </div>
        </div>
      );
    };

    // --- Rendu de l'étape Credentials ---
    const renderCredentialsStep = () => (
      <div className="space-y-4">
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
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                passwordInputRef.current?.focus();
              }
            }}
          />
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label htmlFor="password" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Mot de passe <span className="text-red-500">*</span>
            </label>
            {showForgotPassword && (
              <button
                type="button"
                onClick={handleForgotPassword}
                className="text-xs text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300 transition-colors"
              >
                Mot de passe oublié ?
              </button>
            )}
          </div>
          <Input
            ref={passwordInputRef}
            id="password"
            type={showPassword ? 'text' : 'password'}
            placeholder="Votre mot de passe"
            value={formData.password}
            onChange={(e) => handleFieldChange('password', e.target.value)}
            error={formErrors.password}
            disabled={disabled || isSubmitting || isLoading || isLocked}
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
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                formRef.current?.dispatchEvent(
                  new Event('submit', { cancelable: true, bubbles: true })
                );
              }
            }}
          />
        </div>

        <div className="flex items-center justify-between">
          <Checkbox
            id="rememberMe"
            checked={formData.rememberMe || false}
            onCheckedChange={(checked) => handleFieldChange('rememberMe', !!checked)}
            disabled={disabled || isSubmitting || isLoading || isLocked}
          >
            <span className="text-sm text-gray-600 dark:text-gray-300">Se souvenir de moi</span>
          </Checkbox>

          {showRegister && (
            <button
              type="button"
              onClick={() => {
                // Navigation vers la page d'inscription
                toast({
                  title: 'Créer un compte',
                  description: 'Redirection vers la page d\'inscription',
                  duration: 3000,
                });
              }}
              className="text-sm text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300 transition-colors"
            >
              Créer un compte
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

    // --- Rendu de l'étape 2FA ---
    const renderTwoFactorStep = () => (
      <div className="space-y-4">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-brand-100 dark:bg-brand-900/30">
            <ShieldCheckIcon className="h-8 w-8 text-brand-600 dark:text-brand-400" />
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Entrez le code de vérification à 6 chiffres
          </p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            Envoyé sur votre méthode d'authentification
          </p>
        </div>

        {/* Méthode 2FA */}
        {twoFactorMethods.length > 1 && (
          <div className="flex flex-wrap gap-2 justify-center">
            {twoFactorMethods.map((method) => (
              <Badge
                key={method}
                variant={twoFactorMethod === method ? 'primary' : 'outline'}
                className="cursor-pointer"
                onClick={() => setTwoFactorMethod(method)}
              >
                {method === 'authenticator' && '🔐 Authenticator'}
                {method === 'sms' && '📱 SMS'}
                {method === 'email' && '📧 Email'}
                {method === 'recovery' && '🔑 Récupération'}
              </Badge>
            ))}
          </div>
        )}

        <div className="space-y-2">
          <label htmlFor="twoFactorCode" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Code de vérification <span className="text-red-500">*</span>
          </label>
          <Input
            ref={twoFactorInputRef}
            id="twoFactorCode"
            type="text"
            placeholder="000000"
            value={formData.twoFactorCode || ''}
            onChange={(e) => handleFieldChange('twoFactorCode', e.target.value)}
            error={formErrors.twoFactorCode}
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
            className="text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300 transition-colors"
            onClick={() => {
              toast({
                title: 'Code renvoyé',
                description: 'Un nouveau code vous a été envoyé',
                duration: 3000,
              });
            }}
          >
            Renvoyer le code
          </button>
        </div>

        <Button
          type="button"
          variant="ghost"
          size="sm"
          className="w-full text-gray-500"
          onClick={() => setStep('credentials')}
        >
          <ArrowLeftIcon className="mr-2 h-4 w-4" />
          Retour
        </Button>
      </div>
    );

    // --- Rendu de l'étape Loading ---
    const renderLoadingStep = () => (
      <div className="flex flex-col items-center justify-center py-8">
        <ArrowPathIcon className="h-12 w-12 animate-spin text-brand-500" />
        <p className="mt-4 text-sm text-gray-500 dark:text-gray-400">
          Connexion en cours...
        </p>
        <Progress value={undefined} className="mt-4 w-32 h-1" indeterminate />
      </div>
    );

    // --- Rendu de l'étape Success ---
    const renderSuccessStep = () => (
      <div className="flex flex-col items-center justify-center py-8 text-center">
        <div className="flex h-20 w-20 items-center justify-center rounded-full bg-green-100 dark:bg-green-900/30">
          <CheckCircleIcon className="h-10 w-10 text-green-600 dark:text-green-400" />
        </div>
        <h3 className="mt-4 text-xl font-semibold text-gray-900 dark:text-white">
          Connexion réussie !
        </h3>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
          Redirection vers votre tableau de bord...
        </p>
        <Progress value={100} className="mt-4 w-32 h-1" />
      </div>
    );

    // --- Rendu de l'état verrouillé ---
    const renderLockedState = () => (
      <div className="mt-4 flex items-center gap-2 rounded-lg bg-red-50 dark:bg-red-900/20 p-3 text-sm text-red-600 dark:text-red-400">
        <ClockIcon className="h-5 w-5 flex-shrink-0" />
        <span>
          Compte temporairement verrouillé. Réessayez dans {lockTimer} secondes.
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
            <CardTitle className="text-center flex-1">{title}</CardTitle>
            {showThemeToggle && (
              <button
                type="button"
                onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
                className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                aria-label="Changer le thème"
              >
                {resolvedTheme === 'dark' ? (
                  <SunIcon className="h-5 w-5" />
                ) : (
                  <MoonIcon className="h-5 w-5" />
                )}
              </button>
            )}
          </div>
          {subtitle && step === 'credentials' && (
            <p className="text-sm text-gray-500 dark:text-gray-400 text-center">
              {subtitle}
            </p>
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

            {/* Contenu de l'étape */}
            <AnimatePresence mode="wait">
              <motion.div
                key={step}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
              >
                {step === 'credentials' && renderCredentialsStep()}
                {step === '2fa' && renderTwoFactorStep()}
                {step === 'loading' && renderLoadingStep()}
                {step === 'success' && renderSuccessStep()}
              </motion.div>
            </AnimatePresence>

            {/* Compte verrouillé */}
            {isLockedScreen && renderLockedState()}
          </form>

          {/* Social Login */}
          {step === 'credentials' && renderSocialLogin()}
        </CardContent>

        {/* Footer */}
        {step === 'credentials' && !isLockedScreen && (
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
              {isSubmitting ? 'Connexion en cours...' : 'Se connecter'}
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

        {/* Footer 2FA */}
        {step === '2fa' && !isLockedScreen && (
          <CardFooter className="border-t border-gray-200 dark:border-gray-700 p-6">
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
              Vérifier
            </Button>
          </CardFooter>
        )}
      </Card>
    );
  }
);

LoginForm.displayName = 'LoginForm';

export default LoginForm;

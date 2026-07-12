// apps/web/src/components/forms/auth/RegisterForm.tsx
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
  UserIcon,
  EnvelopeIcon,
  LockClosedIcon,
  EyeIcon,
  EyeSlashIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ArrowPathIcon,
  ShieldCheckIcon,
  KeyIcon,
  DevicePhoneMobileIcon,
  AtSymbolIcon,
  UserGroupIcon,
  BuildingOfficeIcon,
  BriefcaseIcon,
  CalendarIcon,
  ClockIcon,
  CheckIcon,
  XMarkIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
  DocumentTextIcon,
  ClipboardDocumentIcon,
  ShieldExclamationIcon,
  FingerPrintIcon,
  QrCodeIcon,
  GlobeAltIcon,
  ComputerDesktopIcon,
  WifiIcon,
  SignalIcon,
  ExclamationCircleIcon,
  PlusIcon,
  MinusIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  LinkIcon,
  BookmarkIcon,
  HeartIcon,
  StarIcon,
  FlagIcon,
} from '@heroicons/react/24/outline';
import {
  CheckCircleIcon as CheckCircleSolid,
  ExclamationCircleIcon as ExclamationCircleSolid,
} from '@heroicons/react/24/solid';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Checkbox } from '@/components/common/Checkbox';
import { Select } from '@/components/common/Select';
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

export type RegisterStep = 'account' | 'profile' | 'verification' | 'success';

export interface RegisterFormData {
  // --- Compte ---
  email: string;
  password: string;
  confirmPassword: string;
  username?: string;

  // --- Profil ---
  firstName: string;
  lastName: string;
  displayName?: string;
  phone?: string;
  company?: string;
  position?: string;
  referralCode?: string;

  // --- Préférences ---
  language?: string;
  timezone?: string;
  newsletter?: boolean;
  termsAccepted: boolean;
  privacyAccepted: boolean;
  marketingAccepted?: boolean;

  // --- Vérification ---
  verificationCode?: string;
  verificationMethod?: 'email' | 'sms' | 'authenticator';
}

export interface RegisterFormProps {
  // --- Contrôle ---
  /** Étape initiale */
  initialStep?: RegisterStep;
  /** Données initiales */
  initialData?: Partial<RegisterFormData>;
  /** Callback de soumission */
  onSubmit?: (data: RegisterFormData) => void | Promise<void>;
  /** Callback de succès */
  onSuccess?: (data: RegisterFormData) => void;
  /** Callback d'erreur */
  onError?: (error: string) => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de changement d'étape */
  onStepChange?: (step: RegisterStep) => void;

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
  /** Exiger la vérification email */
  requireEmailVerification?: boolean;
  /** Exiger le numéro de téléphone */
  requirePhone?: boolean;
  /** Exiger la société */
  requireCompany?: boolean;
  /** Exiger le code de parrainage */
  requireReferral?: boolean;
  /** Afficher les options de newsletter */
  showNewsletter?: boolean;
  /** Afficher les options marketing */
  showMarketing?: boolean;
  /** Délai de renvoi du code (secondes) */
  resendCooldown?: number;
  /** Nombre maximum de tentatives */
  maxAttempts?: number;
  /** URL de redirection après succès */
  redirectUrl?: string;

  // --- Social Login ---
  /** Afficher les options sociales */
  showSocialLogin?: boolean;
  /** Fournisseurs sociaux disponibles */
  socialProviders?: ('google' | 'github' | 'apple' | 'facebook' | 'twitter')[];
  /** Callback pour les providers sociaux */
  onSocialLogin?: (provider: string) => void;

  // --- États ---
  /** État de chargement */
  isLoading?: boolean;
  /** État d'erreur */
  error?: string | null;
  /** Message de succès */
  success?: string | null;
  /** Désactiver le formulaire */
  disabled?: boolean;

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
  /** Callback de validation du téléphone */
  validatePhone?: (phone: string) => boolean | string;
  /** Callback de validation du code */
  validateCode?: (code: string) => boolean | string;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const SOCIAL_ICONS = {
  google: (
    <svg className="h-5 w-5" viewBox="0 0 24 24">
      <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z" />
      <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" />
      <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" />
      <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" />
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

const LANGUAGES = [
  { value: 'fr', label: 'Français' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Español' },
  { value: 'de', label: 'Deutsch' },
  { value: 'it', label: 'Italiano' },
  { value: 'pt', label: 'Português' },
];

const TIMEZONES = [
  { value: 'Europe/Paris', label: 'Europe/Paris (UTC+1)' },
  { value: 'Europe/London', label: 'Europe/London (UTC+0)' },
  { value: 'America/New_York', label: 'America/New_York (UTC-5)' },
  { value: 'America/Chicago', label: 'America/Chicago (UTC-6)' },
  { value: 'Asia/Tokyo', label: 'Asia/Tokyo (UTC+9)' },
  { value: 'Asia/Singapore', label: 'Asia/Singapore (UTC+8)' },
];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const RegisterForm = forwardRef<HTMLDivElement, RegisterFormProps>(
  (props, ref) => {
    const {
      // Contrôle
      initialStep = 'account',
      initialData = {},
      onSubmit,
      onSuccess,
      onError,
      onCancel,
      onStepChange,

      // Apparence
      title = 'Créer un compte',
      subtitle = 'Rejoignez Nexus Trading IA',
      className,
      variant = 'default',
      size = 'md',

      // Configuration
      requireEmailVerification = true,
      requirePhone = false,
      requireCompany = false,
      requireReferral = false,
      showNewsletter = true,
      showMarketing = true,
      resendCooldown = 60,
      maxAttempts = 3,
      redirectUrl = '/dashboard',

      // Social Login
      showSocialLogin = true,
      socialProviders = ['google', 'github', 'apple'],
      onSocialLogin,

      // États
      isLoading = false,
      error = null,
      success = null,
      disabled = false,

      // Accessibilité
      ariaLabel = 'Formulaire d\'inscription',
      id,

      // Avancé
      validateEmail: externalValidateEmail,
      validatePassword: externalValidatePassword,
      validatePhone: externalValidatePhone,
      validateCode: externalValidateCode,
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const formRef = useRef<HTMLFormElement>(null);
    const emailInputRef = useRef<HTMLInputElement>(null);
    const passwordInputRef = useRef<HTMLInputElement>(null);
    const codeInputRef = useRef<HTMLInputElement>(null);
    const timerRef = useRef<NodeJS.Timeout | null>(null);

    // ========================================================================
    // HOOKS
    // ========================================================================

    const { toast } = useToast();
    const { signUp, verifyEmail, resendVerification } = useAuth();
    const { resolvedTheme, setTheme } = useTheme();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [step, setStep] = useState<RegisterStep>(initialStep);
    const [formData, setFormData] = useState<RegisterFormData>({
      email: '',
      password: '',
      confirmPassword: '',
      username: '',
      firstName: '',
      lastName: '',
      displayName: '',
      phone: '',
      company: '',
      position: '',
      referralCode: '',
      language: 'fr',
      timezone: 'Europe/Paris',
      newsletter: true,
      termsAccepted: false,
      privacyAccepted: false,
      marketingAccepted: false,
      verificationCode: '',
      verificationMethod: 'email',
      ...initialData,
    });

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [passwordStrength, setPasswordStrength] = useState(0);
    const [isResending, setIsResending] = useState(false);
    const [resendCooldown, setResendCooldown] = useState(0);
    const [attempts, setAttempts] = useState(0);
    const [isLocked, setIsLocked] = useState(false);
    const [termsScroll, setTermsScroll] = useState(false);
    const [privacyScroll, setPrivacyScroll] = useState(false);

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

    const validatePhone = useCallback((phone: string): boolean | string => {
      if (externalValidatePhone) {
        return externalValidatePhone(phone);
      }
      if (!phone && requirePhone) return 'Le numéro de téléphone est requis';
      if (phone && !/^[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}$/.test(phone)) {
        return 'Veuillez entrer un numéro de téléphone valide';
      }
      return true;
    }, [externalValidatePhone, requirePhone]);

    const validateCode = useCallback((code: string): boolean | string => {
      if (externalValidateCode) {
        return externalValidateCode(code);
      }
      if (!code) return 'Le code de vérification est requis';
      if (!/^\d{6}$/.test(code)) return 'Le code doit contenir 6 chiffres';
      return true;
    }, [externalValidateCode]);

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

    const handleFieldChange = useCallback(<K extends keyof RegisterFormData>(
      field: K,
      value: RegisterFormData[K]
    ) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
      setFormErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });

      if (field === 'password') {
        setPasswordStrength(calculatePasswordStrength(value as string));
        // Valider la confirmation en temps réel
        if (formData.confirmPassword) {
          const confirmResult = validateConfirmPassword(value as string, formData.confirmPassword);
          if (typeof confirmResult === 'string') {
            setFormErrors((prev) => ({ ...prev, confirmPassword: confirmResult }));
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
        const password = formData.password;
        const confirm = value as string;
        if (password && confirm) {
          const result = validateConfirmPassword(password, confirm);
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
    }, [formData]);

    const validateConfirmPassword = useCallback((password: string, confirm: string): boolean | string => {
      if (!confirm) return 'Veuillez confirmer le mot de passe';
      if (password !== confirm) return 'Les mots de passe ne correspondent pas';
      return true;
    }, []);

    // ========================================================================
    // VALIDATION DU FORMULAIRE
    // ========================================================================

    const validateStep = useCallback((): boolean => {
      const errors: Record<string, string> = {};
      let isValid = true;

      if (step === 'account') {
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

        const confirmResult = validateConfirmPassword(formData.password, formData.confirmPassword);
        if (typeof confirmResult === 'string') {
          errors.confirmPassword = confirmResult;
          isValid = false;
        }

        if (formData.phone) {
          const phoneResult = validatePhone(formData.phone);
          if (typeof phoneResult === 'string') {
            errors.phone = phoneResult;
            isValid = false;
          }
        }

        if (!formData.termsAccepted) {
          errors.terms = 'Vous devez accepter les conditions d\'utilisation';
          isValid = false;
        }

        if (!formData.privacyAccepted) {
          errors.privacy = 'Vous devez accepter la politique de confidentialité';
          isValid = false;
        }
      }

      if (step === 'profile') {
        if (!formData.firstName) {
          errors.firstName = 'Le prénom est requis';
          isValid = false;
        }
        if (!formData.lastName) {
          errors.lastName = 'Le nom est requis';
          isValid = false;
        }
        if (requireCompany && !formData.company) {
          errors.company = 'La société est requise';
          isValid = false;
        }
        if (requireReferral && !formData.referralCode) {
          errors.referralCode = 'Le code de parrainage est requis';
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

      setFormErrors(errors);
      return isValid;
    }, [
      step,
      formData,
      validateEmail,
      validatePassword,
      validateConfirmPassword,
      validatePhone,
      validateCode,
      requireCompany,
      requireReferral,
    ]);

    // ========================================================================
    // NAVIGATION ENTRE LES ÉTAPES
    // ========================================================================

    const goToStep = useCallback((newStep: RegisterStep) => {
      setStep(newStep);
      if (onStepChange) onStepChange(newStep);

      // Focus sur le premier champ
      setTimeout(() => {
        switch (newStep) {
          case 'account':
            emailInputRef.current?.focus();
            break;
          case 'verification':
            codeInputRef.current?.focus();
            break;
          default:
            break;
        }
      }, 100);
    }, [onStepChange]);

    const handleNext = useCallback(async () => {
      if (!validateStep()) {
        toast({
          title: 'Erreur de validation',
          description: 'Veuillez corriger les erreurs du formulaire',
          variant: 'destructive',
        });
        return;
      }

      if (step === 'account') {
        // Aller à l'étape profil ou vérification
        if (requireEmailVerification) {
          try {
            // Envoyer le code de vérification
            setIsSubmitting(true);
            await signUp({
              email: formData.email,
              password: formData.password,
            });
            goToStep('verification');
            // Démarrer le compte à rebours
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
            toast({
              title: 'Code envoyé',
              description: 'Un code de vérification a été envoyé à votre email',
              duration: 4000,
            });
          } catch (err) {
            const errorMessage = err instanceof Error ? err.message : 'Erreur d\'envoi du code';
            toast({
              title: 'Erreur',
              description: errorMessage,
              variant: 'destructive',
            });
          } finally {
            setIsSubmitting(false);
          }
        } else {
          goToStep('profile');
        }
      } else if (step === 'profile') {
        // Soumettre le formulaire complet
        await handleSubmit(new Event('submit') as any);
      }
    }, [step, validateStep, formData, requireEmailVerification, resendCooldown, signUp, goToStep, toast]);

    const handleBack = useCallback(() => {
      const stepOrder: RegisterStep[] = ['account', 'profile', 'verification', 'success'];
      const currentIndex = stepOrder.indexOf(step);
      if (currentIndex > 0) {
        goToStep(stepOrder[currentIndex - 1]);
      }
    }, [step, goToStep]);

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
        // Construction des données finales
        const submitData = { ...formData };
        delete submitData.confirmPassword;
        delete submitData.verificationCode;

        // Appel de l'API d'inscription
        if (onSubmit) {
          await onSubmit(submitData);
        }

        // Succès
        goToStep('success');
        if (onSuccess) onSuccess(submitData);

        toast({
          title: 'Inscription réussie',
          description: 'Bienvenue sur Nexus Trading IA',
          variant: 'success',
        });

        if (debug) {
          console.log('Inscription réussie:', submitData);
        }

        // Redirection
        if (redirectUrl) {
          setTimeout(() => {
            window.location.href = redirectUrl;
          }, 2000);
        }

      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Erreur d\'inscription';
        if (onError) onError(errorMessage);
        toast({
          title: 'Erreur d\'inscription',
          description: errorMessage,
          variant: 'destructive',
        });
        if (debug) console.error('Erreur d\'inscription:', err);
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
      onSubmit,
      onSuccess,
      onError,
      goToStep,
      redirectUrl,
      toast,
      debug,
    ]);

    // ========================================================================
    // RENVOI DU CODE
    // ========================================================================

    const handleResendCode = useCallback(async () => {
      if (isResending || resendCooldown > 0 || isLocked) return;

      setIsResending(true);
      try {
        await resendVerification(formData.email);
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
        toast({
          title: 'Code renvoyé',
          description: 'Un nouveau code vous a été envoyé',
          duration: 4000,
        });
      } catch (err) {
        toast({
          title: 'Erreur',
          description: 'Impossible de renvoyer le code. Veuillez réessayer.',
          variant: 'destructive',
        });
      } finally {
        setIsResending(false);
      }
    }, [isResending, resendCooldown, isLocked, formData.email, resendVerification, toast]);

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

    // --- Rendu de l'étape Account ---
    const renderAccountStep = () => (
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
          <label htmlFor="password" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Mot de passe <span className="text-red-500">*</span>
          </label>
          <Input
            ref={passwordInputRef}
            id="password"
            type={showPassword ? 'text' : 'password'}
            placeholder="Mot de passe"
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
          />
          {formData.password && (
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

        {requirePhone && (
          <div className="space-y-2">
            <label htmlFor="phone" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Téléphone {requirePhone && <span className="text-red-500">*</span>}
            </label>
            <Input
              id="phone"
              type="tel"
              placeholder="+33 6 12 34 56 78"
              value={formData.phone || ''}
              onChange={(e) => handleFieldChange('phone', e.target.value)}
              error={formErrors.phone}
              disabled={disabled || isSubmitting || isLoading || isLocked}
              className="h-11"
              prefix={<DevicePhoneMobileIcon className="h-4 w-4 text-gray-400" />}
            />
          </div>
        )}

        <Separator />

        <div className="space-y-2">
          <div className="flex items-start gap-3">
            <Checkbox
              id="terms"
              checked={formData.termsAccepted}
              onCheckedChange={(checked) => handleFieldChange('termsAccepted', !!checked)}
              disabled={disabled || isSubmitting || isLoading || isLocked}
            />
            <label htmlFor="terms" className="text-sm text-gray-600 dark:text-gray-300">
              J'accepte les{' '}
              <button
                type="button"
                className="text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
                onClick={() => setTermsScroll(true)}
              >
                conditions d'utilisation
              </button>
              {' '}et{' '}
              <button
                type="button"
                className="text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
                onClick={() => setPrivacyScroll(true)}
              >
                la politique de confidentialité
              </button>
              {' '}<span className="text-red-500">*</span>
            </label>
          </div>
          {formErrors.terms && (
            <p className="text-sm text-red-600 dark:text-red-400">{formErrors.terms}</p>
          )}
          {formErrors.privacy && (
            <p className="text-sm text-red-600 dark:text-red-400">{formErrors.privacy}</p>
          )}
        </div>

        {showNewsletter && (
          <div className="flex items-start gap-3">
            <Checkbox
              id="newsletter"
              checked={formData.newsletter}
              onCheckedChange={(checked) => handleFieldChange('newsletter', !!checked)}
              disabled={disabled || isSubmitting || isLoading || isLocked}
            />
            <label htmlFor="newsletter" className="text-sm text-gray-600 dark:text-gray-300">
              Je souhaite recevoir la newsletter Nexus
            </label>
          </div>
        )}

        {showMarketing && (
          <div className="flex items-start gap-3">
            <Checkbox
              id="marketing"
              checked={formData.marketingAccepted}
              onCheckedChange={(checked) => handleFieldChange('marketingAccepted', !!checked)}
              disabled={disabled || isSubmitting || isLoading || isLocked}
            />
            <label htmlFor="marketing" className="text-sm text-gray-600 dark:text-gray-300">
              Je souhaite recevoir des offres promotionnelles
            </label>
          </div>
        )}

        {attempts > 0 && attempts < maxAttempts && !isLocked && (
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Tentatives restantes: {maxAttempts - attempts}
          </p>
        )}
      </div>
    );

    // --- Rendu de l'étape Profile ---
    const renderProfileStep = () => (
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label htmlFor="firstName" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Prénom <span className="text-red-500">*</span>
            </label>
            <Input
              id="firstName"
              placeholder="Jean"
              value={formData.firstName}
              onChange={(e) => handleFieldChange('firstName', e.target.value)}
              error={formErrors.firstName}
              disabled={disabled || isSubmitting || isLoading || isLocked}
              className="h-11"
              autoFocus
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="lastName" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Nom <span className="text-red-500">*</span>
            </label>
            <Input
              id="lastName"
              placeholder="Dupont"
              value={formData.lastName}
              onChange={(e) => handleFieldChange('lastName', e.target.value)}
              error={formErrors.lastName}
              disabled={disabled || isSubmitting || isLoading || isLocked}
              className="h-11"
            />
          </div>
        </div>

        <div className="space-y-2">
          <label htmlFor="displayName" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Nom d'affichage
          </label>
          <Input
            id="displayName"
            placeholder="Jean D."
            value={formData.displayName || ''}
            onChange={(e) => handleFieldChange('displayName', e.target.value)}
            disabled={disabled || isSubmitting || isLoading || isLocked}
            className="h-11"
          />
        </div>

        {requireCompany && (
          <div className="space-y-2">
            <label htmlFor="company" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Société <span className="text-red-500">*</span>
            </label>
            <Input
              id="company"
              placeholder="Nexus Trading IA"
              value={formData.company || ''}
              onChange={(e) => handleFieldChange('company', e.target.value)}
              error={formErrors.company}
              disabled={disabled || isSubmitting || isLoading || isLocked}
              className="h-11"
              prefix={<BuildingOfficeIcon className="h-4 w-4 text-gray-400" />}
            />
          </div>
        )}

        <div className="space-y-2">
          <label htmlFor="position" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Poste
          </label>
          <Input
            id="position"
            placeholder="Développeur Full Stack"
            value={formData.position || ''}
            onChange={(e) => handleFieldChange('position', e.target.value)}
            disabled={disabled || isSubmitting || isLoading || isLocked}
            className="h-11"
            prefix={<BriefcaseIcon className="h-4 w-4 text-gray-400" />}
          />
        </div>

        {requireReferral && (
          <div className="space-y-2">
            <label htmlFor="referralCode" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Code de parrainage <span className="text-red-500">*</span>
            </label>
            <Input
              id="referralCode"
              placeholder="CODE123"
              value={formData.referralCode || ''}
              onChange={(e) => handleFieldChange('referralCode', e.target.value)}
              error={formErrors.referralCode}
              disabled={disabled || isSubmitting || isLoading || isLocked}
              className="h-11 uppercase"
              prefix={<UserGroupIcon className="h-4 w-4 text-gray-400" />}
            />
          </div>
        )}

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label htmlFor="language" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Langue
            </label>
            <Select
              id="language"
              options={LANGUAGES}
              value={formData.language || 'fr'}
              onChange={(value) => handleFieldChange('language', value)}
              disabled={disabled || isSubmitting || isLoading || isLocked}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="timezone" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Fuseau horaire
            </label>
            <Select
              id="timezone"
              options={TIMEZONES}
              value={formData.timezone || 'Europe/Paris'}
              onChange={(value) => handleFieldChange('timezone', value)}
              disabled={disabled || isSubmitting || isLoading || isLocked}
            />
          </div>
        </div>
      </div>
    );

    // --- Rendu de l'étape Verification ---
    const renderVerificationStep = () => (
      <div className="space-y-4">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-brand-100 dark:bg-brand-900/30">
            <ShieldCheckIcon className="h-8 w-8 text-brand-600 dark:text-brand-400" />
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Un code de vérification a été envoyé à <strong>{formData.email}</strong>
          </p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            Veuillez vérifier votre boîte de réception (et vos spams)
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
            onClick={handleResendCode}
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
          <button
            type="button"
            onClick={handleBack}
            className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 transition-colors"
          >
            Modifier l'email
          </button>
        </div>

        {attempts > 0 && attempts < maxAttempts && !isLocked && (
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Tentatives restantes: {maxAttempts - attempts}
          </p>
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
          Inscription réussie !
        </h3>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
          Bienvenue sur Nexus Trading IA. Votre compte a été créé avec succès.
        </p>
        <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
          Redirection vers votre tableau de bord...
        </p>
        <Progress value={100} className="mt-4 w-32 h-1" />
      </div>
    );

    // --- Rendu des options sociales ---
    const renderSocialLogin = () => {
      if (!showSocialLogin || socialProviders.length === 0 || step !== 'account') return null;

      return (
        <div className="space-y-3 mt-4">
          <div className="flex items-center gap-3">
            <Separator className="flex-1" />
            <span className="text-xs text-gray-500 dark:text-gray-400">ou s'inscrire avec</span>
            <Separator className="flex-1" />
          </div>

          <div className="flex justify-center gap-2">
            {socialProviders.map((provider) => (
              <Tooltip key={provider} content={`S'inscrire avec ${provider}`}>
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
            {onCancel && (
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
          {subtitle && step === 'account' && (
            <p className="text-sm text-gray-500 dark:text-gray-400">{subtitle}</p>
          )}
          {showStepIndicator && (
            <div className="flex items-center justify-center gap-2 mt-3">
              <Badge variant={step === 'account' ? 'primary' : 'outline'} size="sm">
                1. Compte
              </Badge>
              {requireEmailVerification && (
                <>
                  <div className="h-px w-4 bg-gray-300 dark:bg-gray-600" />
                  <Badge variant={step === 'verification' ? 'primary' : 'outline'} size="sm">
                    2. Vérification
                  </Badge>
                </>
              )}
              <div className="h-px w-4 bg-gray-300 dark:bg-gray-600" />
              <Badge variant={step === 'profile' ? 'primary' : 'outline'} size="sm">
                {requireEmailVerification ? '3. Profil' : '2. Profil'}
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
                {step === 'account' && renderAccountStep()}
                {step === 'profile' && renderProfileStep()}
                {step === 'verification' && renderVerificationStep()}
                {step === 'success' && renderSuccessStep()}
              </motion.div>
            </AnimatePresence>

            {/* Compte verrouillé */}
            {isLockedScreen && (
              <div className="mt-4 flex items-center gap-2 rounded-lg bg-red-50 dark:bg-red-900/20 p-3 text-sm text-red-600 dark:text-red-400">
                <ClockIcon className="h-5 w-5 flex-shrink-0" />
                <span>
                  Compte temporairement verrouillé. Veuillez réessayer plus tard.
                </span>
              </div>
            )}
          </form>

          {/* Social Login */}
          {renderSocialLogin()}
        </CardContent>

        {/* Footer */}
        {step !== 'success' && (
          <CardFooter className="flex flex-col gap-3 border-t border-gray-200 dark:border-gray-700 p-6">
            <div className="flex gap-2 w-full">
              {step !== 'account' && (
                <Button
                  type="button"
                  variant="ghost"
                  className="flex-1"
                  onClick={handleBack}
                  disabled={isSubmitting || isLoading || disabled || isLockedScreen}
                >
                  <ArrowLeftIcon className="mr-2 h-4 w-4" />
                  Retour
                </Button>
              )}
              <Button
                type="button"
                variant="primary"
                className={cn(step === 'account' ? 'w-full' : 'flex-1')}
                onClick={step === 'success' ? undefined : handleNext}
                disabled={
                  isSubmitting ||
                  isLoading ||
                  disabled ||
                  isLockedScreen ||
                  step === 'success'
                }
                isLoading={isSubmitting || isLoading}
              >
                {step === 'account' && 'Continuer'}
                {step === 'profile' && 'Créer mon compte'}
                {step === 'verification' && 'Vérifier'}
                <ArrowRightIcon className="ml-2 h-4 w-4" />
              </Button>
            </div>

            {step === 'account' && (
              <p className="text-sm text-gray-500 dark:text-gray-400">
                Vous avez déjà un compte ?{' '}
                <button
                  type="button"
                  onClick={onCancel}
                  className="text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
                >
                  Se connecter
                </button>
              </p>
            )}
          </CardFooter>
        )}

        {/* Footer succès */}
        {step === 'success' && onCancel && (
          <CardFooter className="border-t border-gray-200 dark:border-gray-700 p-6">
            <Button
              type="button"
              variant="primary"
              className="w-full"
              onClick={onCancel}
            >
              Accéder à mon tableau de bord
            </Button>
          </CardFooter>
        )}

        {/* Modal Conditions d'utilisation */}
        {termsScroll && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
            <div className="w-full max-w-2xl max-h-[80vh] rounded-xl bg-white dark:bg-gray-900 p-6 shadow-xl overflow-hidden flex flex-col">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Conditions d'utilisation
                </h3>
                <button
                  type="button"
                  onClick={() => setTermsScroll(false)}
                  className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                >
                  <XMarkIcon className="h-5 w-5" />
                </button>
              </div>
              <div className="flex-1 overflow-y-auto">
                <div className="prose dark:prose-invert max-w-none">
                  <h4>1. Acceptation des conditions</h4>
                  <p>En créant un compte sur Nexus Trading IA, vous acceptez ces conditions d'utilisation...</p>
                  <h4>2. Utilisation du service</h4>
                  <p>Le service est fourni à des fins de trading algorithmique...</p>
                  <h4>3. Responsabilités</h4>
                  <p>Vous êtes responsable de la sécurité de votre compte...</p>
                  <h4>4. Propriété intellectuelle</h4>
                  <p>Tous les droits de propriété intellectuelle appartiennent à Nexus Quantum LTD...</p>
                  <h4>5. Limitation de responsabilité</h4>
                  <p>Nexus Trading IA ne garantit pas les performances de trading...</p>
                </div>
              </div>
              <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                <Button
                  type="button"
                  variant="primary"
                  className="w-full"
                  onClick={() => {
                    setTermsScroll(false);
                    handleFieldChange('termsAccepted', true);
                  }}
                >
                  J'accepte les conditions
                </Button>
              </div>
            </div>
          </div>
        )}

        {/* Modal Politique de confidentialité */}
        {privacyScroll && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
            <div className="w-full max-w-2xl max-h-[80vh] rounded-xl bg-white dark:bg-gray-900 p-6 shadow-xl overflow-hidden flex flex-col">
              <div className="flex items-center justify-between mb-4">
                <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                  Politique de confidentialité
                </h3>
                <button
                  type="button"
                  onClick={() => setPrivacyScroll(false)}
                  className="rounded-lg p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                >
                  <XMarkIcon className="h-5 w-5" />
                </button>
              </div>
              <div className="flex-1 overflow-y-auto">
                <div className="prose dark:prose-invert max-w-none">
                  <h4>1. Collecte des données</h4>
                  <p>Nous collectons les données nécessaires à la création de votre compte...</p>
                  <h4>2. Utilisation des données</h4>
                  <p>Vos données sont utilisées pour fournir le service de trading...</p>
                  <h4>3. Protection des données</h4>
                  <p>Nous mettons en œuvre des mesures de sécurité avancées...</p>
                  <h4>4. Partage des données</h4>
                  <p>Nous ne partageons pas vos données avec des tiers sans votre consentement...</p>
                  <h4>5. Vos droits</h4>
                  <p>Vous avez le droit d'accéder, modifier ou supprimer vos données...</p>
                </div>
              </div>
              <div className="mt-4 pt-4 border-t border-gray-200 dark:border-gray-700">
                <Button
                  type="button"
                  variant="primary"
                  className="w-full"
                  onClick={() => {
                    setPrivacyScroll(false);
                    handleFieldChange('privacyAccepted', true);
                  }}
                >
                  J'accepte la politique de confidentialité
                </Button>
              </div>
            </div>
          </div>
        )}
      </Card>
    );
  }
);

RegisterForm.displayName = 'RegisterForm';

export default RegisterForm;

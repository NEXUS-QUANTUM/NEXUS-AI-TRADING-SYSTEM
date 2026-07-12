// apps/web/src/components/forms/auth/TwoFactorForm.tsx
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
  ShieldCheckIcon,
  KeyIcon,
  DevicePhoneMobileIcon,
  EnvelopeIcon,
  QrCodeIcon,
  FingerPrintIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ArrowPathIcon,
  EyeIcon,
  EyeSlashIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  CheckIcon,
  XMarkIcon,
  ClockIcon,
  ExclamationCircleIcon,
  DocumentTextIcon,
  ClipboardDocumentIcon,
  LockClosedIcon,
  ShieldExclamationIcon,
  UserIcon,
  AtSymbolIcon,
} from '@heroicons/react/24/outline';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Separator } from '@/components/common/Separator';
import { Progress } from '@/components/common/Progress';
import { Tooltip } from '@/components/common/Tooltip';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/common/Tabs';
import { useToast } from '@/hooks/useToast';
import { useAuth } from '@/hooks/useAuth';

// ============================================================================
// TYPES
// ============================================================================

export type TwoFactorMethod = 'authenticator' | 'sms' | 'email' | 'recovery';
export type TwoFactorStep = 'method' | 'verify' | 'setup' | 'recovery' | 'success';

export interface TwoFactorFormData {
  /** Méthode 2FA */
  method: TwoFactorMethod;
  /** Code de vérification */
  code: string;
  /** Code de récupération */
  recoveryCode?: string;
  /** Email pour la méthode email */
  email?: string;
  /** Téléphone pour la méthode sms */
  phone?: string;
  /** Secret pour l'authenticator */
  secret?: string;
  /** QR Code pour l'authenticator */
  qrCode?: string;
}

export interface TwoFactorFormProps {
  // --- Contrôle ---
  /** Méthode initiale */
  initialMethod?: TwoFactorMethod;
  /** Étape initiale */
  initialStep?: TwoFactorStep;
  /** Données initiales */
  initialData?: Partial<TwoFactorFormData>;
  /** Callback de soumission */
  onSubmit?: (data: TwoFactorFormData) => void | Promise<void>;
  /** Callback de succès */
  onSuccess?: (data: TwoFactorFormData) => void;
  /** Callback d'erreur */
  onError?: (error: string) => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de changement d'étape */
  onStepChange?: (step: TwoFactorStep) => void;

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
  /** Afficher les méthodes disponibles */
  showMethods?: boolean;

  // --- Configuration ---
  /** Méthodes 2FA disponibles */
  availableMethods?: TwoFactorMethod[];
  /** Délai de renvoi du code (secondes) */
  resendCooldown?: number;
  /** Nombre maximum de tentatives */
  maxAttempts?: number;
  /** Longueur du code */
  codeLength?: number;
  /** Exiger la récupération */
  requireRecovery?: boolean;
  /** Afficher les codes de récupération */
  showRecoveryCodes?: boolean;
  /** Nombre de codes de récupération */
  recoveryCodeCount?: number;

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
  /** Callback de validation du code */
  validateCode?: (code: string) => boolean | string;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const METHOD_ICONS: Record<TwoFactorMethod, React.ReactNode> = {
  authenticator: <QrCodeIcon className="h-6 w-6" />,
  sms: <DevicePhoneMobileIcon className="h-6 w-6" />,
  email: <EnvelopeIcon className="h-6 w-6" />,
  recovery: <KeyIcon className="h-6 w-6" />,
};

const METHOD_LABELS: Record<TwoFactorMethod, string> = {
  authenticator: 'Application Authenticator',
  sms: 'SMS',
  email: 'Email',
  recovery: 'Code de récupération',
};

const METHOD_DESCRIPTIONS: Record<TwoFactorMethod, string> = {
  authenticator: 'Utilisez Google Authenticator, Authy ou une application compatible',
  sms: 'Recevez un code par SMS sur votre téléphone',
  email: 'Recevez un code par email',
  recovery: 'Utilisez l\'un de vos codes de récupération',
};

const RECOVERY_CODE_COUNT = 8;

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const TwoFactorForm = forwardRef<HTMLDivElement, TwoFactorFormProps>(
  (props, ref) => {
    const {
      // Contrôle
      initialMethod = 'authenticator',
      initialStep = 'method',
      initialData = {},
      onSubmit,
      onSuccess,
      onError,
      onCancel,
      onStepChange,

      // Apparence
      title = 'Authentification à deux facteurs',
      subtitle = 'Sécurisez votre compte avec une vérification supplémentaire',
      className,
      variant = 'default',
      size = 'md',
      showMethods = true,

      // Configuration
      availableMethods = ['authenticator', 'sms', 'email', 'recovery'],
      resendCooldown = 30,
      maxAttempts = 5,
      codeLength = 6,
      requireRecovery = true,
      showRecoveryCodes = true,
      recoveryCodeCount = RECOVERY_CODE_COUNT,

      // États
      isLoading = false,
      error = null,
      success = null,
      disabled = false,

      // Accessibilité
      ariaLabel = 'Formulaire d\'authentification à deux facteurs',
      id,

      // Avancé
      validateCode: externalValidateCode,
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const formRef = useRef<HTMLFormElement>(null);
    const codeInputRef = useRef<HTMLInputElement>(null);
    const recoveryInputRef = useRef<HTMLInputElement>(null);
    const timerRef = useRef<NodeJS.Timeout | null>(null);

    // ========================================================================
    // HOOKS
    // ========================================================================

    const { toast } = useToast();
    const { verify2FA, setup2FA, resend2FACode } = useAuth();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [step, setStep] = useState<TwoFactorStep>(initialStep);
    const [formData, setFormData] = useState<TwoFactorFormData>({
      method: initialMethod,
      code: '',
      recoveryCode: '',
      email: '',
      phone: '',
      secret: '',
      qrCode: '',
      ...initialData,
    });
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [attempts, setAttempts] = useState(0);
    const [isLocked, setIsLocked] = useState(false);
    const [resendCooldownLeft, setResendCooldownLeft] = useState(0);
    const [isResending, setIsResending] = useState(false);
    const [recoveryCodes, setRecoveryCodes] = useState<string[]>([]);
    const [selectedMethod, setSelectedMethod] = useState<TwoFactorMethod>(initialMethod);
    const [showRecovery, setShowRecovery] = useState(false);
    const [qrCodeImage, setQrCodeImage] = useState<string | null>(null);
    const [secretKey, setSecretKey] = useState<string | null>(null);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validateCode = useCallback((code: string): boolean | string => {
      if (externalValidateCode) {
        return externalValidateCode(code);
      }
      if (!code) return 'Le code est requis';
      if (!/^\d{6}$/.test(code)) return 'Le code doit contenir 6 chiffres';
      return true;
    }, [externalValidateCode]);

    const validateRecoveryCode = useCallback((code: string): boolean | string => {
      if (!code) return 'Le code de récupération est requis';
      if (code.length < 8) return 'Code de récupération invalide';
      return true;
    }, []);

    // ========================================================================
    // GESTIONNAIRES DE CHAMPS
    // ========================================================================

    const handleFieldChange = useCallback(<K extends keyof TwoFactorFormData>(
      field: K,
      value: TwoFactorFormData[K]
    ) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
      setFormErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }, []);

    const handleMethodChange = useCallback((method: TwoFactorMethod) => {
      setSelectedMethod(method);
      handleFieldChange('method', method);
      if (onStepChange) onStepChange('method');
    }, [handleFieldChange, onStepChange]);

    // ========================================================================
    // VALIDATION DU FORMULAIRE
    // ========================================================================

    const validateStep = useCallback((): boolean => {
      const errors: Record<string, string> = {};
      let isValid = true;

      if (step === 'verify') {
        const codeResult = validateCode(formData.code);
        if (typeof codeResult === 'string') {
          errors.code = codeResult;
          isValid = false;
        }
      }

      if (step === 'recovery') {
        const recoveryResult = validateRecoveryCode(formData.recoveryCode || '');
        if (typeof recoveryResult === 'string') {
          errors.recoveryCode = recoveryResult;
          isValid = false;
        }
      }

      setFormErrors(errors);
      return isValid;
    }, [step, formData, validateCode, validateRecoveryCode]);

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
        let result;

        if (step === 'setup') {
          // Configuration de la 2FA
          result = await setup2FA({
            method: formData.method,
            ...(formData.method === 'authenticator' && { secret: formData.secret }),
            ...(formData.method === 'sms' && { phone: formData.phone }),
            ...(formData.method === 'email' && { email: formData.email }),
          });

          if (result.recoveryCodes) {
            setRecoveryCodes(result.recoveryCodes);
          }

          setStep('success');
          if (onStepChange) onStepChange('success');
          if (onSuccess) onSuccess(formData);

          toast({
            title: '2FA activée',
            description: `L'authentification à deux facteurs a été activée avec succès`,
            variant: 'success',
          });

          if (debug) {
            console.log('2FA activée:', formData);
          }
          return;
        }

        if (step === 'verify') {
          // Vérification du code
          result = await verify2FA({
            code: formData.code,
            method: formData.method,
          });

          if (result.success) {
            setStep('success');
            if (onStepChange) onStepChange('success');
            if (onSuccess) onSuccess(formData);

            toast({
              title: 'Vérification réussie',
              description: 'Code 2FA validé avec succès',
              variant: 'success',
            });
          }
          return;
        }

        if (step === 'recovery') {
          // Utilisation d'un code de récupération
          result = await verify2FA({
            code: formData.recoveryCode || '',
            method: 'recovery',
          });

          if (result.success) {
            setStep('success');
            if (onStepChange) onStepChange('success');
            if (onSuccess) onSuccess(formData);

            toast({
              title: 'Récupération réussie',
              description: 'Code de récupération validé avec succès',
              variant: 'success',
            });
          }
          return;
        }

        // Soumission générale
        if (onSubmit) {
          await onSubmit(formData);
        }

      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Erreur de vérification';
        if (onError) onError(errorMessage);
        toast({
          title: 'Erreur',
          description: errorMessage,
          variant: 'destructive',
        });
        if (debug) console.error('Erreur 2FA:', err);
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
      setup2FA,
      verify2FA,
      onSubmit,
      onSuccess,
      onError,
      onStepChange,
      toast,
      debug,
    ]);

    // ========================================================================
    // RENVOI DU CODE
    // ========================================================================

    const handleResend = useCallback(async () => {
      if (isResending || resendCooldownLeft > 0 || isLocked) return;

      setIsResending(true);
      try {
        await resend2FACode({
          method: formData.method,
          ...(formData.method === 'sms' && { phone: formData.phone }),
          ...(formData.method === 'email' && { email: formData.email }),
        });

        setResendCooldownLeft(resendCooldown);
        if (timerRef.current) {
          clearInterval(timerRef.current);
        }
        timerRef.current = setInterval(() => {
          setResendCooldownLeft((prev) => {
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
    }, [isResending, resendCooldownLeft, isLocked, formData.method, formData.phone, formData.email, resend2FACode, resendCooldown, toast]);

    // ========================================================================
    // INITIALISATION 2FA
    // ========================================================================

    useEffect(() => {
      if (step === 'setup' && formData.method === 'authenticator') {
        // Générer le secret et le QR code
        const generateSecret = async () => {
          try {
            const result = await setup2FA({ method: 'authenticator' });
            setSecretKey(result.secret);
            setQrCodeImage(result.qrCode);
            handleFieldChange('secret', result.secret);
            handleFieldChange('qrCode', result.qrCode);
          } catch (err) {
            toast({
              title: 'Erreur',
              description: 'Impossible de générer le code QR',
              variant: 'destructive',
            });
          }
        };
        generateSecret();
      }
    }, [step, formData.method, setup2FA, handleFieldChange, toast]);

    // ========================================================================
    // RENDU
    // ========================================================================

    // --- Rendu de la sélection de méthode ---
    const renderMethodSelection = () => (
      <div className="space-y-4">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-brand-100 dark:bg-brand-900/30">
            <ShieldCheckIcon className="h-8 w-8 text-brand-600 dark:text-brand-400" />
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Choisissez votre méthode d'authentification
          </p>
        </div>

        <div className="grid grid-cols-1 gap-3">
          {availableMethods.map((method) => (
            <button
              key={method}
              type="button"
              className={cn(
                'flex items-center gap-4 rounded-lg border-2 p-4 text-left transition-all',
                selectedMethod === method
                  ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                  : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
              )}
              onClick={() => handleMethodChange(method)}
              disabled={disabled || isSubmitting || isLoading}
            >
              <div className={cn(
                'flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full',
                selectedMethod === method
                  ? 'bg-brand-500 text-white'
                  : 'bg-gray-100 dark:bg-gray-800 text-gray-500 dark:text-gray-400'
              )}>
                {METHOD_ICONS[method]}
              </div>
              <div className="flex-1">
                <p className="font-medium text-gray-900 dark:text-white">
                  {METHOD_LABELS[method]}
                </p>
                <p className="text-sm text-gray-500 dark:text-gray-400">
                  {METHOD_DESCRIPTIONS[method]}
                </p>
              </div>
              {selectedMethod === method && (
                <CheckIcon className="h-5 w-5 text-brand-500" />
              )}
            </button>
          ))}
        </div>

        <div className="flex justify-end">
          <Button
            type="button"
            variant="primary"
            onClick={() => {
              if (selectedMethod === 'recovery') {
                setStep('recovery');
                if (onStepChange) onStepChange('recovery');
              } else {
                setStep('verify');
                if (onStepChange) onStepChange('verify');
                // Focus sur le champ code
                setTimeout(() => codeInputRef.current?.focus(), 100);
              }
            }}
            disabled={disabled || isSubmitting || isLoading}
          >
            Continuer
            <ArrowRightIcon className="ml-2 h-4 w-4" />
          </Button>
        </div>

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
      </div>
    );

    // --- Rendu de l'étape Verify ---
    const renderVerifyStep = () => (
      <div className="space-y-4">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-brand-100 dark:bg-brand-900/30">
            {METHOD_ICONS[selectedMethod]}
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Entrez le code de vérification envoyé
          </p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            {selectedMethod === 'authenticator' && 'Ouvrez votre application Authenticator'}
            {selectedMethod === 'sms' && 'Code envoyé par SMS'}
            {selectedMethod === 'email' && 'Code envoyé par email'}
          </p>
        </div>

        <div className="space-y-2">
          <label htmlFor="code" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Code de vérification <span className="text-red-500">*</span>
          </label>
          <Input
            ref={codeInputRef}
            id="code"
            type="text"
            placeholder="000000"
            value={formData.code}
            onChange={(e) => handleFieldChange('code', e.target.value)}
            error={formErrors.code}
            disabled={disabled || isSubmitting || isLoading || isLocked}
            autoFocus
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

        <div className="flex items-center justify-between text-sm">
          <button
            type="button"
            onClick={handleResend}
            disabled={isResending || resendCooldownLeft > 0 || isLocked}
            className={cn(
              'text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300 transition-colors',
              (isResending || resendCooldownLeft > 0 || isLocked) && 'opacity-50 cursor-not-allowed'
            )}
          >
            {isResending ? (
              <>
                <ArrowPathIcon className="inline h-3 w-3 animate-spin mr-1" />
                Envoi en cours...
              </>
            ) : resendCooldownLeft > 0 ? (
              `Renvoyer dans ${resendCooldownLeft}s`
            ) : (
              'Renvoyer le code'
            )}
          </button>
          <button
            type="button"
            onClick={() => {
              setStep('method');
              if (onStepChange) onStepChange('method');
            }}
            className="text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 transition-colors"
          >
            <ArrowLeftIcon className="inline h-3 w-3 mr-1" />
            Changer de méthode
          </button>
        </div>

        {attempts > 0 && attempts < maxAttempts && !isLocked && (
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Tentatives restantes: {maxAttempts - attempts}
          </p>
        )}
      </div>
    );

    // --- Rendu de l'étape Recovery ---
    const renderRecoveryStep = () => (
      <div className="space-y-4">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-yellow-100 dark:bg-yellow-900/30">
            <KeyIcon className="h-8 w-8 text-yellow-600 dark:text-yellow-400" />
          </div>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Utilisez l'un de vos codes de récupération
          </p>
          <p className="text-xs text-gray-400 dark:text-gray-500 mt-1">
            Chaque code ne peut être utilisé qu'une seule fois
          </p>
        </div>

        <div className="space-y-2">
          <label htmlFor="recoveryCode" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Code de récupération <span className="text-red-500">*</span>
          </label>
          <Input
            ref={recoveryInputRef}
            id="recoveryCode"
            type="text"
            placeholder="XXXX-XXXX-XXXX-XXXX"
            value={formData.recoveryCode || ''}
            onChange={(e) => handleFieldChange('recoveryCode', e.target.value)}
            error={formErrors.recoveryCode}
            disabled={disabled || isSubmitting || isLoading || isLocked}
            autoFocus
            className="h-11 font-mono text-center tracking-wider"
            prefix={<KeyIcon className="h-4 w-4 text-gray-400" />}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                handleSubmit(e);
              }
            }}
          />
        </div>

        <button
          type="button"
          onClick={() => {
            setStep('method');
            if (onStepChange) onStepChange('method');
          }}
          className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 transition-colors"
        >
          <ArrowLeftIcon className="inline h-3 w-3 mr-1" />
          Retour
        </button>

        {attempts > 0 && attempts < maxAttempts && !isLocked && (
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Tentatives restantes: {maxAttempts - attempts}
          </p>
        )}
      </div>
    );

    // --- Rendu de l'étape Setup (configuration 2FA) ---
    const renderSetupStep = () => (
      <div className="space-y-4">
        <div className="text-center">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-full bg-brand-100 dark:bg-brand-900/30">
            <ShieldCheckIcon className="h-8 w-8 text-brand-600 dark:text-brand-400" />
          </div>
          <p className="text-sm font-medium text-gray-900 dark:text-white">
            Configurer l'authentification à deux facteurs
          </p>
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {selectedMethod === 'authenticator' && 'Scannez le QR code avec votre application Authenticator'}
            {selectedMethod === 'sms' && 'Entrez votre numéro de téléphone'}
            {selectedMethod === 'email' && 'Entrez votre email de vérification'}
          </p>
        </div>

        {selectedMethod === 'authenticator' && (
          <div className="space-y-4">
            {qrCodeImage && (
              <div className="flex justify-center">
                <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 bg-white dark:bg-gray-800">
                  <img
                    src={qrCodeImage}
                    alt="QR Code 2FA"
                    className="h-48 w-48"
                  />
                </div>
              </div>
            )}
            {secretKey && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Clé secrète
                </label>
                <div className="flex items-center gap-2">
                  <code className="flex-1 rounded-lg bg-gray-100 dark:bg-gray-800 p-2 text-sm font-mono text-center">
                    {secretKey}
                  </code>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => {
                      navigator.clipboard.writeText(secretKey);
                      toast({
                        title: 'Copié',
                        description: 'La clé secrète a été copiée dans le presse-papier',
                        duration: 2000,
                      });
                    }}
                  >
                    <ClipboardDocumentIcon className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            )}
            <div className="space-y-2">
              <label htmlFor="setupCode" className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Code de vérification <span className="text-red-500">*</span>
              </label>
              <Input
                ref={codeInputRef}
                id="setupCode"
                type="text"
                placeholder="000000"
                value={formData.code}
                onChange={(e) => handleFieldChange('code', e.target.value)}
                error={formErrors.code}
                disabled={disabled || isSubmitting || isLoading || isLocked}
                className="h-11 text-center text-lg font-mono tracking-widest"
                maxLength={codeLength}
                prefix={<KeyIcon className="h-4 w-4 text-gray-400" />}
              />
            </div>
          </div>
        )}

        {selectedMethod === 'sms' && (
          <div className="space-y-2">
            <label htmlFor="phone" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Numéro de téléphone <span className="text-red-500">*</span>
            </label>
            <Input
              id="phone"
              type="tel"
              placeholder="+33 6 12 34 56 78"
              value={formData.phone || ''}
              onChange={(e) => handleFieldChange('phone', e.target.value)}
              disabled={disabled || isSubmitting || isLoading || isLocked}
              className="h-11"
              prefix={<DevicePhoneMobileIcon className="h-4 w-4 text-gray-400" />}
            />
          </div>
        )}

        {selectedMethod === 'email' && (
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
              disabled={disabled || isSubmitting || isLoading || isLocked}
              className="h-11"
              prefix={<EnvelopeIcon className="h-4 w-4 text-gray-400" />}
            />
          </div>
        )}

        <Button
          type="button"
          variant="primary"
          className="w-full"
          onClick={handleSubmit}
          disabled={isSubmitting || isLoading || disabled || isLocked}
          isLoading={isSubmitting || isLoading}
        >
          Activer la 2FA
        </Button>

        <button
          type="button"
          onClick={() => {
            setStep('method');
            if (onStepChange) onStepChange('method');
          }}
          className="text-sm text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300 transition-colors w-full text-center"
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
          {step === 'setup' ? '2FA activée !' : 'Vérification réussie !'}
        </h3>
        <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
          {step === 'setup' 
            ? 'L\'authentification à deux facteurs a été activée avec succès.'
            : 'Code vérifié avec succès.'
          }
        </p>

        {showRecoveryCodes && recoveryCodes.length > 0 && (
          <div className="mt-4 w-full">
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Codes de récupération
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Gardez ces codes dans un endroit sûr. Chaque code ne peut être utilisé qu'une seule fois.
            </p>
            <div className="mt-2 grid grid-cols-2 gap-1 rounded-lg bg-gray-50 dark:bg-gray-800/50 p-3">
              {recoveryCodes.map((code, index) => (
                <code key={index} className="font-mono text-sm">
                  {code}
                </code>
              ))}
            </div>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              className="mt-2"
              onClick={() => {
                navigator.clipboard.writeText(recoveryCodes.join('\n'));
                toast({
                  title: 'Copié',
                  description: 'Les codes de récupération ont été copiés dans le presse-papier',
                  duration: 2000,
                });
              }}
            >
              <ClipboardDocumentIcon className="h-4 w-4 mr-2" />
              Copier les codes
            </Button>
          </div>
        )}

        <div className="mt-6 flex gap-3">
          <Button
            type="button"
            variant="primary"
            onClick={() => {
              if (onCancel) onCancel();
              else if (step === 'setup') {
                // Redirection vers la page de sécurité
                window.location.href = '/settings/security';
              }
            }}
          >
            Terminé
          </Button>
        </div>
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
          {subtitle && step === 'method' && (
            <p className="text-sm text-gray-500 dark:text-gray-400">{subtitle}</p>
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
                {step === 'method' && renderMethodSelection()}
                {step === 'verify' && renderVerifyStep()}
                {step === 'recovery' && renderRecoveryStep()}
                {step === 'setup' && renderSetupStep()}
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
        </CardContent>

        {/* Footer pour les étapes verify/recovery */}
        {(step === 'verify' || step === 'recovery') && !isLockedScreen && (
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
              {step === 'verify' && 'Vérifier'}
              {step === 'recovery' && 'Utiliser le code de récupération'}
            </Button>
          </CardFooter>
        )}

        {/* Footer pour l'étape setup */}
        {step === 'setup' && !isLockedScreen && (
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
              Activer
            </Button>
          </CardFooter>
        )}
      </Card>
    );
  }
);

TwoFactorForm.displayName = 'TwoFactorForm';

export default TwoFactorForm;

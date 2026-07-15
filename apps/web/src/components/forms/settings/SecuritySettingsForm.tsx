// apps/web/src/components/forms/settings/SecuritySettingsForm.tsx
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
  ShieldExclamationIcon,
  LockClosedIcon,
  LockOpenIcon,
  KeyIcon,
  FingerPrintIcon,
  QrCodeIcon,
  DevicePhoneMobileIcon,
  LaptopIcon,
  ComputerDesktopIcon,
  GlobeAltIcon,
  ClockIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ExclamationCircleIcon,
  PlusIcon,
  MinusIcon,
  CheckIcon,
  XMarkIcon,
  ArrowPathIcon,
  PencilIcon,
  TrashIcon,
  Cog6ToothIcon,
  AdjustmentsHorizontalIcon,
  EyeIcon,
  EyeSlashIcon,
  UserIcon,
  UserGroupIcon,
  BuildingOfficeIcon,
  EnvelopeIcon,
  PhoneIcon,
  MapPinIcon,
  CalendarIcon,
  DocumentTextIcon,
  ReceiptPercentIcon,
  WifiIcon,
  WifiSlashIcon,
  ServerIcon,
  CloudIcon,
  DatabaseIcon,
  LinkIcon,
  LinkSlashIcon,
} from '@heroicons/react/24/outline';
import {
  CheckCircleIcon as CheckCircleSolid,
  ExclamationCircleIcon as ExclamationCircleSolid,
} from '@heroicons/react/24/solid';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Select } from '@/components/common/Select';
import { Switch } from '@/components/common/Switch';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/common/Tabs';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Separator } from '@/components/common/Separator';
import { Progress } from '@/components/common/Progress';
import { Tooltip } from '@/components/common/Tooltip';
import { ScrollArea } from '@/components/common/ScrollArea';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type TwoFactorMethod = 'authenticator' | 'sms' | 'email' | 'recovery' | 'none';
export type SessionStatus = 'active' | 'inactive' | 'expired' | 'revoked';
export type DeviceType = 'desktop' | 'mobile' | 'tablet' | 'unknown';
export type SecurityLevel = 'low' | 'medium' | 'high' | 'maximum';
export type PasswordPolicy = 'basic' | 'standard' | 'strict' | 'custom';

export interface Device {
  /** Identifiant du dispositif */
  id: string;
  /** Nom du dispositif */
  name: string;
  /** Type de dispositif */
  type: DeviceType;
  /** Navigateur */
  browser: string;
  /** Système d'exploitation */
  os: string;
  /** Adresse IP */
  ip: string;
  /** Localisation */
  location?: string;
  /** Dernière utilisation */
  lastUsed: Date;
  /** Date de création */
  createdAt: Date;
  /** Est approuvé */
  isApproved: boolean;
  /** Est le dispositif actuel */
  isCurrent: boolean;
}

export interface Session {
  /** Identifiant de session */
  id: string;
  /** Dispositif */
  device: Device;
  /** Date de début */
  startedAt: Date;
  /** Date d'expiration */
  expiresAt: Date;
  /** Statut */
  status: SessionStatus;
  /** Dernière activité */
  lastActivity: Date;
}

export interface SecuritySettingsData {
  /** Mot de passe actuel */
  currentPassword?: string;
  /** Nouveau mot de passe */
  newPassword?: string;
  /** Confirmation du mot de passe */
  confirmPassword?: string;
  /** Politique de mot de passe */
  passwordPolicy: PasswordPolicy;
  /** Exigences de mot de passe */
  passwordRequirements: {
    minLength: number;
    requireUppercase: boolean;
    requireLowercase: boolean;
    requireNumber: boolean;
    requireSpecial: boolean;
    maxAge: number;
    preventReuse: number;
  };
  /** 2FA */
  twoFactor: {
    method: TwoFactorMethod;
    enabled: boolean;
    verified: boolean;
    backupCodes?: string[];
    phoneNumber?: string;
    email?: string;
    authenticatorSecret?: string;
  };
  /** Sessions */
  sessions: Session[];
  /** Dispositifs */
  devices: Device[];
  /** Paramètres de sécurité */
  settings: {
    /** Session timeout (minutes) */
    sessionTimeout: number;
    /** Activer la session unique */
    singleSession: boolean;
    /** Activer la vérification IP */
    ipVerification: boolean;
    /** Activer la vérification de localisation */
    locationVerification: boolean;
    /** Activer la notification de nouveau dispositif */
    newDeviceNotification: boolean;
    /** Activer le verrouillage automatique */
    autoLock: boolean;
    /** Délai de verrouillage (minutes) */
    autoLockDelay: number;
    /** Activer le nettoyage automatique */
    autoCleanup: boolean;
    /** Délai de nettoyage (jours) */
    autoCleanupDelay: number;
    /** IPs autorisées */
    allowedIPs: string[];
    /** IPs bloquées */
    blockedIPs: string[];
  };
  /** Historique de sécurité */
  history?: Array<{
    id: string;
    event: string;
    details: string;
    timestamp: Date;
    ip: string;
    location?: string;
    status: 'success' | 'warning' | 'error';
  }>;
  /** Niveau de sécurité global */
  securityScore?: number;
  /** Dernière vérification */
  lastCheck?: Date;
}

export interface SecuritySettingsFormProps {
  // --- Contrôle ---
  /** Données initiales */
  initialData?: Partial<SecuritySettingsData>;
  /** Callback de soumission */
  onSubmit?: (data: SecuritySettingsData) => void | Promise<void>;
  /** Callback de succès */
  onSuccess?: (data: SecuritySettingsData) => void;
  /** Callback d'erreur */
  onError?: (error: string) => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de changement */
  onChange?: (data: SecuritySettingsData) => void;

  // --- Apparence ---
  /** Titre du formulaire */
  title?: string;
  /** Sous-titre */
  subtitle?: string;
  /** Classes additionnelles */
  className?: string;
  /** Variante de la carte */
  variant?: 'default' | 'glass' | 'solid' | 'outlined';

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
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const PASSWORD_POLICIES: { value: PasswordPolicy; label: string; description: string }[] = [
  {
    value: 'basic',
    label: 'Basique',
    description: 'Longueur minimale: 8 caractères',
  },
  {
    value: 'standard',
    label: 'Standard',
    description: '8 caractères, majuscule, minuscule, chiffre',
  },
  {
    value: 'strict',
    label: 'Strict',
    description: '12 caractères, majuscule, minuscule, chiffre, spécial',
  },
  {
    value: 'custom',
    label: 'Personnalisé',
    description: 'Configuration manuelle des exigences',
  },
];

const TWO_FACTOR_METHODS: { value: TwoFactorMethod; label: string; icon: React.ReactNode; description: string }[] = [
  {
    value: 'authenticator',
    label: 'Authenticator',
    icon: <QrCodeIcon className="h-4 w-4" />,
    description: 'Google Authenticator, Authy, etc.',
  },
  {
    value: 'sms',
    label: 'SMS',
    icon: <DevicePhoneMobileIcon className="h-4 w-4" />,
    description: 'Code envoyé par SMS',
  },
  {
    value: 'email',
    label: 'Email',
    icon: <EnvelopeIcon className="h-4 w-4" />,
    description: 'Code envoyé par email',
  },
  {
    value: 'recovery',
    label: 'Récupération',
    icon: <KeyIcon className="h-4 w-4" />,
    description: 'Codes de récupération',
  },
  {
    value: 'none',
    label: 'Aucune',
    icon: <XMarkIcon className="h-4 w-4" />,
    description: 'Désactiver la 2FA',
  },
];

const DEVICE_ICONS: Record<DeviceType, React.ReactNode> = {
  desktop: <ComputerDesktopIcon className="h-5 w-5" />,
  mobile: <DevicePhoneMobileIcon className="h-5 w-5" />,
  tablet: <DevicePhoneMobileIcon className="h-5 w-5" />,
  unknown: <LaptopIcon className="h-5 w-5" />,
};

const SESSION_STATUS_MAP: Record<SessionStatus, { color: string; label: string; icon: React.ReactNode }> = {
  active: {
    color: 'text-green-500',
    label: 'Active',
    icon: <CheckCircleIcon className="h-4 w-4" />,
  },
  inactive: {
    color: 'text-yellow-500',
    label: 'Inactive',
    icon: <ExclamationTriangleIcon className="h-4 w-4" />,
  },
  expired: {
    color: 'text-gray-400',
    label: 'Expirée',
    icon: <ClockIcon className="h-4 w-4" />,
  },
  revoked: {
    color: 'text-red-500',
    label: 'Révoquée',
    icon: <XMarkIcon className="h-4 w-4" />,
  },
};

const SECURITY_LEVELS: { value: SecurityLevel; label: string; color: string; score: number }[] = [
  { value: 'low', label: 'Faible', color: 'text-red-500', score: 25 },
  { value: 'medium', label: 'Moyen', color: 'text-yellow-500', score: 50 },
  { value: 'high', label: 'Élevé', color: 'text-green-500', score: 75 },
  { value: 'maximum', label: 'Maximum', color: 'text-emerald-500', score: 100 },
];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const SecuritySettingsForm = forwardRef<HTMLDivElement, SecuritySettingsFormProps>(
  (props, ref) => {
    const {
      // Contrôle
      initialData = {},
      onSubmit,
      onSuccess,
      onError,
      onCancel,
      onChange,

      // Apparence
      title = 'Sécurité',
      subtitle = 'Configurez vos paramètres de sécurité',
      className,
      variant = 'default',

      // États
      isLoading = false,
      error = null,
      success = null,
      disabled = false,

      // Accessibilité
      ariaLabel = 'Paramètres de sécurité',
      id,

      // Avancé
      debug = false,
    } = props;

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const formRef = useRef<HTMLFormElement>(null);
    const passwordInputRef = useRef<HTMLInputElement>(null);

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [formData, setFormData] = useState<SecuritySettingsData>({
      passwordPolicy: 'standard',
      passwordRequirements: {
        minLength: 8,
        requireUppercase: true,
        requireLowercase: true,
        requireNumber: true,
        requireSpecial: false,
        maxAge: 90,
        preventReuse: 5,
      },
      twoFactor: {
        method: 'authenticator',
        enabled: false,
        verified: false,
        backupCodes: [],
      },
      sessions: [],
      devices: [],
      settings: {
        sessionTimeout: 60,
        singleSession: false,
        ipVerification: true,
        locationVerification: false,
        newDeviceNotification: true,
        autoLock: true,
        autoLockDelay: 15,
        autoCleanup: true,
        autoCleanupDelay: 30,
        allowedIPs: [],
        blockedIPs: [],
      },
      securityScore: 75,
      lastCheck: new Date(),
      ...initialData,
    });

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [activeTab, setActiveTab] = useState<'password' | 'twofactor' | 'sessions' | 'settings'>('password');
    const [showPassword, setShowPassword] = useState(false);
    const [showNewPassword, setShowNewPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [passwordStrength, setPasswordStrength] = useState(0);
    const [isGeneratingBackupCodes, setIsGeneratingBackupCodes] = useState(false);
    const [newIP, setNewIP] = useState('');
    const [newBlockedIP, setNewBlockedIP] = useState('');

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validate = useCallback((): boolean => {
      const errors: Record<string, string> = {};

      // Validation du mot de passe
      if (formData.newPassword) {
        if (formData.newPassword.length < formData.passwordRequirements.minLength) {
          errors.newPassword = `Le mot de passe doit contenir au moins ${formData.passwordRequirements.minLength} caractères`;
        }
        if (formData.passwordRequirements.requireUppercase && !/[A-Z]/.test(formData.newPassword)) {
          errors.newPassword = 'Le mot de passe doit contenir une majuscule';
        }
        if (formData.passwordRequirements.requireLowercase && !/[a-z]/.test(formData.newPassword)) {
          errors.newPassword = 'Le mot de passe doit contenir une minuscule';
        }
        if (formData.passwordRequirements.requireNumber && !/[0-9]/.test(formData.newPassword)) {
          errors.newPassword = 'Le mot de passe doit contenir un chiffre';
        }
        if (formData.passwordRequirements.requireSpecial && !/[!@#$%^&*(),.?":{}|<>]/.test(formData.newPassword)) {
          errors.newPassword = 'Le mot de passe doit contenir un caractère spécial';
        }
        if (formData.newPassword !== formData.confirmPassword) {
          errors.confirmPassword = 'Les mots de passe ne correspondent pas';
        }
      }

      // Validation 2FA
      if (formData.twoFactor.enabled) {
        if (formData.twoFactor.method === 'sms' && !formData.twoFactor.phoneNumber) {
          errors.twoFactorPhone = 'Le numéro de téléphone est requis pour la 2FA par SMS';
        }
        if (formData.twoFactor.method === 'email' && !formData.twoFactor.email) {
          errors.twoFactorEmail = 'L\'email est requis pour la 2FA par email';
        }
      }

      // Validation des IPs
      const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
      formData.settings.allowedIPs.forEach(ip => {
        if (!ipRegex.test(ip)) {
          errors.allowedIPs = 'Format d\'IP invalide';
        }
      });
      formData.settings.blockedIPs.forEach(ip => {
        if (!ipRegex.test(ip)) {
          errors.blockedIPs = 'Format d\'IP invalide';
        }
      });

      setFormErrors(errors);
      return Object.keys(errors).length === 0;
    }, [formData]);

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

    const handleFieldChange = useCallback(<K extends keyof SecuritySettingsData>(
      field: K,
      value: SecuritySettingsData[K]
    ) => {
      setFormData(prev => ({ ...prev, [field]: value }));
      setFormErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }, []);

    const handleNestedFieldChange = useCallback(
      <P extends keyof SecuritySettingsData, K extends string>(
        parent: P,
        field: K,
        value: any
      ) => {
        setFormData(prev => ({
          ...prev,
          [parent]: {
            ...prev[parent],
            [field]: value,
          },
        }));
      },
      []
    );

    const handlePasswordChange = useCallback((field: 'currentPassword' | 'newPassword' | 'confirmPassword', value: string) => {
      handleFieldChange(field, value);
      if (field === 'newPassword') {
        setPasswordStrength(calculatePasswordStrength(value));
      }
    }, [handleFieldChange, calculatePasswordStrength]);

    // ========================================================================
    // GESTION DES BACKUP CODES
    // ========================================================================

    const generateBackupCodes = useCallback(() => {
      setIsGeneratingBackupCodes(true);

      // Simuler la génération de codes
      setTimeout(() => {
        const codes = Array.from({ length: 8 }, () => {
          const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789';
          let code = '';
          for (let i = 0; i < 8; i++) {
            code += chars[Math.floor(Math.random() * chars.length)];
          }
          return code;
        });

        handleNestedFieldChange('twoFactor', 'backupCodes', codes);
        setIsGeneratingBackupCodes(false);

        toast({
          title: 'Codes de récupération générés',
          description: 'Conservez ces codes dans un endroit sûr',
          duration: 5000,
        });
      }, 1500);
    }, [handleNestedFieldChange, toast]);

    // ========================================================================
    // GESTION DES SESSIONS
    // ========================================================================

    const revokeSession = useCallback((sessionId: string) => {
      setFormData(prev => ({
        ...prev,
        sessions: prev.sessions.map(s =>
          s.id === sessionId ? { ...s, status: 'revoked' as SessionStatus } : s
        ),
      }));

      toast({
        title: 'Session révoquée',
        description: 'La session a été révoquée avec succès',
        duration: 2000,
      });
    }, [toast]);

    const revokeAllSessions = useCallback(() => {
      if (confirm('Êtes-vous sûr de vouloir révoquer toutes les sessions ?')) {
        setFormData(prev => ({
          ...prev,
          sessions: prev.sessions.map(s =>
            s.isCurrent ? s : { ...s, status: 'revoked' as SessionStatus }
          ),
        }));

        toast({
          title: 'Sessions révoquées',
          description: 'Toutes les sessions ont été révoquées',
          duration: 3000,
        });
      }
    }, [toast]);

    // ========================================================================
    // GESTION DES IPs
    // ========================================================================

    const addAllowedIP = useCallback(() => {
      const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
      if (!ipRegex.test(newIP)) {
        toast({
          title: 'IP invalide',
          description: 'Format d\'IP invalide',
          variant: 'destructive',
        });
        return;
      }

      if (formData.settings.allowedIPs.includes(newIP)) {
        toast({
          title: 'IP déjà présente',
          description: 'Cette IP est déjà dans la liste des autorisées',
          variant: 'destructive',
        });
        return;
      }

      setFormData(prev => ({
        ...prev,
        settings: {
          ...prev.settings,
          allowedIPs: [...prev.settings.allowedIPs, newIP],
        },
      }));
      setNewIP('');

      toast({
        title: 'IP ajoutée',
        description: 'L\'IP a été ajoutée à la liste des autorisées',
        duration: 2000,
      });
    }, [newIP, formData.settings.allowedIPs, toast]);

    const removeAllowedIP = useCallback((ip: string) => {
      setFormData(prev => ({
        ...prev,
        settings: {
          ...prev.settings,
          allowedIPs: prev.settings.allowedIPs.filter(i => i !== ip),
        },
      }));

      toast({
        title: 'IP retirée',
        description: 'L\'IP a été retirée de la liste des autorisées',
        duration: 2000,
      });
    }, [toast]);

    const addBlockedIP = useCallback(() => {
      const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
      if (!ipRegex.test(newBlockedIP)) {
        toast({
          title: 'IP invalide',
          description: 'Format d\'IP invalide',
          variant: 'destructive',
        });
        return;
      }

      if (formData.settings.blockedIPs.includes(newBlockedIP)) {
        toast({
          title: 'IP déjà présente',
          description: 'Cette IP est déjà dans la liste des bloquées',
          variant: 'destructive',
        });
        return;
      }

      setFormData(prev => ({
        ...prev,
        settings: {
          ...prev.settings,
          blockedIPs: [...prev.settings.blockedIPs, newBlockedIP],
        },
      }));
      setNewBlockedIP('');

      toast({
        title: 'IP bloquée',
        description: 'L\'IP a été ajoutée à la liste des bloquées',
        duration: 2000,
      });
    }, [newBlockedIP, formData.settings.blockedIPs, toast]);

    const removeBlockedIP = useCallback((ip: string) => {
      setFormData(prev => ({
        ...prev,
        settings: {
          ...prev.settings,
          blockedIPs: prev.settings.blockedIPs.filter(i => i !== ip),
        },
      }));

      toast({
        title: 'IP débloquée',
        description: 'L\'IP a été retirée de la liste des bloquées',
        duration: 2000,
      });
    }, [toast]);

    // ========================================================================
    // SOUMISSION
    // ========================================================================

    const handleSubmit = useCallback(async (e: React.FormEvent) => {
      e.preventDefault();

      if (isSubmitting || isLoading || disabled) return;

      if (!validate()) {
        toast({
          title: 'Erreur de validation',
          description: 'Veuillez corriger les erreurs du formulaire',
          variant: 'destructive',
        });
        return;
      }

      setIsSubmitting(true);

      try {
        if (onSubmit) {
          await onSubmit(formData);
        }

        if (onSuccess) onSuccess(formData);

        toast({
          title: 'Paramètres de sécurité sauvegardés',
          description: 'Vos paramètres de sécurité ont été mis à jour',
          variant: 'success',
        });

        if (debug) {
          console.log('Security settings saved:', formData);
        }

      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Erreur de sauvegarde';
        if (onError) onError(errorMessage);
        toast({
          title: 'Erreur',
          description: errorMessage,
          variant: 'destructive',
        });
        if (debug) console.error('Erreur de sauvegarde:', err);
      } finally {
        setIsSubmitting(false);
      }
    }, [isSubmitting, isLoading, disabled, formData, validate, onSubmit, onSuccess, onError, toast, debug]);

    // ========================================================================
    // NOTIFICATION DES CHANGEMENTS
    // ========================================================================

    useEffect(() => {
      if (onChange) {
        onChange(formData);
      }
    }, [formData, onChange]);

    // ========================================================================
    // RENDU DE L'ONGLET MOT DE PASSE
    // ========================================================================

    const renderPasswordTab = () => (
      <div className="space-y-6">
        {/* Politique de mot de passe */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Politique de mot de passe
          </label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {PASSWORD_POLICIES.map((policy) => (
              <button
                key={policy.value}
                type="button"
                className={cn(
                  'rounded-lg border-2 p-3 text-center transition-all',
                  formData.passwordPolicy === policy.value
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
                onClick={() => handleFieldChange('passwordPolicy', policy.value)}
                disabled={disabled || isSubmitting || isLoading}
              >
                <span className="text-sm font-medium">{policy.label}</span>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {policy.description}
                </p>
              </button>
            ))}
          </div>
        </div>

        <Separator />

        {/* Changement de mot de passe */}
        <div className="space-y-4">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Changer le mot de passe
          </h4>

          <div className="space-y-3">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Mot de passe actuel
              </label>
              <div className="relative">
                <Input
                  type={showPassword ? 'text' : 'password'}
                  placeholder="Mot de passe actuel"
                  value={formData.currentPassword || ''}
                  onChange={(e) => handlePasswordChange('currentPassword', e.target.value)}
                  disabled={disabled || isSubmitting || isLoading}
                  className="pr-10"
                />
                <button
                  type="button"
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? <EyeSlashIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Nouveau mot de passe
              </label>
              <div className="relative">
                <Input
                  ref={passwordInputRef}
                  type={showNewPassword ? 'text' : 'password'}
                  placeholder="Nouveau mot de passe"
                  value={formData.newPassword || ''}
                  onChange={(e) => handlePasswordChange('newPassword', e.target.value)}
                  error={formErrors.newPassword}
                  disabled={disabled || isSubmitting || isLoading}
                  className="pr-10"
                />
                <button
                  type="button"
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  onClick={() => setShowNewPassword(!showNewPassword)}
                >
                  {showNewPassword ? <EyeSlashIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
                </button>
              </div>
              {formData.newPassword && (
                <div className="space-y-1">
                  <Progress value={passwordStrength} className="h-1" />
                  <p className="text-xs text-gray-500 dark:text-gray-400">
                    Force: {passwordStrength >= 80 ? 'Fort' : passwordStrength >= 60 ? 'Moyen' : 'Faible'}
                  </p>
                </div>
              )}
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Confirmer le mot de passe
              </label>
              <div className="relative">
                <Input
                  type={showConfirmPassword ? 'text' : 'password'}
                  placeholder="Confirmer le mot de passe"
                  value={formData.confirmPassword || ''}
                  onChange={(e) => handlePasswordChange('confirmPassword', e.target.value)}
                  error={formErrors.confirmPassword}
                  disabled={disabled || isSubmitting || isLoading}
                  className="pr-10"
                />
                <button
                  type="button"
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                >
                  {showConfirmPassword ? <EyeSlashIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
                </button>
              </div>
            </div>
          </div>
        </div>

        <Separator />

        {/* Exigences */}
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Exigences du mot de passe
          </h4>
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600 dark:text-gray-300">Longueur minimale:</span>
              <Input
                type="number"
                value={formData.passwordRequirements.minLength}
                onChange={(e) => handleNestedFieldChange('passwordRequirements', 'minLength', parseInt(e.target.value) || 8)}
                disabled={disabled || isSubmitting || isLoading || formData.passwordPolicy !== 'custom'}
                className="w-20"
                min={4}
                max={32}
              />
              <span className="text-sm text-gray-600 dark:text-gray-300">caractères</span>
            </div>

            <div className="flex flex-wrap gap-4">
              <div className="flex items-center gap-2">
                <Switch
                  checked={formData.passwordRequirements.requireUppercase}
                  onCheckedChange={(checked) => handleNestedFieldChange('passwordRequirements', 'requireUppercase', checked)}
                  disabled={disabled || isSubmitting || isLoading || formData.passwordPolicy !== 'custom'}
                  size="sm"
                />
                <span className="text-sm text-gray-600 dark:text-gray-300">Majuscule</span>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  checked={formData.passwordRequirements.requireLowercase}
                  onCheckedChange={(checked) => handleNestedFieldChange('passwordRequirements', 'requireLowercase', checked)}
                  disabled={disabled || isSubmitting || isLoading || formData.passwordPolicy !== 'custom'}
                  size="sm"
                />
                <span className="text-sm text-gray-600 dark:text-gray-300">Minuscule</span>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  checked={formData.passwordRequirements.requireNumber}
                  onCheckedChange={(checked) => handleNestedFieldChange('passwordRequirements', 'requireNumber', checked)}
                  disabled={disabled || isSubmitting || isLoading || formData.passwordPolicy !== 'custom'}
                  size="sm"
                />
                <span className="text-sm text-gray-600 dark:text-gray-300">Chiffre</span>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  checked={formData.passwordRequirements.requireSpecial}
                  onCheckedChange={(checked) => handleNestedFieldChange('passwordRequirements', 'requireSpecial', checked)}
                  disabled={disabled || isSubmitting || isLoading || formData.passwordPolicy !== 'custom'}
                  size="sm"
                />
                <span className="text-sm text-gray-600 dark:text-gray-300">Caractère spécial</span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600 dark:text-gray-300">Âge maximal (jours):</span>
              <Input
                type="number"
                value={formData.passwordRequirements.maxAge}
                onChange={(e) => handleNestedFieldChange('passwordRequirements', 'maxAge', parseInt(e.target.value) || 90)}
                disabled={disabled || isSubmitting || isLoading || formData.passwordPolicy !== 'custom'}
                className="w-20"
                min={1}
                max={365}
              />
            </div>

            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600 dark:text-gray-300">Prévention de réutilisation:</span>
              <Input
                type="number"
                value={formData.passwordRequirements.preventReuse}
                onChange={(e) => handleNestedFieldChange('passwordRequirements', 'preventReuse', parseInt(e.target.value) || 5)}
                disabled={disabled || isSubmitting || isLoading || formData.passwordPolicy !== 'custom'}
                className="w-20"
                min={1}
                max={20}
              />
              <span className="text-sm text-gray-600 dark:text-gray-300">derniers mots de passe</span>
            </div>
          </div>
        </div>
      </div>
    );

    // ========================================================================
    // RENDU DE L'ONGLET 2FA
    // ========================================================================

    const renderTwoFactorTab = () => (
      <div className="space-y-6">
        {/* État 2FA */}
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Authentification à deux facteurs
              </h4>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                {formData.twoFactor.enabled ? '2FA activée' : '2FA désactivée'}
              </p>
            </div>
            <Switch
              checked={formData.twoFactor.enabled}
              onCheckedChange={(checked) => handleNestedFieldChange('twoFactor', 'enabled', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          {formData.twoFactor.enabled && (
            <Badge variant={formData.twoFactor.verified ? 'success' : 'warning'} size="sm" className="mt-2">
              {formData.twoFactor.verified ? 'Vérifié' : 'En attente de vérification'}
            </Badge>
          )}
        </div>

        {formData.twoFactor.enabled && (
          <>
            <Separator />

            {/* Méthode 2FA */}
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Méthode d'authentification
              </h4>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                {TWO_FACTOR_METHODS.map((method) => (
                  <button
                    key={method.value}
                    type="button"
                    className={cn(
                      'flex items-center gap-3 rounded-lg border-2 p-3 transition-all',
                      formData.twoFactor.method === method.value
                        ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                        : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                    )}
                    onClick={() => handleNestedFieldChange('twoFactor', 'method', method.value)}
                    disabled={disabled || isSubmitting || isLoading || method.value === 'none'}
                  >
                    <span className="text-gray-500">{method.icon}</span>
                    <div className="flex-1 text-left">
                      <p className="font-medium">{method.label}</p>
                      <p className="text-xs text-gray-500 dark:text-gray-400">
                        {method.description}
                      </p>
                    </div>
                    {formData.twoFactor.method === method.value && (
                      <CheckIcon className="h-4 w-4 text-brand-500" />
                    )}
                  </button>
                ))}
              </div>
            </div>

            {/* Configuration spécifique */}
            {formData.twoFactor.method === 'authenticator' && (
              <div className="space-y-3">
                <div className="rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 p-4 text-center">
                  <QrCodeIcon className="mx-auto h-16 w-16 text-gray-400" />
                  <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                    Scannez le QR code avec votre application Authenticator
                  </p>
                  <p className="text-xs text-gray-400 dark:text-gray-500">
                    Code secret: {formData.twoFactor.authenticatorSecret || '••••••••••••'}
                  </p>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="mt-2"
                    onClick={() => {
                      const secret = Array.from({ length: 16 }, () => 
                        'ABCDEFGHIJKLMNOPQRSTUVWXYZ234567'[Math.floor(Math.random() * 32)]
                      ).join('');
                      handleNestedFieldChange('twoFactor', 'authenticatorSecret', secret);
                    }}
                    disabled={disabled || isSubmitting || isLoading}
                  >
                    <ArrowPathIcon className="h-4 w-4 mr-2" />
                    Générer un nouveau secret
                  </Button>
                </div>
              </div>
            )}

            {formData.twoFactor.method === 'sms' && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Numéro de téléphone
                </label>
                <Input
                  type="tel"
                  placeholder="+33 6 12 34 56 78"
                  value={formData.twoFactor.phoneNumber || ''}
                  onChange={(e) => handleNestedFieldChange('twoFactor', 'phoneNumber', e.target.value)}
                  error={formErrors.twoFactorPhone}
                  disabled={disabled || isSubmitting || isLoading}
                />
              </div>
            )}

            {formData.twoFactor.method === 'email' && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Email
                </label>
                <Input
                  type="email"
                  placeholder="securite@exemple.com"
                  value={formData.twoFactor.email || ''}
                  onChange={(e) => handleNestedFieldChange('twoFactor', 'email', e.target.value)}
                  error={formErrors.twoFactorEmail}
                  disabled={disabled || isSubmitting || isLoading}
                />
              </div>
            )}

            <Separator />

            {/* Codes de récupération */}
            <div className="space-y-3">
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Codes de récupération
              </h4>
              {formData.twoFactor.backupCodes && formData.twoFactor.backupCodes.length > 0 ? (
                <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-4">
                  <div className="grid grid-cols-2 gap-1 font-mono text-sm">
                    {formData.twoFactor.backupCodes.map((code, index) => (
                      <span key={index} className="p-1">{code}</span>
                    ))}
                  </div>
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="mt-2"
                    onClick={() => {
                      navigator.clipboard.writeText(formData.twoFactor.backupCodes!.join('\n'));
                      toast({
                        title: 'Codes copiés',
                        description: 'Les codes de récupération ont été copiés dans le presse-papier',
                        duration: 2000,
                      });
                    }}
                  >
                    <DocumentTextIcon className="h-4 w-4 mr-2" />
                    Copier les codes
                  </Button>
                </div>
              ) : (
                <Button
                  type="button"
                  variant="outline"
                  onClick={generateBackupCodes}
                  disabled={disabled || isSubmitting || isLoading || isGeneratingBackupCodes}
                  isLoading={isGeneratingBackupCodes}
                >
                  {isGeneratingBackupCodes ? 'Génération...' : 'Générer les codes de récupération'}
                </Button>
              )}
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Ces codes permettent de récupérer l'accès à votre compte en cas de perte de votre méthode 2FA.
                Conservez-les dans un endroit sûr.
              </p>
            </div>
          </>
        )}
      </div>
    );

    // ========================================================================
    // RENDU DE L'ONGLET SESSIONS
    // ========================================================================

    const renderSessionsTab = () => (
      <div className="space-y-6">
        {/* Sessions actives */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Sessions actives
            </h4>
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={revokeAllSessions}
              disabled={disabled || isSubmitting || isLoading || formData.sessions.length === 0}
              className="text-red-500 hover:text-red-600"
            >
              <TrashIcon className="h-4 w-4 mr-2" />
              Révoquer toutes
            </Button>
          </div>

          {formData.sessions.length === 0 ? (
            <div className="rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 p-8 text-center">
              <LaptopIcon className="mx-auto h-12 w-12 text-gray-400" />
              <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                Aucune session active
              </p>
            </div>
          ) : (
            <ScrollArea className="max-h-64">
              <div className="space-y-2">
                {formData.sessions.map((session) => {
                  const statusInfo = SESSION_STATUS_MAP[session.status] || SESSION_STATUS_MAP.inactive;
                  return (
                    <div
                      key={session.id}
                      className={cn(
                        'flex items-center gap-3 rounded-lg border p-3',
                        session.isCurrent ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20' : 'border-gray-200 dark:border-gray-700'
                      )}
                    >
                      <div className="flex-shrink-0">
                        {DEVICE_ICONS[session.device.type] || DEVICE_ICONS.unknown}
                      </div>
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{session.device.name}</span>
                          {session.isCurrent && (
                            <Badge variant="primary" size="xs">Actuelle</Badge>
                          )}
                          <span className={cn('flex items-center gap-1 text-xs', statusInfo.color)}>
                            {statusInfo.icon}
                            {statusInfo.label}
                          </span>
                        </div>
                        <div className="flex flex-wrap gap-2 text-xs text-gray-500 dark:text-gray-400">
                          <span>{session.device.browser}</span>
                          <span>•</span>
                          <span>{session.device.os}</span>
                          <span>•</span>
                          <span>{session.device.ip}</span>
                          {session.device.location && (
                            <>
                              <span>•</span>
                              <span>{session.device.location}</span>
                            </>
                          )}
                        </div>
                        <div className="flex gap-3 text-xs text-gray-400">
                          <span>Début: {session.startedAt.toLocaleString()}</span>
                          <span>Expire: {session.expiresAt.toLocaleString()}</span>
                          <span>Dernière activité: {session.lastActivity.toLocaleString()}</span>
                        </div>
                      </div>
                      {!session.isCurrent && session.status === 'active' && (
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => revokeSession(session.id)}
                          disabled={disabled || isSubmitting || isLoading}
                          className="text-red-500 hover:text-red-600"
                        >
                          <XMarkIcon className="h-4 w-4" />
                        </Button>
                      )}
                    </div>
                  );
                })}
              </div>
            </ScrollArea>
          )}
        </div>

        <Separator />

        {/* Appareils */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Appareils connus
          </h4>

          {formData.devices.length === 0 ? (
            <div className="rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 p-8 text-center">
              <DevicePhoneMobileIcon className="mx-auto h-12 w-12 text-gray-400" />
              <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                Aucun appareil enregistré
              </p>
            </div>
          ) : (
            <div className="space-y-2">
              {formData.devices.map((device) => (
                <div
                  key={device.id}
                  className={cn(
                    'flex items-center gap-3 rounded-lg border p-3',
                    device.isCurrent ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20' : 'border-gray-200 dark:border-gray-700'
                  )}
                >
                  <div className="flex-shrink-0">
                    {DEVICE_ICONS[device.type] || DEVICE_ICONS.unknown}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{device.name}</span>
                      {device.isCurrent && (
                        <Badge variant="primary" size="xs">Actuel</Badge>
                      )}
                      {device.isApproved ? (
                        <Badge variant="success" size="xs">Approuvé</Badge>
                      ) : (
                        <Badge variant="warning" size="xs">En attente</Badge>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2 text-xs text-gray-500 dark:text-gray-400">
                      <span>{device.browser}</span>
                      <span>•</span>
                      <span>{device.os}</span>
                      <span>•</span>
                      <span>{device.ip}</span>
                      {device.location && (
                        <>
                          <span>•</span>
                          <span>{device.location}</span>
                        </>
                      )}
                    </div>
                    <div className="flex gap-3 text-xs text-gray-400">
                      <span>Créé: {device.createdAt.toLocaleString()}</span>
                      <span>Dernière utilisation: {device.lastUsed.toLocaleString()}</span>
                    </div>
                  </div>
                  {!device.isCurrent && (
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => {
                        setFormData(prev => ({
                          ...prev,
                          devices: prev.devices.map(d =>
                            d.id === device.id ? { ...d, isApproved: !d.isApproved } : d
                          ),
                        }));
                        toast({
                          title: device.isApproved ? 'Appareil désapprouvé' : 'Appareil approuvé',
                          description: `L'appareil ${device.name} a été ${device.isApproved ? 'désapprouvé' : 'approuvé'}`,
                          duration: 2000,
                        });
                      }}
                      disabled={disabled || isSubmitting || isLoading}
                    >
                      {device.isApproved ? (
                        <LockOpenIcon className="h-4 w-4" />
                      ) : (
                        <LockClosedIcon className="h-4 w-4" />
                      )}
                    </Button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    );

    // ========================================================================
    // RENDU DE L'ONGLET PARAMÈTRES
    // ========================================================================

    const renderSettingsTab = () => (
      <div className="space-y-6">
        {/* Score de sécurité */}
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center justify-between">
            <div>
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Score de sécurité
              </h4>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Dernière vérification: {formData.lastCheck?.toLocaleString() || 'Jamais'}
              </p>
            </div>
            <div className="text-right">
              <span className="text-2xl font-bold text-gray-900 dark:text-white">
                {formData.securityScore || 0}%
              </span>
              <Badge
                variant={
                  (formData.securityScore || 0) >= 75 ? 'success' :
                  (formData.securityScore || 0) >= 50 ? 'warning' :
                  'danger'
                }
                size="sm"
                className="ml-2"
              >
                {SECURITY_LEVELS.find(l => l.score <= (formData.securityScore || 0))?.label || 'Faible'}
              </Badge>
            </div>
          </div>
          <Progress
            value={formData.securityScore || 0}
            className="mt-2 h-1.5"
            variant={
              (formData.securityScore || 0) >= 75 ? 'success' :
              (formData.securityScore || 0) >= 50 ? 'warning' :
              'error'
            }
          />
        </div>

        <Separator />

        {/* Paramètres de session */}
        <div className="space-y-4">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Paramètres de session
          </h4>

          <div className="flex items-center gap-2">
            <span className="text-sm text-gray-600 dark:text-gray-300 flex-1">
              Durée de session (minutes)
            </span>
            <Input
              type="number"
              value={formData.settings.sessionTimeout}
              onChange={(e) => handleNestedFieldChange('settings', 'sessionTimeout', parseInt(e.target.value) || 60)}
              disabled={disabled || isSubmitting || isLoading}
              className="w-24"
              min={5}
              max={1440}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Session unique
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Une seule session active à la fois
              </p>
            </div>
            <Switch
              checked={formData.settings.singleSession}
              onCheckedChange={(checked) => handleNestedFieldChange('settings', 'singleSession', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Vérification IP
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Vérifier l'adresse IP à chaque connexion
              </p>
            </div>
            <Switch
              checked={formData.settings.ipVerification}
              onCheckedChange={(checked) => handleNestedFieldChange('settings', 'ipVerification', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Vérification de localisation
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Vérifier la localisation à chaque connexion
              </p>
            </div>
            <Switch
              checked={formData.settings.locationVerification}
              onCheckedChange={(checked) => handleNestedFieldChange('settings', 'locationVerification', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Notification nouveau dispositif
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Recevoir une alerte lors d'une nouvelle connexion
              </p>
            </div>
            <Switch
              checked={formData.settings.newDeviceNotification}
              onCheckedChange={(checked) => handleNestedFieldChange('settings', 'newDeviceNotification', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <Separator />

        {/* Verrouillage automatique */}
        <div className="space-y-4">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Verrouillage automatique
          </h4>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Activer le verrouillage
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Verrouiller automatiquement après une période d'inactivité
              </p>
            </div>
            <Switch
              checked={formData.settings.autoLock}
              onCheckedChange={(checked) => handleNestedFieldChange('settings', 'autoLock', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          {formData.settings.autoLock && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600 dark:text-gray-300 flex-1">
                Délai de verrouillage (minutes)
              </span>
              <Input
                type="number"
                value={formData.settings.autoLockDelay}
                onChange={(e) => handleNestedFieldChange('settings', 'autoLockDelay', parseInt(e.target.value) || 15)}
                disabled={disabled || isSubmitting || isLoading}
                className="w-24"
                min={1}
                max={60}
              />
            </div>
          )}
        </div>

        <Separator />

        {/* Nettoyage automatique */}
        <div className="space-y-4">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Nettoyage automatique
          </h4>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Activer le nettoyage
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Supprimer automatiquement les sessions anciennes
              </p>
            </div>
            <Switch
              checked={formData.settings.autoCleanup}
              onCheckedChange={(checked) => handleNestedFieldChange('settings', 'autoCleanup', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          {formData.settings.autoCleanup && (
            <div className="flex items-center gap-2">
              <span className="text-sm text-gray-600 dark:text-gray-300 flex-1">
                Délai de nettoyage (jours)
              </span>
              <Input
                type="number"
                value={formData.settings.autoCleanupDelay}
                onChange={(e) => handleNestedFieldChange('settings', 'autoCleanupDelay', parseInt(e.target.value) || 30)}
                disabled={disabled || isSubmitting || isLoading}
                className="w-24"
                min={1}
                max={365}
              />
            </div>
          )}
        </div>

        <Separator />

        {/* IPs autorisées */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            IPs autorisées
          </h4>

          <div className="flex gap-2">
            <Input
              type="text"
              placeholder="192.168.1.1"
              value={newIP}
              onChange={(e) => setNewIP(e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
              className="flex-1"
            />
            <Button
              type="button"
              variant="outline"
              onClick={addAllowedIP}
              disabled={disabled || isSubmitting || isLoading || !newIP}
            >
              <PlusIcon className="h-4 w-4" />
            </Button>
          </div>

          {formData.settings.allowedIPs.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {formData.settings.allowedIPs.map((ip) => (
                <Badge key={ip} variant="outline" className="flex items-center gap-1">
                  {ip}
                  <button
                    type="button"
                    className="ml-1 text-gray-400 hover:text-red-500"
                    onClick={() => removeAllowedIP(ip)}
                    disabled={disabled || isSubmitting || isLoading}
                  >
                    <XMarkIcon className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Aucune IP autorisée
            </p>
          )}
        </div>

        <Separator />

        {/* IPs bloquées */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            IPs bloquées
          </h4>

          <div className="flex gap-2">
            <Input
              type="text"
              placeholder="192.168.1.1"
              value={newBlockedIP}
              onChange={(e) => setNewBlockedIP(e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
              className="flex-1"
            />
            <Button
              type="button"
              variant="outline"
              onClick={addBlockedIP}
              disabled={disabled || isSubmitting || isLoading || !newBlockedIP}
            >
              <PlusIcon className="h-4 w-4" />
            </Button>
          </div>

          {formData.settings.blockedIPs.length > 0 ? (
            <div className="flex flex-wrap gap-2">
              {formData.settings.blockedIPs.map((ip) => (
                <Badge key={ip} variant="outline" className="flex items-center gap-1 border-red-200 text-red-600 dark:border-red-800 dark:text-red-400">
                  {ip}
                  <button
                    type="button"
                    className="ml-1 text-gray-400 hover:text-red-500"
                    onClick={() => removeBlockedIP(ip)}
                    disabled={disabled || isSubmitting || isLoading}
                  >
                    <XMarkIcon className="h-3 w-3" />
                  </button>
                </Badge>
              ))}
            </div>
          ) : (
            <p className="text-sm text-gray-500 dark:text-gray-400">
              Aucune IP bloquée
            </p>
          )}
        </div>
      </div>
    );

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const hasError = !!error || Object.keys(formErrors).length > 0;

    return (
      <Card
        ref={ref}
        id={id}
        className={cn(
          'w-full max-w-4xl mx-auto overflow-hidden',
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
            <div>
              <CardTitle className="flex items-center gap-2">
                {title}
                <Badge
                  variant={
                    (formData.securityScore || 0) >= 75 ? 'success' :
                    (formData.securityScore || 0) >= 50 ? 'warning' :
                    'danger'
                  }
                  size="sm"
                >
                  {SECURITY_LEVELS.find(l => l.score <= (formData.securityScore || 0))?.label || 'Faible'}
                </Badge>
              </CardTitle>
              {subtitle && (
                <p className="text-sm text-gray-500 dark:text-gray-400">{subtitle}</p>
              )}
            </div>
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
        </CardHeader>

        {/* Tabs */}
        <div className="border-b border-gray-200 dark:border-gray-700">
          <div className="flex overflow-x-auto">
            {[
              { id: 'password', label: '🔑 Mot de passe' },
              { id: 'twofactor', label: '🔐 2FA' },
              { id: 'sessions', label: '📱 Sessions' },
              { id: 'settings', label: '⚙️ Paramètres' },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={cn(
                  'px-4 py-2.5 text-sm font-medium transition-colors whitespace-nowrap border-b-2',
                  activeTab === tab.id
                    ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                )}
                onClick={() => setActiveTab(tab.id as any)}
                disabled={disabled || isSubmitting || isLoading}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Contenu */}
        <CardContent className="p-6">
          <form ref={formRef} onSubmit={handleSubmit} noValidate>
            {/* Erreur globale */}
            {hasError && error && (
              <div className="mb-4 flex items-start gap-2 rounded-lg bg-red-50 dark:bg-red-900/20 p-3 text-sm text-red-600 dark:text-red-400">
                <ExclamationCircleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {/* Succès */}
            {success && (
              <div className="mb-4 flex items-start gap-2 rounded-lg bg-green-50 dark:bg-green-900/20 p-3 text-sm text-green-600 dark:text-green-400">
                <CheckCircleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />
                <span>{success}</span>
              </div>
            )}

            {/* Contenu de l'onglet */}
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
              >
                {activeTab === 'password' && renderPasswordTab()}
                {activeTab === 'twofactor' && renderTwoFactorTab()}
                {activeTab === 'sessions' && renderSessionsTab()}
                {activeTab === 'settings' && renderSettingsTab()}
              </motion.div>
            </AnimatePresence>

            {/* Actions */}
            <div className="mt-6 flex items-center justify-end gap-3 pt-6 border-t border-gray-200 dark:border-gray-700">
              <Button
                type="submit"
                variant="primary"
                onClick={handleSubmit}
                disabled={disabled || isSubmitting || isLoading}
                isLoading={isSubmitting || isLoading}
              >
                {isSubmitting ? 'Sauvegarde...' : 'Sauvegarder'}
              </Button>
            </div>
          </form>
        </CardContent>

        {/* Footer */}
        <CardFooter className="border-t border-gray-200 dark:border-gray-700 px-4 py-2 text-xs text-gray-400">
          <div className="flex items-center justify-between w-full">
            <span>
              Score: {formData.securityScore || 0}% • 
              2FA: {formData.twoFactor.enabled ? 'Activée' : 'Désactivée'}
            </span>
            <span>
              {formData.sessions.length} sessions • 
              {formData.devices.length} appareils
            </span>
          </div>
        </CardFooter>
      </Card>
    );
  }
);

SecuritySettingsForm.displayName = 'SecuritySettingsForm';

// ============================================================================
// EXPORTS
// ============================================================================

export default SecuritySettingsForm;

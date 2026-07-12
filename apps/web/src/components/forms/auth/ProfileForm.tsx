// apps/web/src/components/forms/auth/ProfileForm.tsx
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
  PhoneIcon,
  MapPinIcon,
  GlobeAltIcon,
  BriefcaseIcon,
  BuildingOfficeIcon,
  CalendarIcon,
  ClockIcon,
  CheckCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ArrowPathIcon,
  PencilIcon,
  TrashIcon,
  CameraIcon,
  EyeIcon,
  EyeSlashIcon,
  LockClosedIcon,
  ShieldCheckIcon,
  KeyIcon,
  DevicePhoneMobileIcon,
  AtSymbolIcon,
  UserGroupIcon,
  LinkIcon,
  DocumentTextIcon,
  PhotoIcon,
  XMarkIcon,
  PlusIcon,
  MinusIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
  CloudArrowUpIcon,
  CloudArrowDownIcon,
  DocumentDuplicateIcon,
  ShareIcon,
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
import { Textarea } from '@/components/common/Textarea';
import { Select } from '@/components/common/Select';
import { Switch } from '@/components/common/Switch';
import { Checkbox } from '@/components/common/Checkbox';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Separator } from '@/components/common/Separator';
import { Avatar, AvatarImage, AvatarFallback } from '@/components/common/Avatar';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/common/Tabs';
import { Progress } from '@/components/common/Progress';
import { Tooltip } from '@/components/common/Tooltip';
import { useToast } from '@/hooks/useToast';
import { useAuth } from '@/hooks/useAuth';
import { useTheme } from 'next-themes';

// ============================================================================
// TYPES
// ============================================================================

export type ProfileTab = 'personal' | 'contact' | 'professional' | 'security' | 'preferences' | 'social';

export interface ProfileFormData {
  // --- Informations personnelles ---
  firstName: string;
  lastName: string;
  displayName?: string;
  email: string;
  phone?: string;
  bio?: string;
  birthDate?: string;
  gender?: 'male' | 'female' | 'other' | 'prefer_not_to_say';

  // --- Contact ---
  address?: {
    street?: string;
    city?: string;
    state?: string;
    country?: string;
    postalCode?: string;
  };
  emergencyContact?: {
    name?: string;
    phone?: string;
    relationship?: string;
  };

  // --- Professionnel ---
  company?: string;
  position?: string;
  industry?: string;
  yearsOfExperience?: number;
  skills?: string[];
  certifications?: string[];
  languages?: string[];

  // --- Sécurité ---
  currentPassword?: string;
  newPassword?: string;
  confirmPassword?: string;
  twoFactorEnabled?: boolean;
  twoFactorMethod?: 'authenticator' | 'sms' | 'email';

  // --- Préférences ---
  language?: string;
  timezone?: string;
  theme?: 'light' | 'dark' | 'system';
  notifications?: {
    email: boolean;
    push: boolean;
    sms: boolean;
    marketing: boolean;
    tradingAlerts: boolean;
  };
  privacy?: {
    profileVisible: boolean;
    emailVisible: boolean;
    phoneVisible: boolean;
    showOnlineStatus: boolean;
    allowDataCollection: boolean;
  };

  // --- Social ---
  socialLinks?: {
    twitter?: string;
    linkedin?: string;
    github?: string;
    website?: string;
    instagram?: string;
    telegram?: string;
  };

  // --- Avatar ---
  avatar?: File | string | null;
  avatarUrl?: string;
}

export interface ProfileFormProps {
  // --- Contrôle ---
  /** Données initiales du profil */
  initialData?: Partial<ProfileFormData>;
  /** Callback de soumission */
  onSubmit?: (data: ProfileFormData) => void | Promise<void>;
  /** Callback de succès */
  onSuccess?: (data: ProfileFormData) => void;
  /** Callback d'erreur */
  onError?: (error: string) => void;
  /** Callback d'annulation */
  onCancel?: () => void;

  // --- Apparence ---
  /** Titre du formulaire */
  title?: string;
  /** Sous-titre */
  subtitle?: string;
  /** Classes additionnelles */
  className?: string;
  /** Variante de la carte */
  variant?: 'default' | 'glass' | 'solid' | 'outlined';
  /** Onglet initial */
  defaultTab?: ProfileTab;

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
  /** Permettre la suppression du compte */
  allowDeleteAccount?: boolean;
  /** URL de redirection après suppression */
  deleteRedirectUrl?: string;
  /** Format de date préféré */
  dateFormat?: string;
  /** Devise préférée */
  currency?: string;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ID */
  id?: string;

  // --- Avancé ---
  /** Callback de validation de l'email */
  validateEmail?: (email: string) => boolean | string;
  /** Callback de validation du téléphone */
  validatePhone?: (phone: string) => boolean | string;
  /** Callback de validation du mot de passe */
  validatePassword?: (password: string) => boolean | string;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const COUNTRIES = [
  { value: 'fr', label: 'France' },
  { value: 'be', label: 'Belgique' },
  { value: 'ch', label: 'Suisse' },
  { value: 'ca', label: 'Canada' },
  { value: 'us', label: 'États-Unis' },
  { value: 'uk', label: 'Royaume-Uni' },
  { value: 'de', label: 'Allemagne' },
  { value: 'es', label: 'Espagne' },
  { value: 'it', label: 'Italie' },
  { value: 'pt', label: 'Portugal' },
  { value: 'nl', label: 'Pays-Bas' },
  { value: 'lu', label: 'Luxembourg' },
];

const LANGUAGES = [
  { value: 'fr', label: 'Français' },
  { value: 'en', label: 'English' },
  { value: 'es', label: 'Español' },
  { value: 'de', label: 'Deutsch' },
  { value: 'it', label: 'Italiano' },
  { value: 'pt', label: 'Português' },
  { value: 'nl', label: 'Nederlands' },
  { value: 'zh', label: '中文' },
  { value: 'ja', label: '日本語' },
  { value: 'ko', label: '한국어' },
];

const TIMEZONES = [
  { value: 'Europe/Paris', label: 'Europe/Paris (UTC+1)' },
  { value: 'Europe/London', label: 'Europe/London (UTC+0)' },
  { value: 'America/New_York', label: 'America/New_York (UTC-5)' },
  { value: 'America/Chicago', label: 'America/Chicago (UTC-6)' },
  { value: 'America/Los_Angeles', label: 'America/Los_Angeles (UTC-8)' },
  { value: 'Asia/Tokyo', label: 'Asia/Tokyo (UTC+9)' },
  { value: 'Asia/Singapore', label: 'Asia/Singapore (UTC+8)' },
  { value: 'Australia/Sydney', label: 'Australia/Sydney (UTC+11)' },
];

const GENDER_OPTIONS = [
  { value: 'male', label: 'Homme' },
  { value: 'female', label: 'Femme' },
  { value: 'other', label: 'Autre' },
  { value: 'prefer_not_to_say', label: 'Je préfère ne pas dire' },
];

const SKILLS_SUGGESTIONS = [
  'Trading Algorithmique', 'Analyse Technique', 'Gestion des Risques',
  'Python', 'JavaScript', 'React', 'Next.js', 'TypeScript',
  'Machine Learning', 'Data Science', 'Finance', 'Economie',
  'Leadership', 'Communication', 'Stratégie', 'Innovation',
];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const ProfileForm = forwardRef<HTMLDivElement, ProfileFormProps>(
  (props, ref) => {
    const {
      // Contrôle
      initialData = {},
      onSubmit,
      onSuccess,
      onError,
      onCancel,

      // Apparence
      title = 'Mon Profil',
      subtitle = 'Gérez vos informations personnelles',
      className,
      variant = 'default',
      defaultTab = 'personal',

      // États
      isLoading = false,
      error = null,
      success = null,
      disabled = false,

      // Configuration
      allowDeleteAccount = true,
      deleteRedirectUrl = '/',
      dateFormat = 'DD/MM/YYYY',
      currency = 'EUR',

      // Accessibilité
      ariaLabel = 'Formulaire de profil',
      id,

      // Avancé
      validateEmail: externalValidateEmail,
      validatePhone: externalValidatePhone,
      validatePassword: externalValidatePassword,
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const formRef = useRef<HTMLFormElement>(null);
    const avatarInputRef = useRef<HTMLInputElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // ========================================================================
    // HOOKS
    // ========================================================================

    const { toast } = useToast();
    const { user, updateProfile, updatePassword, deleteAccount } = useAuth();
    const { theme, setTheme } = useTheme();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [activeTab, setActiveTab] = useState<ProfileTab>(defaultTab);
    const [formData, setFormData] = useState<ProfileFormData>({
      firstName: '',
      lastName: '',
      displayName: '',
      email: '',
      phone: '',
      bio: '',
      birthDate: '',
      gender: 'prefer_not_to_say',
      address: {},
      emergencyContact: {},
      company: '',
      position: '',
      industry: '',
      yearsOfExperience: 0,
      skills: [],
      certifications: [],
      languages: ['fr'],
      currentPassword: '',
      newPassword: '',
      confirmPassword: '',
      twoFactorEnabled: false,
      twoFactorMethod: 'authenticator',
      language: 'fr',
      timezone: 'Europe/Paris',
      theme: 'system',
      notifications: {
        email: true,
        push: true,
        sms: false,
        marketing: false,
        tradingAlerts: true,
      },
      privacy: {
        profileVisible: true,
        emailVisible: false,
        phoneVisible: false,
        showOnlineStatus: true,
        allowDataCollection: true,
      },
      socialLinks: {},
      avatar: null,
      avatarUrl: '',
      ...initialData,
    });

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [showPassword, setShowPassword] = useState(false);
    const [showConfirmPassword, setShowConfirmPassword] = useState(false);
    const [showCurrentPassword, setShowCurrentPassword] = useState(false);
    const [passwordStrength, setPasswordStrength] = useState(0);
    const [avatarPreview, setAvatarPreview] = useState<string | null>(formData.avatarUrl || null);
    const [isDeleting, setIsDeleting] = useState(false);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
    const [deleteConfirmText, setDeleteConfirmText] = useState('');
    const [skillInput, setSkillInput] = useState('');
    const [skillSuggestions, setSkillSuggestions] = useState<string[]>([]);
    const [showSkillSuggestions, setShowSkillSuggestions] = useState(false);

    // ========================================================================
    // USER DATA
    // ========================================================================

    useEffect(() => {
      if (user) {
        setFormData((prev) => ({
          ...prev,
          firstName: user.firstName || prev.firstName,
          lastName: user.lastName || prev.lastName,
          email: user.email || prev.email,
          displayName: user.displayName || prev.displayName,
          phone: user.phone || prev.phone,
          avatarUrl: user.avatar || prev.avatarUrl,
          ...user.profile,
        }));
        if (user.avatar) {
          setAvatarPreview(user.avatar);
        }
      }
    }, [user]);

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

    const validatePhone = useCallback((phone: string): boolean | string => {
      if (externalValidatePhone) {
        return externalValidatePhone(phone);
      }
      if (!phone) return true;
      const phoneRegex = /^[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}$/;
      if (!phoneRegex.test(phone)) return 'Veuillez entrer un numéro de téléphone valide';
      return true;
    }, [externalValidatePhone]);

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

    const handleFieldChange = useCallback(<K extends keyof ProfileFormData>(
      field: K,
      value: ProfileFormData[K]
    ) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
      setFormErrors((prev) => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });

      if (field === 'newPassword' && typeof value === 'string') {
        setPasswordStrength(calculatePasswordStrength(value));
      }

      if (field === 'newPassword' || field === 'confirmPassword') {
        const password = field === 'newPassword' ? value : formData.newPassword;
        const confirm = field === 'confirmPassword' ? value : formData.confirmPassword;
        if (password && confirm && password !== confirm) {
          setFormErrors((prev) => ({ ...prev, confirmPassword: 'Les mots de passe ne correspondent pas' }));
        } else if (password && confirm) {
          setFormErrors((prev) => {
            const newErrors = { ...prev };
            delete newErrors.confirmPassword;
            return newErrors;
          });
        }
      }
    }, [formData, calculatePasswordStrength]);

    const handleNestedFieldChange = useCallback((
      parent: 'address' | 'emergencyContact' | 'notifications' | 'privacy' | 'socialLinks',
      field: string,
      value: any
    ) => {
      setFormData((prev) => ({
        ...prev,
        [parent]: {
          ...prev[parent],
          [field]: value,
        },
      }));
    }, []);

    // ========================================================================
    // AVATAR
    // ========================================================================

    const handleAvatarChange = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      // Vérifier la taille (max 5MB)
      if (file.size > 5 * 1024 * 1024) {
        toast({
          title: 'Fichier trop volumineux',
          description: 'L\'avatar ne doit pas dépasser 5MB',
          variant: 'destructive',
        });
        return;
      }

      // Vérifier le type
      if (!file.type.startsWith('image/')) {
        toast({
          title: 'Format invalide',
          description: 'Veuillez sélectionner une image',
          variant: 'destructive',
        });
        return;
      }

      const reader = new FileReader();
      reader.onloadend = () => {
        setAvatarPreview(reader.result as string);
        handleFieldChange('avatar', file);
        handleFieldChange('avatarUrl', reader.result as string);
      };
      reader.readAsDataURL(file);
    }, [handleFieldChange, toast]);

    const handleRemoveAvatar = useCallback(() => {
      setAvatarPreview(null);
      handleFieldChange('avatar', null);
      handleFieldChange('avatarUrl', '');
      if (avatarInputRef.current) {
        avatarInputRef.current.value = '';
      }
    }, [handleFieldChange]);

    // ========================================================================
    // SKILLS
    // ========================================================================

    const handleAddSkill = useCallback((skill: string) => {
      const trimmed = skill.trim();
      if (!trimmed) return;
      if (formData.skills?.includes(trimmed)) {
        toast({
          title: 'Compétence déjà ajoutée',
          description: `"${trimmed}" est déjà dans votre liste`,
          variant: 'default',
        });
        return;
      }
      handleFieldChange('skills', [...(formData.skills || []), trimmed]);
      setSkillInput('');
      setShowSkillSuggestions(false);
    }, [formData.skills, handleFieldChange, toast]);

    const handleRemoveSkill = useCallback((skill: string) => {
      handleFieldChange('skills', (formData.skills || []).filter((s) => s !== skill));
    }, [formData.skills, handleFieldChange]);

    const handleSkillInputChange = useCallback((value: string) => {
      setSkillInput(value);
      if (value.length > 0) {
        const filtered = SKILLS_SUGGESTIONS.filter((s) =>
          s.toLowerCase().includes(value.toLowerCase()) &&
          !formData.skills?.includes(s)
        );
        setSkillSuggestions(filtered.slice(0, 5));
        setShowSkillSuggestions(true);
      } else {
        setSkillSuggestions([]);
        setShowSkillSuggestions(false);
      }
    }, [formData.skills]);

    // ========================================================================
    // VALIDATION DU FORMULAIRE
    // ========================================================================

    const validateTab = useCallback((tab: ProfileTab): boolean => {
      const errors: Record<string, string> = {};
      let isValid = true;

      if (tab === 'personal') {
        const emailResult = validateEmail(formData.email);
        if (typeof emailResult === 'string') {
          errors.email = emailResult;
          isValid = false;
        }
        if (formData.phone) {
          const phoneResult = validatePhone(formData.phone);
          if (typeof phoneResult === 'string') {
            errors.phone = phoneResult;
            isValid = false;
          }
        }
      }

      if (tab === 'security') {
        if (formData.newPassword) {
          const passwordResult = validatePassword(formData.newPassword);
          if (typeof passwordResult === 'string') {
            errors.newPassword = passwordResult;
            isValid = false;
          }
          if (formData.newPassword !== formData.confirmPassword) {
            errors.confirmPassword = 'Les mots de passe ne correspondent pas';
            isValid = false;
          }
        }
      }

      setFormErrors(errors);
      return isValid;
    }, [formData, validateEmail, validatePhone, validatePassword]);

    // ========================================================================
    // SOUMISSION
    // ========================================================================

    const handleSubmit = useCallback(async (e: React.FormEvent) => {
      e.preventDefault();

      if (isSubmitting || isLoading || disabled) return;

      // Valider l'onglet actif
      if (!validateTab(activeTab)) {
        toast({
          title: 'Erreur de validation',
          description: 'Veuillez corriger les erreurs du formulaire',
          variant: 'destructive',
        });
        return;
      }

      setIsSubmitting(true);

      try {
        // Préparer les données
        const submitData = { ...formData };

        // Gérer le changement de mot de passe
        if (submitData.newPassword && submitData.currentPassword) {
          await updatePassword({
            currentPassword: submitData.currentPassword,
            newPassword: submitData.newPassword,
          });
          // Ne pas envoyer les mots de passe au profil
          delete submitData.currentPassword;
          delete submitData.newPassword;
          delete submitData.confirmPassword;
        } else {
          delete submitData.currentPassword;
          delete submitData.newPassword;
          delete submitData.confirmPassword;
        }

        // Supprimer l'avatar File (ne peut pas être sérialisé)
        if (submitData.avatar instanceof File) {
          // L'avatar est géré séparément
          delete submitData.avatar;
        }

        // Mettre à jour le profil
        await updateProfile(submitData);

        if (onSubmit) {
          await onSubmit(submitData);
        }

        if (onSuccess) {
          onSuccess(submitData);
        }

        toast({
          title: 'Profil mis à jour',
          description: 'Vos informations ont été enregistrées avec succès',
          variant: 'success',
        });

        if (debug) {
          console.log('Profil mis à jour:', submitData);
        }

      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Erreur lors de la mise à jour du profil';
        setFormErrors((prev) => ({ ...prev, _form: errorMessage }));
        if (onError) onError(errorMessage);
        toast({
          title: 'Erreur',
          description: errorMessage,
          variant: 'destructive',
        });
        if (debug) console.error('Erreur de mise à jour:', err);
      } finally {
        setIsSubmitting(false);
      }
    }, [
      isSubmitting,
      isLoading,
      disabled,
      activeTab,
      validateTab,
      formData,
      updateProfile,
      updatePassword,
      onSubmit,
      onSuccess,
      onError,
      toast,
      debug,
    ]);

    // ========================================================================
    // SUPPRESSION DU COMPTE
    // ========================================================================

    const handleDeleteAccount = useCallback(async () => {
      if (!allowDeleteAccount) return;
      if (deleteConfirmText !== 'SUPPRIMER') {
        toast({
          title: 'Confirmation incorrecte',
          description: 'Veuillez taper "SUPPRIMER" pour confirmer',
          variant: 'destructive',
        });
        return;
      }

      setIsDeleting(true);
      try {
        await deleteAccount();
        toast({
          title: 'Compte supprimé',
          description: 'Votre compte a été supprimé avec succès',
          variant: 'success',
        });
        if (deleteRedirectUrl) {
          window.location.href = deleteRedirectUrl;
        }
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Erreur lors de la suppression';
        toast({
          title: 'Erreur',
          description: errorMessage,
          variant: 'destructive',
        });
      } finally {
        setIsDeleting(false);
        setShowDeleteConfirm(false);
      }
    }, [allowDeleteAccount, deleteConfirmText, deleteRedirectUrl, deleteAccount, toast]);

    // ========================================================================
    // RENDU DES ONGLETS
    // ========================================================================

    const renderPersonalTab = () => (
      <div className="space-y-4">
        {/* Avatar */}
        <div className="flex items-center gap-6">
          <div className="relative">
            <Avatar className="h-24 w-24 border-2 border-gray-200 dark:border-gray-700">
              <AvatarImage src={avatarPreview || formData.avatarUrl || undefined} />
              <AvatarFallback className="text-2xl">
                {formData.firstName?.[0] || formData.email?.[0] || 'U'}
              </AvatarFallback>
            </Avatar>
            <button
              type="button"
              className="absolute -bottom-1 -right-1 rounded-full bg-brand-500 p-1.5 text-white hover:bg-brand-600 transition-colors"
              onClick={() => avatarInputRef.current?.click()}
            >
              <CameraIcon className="h-4 w-4" />
            </button>
            <input
              ref={avatarInputRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={handleAvatarChange}
            />
          </div>
          <div className="space-y-1">
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Photo de profil
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              JPG, PNG ou GIF • Max 5MB
            </p>
            <div className="flex gap-2">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => avatarInputRef.current?.click()}
              >
                Changer
              </Button>
              {avatarPreview && (
                <Button
                  type="button"
                  variant="ghost"
                  size="sm"
                  onClick={handleRemoveAvatar}
                >
                  <TrashIcon className="h-4 w-4" />
                </Button>
              )}
            </div>
          </div>
        </div>

        <Separator />

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
              disabled={disabled || isSubmitting || isLoading}
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
              disabled={disabled || isSubmitting || isLoading}
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
            disabled={disabled || isSubmitting || isLoading}
          />
          <p className="text-xs text-gray-500 dark:text-gray-400">
            Comment votre nom apparaîtra sur la plateforme
          </p>
        </div>

        <div className="space-y-2">
          <label htmlFor="email" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Email <span className="text-red-500">*</span>
          </label>
          <Input
            id="email"
            type="email"
            placeholder="jean@email.com"
            value={formData.email}
            onChange={(e) => handleFieldChange('email', e.target.value)}
            error={formErrors.email}
            disabled={disabled || isSubmitting || isLoading}
            prefix={<EnvelopeIcon className="h-4 w-4 text-gray-400" />}
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="phone" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Téléphone
          </label>
          <Input
            id="phone"
            type="tel"
            placeholder="+33 6 12 34 56 78"
            value={formData.phone || ''}
            onChange={(e) => handleFieldChange('phone', e.target.value)}
            error={formErrors.phone}
            disabled={disabled || isSubmitting || isLoading}
            prefix={<PhoneIcon className="h-4 w-4 text-gray-400" />}
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="bio" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Bio
          </label>
          <Textarea
            id="bio"
            placeholder="Parlez-nous de vous..."
            value={formData.bio || ''}
            onChange={(e) => handleFieldChange('bio', e.target.value)}
            rows={3}
            disabled={disabled || isSubmitting || isLoading}
          />
          <p className="text-xs text-gray-500 dark:text-gray-400">
            {formData.bio?.length || 0} / 500 caractères
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label htmlFor="birthDate" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Date de naissance
            </label>
            <Input
              id="birthDate"
              type="date"
              value={formData.birthDate || ''}
              onChange={(e) => handleFieldChange('birthDate', e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="gender" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Genre
            </label>
            <Select
              id="gender"
              options={GENDER_OPTIONS}
              value={formData.gender || 'prefer_not_to_say'}
              onChange={(value) => handleFieldChange('gender', value as any)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>
      </div>
    );

    const renderContactTab = () => (
      <div className="space-y-4">
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Adresse
        </h3>

        <div className="space-y-2">
          <label htmlFor="street" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Rue
          </label>
          <Input
            id="street"
            placeholder="123 Rue de la Paix"
            value={formData.address?.street || ''}
            onChange={(e) => handleNestedFieldChange('address', 'street', e.target.value)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label htmlFor="city" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Ville
            </label>
            <Input
              id="city"
              placeholder="Paris"
              value={formData.address?.city || ''}
              onChange={(e) => handleNestedFieldChange('address', 'city', e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="state" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Région / État
            </label>
            <Input
              id="state"
              placeholder="Île-de-France"
              value={formData.address?.state || ''}
              onChange={(e) => handleNestedFieldChange('address', 'state', e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label htmlFor="country" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Pays
            </label>
            <Select
              id="country"
              options={COUNTRIES}
              value={formData.address?.country || 'fr'}
              onChange={(value) => handleNestedFieldChange('address', 'country', value)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="postalCode" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Code postal
            </label>
            <Input
              id="postalCode"
              placeholder="75001"
              value={formData.address?.postalCode || ''}
              onChange={(e) => handleNestedFieldChange('address', 'postalCode', e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <Separator />

        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Contact d'urgence
        </h3>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label htmlFor="emergencyName" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Nom
            </label>
            <Input
              id="emergencyName"
              placeholder="Marie Dupont"
              value={formData.emergencyContact?.name || ''}
              onChange={(e) => handleNestedFieldChange('emergencyContact', 'name', e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="emergencyPhone" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Téléphone
            </label>
            <Input
              id="emergencyPhone"
              placeholder="+33 6 12 34 56 78"
              value={formData.emergencyContact?.phone || ''}
              onChange={(e) => handleNestedFieldChange('emergencyContact', 'phone', e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <div className="space-y-2">
          <label htmlFor="emergencyRelationship" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Relation
          </label>
          <Input
            id="emergencyRelationship"
            placeholder="Conjoint(e)"
            value={formData.emergencyContact?.relationship || ''}
            onChange={(e) => handleNestedFieldChange('emergencyContact', 'relationship', e.target.value)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>
      </div>
    );

    const renderProfessionalTab = () => (
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label htmlFor="company" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Entreprise
            </label>
            <Input
              id="company"
              placeholder="Nexus Trading IA"
              value={formData.company || ''}
              onChange={(e) => handleFieldChange('company', e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
              prefix={<BuildingOfficeIcon className="h-4 w-4 text-gray-400" />}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="position" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Poste
            </label>
            <Input
              id="position"
              placeholder="Développeur Full Stack"
              value={formData.position || ''}
              onChange={(e) => handleFieldChange('position', e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
              prefix={<BriefcaseIcon className="h-4 w-4 text-gray-400" />}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label htmlFor="industry" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Industrie
            </label>
            <Input
              id="industry"
              placeholder="FinTech"
              value={formData.industry || ''}
              onChange={(e) => handleFieldChange('industry', e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label htmlFor="yearsOfExperience" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Années d'expérience
            </label>
            <Input
              id="yearsOfExperience"
              type="number"
              min={0}
              max={50}
              placeholder="5"
              value={formData.yearsOfExperience || ''}
              onChange={(e) => handleFieldChange('yearsOfExperience', parseInt(e.target.value) || 0)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Compétences
          </label>
          <div className="flex flex-wrap gap-2">
            {formData.skills?.map((skill) => (
              <Badge key={skill} variant="primary" className="flex items-center gap-1">
                {skill}
                <button
                  type="button"
                  onClick={() => handleRemoveSkill(skill)}
                  className="ml-1 rounded-full hover:bg-brand-600/20 p-0.5"
                >
                  <XMarkIcon className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
          <div className="relative">
            <Input
              placeholder="Ajouter une compétence..."
              value={skillInput}
              onChange={(e) => handleSkillInputChange(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  e.preventDefault();
                  handleAddSkill(skillInput);
                }
              }}
              suffix={
                <button
                  type="button"
                  onClick={() => handleAddSkill(skillInput)}
                  className="text-brand-600 hover:text-brand-700"
                >
                  <PlusIcon className="h-4 w-4" />
                </button>
              }
              disabled={disabled || isSubmitting || isLoading}
            />
            {showSkillSuggestions && skillSuggestions.length > 0 && (
              <div className="absolute z-10 mt-1 w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-lg">
                {skillSuggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    type="button"
                    className="w-full px-3 py-2 text-left text-sm hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                    onClick={() => handleAddSkill(suggestion)}
                  >
                    {suggestion}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Langues parlées
          </label>
          <div className="flex flex-wrap gap-2">
            {formData.languages?.map((lang) => (
              <Badge key={lang} variant="outline" className="flex items-center gap-1">
                {LANGUAGES.find((l) => l.value === lang)?.label || lang}
                <button
                  type="button"
                  onClick={() => {
                    handleFieldChange(
                      'languages',
                      (formData.languages || []).filter((l) => l !== lang)
                    );
                  }}
                  className="ml-1 rounded-full hover:bg-gray-200 dark:hover:bg-gray-700 p-0.5"
                >
                  <XMarkIcon className="h-3 w-3" />
                </button>
              </Badge>
            ))}
          </div>
          <Select
            options={LANGUAGES.filter((l) => !formData.languages?.includes(l.value))}
            value=""
            onChange={(value) => {
              if (value) {
                handleFieldChange('languages', [...(formData.languages || []), value]);
              }
            }}
            placeholder="Ajouter une langue..."
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>
      </div>
    );

    const renderSecurityTab = () => (
      <div className="space-y-4">
        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Changer le mot de passe
        </h3>

        <div className="space-y-2">
          <label htmlFor="currentPassword" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Mot de passe actuel
          </label>
          <Input
            id="currentPassword"
            type={showCurrentPassword ? 'text' : 'password'}
            placeholder="Votre mot de passe actuel"
            value={formData.currentPassword || ''}
            onChange={(e) => handleFieldChange('currentPassword', e.target.value)}
            error={formErrors.currentPassword}
            disabled={disabled || isSubmitting || isLoading}
            suffix={
              <button
                type="button"
                onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                {showCurrentPassword ? (
                  <EyeSlashIcon className="h-4 w-4" />
                ) : (
                  <EyeIcon className="h-4 w-4" />
                )}
              </button>
            }
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="newPassword" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Nouveau mot de passe
          </label>
          <Input
            id="newPassword"
            type={showPassword ? 'text' : 'password'}
            placeholder="Nouveau mot de passe"
            value={formData.newPassword || ''}
            onChange={(e) => handleFieldChange('newPassword', e.target.value)}
            error={formErrors.newPassword}
            disabled={disabled || isSubmitting || isLoading}
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
            Confirmer le mot de passe
          </label>
          <Input
            id="confirmPassword"
            type={showConfirmPassword ? 'text' : 'password'}
            placeholder="Confirmer le nouveau mot de passe"
            value={formData.confirmPassword || ''}
            onChange={(e) => handleFieldChange('confirmPassword', e.target.value)}
            error={formErrors.confirmPassword}
            disabled={disabled || isSubmitting || isLoading}
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

        <Separator />

        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Authentification à deux facteurs (2FA)
        </h3>

        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm text-gray-700 dark:text-gray-300">Activer la 2FA</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Ajoute une couche de sécurité supplémentaire
            </p>
          </div>
          <Switch
            checked={formData.twoFactorEnabled || false}
            onCheckedChange={(checked) => handleFieldChange('twoFactorEnabled', checked)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        {formData.twoFactorEnabled && (
          <div className="space-y-2">
            <label htmlFor="twoFactorMethod" className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Méthode 2FA
            </label>
            <Select
              id="twoFactorMethod"
              options={[
                { value: 'authenticator', label: '🔐 Application Authenticator' },
                { value: 'sms', label: '📱 SMS' },
                { value: 'email', label: '📧 Email' },
              ]}
              value={formData.twoFactorMethod || 'authenticator'}
              onChange={(value) => handleFieldChange('twoFactorMethod', value as any)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        )}

        <Separator />

        <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-4">
          <div className="flex items-start gap-3">
            <ShieldCheckIcon className="h-5 w-5 text-gray-400 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Sessions actives
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Vous êtes connecté sur 2 appareils
              </p>
              <button
                type="button"
                className="mt-2 text-sm text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
              >
                Gérer les sessions
              </button>
            </div>
          </div>
        </div>
      </div>
    );

    const renderPreferencesTab = () => (
      <div className="space-y-4">
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
              disabled={disabled || isSubmitting || isLoading}
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
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Thème
          </label>
          <div className="flex gap-2">
            {['light', 'dark', 'system'].map((themeOption) => (
              <button
                key={themeOption}
                type="button"
                className={cn(
                  'flex-1 rounded-lg border-2 p-3 text-center transition-all',
                  formData.theme === themeOption
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
                onClick={() => handleFieldChange('theme', themeOption as any)}
                disabled={disabled || isSubmitting || isLoading}
              >
                {themeOption === 'light' && '☀️ Clair'}
                {themeOption === 'dark' && '🌙 Sombre'}
                {themeOption === 'system' && '🔄 Système'}
              </button>
            ))}
          </div>
        </div>

        <Separator />

        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Notifications
        </h3>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-700 dark:text-gray-300">Notifications par email</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Recevoir des emails de la plateforme</p>
            </div>
            <Switch
              checked={formData.notifications?.email || false}
              onCheckedChange={(checked) => handleNestedFieldChange('notifications', 'email', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-700 dark:text-gray-300">Notifications push</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Notifications sur votre navigateur</p>
            </div>
            <Switch
              checked={formData.notifications?.push || false}
              onCheckedChange={(checked) => handleNestedFieldChange('notifications', 'push', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-700 dark:text-gray-300">Alertes de trading</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Notifications pour vos trades</p>
            </div>
            <Switch
              checked={formData.notifications?.tradingAlerts || false}
              onCheckedChange={(checked) => handleNestedFieldChange('notifications', 'tradingAlerts', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-700 dark:text-gray-300">Marketing</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Offres et actualités de Nexus</p>
            </div>
            <Switch
              checked={formData.notifications?.marketing || false}
              onCheckedChange={(checked) => handleNestedFieldChange('notifications', 'marketing', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <Separator />

        <h3 className="text-sm font-medium text-gray-700 dark:text-gray-300">
          Vie privée
        </h3>

        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-700 dark:text-gray-300">Profil visible</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Votre profil est visible par les autres utilisateurs</p>
            </div>
            <Switch
              checked={formData.privacy?.profileVisible || false}
              onCheckedChange={(checked) => handleNestedFieldChange('privacy', 'profileVisible', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-700 dark:text-gray-300">Email visible</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Votre email est visible par les autres</p>
            </div>
            <Switch
              checked={formData.privacy?.emailVisible || false}
              onCheckedChange={(checked) => handleNestedFieldChange('privacy', 'emailVisible', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm text-gray-700 dark:text-gray-300">Statut en ligne</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Afficher votre statut en ligne</p>
            </div>
            <Switch
              checked={formData.privacy?.showOnlineStatus || false}
              onCheckedChange={(checked) => handleNestedFieldChange('privacy', 'showOnlineStatus', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>
      </div>
    );

    const renderSocialTab = () => (
      <div className="space-y-4">
        <div className="space-y-2">
          <label htmlFor="website" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Site web
          </label>
          <Input
            id="website"
            placeholder="https://monsite.com"
            value={formData.socialLinks?.website || ''}
            onChange={(e) => handleNestedFieldChange('socialLinks', 'website', e.target.value)}
            disabled={disabled || isSubmitting || isLoading}
            prefix={<LinkIcon className="h-4 w-4 text-gray-400" />}
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="twitter" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Twitter / X
          </label>
          <Input
            id="twitter"
            placeholder="@votre_compte"
            value={formData.socialLinks?.twitter || ''}
            onChange={(e) => handleNestedFieldChange('socialLinks', 'twitter', e.target.value)}
            disabled={disabled || isSubmitting || isLoading}
            prefix={<span className="text-gray-400">@</span>}
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="linkedin" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            LinkedIn
          </label>
          <Input
            id="linkedin"
            placeholder="https://linkedin.com/in/votre-profil"
            value={formData.socialLinks?.linkedin || ''}
            onChange={(e) => handleNestedFieldChange('socialLinks', 'linkedin', e.target.value)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="github" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            GitHub
          </label>
          <Input
            id="github"
            placeholder="https://github.com/votre-compte"
            value={formData.socialLinks?.github || ''}
            onChange={(e) => handleNestedFieldChange('socialLinks', 'github', e.target.value)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="telegram" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Telegram
          </label>
          <Input
            id="telegram"
            placeholder="@votre_compte"
            value={formData.socialLinks?.telegram || ''}
            onChange={(e) => handleNestedFieldChange('socialLinks', 'telegram', e.target.value)}
            disabled={disabled || isSubmitting || isLoading}
            prefix={<span className="text-gray-400">@</span>}
          />
        </div>

        <div className="space-y-2">
          <label htmlFor="instagram" className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Instagram
          </label>
          <Input
            id="instagram"
            placeholder="@votre_compte"
            value={formData.socialLinks?.instagram || ''}
            onChange={(e) => handleNestedFieldChange('socialLinks', 'instagram', e.target.value)}
            disabled={disabled || isSubmitting || isLoading}
            prefix={<span className="text-gray-400">@</span>}
          />
        </div>
      </div>
    );

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const tabs = [
      { id: 'personal', label: '👤 Personnel', component: renderPersonalTab },
      { id: 'contact', label: '📞 Contact', component: renderContactTab },
      { id: 'professional', label: '💼 Professionnel', component: renderProfessionalTab },
      { id: 'security', label: '🔒 Sécurité', component: renderSecurityTab },
      { id: 'preferences', label: '⚙️ Préférences', component: renderPreferencesTab },
      { id: 'social', label: '🔗 Social', component: renderSocialTab },
    ];

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
              <CardTitle>{title}</CardTitle>
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
            {tabs.map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={cn(
                  'px-4 py-2.5 text-sm font-medium transition-colors whitespace-nowrap border-b-2',
                  activeTab === tab.id
                    ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                )}
                onClick={() => setActiveTab(tab.id as ProfileTab)}
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
            {formErrors._form && (
              <div className="mb-4 flex items-start gap-2 rounded-lg bg-red-50 dark:bg-red-900/20 p-3 text-sm text-red-600 dark:text-red-400">
                <ExclamationTriangleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />
                <span>{formErrors._form}</span>
              </div>
            )}

            {/* Succès */}
            {success && (
              <div className="mb-4 flex items-start gap-2 rounded-lg bg-green-50 dark:bg-green-900/20 p-3 text-sm text-green-600 dark:text-green-400">
                <CheckCircleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />
                <span>{success}</span>
              </div>
            )}

            {/* Onglet actif */}
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
              >
                {tabs.find((t) => t.id === activeTab)?.component()}
              </motion.div>
            </AnimatePresence>

            {/* Actions */}
            <div className="mt-6 flex flex-wrap items-center justify-between gap-3 pt-6 border-t border-gray-200 dark:border-gray-700">
              <div className="flex items-center gap-2">
                {allowDeleteAccount && (
                  <button
                    type="button"
                    className="text-sm text-red-600 hover:text-red-700 dark:text-red-400 dark:hover:text-red-300 transition-colors"
                    onClick={() => setShowDeleteConfirm(true)}
                    disabled={disabled || isSubmitting || isLoading}
                  >
                    <TrashIcon className="inline h-4 w-4 mr-1" />
                    Supprimer le compte
                  </button>
                )}
              </div>
              <div className="flex gap-2">
                <Button
                  type="submit"
                  variant="primary"
                  disabled={disabled || isSubmitting || isLoading}
                  isLoading={isSubmitting || isLoading}
                >
                  {isSubmitting ? 'Enregistrement...' : 'Enregistrer les modifications'}
                </Button>
              </div>
            </div>
          </form>
        </CardContent>

        {/* Modal de confirmation de suppression */}
        {showDeleteConfirm && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
            <div className="w-full max-w-md rounded-xl bg-white dark:bg-gray-900 p-6 shadow-xl">
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full bg-red-100 dark:bg-red-900/30">
                  <ExclamationTriangleIcon className="h-6 w-6 text-red-600 dark:text-red-400" />
                </div>
                <div className="flex-1">
                  <h3 className="text-lg font-semibold text-gray-900 dark:text-white">
                    Supprimer le compte
                  </h3>
                  <p className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                    Cette action est irréversible. Toutes vos données seront supprimées.
                  </p>
                  <div className="mt-4">
                    <label htmlFor="deleteConfirm" className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Tapez <span className="font-bold">SUPPRIMER</span> pour confirmer
                    </label>
                    <Input
                      id="deleteConfirm"
                      placeholder="SUPPRIMER"
                      value={deleteConfirmText}
                      onChange={(e) => setDeleteConfirmText(e.target.value)}
                      className="mt-1"
                      disabled={isDeleting}
                    />
                  </div>
                </div>
              </div>
              <div className="mt-6 flex justify-end gap-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => {
                    setShowDeleteConfirm(false);
                    setDeleteConfirmText('');
                  }}
                  disabled={isDeleting}
                >
                  Annuler
                </Button>
                <Button
                  type="button"
                  variant="danger"
                  onClick={handleDeleteAccount}
                  isLoading={isDeleting}
                  disabled={deleteConfirmText !== 'SUPPRIMER' || isDeleting}
                >
                  Supprimer
                </Button>
              </div>
            </div>
          </div>
        )}
      </Card>
    );
  }
);

ProfileForm.displayName = 'ProfileForm';

export default ProfileForm;

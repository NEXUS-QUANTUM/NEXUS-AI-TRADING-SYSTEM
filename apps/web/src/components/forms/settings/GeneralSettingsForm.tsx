// apps/web/src/components/forms/settings/GeneralSettingsForm.tsx
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
  GlobeAltIcon,
  LanguageIcon,
  ClockIcon,
  UserIcon,
  EnvelopeIcon,
  BellIcon,
  ShieldCheckIcon,
  Cog6ToothIcon,
  AdjustmentsHorizontalIcon,
  CheckIcon,
  XMarkIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  EyeIcon,
  EyeSlashIcon,
  PencilIcon,
  TrashIcon,
  DocumentDuplicateIcon,
  ShareIcon,
  LinkIcon,
  BookmarkIcon,
  HeartIcon,
  StarIcon,
  FlagIcon,
  PrinterIcon,
  ClipboardIcon,
  PlusIcon,
  MinusIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  SunIcon,
  MoonIcon,
  ComputerDesktopIcon,
  SparklesIcon,
  RocketLaunchIcon,
  ShieldExclamationIcon,
  WifiIcon,
  WifiSlashIcon,
  ServerIcon,
  CloudIcon,
  DatabaseIcon,
  LockClosedIcon,
  LockOpenIcon,
  UserGroupIcon,
  BuildingOfficeIcon,
  PhoneIcon,
  MapPinIcon,
  CalendarIcon,
  DocumentTextIcon,
  ReceiptPercentIcon,
} from '@heroicons/react/24/outline';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Select } from '@/components/common/Select';
import { Switch } from '@/components/common/Switch';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/common/Tabs';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Separator } from '@/components/common/Separator';
import { Tooltip } from '@/components/common/Tooltip';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type Language = 'fr' | 'en' | 'es' | 'de' | 'it' | 'pt' | 'nl' | 'ja' | 'zh' | 'ko' | 'ru';
export type Timezone = string;
export type DateFormat = 'DD/MM/YYYY' | 'MM/DD/YYYY' | 'YYYY-MM-DD' | 'DD-MM-YYYY' | 'MM-DD-YYYY' | 'YYYY/MM/DD';
export type TimeFormat = '12h' | '24h';
export type WeekStart = 'monday' | 'sunday' | 'saturday';
export type Currency = 'EUR' | 'USD' | 'GBP' | 'CHF' | 'CAD' | 'JPY' | 'BTC' | 'ETH' | 'USDT';
export type NotificationLevel = 'all' | 'important' | 'none';

export interface GeneralSettingsData {
  /** Langue de l'interface */
  language: Language;
  /** Fuseau horaire */
  timezone: Timezone;
  /** Format de date */
  dateFormat: DateFormat;
  /** Format de l'heure */
  timeFormat: TimeFormat;
  /** Premier jour de la semaine */
  weekStart: WeekStart;
  /** Devise par défaut */
  currency: Currency;
  /** Nom de l'utilisateur */
  username: string;
  /** Email */
  email: string;
  /** Téléphone */
  phone?: string;
  /** Bio */
  bio?: string;
  /** Société */
  company?: string;
  /** Poste */
  position?: string;
  /** Site web */
  website?: string;
  /** Adresse */
  address?: string;
  /** Niveau de notification */
  notificationLevel: NotificationLevel;
  /** Activer les notifications par email */
  emailNotifications: boolean;
  /** Activer les notifications push */
  pushNotifications: boolean;
  /** Activer les notifications SMS */
  smsNotifications: boolean;
  /** Activer le mode sombre automatique */
  autoDarkMode: boolean;
  /** Activer les animations */
  animations: boolean;
  /** Activer les raccourcis clavier */
  keyboardShortcuts: boolean;
  /** Activer le mode hors ligne */
  offlineMode: boolean;
  /** Activer la compression des données */
  dataCompression: boolean;
  /** Activer le débogage */
  debugMode: boolean;
  /** Activer les analytics */
  analytics: boolean;
  /** Activer les cookies */
  cookies: boolean;
  /** Activer les mises à jour automatiques */
  autoUpdates: boolean;
  /** Version */
  version?: string;
  /** Dernière mise à jour */
  lastUpdate?: Date;
}

export interface GeneralSettingsFormProps {
  // --- Contrôle ---
  /** Données initiales */
  initialData?: Partial<GeneralSettingsData>;
  /** Callback de soumission */
  onSubmit?: (data: GeneralSettingsData) => void | Promise<void>;
  /** Callback de succès */
  onSuccess?: (data: GeneralSettingsData) => void;
  /** Callback d'erreur */
  onError?: (error: string) => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de changement */
  onChange?: (data: GeneralSettingsData) => void;

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

const LANGUAGES: { value: Language; label: string; flag: string }[] = [
  { value: 'fr', label: 'Français', flag: '🇫🇷' },
  { value: 'en', label: 'English', flag: '🇬🇧' },
  { value: 'es', label: 'Español', flag: '🇪🇸' },
  { value: 'de', label: 'Deutsch', flag: '🇩🇪' },
  { value: 'it', label: 'Italiano', flag: '🇮🇹' },
  { value: 'pt', label: 'Português', flag: '🇵🇹' },
  { value: 'nl', label: 'Nederlands', flag: '🇳🇱' },
  { value: 'ja', label: '日本語', flag: '🇯🇵' },
  { value: 'zh', label: '中文', flag: '🇨🇳' },
  { value: 'ko', label: '한국어', flag: '🇰🇷' },
  { value: 'ru', label: 'Русский', flag: '🇷🇺' },
];

const TIMEZONES = [
  { value: 'Europe/Paris', label: 'Europe/Paris (UTC+1)' },
  { value: 'Europe/London', label: 'Europe/London (UTC+0)' },
  { value: 'Europe/Berlin', label: 'Europe/Berlin (UTC+1)' },
  { value: 'Europe/Madrid', label: 'Europe/Madrid (UTC+1)' },
  { value: 'Europe/Rome', label: 'Europe/Rome (UTC+1)' },
  { value: 'America/New_York', label: 'America/New_York (UTC-5)' },
  { value: 'America/Chicago', label: 'America/Chicago (UTC-6)' },
  { value: 'America/Los_Angeles', label: 'America/Los_Angeles (UTC-8)' },
  { value: 'America/Toronto', label: 'America/Toronto (UTC-5)' },
  { value: 'Asia/Tokyo', label: 'Asia/Tokyo (UTC+9)' },
  { value: 'Asia/Singapore', label: 'Asia/Singapore (UTC+8)' },
  { value: 'Asia/Dubai', label: 'Asia/Dubai (UTC+4)' },
  { value: 'Australia/Sydney', label: 'Australia/Sydney (UTC+11)' },
  { value: 'Pacific/Auckland', label: 'Pacific/Auckland (UTC+12)' },
  { value: 'UTC', label: 'UTC' },
];

const DATE_FORMATS: { value: DateFormat; label: string; example: string }[] = [
  { value: 'DD/MM/YYYY', label: 'DD/MM/YYYY', example: '31/12/2024' },
  { value: 'MM/DD/YYYY', label: 'MM/DD/YYYY', example: '12/31/2024' },
  { value: 'YYYY-MM-DD', label: 'YYYY-MM-DD', example: '2024-12-31' },
  { value: 'DD-MM-YYYY', label: 'DD-MM-YYYY', example: '31-12-2024' },
  { value: 'MM-DD-YYYY', label: 'MM-DD-YYYY', example: '12-31-2024' },
  { value: 'YYYY/MM/DD', label: 'YYYY/MM/DD', example: '2024/12/31' },
];

const TIME_FORMATS: { value: TimeFormat; label: string; example: string }[] = [
  { value: '24h', label: '24h', example: '14:30' },
  { value: '12h', label: '12h', example: '2:30 PM' },
];

const WEEK_STARTS: { value: WeekStart; label: string }[] = [
  { value: 'monday', label: 'Lundi' },
  { value: 'sunday', label: 'Dimanche' },
  { value: 'saturday', label: 'Samedi' },
];

const CURRENCIES: { value: Currency; label: string; symbol: string }[] = [
  { value: 'EUR', label: 'Euro', symbol: '€' },
  { value: 'USD', label: 'Dollar US', symbol: '$' },
  { value: 'GBP', label: 'Livre Sterling', symbol: '£' },
  { value: 'CHF', label: 'Franc Suisse', symbol: 'Fr' },
  { value: 'CAD', label: 'Dollar Canadien', symbol: 'C$' },
  { value: 'JPY', label: 'Yen Japonais', symbol: '¥' },
  { value: 'BTC', label: 'Bitcoin', symbol: '₿' },
  { value: 'ETH', label: 'Ethereum', symbol: 'Ξ' },
  { value: 'USDT', label: 'Tether', symbol: '₮' },
];

const NOTIFICATION_LEVELS: { value: NotificationLevel; label: string; description: string }[] = [
  { value: 'all', label: 'Toutes', description: 'Recevoir toutes les notifications' },
  { value: 'important', label: 'Importantes', description: 'Recevoir uniquement les notifications importantes' },
  { value: 'none', label: 'Aucune', description: 'Ne recevoir aucune notification' },
];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const GeneralSettingsForm = forwardRef<HTMLDivElement, GeneralSettingsFormProps>(
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
      title = 'Paramètres généraux',
      subtitle = 'Configurez les préférences générales de l\'application',
      className,
      variant = 'default',

      // États
      isLoading = false,
      error = null,
      success = null,
      disabled = false,

      // Accessibilité
      ariaLabel = 'Paramètres généraux',
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

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [formData, setFormData] = useState<GeneralSettingsData>({
      language: 'fr',
      timezone: 'Europe/Paris',
      dateFormat: 'DD/MM/YYYY',
      timeFormat: '24h',
      weekStart: 'monday',
      currency: 'EUR',
      username: '',
      email: '',
      notificationLevel: 'all',
      emailNotifications: true,
      pushNotifications: true,
      smsNotifications: false,
      autoDarkMode: true,
      animations: true,
      keyboardShortcuts: true,
      offlineMode: false,
      dataCompression: true,
      debugMode: false,
      analytics: true,
      cookies: true,
      autoUpdates: true,
      ...initialData,
    });

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [activeTab, setActiveTab] = useState<'general' | 'preferences' | 'notifications'>('general');
    const [showPassword, setShowPassword] = useState(false);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validate = useCallback((): boolean => {
      const errors: Record<string, string> = {};

      if (!formData.username) {
        errors.username = 'Le nom d\'utilisateur est requis';
      }

      if (!formData.email) {
        errors.email = 'L\'email est requis';
      } else if (!/^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/.test(formData.email)) {
        errors.email = 'Email invalide';
      }

      setFormErrors(errors);
      return Object.keys(errors).length === 0;
    }, [formData]);

    // ========================================================================
    // GESTIONNAIRES DE CHAMPS
    // ========================================================================

    const handleFieldChange = useCallback(<K extends keyof GeneralSettingsData>(
      field: K,
      value: GeneralSettingsData[K]
    ) => {
      setFormData(prev => ({ ...prev, [field]: value }));
      setFormErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }, []);

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
          title: 'Paramètres sauvegardés',
          description: 'Les paramètres généraux ont été mis à jour',
          variant: 'success',
        });

        if (debug) {
          console.log('General settings saved:', formData);
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
    // RENDU DE L'ONGLET GENERAL
    // ========================================================================

    const renderGeneralTab = () => (
      <div className="space-y-6">
        {/* Langue et région */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Langue
            </label>
            <Select
              options={LANGUAGES.map(lang => ({
                value: lang.value,
                label: `${lang.flag} ${lang.label}`,
              }))}
              value={formData.language}
              onChange={(value) => handleFieldChange('language', value as Language)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Fuseau horaire
            </label>
            <Select
              options={TIMEZONES}
              value={formData.timezone}
              onChange={(value) => handleFieldChange('timezone', value)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Format de date
            </label>
            <Select
              options={DATE_FORMATS.map(df => ({
                value: df.value,
                label: `${df.label} (${df.example})`,
              }))}
              value={formData.dateFormat}
              onChange={(value) => handleFieldChange('dateFormat', value as DateFormat)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Format de l'heure
            </label>
            <Select
              options={TIME_FORMATS}
              value={formData.timeFormat}
              onChange={(value) => handleFieldChange('timeFormat', value as TimeFormat)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Premier jour de la semaine
            </label>
            <Select
              options={WEEK_STARTS}
              value={formData.weekStart}
              onChange={(value) => handleFieldChange('weekStart', value as WeekStart)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Devise par défaut
            </label>
            <Select
              options={CURRENCIES.map(c => ({
                value: c.value,
                label: `${c.symbol} ${c.label}`,
              }))}
              value={formData.currency}
              onChange={(value) => handleFieldChange('currency', value as Currency)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <Separator />

        {/* Informations utilisateur */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Nom d'utilisateur
            </label>
            <Input
              type="text"
              placeholder="johndoe"
              value={formData.username}
              onChange={(e) => handleFieldChange('username', e.target.value)}
              error={formErrors.username}
              disabled={disabled || isSubmitting || isLoading}
              prefix={<UserIcon className="h-4 w-4 text-gray-400" />}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Email
            </label>
            <Input
              type="email"
              placeholder="john@exemple.com"
              value={formData.email}
              onChange={(e) => handleFieldChange('email', e.target.value)}
              error={formErrors.email}
              disabled={disabled || isSubmitting || isLoading}
              prefix={<EnvelopeIcon className="h-4 w-4 text-gray-400" />}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Téléphone
            </label>
            <Input
              type="tel"
              placeholder="+33 6 12 34 56 78"
              value={formData.phone || ''}
              onChange={(e) => handleFieldChange('phone', e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
              prefix={<PhoneIcon className="h-4 w-4 text-gray-400" />}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Société
            </label>
            <Input
              type="text"
              placeholder="Nexus Trading IA"
              value={formData.company || ''}
              onChange={(e) => handleFieldChange('company', e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
              prefix={<BuildingOfficeIcon className="h-4 w-4 text-gray-400" />}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Poste
            </label>
            <Input
              type="text"
              placeholder="Développeur Full Stack"
              value={formData.position || ''}
              onChange={(e) => handleFieldChange('position', e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
              prefix={<Cog6ToothIcon className="h-4 w-4 text-gray-400" />}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Site web
            </label>
            <Input
              type="url"
              placeholder="https://mon-site.com"
              value={formData.website || ''}
              onChange={(e) => handleFieldChange('website', e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
              prefix={<GlobeAltIcon className="h-4 w-4 text-gray-400" />}
            />
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Bio
          </label>
          <textarea
            className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:focus:ring-brand-500/20"
            rows={3}
            placeholder="Parlez-nous de vous..."
            value={formData.bio || ''}
            onChange={(e) => handleFieldChange('bio', e.target.value)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Adresse
          </label>
          <textarea
            className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:focus:ring-brand-500/20"
            rows={2}
            placeholder="123 Rue de la Paix, 75001 Paris"
            value={formData.address || ''}
            onChange={(e) => handleFieldChange('address', e.target.value)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>
      </div>
    );

    // ========================================================================
    // RENDU DE L'ONGLET PREFERENCES
    // ========================================================================

    const renderPreferencesTab = () => (
      <div className="space-y-6">
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Mode sombre automatique
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Activer automatiquement le mode sombre selon l'heure
              </p>
            </div>
            <Switch
              checked={formData.autoDarkMode}
              onCheckedChange={(checked) => handleFieldChange('autoDarkMode', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Animations
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Activer les animations de l'interface
              </p>
            </div>
            <Switch
              checked={formData.animations}
              onCheckedChange={(checked) => handleFieldChange('animations', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Raccourcis clavier
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Activer les raccourcis clavier
              </p>
            </div>
            <Switch
              checked={formData.keyboardShortcuts}
              onCheckedChange={(checked) => handleFieldChange('keyboardShortcuts', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <Separator />

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Mode hors ligne
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Accéder aux données en mode hors ligne
              </p>
            </div>
            <Switch
              checked={formData.offlineMode}
              onCheckedChange={(checked) => handleFieldChange('offlineMode', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Compression des données
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Compresser les données pour économiser la bande passante
              </p>
            </div>
            <Switch
              checked={formData.dataCompression}
              onCheckedChange={(checked) => handleFieldChange('dataCompression', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <Separator />

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Mode débogage
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Afficher les informations de débogage
              </p>
            </div>
            <Switch
              checked={formData.debugMode}
              onCheckedChange={(checked) => handleFieldChange('debugMode', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Analytics
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Partager des données anonymes d'utilisation
              </p>
            </div>
            <Switch
              checked={formData.analytics}
              onCheckedChange={(checked) => handleFieldChange('analytics', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Cookies
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Autoriser l'utilisation des cookies
              </p>
            </div>
            <Switch
              checked={formData.cookies}
              onCheckedChange={(checked) => handleFieldChange('cookies', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Mises à jour automatiques
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Installer automatiquement les mises à jour
              </p>
            </div>
            <Switch
              checked={formData.autoUpdates}
              onCheckedChange={(checked) => handleFieldChange('autoUpdates', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <Separator />

        {/* Informations système */}
        <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-4 space-y-2">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">Informations système</h4>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <span className="text-gray-500 dark:text-gray-400">Version</span>
            <span className="text-gray-900 dark:text-white font-mono">
              {formData.version || '1.0.0'}
            </span>
            <span className="text-gray-500 dark:text-gray-400">Dernière mise à jour</span>
            <span className="text-gray-900 dark:text-white">
              {formData.lastUpdate ? formData.lastUpdate.toLocaleString() : 'Jamais'}
            </span>
          </div>
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="mt-2"
            onClick={() => {
              toast({
                title: 'Vérification des mises à jour',
                description: 'Recherche des mises à jour en cours...',
                duration: 3000,
              });
            }}
            disabled={disabled || isSubmitting || isLoading}
          >
            <ArrowPathIcon className="h-4 w-4 mr-2" />
            Vérifier les mises à jour
          </Button>
        </div>
      </div>
    );

    // ========================================================================
    // RENDU DE L'ONGLET NOTIFICATIONS
    // ========================================================================

    const renderNotificationsTab = () => (
      <div className="space-y-6">
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Niveau de notification
          </label>
          <Select
            options={NOTIFICATION_LEVELS.map(n => ({
              value: n.value,
              label: `${n.label} - ${n.description}`,
            }))}
            value={formData.notificationLevel}
            onChange={(value) => handleFieldChange('notificationLevel', value as NotificationLevel)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <Separator />

        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Notifications par email
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Recevoir les notifications par email
              </p>
            </div>
            <Switch
              checked={formData.emailNotifications}
              onCheckedChange={(checked) => handleFieldChange('emailNotifications', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Notifications push
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Recevoir les notifications push
              </p>
            </div>
            <Switch
              checked={formData.pushNotifications}
              onCheckedChange={(checked) => handleFieldChange('pushNotifications', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Notifications SMS
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Recevoir les notifications par SMS
              </p>
            </div>
            <Switch
              checked={formData.smsNotifications}
              onCheckedChange={(checked) => handleFieldChange('smsNotifications', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <Separator />

        {/* Types de notifications */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">Types de notifications</h4>
          <div className="space-y-2">
            <div className="flex items-center gap-3">
              <input type="checkbox" className="rounded border-gray-300 dark:border-gray-600" defaultChecked />
              <span className="text-sm">Alertes de trading</span>
            </div>
            <div className="flex items-center gap-3">
              <input type="checkbox" className="rounded border-gray-300 dark:border-gray-600" defaultChecked />
              <span className="text-sm">Mises à jour du système</span>
            </div>
            <div className="flex items-center gap-3">
              <input type="checkbox" className="rounded border-gray-300 dark:border-gray-600" defaultChecked />
              <span className="text-sm">Rapports de performance</span>
            </div>
            <div className="flex items-center gap-3">
              <input type="checkbox" className="rounded border-gray-300 dark:border-gray-600" />
              <span className="text-sm">Offres promotionnelles</span>
            </div>
            <div className="flex items-center gap-3">
              <input type="checkbox" className="rounded border-gray-300 dark:border-gray-600" />
              <span className="text-sm">Newsletter</span>
            </div>
          </div>
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
                <Badge variant="outline" size="sm" className="flex items-center gap-1">
                  <GlobeAltIcon className="h-3 w-3" />
                  {LANGUAGES.find(l => l.value === formData.language)?.label || 'Français'}
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
              { id: 'general', label: '👤 Général' },
              { id: 'preferences', label: '⚙️ Préférences' },
              { id: 'notifications', label: '🔔 Notifications' },
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
                {activeTab === 'general' && renderGeneralTab()}
                {activeTab === 'preferences' && renderPreferencesTab()}
                {activeTab === 'notifications' && renderNotificationsTab()}
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
              Langue: {LANGUAGES.find(l => l.value === formData.language)?.label || 'Français'}
            </span>
            <span>
              Fuseau: {formData.timezone}
            </span>
          </div>
        </CardFooter>
      </Card>
    );
  }
);

GeneralSettingsForm.displayName = 'GeneralSettingsForm';

// ============================================================================
// EXPORTS
// ============================================================================

export default GeneralSettingsForm;

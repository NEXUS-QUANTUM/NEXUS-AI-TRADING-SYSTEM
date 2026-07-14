// apps/web/src/components/forms/settings/NotificationSettingsForm.tsx
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
  BellIcon,
  BellSlashIcon,
  EnvelopeIcon,
  DevicePhoneMobileIcon,
  ChatBubbleLeftRightIcon,
  SpeakerWaveIcon,
  SpeakerXMarkIcon,
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
  ClockIcon,
  CalendarIcon,
  UserIcon,
  UserGroupIcon,
  BuildingOfficeIcon,
  GlobeAltIcon,
  ShieldCheckIcon,
  SparklesIcon,
  RocketLaunchIcon,
  WifiIcon,
  WifiSlashIcon,
  ServerIcon,
  CloudIcon,
  DatabaseIcon,
  LockClosedIcon,
  LockOpenIcon,
  LinkIcon,
  LinkSlashIcon,
  DocumentTextIcon,
  ChartBarIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
} from '@heroicons/react/24/outline';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Select } from '@/components/common/Select';
import { Switch } from '@/components/common/Switch';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/common/Tabs';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Separator } from '@/components/common/Separator';
import { Slider } from '@/components/common/Slider';
import { Tooltip } from '@/components/common/Tooltip';
import { ScrollArea } from '@/components/common/ScrollArea';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type NotificationChannel = 'email' | 'push' | 'sms' | 'webhook' | 'slack' | 'telegram' | 'discord';
export type NotificationPriority = 'low' | 'medium' | 'high' | 'critical';
export type NotificationType =
  | 'trade'
  | 'signal'
  | 'alert'
  | 'system'
  | 'security'
  | 'performance'
  | 'news'
  | 'social'
  | 'custom';
export type NotificationSchedule = 'immediate' | 'daily' | 'weekly' | 'monthly' | 'custom';
export type NotificationSound = 'none' | 'default' | 'gentle' | 'urgent' | 'custom';
export type NotificationFrequency = 'realtime' | 'batched' | 'digest';

export interface NotificationRule {
  /** Identifiant de la règle */
  id: string;
  /** Nom de la règle */
  name: string;
  /** Types de notifications */
  types: NotificationType[];
  /** Canaux */
  channels: NotificationChannel[];
  /** Priorité */
  priority: NotificationPriority;
  /** Horaire */
  schedule?: {
    /** Type d'horaire */
    type: NotificationSchedule;
    /** Heure (pour daily) */
    time?: string;
    /** Jour de la semaine (pour weekly) */
    dayOfWeek?: number;
    /** Jour du mois (pour monthly) */
    dayOfMonth?: number;
  };
  /** Filtres */
  filters?: {
    /** Symbole */
    symbols?: string[];
    /** Seuil minimum */
    minThreshold?: number;
    /** Seuil maximum */
    maxThreshold?: number;
    /** Tags */
    tags?: string[];
  };
  /** Est activée */
  enabled: boolean;
  /** Dernière notification */
  lastSent?: Date;
  /** Nombre de notifications */
  count?: number;
}

export interface NotificationSettingsData {
  /** Canaux activés */
  channels: {
    email: boolean;
    push: boolean;
    sms: boolean;
    webhook: boolean;
    slack: boolean;
    telegram: boolean;
    discord: boolean;
  };
  /** Configuration des canaux */
  channelConfigs: {
    email?: {
      address: string;
      cc?: string[];
      bcc?: string[];
    };
    push?: {
      enabled: boolean;
      sound: NotificationSound;
      vibration: boolean;
      badge: boolean;
    };
    sms?: {
      phone: string;
      provider: 'twilio' | 'nexmo' | 'custom';
      accountSid?: string;
      authToken?: string;
    };
    webhook?: {
      url: string;
      method: 'POST' | 'PUT' | 'PATCH';
      headers?: Record<string, string>;
      secret?: string;
    };
    slack?: {
      webhookUrl: string;
      channel: string;
      username?: string;
      icon?: string;
    };
    telegram?: {
      botToken: string;
      chatId: string;
    };
    discord?: {
      webhookUrl: string;
      username?: string;
      avatar?: string;
    };
  };
  /** Règles de notification */
  rules: NotificationRule[];
  /** Préférences globales */
  preferences: {
    /** Fréquence */
    frequency: NotificationFrequency;
    /** Heure de silence (début) */
    quietHoursStart?: string;
    /** Heure de silence (fin) */
    quietHoursEnd?: string;
    /** Activer les heures de silence */
    quietHoursEnabled: boolean;
    /** Désactiver pendant les heures de silence */
    quietHoursMute: boolean;
    /** Regrouper les notifications */
    groupNotifications: boolean;
    /** Délai de regroupement (ms) */
    groupDelay: number;
    /** Message par défaut */
    defaultMessage?: string;
    /** Template personnalisé */
    customTemplate?: string;
  };
  /** Statistiques */
  stats?: {
    totalSent: number;
    lastSent: Date;
    successRate: number;
    averageLatency: number;
    byChannel: Record<NotificationChannel, number>;
    byType: Record<NotificationType, number>;
  };
}

export interface NotificationSettingsFormProps {
  // --- Contrôle ---
  /** Données initiales */
  initialData?: Partial<NotificationSettingsData>;
  /** Callback de soumission */
  onSubmit?: (data: NotificationSettingsData) => void | Promise<void>;
  /** Callback de succès */
  onSuccess?: (data: NotificationSettingsData) => void;
  /** Callback d'erreur */
  onError?: (error: string) => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de changement */
  onChange?: (data: NotificationSettingsData) => void;

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

const CHANNELS: { value: NotificationChannel; label: string; icon: React.ReactNode; color: string }[] = [
  { value: 'email', label: 'Email', icon: <EnvelopeIcon className="h-4 w-4" />, color: 'text-blue-500' },
  { value: 'push', label: 'Push', icon: <DevicePhoneMobileIcon className="h-4 w-4" />, color: 'text-green-500' },
  { value: 'sms', label: 'SMS', icon: <ChatBubbleLeftRightIcon className="h-4 w-4" />, color: 'text-purple-500' },
  { value: 'webhook', label: 'Webhook', icon: <LinkIcon className="h-4 w-4" />, color: 'text-orange-500' },
  { value: 'slack', label: 'Slack', icon: <ChatBubbleLeftRightIcon className="h-4 w-4" />, color: 'text-red-500' },
  { value: 'telegram', label: 'Telegram', icon: <ChatBubbleLeftRightIcon className="h-4 w-4" />, color: 'text-blue-400' },
  { value: 'discord', label: 'Discord', icon: <ChatBubbleLeftRightIcon className="h-4 w-4" />, color: 'text-indigo-500' },
];

const NOTIFICATION_TYPES: { value: NotificationType; label: string; icon: React.ReactNode; color: string }[] = [
  { value: 'trade', label: 'Trades', icon: <ArrowTrendingUpIcon className="h-4 w-4" />, color: 'text-green-500' },
  { value: 'signal', label: 'Signaux', icon: <SparklesIcon className="h-4 w-4" />, color: 'text-purple-500' },
  { value: 'alert', label: 'Alertes', icon: <ExclamationTriangleIcon className="h-4 w-4" />, color: 'text-yellow-500' },
  { value: 'system', label: 'Système', icon: <ServerIcon className="h-4 w-4" />, color: 'text-gray-500' },
  { value: 'security', label: 'Sécurité', icon: <ShieldCheckIcon className="h-4 w-4" />, color: 'text-red-500' },
  { value: 'performance', label: 'Performance', icon: <ChartBarIcon className="h-4 w-4" />, color: 'text-blue-500' },
  { value: 'news', label: 'Actualités', icon: <DocumentTextIcon className="h-4 w-4" />, color: 'text-indigo-500' },
  { value: 'social', label: 'Social', icon: <UserGroupIcon className="h-4 w-4" />, color: 'text-pink-500' },
  { value: 'custom', label: 'Personnalisé', icon: <Cog6ToothIcon className="h-4 w-4" />, color: 'text-gray-500' },
];

const PRIORITIES: { value: NotificationPriority; label: string; color: string }[] = [
  { value: 'low', label: 'Basse', color: 'text-gray-500' },
  { value: 'medium', label: 'Moyenne', color: 'text-blue-500' },
  { value: 'high', label: 'Haute', color: 'text-yellow-500' },
  { value: 'critical', label: 'Critique', color: 'text-red-500' },
];

const SCHEDULES: { value: NotificationSchedule; label: string }[] = [
  { value: 'immediate', label: 'Immédiat' },
  { value: 'daily', label: 'Quotidien' },
  { value: 'weekly', label: 'Hebdomadaire' },
  { value: 'monthly', label: 'Mensuel' },
  { value: 'custom', label: 'Personnalisé' },
];

const SOUNDS: { value: NotificationSound; label: string }[] = [
  { value: 'none', label: 'Aucun' },
  { value: 'default', label: 'Par défaut' },
  { value: 'gentle', label: 'Doux' },
  { value: 'urgent', label: 'Urgent' },
  { value: 'custom', label: 'Personnalisé' },
];

const FREQUENCIES: { value: NotificationFrequency; label: string; description: string }[] = [
  { value: 'realtime', label: 'Temps réel', description: 'Notifications instantanées' },
  { value: 'batched', label: 'Batch', description: 'Notifications groupées' },
  { value: 'digest', label: 'Digest', description: 'Résumé périodique' },
];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const NotificationSettingsForm = forwardRef<HTMLDivElement, NotificationSettingsFormProps>(
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
      title = 'Notifications',
      subtitle = 'Configurez vos préférences de notification',
      className,
      variant = 'default',

      // États
      isLoading = false,
      error = null,
      success = null,
      disabled = false,

      // Accessibilité
      ariaLabel = 'Paramètres de notification',
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

    const [formData, setFormData] = useState<NotificationSettingsData>({
      channels: {
        email: true,
        push: true,
        sms: false,
        webhook: false,
        slack: false,
        telegram: false,
        discord: false,
      },
      channelConfigs: {},
      rules: [],
      preferences: {
        frequency: 'realtime',
        quietHoursEnabled: false,
        quietHoursMute: true,
        groupNotifications: true,
        groupDelay: 5000,
      },
      ...initialData,
    });

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [activeTab, setActiveTab] = useState<'channels' | 'rules' | 'preferences'>('channels');
    const [isAddingRule, setIsAddingRule] = useState(false);
    const [editingRuleIndex, setEditingRuleIndex] = useState<number | null>(null);
    const [newRule, setNewRule] = useState<Partial<NotificationRule>>({
      name: '',
      types: [],
      channels: [],
      priority: 'medium',
      enabled: true,
    });

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validate = useCallback((): boolean => {
      const errors: Record<string, string> = {};

      // Vérifier les règles
      formData.rules.forEach((rule, index) => {
        if (!rule.name) {
          errors[`rule_${index}_name`] = 'Le nom de la règle est requis';
        }
        if (rule.types.length === 0) {
          errors[`rule_${index}_types`] = 'Sélectionnez au moins un type';
        }
        if (rule.channels.length === 0) {
          errors[`rule_${index}_channels`] = 'Sélectionnez au moins un canal';
        }
      });

      setFormErrors(errors);
      return Object.keys(errors).length === 0;
    }, [formData]);

    // ========================================================================
    // GESTIONNAIRES DE CHAMPS
    // ========================================================================

    const handleFieldChange = useCallback(<K extends keyof NotificationSettingsData>(
      field: K,
      value: NotificationSettingsData[K]
    ) => {
      setFormData(prev => ({ ...prev, [field]: value }));
    }, []);

    const handleChannelToggle = useCallback((channel: NotificationChannel, enabled: boolean) => {
      setFormData(prev => ({
        ...prev,
        channels: { ...prev.channels, [channel]: enabled },
      }));
    }, []);

    const handleChannelConfigChange = useCallback(
      <C extends keyof NotificationSettingsData['channelConfigs']>(
        channel: C,
        field: string,
        value: any
      ) => {
        setFormData(prev => ({
          ...prev,
          channelConfigs: {
            ...prev.channelConfigs,
            [channel]: {
              ...prev.channelConfigs[channel],
              [field]: value,
            },
          },
        }));
      },
      []
    );

    const handlePreferenceChange = useCallback(<K extends keyof NotificationSettingsData['preferences']>(
      field: K,
      value: NotificationSettingsData['preferences'][K]
    ) => {
      setFormData(prev => ({
        ...prev,
        preferences: { ...prev.preferences, [field]: value },
      }));
    }, []);

    // ========================================================================
    // GESTION DES RÈGLES
    // ========================================================================

    const handleAddRule = useCallback(() => {
      if (!newRule.name) {
        toast({
          title: 'Erreur',
          description: 'Le nom de la règle est requis',
          variant: 'destructive',
        });
        return;
      }

      const rule: NotificationRule = {
        id: `rule_${Date.now()}`,
        name: newRule.name,
        types: newRule.types || [],
        channels: newRule.channels || [],
        priority: newRule.priority || 'medium',
        enabled: newRule.enabled !== undefined ? newRule.enabled : true,
        ...(newRule.schedule && { schedule: newRule.schedule }),
        ...(newRule.filters && { filters: newRule.filters }),
      };

      setFormData(prev => ({
        ...prev,
        rules: [...prev.rules, rule],
      }));

      setNewRule({
        name: '',
        types: [],
        channels: [],
        priority: 'medium',
        enabled: true,
      });
      setIsAddingRule(false);

      toast({
        title: 'Règle ajoutée',
        description: `La règle "${rule.name}" a été ajoutée`,
        duration: 2000,
      });
    }, [newRule, toast]);

    const handleUpdateRule = useCallback(() => {
      if (editingRuleIndex === null) return;
      if (!newRule.name) {
        toast({
          title: 'Erreur',
          description: 'Le nom de la règle est requis',
          variant: 'destructive',
        });
        return;
      }

      setFormData(prev => {
        const newRules = [...prev.rules];
        newRules[editingRuleIndex] = {
          ...newRules[editingRuleIndex],
          name: newRule.name,
          types: newRule.types || [],
          channels: newRule.channels || [],
          priority: newRule.priority || 'medium',
          enabled: newRule.enabled !== undefined ? newRule.enabled : true,
          ...(newRule.schedule && { schedule: newRule.schedule }),
          ...(newRule.filters && { filters: newRule.filters }),
        };
        return { ...prev, rules: newRules };
      });

      setNewRule({
        name: '',
        types: [],
        channels: [],
        priority: 'medium',
        enabled: true,
      });
      setIsAddingRule(false);
      setEditingRuleIndex(null);

      toast({
        title: 'Règle mise à jour',
        description: 'La règle a été mise à jour',
        duration: 2000,
      });
    }, [editingRuleIndex, newRule, toast]);

    const handleRemoveRule = useCallback((index: number) => {
      const rule = formData.rules[index];
      setFormData(prev => ({
        ...prev,
        rules: prev.rules.filter((_, i) => i !== index),
      }));

      toast({
        title: 'Règle supprimée',
        description: `La règle "${rule.name}" a été supprimée`,
        duration: 2000,
      });
    }, [formData.rules, toast]);

    const handleToggleRule = useCallback((index: number) => {
      setFormData(prev => {
        const newRules = [...prev.rules];
        newRules[index] = { ...newRules[index], enabled: !newRules[index].enabled };
        return { ...prev, rules: newRules };
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
          description: 'Les préférences de notification ont été mises à jour',
          variant: 'success',
        });

        if (debug) {
          console.log('Notification settings saved:', formData);
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
    // RENDU DES CANAUX
    // ========================================================================

    const renderChannels = () => (
      <div className="space-y-6">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          {CHANNELS.map((channel) => (
            <div
              key={channel.value}
              className={cn(
                'flex items-center gap-3 rounded-lg border p-3 transition-colors',
                formData.channels[channel.value]
                  ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                  : 'border-gray-200 dark:border-gray-700'
              )}
            >
              <div className={cn('flex-shrink-0', channel.color)}>
                {channel.icon}
              </div>
              <div className="flex-1">
                <p className="font-medium">{channel.label}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">
                  {formData.channels[channel.value] ? 'Activé' : 'Désactivé'}
                </p>
              </div>
              <Switch
                checked={formData.channels[channel.value]}
                onCheckedChange={(checked) => handleChannelToggle(channel.value, checked)}
                disabled={disabled || isSubmitting || isLoading}
              />
            </div>
          ))}
        </div>

        <Separator />

        {/* Configuration des canaux */}
        {CHANNELS.map((channel) => {
          if (!formData.channels[channel.value]) return null;

          return (
            <div key={channel.value} className="space-y-3">
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Configuration {channel.label}
              </h4>

              {channel.value === 'email' && (
                <div className="grid grid-cols-1 gap-3">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Adresse email
                    </label>
                    <Input
                      type="email"
                      placeholder="notifications@exemple.com"
                      value={formData.channelConfigs.email?.address || ''}
                      onChange={(e) => handleChannelConfigChange('email', 'address', e.target.value)}
                      disabled={disabled || isSubmitting || isLoading}
                    />
                  </div>
                </div>
              )}

              {channel.value === 'push' && (
                <div className="space-y-3">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Son
                    </label>
                    <Select
                      options={SOUNDS}
                      value={formData.channelConfigs.push?.sound || 'default'}
                      onChange={(value) => handleChannelConfigChange('push', 'sound', value)}
                      disabled={disabled || isSubmitting || isLoading}
                    />
                  </div>
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={formData.channelConfigs.push?.vibration || false}
                        onCheckedChange={(checked) => handleChannelConfigChange('push', 'vibration', checked)}
                        disabled={disabled || isSubmitting || isLoading}
                      />
                      <span className="text-sm text-gray-600 dark:text-gray-300">Vibration</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={formData.channelConfigs.push?.badge || false}
                        onCheckedChange={(checked) => handleChannelConfigChange('push', 'badge', checked)}
                        disabled={disabled || isSubmitting || isLoading}
                      />
                      <span className="text-sm text-gray-600 dark:text-gray-300">Badge</span>
                    </div>
                  </div>
                </div>
              )}

              {channel.value === 'sms' && (
                <div className="grid grid-cols-1 gap-3">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Numéro de téléphone
                    </label>
                    <Input
                      type="tel"
                      placeholder="+33 6 12 34 56 78"
                      value={formData.channelConfigs.sms?.phone || ''}
                      onChange={(e) => handleChannelConfigChange('sms', 'phone', e.target.value)}
                      disabled={disabled || isSubmitting || isLoading}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Fournisseur
                    </label>
                    <Select
                      options={[
                        { value: 'twilio', label: 'Twilio' },
                        { value: 'nexmo', label: 'Nexmo' },
                        { value: 'custom', label: 'Personnalisé' },
                      ]}
                      value={formData.channelConfigs.sms?.provider || 'twilio'}
                      onChange={(value) => handleChannelConfigChange('sms', 'provider', value)}
                      disabled={disabled || isSubmitting || isLoading}
                    />
                  </div>
                </div>
              )}

              {channel.value === 'webhook' && (
                <div className="grid grid-cols-1 gap-3">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      URL
                    </label>
                    <Input
                      type="url"
                      placeholder="https://api.exemple.com/webhook"
                      value={formData.channelConfigs.webhook?.url || ''}
                      onChange={(e) => handleChannelConfigChange('webhook', 'url', e.target.value)}
                      disabled={disabled || isSubmitting || isLoading}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Méthode
                    </label>
                    <Select
                      options={[
                        { value: 'POST', label: 'POST' },
                        { value: 'PUT', label: 'PUT' },
                        { value: 'PATCH', label: 'PATCH' },
                      ]}
                      value={formData.channelConfigs.webhook?.method || 'POST'}
                      onChange={(value) => handleChannelConfigChange('webhook', 'method', value)}
                      disabled={disabled || isSubmitting || isLoading}
                    />
                  </div>
                </div>
              )}

              {channel.value === 'slack' && (
                <div className="grid grid-cols-1 gap-3">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Webhook URL
                    </label>
                    <Input
                      type="url"
                      placeholder="https://hooks.slack.com/services/..."
                      value={formData.channelConfigs.slack?.webhookUrl || ''}
                      onChange={(e) => handleChannelConfigChange('slack', 'webhookUrl', e.target.value)}
                      disabled={disabled || isSubmitting || isLoading}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Canal
                    </label>
                    <Input
                      type="text"
                      placeholder="#general"
                      value={formData.channelConfigs.slack?.channel || ''}
                      onChange={(e) => handleChannelConfigChange('slack', 'channel', e.target.value)}
                      disabled={disabled || isSubmitting || isLoading}
                    />
                  </div>
                </div>
              )}

              {channel.value === 'telegram' && (
                <div className="grid grid-cols-1 gap-3">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Bot Token
                    </label>
                    <Input
                      type="text"
                      placeholder="123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
                      value={formData.channelConfigs.telegram?.botToken || ''}
                      onChange={(e) => handleChannelConfigChange('telegram', 'botToken', e.target.value)}
                      disabled={disabled || isSubmitting || isLoading}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Chat ID
                    </label>
                    <Input
                      type="text"
                      placeholder="123456789"
                      value={formData.channelConfigs.telegram?.chatId || ''}
                      onChange={(e) => handleChannelConfigChange('telegram', 'chatId', e.target.value)}
                      disabled={disabled || isSubmitting || isLoading}
                    />
                  </div>
                </div>
              )}

              {channel.value === 'discord' && (
                <div className="grid grid-cols-1 gap-3">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Webhook URL
                    </label>
                    <Input
                      type="url"
                      placeholder="https://discord.com/api/webhooks/..."
                      value={formData.channelConfigs.discord?.webhookUrl || ''}
                      onChange={(e) => handleChannelConfigChange('discord', 'webhookUrl', e.target.value)}
                      disabled={disabled || isSubmitting || isLoading}
                    />
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    );

    // ========================================================================
    // RENDU DES RÈGLES
    // ========================================================================

    const renderRules = () => (
      <div className="space-y-6">
        {/* Liste des règles */}
        {formData.rules.length > 0 && (
          <div className="space-y-3">
            {formData.rules.map((rule, index) => (
              <div
                key={rule.id}
                className={cn(
                  'flex items-center gap-3 rounded-lg border p-3',
                  rule.enabled ? 'border-gray-200 dark:border-gray-700' : 'border-gray-300 dark:border-gray-600 opacity-60'
                )}
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{rule.name}</span>
                    <Badge variant={rule.priority === 'critical' ? 'danger' : rule.priority === 'high' ? 'warning' : 'default'}>
                      {PRIORITIES.find(p => p.value === rule.priority)?.label || 'Moyenne'}
                    </Badge>
                    {rule.types.length > 0 && (
                      <Badge variant="outline" size="xs">
                        {rule.types.length} type{rule.types.length > 1 ? 's' : ''}
                      </Badge>
                    )}
                    {rule.channels.length > 0 && (
                      <Badge variant="outline" size="xs">
                        {rule.channels.length} canal{rule.channels.length > 1 ? 'x' : ''}
                      </Badge>
                    )}
                    {!rule.enabled && (
                      <Badge variant="outline" size="xs">Désactivée</Badge>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1 mt-1">
                    {rule.types.map((type) => {
                      const typeInfo = NOTIFICATION_TYPES.find(t => t.value === type);
                      return (
                        <Badge key={type} variant="outline" size="xs" className={typeInfo?.color}>
                          {typeInfo?.label || type}
                        </Badge>
                      );
                    })}
                    {rule.channels.map((channel) => {
                      const channelInfo = CHANNELS.find(c => c.value === channel);
                      return (
                        <Badge key={channel} variant="outline" size="xs" className={channelInfo?.color}>
                          {channelInfo?.label || channel}
                        </Badge>
                      );
                    })}
                  </div>
                </div>
                <div className="flex items-center gap-1">
                  <Tooltip content={rule.enabled ? 'Désactiver' : 'Activer'}>
                    <button
                      type="button"
                      className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                      onClick={() => handleToggleRule(index)}
                    >
                      {rule.enabled ? <BellIcon className="h-4 w-4" /> : <BellSlashIcon className="h-4 w-4" />}
                    </button>
                  </Tooltip>
                  <Tooltip content="Modifier">
                    <button
                      type="button"
                      className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                      onClick={() => {
                        setNewRule(rule);
                        setEditingRuleIndex(index);
                        setIsAddingRule(true);
                      }}
                    >
                      <PencilIcon className="h-4 w-4" />
                    </button>
                  </Tooltip>
                  <Tooltip content="Supprimer">
                    <button
                      type="button"
                      className="rounded p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                      onClick={() => handleRemoveRule(index)}
                    >
                      <TrashIcon className="h-4 w-4" />
                    </button>
                  </Tooltip>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Ajout/Modification de règle */}
        {isAddingRule && (
          <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {editingRuleIndex !== null ? 'Modifier la règle' : 'Ajouter une règle'}
              </h4>
              <button
                type="button"
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                onClick={() => {
                  setIsAddingRule(false);
                  setEditingRuleIndex(null);
                  setNewRule({
                    name: '',
                    types: [],
                    channels: [],
                    priority: 'medium',
                    enabled: true,
                  });
                }}
              >
                <XMarkIcon className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Nom
                </label>
                <Input
                  type="text"
                  placeholder="Ma règle"
                  value={newRule.name || ''}
                  onChange={(e) => setNewRule({ ...newRule, name: e.target.value })}
                />
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Types
                </label>
                <div className="flex flex-wrap gap-2">
                  {NOTIFICATION_TYPES.map((type) => (
                    <button
                      key={type.value}
                      type="button"
                      className={cn(
                        'flex items-center gap-1 rounded-lg border-2 px-3 py-1.5 text-sm transition-all',
                        (newRule.types || []).includes(type.value)
                          ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-400'
                          : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                      )}
                      onClick={() => {
                        const types = newRule.types || [];
                        const newTypes = types.includes(type.value)
                          ? types.filter(t => t !== type.value)
                          : [...types, type.value];
                        setNewRule({ ...newRule, types: newTypes });
                      }}
                    >
                      {type.icon}
                      {type.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Canaux
                </label>
                <div className="flex flex-wrap gap-2">
                  {CHANNELS.map((channel) => (
                    <button
                      key={channel.value}
                      type="button"
                      className={cn(
                        'flex items-center gap-1 rounded-lg border-2 px-3 py-1.5 text-sm transition-all',
                        (newRule.channels || []).includes(channel.value)
                          ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-400'
                          : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                      )}
                      onClick={() => {
                        const channels = newRule.channels || [];
                        const newChannels = channels.includes(channel.value)
                          ? channels.filter(c => c !== channel.value)
                          : [...channels, channel.value];
                        setNewRule({ ...newRule, channels: newChannels });
                      }}
                    >
                      {channel.icon}
                      {channel.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Priorité
                  </label>
                  <Select
                    options={PRIORITIES.map(p => ({ value: p.value, label: p.label }))}
                    value={newRule.priority || 'medium'}
                    onChange={(value) => setNewRule({ ...newRule, priority: value as NotificationPriority })}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Activée
                  </label>
                  <div className="pt-2">
                    <Switch
                      checked={newRule.enabled !== undefined ? newRule.enabled : true}
                      onCheckedChange={(checked) => setNewRule({ ...newRule, enabled: checked })}
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsAddingRule(false);
                  setEditingRuleIndex(null);
                  setNewRule({
                    name: '',
                    types: [],
                    channels: [],
                    priority: 'medium',
                    enabled: true,
                  });
                }}
              >
                Annuler
              </Button>
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={editingRuleIndex !== null ? handleUpdateRule : handleAddRule}
              >
                {editingRuleIndex !== null ? 'Mettre à jour' : 'Ajouter'}
              </Button>
            </div>
          </div>
        )}

        {!isAddingRule && (
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => setIsAddingRule(true)}
            disabled={disabled || isSubmitting || isLoading}
          >
            <PlusIcon className="h-4 w-4 mr-2" />
            Ajouter une règle
          </Button>
        )}
      </div>
    );

    // ========================================================================
    // RENDU DES PRÉFÉRENCES
    // ========================================================================

    const renderPreferences = () => (
      <div className="space-y-6">
        <div className="space-y-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Fréquence
            </label>
            <Select
              options={FREQUENCIES.map(f => ({ value: f.value, label: `${f.label} - ${f.description}` }))}
              value={formData.preferences.frequency}
              onChange={(value) => handlePreferenceChange('frequency', value as NotificationFrequency)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <Separator />

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Heures de silence
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Désactiver les notifications pendant certaines heures
              </p>
            </div>
            <Switch
              checked={formData.preferences.quietHoursEnabled}
              onCheckedChange={(checked) => handlePreferenceChange('quietHoursEnabled', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          {formData.preferences.quietHoursEnabled && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pl-6">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Début
                </label>
                <Input
                  type="time"
                  value={formData.preferences.quietHoursStart || '22:00'}
                  onChange={(e) => handlePreferenceChange('quietHoursStart', e.target.value)}
                  disabled={disabled || isSubmitting || isLoading}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Fin
                </label>
                <Input
                  type="time"
                  value={formData.preferences.quietHoursEnd || '07:00'}
                  onChange={(e) => handlePreferenceChange('quietHoursEnd', e.target.value)}
                  disabled={disabled || isSubmitting || isLoading}
                />
              </div>
              <div className="col-span-2 flex items-center gap-2">
                <Switch
                  checked={formData.preferences.quietHoursMute}
                  onCheckedChange={(checked) => handlePreferenceChange('quietHoursMute', checked)}
                  disabled={disabled || isSubmitting || isLoading}
                />
                <span className="text-sm text-gray-600 dark:text-gray-300">
                  Désactiver complètement (sinon mode silencieux)
                </span>
              </div>
            </div>
          )}

          <Separator />

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Regrouper les notifications
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Regrouper les notifications similaires
              </p>
            </div>
            <Switch
              checked={formData.preferences.groupNotifications}
              onCheckedChange={(checked) => handlePreferenceChange('groupNotifications', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          {formData.preferences.groupNotifications && (
            <div className="pl-6 space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Délai de regroupement (ms)
              </label>
              <Input
                type="number"
                value={formData.preferences.groupDelay}
                onChange={(e) => handlePreferenceChange('groupDelay', parseInt(e.target.value) || 5000)}
                disabled={disabled || isSubmitting || isLoading}
                step={1000}
                min={1000}
              />
            </div>
          )}
        </div>

        <Separator />

        {/* Statistiques */}
        {formData.stats && (
          <div className="space-y-3">
            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">Statistiques</h4>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
              <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-2 text-center">
                <div className="text-lg font-bold">{formData.stats.totalSent}</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Envoyées</div>
              </div>
              <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-2 text-center">
                <div className="text-lg font-bold">{formData.stats.successRate}%</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Taux de succès</div>
              </div>
              <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-2 text-center">
                <div className="text-lg font-bold">{formData.stats.averageLatency}ms</div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Latence moyenne</div>
              </div>
              <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-2 text-center">
                <div className="text-lg font-bold">
                  {formData.stats.lastSent.toLocaleString()}
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400">Dernier envoi</div>
              </div>
            </div>
          </div>
        )}
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
                  <BellIcon className="h-3 w-3" />
                  {formData.rules.length} règles
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
              { id: 'channels', label: '📡 Canaux' },
              { id: 'rules', label: '📋 Règles' },
              { id: 'preferences', label: '⚙️ Préférences' },
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
                {activeTab === 'channels' && renderChannels()}
                {activeTab === 'rules' && renderRules()}
                {activeTab === 'preferences' && renderPreferences()}
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
              {Object.values(formData.channels).filter(Boolean).length} canaux actifs
            </span>
            <span>
              {formData.rules.length} règles configurées
            </span>
          </div>
        </CardFooter>
      </Card>
    );
  }
);

NotificationSettingsForm.displayName = 'NotificationSettingsForm';

// ============================================================================
// EXPORTS
// ============================================================================

export default NotificationSettingsForm;

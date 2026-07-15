// apps/web/src/components/forms/trading/AlertForm.tsx
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
  EnvelopeIcon,
  DevicePhoneMobileIcon,
  ChatBubbleLeftRightIcon,
  GlobeAltIcon,
  ShieldCheckIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  ChartBarIcon,
  ChartLineIcon,
  ChartPieIcon,
  CurrencyDollarIcon,
  PercentIcon,
  ScaleIcon,
  TagIcon,
  HashtagIcon,
  LinkIcon,
  LinkSlashIcon,
  EyeIcon,
  EyeSlashIcon,
  UserIcon,
  UserGroupIcon,
  BuildingOfficeIcon,
  DocumentTextIcon,
  TableCellsIcon,
  Squares2X2Icon,
  ListBulletIcon,
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
import { Slider } from '@/components/common/Slider';
import { Tooltip } from '@/components/common/Tooltip';
import { ScrollArea } from '@/components/common/ScrollArea';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type AlertType = 
  | 'price' 
  | 'volume' 
  | 'technical' 
  | 'signal' 
  | 'news' 
  | 'system' 
  | 'custom';

export type AlertCondition = 
  | 'above' 
  | 'below' 
  | 'cross_above' 
  | 'cross_below' 
  | 'between' 
  | 'outside' 
  | 'change_percent' 
  | 'volume_spike' 
  | 'rsi_above' 
  | 'rsi_below' 
  | 'macd_cross' 
  | 'bb_breakout';

export type AlertChannel = 
  | 'email' 
  | 'push' 
  | 'sms' 
  | 'webhook' 
  | 'slack' 
  | 'telegram' 
  | 'discord' 
  | 'all';

export type AlertPriority = 'low' | 'medium' | 'high' | 'critical';
export type AlertStatus = 'active' | 'inactive' | 'triggered' | 'expired';
export type AlertFrequency = 'once' | 'always' | 'daily' | 'weekly' | 'monthly';
export type AlertAction = 'notify' | 'order' | 'webhook' | 'email' | 'sms';

export interface AlertConditionConfig {
  /** Type de condition */
  type: AlertCondition;
  /** Valeur seuil */
  value: number;
  /** Valeur seuil 2 (pour between/outside) */
  value2?: number;
  /** Symbole cible */
  symbol: string;
  /** Timeframe (pour les indicateurs techniques) */
  timeframe?: string;
  /** Paramètres supplémentaires */
  params?: Record<string, any>;
}

export interface AlertActionConfig {
  /** Type d'action */
  type: AlertAction;
  /** Configuration spécifique */
  config: Record<string, any>;
  /** Délai avant exécution (ms) */
  delay?: number;
  /** Nombre maximum d'exécutions */
  maxExecutions?: number;
}

export interface AlertSchedule {
  /** Type de fréquence */
  frequency: AlertFrequency;
  /** Heure de déclenchement (pour daily) */
  time?: string;
  /** Jour de la semaine (pour weekly) */
  dayOfWeek?: number;
  /** Jour du mois (pour monthly) */
  dayOfMonth?: number;
  /** Date de début */
  startDate?: Date;
  /** Date de fin */
  endDate?: Date;
}

export interface Alert {
  /** Identifiant */
  id: string;
  /** Nom de l'alerte */
  name: string;
  /** Description */
  description?: string;
  /** Type d'alerte */
  type: AlertType;
  /** Conditions */
  conditions: AlertConditionConfig[];
  /** Actions */
  actions: AlertActionConfig[];
  /** Canal de notification */
  channels: AlertChannel[];
  /** Priorité */
  priority: AlertPriority;
  /** Statut */
  status: AlertStatus;
  /** Horaire */
  schedule?: AlertSchedule;
  /** Tags */
  tags?: string[];
  /** Dernier déclenchement */
  lastTriggered?: Date;
  /** Nombre de déclenchements */
  triggerCount?: number;
  /** Est-ce que l'alerte est silencieuse */
  silent?: boolean;
  /** Est-ce que l'alerte est récurrente */
  recurring?: boolean;
  /** Intervalle de récurrence (ms) */
  recurrenceInterval?: number;
  /** Délai avant récurrence (ms) */
  cooldownPeriod?: number;
}

export interface AlertFormProps {
  // --- Contrôle ---
  /** Données initiales de l'alerte */
  initialData?: Partial<Alert>;
  /** Mode d'édition */
  mode?: 'create' | 'edit' | 'duplicate' | 'view';
  /** Callback de soumission */
  onSubmit?: (data: Alert) => void | Promise<void>;
  /** Callback de succès */
  onSuccess?: (data: Alert) => void;
  /** Callback d'erreur */
  onError?: (error: string) => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de changement */
  onChange?: (data: Alert) => void;

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
  /** Symboles disponibles */
  availableSymbols?: string[];
  /** Canaux disponibles */
  availableChannels?: AlertChannel[];
  /** Actions disponibles */
  availableActions?: AlertAction[];
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const ALERT_TYPES: { value: AlertType; label: string; icon: React.ReactNode; description: string }[] = [
  { value: 'price', label: 'Prix', icon: <CurrencyDollarIcon className="h-4 w-4" />, description: 'Alerte basée sur le prix' },
  { value: 'volume', label: 'Volume', icon: <ChartBarIcon className="h-4 w-4" />, description: 'Alerte basée sur le volume' },
  { value: 'technical', label: 'Technique', icon: <ChartLineIcon className="h-4 w-4" />, description: 'Alerte basée sur des indicateurs techniques' },
  { value: 'signal', label: 'Signal', icon: <ArrowTrendingUpIcon className="h-4 w-4" />, description: 'Alerte basée sur des signaux de trading' },
  { value: 'news', label: 'Actualités', icon: <DocumentTextIcon className="h-4 w-4" />, description: 'Alerte basée sur les actualités' },
  { value: 'system', label: 'Système', icon: <Cog6ToothIcon className="h-4 w-4" />, description: 'Alerte système' },
  { value: 'custom', label: 'Personnalisé', icon: <AdjustmentsHorizontalIcon className="h-4 w-4" />, description: 'Alerte personnalisée' },
];

const ALERT_CONDITIONS: { value: AlertCondition; label: string; description: string }[] = [
  { value: 'above', label: 'Supérieur à', description: 'Déclenché lorsque la valeur est supérieure au seuil' },
  { value: 'below', label: 'Inférieur à', description: 'Déclenché lorsque la valeur est inférieure au seuil' },
  { value: 'cross_above', label: 'Croisement au-dessus', description: 'Déclenché lorsque la valeur croise au-dessus du seuil' },
  { value: 'cross_below', label: 'Croisement en-dessous', description: 'Déclenché lorsque la valeur croise en-dessous du seuil' },
  { value: 'between', label: 'Entre', description: 'Déclenché lorsque la valeur est entre deux seuils' },
  { value: 'outside', label: 'En dehors', description: 'Déclenché lorsque la valeur est en dehors de deux seuils' },
  { value: 'change_percent', label: 'Changement %', description: 'Déclenché lorsque le changement en pourcentage dépasse le seuil' },
  { value: 'volume_spike', label: 'Pic de volume', description: 'Déclenché lors d\'un pic de volume' },
  { value: 'rsi_above', label: 'RSI au-dessus', description: 'Déclenché lorsque le RSI est au-dessus du seuil' },
  { value: 'rsi_below', label: 'RSI en-dessous', description: 'Déclenché lorsque le RSI est en-dessous du seuil' },
  { value: 'macd_cross', label: 'Croisement MACD', description: 'Déclenché lors d\'un croisement MACD' },
  { value: 'bb_breakout', label: 'Breakout Bollinger', description: 'Déclenché lors d\'un breakout des bandes de Bollinger' },
];

const ALERT_PRIORITIES: { value: AlertPriority; label: string; color: string; score: number }[] = [
  { value: 'low', label: 'Basse', color: 'text-gray-500', score: 1 },
  { value: 'medium', label: 'Moyenne', color: 'text-blue-500', score: 2 },
  { value: 'high', label: 'Haute', color: 'text-yellow-500', score: 3 },
  { value: 'critical', label: 'Critique', color: 'text-red-500', score: 4 },
];

const ALERT_CHANNELS: { value: AlertChannel; label: string; icon: React.ReactNode }[] = [
  { value: 'email', label: 'Email', icon: <EnvelopeIcon className="h-4 w-4" /> },
  { value: 'push', label: 'Push', icon: <DevicePhoneMobileIcon className="h-4 w-4" /> },
  { value: 'sms', label: 'SMS', icon: <ChatBubbleLeftRightIcon className="h-4 w-4" /> },
  { value: 'webhook', label: 'Webhook', icon: <LinkIcon className="h-4 w-4" /> },
  { value: 'slack', label: 'Slack', icon: <ChatBubbleLeftRightIcon className="h-4 w-4" /> },
  { value: 'telegram', label: 'Telegram', icon: <ChatBubbleLeftRightIcon className="h-4 w-4" /> },
  { value: 'discord', label: 'Discord', icon: <ChatBubbleLeftRightIcon className="h-4 w-4" /> },
  { value: 'all', label: 'Tous', icon: <GlobeAltIcon className="h-4 w-4" /> },
];

const ALERT_ACTIONS: { value: AlertAction; label: string; description: string }[] = [
  { value: 'notify', label: 'Notifier', description: 'Envoyer une notification' },
  { value: 'order', label: 'Ordre', description: 'Placer un ordre' },
  { value: 'webhook', label: 'Webhook', description: 'Appeler un webhook' },
  { value: 'email', label: 'Email', description: 'Envoyer un email' },
  { value: 'sms', label: 'SMS', description: 'Envoyer un SMS' },
];

const ALERT_FREQUENCIES: { value: AlertFrequency; label: string }[] = [
  { value: 'once', label: 'Une fois' },
  { value: 'always', label: 'Toujours' },
  { value: 'daily', label: 'Quotidien' },
  { value: 'weekly', label: 'Hebdomadaire' },
  { value: 'monthly', label: 'Mensuel' },
];

const ALERT_STATUSES: { value: AlertStatus; label: string; color: string }[] = [
  { value: 'active', label: 'Active', color: 'text-green-500' },
  { value: 'inactive', label: 'Inactive', color: 'text-gray-400' },
  { value: 'triggered', label: 'Déclenchée', color: 'text-yellow-500' },
  { value: 'expired', label: 'Expirée', color: 'text-red-500' },
];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const AlertForm = forwardRef<HTMLDivElement, AlertFormProps>(
  (props, ref) => {
    const {
      // Contrôle
      initialData = {},
      mode = 'create',
      onSubmit,
      onSuccess,
      onError,
      onCancel,
      onChange,

      // Apparence
      title = mode === 'create' ? 'Nouvelle alerte' : 'Modifier l\'alerte',
      subtitle = mode === 'create' ? 'Configurez votre alerte de trading' : 'Modifiez les paramètres de l\'alerte',
      className,
      variant = 'default',

      // États
      isLoading = false,
      error = null,
      success = null,
      disabled = false,

      // Accessibilité
      ariaLabel = 'Formulaire d\'alerte',
      id,

      // Avancé
      availableSymbols = ['BTCUSDT', 'ETHUSDT', 'BNBUSDT', 'XRPUSDT', 'ADAUSDT', 'SOLUSDT', 'DOTUSDT', 'DOGEUSDT'],
      availableChannels = ['email', 'push', 'sms', 'webhook', 'slack', 'telegram', 'discord'],
      availableActions = ['notify', 'order', 'webhook', 'email', 'sms'],
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

    const [formData, setFormData] = useState<Alert>({
      id: initialData.id || `alert_${Date.now()}`,
      name: initialData.name || '',
      description: initialData.description || '',
      type: initialData.type || 'price',
      conditions: initialData.conditions || [{
        type: 'above',
        value: 0,
        symbol: 'BTCUSDT',
      }],
      actions: initialData.actions || [{
        type: 'notify',
        config: {},
      }],
      channels: initialData.channels || ['push'],
      priority: initialData.priority || 'medium',
      status: initialData.status || 'active',
      schedule: initialData.schedule,
      tags: initialData.tags || [],
      silent: initialData.silent || false,
      recurring: initialData.recurring || false,
      recurrenceInterval: initialData.recurrenceInterval || 60000,
      cooldownPeriod: initialData.cooldownPeriod || 30000,
      ...initialData,
    });

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [activeTab, setActiveTab] = useState<'general' | 'conditions' | 'actions' | 'schedule'>('general');
    const [isAddingCondition, setIsAddingCondition] = useState(false);
    const [isAddingAction, setIsAddingAction] = useState(false);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validate = useCallback((): boolean => {
      const errors: Record<string, string> = {};

      if (!formData.name) {
        errors.name = 'Le nom de l\'alerte est requis';
      }

      if (formData.conditions.length === 0) {
        errors.conditions = 'Au moins une condition est requise';
      }

      formData.conditions.forEach((condition, index) => {
        if (!condition.symbol) {
          errors[`condition_${index}_symbol`] = 'Le symbole est requis';
        }
        if (condition.value <= 0) {
          errors[`condition_${index}_value`] = 'La valeur doit être positive';
        }
        if (condition.type === 'between' || condition.type === 'outside') {
          if (!condition.value2 || condition.value2 <= condition.value) {
            errors[`condition_${index}_value2`] = 'La valeur supérieure doit être supérieure à la valeur inférieure';
          }
        }
      });

      if (formData.channels.length === 0) {
        errors.channels = 'Au moins un canal est requis';
      }

      if (formData.actions.length === 0) {
        errors.actions = 'Au moins une action est requise';
      }

      setFormErrors(errors);
      return Object.keys(errors).length === 0;
    }, [formData]);

    // ========================================================================
    // GESTIONNAIRES DE CHAMPS
    // ========================================================================

    const handleFieldChange = useCallback(<K extends keyof Alert>(
      field: K,
      value: Alert[K]
    ) => {
      setFormData(prev => ({ ...prev, [field]: value }));
      setFormErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }, []);

    // ========================================================================
    // GESTION DES CONDITIONS
    // ========================================================================

    const handleAddCondition = useCallback(() => {
      setFormData(prev => ({
        ...prev,
        conditions: [
          ...prev.conditions,
          {
            type: 'above',
            value: 0,
            symbol: availableSymbols[0] || 'BTCUSDT',
          },
        ],
      }));
      setIsAddingCondition(false);
    }, [availableSymbols]);

    const handleRemoveCondition = useCallback((index: number) => {
      setFormData(prev => ({
        ...prev,
        conditions: prev.conditions.filter((_, i) => i !== index),
      }));
    }, []);

    const handleUpdateCondition = useCallback((index: number, field: keyof AlertConditionConfig, value: any) => {
      setFormData(prev => {
        const newConditions = [...prev.conditions];
        newConditions[index] = { ...newConditions[index], [field]: value };
        return { ...prev, conditions: newConditions };
      });
      setFormErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[`condition_${index}_${field}`];
        return newErrors;
      });
    }, []);

    // ========================================================================
    // GESTION DES ACTIONS
    // ========================================================================

    const handleAddAction = useCallback(() => {
      setFormData(prev => ({
        ...prev,
        actions: [
          ...prev.actions,
          {
            type: 'notify',
            config: {},
          },
        ],
      }));
      setIsAddingAction(false);
    }, []);

    const handleRemoveAction = useCallback((index: number) => {
      setFormData(prev => ({
        ...prev,
        actions: prev.actions.filter((_, i) => i !== index),
      }));
    }, []);

    const handleUpdateAction = useCallback((index: number, field: keyof AlertActionConfig, value: any) => {
      setFormData(prev => {
        const newActions = [...prev.actions];
        newActions[index] = { ...newActions[index], [field]: value };
        return { ...prev, actions: newActions };
      });
    }, []);

    // ========================================================================
    // CHANNELS
    // ========================================================================

    const handleToggleChannel = useCallback((channel: AlertChannel) => {
      setFormData(prev => {
        const channels = prev.channels.includes(channel)
          ? prev.channels.filter(c => c !== channel)
          : [...prev.channels, channel];
        return { ...prev, channels };
      });
      setFormErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors.channels;
        return newErrors;
      });
    }, []);

    // ========================================================================
    // TAGS
    // ========================================================================

    const handleAddTag = useCallback((tag: string) => {
      const trimmed = tag.trim();
      if (!trimmed || formData.tags?.includes(trimmed)) return;

      setFormData(prev => ({
        ...prev,
        tags: [...(prev.tags || []), trimmed],
      }));
    }, [formData.tags]);

    const handleRemoveTag = useCallback((tag: string) => {
      setFormData(prev => ({
        ...prev,
        tags: prev.tags?.filter(t => t !== tag) || [],
      }));
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
          title: mode === 'create' ? 'Alerte créée' : 'Alerte mise à jour',
          description: `L'alerte "${formData.name}" a été ${mode === 'create' ? 'créée' : 'mise à jour'} avec succès`,
          variant: 'success',
        });

        if (debug) {
          console.log('Alert saved:', formData);
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
    }, [isSubmitting, isLoading, disabled, formData, validate, mode, onSubmit, onSuccess, onError, toast, debug]);

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
        {/* Nom et description */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Nom <span className="text-red-500">*</span>
          </label>
          <Input
            type="text"
            placeholder="Ma super alerte"
            value={formData.name}
            onChange={(e) => handleFieldChange('name', e.target.value)}
            error={formErrors.name}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Description
          </label>
          <textarea
            className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-3 text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:focus:ring-brand-500/20"
            rows={2}
            placeholder="Description de l'alerte..."
            value={formData.description || ''}
            onChange={(e) => handleFieldChange('description', e.target.value)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Type d'alerte
            </label>
            <Select
              options={ALERT_TYPES.map(t => ({ value: t.value, label: `${t.label} - ${t.description}` }))}
              value={formData.type}
              onChange={(value) => handleFieldChange('type', value as AlertType)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Priorité
            </label>
            <Select
              options={ALERT_PRIORITIES.map(p => ({ value: p.value, label: `${p.label} (${p.score})` }))}
              value={formData.priority}
              onChange={(value) => handleFieldChange('priority', value as AlertPriority)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Statut
            </label>
            <Select
              options={ALERT_STATUSES.map(s => ({ value: s.value, label: s.label }))}
              value={formData.status}
              onChange={(value) => handleFieldChange('status', value as AlertStatus)}
              disabled={disabled || isSubmitting || isLoading || mode === 'view'}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Tags
            </label>
            <div className="flex flex-wrap gap-1 p-2 border border-gray-200 dark:border-gray-700 rounded-lg min-h-[2.5rem]">
              {formData.tags?.map((tag) => (
                <Badge key={tag} variant="outline" className="flex items-center gap-1">
                  <TagIcon className="h-3 w-3" />
                  {tag}
                  {!disabled && !isSubmitting && !isLoading && (
                    <button
                      type="button"
                      className="ml-1 text-gray-400 hover:text-red-500"
                      onClick={() => handleRemoveTag(tag)}
                    >
                      <XMarkIcon className="h-3 w-3" />
                    </button>
                  )}
                </Badge>
              ))}
              {!disabled && !isSubmitting && !isLoading && (
                <input
                  type="text"
                  className="flex-1 min-w-[60px] bg-transparent outline-none text-sm placeholder-gray-400 dark:placeholder-gray-500"
                  placeholder="Ajouter un tag..."
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleAddTag(e.currentTarget.value);
                      e.currentTarget.value = '';
                    }
                  }}
                  onBlur={(e) => {
                    if (e.target.value) {
                      handleAddTag(e.target.value);
                      e.target.value = '';
                    }
                  }}
                />
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <Switch
              checked={formData.silent}
              onCheckedChange={(checked) => handleFieldChange('silent', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
            <span className="text-sm text-gray-600 dark:text-gray-300">Mode silencieux</span>
          </div>
          <div className="flex items-center gap-2">
            <Switch
              checked={formData.recurring}
              onCheckedChange={(checked) => handleFieldChange('recurring', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
            <span className="text-sm text-gray-600 dark:text-gray-300">Récurrente</span>
          </div>
        </div>

        {formData.recurring && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Intervalle de récurrence (ms)
              </label>
              <Input
                type="number"
                value={formData.recurrenceInterval || 60000}
                onChange={(e) => handleFieldChange('recurrenceInterval', parseInt(e.target.value) || 60000)}
                disabled={disabled || isSubmitting || isLoading}
                step={1000}
                min={1000}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Délai de refroidissement (ms)
              </label>
              <Input
                type="number"
                value={formData.cooldownPeriod || 30000}
                onChange={(e) => handleFieldChange('cooldownPeriod', parseInt(e.target.value) || 30000)}
                disabled={disabled || isSubmitting || isLoading}
                step={1000}
                min={0}
              />
            </div>
          </div>
        )}
      </div>
    );

    // ========================================================================
    // RENDU DE L'ONGLET CONDITIONS
    // ========================================================================

    const renderConditionsTab = () => (
      <div className="space-y-6">
        {formData.conditions.length === 0 ? (
          <div className="rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 p-8 text-center">
            <ChartLineIcon className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
              Aucune condition configurée
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              Ajoutez une condition pour déclencher l'alerte
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {formData.conditions.map((condition, index) => (
              <div
                key={index}
                className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Condition {index + 1}
                  </h4>
                  {formData.conditions.length > 1 && !disabled && (
                    <button
                      type="button"
                      className="text-gray-400 hover:text-red-500"
                      onClick={() => handleRemoveCondition(index)}
                    >
                      <TrashIcon className="h-4 w-4" />
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Symbole
                    </label>
                    <Select
                      options={availableSymbols.map(s => ({ value: s, label: s }))}
                      value={condition.symbol}
                      onChange={(value) => handleUpdateCondition(index, 'symbol', value)}
                      disabled={disabled || isSubmitting || isLoading}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Condition
                    </label>
                    <Select
                      options={ALERT_CONDITIONS.map(c => ({ value: c.value, label: c.label }))}
                      value={condition.type}
                      onChange={(value) => handleUpdateCondition(index, 'type', value as AlertCondition)}
                      disabled={disabled || isSubmitting || isLoading}
                    />
                  </div>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Valeur seuil
                    </label>
                    <Input
                      type="number"
                      value={condition.value}
                      onChange={(e) => handleUpdateCondition(index, 'value', parseFloat(e.target.value) || 0)}
                      error={formErrors[`condition_${index}_value`]}
                      disabled={disabled || isSubmitting || isLoading}
                      step={0.01}
                    />
                  </div>
                  {(condition.type === 'between' || condition.type === 'outside') && (
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        Valeur seuil 2
                      </label>
                      <Input
                        type="number"
                        value={condition.value2 || 0}
                        onChange={(e) => handleUpdateCondition(index, 'value2', parseFloat(e.target.value) || 0)}
                        error={formErrors[`condition_${index}_value2`]}
                        disabled={disabled || isSubmitting || isLoading}
                        step={0.01}
                      />
                    </div>
                  )}
                </div>

                {condition.type === 'change_percent' && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Période (barres)
                    </label>
                    <Input
                      type="number"
                      value={condition.params?.period || 1}
                      onChange={(e) => handleUpdateCondition(index, 'params', { 
                        ...condition.params, 
                        period: parseInt(e.target.value) || 1 
                      })}
                      disabled={disabled || isSubmitting || isLoading}
                      min={1}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {!disabled && !isSubmitting && !isLoading && (
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={handleAddCondition}
          >
            <PlusIcon className="h-4 w-4 mr-2" />
            Ajouter une condition
          </Button>
        )}
      </div>
    );

    // ========================================================================
    // RENDU DE L'ONGLET ACTIONS
    // ========================================================================

    const renderActionsTab = () => (
      <div className="space-y-6">
        {formData.actions.length === 0 ? (
          <div className="rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 p-8 text-center">
            <Cog6ToothIcon className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
              Aucune action configurée
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              Ajoutez une action à exécuter lors du déclenchement
            </p>
          </div>
        ) : (
          <div className="space-y-3">
            {formData.actions.map((action, index) => (
              <div
                key={index}
                className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-3"
              >
                <div className="flex items-center justify-between">
                  <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Action {index + 1}
                  </h4>
                  {formData.actions.length > 1 && !disabled && (
                    <button
                      type="button"
                      className="text-gray-400 hover:text-red-500"
                      onClick={() => handleRemoveAction(index)}
                    >
                      <TrashIcon className="h-4 w-4" />
                    </button>
                  )}
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Type d'action
                    </label>
                    <Select
                      options={availableActions.map(a => ({ 
                        value: a, 
                        label: ALERT_ACTIONS.find(act => act.value === a)?.label || a 
                      }))}
                      value={action.type}
                      onChange={(value) => handleUpdateAction(index, 'type', value as AlertAction)}
                      disabled={disabled || isSubmitting || isLoading}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Délai (ms)
                    </label>
                    <Input
                      type="number"
                      value={action.delay || 0}
                      onChange={(e) => handleUpdateAction(index, 'delay', parseInt(e.target.value) || 0)}
                      disabled={disabled || isSubmitting || isLoading}
                      step={100}
                      min={0}
                    />
                  </div>
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Nombre max d'exécutions
                  </label>
                  <Input
                    type="number"
                    value={action.maxExecutions || 0}
                    onChange={(e) => handleUpdateAction(index, 'maxExecutions', parseInt(e.target.value) || 0)}
                    disabled={disabled || isSubmitting || isLoading}
                    min={0}
                  />
                  <p className="text-xs text-gray-400">0 = illimité</p>
                </div>

                {action.type === 'webhook' && (
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      URL du webhook
                    </label>
                    <Input
                      type="url"
                      placeholder="https://api.exemple.com/webhook"
                      value={action.config?.url || ''}
                      onChange={(e) => handleUpdateAction(index, 'config', { ...action.config, url: e.target.value })}
                      disabled={disabled || isSubmitting || isLoading}
                    />
                  </div>
                )}

                {action.type === 'order' && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        Type d'ordre
                      </label>
                      <Select
                        options={[
                          { value: 'market', label: 'Marché' },
                          { value: 'limit', label: 'Limite' },
                          { value: 'stop', label: 'Stop' },
                        ]}
                        value={action.config?.orderType || 'market'}
                        onChange={(e) => handleUpdateAction(index, 'config', { ...action.config, orderType: e })}
                        disabled={disabled || isSubmitting || isLoading}
                      />
                    </div>
                    <div className="space-y-2">
                      <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                        Quantité
                      </label>
                      <Input
                        type="number"
                        value={action.config?.quantity || 0}
                        onChange={(e) => handleUpdateAction(index, 'config', { ...action.config, quantity: parseFloat(e.target.value) || 0 })}
                        disabled={disabled || isSubmitting || isLoading}
                        step={0.001}
                        min={0.001}
                      />
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}

        {!disabled && !isSubmitting && !isLoading && (
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={handleAddAction}
          >
            <PlusIcon className="h-4 w-4 mr-2" />
            Ajouter une action
          </Button>
        )}
      </div>
    );

    // ========================================================================
    // RENDU DE L'ONGLET SCHEDULE
    // ========================================================================

    const renderScheduleTab = () => (
      <div className="space-y-6">
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Fréquence
          </label>
          <Select
            options={ALERT_FREQUENCIES}
            value={formData.schedule?.frequency || 'once'}
            onChange={(value) => {
              const schedule = formData.schedule || { frequency: 'once' };
              handleFieldChange('schedule', { ...schedule, frequency: value as AlertFrequency });
            }}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        {formData.schedule?.frequency === 'daily' && (
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Heure de déclenchement
            </label>
            <Input
              type="time"
              value={formData.schedule?.time || '09:00'}
              onChange={(e) => {
                const schedule = formData.schedule || { frequency: 'daily' };
                handleFieldChange('schedule', { ...schedule, time: e.target.value });
              }}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        )}

        {formData.schedule?.frequency === 'weekly' && (
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Jour de la semaine
            </label>
            <Select
              options={[
                { value: '0', label: 'Dimanche' },
                { value: '1', label: 'Lundi' },
                { value: '2', label: 'Mardi' },
                { value: '3', label: 'Mercredi' },
                { value: '4', label: 'Jeudi' },
                { value: '5', label: 'Vendredi' },
                { value: '6', label: 'Samedi' },
              ]}
              value={String(formData.schedule?.dayOfWeek || 1)}
              onChange={(value) => {
                const schedule = formData.schedule || { frequency: 'weekly' };
                handleFieldChange('schedule', { ...schedule, dayOfWeek: parseInt(value) });
              }}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        )}

        {formData.schedule?.frequency === 'monthly' && (
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Jour du mois
            </label>
            <Input
              type="number"
              min={1}
              max={31}
              value={formData.schedule?.dayOfMonth || 1}
              onChange={(e) => {
                const schedule = formData.schedule || { frequency: 'monthly' };
                handleFieldChange('schedule', { ...schedule, dayOfMonth: parseInt(e.target.value) || 1 });
              }}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        )}

        <Separator />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Date de début
            </label>
            <Input
              type="datetime-local"
              value={formData.schedule?.startDate ? new Date(formData.schedule.startDate).toISOString().slice(0, 16) : ''}
              onChange={(e) => {
                const schedule = formData.schedule || { frequency: 'once' };
                handleFieldChange('schedule', { 
                  ...schedule, 
                  startDate: e.target.value ? new Date(e.target.value) : undefined 
                });
              }}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Date de fin
            </label>
            <Input
              type="datetime-local"
              value={formData.schedule?.endDate ? new Date(formData.schedule.endDate).toISOString().slice(0, 16) : ''}
              onChange={(e) => {
                const schedule = formData.schedule || { frequency: 'once' };
                handleFieldChange('schedule', { 
                  ...schedule, 
                  endDate: e.target.value ? new Date(e.target.value) : undefined 
                });
              }}
              disabled={disabled || isSubmitting || isLoading}
            />
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
                {formData.status === 'active' ? (
                  <Badge variant="success" size="sm" className="flex items-center gap-1">
                    <span className="inline-block h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                    Active
                  </Badge>
                ) : (
                  <Badge variant="outline" size="sm">
                    {formData.status}
                  </Badge>
                )}
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
              { id: 'general', label: '⚙️ Général' },
              { id: 'conditions', label: '📊 Conditions' },
              { id: 'actions', label: '⚡ Actions' },
              { id: 'schedule', label: '📅 Horaire' },
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
                {activeTab === 'conditions' && renderConditionsTab()}
                {activeTab === 'actions' && renderActionsTab()}
                {activeTab === 'schedule' && renderScheduleTab()}
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
                {isSubmitting ? 'Sauvegarde...' : mode === 'create' ? 'Créer l\'alerte' : 'Mettre à jour'}
              </Button>
            </div>
          </form>
        </CardContent>

        {/* Footer */}
        <CardFooter className="border-t border-gray-200 dark:border-gray-700 px-4 py-2 text-xs text-gray-400">
          <div className="flex items-center justify-between w-full">
            <span>
              {formData.conditions.length} condition{formData.conditions.length > 1 ? 's' : ''} • 
              {formData.actions.length} action{formData.actions.length > 1 ? 's' : ''}
            </span>
            <span>
              {formData.channels.length} canal{formData.channels.length > 1 ? 'x' : ''} • 
              Priorité: {formData.priority}
            </span>
          </div>
        </CardFooter>
      </Card>
    );
  }
);

AlertForm.displayName = 'AlertForm';

// ============================================================================
// EXPORTS
// ============================================================================

export default AlertForm;

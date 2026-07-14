// apps/web/src/components/forms/settings/APISettingsForm.tsx
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
  KeyIcon,
  PlusIcon,
  MinusIcon,
  CheckIcon,
  XMarkIcon,
  EyeIcon,
  EyeSlashIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ClipboardIcon,
  DocumentDuplicateIcon,
  TrashIcon,
  PencilIcon,
  Cog6ToothIcon,
  AdjustmentsHorizontalIcon,
  GlobeAltIcon,
  ShieldCheckIcon,
  ClockIcon,
  ChartBarIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  WifiIcon,
  WifiSlashIcon,
  ServerIcon,
  CloudIcon,
  DatabaseIcon,
  LinkIcon,
  LinkSlashIcon,
  LockClosedIcon,
  LockOpenIcon,
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
import { ScrollArea } from '@/components/common/ScrollArea';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type APIProvider = 'nexus' | 'openai' | 'anthropic' | 'google' | 'aws' | 'azure' | 'custom';
export type APIStatus = 'active' | 'inactive' | 'error' | 'rate_limited';
export type APIAuthType = 'api_key' | 'oauth2' | 'jwt' | 'basic' | 'bearer' | 'none';
export type APIRateLimitUnit = 'second' | 'minute' | 'hour' | 'day' | 'month';

export interface APIEndpoint {
  /** Nom de l'endpoint */
  name: string;
  /** URL de l'endpoint */
  url: string;
  /** Méthode HTTP */
  method: 'GET' | 'POST' | 'PUT' | 'DELETE' | 'PATCH';
  /** Description */
  description?: string;
  /** Statut */
  status: APIStatus;
  /** Latence moyenne (ms) */
  latency?: number;
  /** Nombre de requêtes */
  requests?: number;
  /** Taux d'erreur (%) */
  errorRate?: number;
}

export interface APIConfig {
  /** Fournisseur API */
  provider: APIProvider;
  /** Nom de l'API */
  name: string;
  /** Clé API (masquée) */
  apiKey?: string;
  /** URL de base */
  baseUrl: string;
  /** Type d'authentification */
  authType: APIAuthType;
  /** Endpoints configurés */
  endpoints: APIEndpoint[];
  /** Taux de limitation */
  rateLimit: {
    /** Nombre de requêtes */
    requests: number;
    /** Période */
    period: number;
    /** Unité */
    unit: APIRateLimitUnit;
  };
  /** Est activé */
  enabled: boolean;
  /** Version */
  version?: string;
  /** Délai d'expiration (ms) */
  timeout?: number;
  /** Nombre de retries */
  retries?: number;
  /** Est-ce que les logs sont activés */
  loggingEnabled?: boolean;
  /** Est-ce que le cache est activé */
  cacheEnabled?: boolean;
  /** Durée du cache (ms) */
  cacheDuration?: number;
  /** Headers personnalisés */
  customHeaders?: Record<string, string>;
  /** Métadonnées */
  metadata?: Record<string, any>;
}

export interface APISettingsFormData {
  /** Configuration API */
  config: APIConfig;
  /** Logs d'API */
  logs?: Array<{
    timestamp: Date;
    endpoint: string;
    status: number;
    duration: number;
    error?: string;
  }>;
  /** Statistiques */
  stats?: {
    totalRequests: number;
    successRate: number;
    averageLatency: number;
    errorRate: number;
    rateLimitUsage: number;
  };
}

export interface APISettingsFormProps {
  // --- Contrôle ---
  /** Données initiales */
  initialData?: Partial<APISettingsFormData>;
  /** Callback de soumission */
  onSubmit?: (data: APISettingsFormData) => void | Promise<void>;
  /** Callback de succès */
  onSuccess?: (data: APISettingsFormData) => void;
  /** Callback d'erreur */
  onError?: (error: string) => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de changement */
  onChange?: (data: APISettingsFormData) => void;

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

const PROVIDERS: Record<APIProvider, { label: string; icon: React.ReactNode; color: string }> = {
  nexus: {
    label: 'Nexus AI',
    icon: <ShieldCheckIcon className="h-5 w-5" />,
    color: 'text-brand-500',
  },
  openai: {
    label: 'OpenAI',
    icon: <Cog6ToothIcon className="h-5 w-5" />,
    color: 'text-green-500',
  },
  anthropic: {
    label: 'Anthropic',
    icon: <Cog6ToothIcon className="h-5 w-5" />,
    color: 'text-purple-500',
  },
  google: {
    label: 'Google AI',
    icon: <Cog6ToothIcon className="h-5 w-5" />,
    color: 'text-blue-500',
  },
  aws: {
    label: 'AWS',
    icon: <CloudIcon className="h-5 w-5" />,
    color: 'text-orange-500',
  },
  azure: {
    label: 'Azure',
    icon: <CloudIcon className="h-5 w-5" />,
    color: 'text-blue-600',
  },
  custom: {
    label: 'Personnalisé',
    icon: <Cog6ToothIcon className="h-5 w-5" />,
    color: 'text-gray-500',
  },
};

const AUTH_TYPES: { value: APIAuthType; label: string }[] = [
  { value: 'api_key', label: 'Clé API' },
  { value: 'oauth2', label: 'OAuth 2.0' },
  { value: 'jwt', label: 'JWT' },
  { value: 'basic', label: 'Basic Auth' },
  { value: 'bearer', label: 'Bearer Token' },
  { value: 'none', label: 'Aucune' },
];

const STATUS_MAP: Record<APIStatus, { color: string; label: string; icon: React.ReactNode }> = {
  active: {
    color: 'text-green-500',
    label: 'Actif',
    icon: <CheckCircleIcon className="h-4 w-4" />,
  },
  inactive: {
    color: 'text-gray-400',
    label: 'Inactif',
    icon: <XMarkIcon className="h-4 w-4" />,
  },
  error: {
    color: 'text-red-500',
    label: 'Erreur',
    icon: <ExclamationCircleIcon className="h-4 w-4" />,
  },
  rate_limited: {
    color: 'text-yellow-500',
    label: 'Limité',
    icon: <ExclamationTriangleIcon className="h-4 w-4" />,
  },
};

const RATE_LIMIT_UNITS: { value: APIRateLimitUnit; label: string }[] = [
  { value: 'second', label: 'Par seconde' },
  { value: 'minute', label: 'Par minute' },
  { value: 'hour', label: 'Par heure' },
  { value: 'day', label: 'Par jour' },
  { value: 'month', label: 'Par mois' },
];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const APISettingsForm = forwardRef<HTMLDivElement, APISettingsFormProps>(
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
      title = 'Paramètres API',
      subtitle = 'Configurez les intégrations API',
      className,
      variant = 'default',

      // États
      isLoading = false,
      error = null,
      success = null,
      disabled = false,

      // Accessibilité
      ariaLabel = 'Configuration API',
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
    const apiKeyInputRef = useRef<HTMLInputElement>(null);

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [formData, setFormData] = useState<APISettingsFormData>({
      config: {
        provider: 'nexus',
        name: 'API Nexus',
        baseUrl: 'https://api.nexus.com/v1',
        authType: 'api_key',
        endpoints: [],
        rateLimit: {
          requests: 100,
          period: 1,
          unit: 'minute',
        },
        enabled: true,
        timeout: 30000,
        retries: 3,
        loggingEnabled: true,
        cacheEnabled: true,
        cacheDuration: 300000,
        customHeaders: {},
        ...initialData.config,
      },
      logs: [],
      stats: {
        totalRequests: 0,
        successRate: 100,
        averageLatency: 0,
        errorRate: 0,
        rateLimitUsage: 0,
      },
      ...initialData,
    });

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [showApiKey, setShowApiKey] = useState(false);
    const [activeTab, setActiveTab] = useState<'general' | 'endpoints' | 'security' | 'logs'>('general');
    const [newEndpoint, setNewEndpoint] = useState<Partial<APIEndpoint>>({
      method: 'GET',
      status: 'active',
    });
    const [editingEndpointIndex, setEditingEndpointIndex] = useState<number | null>(null);
    const [isAddingEndpoint, setIsAddingEndpoint] = useState(false);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validate = useCallback((): boolean => {
      const errors: Record<string, string> = {};

      if (!formData.config.name) {
        errors.name = 'Le nom de l\'API est requis';
      }

      if (!formData.config.baseUrl) {
        errors.baseUrl = 'L\'URL de base est requise';
      }

      if (formData.config.authType === 'api_key' && !formData.config.apiKey) {
        errors.apiKey = 'La clé API est requise';
      }

      if (formData.config.rateLimit.requests <= 0) {
        errors.rateLimit = 'Le nombre de requêtes doit être supérieur à 0';
      }

      setFormErrors(errors);
      return Object.keys(errors).length === 0;
    }, [formData]);

    // ========================================================================
    // GESTIONNAIRES DE CHAMPS
    // ========================================================================

    const handleConfigChange = useCallback(<K extends keyof APIConfig>(
      field: K,
      value: APIConfig[K]
    ) => {
      setFormData(prev => ({
        ...prev,
        config: { ...prev.config, [field]: value },
      }));
      setFormErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }, []);

    const handleNestedConfigChange = useCallback((
      parent: 'rateLimit' | 'customHeaders',
      field: string,
      value: any
    ) => {
      setFormData(prev => ({
        ...prev,
        config: {
          ...prev.config,
          [parent]: {
            ...prev.config[parent],
            [field]: value,
          },
        },
      }));
    }, []);

    const handleEndpointChange = useCallback((
      index: number,
      field: keyof APIEndpoint,
      value: any
    ) => {
      setFormData(prev => {
        const newEndpoints = [...prev.config.endpoints];
        newEndpoints[index] = { ...newEndpoints[index], [field]: value };
        return { ...prev, config: { ...prev.config, endpoints: newEndpoints } };
      });
    }, []);

    const handleAddEndpoint = useCallback(() => {
      if (!newEndpoint.name || !newEndpoint.url) {
        toast({
          title: 'Erreur',
          description: 'Le nom et l\'URL sont requis',
          variant: 'destructive',
        });
        return;
      }

      setFormData(prev => ({
        ...prev,
        config: {
          ...prev.config,
          endpoints: [
            ...prev.config.endpoints,
            {
              name: newEndpoint.name,
              url: newEndpoint.url,
              method: newEndpoint.method || 'GET',
              status: newEndpoint.status || 'active',
              description: newEndpoint.description,
            } as APIEndpoint,
          ],
        },
      }));

      setNewEndpoint({ method: 'GET', status: 'active' });
      setIsAddingEndpoint(false);
      
      toast({
        title: 'Endpoint ajouté',
        description: `L'endpoint "${newEndpoint.name}" a été ajouté`,
        duration: 2000,
      });
    }, [newEndpoint, toast]);

    const handleRemoveEndpoint = useCallback((index: number) => {
      const endpoint = formData.config.endpoints[index];
      setFormData(prev => ({
        ...prev,
        config: {
          ...prev.config,
          endpoints: prev.config.endpoints.filter((_, i) => i !== index),
        },
      }));

      toast({
        title: 'Endpoint supprimé',
        description: `L'endpoint "${endpoint.name}" a été supprimé`,
        duration: 2000,
      });
    }, [formData.config.endpoints, toast]);

    const handleEditEndpoint = useCallback((index: number) => {
      setEditingEndpointIndex(index);
      setNewEndpoint(formData.config.endpoints[index]);
      setIsAddingEndpoint(true);
    }, [formData.config.endpoints]);

    const handleUpdateEndpoint = useCallback(() => {
      if (editingEndpointIndex === null) return;
      if (!newEndpoint.name || !newEndpoint.url) {
        toast({
          title: 'Erreur',
          description: 'Le nom et l\'URL sont requis',
          variant: 'destructive',
        });
        return;
      }

      setFormData(prev => {
        const newEndpoints = [...prev.config.endpoints];
        newEndpoints[editingEndpointIndex] = {
          ...newEndpoints[editingEndpointIndex],
          name: newEndpoint.name,
          url: newEndpoint.url,
          method: newEndpoint.method || 'GET',
          status: newEndpoint.status || 'active',
          description: newEndpoint.description,
        };
        return { ...prev, config: { ...prev.config, endpoints: newEndpoints } };
      });

      setEditingEndpointIndex(null);
      setNewEndpoint({ method: 'GET', status: 'active' });
      setIsAddingEndpoint(false);

      toast({
        title: 'Endpoint mis à jour',
        description: `L'endpoint a été mis à jour`,
        duration: 2000,
      });
    }, [editingEndpointIndex, newEndpoint, toast]);

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
          title: 'Configuration sauvegardée',
          description: 'Les paramètres API ont été mis à jour avec succès',
          variant: 'success',
        });

        if (debug) {
          console.log('API settings saved:', formData);
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
    // RENDU
    // ========================================================================

    const renderGeneralTab = () => (
      <div className="space-y-6">
        {/* Informations générales */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Fournisseur
            </label>
            <Select
              options={Object.entries(PROVIDERS).map(([value, { label }]) => ({
                value,
                label,
              }))}
              value={formData.config.provider}
              onChange={(value) => handleConfigChange('provider', value as APIProvider)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Nom de l'API
            </label>
            <Input
              type="text"
              value={formData.config.name}
              onChange={(e) => handleConfigChange('name', e.target.value)}
              error={formErrors.name}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            URL de base
          </label>
          <Input
            type="url"
            placeholder="https://api.exemple.com/v1"
            value={formData.config.baseUrl}
            onChange={(e) => handleConfigChange('baseUrl', e.target.value)}
            error={formErrors.baseUrl}
            disabled={disabled || isSubmitting || isLoading}
            prefix={<GlobeAltIcon className="h-4 w-4 text-gray-400" />}
          />
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Version
            </label>
            <Input
              type="text"
              placeholder="v1"
              value={formData.config.version || ''}
              onChange={(e) => handleConfigChange('version', e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Délai d'expiration (ms)
            </label>
            <Input
              type="number"
              value={formData.config.timeout || 30000}
              onChange={(e) => handleConfigChange('timeout', parseInt(e.target.value) || 30000)}
              disabled={disabled || isSubmitting || isLoading}
              step={1000}
              min={1000}
            />
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">API activée</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Activer ou désactiver l'API</p>
          </div>
          <Switch
            checked={formData.config.enabled}
            onCheckedChange={(checked) => handleConfigChange('enabled', checked)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <Separator />

        {/* Taux de limitation */}
        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">Taux de limitation</h4>

        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Requêtes
            </label>
            <Input
              type="number"
              value={formData.config.rateLimit.requests}
              onChange={(e) => handleNestedConfigChange('rateLimit', 'requests', parseInt(e.target.value) || 0)}
              error={formErrors.rateLimit}
              disabled={disabled || isSubmitting || isLoading}
              min={1}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Période
            </label>
            <Input
              type="number"
              value={formData.config.rateLimit.period}
              onChange={(e) => handleNestedConfigChange('rateLimit', 'period', parseInt(e.target.value) || 1)}
              disabled={disabled || isSubmitting || isLoading}
              min={1}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Unité
            </label>
            <Select
              options={RATE_LIMIT_UNITS}
              value={formData.config.rateLimit.unit}
              onChange={(value) => handleNestedConfigChange('rateLimit', 'unit', value)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-3 text-sm text-gray-500 dark:text-gray-400">
          <InformationCircleIcon className="inline h-4 w-4 mr-1" />
          Limite: {formData.config.rateLimit.requests} requêtes par {formData.config.rateLimit.period} {formData.config.rateLimit.unit}(s)
        </div>
      </div>
    );

    const renderEndpointsTab = () => (
      <div className="space-y-6">
        {/* Liste des endpoints */}
        <div className="space-y-3">
          {formData.config.endpoints.length === 0 ? (
            <div className="rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 p-8 text-center">
              <LinkIcon className="mx-auto h-12 w-12 text-gray-400" />
              <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                Aucun endpoint configuré
              </p>
              <p className="text-xs text-gray-400 dark:text-gray-500">
                Ajoutez des endpoints pour configurer les points d'accès API
              </p>
            </div>
          ) : (
            formData.config.endpoints.map((endpoint, index) => {
              const statusInfo = STATUS_MAP[endpoint.status] || STATUS_MAP.inactive;

              return (
                <div
                  key={index}
                  className="flex items-center gap-3 rounded-lg border border-gray-200 dark:border-gray-700 p-3"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <Badge variant="outline" size="xs" className="font-mono">
                        {endpoint.method}
                      </Badge>
                      <span className="font-medium">{endpoint.name}</span>
                      <span className={cn('flex items-center gap-1 text-xs', statusInfo.color)}>
                        {statusInfo.icon}
                        {statusInfo.label}
                      </span>
                    </div>
                    <p className="text-sm text-gray-500 dark:text-gray-400 truncate">
                      {endpoint.url}
                    </p>
                    {endpoint.description && (
                      <p className="text-xs text-gray-400 dark:text-gray-500">
                        {endpoint.description}
                      </p>
                    )}
                    {endpoint.latency !== undefined && (
                      <div className="mt-1 flex items-center gap-3 text-xs text-gray-400">
                        <span>Latence: {endpoint.latency}ms</span>
                        <span>Requêtes: {endpoint.requests || 0}</span>
                        <span>Erreurs: {endpoint.errorRate || 0}%</span>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    <Tooltip content="Modifier">
                      <button
                        type="button"
                        className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                        onClick={() => handleEditEndpoint(index)}
                      >
                        <PencilIcon className="h-4 w-4" />
                      </button>
                    </Tooltip>
                    <Tooltip content="Supprimer">
                      <button
                        type="button"
                        className="rounded p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                        onClick={() => handleRemoveEndpoint(index)}
                      >
                        <TrashIcon className="h-4 w-4" />
                      </button>
                    </Tooltip>
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Ajout/Modification d'endpoint */}
        {isAddingEndpoint && (
          <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {editingEndpointIndex !== null ? 'Modifier l\'endpoint' : 'Nouvel endpoint'}
              </h4>
              <button
                type="button"
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                onClick={() => {
                  setIsAddingEndpoint(false);
                  setEditingEndpointIndex(null);
                  setNewEndpoint({ method: 'GET', status: 'active' });
                }}
              >
                <XMarkIcon className="h-4 w-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Nom
                </label>
                <Input
                  type="text"
                  placeholder="users"
                  value={newEndpoint.name || ''}
                  onChange={(e) => setNewEndpoint({ ...newEndpoint, name: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Méthode
                </label>
                <Select
                  options={[
                    { value: 'GET', label: 'GET' },
                    { value: 'POST', label: 'POST' },
                    { value: 'PUT', label: 'PUT' },
                    { value: 'DELETE', label: 'DELETE' },
                    { value: 'PATCH', label: 'PATCH' },
                  ]}
                  value={newEndpoint.method || 'GET'}
                  onChange={(value) => setNewEndpoint({ ...newEndpoint, method: value as any })}
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                URL
              </label>
              <Input
                type="text"
                placeholder="/users"
                value={newEndpoint.url || ''}
                onChange={(e) => setNewEndpoint({ ...newEndpoint, url: e.target.value })}
              />
            </div>

            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Description
              </label>
              <Input
                type="text"
                placeholder="Récupère la liste des utilisateurs"
                value={newEndpoint.description || ''}
                onChange={(e) => setNewEndpoint({ ...newEndpoint, description: e.target.value })}
              />
            </div>

            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsAddingEndpoint(false);
                  setEditingEndpointIndex(null);
                  setNewEndpoint({ method: 'GET', status: 'active' });
                }}
              >
                Annuler
              </Button>
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={editingEndpointIndex !== null ? handleUpdateEndpoint : handleAddEndpoint}
              >
                {editingEndpointIndex !== null ? 'Mettre à jour' : 'Ajouter'}
              </Button>
            </div>
          </div>
        )}

        {!isAddingEndpoint && (
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => {
              setNewEndpoint({ method: 'GET', status: 'active' });
              setIsAddingEndpoint(true);
            }}
            disabled={disabled || isSubmitting || isLoading}
          >
            <PlusIcon className="h-4 w-4 mr-2" />
            Ajouter un endpoint
          </Button>
        )}
      </div>
    );

    const renderSecurityTab = () => (
      <div className="space-y-6">
        {/* Authentification */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Type d'authentification
          </label>
          <Select
            options={AUTH_TYPES}
            value={formData.config.authType}
            onChange={(value) => handleConfigChange('authType', value as APIAuthType)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        {formData.config.authType === 'api_key' && (
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Clé API
            </label>
            <div className="relative">
              <Input
                ref={apiKeyInputRef}
                type={showApiKey ? 'text' : 'password'}
                value={formData.config.apiKey || ''}
                onChange={(e) => handleConfigChange('apiKey', e.target.value)}
                error={formErrors.apiKey}
                disabled={disabled || isSubmitting || isLoading}
                placeholder="sk-..."
                className="pr-20"
              />
              <div className="absolute right-2 top-1/2 -translate-y-1/2 flex items-center gap-1">
                <button
                  type="button"
                  className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                  onClick={() => setShowApiKey(!showApiKey)}
                >
                  {showApiKey ? (
                    <EyeSlashIcon className="h-4 w-4" />
                  ) : (
                    <EyeIcon className="h-4 w-4" />
                  )}
                </button>
                <Tooltip content="Générer">
                  <button
                    type="button"
                    className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    onClick={() => {
                      const newKey = `sk-${Math.random().toString(36).substring(2, 15)}${Math.random().toString(36).substring(2, 15)}`;
                      handleConfigChange('apiKey', newKey);
                    }}
                  >
                    <ArrowPathIcon className="h-4 w-4" />
                  </button>
                </Tooltip>
              </div>
            </div>
          </div>
        )}

        <Separator />

        {/* Options de sécurité */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Logs activés</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Enregistrer les appels API</p>
          </div>
          <Switch
            checked={formData.config.loggingEnabled || false}
            onCheckedChange={(checked) => handleConfigChange('loggingEnabled', checked)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Cache activé</p>
            <p className="text-xs text-gray-500 dark:text-gray-400">Mettre en cache les réponses</p>
          </div>
          <Switch
            checked={formData.config.cacheEnabled || false}
            onCheckedChange={(checked) => handleConfigChange('cacheEnabled', checked)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        {formData.config.cacheEnabled && (
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Durée du cache (ms)
            </label>
            <Input
              type="number"
              value={formData.config.cacheDuration || 300000}
              onChange={(e) => handleConfigChange('cacheDuration', parseInt(e.target.value) || 300000)}
              disabled={disabled || isSubmitting || isLoading}
              step={1000}
              min={0}
            />
          </div>
        )}

        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Nombre de retries
          </label>
          <Input
            type="number"
            value={formData.config.retries || 3}
            onChange={(e) => handleConfigChange('retries', parseInt(e.target.value) || 3)}
            disabled={disabled || isSubmitting || isLoading}
            min={0}
            max={10}
          />
        </div>

        <Separator />

        {/* Headers personnalisés */}
        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">Headers personnalisés</h4>

        {Object.entries(formData.config.customHeaders || {}).length === 0 ? (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            Aucun header personnalisé configuré
          </p>
        ) : (
          Object.entries(formData.config.customHeaders || {}).map(([key, value]) => (
            <div key={key} className="flex items-center gap-2">
              <span className="text-sm font-mono text-gray-600 dark:text-gray-300">{key}:</span>
              <span className="text-sm text-gray-500 dark:text-gray-400">{value}</span>
              <button
                type="button"
                className="rounded p-1 text-gray-400 hover:text-red-600 transition-colors"
                onClick={() => {
                  const newHeaders = { ...formData.config.customHeaders };
                  delete newHeaders[key];
                  handleConfigChange('customHeaders', newHeaders);
                }}
              >
                <TrashIcon className="h-4 w-4" />
              </button>
            </div>
          ))
        )}

        <div className="flex gap-2">
          <Input
            type="text"
            placeholder="X-API-Key"
            className="flex-1"
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                const input = e.target as HTMLInputElement;
                const key = input.value.trim();
                if (key) {
                  const value = prompt(`Valeur pour ${key}:`);
                  if (value !== null) {
                    handleConfigChange('customHeaders', {
                      ...formData.config.customHeaders,
                      [key]: value,
                    });
                    input.value = '';
                  }
                }
              }
            }}
          />
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              const key = prompt('Nom du header:');
              if (key?.trim()) {
                const value = prompt(`Valeur pour ${key}:`);
                if (value !== null) {
                  handleConfigChange('customHeaders', {
                    ...formData.config.customHeaders,
                    [key.trim()]: value,
                  });
                }
              }
            }}
          >
            <PlusIcon className="h-4 w-4" />
          </Button>
        </div>
      </div>
    );

    const renderLogsTab = () => (
      <div className="space-y-6">
        {/* Statistiques */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-3 text-center">
            <div className="text-2xl font-bold text-gray-900 dark:text-white">
              {formData.stats?.totalRequests || 0}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Requêtes totales</div>
          </div>
          <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-3 text-center">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {formData.stats?.successRate || 0}%
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Taux de succès</div>
          </div>
          <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-3 text-center">
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {formData.stats?.averageLatency || 0}ms
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Latence moyenne</div>
          </div>
          <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-3 text-center">
            <div className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
              {formData.stats?.rateLimitUsage || 0}%
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Utilisation du taux</div>
          </div>
        </div>

        <Separator />

        {/* Logs */}
        <div className="space-y-2">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">Historique des appels</h4>

          {formData.logs && formData.logs.length > 0 ? (
            <ScrollArea className="max-h-64">
              <div className="space-y-1">
                {formData.logs.map((log, index) => (
                  <div
                    key={index}
                    className="flex items-center gap-3 rounded-lg border border-gray-200 dark:border-gray-700 p-2 text-sm"
                  >
                    <span className="text-xs text-gray-400">
                      {log.timestamp.toLocaleString()}
                    </span>
                    <Badge
                      variant={log.status < 400 ? 'success' : 'danger'}
                      size="xs"
                    >
                      {log.status}
                    </Badge>
                    <span className="flex-1 font-mono text-xs truncate">
                      {log.endpoint}
                    </span>
                    <span className="text-xs text-gray-400">{log.duration}ms</span>
                    {log.error && (
                      <span className="text-xs text-red-500">{log.error}</span>
                    )}
                  </div>
                ))}
              </div>
            </ScrollArea>
          ) : (
            <div className="rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 p-8 text-center">
              <ClockIcon className="mx-auto h-12 w-12 text-gray-400" />
              <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                Aucun log disponible
              </p>
              <p className="text-xs text-gray-400 dark:text-gray-500">
                Les logs apparaîtront ici lorsque l'API sera utilisée
              </p>
            </div>
          )}
        </div>

        <div className="flex justify-end">
          <Button
            type="button"
            variant="ghost"
            size="sm"
            onClick={() => {
              setFormData(prev => ({
                ...prev,
                logs: [],
              }));
              toast({
                title: 'Logs effacés',
                description: 'L\'historique des logs a été effacé',
                duration: 2000,
              });
            }}
            disabled={disabled || isSubmitting || isLoading}
          >
            <TrashIcon className="h-4 w-4 mr-2" />
            Effacer les logs
          </Button>
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
                {formData.config.enabled ? (
                  <Badge variant="success" size="sm" className="flex items-center gap-1">
                    <span className="inline-block h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                    Actif
                  </Badge>
                ) : (
                  <Badge variant="outline" size="sm" className="flex items-center gap-1">
                    <span className="inline-block h-1.5 w-1.5 rounded-full bg-gray-400" />
                    Inactif
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
              { id: 'endpoints', label: '🔗 Endpoints' },
              { id: 'security', label: '🔒 Sécurité' },
              { id: 'logs', label: '📊 Logs' },
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
                {activeTab === 'endpoints' && renderEndpointsTab()}
                {activeTab === 'security' && renderSecurityTab()}
                {activeTab === 'logs' && renderLogsTab()}
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
              Fournisseur: {PROVIDERS[formData.config.provider]?.label || formData.config.provider}
            </span>
            <span>
              {formData.config.endpoints.length} endpoints • 
              {formData.config.loggingEnabled ? ' Logs activés' : ' Logs désactivés'}
            </span>
          </div>
        </CardFooter>
      </Card>
    );
  }
);

APISettingsForm.displayName = 'APISettingsForm';

// ============================================================================
// EXPORTS
// ============================================================================

export default APISettingsForm;

// apps/web/src/components/forms/settings/BrokerSettingsForm.tsx
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
  BuildingOfficeIcon,
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
  UserIcon,
  BanknotesIcon,
  CurrencyDollarIcon,
  WalletIcon,
  CreditCardIcon,
  BuildingLibraryIcon,
  HomeIcon,
  OfficeBuildingIcon,
  TruckIcon,
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

export type BrokerProvider = 
  | 'binance' 
  | 'bybit' 
  | 'coinbase' 
  | 'kraken' 
  | 'oanda' 
  | 'alpaca' 
  | 'interactive_brokers' 
  | 'tradingview'
  | 'custom';

export type BrokerStatus = 'connected' | 'disconnected' | 'error' | 'pending' | 'rate_limited';
export type BrokerType = 'cex' | 'dex' | 'forex' | 'stocks' | 'futures' | 'options' | 'crypto';
export type BrokerAccountType = 'live' | 'demo' | 'paper';

export interface BrokerAccount {
  /** Identifiant du compte */
  id: string;
  /** Nom du compte */
  name: string;
  /** Type de compte */
  type: BrokerAccountType;
  /** Devise du compte */
  currency: string;
  /** Balance */
  balance: number;
  /** Balance disponible */
  available?: number;
  /** P&L total */
  totalPnl?: number;
  /** P&L en pourcentage */
  pnlPercent?: number;
  /** Statut du compte */
  status: 'active' | 'inactive' | 'suspended';
}

export interface BrokerConfig {
  /** Fournisseur */
  provider: BrokerProvider;
  /** Nom du broker */
  name: string;
  /** Type de broker */
  type: BrokerType;
  /** URL de l'API */
  apiUrl: string;
  /** Clé API */
  apiKey?: string;
  /** Secret API */
  apiSecret?: string;
  /** Passphrase (pour certains brokers) */
  passphrase?: string;
  /** Client ID */
  clientId?: string;
  /** Account ID */
  accountId?: string;
  /** Est activé */
  enabled: boolean;
  /** Est en mode test */
  testMode: boolean;
  /** Statut de la connexion */
  status: BrokerStatus;
  /** Dernière connexion */
  lastConnection?: Date;
  /** Latence (ms) */
  latency?: number;
  /** Taux de réussite */
  successRate?: number;
  /** Nombre de requêtes */
  totalRequests?: number;
  /** Comptes associés */
  accounts: BrokerAccount[];
  /** Timeout (ms) */
  timeout?: number;
  /** Retry attempts */
  retryAttempts?: number;
  /** Rate limit */
  rateLimit?: {
    requests: number;
    period: number;
    unit: 'second' | 'minute' | 'hour';
  };
  /** Headers personnalisés */
  customHeaders?: Record<string, string>;
  /** Métadonnées */
  metadata?: Record<string, any>;
}

export interface BrokerSettingsFormData {
  /** Configuration des brokers */
  brokers: BrokerConfig[];
  /** Broker actif par défaut */
  defaultBrokerId?: string;
  /** Préférences */
  preferences: {
    /** Auto-reconnect */
    autoReconnect: boolean;
    /** Retry sur échec */
    retryOnFailure: boolean;
    /** Log des requêtes */
    logRequests: boolean;
    /** Cache des réponses */
    cacheResponses: boolean;
    /** Durée du cache (ms) */
    cacheDuration: number;
    /** WebSocket activé */
    websocketEnabled: boolean;
    /** Reconnect automatique WebSocket */
    websocketAutoReconnect: boolean;
  };
}

export interface BrokerSettingsFormProps {
  // --- Contrôle ---
  /** Données initiales */
  initialData?: Partial<BrokerSettingsFormData>;
  /** Callback de soumission */
  onSubmit?: (data: BrokerSettingsFormData) => void | Promise<void>;
  /** Callback de succès */
  onSuccess?: (data: BrokerSettingsFormData) => void;
  /** Callback d'erreur */
  onError?: (error: string) => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de changement */
  onChange?: (data: BrokerSettingsFormData) => void;

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

const BROKER_PROVIDERS: Record<BrokerProvider, { label: string; icon: React.ReactNode; color: string; docs: string }> = {
  binance: {
    label: 'Binance',
    icon: <BuildingOfficeIcon className="h-5 w-5" />,
    color: 'text-yellow-500',
    docs: 'https://binance-docs.github.io/apidocs',
  },
  bybit: {
    label: 'Bybit',
    icon: <BuildingOfficeIcon className="h-5 w-5" />,
    color: 'text-blue-500',
    docs: 'https://bybit-exchange.github.io/docs',
  },
  coinbase: {
    label: 'Coinbase',
    icon: <BuildingOfficeIcon className="h-5 w-5" />,
    color: 'text-blue-600',
    docs: 'https://docs.cloud.coinbase.com',
  },
  kraken: {
    label: 'Kraken',
    icon: <BuildingOfficeIcon className="h-5 w-5" />,
    color: 'text-purple-500',
    docs: 'https://docs.kraken.com/rest',
  },
  oanda: {
    label: 'OANDA',
    icon: <BuildingOfficeIcon className="h-5 w-5" />,
    color: 'text-green-500',
    docs: 'https://developer.oanda.com/rest-v20',
  },
  alpaca: {
    label: 'Alpaca',
    icon: <BuildingOfficeIcon className="h-5 w-5" />,
    color: 'text-red-500',
    docs: 'https://alpaca.markets/docs',
  },
  interactive_brokers: {
    label: 'Interactive Brokers',
    icon: <BuildingOfficeIcon className="h-5 w-5" />,
    color: 'text-orange-500',
    docs: 'https://www.interactivebrokers.com/api',
  },
  tradingview: {
    label: 'TradingView',
    icon: <BuildingOfficeIcon className="h-5 w-5" />,
    color: 'text-blue-400',
    docs: 'https://www.tradingview.com/rest-api-spec',
  },
  custom: {
    label: 'Personnalisé',
    icon: <BuildingOfficeIcon className="h-5 w-5" />,
    color: 'text-gray-500',
    docs: '',
  },
};

const BROKER_TYPES: { value: BrokerType; label: string }[] = [
  { value: 'cex', label: 'CEX' },
  { value: 'dex', label: 'DEX' },
  { value: 'forex', label: 'Forex' },
  { value: 'stocks', label: 'Actions' },
  { value: 'futures', label: 'Futures' },
  { value: 'options', label: 'Options' },
  { value: 'crypto', label: 'Crypto-monnaies' },
];

const ACCOUNT_TYPES: { value: BrokerAccountType; label: string }[] = [
  { value: 'live', label: 'Compte réel' },
  { value: 'demo', label: 'Compte de démonstration' },
  { value: 'paper', label: 'Paper Trading' },
];

const STATUS_MAP: Record<BrokerStatus, { color: string; label: string; icon: React.ReactNode }> = {
  connected: {
    color: 'text-green-500',
    label: 'Connecté',
    icon: <CheckCircleIcon className="h-4 w-4" />,
  },
  disconnected: {
    color: 'text-gray-400',
    label: 'Déconnecté',
    icon: <XMarkIcon className="h-4 w-4" />,
  },
  error: {
    color: 'text-red-500',
    label: 'Erreur',
    icon: <ExclamationCircleIcon className="h-4 w-4" />,
  },
  pending: {
    color: 'text-yellow-500',
    label: 'En attente',
    icon: <ClockIcon className="h-4 w-4" />,
  },
  rate_limited: {
    color: 'text-orange-500',
    label: 'Limité',
    icon: <ExclamationTriangleIcon className="h-4 w-4" />,
  },
};

const CURRENCIES = [
  { value: 'EUR', label: 'EUR' },
  { value: 'USD', label: 'USD' },
  { value: 'GBP', label: 'GBP' },
  { value: 'CHF', label: 'CHF' },
  { value: 'JPY', label: 'JPY' },
  { value: 'CAD', label: 'CAD' },
  { value: 'AUD', label: 'AUD' },
  { value: 'BTC', label: 'BTC' },
  { value: 'ETH', label: 'ETH' },
  { value: 'USDT', label: 'USDT' },
];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const BrokerSettingsForm = forwardRef<HTMLDivElement, BrokerSettingsFormProps>(
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
      title = 'Paramètres Broker',
      subtitle = 'Configurez vos connexions aux brokers de trading',
      className,
      variant = 'default',

      // États
      isLoading = false,
      error = null,
      success = null,
      disabled = false,

      // Accessibilité
      ariaLabel = 'Configuration des brokers',
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

    const [formData, setFormData] = useState<BrokerSettingsFormData>({
      brokers: [],
      preferences: {
        autoReconnect: true,
        retryOnFailure: true,
        logRequests: true,
        cacheResponses: true,
        cacheDuration: 300000,
        websocketEnabled: true,
        websocketAutoReconnect: true,
      },
      ...initialData,
    });

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [activeTab, setActiveTab] = useState<'brokers' | 'preferences' | 'status'>('brokers');
    const [isAddingBroker, setIsAddingBroker] = useState(false);
    const [editingBrokerIndex, setEditingBrokerIndex] = useState<number | null>(null);
    const [showApiKey, setShowApiKey] = useState(false);
    const [showApiSecret, setShowApiSecret] = useState(false);
    const [selectedBroker, setSelectedBroker] = useState<BrokerProvider>('binance');
    const [newBroker, setNewBroker] = useState<Partial<BrokerConfig>>({
      provider: 'binance',
      name: '',
      type: 'cex',
      apiUrl: '',
      enabled: true,
      testMode: true,
      status: 'pending',
      accounts: [],
      timeout: 30000,
      retryAttempts: 3,
    });

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validate = useCallback((): boolean => {
      const errors: Record<string, string> = {};

      formData.brokers.forEach((broker, index) => {
        if (!broker.name) {
          errors[`broker_${index}_name`] = 'Le nom du broker est requis';
        }
        if (!broker.apiUrl) {
          errors[`broker_${index}_apiUrl`] = 'L\'URL de l\'API est requise';
        }
        if (broker.provider !== 'custom' && !broker.apiKey) {
          errors[`broker_${index}_apiKey`] = 'La clé API est requise';
        }
      });

      setFormErrors(errors);
      return Object.keys(errors).length === 0;
    }, [formData]);

    // ========================================================================
    // GESTIONNAIRES DE CHAMPS
    // ========================================================================

    const handleFieldChange = useCallback(<K extends keyof BrokerSettingsFormData>(
      field: K,
      value: BrokerSettingsFormData[K]
    ) => {
      setFormData(prev => ({ ...prev, [field]: value }));
    }, []);

    const handlePreferenceChange = useCallback(<K extends keyof BrokerSettingsFormData['preferences']>(
      field: K,
      value: BrokerSettingsFormData['preferences'][K]
    ) => {
      setFormData(prev => ({
        ...prev,
        preferences: { ...prev.preferences, [field]: value },
      }));
    }, []);

    const handleBrokerChange = useCallback((index: number, field: keyof BrokerConfig, value: any) => {
      setFormData(prev => {
        const newBrokers = [...prev.brokers];
        newBrokers[index] = { ...newBrokers[index], [field]: value };
        return { ...prev, brokers: newBrokers };
      });
      setFormErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[`broker_${index}_${field}`];
        return newErrors;
      });
    }, []);

    // ========================================================================
    // GESTION DES BROKERS
    // ========================================================================

    const handleAddBroker = useCallback(() => {
      if (!newBroker.name || !newBroker.apiUrl) {
        toast({
          title: 'Erreur',
          description: 'Le nom et l\'URL de l\'API sont requis',
          variant: 'destructive',
        });
        return;
      }

      const broker: BrokerConfig = {
        provider: newBroker.provider || 'custom',
        name: newBroker.name,
        type: newBroker.type || 'cex',
        apiUrl: newBroker.apiUrl,
        apiKey: newBroker.apiKey,
        apiSecret: newBroker.apiSecret,
        passphrase: newBroker.passphrase,
        clientId: newBroker.clientId,
        accountId: newBroker.accountId,
        enabled: newBroker.enabled !== undefined ? newBroker.enabled : true,
        testMode: newBroker.testMode !== undefined ? newBroker.testMode : true,
        status: 'pending',
        accounts: [],
        timeout: newBroker.timeout || 30000,
        retryAttempts: newBroker.retryAttempts || 3,
        customHeaders: newBroker.customHeaders || {},
        metadata: newBroker.metadata || {},
      };

      setFormData(prev => ({
        ...prev,
        brokers: [...prev.brokers, broker],
      }));

      setNewBroker({
        provider: 'binance',
        name: '',
        type: 'cex',
        apiUrl: '',
        enabled: true,
        testMode: true,
        status: 'pending',
        accounts: [],
        timeout: 30000,
        retryAttempts: 3,
      });
      setIsAddingBroker(false);
      setEditingBrokerIndex(null);

      toast({
        title: 'Broker ajouté',
        description: `Le broker "${broker.name}" a été ajouté avec succès`,
        duration: 2000,
      });
    }, [newBroker, toast]);

    const handleUpdateBroker = useCallback(() => {
      if (editingBrokerIndex === null) return;
      if (!newBroker.name || !newBroker.apiUrl) {
        toast({
          title: 'Erreur',
          description: 'Le nom et l\'URL de l\'API sont requis',
          variant: 'destructive',
        });
        return;
      }

      setFormData(prev => {
        const newBrokers = [...prev.brokers];
        newBrokers[editingBrokerIndex] = {
          ...newBrokers[editingBrokerIndex],
          provider: newBroker.provider || 'custom',
          name: newBroker.name,
          type: newBroker.type || 'cex',
          apiUrl: newBroker.apiUrl,
          apiKey: newBroker.apiKey,
          apiSecret: newBroker.apiSecret,
          passphrase: newBroker.passphrase,
          clientId: newBroker.clientId,
          accountId: newBroker.accountId,
          enabled: newBroker.enabled !== undefined ? newBroker.enabled : true,
          testMode: newBroker.testMode !== undefined ? newBroker.testMode : true,
          timeout: newBroker.timeout || 30000,
          retryAttempts: newBroker.retryAttempts || 3,
          customHeaders: newBroker.customHeaders || {},
          metadata: newBroker.metadata || {},
        };
        return { ...prev, brokers: newBrokers };
      });

      setNewBroker({
        provider: 'binance',
        name: '',
        type: 'cex',
        apiUrl: '',
        enabled: true,
        testMode: true,
        status: 'pending',
        accounts: [],
        timeout: 30000,
        retryAttempts: 3,
      });
      setIsAddingBroker(false);
      setEditingBrokerIndex(null);

      toast({
        title: 'Broker mis à jour',
        description: 'Le broker a été mis à jour avec succès',
        duration: 2000,
      });
    }, [editingBrokerIndex, newBroker, toast]);

    const handleRemoveBroker = useCallback((index: number) => {
      const broker = formData.brokers[index];
      setFormData(prev => ({
        ...prev,
        brokers: prev.brokers.filter((_, i) => i !== index),
      }));

      toast({
        title: 'Broker supprimé',
        description: `Le broker "${broker.name}" a été supprimé`,
        duration: 2000,
      });
    }, [formData.brokers, toast]);

    const handleEditBroker = useCallback((index: number) => {
      const broker = formData.brokers[index];
      setNewBroker({ ...broker });
      setEditingBrokerIndex(index);
      setIsAddingBroker(true);
    }, [formData.brokers]);

    const handleTestConnection = useCallback(async (index: number) => {
      const broker = formData.brokers[index];

      toast({
        title: 'Test de connexion',
        description: `Connexion à ${broker.name} en cours...`,
        duration: 2000,
      });

      // Simuler un test de connexion
      setTimeout(() => {
        const isConnected = Math.random() > 0.2;
        const status = isConnected ? 'connected' : 'error';

        setFormData(prev => {
          const newBrokers = [...prev.brokers];
          newBrokers[index] = {
            ...newBrokers[index],
            status,
            lastConnection: isConnected ? new Date() : undefined,
            latency: isConnected ? Math.floor(Math.random() * 200) + 50 : undefined,
          };
          return { ...prev, brokers: newBrokers };
        });

        toast({
          title: isConnected ? '✅ Connexion réussie' : '❌ Échec de la connexion',
          description: isConnected 
            ? `Connecté à ${broker.name} avec une latence de ${Math.floor(Math.random() * 200) + 50}ms`
            : `Impossible de se connecter à ${broker.name}. Vérifiez vos identifiants.`,
          variant: isConnected ? 'success' : 'destructive',
          duration: 3000,
        });
      }, 1500);
    }, [formData.brokers, toast]);

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
          description: 'Les paramètres des brokers ont été mis à jour',
          variant: 'success',
        });

        if (debug) {
          console.log('Broker settings saved:', formData);
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
    // RENDU DES BROKERS
    // ========================================================================

    const renderBrokers = () => (
      <div className="space-y-6">
        {/* Liste des brokers */}
        {formData.brokers.length > 0 && (
          <div className="space-y-3">
            {formData.brokers.map((broker, index) => {
              const providerInfo = BROKER_PROVIDERS[broker.provider] || BROKER_PROVIDERS.custom;
              const statusInfo = STATUS_MAP[broker.status] || STATUS_MAP.disconnected;

              return (
                <div
                  key={index}
                  className={cn(
                    'flex items-center gap-3 rounded-lg border p-3',
                    broker.enabled ? 'border-gray-200 dark:border-gray-700' : 'border-gray-300 dark:border-gray-600 opacity-60'
                  )}
                >
                  <div className="flex-shrink-0">
                    <div className={cn('flex h-10 w-10 items-center justify-center rounded-full', providerInfo.color, 'bg-gray-100 dark:bg-gray-800')}>
                      {providerInfo.icon}
                    </div>
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{broker.name}</span>
                      <Badge variant="outline" size="xs">{broker.type.toUpperCase()}</Badge>
                      <span className={cn('flex items-center gap-1 text-xs', statusInfo.color)}>
                        {statusInfo.icon}
                        {statusInfo.label}
                      </span>
                      {broker.testMode && (
                        <Badge variant="warning" size="xs">Test</Badge>
                      )}
                      {!broker.enabled && (
                        <Badge variant="outline" size="xs">Désactivé</Badge>
                      )}
                    </div>
                    <p className="text-sm text-gray-500 dark:text-gray-400 truncate">
                      {broker.apiUrl}
                    </p>
                    {broker.latency && (
                      <div className="flex items-center gap-3 text-xs text-gray-400">
                        <span>Latence: {broker.latency}ms</span>
                        <span>Taux de succès: {broker.successRate || 0}%</span>
                        <span>Requêtes: {broker.totalRequests || 0}</span>
                      </div>
                    )}
                  </div>
                  <div className="flex items-center gap-1">
                    <Tooltip content="Tester la connexion">
                      <button
                        type="button"
                        className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                        onClick={() => handleTestConnection(index)}
                        disabled={disabled || isSubmitting || isLoading}
                      >
                        <WifiIcon className="h-4 w-4" />
                      </button>
                    </Tooltip>
                    <Tooltip content="Modifier">
                      <button
                        type="button"
                        className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                        onClick={() => handleEditBroker(index)}
                      >
                        <PencilIcon className="h-4 w-4" />
                      </button>
                    </Tooltip>
                    <Tooltip content="Supprimer">
                      <button
                        type="button"
                        className="rounded p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                        onClick={() => handleRemoveBroker(index)}
                      >
                        <TrashIcon className="h-4 w-4" />
                      </button>
                    </Tooltip>
                  </div>
                </div>
              );
            })}
          </div>
        )}

        {/* Ajout/Modification de broker */}
        {isAddingBroker && (
          <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {editingBrokerIndex !== null ? 'Modifier le broker' : 'Ajouter un broker'}
              </h4>
              <button
                type="button"
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                onClick={() => {
                  setIsAddingBroker(false);
                  setEditingBrokerIndex(null);
                  setNewBroker({
                    provider: 'binance',
                    name: '',
                    type: 'cex',
                    apiUrl: '',
                    enabled: true,
                    testMode: true,
                    status: 'pending',
                    accounts: [],
                    timeout: 30000,
                    retryAttempts: 3,
                  });
                }}
              >
                <XMarkIcon className="h-4 w-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Fournisseur
                </label>
                <Select
                  options={Object.entries(BROKER_PROVIDERS).map(([value, { label }]) => ({
                    value,
                    label,
                  }))}
                  value={newBroker.provider || 'custom'}
                  onChange={(value) => setNewBroker({ ...newBroker, provider: value as BrokerProvider })}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Nom du broker
                </label>
                <Input
                  type="text"
                  placeholder="Mon broker"
                  value={newBroker.name || ''}
                  onChange={(e) => setNewBroker({ ...newBroker, name: e.target.value })}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Type
                </label>
                <Select
                  options={BROKER_TYPES}
                  value={newBroker.type || 'cex'}
                  onChange={(value) => setNewBroker({ ...newBroker, type: value as BrokerType })}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  URL de l'API
                </label>
                <Input
                  type="text"
                  placeholder="https://api.broker.com/v1"
                  value={newBroker.apiUrl || ''}
                  onChange={(e) => setNewBroker({ ...newBroker, apiUrl: e.target.value })}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Clé API
                </label>
                <div className="relative">
                  <Input
                    type={showApiKey ? 'text' : 'password'}
                    placeholder="Votre clé API"
                    value={newBroker.apiKey || ''}
                    onChange={(e) => setNewBroker({ ...newBroker, apiKey: e.target.value })}
                    className="pr-10"
                  />
                  <button
                    type="button"
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    onClick={() => setShowApiKey(!showApiKey)}
                  >
                    {showApiKey ? <EyeSlashIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
                  </button>
                </div>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Secret API
                </label>
                <div className="relative">
                  <Input
                    type={showApiSecret ? 'text' : 'password'}
                    placeholder="Votre secret API"
                    value={newBroker.apiSecret || ''}
                    onChange={(e) => setNewBroker({ ...newBroker, apiSecret: e.target.value })}
                    className="pr-10"
                  />
                  <button
                    type="button"
                    className="absolute right-2 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600"
                    onClick={() => setShowApiSecret(!showApiSecret)}
                  >
                    {showApiSecret ? <EyeSlashIcon className="h-4 w-4" /> : <EyeIcon className="h-4 w-4" />}
                  </button>
                </div>
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Passphrase
                </label>
                <Input
                  type="text"
                  placeholder="Passphrase (si requis)"
                  value={newBroker.passphrase || ''}
                  onChange={(e) => setNewBroker({ ...newBroker, passphrase: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Client ID
                </label>
                <Input
                  type="text"
                  placeholder="Client ID (si requis)"
                  value={newBroker.clientId || ''}
                  onChange={(e) => setNewBroker({ ...newBroker, clientId: e.target.value })}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Timeout (ms)
                </label>
                <Input
                  type="number"
                  value={newBroker.timeout || 30000}
                  onChange={(e) => setNewBroker({ ...newBroker, timeout: parseInt(e.target.value) || 30000 })}
                  step={1000}
                  min={1000}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Tentatives de retry
                </label>
                <Input
                  type="number"
                  value={newBroker.retryAttempts || 3}
                  onChange={(e) => setNewBroker({ ...newBroker, retryAttempts: parseInt(e.target.value) || 3 })}
                  min={0}
                  max={10}
                />
              </div>
            </div>

            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <Switch
                  checked={newBroker.enabled !== undefined ? newBroker.enabled : true}
                  onCheckedChange={(checked) => setNewBroker({ ...newBroker, enabled: checked })}
                />
                <span className="text-sm text-gray-600 dark:text-gray-300">Activé</span>
              </div>
              <div className="flex items-center gap-2">
                <Switch
                  checked={newBroker.testMode !== undefined ? newBroker.testMode : true}
                  onCheckedChange={(checked) => setNewBroker({ ...newBroker, testMode: checked })}
                />
                <span className="text-sm text-gray-600 dark:text-gray-300">Mode test</span>
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsAddingBroker(false);
                  setEditingBrokerIndex(null);
                  setNewBroker({
                    provider: 'binance',
                    name: '',
                    type: 'cex',
                    apiUrl: '',
                    enabled: true,
                    testMode: true,
                    status: 'pending',
                    accounts: [],
                    timeout: 30000,
                    retryAttempts: 3,
                  });
                }}
              >
                Annuler
              </Button>
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={editingBrokerIndex !== null ? handleUpdateBroker : handleAddBroker}
              >
                {editingBrokerIndex !== null ? 'Mettre à jour' : 'Ajouter'}
              </Button>
            </div>
          </div>
        )}

        {!isAddingBroker && (
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => setIsAddingBroker(true)}
            disabled={disabled || isSubmitting || isLoading}
          >
            <PlusIcon className="h-4 w-4 mr-2" />
            Ajouter un broker
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
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Reconnexion automatique
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Se reconnecter automatiquement en cas de perte de connexion
              </p>
            </div>
            <Switch
              checked={formData.preferences.autoReconnect}
              onCheckedChange={(checked) => handlePreferenceChange('autoReconnect', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Retry sur échec
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Réessayer automatiquement en cas d'échec de requête
              </p>
            </div>
            <Switch
              checked={formData.preferences.retryOnFailure}
              onCheckedChange={(checked) => handlePreferenceChange('retryOnFailure', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Log des requêtes
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Enregistrer toutes les requêtes API
              </p>
            </div>
            <Switch
              checked={formData.preferences.logRequests}
              onCheckedChange={(checked) => handlePreferenceChange('logRequests', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Cache des réponses
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Mettre en cache les réponses des requêtes
              </p>
            </div>
            <Switch
              checked={formData.preferences.cacheResponses}
              onCheckedChange={(checked) => handlePreferenceChange('cacheResponses', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          {formData.preferences.cacheResponses && (
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Durée du cache (ms)
              </label>
              <Input
                type="number"
                value={formData.preferences.cacheDuration}
                onChange={(e) => handlePreferenceChange('cacheDuration', parseInt(e.target.value) || 300000)}
                disabled={disabled || isSubmitting || isLoading}
                step={10000}
                min={10000}
              />
            </div>
          )}

          <Separator />

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                WebSocket activé
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Utiliser WebSocket pour les données en temps réel
              </p>
            </div>
            <Switch
              checked={formData.preferences.websocketEnabled}
              onCheckedChange={(checked) => handlePreferenceChange('websocketEnabled', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Reconnect automatique WebSocket
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Se reconnecter automatiquement au WebSocket
              </p>
            </div>
            <Switch
              checked={formData.preferences.websocketAutoReconnect}
              onCheckedChange={(checked) => handlePreferenceChange('websocketAutoReconnect', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>
      </div>
    );

    // ========================================================================
    // RENDU DU STATUT
    // ========================================================================

    const renderStatus = () => (
      <div className="space-y-6">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-3 text-center">
            <div className="text-2xl font-bold text-gray-900 dark:text-white">
              {formData.brokers.length}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Brokers configurés</div>
          </div>
          <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-3 text-center">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {formData.brokers.filter(b => b.status === 'connected').length}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Connectés</div>
          </div>
          <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-3 text-center">
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {formData.brokers.filter(b => b.status === 'error').length}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">En erreur</div>
          </div>
          <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-3 text-center">
            <div className="text-2xl font-bold text-blue-600 dark:text-blue-400">
              {formData.brokers.filter(b => b.enabled).length}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Activés</div>
          </div>
        </div>

        <Separator />

        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">Statut détaillé</h4>
          {formData.brokers.length === 0 ? (
            <p className="text-sm text-gray-500 dark:text-gray-400">Aucun broker configuré</p>
          ) : (
            formData.brokers.map((broker, index) => {
              const statusInfo = STATUS_MAP[broker.status] || STATUS_MAP.disconnected;
              return (
                <div key={index} className="flex items-center gap-3 rounded-lg border border-gray-200 dark:border-gray-700 p-3">
                  <span className="font-medium">{broker.name}</span>
                  <span className={cn('flex items-center gap-1 text-sm', statusInfo.color)}>
                    {statusInfo.icon}
                    {statusInfo.label}
                  </span>
                  {broker.lastConnection && (
                    <span className="text-xs text-gray-400">
                      Dernière connexion: {broker.lastConnection.toLocaleString()}
                    </span>
                  )}
                  {broker.latency && (
                    <span className="text-xs text-gray-400">Latence: {broker.latency}ms</span>
                  )}
                  <span className="ml-auto text-xs text-gray-400">
                    {broker.totalRequests || 0} requêtes
                  </span>
                </div>
              );
            })
          )}
        </div>

        <div className="flex justify-end">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              formData.brokers.forEach((_, index) => handleTestConnection(index));
            }}
            disabled={disabled || isSubmitting || isLoading || formData.brokers.length === 0}
          >
            <ArrowPathIcon className="h-4 w-4 mr-2" />
            Tester toutes les connexions
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
                <Badge variant="outline" size="sm" className="flex items-center gap-1">
                  <BuildingOfficeIcon className="h-3 w-3" />
                  {formData.brokers.length} brokers
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
              { id: 'brokers', label: '🔌 Brokers' },
              { id: 'preferences', label: '⚙️ Préférences' },
              { id: 'status', label: '📊 Statut' },
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
                {activeTab === 'brokers' && renderBrokers()}
                {activeTab === 'preferences' && renderPreferences()}
                {activeTab === 'status' && renderStatus()}
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
              {formData.brokers.length} brokers • 
              {formData.brokers.filter(b => b.enabled).length} activés
            </span>
            <span>
              Connectés: {formData.brokers.filter(b => b.status === 'connected').length}
            </span>
          </div>
        </CardFooter>
      </Card>
    );
  }
);

BrokerSettingsForm.displayName = 'BrokerSettingsForm';

// ============================================================================
// EXPORTS
// ============================================================================

export default BrokerSettingsForm;

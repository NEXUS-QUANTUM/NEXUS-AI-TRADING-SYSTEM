// apps/web/src/components/forms/settings/TradingSettingsForm.tsx
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
  ChartBarIcon,
  ChartPieIcon,
  ChartLineIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
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
  BellIcon,
  BellSlashIcon,
  ShieldCheckIcon,
  ShieldExclamationIcon,
  WalletIcon,
  BanknotesIcon,
  CurrencyDollarIcon,
  PercentIcon,
  ScaleIcon,
  DocumentTextIcon,
  TableCellsIcon,
  Squares2X2Icon,
  ListBulletIcon,
  EyeIcon,
  EyeSlashIcon,
  LinkIcon,
  LinkSlashIcon,
  GlobeAltIcon,
  ServerIcon,
  CloudIcon,
  DatabaseIcon,
  WifiIcon,
  WifiSlashIcon,
  LockClosedIcon,
  LockOpenIcon,
  UserIcon,
  UserGroupIcon,
  BuildingOfficeIcon,
  EnvelopeIcon,
  PhoneIcon,
  MapPinIcon,
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

export type TradingMode = 'manual' | 'semi_automatic' | 'automatic' | 'paper';
export type OrderType = 'market' | 'limit' | 'stop' | 'stop_limit' | 'trailing_stop' | 'take_profit';
export type TimeInForce = 'GTC' | 'IOC' | 'FOK' | 'DAY' | 'GTT';
export type TradingStrategy = 'scalping' | 'day' | 'swing' | 'position' | 'arbitrage' | 'grid' | 'martingale' | 'custom';
export type TradingSymbol = {
  /** Symbole */
  symbol: string;
  /** Base de la paire */
  base: string;
  /** Quote de la paire */
  quote: string;
  /** Est activé */
  enabled: boolean;
  /** Taille minimale */
  minQty: number;
  /** Taille maximale */
  maxQty: number;
  /** Pas de quantité */
  stepQty: number;
  /** Prix minimal */
  minPrice: number;
  /** Prix maximal */
  maxPrice: number;
  /** Pas de prix */
  stepPrice: number;
};

export interface TradingAlert {
  /** Identifiant */
  id: string;
  /** Nom */
  name: string;
  /** Symbole */
  symbol: string;
  /** Condition */
  condition: 'above' | 'below' | 'cross_above' | 'cross_below' | 'between';
  /** Valeur */
  value: number;
  /** Valeur supérieure (pour between) */
  value2?: number;
  /** Canal */
  channel: 'email' | 'push' | 'sms' | 'all';
  /** Est activée */
  enabled: boolean;
  /** Dernière notification */
  lastTriggered?: Date;
}

export interface TradingSettingsData {
  /** Mode de trading */
  mode: TradingMode;
  /** Type d'ordre par défaut */
  defaultOrderType: OrderType;
  /** Time in force par défaut */
  defaultTimeInForce: TimeInForce;
  /** Stratégie par défaut */
  defaultStrategy: TradingStrategy;
  /** Symboles */
  symbols: TradingSymbol[];
  /** Symboles actifs */
  activeSymbols: string[];
  /** Taille de position par défaut */
  defaultPositionSize: number;
  /** Effet de levier maximal */
  maxLeverage: number;
  /** Slippage toléré (%) */
  slippageTolerance: number;
  /** Spread maximal (%) */
  maxSpread: number;
  /** Alertes */
  alerts: TradingAlert[];
  /** Préférences */
  preferences: {
    /** Confirmer les ordres */
    confirmOrders: boolean;
    /** Afficher les notifications */
    showNotifications: boolean;
    /** Son des notifications */
    notificationSound: 'none' | 'default' | 'gentle' | 'urgent';
    /** Auto-ajuster les positions */
    autoAdjustPositions: boolean;
    /** Utiliser le trailing stop par défaut */
    useTrailingStop: boolean;
    /** Distance du trailing stop (%) */
    trailingStopDistance: number;
    /** Activer le trading automatique */
    autoTradingEnabled: boolean;
    /** Activer le paper trading */
    paperTradingEnabled: boolean;
    /** Capital de paper trading */
    paperTradingCapital: number;
    /** Activer les logs de trading */
    tradingLogsEnabled: boolean;
    /** Activer l'analyse technique */
    technicalAnalysisEnabled: boolean;
    /** Activer le backtesting */
    backtestingEnabled: boolean;
    /** Nombre de barres pour l'analyse */
    analysisBars: number;
    /** Période de l'analyse */
    analysisPeriod: '1m' | '5m' | '15m' | '30m' | '1h' | '4h' | '1d' | '1w';
  };
}

export interface TradingSettingsFormProps {
  // --- Contrôle ---
  /** Données initiales */
  initialData?: Partial<TradingSettingsData>;
  /** Callback de soumission */
  onSubmit?: (data: TradingSettingsData) => void | Promise<void>;
  /** Callback de succès */
  onSuccess?: (data: TradingSettingsData) => void;
  /** Callback d'erreur */
  onError?: (error: string) => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de changement */
  onChange?: (data: TradingSettingsData) => void;

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

const TRADING_MODES: { value: TradingMode; label: string; description: string; icon: React.ReactNode }[] = [
  {
    value: 'manual',
    label: 'Manuel',
    description: 'Exécution manuelle des ordres',
    icon: <UserIcon className="h-4 w-4" />,
  },
  {
    value: 'semi_automatic',
    label: 'Semi-automatique',
    description: 'Signaux avec confirmation manuelle',
    icon: <AdjustmentsHorizontalIcon className="h-4 w-4" />,
  },
  {
    value: 'automatic',
    label: 'Automatique',
    description: 'Exécution automatique des ordres',
    icon: <ArrowTrendingUpIcon className="h-4 w-4" />,
  },
  {
    value: 'paper',
    label: 'Paper Trading',
    description: 'Simulation sans risque réel',
    icon: <WalletIcon className="h-4 w-4" />,
  },
];

const ORDER_TYPES: { value: OrderType; label: string; description: string }[] = [
  { value: 'market', label: 'Marché', description: 'Exécution immédiate au meilleur prix' },
  { value: 'limit', label: 'Limite', description: 'Exécution à un prix spécifique' },
  { value: 'stop', label: 'Stop', description: 'Déclenché à un prix stop' },
  { value: 'stop_limit', label: 'Stop Limite', description: 'Ordre limite déclenché par un stop' },
  { value: 'trailing_stop', label: 'Trailing Stop', description: 'Stop qui suit le prix' },
  { value: 'take_profit', label: 'Take Profit', description: 'Fermeture à un niveau de profit' },
];

const TIME_IN_FORCE: { value: TimeInForce; label: string; description: string }[] = [
  { value: 'GTC', label: 'GTC', description: 'Good Till Canceled' },
  { value: 'IOC', label: 'IOC', description: 'Immediate or Cancel' },
  { value: 'FOK', label: 'FOK', description: 'Fill or Kill' },
  { value: 'DAY', label: 'Jour', description: 'Valable jusqu\'à la fin du jour' },
  { value: 'GTT', label: 'GTT', description: 'Good Till Time' },
];

const STRATEGIES: { value: TradingStrategy; label: string; description: string }[] = [
  { value: 'scalping', label: 'Scalping', description: 'Trades rapides sur de petits mouvements' },
  { value: 'day', label: 'Day Trading', description: 'Positions fermées dans la journée' },
  { value: 'swing', label: 'Swing Trading', description: 'Positions de quelques jours à semaines' },
  { value: 'position', label: 'Position Trading', description: 'Positions long terme' },
  { value: 'arbitrage', label: 'Arbitrage', description: 'Profit des écarts de prix' },
  { value: 'grid', label: 'Grid Trading', description: 'Achats/ventes sur une grille de prix' },
  { value: 'martingale', label: 'Martingale', description: 'Doublement après perte' },
  { value: 'custom', label: 'Personnalisé', description: 'Stratégie personnalisée' },
];

const NOTIFICATION_SOUNDS: { value: 'none' | 'default' | 'gentle' | 'urgent'; label: string }[] = [
  { value: 'none', label: 'Aucun' },
  { value: 'default', label: 'Par défaut' },
  { value: 'gentle', label: 'Doux' },
  { value: 'urgent', label: 'Urgent' },
];

const ANALYSIS_PERIODS: { value: '1m' | '5m' | '15m' | '30m' | '1h' | '4h' | '1d' | '1w'; label: string }[] = [
  { value: '1m', label: '1 minute' },
  { value: '5m', label: '5 minutes' },
  { value: '15m', label: '15 minutes' },
  { value: '30m', label: '30 minutes' },
  { value: '1h', label: '1 heure' },
  { value: '4h', label: '4 heures' },
  { value: '1d', label: '1 jour' },
  { value: '1w', label: '1 semaine' },
];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const TradingSettingsForm = forwardRef<HTMLDivElement, TradingSettingsFormProps>(
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
      title = 'Paramètres de trading',
      subtitle = 'Configurez vos préférences de trading',
      className,
      variant = 'default',

      // États
      isLoading = false,
      error = null,
      success = null,
      disabled = false,

      // Accessibilité
      ariaLabel = 'Paramètres de trading',
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

    const [formData, setFormData] = useState<TradingSettingsData>({
      mode: 'semi_automatic',
      defaultOrderType: 'limit',
      defaultTimeInForce: 'GTC',
      defaultStrategy: 'swing',
      symbols: [],
      activeSymbols: [],
      defaultPositionSize: 1,
      maxLeverage: 10,
      slippageTolerance: 0.5,
      maxSpread: 0.2,
      alerts: [],
      preferences: {
        confirmOrders: true,
        showNotifications: true,
        notificationSound: 'default',
        autoAdjustPositions: false,
        useTrailingStop: false,
        trailingStopDistance: 2,
        autoTradingEnabled: false,
        paperTradingEnabled: true,
        paperTradingCapital: 10000,
        tradingLogsEnabled: true,
        technicalAnalysisEnabled: true,
        backtestingEnabled: true,
        analysisBars: 100,
        analysisPeriod: '1h',
      },
      ...initialData,
    });

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [activeTab, setActiveTab] = useState<'general' | 'symbols' | 'alerts' | 'preferences'>('general');
    const [isAddingSymbol, setIsAddingSymbol] = useState(false);
    const [isAddingAlert, setIsAddingAlert] = useState(false);
    const [editingAlertIndex, setEditingAlertIndex] = useState<number | null>(null);
    const [newSymbol, setNewSymbol] = useState<Partial<TradingSymbol>>({
      symbol: '',
      base: '',
      quote: '',
      enabled: true,
      minQty: 0.001,
      maxQty: 100,
      stepQty: 0.001,
      minPrice: 0.01,
      maxPrice: 100000,
      stepPrice: 0.01,
    });
    const [newAlert, setNewAlert] = useState<Partial<TradingAlert>>({
      name: '',
      symbol: '',
      condition: 'above',
      value: 0,
      channel: 'all',
      enabled: true,
    });

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validate = useCallback((): boolean => {
      const errors: Record<string, string> = {};

      if (formData.defaultPositionSize <= 0) {
        errors.defaultPositionSize = 'La taille de position doit être positive';
      }

      if (formData.maxLeverage < 1 || formData.maxLeverage > 100) {
        errors.maxLeverage = 'Le levier doit être entre 1 et 100';
      }

      if (formData.slippageTolerance < 0 || formData.slippageTolerance > 10) {
        errors.slippageTolerance = 'Le slippage doit être entre 0% et 10%';
      }

      if (formData.maxSpread < 0 || formData.maxSpread > 5) {
        errors.maxSpread = 'Le spread doit être entre 0% et 5%';
      }

      formData.alerts.forEach((alert, index) => {
        if (!alert.name) {
          errors[`alert_${index}_name`] = 'Le nom de l\'alerte est requis';
        }
        if (!alert.symbol) {
          errors[`alert_${index}_symbol`] = 'Le symbole est requis';
        }
        if (alert.value <= 0) {
          errors[`alert_${index}_value`] = 'La valeur doit être positive';
        }
      });

      setFormErrors(errors);
      return Object.keys(errors).length === 0;
    }, [formData]);

    // ========================================================================
    // GESTIONNAIRES DE CHAMPS
    // ========================================================================

    const handleFieldChange = useCallback(<K extends keyof TradingSettingsData>(
      field: K,
      value: TradingSettingsData[K]
    ) => {
      setFormData(prev => ({ ...prev, [field]: value }));
      setFormErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }, []);

    const handleNestedFieldChange = useCallback(
      <P extends keyof TradingSettingsData, K extends string>(
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

    const handlePreferenceChange = useCallback(<K extends keyof TradingSettingsData['preferences']>(
      field: K,
      value: TradingSettingsData['preferences'][K]
    ) => {
      setFormData(prev => ({
        ...prev,
        preferences: { ...prev.preferences, [field]: value },
      }));
    }, []);

    // ========================================================================
    // GESTION DES SYMBOLES
    // ========================================================================

    const handleAddSymbol = useCallback(() => {
      if (!newSymbol.symbol || !newSymbol.base || !newSymbol.quote) {
        toast({
          title: 'Erreur',
          description: 'Le symbole, la base et la quote sont requis',
          variant: 'destructive',
        });
        return;
      }

      const symbol: TradingSymbol = {
        symbol: newSymbol.symbol,
        base: newSymbol.base,
        quote: newSymbol.quote,
        enabled: newSymbol.enabled !== undefined ? newSymbol.enabled : true,
        minQty: newSymbol.minQty || 0.001,
        maxQty: newSymbol.maxQty || 100,
        stepQty: newSymbol.stepQty || 0.001,
        minPrice: newSymbol.minPrice || 0.01,
        maxPrice: newSymbol.maxPrice || 100000,
        stepPrice: newSymbol.stepPrice || 0.01,
      };

      setFormData(prev => ({
        ...prev,
        symbols: [...prev.symbols, symbol],
        activeSymbols: [...prev.activeSymbols, symbol.symbol],
      }));

      setNewSymbol({
        symbol: '',
        base: '',
        quote: '',
        enabled: true,
        minQty: 0.001,
        maxQty: 100,
        stepQty: 0.001,
        minPrice: 0.01,
        maxPrice: 100000,
        stepPrice: 0.01,
      });
      setIsAddingSymbol(false);

      toast({
        title: 'Symbole ajouté',
        description: `Le symbole ${symbol.symbol} a été ajouté`,
        duration: 2000,
      });
    }, [newSymbol, toast]);

    const handleRemoveSymbol = useCallback((symbol: string) => {
      setFormData(prev => ({
        ...prev,
        symbols: prev.symbols.filter(s => s.symbol !== symbol),
        activeSymbols: prev.activeSymbols.filter(s => s !== symbol),
      }));

      toast({
        title: 'Symbole supprimé',
        description: `Le symbole ${symbol} a été supprimé`,
        duration: 2000,
      });
    }, [toast]);

    const handleToggleSymbol = useCallback((symbol: string) => {
      setFormData(prev => {
        const isActive = prev.activeSymbols.includes(symbol);
        return {
          ...prev,
          activeSymbols: isActive
            ? prev.activeSymbols.filter(s => s !== symbol)
            : [...prev.activeSymbols, symbol],
        };
      });
    }, []);

    // ========================================================================
    // GESTION DES ALERTES
    // ========================================================================

    const handleAddAlert = useCallback(() => {
      if (!newAlert.name || !newAlert.symbol || !newAlert.value) {
        toast({
          title: 'Erreur',
          description: 'Le nom, le symbole et la valeur sont requis',
          variant: 'destructive',
        });
        return;
      }

      const alert: TradingAlert = {
        id: `alert_${Date.now()}`,
        name: newAlert.name,
        symbol: newAlert.symbol,
        condition: newAlert.condition || 'above',
        value: newAlert.value,
        channel: newAlert.channel || 'all',
        enabled: newAlert.enabled !== undefined ? newAlert.enabled : true,
        ...(newAlert.value2 && { value2: newAlert.value2 }),
      };

      setFormData(prev => ({
        ...prev,
        alerts: [...prev.alerts, alert],
      }));

      setNewAlert({
        name: '',
        symbol: '',
        condition: 'above',
        value: 0,
        channel: 'all',
        enabled: true,
      });
      setIsAddingAlert(false);

      toast({
        title: 'Alerte ajoutée',
        description: `L'alerte "${alert.name}" a été ajoutée`,
        duration: 2000,
      });
    }, [newAlert, toast]);

    const handleUpdateAlert = useCallback(() => {
      if (editingAlertIndex === null) return;
      if (!newAlert.name || !newAlert.symbol || !newAlert.value) {
        toast({
          title: 'Erreur',
          description: 'Le nom, le symbole et la valeur sont requis',
          variant: 'destructive',
        });
        return;
      }

      setFormData(prev => {
        const newAlerts = [...prev.alerts];
        newAlerts[editingAlertIndex] = {
          ...newAlerts[editingAlertIndex],
          name: newAlert.name,
          symbol: newAlert.symbol,
          condition: newAlert.condition || 'above',
          value: newAlert.value,
          channel: newAlert.channel || 'all',
          enabled: newAlert.enabled !== undefined ? newAlert.enabled : true,
          ...(newAlert.value2 && { value2: newAlert.value2 }),
        };
        return { ...prev, alerts: newAlerts };
      });

      setNewAlert({
        name: '',
        symbol: '',
        condition: 'above',
        value: 0,
        channel: 'all',
        enabled: true,
      });
      setIsAddingAlert(false);
      setEditingAlertIndex(null);

      toast({
        title: 'Alerte mise à jour',
        description: 'L\'alerte a été mise à jour',
        duration: 2000,
      });
    }, [editingAlertIndex, newAlert, toast]);

    const handleRemoveAlert = useCallback((index: number) => {
      const alert = formData.alerts[index];
      setFormData(prev => ({
        ...prev,
        alerts: prev.alerts.filter((_, i) => i !== index),
      }));

      toast({
        title: 'Alerte supprimée',
        description: `L'alerte "${alert.name}" a été supprimée`,
        duration: 2000,
      });
    }, [formData.alerts, toast]);

    const handleToggleAlert = useCallback((index: number) => {
      setFormData(prev => {
        const newAlerts = [...prev.alerts];
        newAlerts[index] = { ...newAlerts[index], enabled: !newAlerts[index].enabled };
        return { ...prev, alerts: newAlerts };
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
          title: 'Paramètres de trading sauvegardés',
          description: 'Vos paramètres de trading ont été mis à jour',
          variant: 'success',
        });

        if (debug) {
          console.log('Trading settings saved:', formData);
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
        {/* Mode de trading */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Mode de trading
          </label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {TRADING_MODES.map((mode) => (
              <button
                key={mode.value}
                type="button"
                className={cn(
                  'flex flex-col items-center gap-1 rounded-lg border-2 p-3 transition-all',
                  formData.mode === mode.value
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
                onClick={() => handleFieldChange('mode', mode.value)}
                disabled={disabled || isSubmitting || isLoading}
              >
                {mode.icon}
                <span className="text-sm font-medium">{mode.label}</span>
                <span className="text-xs text-gray-500 dark:text-gray-400 text-center">
                  {mode.description}
                </span>
              </button>
            ))}
          </div>
        </div>

        <Separator />

        {/* Types d'ordres par défaut */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Type d'ordre par défaut
            </label>
            <Select
              options={ORDER_TYPES.map(o => ({ value: o.value, label: `${o.label} - ${o.description}` }))}
              value={formData.defaultOrderType}
              onChange={(value) => handleFieldChange('defaultOrderType', value as OrderType)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Time in Force par défaut
            </label>
            <Select
              options={TIME_IN_FORCE.map(t => ({ value: t.value, label: `${t.label} - ${t.description}` }))}
              value={formData.defaultTimeInForce}
              onChange={(value) => handleFieldChange('defaultTimeInForce', value as TimeInForce)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Stratégie par défaut
            </label>
            <Select
              options={STRATEGIES.map(s => ({ value: s.value, label: `${s.label} - ${s.description}` }))}
              value={formData.defaultStrategy}
              onChange={(value) => handleFieldChange('defaultStrategy', value as TradingStrategy)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Taille de position par défaut
            </label>
            <Input
              type="number"
              value={formData.defaultPositionSize}
              onChange={(e) => handleFieldChange('defaultPositionSize', parseFloat(e.target.value) || 0)}
              error={formErrors.defaultPositionSize}
              disabled={disabled || isSubmitting || isLoading}
              step={0.01}
              min={0.01}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Effet de levier maximal
            </label>
            <Input
              type="number"
              value={formData.maxLeverage}
              onChange={(e) => handleFieldChange('maxLeverage', parseInt(e.target.value) || 1)}
              error={formErrors.maxLeverage}
              disabled={disabled || isSubmitting || isLoading}
              min={1}
              max={100}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Slippage toléré (%)
            </label>
            <Input
              type="number"
              value={formData.slippageTolerance}
              onChange={(e) => handleFieldChange('slippageTolerance', parseFloat(e.target.value) || 0)}
              error={formErrors.slippageTolerance}
              disabled={disabled || isSubmitting || isLoading}
              step={0.01}
              min={0}
              max={10}
            />
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Spread maximal (%)
          </label>
          <Input
            type="number"
            value={formData.maxSpread}
            onChange={(e) => handleFieldChange('maxSpread', parseFloat(e.target.value) || 0)}
            error={formErrors.maxSpread}
            disabled={disabled || isSubmitting || isLoading}
            step={0.01}
            min={0}
            max={5}
          />
        </div>
      </div>
    );

    // ========================================================================
    // RENDU DE L'ONGLET SYMBOLES
    // ========================================================================

    const renderSymbolsTab = () => (
      <div className="space-y-6">
        {/* Liste des symboles */}
        {formData.symbols.length > 0 && (
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Symboles configurés
              </h4>
              <span className="text-xs text-gray-400">
                {formData.activeSymbols.length} / {formData.symbols.length} actifs
              </span>
            </div>
            {formData.symbols.map((symbol, index) => {
              const isActive = formData.activeSymbols.includes(symbol.symbol);
              return (
                <div
                  key={index}
                  className={cn(
                    'flex items-center gap-3 rounded-lg border p-3',
                    isActive ? 'border-gray-200 dark:border-gray-700' : 'border-gray-300 dark:border-gray-600 opacity-60'
                  )}
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{symbol.symbol}</span>
                      <Badge variant="outline" size="xs">
                        {symbol.base}/{symbol.quote}
                      </Badge>
                      {isActive ? (
                        <Badge variant="success" size="xs">Actif</Badge>
                      ) : (
                        <Badge variant="outline" size="xs">Inactif</Badge>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-2 text-xs text-gray-500 dark:text-gray-400">
                      <span>Min: {symbol.minQty}</span>
                      <span>Max: {symbol.maxQty}</span>
                      <span>Step: {symbol.stepQty}</span>
                      <span>Prix: {symbol.minPrice} - {symbol.maxPrice}</span>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Tooltip content={isActive ? 'Désactiver' : 'Activer'}>
                      <button
                        type="button"
                        className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                        onClick={() => handleToggleSymbol(symbol.symbol)}
                      >
                        {isActive ? <EyeIcon className="h-4 w-4" /> : <EyeSlashIcon className="h-4 w-4" />}
                      </button>
                    </Tooltip>
                    <Tooltip content="Supprimer">
                      <button
                        type="button"
                        className="rounded p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                        onClick={() => handleRemoveSymbol(symbol.symbol)}
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

        {/* Ajout de symbole */}
        {isAddingSymbol ? (
          <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Ajouter un symbole
              </h4>
              <button
                type="button"
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                onClick={() => {
                  setIsAddingSymbol(false);
                  setNewSymbol({
                    symbol: '',
                    base: '',
                    quote: '',
                    enabled: true,
                    minQty: 0.001,
                    maxQty: 100,
                    stepQty: 0.001,
                    minPrice: 0.01,
                    maxPrice: 100000,
                    stepPrice: 0.01,
                  });
                }}
              >
                <XMarkIcon className="h-4 w-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Symbole
                </label>
                <Input
                  type="text"
                  placeholder="BTCUSDT"
                  value={newSymbol.symbol || ''}
                  onChange={(e) => setNewSymbol({ ...newSymbol, symbol: e.target.value.toUpperCase() })}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Base
                </label>
                <Input
                  type="text"
                  placeholder="BTC"
                  value={newSymbol.base || ''}
                  onChange={(e) => setNewSymbol({ ...newSymbol, base: e.target.value.toUpperCase() })}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Quote
                </label>
                <Input
                  type="text"
                  placeholder="USDT"
                  value={newSymbol.quote || ''}
                  onChange={(e) => setNewSymbol({ ...newSymbol, quote: e.target.value.toUpperCase() })}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Quantité minimale
                </label>
                <Input
                  type="number"
                  value={newSymbol.minQty || 0.001}
                  onChange={(e) => setNewSymbol({ ...newSymbol, minQty: parseFloat(e.target.value) || 0.001 })}
                  step={0.001}
                  min={0.001}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Quantité maximale
                </label>
                <Input
                  type="number"
                  value={newSymbol.maxQty || 100}
                  onChange={(e) => setNewSymbol({ ...newSymbol, maxQty: parseFloat(e.target.value) || 100 })}
                  step={1}
                  min={1}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Pas de quantité
                </label>
                <Input
                  type="number"
                  value={newSymbol.stepQty || 0.001}
                  onChange={(e) => setNewSymbol({ ...newSymbol, stepQty: parseFloat(e.target.value) || 0.001 })}
                  step={0.001}
                  min={0.001}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Prix minimal
                </label>
                <Input
                  type="number"
                  value={newSymbol.minPrice || 0.01}
                  onChange={(e) => setNewSymbol({ ...newSymbol, minPrice: parseFloat(e.target.value) || 0.01 })}
                  step={0.01}
                  min={0.01}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Prix maximal
                </label>
                <Input
                  type="number"
                  value={newSymbol.maxPrice || 100000}
                  onChange={(e) => setNewSymbol({ ...newSymbol, maxPrice: parseFloat(e.target.value) || 100000 })}
                  step={1}
                  min={1}
                />
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Switch
                checked={newSymbol.enabled !== undefined ? newSymbol.enabled : true}
                onCheckedChange={(checked) => setNewSymbol({ ...newSymbol, enabled: checked })}
              />
              <span className="text-sm text-gray-600 dark:text-gray-300">Activé</span>
            </div>

            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsAddingSymbol(false);
                  setNewSymbol({
                    symbol: '',
                    base: '',
                    quote: '',
                    enabled: true,
                    minQty: 0.001,
                    maxQty: 100,
                    stepQty: 0.001,
                    minPrice: 0.01,
                    maxPrice: 100000,
                    stepPrice: 0.01,
                  });
                }}
              >
                Annuler
              </Button>
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={handleAddSymbol}
              >
                Ajouter
              </Button>
            </div>
          </div>
        ) : (
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => setIsAddingSymbol(true)}
            disabled={disabled || isSubmitting || isLoading}
          >
            <PlusIcon className="h-4 w-4 mr-2" />
            Ajouter un symbole
          </Button>
        )}
      </div>
    );

    // ========================================================================
    // RENDU DE L'ONGLET ALERTES
    // ========================================================================

    const renderAlertsTab = () => (
      <div className="space-y-6">
        {/* Liste des alertes */}
        {formData.alerts.length > 0 && (
          <div className="space-y-2">
            {formData.alerts.map((alert, index) => (
              <div
                key={alert.id}
                className={cn(
                  'flex items-center gap-3 rounded-lg border p-3',
                  alert.enabled ? 'border-gray-200 dark:border-gray-700' : 'border-gray-300 dark:border-gray-600 opacity-60'
                )}
              >
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{alert.name}</span>
                    <Badge variant="outline" size="xs">{alert.symbol}</Badge>
                    <Badge variant="outline" size="xs">
                      {alert.condition === 'above' ? '>' :
                       alert.condition === 'below' ? '<' :
                       alert.condition === 'cross_above' ? '↗' :
                       alert.condition === 'cross_below' ? '↘' :
                       'between'} {alert.value}
                      {alert.value2 && ` - ${alert.value2}`}
                    </Badge>
                    <Badge variant="outline" size="xs">
                      {alert.channel === 'all' ? 'Tous' : alert.channel}
                    </Badge>
                    {alert.enabled ? (
                      <Badge variant="success" size="xs">Active</Badge>
                    ) : (
                      <Badge variant="outline" size="xs">Inactive</Badge>
                    )}
                  </div>
                  {alert.lastTriggered && (
                    <p className="text-xs text-gray-400">
                      Dernière déclenchement: {alert.lastTriggered.toLocaleString()}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  <Tooltip content={alert.enabled ? 'Désactiver' : 'Activer'}>
                    <button
                      type="button"
                      className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                      onClick={() => handleToggleAlert(index)}
                    >
                      {alert.enabled ? <BellIcon className="h-4 w-4" /> : <BellSlashIcon className="h-4 w-4" />}
                    </button>
                  </Tooltip>
                  <Tooltip content="Modifier">
                    <button
                      type="button"
                      className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                      onClick={() => {
                        setNewAlert(alert);
                        setEditingAlertIndex(index);
                        setIsAddingAlert(true);
                      }}
                    >
                      <PencilIcon className="h-4 w-4" />
                    </button>
                  </Tooltip>
                  <Tooltip content="Supprimer">
                    <button
                      type="button"
                      className="rounded p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                      onClick={() => handleRemoveAlert(index)}
                    >
                      <TrashIcon className="h-4 w-4" />
                    </button>
                  </Tooltip>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Ajout/Modification d'alerte */}
        {isAddingAlert ? (
          <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                {editingAlertIndex !== null ? 'Modifier l\'alerte' : 'Ajouter une alerte'}
              </h4>
              <button
                type="button"
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                onClick={() => {
                  setIsAddingAlert(false);
                  setEditingAlertIndex(null);
                  setNewAlert({
                    name: '',
                    symbol: '',
                    condition: 'above',
                    value: 0,
                    channel: 'all',
                    enabled: true,
                  });
                }}
              >
                <XMarkIcon className="h-4 w-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Nom
                </label>
                <Input
                  type="text"
                  placeholder="Alerte BTC"
                  value={newAlert.name || ''}
                  onChange={(e) => setNewAlert({ ...newAlert, name: e.target.value })}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Symbole
                </label>
                <Input
                  type="text"
                  placeholder="BTCUSDT"
                  value={newAlert.symbol || ''}
                  onChange={(e) => setNewAlert({ ...newAlert, symbol: e.target.value.toUpperCase() })}
                />
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Condition
                </label>
                <Select
                  options={[
                    { value: 'above', label: 'Supérieur à' },
                    { value: 'below', label: 'Inférieur à' },
                    { value: 'cross_above', label: 'Croisement au-dessus' },
                    { value: 'cross_below', label: 'Croisement en-dessous' },
                    { value: 'between', label: 'Entre' },
                  ]}
                  value={newAlert.condition || 'above'}
                  onChange={(value) => setNewAlert({ ...newAlert, condition: value as any })}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Valeur
                </label>
                <Input
                  type="number"
                  value={newAlert.value || 0}
                  onChange={(e) => setNewAlert({ ...newAlert, value: parseFloat(e.target.value) || 0 })}
                  step={0.01}
                />
              </div>
            </div>

            {newAlert.condition === 'between' && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Valeur supérieure
                </label>
                <Input
                  type="number"
                  value={newAlert.value2 || 0}
                  onChange={(e) => setNewAlert({ ...newAlert, value2: parseFloat(e.target.value) || 0 })}
                  step={0.01}
                />
              </div>
            )}

            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Canal
                </label>
                <Select
                  options={[
                    { value: 'all', label: 'Tous les canaux' },
                    { value: 'email', label: 'Email' },
                    { value: 'push', label: 'Push' },
                    { value: 'sms', label: 'SMS' },
                  ]}
                  value={newAlert.channel || 'all'}
                  onChange={(value) => setNewAlert({ ...newAlert, channel: value as any })}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Activée
                </label>
                <div className="pt-2">
                  <Switch
                    checked={newAlert.enabled !== undefined ? newAlert.enabled : true}
                    onCheckedChange={(checked) => setNewAlert({ ...newAlert, enabled: checked })}
                  />
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsAddingAlert(false);
                  setEditingAlertIndex(null);
                  setNewAlert({
                    name: '',
                    symbol: '',
                    condition: 'above',
                    value: 0,
                    channel: 'all',
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
                onClick={editingAlertIndex !== null ? handleUpdateAlert : handleAddAlert}
              >
                {editingAlertIndex !== null ? 'Mettre à jour' : 'Ajouter'}
              </Button>
            </div>
          </div>
        ) : (
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => setIsAddingAlert(true)}
            disabled={disabled || isSubmitting || isLoading}
          >
            <PlusIcon className="h-4 w-4 mr-2" />
            Ajouter une alerte
          </Button>
        )}
      </div>
    );

    // ========================================================================
    // RENDU DE L'ONGLET PREFERENCES
    // ========================================================================

    const renderPreferencesTab = () => (
      <div className="space-y-6">
        {/* Notifications */}
        <div className="space-y-4">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Notifications
          </h4>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Afficher les notifications
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Recevoir des notifications pour les événements de trading
              </p>
            </div>
            <Switch
              checked={formData.preferences.showNotifications}
              onCheckedChange={(checked) => handlePreferenceChange('showNotifications', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          {formData.preferences.showNotifications && (
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Son des notifications
              </label>
              <Select
                options={NOTIFICATION_SOUNDS}
                value={formData.preferences.notificationSound}
                onChange={(value) => handlePreferenceChange('notificationSound', value as any)}
                disabled={disabled || isSubmitting || isLoading}
              />
            </div>
          )}
        </div>

        <Separator />

        {/* Trading automatique */}
        <div className="space-y-4">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Trading automatique
          </h4>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Confirmer les ordres
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Demander une confirmation avant l'exécution
              </p>
            </div>
            <Switch
              checked={formData.preferences.confirmOrders}
              onCheckedChange={(checked) => handlePreferenceChange('confirmOrders', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Auto-ajuster les positions
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Ajuster automatiquement la taille des positions
              </p>
            </div>
            <Switch
              checked={formData.preferences.autoAdjustPositions}
              onCheckedChange={(checked) => handlePreferenceChange('autoAdjustPositions', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Utiliser le trailing stop
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Activer le trailing stop par défaut
              </p>
            </div>
            <Switch
              checked={formData.preferences.useTrailingStop}
              onCheckedChange={(checked) => handlePreferenceChange('useTrailingStop', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          {formData.preferences.useTrailingStop && (
            <div className="pl-6 space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Distance du trailing stop (%)
              </label>
              <Input
                type="number"
                value={formData.preferences.trailingStopDistance}
                onChange={(e) => handlePreferenceChange('trailingStopDistance', parseFloat(e.target.value) || 2)}
                disabled={disabled || isSubmitting || isLoading}
                step={0.1}
                min={0.1}
                max={20}
              />
            </div>
          )}

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Trading automatique
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Exécuter automatiquement les signaux de trading
              </p>
            </div>
            <Switch
              checked={formData.preferences.autoTradingEnabled}
              onCheckedChange={(checked) => handlePreferenceChange('autoTradingEnabled', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <Separator />

        {/* Paper trading */}
        <div className="space-y-4">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Paper Trading
          </h4>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Activer le paper trading
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Simuler des trades sans risque réel
              </p>
            </div>
            <Switch
              checked={formData.preferences.paperTradingEnabled}
              onCheckedChange={(checked) => handlePreferenceChange('paperTradingEnabled', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          {formData.preferences.paperTradingEnabled && (
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Capital de paper trading
              </label>
              <Input
                type="number"
                value={formData.preferences.paperTradingCapital}
                onChange={(e) => handlePreferenceChange('paperTradingCapital', parseFloat(e.target.value) || 10000)}
                disabled={disabled || isSubmitting || isLoading}
                step={100}
                min={100}
              />
            </div>
          )}
        </div>

        <Separator />

        {/* Analyse */}
        <div className="space-y-4">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Analyse et logs
          </h4>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Logs de trading
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Enregistrer l'historique des trades
              </p>
            </div>
            <Switch
              checked={formData.preferences.tradingLogsEnabled}
              onCheckedChange={(checked) => handlePreferenceChange('tradingLogsEnabled', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Analyse technique
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Activer l'analyse technique automatique
              </p>
            </div>
            <Switch
              checked={formData.preferences.technicalAnalysisEnabled}
              onCheckedChange={(checked) => handlePreferenceChange('technicalAnalysisEnabled', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Backtesting
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Activer le backtesting des stratégies
              </p>
            </div>
            <Switch
              checked={formData.preferences.backtestingEnabled}
              onCheckedChange={(checked) => handlePreferenceChange('backtestingEnabled', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Nombre de barres pour l'analyse
              </label>
              <Input
                type="number"
                value={formData.preferences.analysisBars}
                onChange={(e) => handlePreferenceChange('analysisBars', parseInt(e.target.value) || 100)}
                disabled={disabled || isSubmitting || isLoading}
                min={1}
                max={1000}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Période de l'analyse
              </label>
              <Select
                options={ANALYSIS_PERIODS}
                value={formData.preferences.analysisPeriod}
                onChange={(value) => handlePreferenceChange('analysisPeriod', value as any)}
                disabled={disabled || isSubmitting || isLoading}
              />
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
                <Badge
                  variant={
                    formData.mode === 'automatic' ? 'success' :
                    formData.mode === 'semi_automatic' ? 'warning' :
                    formData.mode === 'paper' ? 'info' :
                    'default'
                  }
                  size="sm"
                >
                  {formData.mode === 'automatic' ? 'Auto' :
                   formData.mode === 'semi_automatic' ? 'Semi-auto' :
                   formData.mode === 'paper' ? 'Paper' :
                   'Manuel'}
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
              { id: 'general', label: '⚙️ Général' },
              { id: 'symbols', label: '📊 Symboles' },
              { id: 'alerts', label: '🔔 Alertes' },
              { id: 'preferences', label: '🎯 Préférences' },
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
                {activeTab === 'symbols' && renderSymbolsTab()}
                {activeTab === 'alerts' && renderAlertsTab()}
                {activeTab === 'preferences' && renderPreferencesTab()}
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
              Mode: {formData.mode === 'automatic' ? 'Automatique' :
                      formData.mode === 'semi_automatic' ? 'Semi-automatique' :
                      formData.mode === 'paper' ? 'Paper Trading' :
                      'Manuel'}
            </span>
            <span>
              {formData.activeSymbols.length} symboles actifs • 
              {formData.alerts.length} alertes
            </span>
          </div>
        </CardFooter>
      </Card>
    );
  }
);

TradingSettingsForm.displayName = 'TradingSettingsForm';

// ============================================================================
// EXPORTS
// ============================================================================

export default TradingSettingsForm;

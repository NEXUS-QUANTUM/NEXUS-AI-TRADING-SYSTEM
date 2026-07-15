// apps/web/src/components/forms/settings/RiskSettingsForm.tsx
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
  ExclamationTriangleIcon,
  CheckCircleIcon,
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
  ChartBarIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  WalletIcon,
  BanknotesIcon,
  CurrencyDollarIcon,
  PercentIcon,
  ScaleIcon,
  ShieldCheckIcon as ShieldCheckSolid,
  LockClosedIcon,
  LockOpenIcon,
  EyeIcon,
  EyeSlashIcon,
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

export type RiskLevel = 'conservative' | 'moderate' | 'aggressive' | 'custom';
export type StopLossType = 'fixed' | 'percentage' | 'atr' | 'trailing' | 'dynamic';
export type TakeProfitType = 'fixed' | 'percentage' | 'risk_reward' | 'dynamic';
export type PositionSizing = 'fixed' | 'percentage' | 'risk_based' | 'kelly' | 'custom';
export type RiskMetric = 'sharpe' | 'sortino' | 'calmar' | 'max_drawdown' | 'var' | 'cvar';
export type DrawdownAction = 'alert' | 'reduce' | 'pause' | 'stop';

export interface RiskRule {
  /** Identifiant */
  id: string;
  /** Nom */
  name: string;
  /** Condition */
  condition: string;
  /** Action */
  action: string;
  /** Paramètres */
  parameters: Record<string, any>;
  /** Est activée */
  enabled: boolean;
  /** Priorité */
  priority: number;
}

export interface RiskSettingsData {
  /** Niveau de risque */
  level: RiskLevel;
  /** Stop-loss par défaut */
  stopLoss: {
    /** Type */
    type: StopLossType;
    /** Valeur */
    value: number;
    /** Unité */
    unit: 'percent' | 'points' | 'atr';
    /** ATR période */
    atrPeriod?: number;
    /** ATR multiplicateur */
    atrMultiplier?: number;
  };
  /** Take-profit par défaut */
  takeProfit: {
    /** Type */
    type: TakeProfitType;
    /** Valeur */
    value: number;
    /** Unité */
    unit: 'percent' | 'points';
    /** Ratio risque/récompense */
    riskRewardRatio?: number;
  };
  /** Dimensionnement des positions */
  positionSizing: {
    /** Type */
    type: PositionSizing;
    /** Taille fixe */
    fixedSize?: number;
    /** Pourcentage du capital */
    percentage?: number;
    /** Risque par trade (en %) */
    riskPerTrade?: number;
    /** Kelly fraction */
    kellyFraction?: number;
    /** Capital maximal à risquer */
    maxCapitalRisk?: number;
  };
  /** Limites */
  limits: {
    /** Perte maximale quotidienne (%) */
    maxDailyLoss: number;
    /** Perte maximale hebdomadaire (%) */
    maxWeeklyLoss: number;
    /** Perte maximale mensuelle (%) */
    maxMonthlyLoss: number;
    /** Perte maximale par trade (%) */
    maxLossPerTrade: number;
    /** Gain maximal par trade (%) */
    maxGainPerTrade: number;
    /** Nombre maximal de trades par jour */
    maxTradesPerDay: number;
    /** Nombre maximal de trades par semaine */
    maxTradesPerWeek: number;
    /** Nombre maximal de trades par mois */
    maxTradesPerMonth: number;
    /** Positions maximales simultanées */
    maxConcurrentPositions: number;
    /** Exposition maximale du portefeuille (%) */
    maxPortfolioExposure: number;
  };
  /** Drawdown */
  drawdown: {
    /** Seuil d'alerte (%) */
    alertThreshold: number;
    /** Seuil de réduction (%) */
    reduceThreshold: number;
    /** Seuil de pause (%) */
    pauseThreshold: number;
    /** Seuil d'arrêt (%) */
    stopThreshold: number;
    /** Action à effectuer */
    action: DrawdownAction;
  };
  /** Métriques de risque */
  metrics: {
    /** Métriques à surveiller */
    metrics: RiskMetric[];
    /** Seuils */
    thresholds: Partial<Record<RiskMetric, number>>;
  };
  /** Règles personnalisées */
  rules: RiskRule[];
  /** Paramètres avancés */
  advanced: {
    /** Slippage toléré (%) */
    slippageTolerance: number;
    /** Spread maximal (%) */
    maxSpread: number;
    /** Volatilité maximale (%) */
    maxVolatility: number;
    /** Corrélation maximale entre positions */
    maxCorrelation: number;
    /** Utiliser les stops garantis */
    useGuaranteedStops: boolean;
    /** Utiliser les ordres OCO */
    useOCO: boolean;
    /** Désactiver le trading si volatilité élevée */
    disableOnHighVolatility: boolean;
    /** Seuil de volatilité pour désactivation */
    volatilityThreshold: number;
    /** Délai de refroidissement après perte (ms) */
    cooldownAfterLoss: number;
  };
  /** Historique */
  history?: Array<{
    timestamp: Date;
    event: string;
    details: string;
  }>;
}

export interface RiskSettingsFormProps {
  // --- Contrôle ---
  /** Données initiales */
  initialData?: Partial<RiskSettingsData>;
  /** Callback de soumission */
  onSubmit?: (data: RiskSettingsData) => void | Promise<void>;
  /** Callback de succès */
  onSuccess?: (data: RiskSettingsData) => void;
  /** Callback d'erreur */
  onError?: (error: string) => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de changement */
  onChange?: (data: RiskSettingsData) => void;

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

const RISK_LEVELS: { value: RiskLevel; label: string; color: string; description: string }[] = [
  {
    value: 'conservative',
    label: 'Conservateur',
    color: 'text-green-500',
    description: 'Risque minimal, protection du capital prioritaire',
  },
  {
    value: 'moderate',
    label: 'Modéré',
    color: 'text-yellow-500',
    description: 'Équilibre entre risque et rendement',
  },
  {
    value: 'aggressive',
    label: 'Agressif',
    color: 'text-red-500',
    description: 'Recherche de rendement maximal, risque élevé',
  },
  {
    value: 'custom',
    label: 'Personnalisé',
    color: 'text-blue-500',
    description: 'Configuration manuelle des paramètres',
  },
];

const STOP_LOSS_TYPES: { value: StopLossType; label: string; description: string }[] = [
  { value: 'fixed', label: 'Fixé', description: 'Stop-loss à un prix fixe' },
  { value: 'percentage', label: 'Pourcentage', description: 'Stop-loss en pourcentage du prix' },
  { value: 'atr', label: 'ATR', description: 'Stop-loss basé sur l\'ATR' },
  { value: 'trailing', label: 'Trailing', description: 'Stop-loss suiveur' },
  { value: 'dynamic', label: 'Dynamique', description: 'Stop-loss ajusté dynamiquement' },
];

const TAKE_PROFIT_TYPES: { value: TakeProfitType; label: string; description: string }[] = [
  { value: 'fixed', label: 'Fixé', description: 'Take-profit à un prix fixe' },
  { value: 'percentage', label: 'Pourcentage', description: 'Take-profit en pourcentage du prix' },
  { value: 'risk_reward', label: 'Risque/Récompense', description: 'Basé sur le ratio risque/récompense' },
  { value: 'dynamic', label: 'Dynamique', description: 'Take-profit ajusté dynamiquement' },
];

const POSITION_SIZING_TYPES: { value: PositionSizing; label: string; description: string }[] = [
  { value: 'fixed', label: 'Fixé', description: 'Taille de position fixe' },
  { value: 'percentage', label: 'Pourcentage', description: 'Pourcentage du capital' },
  { value: 'risk_based', label: 'Basé sur le risque', description: 'Taille basée sur le risque par trade' },
  { value: 'kelly', label: 'Kelly', description: 'Critère de Kelly' },
  { value: 'custom', label: 'Personnalisé', description: 'Paramètres personnalisés' },
];

const RISK_METRICS: { value: RiskMetric; label: string; description: string }[] = [
  { value: 'sharpe', label: 'Sharpe', description: 'Ratio de Sharpe' },
  { value: 'sortino', label: 'Sortino', description: 'Ratio de Sortino' },
  { value: 'calmar', label: 'Calmar', description: 'Ratio de Calmar' },
  { value: 'max_drawdown', label: 'Max Drawdown', description: 'Perte maximale' },
  { value: 'var', label: 'VaR', description: 'Value at Risk' },
  { value: 'cvar', label: 'CVaR', description: 'Conditional Value at Risk' },
];

const DRAWDOWN_ACTIONS: { value: DrawdownAction; label: string; description: string }[] = [
  { value: 'alert', label: 'Alerte', description: 'Envoyer une alerte' },
  { value: 'reduce', label: 'Réduire', description: 'Réduire la taille des positions' },
  { value: 'pause', label: 'Pause', description: 'Pause du trading' },
  { value: 'stop', label: 'Arrêt', description: 'Arrêt complet du trading' },
];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const RiskSettingsForm = forwardRef<HTMLDivElement, RiskSettingsFormProps>(
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
      title = 'Gestion des risques',
      subtitle = 'Configurez vos paramètres de gestion des risques',
      className,
      variant = 'default',

      // États
      isLoading = false,
      error = null,
      success = null,
      disabled = false,

      // Accessibilité
      ariaLabel = 'Paramètres de gestion des risques',
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

    const [formData, setFormData] = useState<RiskSettingsData>({
      level: 'moderate',
      stopLoss: {
        type: 'percentage',
        value: 2,
        unit: 'percent',
        atrPeriod: 14,
        atrMultiplier: 2,
      },
      takeProfit: {
        type: 'risk_reward',
        value: 2,
        unit: 'percent',
        riskRewardRatio: 2,
      },
      positionSizing: {
        type: 'risk_based',
        riskPerTrade: 2,
        maxCapitalRisk: 20,
      },
      limits: {
        maxDailyLoss: 5,
        maxWeeklyLoss: 10,
        maxMonthlyLoss: 20,
        maxLossPerTrade: 3,
        maxGainPerTrade: 10,
        maxTradesPerDay: 10,
        maxTradesPerWeek: 50,
        maxTradesPerMonth: 200,
        maxConcurrentPositions: 5,
        maxPortfolioExposure: 80,
      },
      drawdown: {
        alertThreshold: 5,
        reduceThreshold: 10,
        pauseThreshold: 15,
        stopThreshold: 20,
        action: 'alert',
      },
      metrics: {
        metrics: ['sharpe', 'max_drawdown'],
        thresholds: {
          sharpe: 1,
          max_drawdown: 20,
        },
      },
      rules: [],
      advanced: {
        slippageTolerance: 0.5,
        maxSpread: 0.2,
        maxVolatility: 5,
        maxCorrelation: 0.7,
        useGuaranteedStops: false,
        useOCO: true,
        disableOnHighVolatility: false,
        volatilityThreshold: 10,
        cooldownAfterLoss: 60000,
      },
      ...initialData,
    });

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [activeTab, setActiveTab] = useState<'general' | 'limits' | 'drawdown' | 'advanced'>('general');
    const [isAddingRule, setIsAddingRule] = useState(false);
    const [editingRuleIndex, setEditingRuleIndex] = useState<number | null>(null);
    const [newRule, setNewRule] = useState<Partial<RiskRule>>({
      name: '',
      condition: '',
      action: '',
      parameters: {},
      enabled: true,
      priority: 1,
    });
    const [selectedMetric, setSelectedMetric] = useState<RiskMetric>('sharpe');

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validate = useCallback((): boolean => {
      const errors: Record<string, string> = {};

      // Stop-loss
      if (formData.stopLoss.value <= 0) {
        errors.stopLoss = 'Le stop-loss doit être supérieur à 0';
      }

      // Take-profit
      if (formData.takeProfit.value <= 0) {
        errors.takeProfit = 'Le take-profit doit être supérieur à 0';
      }

      // Limites
      if (formData.limits.maxDailyLoss < 0) {
        errors.maxDailyLoss = 'La perte quotidienne maximale doit être positive';
      }
      if (formData.limits.maxConcurrentPositions < 1) {
        errors.maxConcurrentPositions = 'Au moins 1 position simultanée';
      }
      if (formData.limits.maxPortfolioExposure < 0 || formData.limits.maxPortfolioExposure > 100) {
        errors.maxPortfolioExposure = 'L\'exposition doit être entre 0% et 100%';
      }

      // Drawdown
      if (formData.drawdown.alertThreshold < 0 || formData.drawdown.alertThreshold > 100) {
        errors.drawdownAlert = 'Le seuil d\'alerte doit être entre 0% et 100%';
      }

      setFormErrors(errors);
      return Object.keys(errors).length === 0;
    }, [formData]);

    // ========================================================================
    // GESTIONNAIRES DE CHAMPS
    // ========================================================================

    const handleFieldChange = useCallback(<K extends keyof RiskSettingsData>(
      field: K,
      value: RiskSettingsData[K]
    ) => {
      setFormData(prev => ({ ...prev, [field]: value }));
      setFormErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }, []);

    const handleNestedFieldChange = useCallback(
      <P extends keyof RiskSettingsData, K extends string>(
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

    const handleLimitChange = useCallback(<K extends keyof RiskSettingsData['limits']>(
      field: K,
      value: RiskSettingsData['limits'][K]
    ) => {
      setFormData(prev => ({
        ...prev,
        limits: { ...prev.limits, [field]: value },
      }));
      setFormErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }, []);

    // ========================================================================
    // GESTION DES RÈGLES
    // ========================================================================

    const handleAddRule = useCallback(() => {
      if (!newRule.name || !newRule.condition || !newRule.action) {
        toast({
          title: 'Erreur',
          description: 'Tous les champs sont requis',
          variant: 'destructive',
        });
        return;
      }

      const rule: RiskRule = {
        id: `rule_${Date.now()}`,
        name: newRule.name,
        condition: newRule.condition,
        action: newRule.action,
        parameters: newRule.parameters || {},
        enabled: newRule.enabled !== undefined ? newRule.enabled : true,
        priority: newRule.priority || 1,
      };

      setFormData(prev => ({
        ...prev,
        rules: [...prev.rules, rule],
      }));

      setNewRule({
        name: '',
        condition: '',
        action: '',
        parameters: {},
        enabled: true,
        priority: 1,
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
      if (!newRule.name || !newRule.condition || !newRule.action) {
        toast({
          title: 'Erreur',
          description: 'Tous les champs sont requis',
          variant: 'destructive',
        });
        return;
      }

      setFormData(prev => {
        const newRules = [...prev.rules];
        newRules[editingRuleIndex] = {
          ...newRules[editingRuleIndex],
          name: newRule.name,
          condition: newRule.condition,
          action: newRule.action,
          parameters: newRule.parameters || {},
          enabled: newRule.enabled !== undefined ? newRule.enabled : true,
          priority: newRule.priority || 1,
        };
        return { ...prev, rules: newRules };
      });

      setNewRule({
        name: '',
        condition: '',
        action: '',
        parameters: {},
        enabled: true,
        priority: 1,
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
          description: 'La configuration des risques a été mise à jour',
          variant: 'success',
        });

        if (debug) {
          console.log('Risk settings saved:', formData);
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
        {/* Niveau de risque */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Niveau de risque
          </label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {RISK_LEVELS.map((level) => (
              <button
                key={level.value}
                type="button"
                className={cn(
                  'rounded-lg border-2 p-3 text-center transition-all',
                  formData.level === level.value
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
                onClick={() => handleFieldChange('level', level.value)}
                disabled={disabled || isSubmitting || isLoading}
              >
                <span className={cn('text-sm font-medium', level.color)}>
                  {level.label}
                </span>
                <p className="text-xs text-gray-500 dark:text-gray-400 mt-1">
                  {level.description}
                </p>
              </button>
            ))}
          </div>
        </div>

        <Separator />

        {/* Stop-loss */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Stop-loss par défaut
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Type
              </label>
              <Select
                options={STOP_LOSS_TYPES.map(s => ({ value: s.value, label: `${s.label} - ${s.description}` }))}
                value={formData.stopLoss.type}
                onChange={(value) => handleNestedFieldChange('stopLoss', 'type', value)}
                disabled={disabled || isSubmitting || isLoading}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Valeur
              </label>
              <Input
                type="number"
                value={formData.stopLoss.value}
                onChange={(e) => handleNestedFieldChange('stopLoss', 'value', parseFloat(e.target.value) || 0)}
                error={formErrors.stopLoss}
                disabled={disabled || isSubmitting || isLoading}
                step={0.1}
                min={0.1}
              />
            </div>
          </div>

          {formData.stopLoss.type === 'atr' && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Période ATR
                </label>
                <Input
                  type="number"
                  value={formData.stopLoss.atrPeriod || 14}
                  onChange={(e) => handleNestedFieldChange('stopLoss', 'atrPeriod', parseInt(e.target.value) || 14)}
                  disabled={disabled || isSubmitting || isLoading}
                  min={1}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Multiplicateur ATR
                </label>
                <Input
                  type="number"
                  value={formData.stopLoss.atrMultiplier || 2}
                  onChange={(e) => handleNestedFieldChange('stopLoss', 'atrMultiplier', parseFloat(e.target.value) || 2)}
                  disabled={disabled || isSubmitting || isLoading}
                  step={0.1}
                  min={0.1}
                />
              </div>
            </div>
          )}
        </div>

        <Separator />

        {/* Take-profit */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Take-profit par défaut
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Type
              </label>
              <Select
                options={TAKE_PROFIT_TYPES.map(t => ({ value: t.value, label: `${t.label} - ${t.description}` }))}
                value={formData.takeProfit.type}
                onChange={(value) => handleNestedFieldChange('takeProfit', 'type', value)}
                disabled={disabled || isSubmitting || isLoading}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Valeur
              </label>
              <Input
                type="number"
                value={formData.takeProfit.value}
                onChange={(e) => handleNestedFieldChange('takeProfit', 'value', parseFloat(e.target.value) || 0)}
                error={formErrors.takeProfit}
                disabled={disabled || isSubmitting || isLoading}
                step={0.1}
                min={0.1}
              />
            </div>
          </div>

          {formData.takeProfit.type === 'risk_reward' && (
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Ratio risque/récompense
              </label>
              <Input
                type="number"
                value={formData.takeProfit.riskRewardRatio || 2}
                onChange={(e) => handleNestedFieldChange('takeProfit', 'riskRewardRatio', parseFloat(e.target.value) || 2)}
                disabled={disabled || isSubmitting || isLoading}
                step={0.1}
                min={0.1}
              />
            </div>
          )}
        </div>

        <Separator />

        {/* Position sizing */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Dimensionnement des positions
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Type
              </label>
              <Select
                options={POSITION_SIZING_TYPES.map(p => ({ value: p.value, label: `${p.label} - ${p.description}` }))}
                value={formData.positionSizing.type}
                onChange={(value) => handleNestedFieldChange('positionSizing', 'type', value)}
                disabled={disabled || isSubmitting || isLoading}
              />
            </div>
            {formData.positionSizing.type === 'fixed' && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Taille fixe
                </label>
                <Input
                  type="number"
                  value={formData.positionSizing.fixedSize || 0}
                  onChange={(e) => handleNestedFieldChange('positionSizing', 'fixedSize', parseFloat(e.target.value) || 0)}
                  disabled={disabled || isSubmitting || isLoading}
                  step={0.01}
                  min={0.01}
                />
              </div>
            )}
            {formData.positionSizing.type === 'percentage' && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Pourcentage du capital
                </label>
                <Input
                  type="number"
                  value={formData.positionSizing.percentage || 0}
                  onChange={(e) => handleNestedFieldChange('positionSizing', 'percentage', parseFloat(e.target.value) || 0)}
                  disabled={disabled || isSubmitting || isLoading}
                  step={0.1}
                  min={0.1}
                  max={100}
                />
              </div>
            )}
            {formData.positionSizing.type === 'risk_based' && (
              <>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Risque par trade (%)
                  </label>
                  <Input
                    type="number"
                    value={formData.positionSizing.riskPerTrade || 0}
                    onChange={(e) => handleNestedFieldChange('positionSizing', 'riskPerTrade', parseFloat(e.target.value) || 0)}
                    disabled={disabled || isSubmitting || isLoading}
                    step={0.1}
                    min={0.1}
                    max={100}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Capital maximal à risquer (%)
                  </label>
                  <Input
                    type="number"
                    value={formData.positionSizing.maxCapitalRisk || 0}
                    onChange={(e) => handleNestedFieldChange('positionSizing', 'maxCapitalRisk', parseFloat(e.target.value) || 0)}
                    disabled={disabled || isSubmitting || isLoading}
                    step={0.1}
                    min={0.1}
                    max={100}
                  />
                </div>
              </>
            )}
            {formData.positionSizing.type === 'kelly' && (
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Fraction de Kelly
                </label>
                <Input
                  type="number"
                  value={formData.positionSizing.kellyFraction || 0.5}
                  onChange={(e) => handleNestedFieldChange('positionSizing', 'kellyFraction', parseFloat(e.target.value) || 0.5)}
                  disabled={disabled || isSubmitting || isLoading}
                  step={0.01}
                  min={0.01}
                  max={1}
                />
              </div>
            )}
          </div>
        </div>
      </div>
    );

    // ========================================================================
    // RENDU DE L'ONGLET LIMITES
    // ========================================================================

    const renderLimitsTab = () => (
      <div className="space-y-6">
        {/* Pertes maximales */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Pertes maximales
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Quotidienne (%)
              </label>
              <Input
                type="number"
                value={formData.limits.maxDailyLoss}
                onChange={(e) => handleLimitChange('maxDailyLoss', parseFloat(e.target.value) || 0)}
                error={formErrors.maxDailyLoss}
                disabled={disabled || isSubmitting || isLoading}
                step={0.1}
                min={0}
                max={100}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Hebdomadaire (%)
              </label>
              <Input
                type="number"
                value={formData.limits.maxWeeklyLoss}
                onChange={(e) => handleLimitChange('maxWeeklyLoss', parseFloat(e.target.value) || 0)}
                disabled={disabled || isSubmitting || isLoading}
                step={0.1}
                min={0}
                max={100}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Mensuelle (%)
              </label>
              <Input
                type="number"
                value={formData.limits.maxMonthlyLoss}
                onChange={(e) => handleLimitChange('maxMonthlyLoss', parseFloat(e.target.value) || 0)}
                disabled={disabled || isSubmitting || isLoading}
                step={0.1}
                min={0}
                max={100}
              />
            </div>
          </div>
        </div>

        <Separator />

        {/* Limites par trade */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Limites par trade
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Perte maximale (%)
              </label>
              <Input
                type="number"
                value={formData.limits.maxLossPerTrade}
                onChange={(e) => handleLimitChange('maxLossPerTrade', parseFloat(e.target.value) || 0)}
                disabled={disabled || isSubmitting || isLoading}
                step={0.1}
                min={0}
                max={100}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Gain maximal (%)
              </label>
              <Input
                type="number"
                value={formData.limits.maxGainPerTrade}
                onChange={(e) => handleLimitChange('maxGainPerTrade', parseFloat(e.target.value) || 0)}
                disabled={disabled || isSubmitting || isLoading}
                step={0.1}
                min={0}
                max={100}
              />
            </div>
          </div>
        </div>

        <Separator />

        {/* Nombre de trades */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Nombre de trades
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Par jour
              </label>
              <Input
                type="number"
                value={formData.limits.maxTradesPerDay}
                onChange={(e) => handleLimitChange('maxTradesPerDay', parseInt(e.target.value) || 0)}
                disabled={disabled || isSubmitting || isLoading}
                min={0}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Par semaine
              </label>
              <Input
                type="number"
                value={formData.limits.maxTradesPerWeek}
                onChange={(e) => handleLimitChange('maxTradesPerWeek', parseInt(e.target.value) || 0)}
                disabled={disabled || isSubmitting || isLoading}
                min={0}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Par mois
              </label>
              <Input
                type="number"
                value={formData.limits.maxTradesPerMonth}
                onChange={(e) => handleLimitChange('maxTradesPerMonth', parseInt(e.target.value) || 0)}
                disabled={disabled || isSubmitting || isLoading}
                min={0}
              />
            </div>
          </div>
        </div>

        <Separator />

        {/* Positions */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Positions
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Positions simultanées maximales
              </label>
              <Input
                type="number"
                value={formData.limits.maxConcurrentPositions}
                onChange={(e) => handleLimitChange('maxConcurrentPositions', parseInt(e.target.value) || 0)}
                error={formErrors.maxConcurrentPositions}
                disabled={disabled || isSubmitting || isLoading}
                min={1}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Exposition maximale du portefeuille (%)
              </label>
              <Input
                type="number"
                value={formData.limits.maxPortfolioExposure}
                onChange={(e) => handleLimitChange('maxPortfolioExposure', parseFloat(e.target.value) || 0)}
                error={formErrors.maxPortfolioExposure}
                disabled={disabled || isSubmitting || isLoading}
                step={0.1}
                min={0}
                max={100}
              />
            </div>
          </div>
        </div>
      </div>
    );

    // ========================================================================
    // RENDU DE L'ONGLET DRAWDOWN
    // ========================================================================

    const renderDrawdownTab = () => (
      <div className="space-y-6">
        {/* Seuils */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Seuils de drawdown
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Seuil d'alerte (%)
              </label>
              <Input
                type="number"
                value={formData.drawdown.alertThreshold}
                onChange={(e) => handleNestedFieldChange('drawdown', 'alertThreshold', parseFloat(e.target.value) || 0)}
                error={formErrors.drawdownAlert}
                disabled={disabled || isSubmitting || isLoading}
                step={0.1}
                min={0}
                max={100}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Seuil de réduction (%)
              </label>
              <Input
                type="number"
                value={formData.drawdown.reduceThreshold}
                onChange={(e) => handleNestedFieldChange('drawdown', 'reduceThreshold', parseFloat(e.target.value) || 0)}
                disabled={disabled || isSubmitting || isLoading}
                step={0.1}
                min={0}
                max={100}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Seuil de pause (%)
              </label>
              <Input
                type="number"
                value={formData.drawdown.pauseThreshold}
                onChange={(e) => handleNestedFieldChange('drawdown', 'pauseThreshold', parseFloat(e.target.value) || 0)}
                disabled={disabled || isSubmitting || isLoading}
                step={0.1}
                min={0}
                max={100}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Seuil d'arrêt (%)
              </label>
              <Input
                type="number"
                value={formData.drawdown.stopThreshold}
                onChange={(e) => handleNestedFieldChange('drawdown', 'stopThreshold', parseFloat(e.target.value) || 0)}
                disabled={disabled || isSubmitting || isLoading}
                step={0.1}
                min={0}
                max={100}
              />
            </div>
          </div>
        </div>

        <Separator />

        {/* Action */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Action en cas de drawdown
          </h4>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Action
            </label>
            <Select
              options={DRAWDOWN_ACTIONS.map(d => ({ value: d.value, label: `${d.label} - ${d.description}` }))}
              value={formData.drawdown.action}
              onChange={(value) => handleNestedFieldChange('drawdown', 'action', value)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <Separator />

        {/* Métriques de risque */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Métriques de risque
          </h4>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Métriques à surveiller
            </label>
            <div className="flex flex-wrap gap-2">
              {RISK_METRICS.map((metric) => (
                <button
                  key={metric.value}
                  type="button"
                  className={cn(
                    'flex items-center gap-1 rounded-lg border-2 px-3 py-1.5 text-sm transition-all',
                    formData.metrics.metrics.includes(metric.value)
                      ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-400'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                  )}
                  onClick={() => {
                    const metrics = formData.metrics.metrics;
                    const newMetrics = metrics.includes(metric.value)
                      ? metrics.filter(m => m !== metric.value)
                      : [...metrics, metric.value];
                    handleNestedFieldChange('metrics', 'metrics', newMetrics);
                  }}
                  disabled={disabled || isSubmitting || isLoading}
                >
                  {metric.label}
                </button>
              ))}
            </div>
          </div>

          {formData.metrics.metrics.map((metric) => {
            const info = RISK_METRICS.find(m => m.value === metric);
            return (
              <div key={metric} className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Seuil {info?.label}
                </label>
                <Input
                  type="number"
                  value={formData.metrics.thresholds[metric] || 0}
                  onChange={(e) => {
                    const newThresholds = { ...formData.metrics.thresholds };
                    newThresholds[metric] = parseFloat(e.target.value) || 0;
                    handleNestedFieldChange('metrics', 'thresholds', newThresholds);
                  }}
                  disabled={disabled || isSubmitting || isLoading}
                  step={0.1}
                />
              </div>
            );
          })}
        </div>
      </div>
    );

    // ========================================================================
    // RENDU DE L'ONGLET AVANCÉ
    // ========================================================================

    const renderAdvancedTab = () => (
      <div className="space-y-6">
        {/* Paramètres avancés */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Paramètres avancés
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Slippage toléré (%)
              </label>
              <Input
                type="number"
                value={formData.advanced.slippageTolerance}
                onChange={(e) => handleNestedFieldChange('advanced', 'slippageTolerance', parseFloat(e.target.value) || 0)}
                disabled={disabled || isSubmitting || isLoading}
                step={0.01}
                min={0}
                max={100}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Spread maximal (%)
              </label>
              <Input
                type="number"
                value={formData.advanced.maxSpread}
                onChange={(e) => handleNestedFieldChange('advanced', 'maxSpread', parseFloat(e.target.value) || 0)}
                disabled={disabled || isSubmitting || isLoading}
                step={0.01}
                min={0}
                max={100}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Volatilité maximale (%)
              </label>
              <Input
                type="number"
                value={formData.advanced.maxVolatility}
                onChange={(e) => handleNestedFieldChange('advanced', 'maxVolatility', parseFloat(e.target.value) || 0)}
                disabled={disabled || isSubmitting || isLoading}
                step={0.1}
                min={0}
                max={100}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Corrélation maximale
              </label>
              <Input
                type="number"
                value={formData.advanced.maxCorrelation}
                onChange={(e) => handleNestedFieldChange('advanced', 'maxCorrelation', parseFloat(e.target.value) || 0)}
                disabled={disabled || isSubmitting || isLoading}
                step={0.01}
                min={0}
                max={1}
              />
            </div>
          </div>
        </div>

        <Separator />

        {/* Options */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Utiliser les stops garantis
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Garantir l'exécution du stop-loss au prix spécifié
              </p>
            </div>
            <Switch
              checked={formData.advanced.useGuaranteedStops}
              onCheckedChange={(checked) => handleNestedFieldChange('advanced', 'useGuaranteedStops', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Utiliser les ordres OCO
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                One Cancels Other - annulation mutuelle des ordres
              </p>
            </div>
            <Switch
              checked={formData.advanced.useOCO}
              onCheckedChange={(checked) => handleNestedFieldChange('advanced', 'useOCO', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Désactiver le trading si volatilité élevée
              </p>
              <p className="text-xs text-gray-500 dark:text-gray-400">
                Arrêter automatiquement le trading en période de forte volatilité
              </p>
            </div>
            <Switch
              checked={formData.advanced.disableOnHighVolatility}
              onCheckedChange={(checked) => handleNestedFieldChange('advanced', 'disableOnHighVolatility', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          {formData.advanced.disableOnHighVolatility && (
            <div className="pl-6 space-y-2">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Seuil de volatilité pour désactivation (%)
              </label>
              <Input
                type="number"
                value={formData.advanced.volatilityThreshold}
                onChange={(e) => handleNestedFieldChange('advanced', 'volatilityThreshold', parseFloat(e.target.value) || 0)}
                disabled={disabled || isSubmitting || isLoading}
                step={0.1}
                min={0}
                max={100}
              />
            </div>
          )}

          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Délai de refroidissement après perte (ms)
            </label>
            <Input
              type="number"
              value={formData.advanced.cooldownAfterLoss}
              onChange={(e) => handleNestedFieldChange('advanced', 'cooldownAfterLoss', parseInt(e.target.value) || 60000)}
              disabled={disabled || isSubmitting || isLoading}
              step={1000}
              min={0}
            />
          </div>
        </div>

        <Separator />

        {/* Règles personnalisées */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Règles personnalisées
          </h4>

          {formData.rules.length > 0 && (
            <div className="space-y-2">
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
                      <Badge variant="outline" size="xs">
                        Priorité {rule.priority}
                      </Badge>
                      {!rule.enabled && (
                        <Badge variant="outline" size="xs">Désactivée</Badge>
                      )}
                    </div>
                    <div className="flex flex-wrap gap-1 mt-1">
                      <Badge variant="outline" size="xs" className="text-xs">
                        Condition: {rule.condition}
                      </Badge>
                      <Badge variant="outline" size="xs" className="text-xs">
                        Action: {rule.action}
                      </Badge>
                    </div>
                  </div>
                  <div className="flex items-center gap-1">
                    <Tooltip content={rule.enabled ? 'Désactiver' : 'Activer'}>
                      <button
                        type="button"
                        className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                        onClick={() => handleToggleRule(index)}
                      >
                        {rule.enabled ? <ShieldCheckIcon className="h-4 w-4" /> : <ShieldExclamationIcon className="h-4 w-4" />}
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

          {isAddingRule ? (
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
                      condition: '',
                      action: '',
                      parameters: {},
                      enabled: true,
                      priority: 1,
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
                    Condition
                  </label>
                  <Input
                    type="text"
                    placeholder="drawdown > 10%"
                    value={newRule.condition || ''}
                    onChange={(e) => setNewRule({ ...newRule, condition: e.target.value })}
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Action
                  </label>
                  <Input
                    type="text"
                    placeholder="reduce_position_size"
                    value={newRule.action || ''}
                    onChange={(e) => setNewRule({ ...newRule, action: e.target.value })}
                  />
                </div>

                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Priorité
                    </label>
                    <Input
                      type="number"
                      value={newRule.priority || 1}
                      onChange={(e) => setNewRule({ ...newRule, priority: parseInt(e.target.value) || 1 })}
                      min={1}
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
                      condition: '',
                      action: '',
                      parameters: {},
                      enabled: true,
                      priority: 1,
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
          ) : (
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
                    formData.level === 'conservative' ? 'success' :
                    formData.level === 'moderate' ? 'warning' :
                    formData.level === 'aggressive' ? 'danger' :
                    'default'
                  }
                  size="sm"
                  className="capitalize"
                >
                  {formData.level === 'conservative' ? 'Conservateur' :
                   formData.level === 'moderate' ? 'Modéré' :
                   formData.level === 'aggressive' ? 'Agressif' :
                   'Personnalisé'}
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
              { id: 'limits', label: '📊 Limites' },
              { id: 'drawdown', label: '📉 Drawdown' },
              { id: 'advanced', label: '🔧 Avancé' },
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
                {activeTab === 'limits' && renderLimitsTab()}
                {activeTab === 'drawdown' && renderDrawdownTab()}
                {activeTab === 'advanced' && renderAdvancedTab()}
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
              Niveau: {formData.level === 'conservative' ? 'Conservateur' :
                       formData.level === 'moderate' ? 'Modéré' :
                       formData.level === 'aggressive' ? 'Agressif' :
                       'Personnalisé'}
            </span>
            <span>
              {formData.rules.length} règles • 
              Stop-loss: {formData.stopLoss.type} • 
              Take-profit: {formData.takeProfit.type}
            </span>
          </div>
        </CardFooter>
      </Card>
    );
  }
);

RiskSettingsForm.displayName = 'RiskSettingsForm';

// ============================================================================
// EXPORTS
// ============================================================================

export default RiskSettingsForm;

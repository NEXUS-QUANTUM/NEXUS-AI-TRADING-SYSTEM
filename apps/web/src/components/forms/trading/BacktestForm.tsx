// apps/web/src/components/forms/trading/BacktestForm.tsx
/**
 * NEXUS AI TRADING SYSTEM - Backtest Form Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * Ce composant permet de configurer et d'exécuter des backtests
 * sur les stratégies de trading avec des paramètres avancés.
 */

'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useForm, useFieldArray, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import {
  Loader2,
  Play,
  BarChart3,
  Calendar,
  Clock,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Download,
  Eye,
  Settings,
  Sliders,
  FileBarChart,
  RefreshCw,
  Plus,
  Trash2,
  ChevronDown,
  ChevronRight,
} from 'lucide-react';

// NEXUS Internal Components
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Checkbox } from '@/components/ui/checkbox';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Calendar as CalendarComponent } from '@/components/ui/calendar';
import { Progress } from '@/components/ui/progress';
import { Separator } from '@/components/ui/separator';
import { ScrollArea } from '@/components/ui/scroll-area';
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';

// NEXUS Hooks & Services
import { useBacktest } from '@/hooks/trading/useBacktest';
import { useStrategies } from '@/hooks/trading/useStrategies';
import { useMarketData } from '@/hooks/market/useMarketData';
import { useWebSocket } from '@/hooks/websocket/useWebSocket';
import { useDebounce } from '@/hooks/utils/useDebounce';

// NEXUS Types
import type {
  BacktestRequest,
  BacktestResponse,
  BacktestResult,
  Strategy,
  MarketSymbol,
  BacktestMetrics,
  Trade,
} from '@/types/trading';

// NEXUS Constants
import {
  TIMEFRAMES,
  BACKTEST_TYPES,
  PERFORMANCE_METRICS,
  DEFAULT_BACKTEST_CONFIG,
  MAX_BACKTEST_DURATION,
} from '@/constants/trading';

// Styles
import '@/styles/forms/trading/backtest-form.css';

/**
 * SCHÉMA DE VALIDATION
 * Zod schema pour la validation du formulaire de backtest
 */
const backtestSchema = z
  .object({
    // Informations générales
    name: z.string()
      .min(3, 'Le nom doit contenir au moins 3 caractères')
      .max(100, 'Le nom ne peut pas dépasser 100 caractères')
      .regex(/^[a-zA-Z0-9\s\-_]+$/, 'Caractères invalides détectés'),

    description: z.string()
      .max(500, 'La description ne peut pas dépasser 500 caractères')
      .optional(),

    // Configuration de la stratégie
    strategyId: z.string().uuid('ID de stratégie invalide'),
    symbol: z.string().min(1, 'Symbole requis'),
    timeframe: z.enum(['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w', '1M']),

    // Période de backtest
    startDate: z.date({
      required_error: 'Date de début requise',
      invalid_type_error: 'Date de début invalide',
    }),
    endDate: z.date({
      required_error: 'Date de fin requise',
      invalid_type_error: 'Date de fin invalide',
    }),

    // Paramètres de backtest
    backtestType: z.enum(['STANDARD', 'WALK_FORWARD', 'MONTE_CARLO']),
    initialCapital: z.number()
      .min(100, 'Le capital minimum est de 100$')
      .max(1000000000, 'Le capital maximum est de 1 milliard $'),

    // Paramètres de trading
    commission: z.number()
      .min(0, 'La commission ne peut pas être négative')
      .max(10, 'La commission maximum est de 10%')
      .default(0.1),

    slippage: z.number()
      .min(0, 'Le slippage ne peut pas être négatif')
      .max(5, 'Le slippage maximum est de 5%')
      .default(0.05),

    positionSize: z.enum(['FIXED', 'PERCENTAGE', 'KELLY', 'RISK_PARITY']),
    positionSizeValue: z.number()
      .min(0.1, 'La valeur minimum est de 0.1%')
      .max(100, 'La valeur maximum est de 100%')
      .default(2),

    maxPositions: z.number()
      .int('Doit être un nombre entier')
      .min(1, 'Minimum 1 position')
      .max(100, 'Maximum 100 positions')
      .default(10),

    // Paramètres de risque
    useStopLoss: z.boolean().default(true),
    stopLossPercent: z.number()
      .min(0.1, 'Le stop-loss minimum est de 0.1%')
      .max(20, 'Le stop-loss maximum est de 20%')
      .default(5),

    useTakeProfit: z.boolean().default(true),
    takeProfitPercent: z.number()
      .min(1, 'Le take-profit minimum est de 1%')
      .max(100, 'Le take-profit maximum est de 100%')
      .default(15),

    useTrailingStop: z.boolean().default(false),
    trailingStopPercent: z.number()
      .min(0.1, 'Le trailing stop minimum est de 0.1%')
      .max(10, 'Le trailing stop maximum est de 10%')
      .default(2),

    // Paramètres avancés
    useDynamicPositionSizing: z.boolean().default(false),
    allowShortSelling: z.boolean().default(false),
    useMargin: z.boolean().default(false),
    marginRatio: z.number()
      .min(1, 'Le ratio de marge minimum est de 1%')
      .max(100, 'Le ratio de marge maximum est de 100%')
      .default(50),

    // Paramètres de sortie
    metricsToTrack: z.array(z.string())
      .min(1, 'Sélectionnez au moins une métrique'),

    generateReport: z.boolean().default(true),
    includeTrades: z.boolean().default(true),
    includeCharts: z.boolean().default(false),

    // Paramètres de simulation
    numberOfSimulations: z.number()
      .int('Doit être un nombre entier')
      .min(1, 'Minimum 1 simulation')
      .max(1000, 'Maximum 1000 simulations')
      .default(100)
      .optional(),

    walkForwardWindow: z.number()
      .int('Doit être un nombre entier')
      .min(10, 'Minimum 10 périodes')
      .max(100, 'Maximum 100 périodes')
      .default(50)
      .optional(),
  })
  .refine(
    (data) => {
      // Validation : La date de fin doit être après la date de début
      return data.endDate > data.startDate;
    },
    {
      message: 'La date de fin doit être après la date de début',
      path: ['endDate'],
    }
  )
  .refine(
    (data) => {
      // Validation : La durée du backtest ne doit pas dépasser MAX_BACKTEST_DURATION
      const duration =
        data.endDate.getTime() - data.startDate.getTime();
      const maxDuration = MAX_BACKTEST_DURATION * 24 * 60 * 60 * 1000;
      return duration <= maxDuration;
    },
    {
      message: `La durée du backtest ne peut pas dépasser ${MAX_BACKTEST_DURATION} jours`,
      path: ['endDate'],
    }
  );

type BacktestFormValues = z.infer<typeof backtestSchema>;

/**
 * PROPS DU COMPOSANT
 */
interface BacktestFormProps {
  /** ID du backtest à éditer (null pour un nouveau) */
  backtestId?: string | null;
  /** Mode de visualisation (lecture seule) */
  readOnly?: boolean;
  /** Fonction de callback après sauvegarde */
  onSave?: (data: BacktestResponse) => void;
  /** Fonction de callback après annulation */
  onCancel?: () => void;
  /** Stratégie par défaut à backtester */
  defaultStrategyId?: string;
  /** Symbole par défaut */
  defaultSymbol?: string;
  /** Classe CSS additionnelle */
  className?: string;
}

/**
 * COMPOSANT PRINCIPAL
 */
export function BacktestForm({
  backtestId = null,
  readOnly = false,
  onSave,
  onCancel,
  defaultStrategyId,
  defaultSymbol = 'BTC-USD',
  className = '',
}: BacktestFormProps) {
  // ============================================================
  // ÉTATS & HOOKS
  // ============================================================

  const [isLoading, setIsLoading] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('basic');
  const [backtestProgress, setBacktestProgress] = useState(0);
  const [backtestStatus, setBacktestStatus] = useState<'idle' | 'running' | 'completed' | 'error'>('idle');
  const [results, setResults] = useState<BacktestResult | null>(null);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [isDirty, setIsDirty] = useState(false);

  // Hooks personnalisés
  const {
    getBacktest,
    createBacktest,
    updateBacktest,
    executeBacktest,
    deleteBacktest,
    getBacktestResult,
  } = useBacktest();

  const { strategies, isLoading: strategiesLoading } = useStrategies();
  const { symbols, isLoading: symbolsLoading } = useMarketData();
  const { sendMessage, lastMessage } = useWebSocket('/ws/trading/backtest');

  // Debounce pour les calculs lourds
  const debouncedProgress = useDebounce(backtestProgress, 300);

  // ============================================================
  // FORMULAIRE REACT-HOOK-FORM
  // ============================================================

  const form = useForm<BacktestFormValues>({
    resolver: zodResolver(backtestSchema),
    defaultValues: {
      name: '',
      description: '',
      strategyId: defaultStrategyId || '',
      symbol: defaultSymbol,
      timeframe: '1h',
      startDate: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000), // 30 jours
      endDate: new Date(),
      backtestType: 'STANDARD',
      initialCapital: 10000,
      commission: 0.1,
      slippage: 0.05,
      positionSize: 'PERCENTAGE',
      positionSizeValue: 2,
      maxPositions: 10,
      useStopLoss: true,
      stopLossPercent: 5,
      useTakeProfit: true,
      takeProfitPercent: 15,
      useTrailingStop: false,
      trailingStopPercent: 2,
      useDynamicPositionSizing: false,
      allowShortSelling: false,
      useMargin: false,
      marginRatio: 50,
      metricsToTrack: ['sharpe_ratio', 'max_drawdown', 'win_rate', 'profit_factor'],
      generateReport: true,
      includeTrades: true,
      includeCharts: false,
      numberOfSimulations: 100,
      walkForwardWindow: 50,
    },
    mode: 'onChange',
  });

  const { control, handleSubmit, watch, setValue, getValues, reset, formState } = form;
  const { errors, isValid } = formState;

  // ============================================================
  // EFFETS
  // ============================================================

  // Chargement des données si édition
  useEffect(() => {
    if (backtestId) {
      loadBacktestData(backtestId);
    }
  }, [backtestId]);

  // Monitoring WebSocket pour les mises à jour en temps réel
  useEffect(() => {
    if (lastMessage) {
      try {
        const data = JSON.parse(lastMessage);
        if (data.type === 'BACKTEST_PROGRESS' && data.backtestId === backtestId) {
          setBacktestProgress(data.progress);
          setBacktestStatus(data.status);
          toast.info('Progression du backtest', {
            description: `${data.progress.toFixed(1)}% terminé`,
          });
        }
        if (data.type === 'BACKTEST_COMPLETED' && data.backtestId === backtestId) {
          setBacktestStatus('completed');
          loadBacktestResult(data.resultId);
          toast.success('Backtest terminé', {
            description: 'Le backtest a été exécuté avec succès',
          });
        }
        if (data.type === 'BACKTEST_ERROR' && data.backtestId === backtestId) {
          setBacktestStatus('error');
          toast.error('Erreur de backtest', {
            description: data.error,
          });
        }
      } catch (error) {
        console.error('Erreur de parsing WebSocket:', error);
      }
    }
  }, [lastMessage]);

  // ============================================================
  // FONCTIONS MÉTIER
  // ============================================================

  /**
   * Charge les données d'un backtest existant
   */
  const loadBacktestData = useCallback(
    async (id: string) => {
      setIsLoading(true);
      try {
        const data = await getBacktest(id);
        if (data) {
          // Transformation des données pour le formulaire
          const formData: BacktestFormValues = {
            name: data.name,
            description: data.description || '',
            strategyId: data.strategyId,
            symbol: data.symbol,
            timeframe: data.timeframe as any,
            startDate: new Date(data.startDate),
            endDate: new Date(data.endDate),
            backtestType: data.backtestType as any,
            initialCapital: data.initialCapital,
            commission: data.commission || 0.1,
            slippage: data.slippage || 0.05,
            positionSize: data.positionSize as any,
            positionSizeValue: data.positionSizeValue || 2,
            maxPositions: data.maxPositions || 10,
            useStopLoss: data.useStopLoss !== false,
            stopLossPercent: data.stopLossPercent || 5,
            useTakeProfit: data.useTakeProfit !== false,
            takeProfitPercent: data.takeProfitPercent || 15,
            useTrailingStop: data.useTrailingStop || false,
            trailingStopPercent: data.trailingStopPercent || 2,
            useDynamicPositionSizing: data.useDynamicPositionSizing || false,
            allowShortSelling: data.allowShortSelling || false,
            useMargin: data.useMargin || false,
            marginRatio: data.marginRatio || 50,
            metricsToTrack: data.metricsToTrack || ['sharpe_ratio', 'max_drawdown'],
            generateReport: data.generateReport !== false,
            includeTrades: data.includeTrades !== false,
            includeCharts: data.includeCharts || false,
            numberOfSimulations: data.numberOfSimulations || 100,
            walkForwardWindow: data.walkForwardWindow || 50,
          };
          reset(formData);
          setIsDirty(false);

          // Charger les résultats si disponibles
          if (data.resultId) {
            await loadBacktestResult(data.resultId);
          }
        }
      } catch (error) {
        console.error('Erreur de chargement:', error);
        toast.error('Erreur de chargement', {
          description: 'Impossible de charger les données du backtest',
        });
      } finally {
        setIsLoading(false);
      }
    },
    [getBacktest, reset]
  );

  /**
   * Charge les résultats d'un backtest
   */
  const loadBacktestResult = useCallback(
    async (resultId: string) => {
      try {
        const result = await getBacktestResult(resultId);
        if (result) {
          setResults(result);
          setBacktestStatus('completed');
        }
      } catch (error) {
        console.error('Erreur de chargement des résultats:', error);
        toast.error('Erreur de chargement des résultats');
      }
    },
    [getBacktestResult]
  );

  /**
   * Sauvegarde le backtest
   */
  const onSubmit = useCallback(
    async (data: BacktestFormValues) => {
      setIsSaving(true);
      try {
        const payload: BacktestRequest = {
          ...data,
          startDate: data.startDate.toISOString(),
          endDate: data.endDate.toISOString(),
        };

        let response: BacktestResponse;
        if (backtestId) {
          response = await updateBacktest(backtestId, payload);
          toast.success('Backtest mis à jour', {
            description: 'Les modifications ont été sauvegardées',
          });
        } else {
          response = await createBacktest(payload);
          toast.success('Backtest créé', {
            description: 'Le backtest a été enregistré avec succès',
          });
        }

        setIsDirty(false);
        if (onSave) {
          onSave(response);
        }
      } catch (error) {
        console.error('Erreur de sauvegarde:', error);
        toast.error('Erreur de sauvegarde', {
          description: error instanceof Error ? error.message : 'Une erreur est survenue',
        });
      } finally {
        setIsSaving(false);
      }
    },
    [backtestId, createBacktest, updateBacktest, onSave]
  );

  /**
   * Exécute le backtest
   */
  const handleRunBacktest = useCallback(async () => {
    const data = getValues();

    // Valider le formulaire
    const isValid = await form.trigger();
    if (!isValid) {
      toast.error('Formulaire invalide', {
        description: 'Veuillez corriger les erreurs avant d\'exécuter le backtest',
      });
      return;
    }

    setIsRunning(true);
    setBacktestStatus('running');
    setBacktestProgress(0);
    setResults(null);

    try {
      const result = await executeBacktest(backtestId || undefined, {
        ...data,
        startDate: data.startDate.toISOString(),
        endDate: data.endDate.toISOString(),
      });

      // Envoi via WebSocket pour suivi en temps réel
      sendMessage(
        JSON.stringify({
          type: 'START_BACKTEST',
          backtestId: result.id,
          userId: 'current_user', // À remplacer par l'utilisateur réel
        })
      );

      toast.success('Backtest lancé', {
        description: 'Le backtest est en cours d\'exécution',
      });
    } catch (error) {
      console.error('Erreur d\'exécution:', error);
      setBacktestStatus('error');
      toast.error('Erreur d\'exécution', {
        description: error instanceof Error ? error.message : 'Une erreur est survenue',
      });
    } finally {
      setIsRunning(false);
    }
  }, [form, getValues, executeBacktest, backtestId, sendMessage]);

  /**
   * Annulation
   */
  const handleCancel = useCallback(() => {
    if (isDirty) {
      if (!confirm('Vous avez des modifications non sauvegardées. Voulez-vous continuer ?')) {
        return;
      }
    }
    reset();
    setResults(null);
    setBacktestStatus('idle');
    setBacktestProgress(0);
    if (onCancel) {
      onCancel();
    }
  }, [isDirty, reset, onCancel]);

  /**
   * Exporte les résultats
   */
  const handleExportResults = useCallback(async () => {
    if (!results) return;

    try {
      // Simulation d'export
      toast.info('Export en cours...');
      await new Promise((resolve) => setTimeout(resolve, 1500));

      // Création du fichier JSON
      const blob = new Blob([JSON.stringify(results, null, 2)], {
        type: 'application/json',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `backtest_results_${results.id}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);

      toast.success('Export terminé', {
        description: 'Les résultats ont été exportés avec succès',
      });
    } catch (error) {
      console.error('Erreur d\'export:', error);
      toast.error('Erreur d\'export');
    }
  }, [results]);

  // ============================================================
  // RENDU DES MÉTRIQUES DE RÉSULTATS
  // ============================================================

  const renderMetrics = useCallback((metrics: BacktestMetrics) => {
    const metricItems = [
      { key: 'totalReturn', label: 'Rendement total', value: metrics.totalReturn, format: '%' },
      { key: 'annualizedReturn', label: 'Rendement annualisé', value: metrics.annualizedReturn, format: '%' },
      { key: 'sharpeRatio', label: 'Ratio de Sharpe', value: metrics.sharpeRatio, format: '' },
      { key: 'sortinoRatio', label: 'Ratio de Sortino', value: metrics.sortinoRatio, format: '' },
      { key: 'maxDrawdown', label: 'Drawdown maximum', value: metrics.maxDrawdown, format: '%' },
      { key: 'winRate', label: 'Taux de réussite', value: metrics.winRate, format: '%' },
      { key: 'profitFactor', label: 'Facteur de profit', value: metrics.profitFactor, format: '' },
      { key: 'totalTrades', label: 'Total trades', value: metrics.totalTrades, format: '' },
      { key: 'avgWin', label: 'Gain moyen', value: metrics.avgWin, format: '$' },
      { key: 'avgLoss', label: 'Perte moyenne', value: metrics.avgLoss, format: '$' },
      { key: 'bestTrade', label: 'Meilleur trade', value: metrics.bestTrade, format: '$' },
      { key: 'worstTrade', label: 'Pire trade', value: metrics.worstTrade, format: '$' },
    ];

    return (
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
        {metricItems.map((item) => {
          const value = metrics[item.key as keyof BacktestMetrics];
          if (value === undefined || value === null) return null;

          const isPositive = typeof value === 'number' && value > 0;
          const isNegative = typeof value === 'number' && value < 0;

          let displayValue = typeof value === 'number' ? value.toFixed(2) : value;
          if (item.format === '%') displayValue += '%';
          else if (item.format === '$') displayValue = `$${displayValue}`;

          return (
            <div key={item.key} className="p-3 bg-muted rounded-lg">
              <p className="text-xs text-muted-foreground">{item.label}</p>
              <p
                className={`text-lg font-mono font-bold ${
                  isPositive ? 'text-green-500' : isNegative ? 'text-red-500' : ''
                }`}
              >
                {displayValue}
              </p>
            </div>
          );
        })}
      </div>
    );
  }, []);

  // ============================================================
  // RENDU PRINCIPAL
  // ============================================================

  if (isLoading && backtestId) {
    return (
      <div className="flex flex-col items-center justify-center p-12 space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <p className="text-muted-foreground">Chargement du backtest...</p>
      </div>
    );
  }

  return (
    <Form {...form}>
      <form
        onSubmit={handleSubmit(onSubmit)}
        className={`backtest-form space-y-6 ${className}`}
        noValidate
      >
        {/* ============================================================
            EN-TÊTE
        ============================================================ */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  <FileBarChart className="w-5 h-5" />
                  {backtestId ? 'Modifier le backtest' : 'Nouveau backtest'}
                  {isDirty && (
                    <Badge variant="outline" className="text-yellow-500 border-yellow-500">
                      <Settings className="w-3 h-3 mr-1" />
                      Modifié
                    </Badge>
                  )}
                  {backtestStatus === 'completed' && results && (
                    <Badge variant="success">
                      <CheckCircle className="w-3 h-3 mr-1" />
                      Terminé
                    </Badge>
                  )}
                  {backtestStatus === 'running' && (
                    <Badge variant="warning" className="animate-pulse">
                      <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                      En cours
                    </Badge>
                  )}
                  {backtestStatus === 'error' && (
                    <Badge variant="destructive">
                      <XCircle className="w-3 h-3 mr-1" />
                      Erreur
                    </Badge>
                  )}
                </CardTitle>
                <CardDescription>
                  {backtestId
                    ? 'Modifiez les paramètres de votre backtest'
                    : 'Configurez un nouveau backtest pour valider votre stratégie'}
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                {!readOnly && (
                  <TooltipProvider>
                    <Tooltip>
                      <TooltipTrigger asChild>
                        <Button
                          type="button"
                          variant="default"
                          size="sm"
                          onClick={handleRunBacktest}
                          disabled={isRunning || !isValid || backtestStatus === 'running'}
                          className="gap-2"
                        >
                          {isRunning ? (
                            <>
                              <Loader2 className="w-4 h-4 animate-spin" />
                              Exécution...
                            </>
                          ) : (
                            <>
                              <Play className="w-4 h-4" />
                              Lancer
                            </>
                          )}
                        </Button>
                      </TooltipTrigger>
                      <TooltipContent>
                        Exécuter le backtest avec les paramètres actuels
                      </TooltipContent>
                    </Tooltip>
                  </TooltipProvider>
                )}
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {/* Barre de progression si en cours */}
            {backtestStatus === 'running' && (
              <div className="mb-4">
                <div className="flex justify-between text-sm mb-1">
                  <span>Progression du backtest</span>
                  <span>{backtestProgress.toFixed(1)}%</span>
                </div>
                <Progress value={backtestProgress} className="h-2" />
              </div>
            )}

            {/* Informations de base */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField
                control={control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Nom du backtest</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        placeholder="Ex: Backtest Stratégie Momentum"
                        disabled={readOnly}
                        className="font-mono"
                      />
                    </FormControl>
                    <FormDescription>
                      Nom descriptif pour ce backtest
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />

              <FormField
                control={control}
                name="strategyId"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Stratégie</FormLabel>
                    <Select
                      disabled={readOnly || strategiesLoading}
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                      value={field.value}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Sélectionnez une stratégie" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {strategies?.map((s: Strategy) => (
                          <SelectItem key={s.id} value={s.id}>
                            <div className="flex items-center gap-2">
                              <span>{s.icon}</span>
                              <span>{s.name}</span>
                              <Badge variant="secondary" className="text-xs">
                                {s.type}
                              </Badge>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      Stratégie à backtester
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </div>

            <FormField
              control={control}
              name="description"
              render={({ field }) => (
                <FormItem className="mt-4">
                  <FormLabel>Description</FormLabel>
                  <FormControl>
                    <Input
                      {...field}
                      placeholder="Description du backtest..."
                      disabled={readOnly}
                    />
                  </FormControl>
                  <FormMessage />
                </FormItem>
              )}
            />
          </CardContent>
        </Card>

        {/* ============================================================
            ONGLETS DE CONFIGURATION
        ============================================================ */}
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="grid w-full grid-cols-4">
            <TabsTrigger value="basic" className="gap-2">
              <BarChart3 className="w-4 h-4" />
              Paramètres
            </TabsTrigger>
            <TabsTrigger value="risk" className="gap-2">
              <AlertTriangle className="w-4 h-4" />
              Risque
            </TabsTrigger>
            <TabsTrigger value="advanced" className="gap-2">
              <Sliders className="w-4 h-4" />
              Avancé
            </TabsTrigger>
            {results && (
              <TabsTrigger value="results" className="gap-2">
                <TrendingUp className="w-4 h-4" />
                Résultats
              </TabsTrigger>
            )}
          </TabsList>

          {/* ============================================================
              ONGLET 1 : PARAMÈTRES DE BASE
          ============================================================ */}
          <TabsContent value="basic" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Configuration du backtest</CardTitle>
                <CardDescription>
                  Paramètres de base pour l'exécution du backtest
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Symbole et Timeframe */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField
                    control={control}
                    name="symbol"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Symbole</FormLabel>
                        <Select
                          disabled={readOnly || symbolsLoading}
                          onValueChange={field.onChange}
                          defaultValue={field.value}
                          value={field.value}
                        >
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="Sélectionnez un symbole" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {symbols?.map((s: MarketSymbol) => (
                              <SelectItem key={s.symbol} value={s.symbol}>
                                <div className="flex items-center gap-2">
                                  <span>{s.icon}</span>
                                  <span>{s.symbol}</span>
                                  <span className="text-xs text-muted-foreground">
                                    - {s.name}
                                  </span>
                                </div>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormDescription>
                          Actif à backtester
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={control}
                    name="timeframe"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Timeframe</FormLabel>
                        <Select
                          disabled={readOnly}
                          onValueChange={field.onChange}
                          defaultValue={field.value}
                          value={field.value}
                        >
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="Sélectionnez un timeframe" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {TIMEFRAMES.map((tf) => (
                              <SelectItem key={tf.value} value={tf.value}>
                                {tf.label}
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormDescription>
                          Période des bougies
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                {/* Période */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField
                    control={control}
                    name="startDate"
                    render={({ field }) => (
                      <FormItem className="flex flex-col">
                        <FormLabel>Date de début</FormLabel>
                        <Popover>
                          <PopoverTrigger asChild>
                            <FormControl>
                              <Button
                                variant="outline"
                                className={`w-full justify-start text-left font-normal ${
                                  !field.value && 'text-muted-foreground'
                                }`}
                                disabled={readOnly}
                              >
                                <Calendar className="mr-2 h-4 w-4" />
                                {field.value ? (
                                  field.value.toLocaleDateString('fr-FR', {
                                    day: '2-digit',
                                    month: '2-digit',
                                    year: 'numeric',
                                  })
                                ) : (
                                  <span>Sélectionnez une date</span>
                                )}
                              </Button>
                            </FormControl>
                          </PopoverTrigger>
                          <PopoverContent className="w-auto p-0" align="start">
                            <CalendarComponent
                              mode="single"
                              selected={field.value}
                              onSelect={field.onChange}
                              disabled={(date) =>
                                date > new Date() || date > new Date('1900-01-01')
                              }
                              initialFocus
                            />
                          </PopoverContent>
                        </Popover>
                        <FormDescription>
                          Début de la période de backtest
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={control}
                    name="endDate"
                    render={({ field }) => (
                      <FormItem className="flex flex-col">
                        <FormLabel>Date de fin</FormLabel>
                        <Popover>
                          <PopoverTrigger asChild>
                            <FormControl>
                              <Button
                                variant="outline"
                                className={`w-full justify-start text-left font-normal ${
                                  !field.value && 'text-muted-foreground'
                                }`}
                                disabled={readOnly}
                              >
                                <Calendar className="mr-2 h-4 w-4" />
                                {field.value ? (
                                  field.value.toLocaleDateString('fr-FR', {
                                    day: '2-digit',
                                    month: '2-digit',
                                    year: 'numeric',
                                  })
                                ) : (
                                  <span>Sélectionnez une date</span>
                                )}
                              </Button>
                            </FormControl>
                          </PopoverTrigger>
                          <PopoverContent className="w-auto p-0" align="start">
                            <CalendarComponent
                              mode="single"
                              selected={field.value}
                              onSelect={field.onChange}
                              disabled={(date) =>
                                date > new Date() || date < watch('startDate')
                              }
                              initialFocus
                            />
                          </PopoverContent>
                        </Popover>
                        <FormDescription>
                          Fin de la période de backtest
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                {/* Type de backtest et capital */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField
                    control={control}
                    name="backtestType"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Type de backtest</FormLabel>
                        <Select
                          disabled={readOnly}
                          onValueChange={field.onChange}
                          defaultValue={field.value}
                          value={field.value}
                        >
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="Sélectionnez un type" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            {BACKTEST_TYPES.map((type) => (
                              <SelectItem key={type.value} value={type.value}>
                                <div className="flex items-center gap-2">
                                  <span>{type.icon}</span>
                                  <span>{type.label}</span>
                                  <span className="text-xs text-muted-foreground">
                                    - {type.description}
                                  </span>
                                </div>
                              </SelectItem>
                            ))}
                          </SelectContent>
                        </Select>
                        <FormDescription>
                          Méthode de backtesting
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={control}
                    name="initialCapital"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Capital initial</FormLabel>
                        <FormControl>
                          <div className="relative">
                            <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                              $
                            </span>
                            <Input
                              {...field}
                              type="number"
                              step="100"
                              min="100"
                              className="pl-7"
                              disabled={readOnly}
                              onChange={(e) => {
                                field.onChange(parseFloat(e.target.value) || 0);
                                setIsDirty(true);
                              }}
                            />
                          </div>
                        </FormControl>
                        <FormDescription>
                          Capital de départ pour le backtest
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ============================================================
              ONGLET 2 : GESTION DU RISQUE
          ============================================================ */}
          <TabsContent value="risk" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Paramètres de risque</CardTitle>
                <CardDescription>
                  Configurez les paramètres de gestion du risque
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Position Sizing */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField
                    control={control}
                    name="positionSize"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Méthode de dimensionnement</FormLabel>
                        <Select
                          disabled={readOnly}
                          onValueChange={field.onChange}
                          defaultValue={field.value}
                          value={field.value}
                        >
                          <FormControl>
                            <SelectTrigger>
                              <SelectValue placeholder="Sélectionnez une méthode" />
                            </SelectTrigger>
                          </FormControl>
                          <SelectContent>
                            <SelectItem value="FIXED">Taille fixe</SelectItem>
                            <SelectItem value="PERCENTAGE">Pourcentage du capital</SelectItem>
                            <SelectItem value="KELLY">Critère de Kelly</SelectItem>
                            <SelectItem value="RISK_PARITY">Parité de risque</SelectItem>
                          </SelectContent>
                        </Select>
                        <FormDescription>
                          Méthode de calcul de la taille des positions
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={control}
                    name="positionSizeValue"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>
                          Valeur : {field.value}
                          {watch('positionSize') === 'FIXED' ? ' unités' : '%'}
                        </FormLabel>
                        <FormControl>
                          <Slider
                            min={watch('positionSize') === 'FIXED' ? 1 : 0.1}
                            max={watch('positionSize') === 'FIXED' ? 100 : 100}
                            step={watch('positionSize') === 'FIXED' ? 1 : 0.1}
                            value={[field.value]}
                            onValueChange={(value) => {
                              field.onChange(value[0]);
                              setIsDirty(true);
                            }}
                            disabled={readOnly}
                          />
                        </FormControl>
                        <FormDescription>
                          Taille des positions à ouvrir
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                {/* Stop Loss et Take Profit */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <FormField
                      control={control}
                      name="useStopLoss"
                      render={({ field }) => (
                        <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                          <div className="space-y-0.5">
                            <FormLabel>Stop Loss</FormLabel>
                            <FormDescription>
                              Activer le stop loss
                            </FormDescription>
                          </div>
                          <FormControl>
                            <Switch
                              checked={field.value}
                              onCheckedChange={(checked) => {
                                field.onChange(checked);
                                setIsDirty(true);
                              }}
                              disabled={readOnly}
                            />
                          </FormControl>
                        </FormItem>
                      )}
                    />

                    {watch('useStopLoss') && (
                      <FormField
                        control={control}
                        name="stopLossPercent"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Stop Loss : {field.value}%</FormLabel>
                            <FormControl>
                              <Slider
                                min={0.1}
                                max={20}
                                step={0.1}
                                value={[field.value]}
                                onValueChange={(value) => {
                                  field.onChange(value[0]);
                                  setIsDirty(true);
                                }}
                                disabled={readOnly}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    )}
                  </div>

                  <div className="space-y-2">
                    <FormField
                      control={control}
                      name="useTakeProfit"
                      render={({ field }) => (
                        <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                          <div className="space-y-0.5">
                            <FormLabel>Take Profit</FormLabel>
                            <FormDescription>
                              Activer le take profit
                            </FormDescription>
                          </div>
                          <FormControl>
                            <Switch
                              checked={field.value}
                              onCheckedChange={(checked) => {
                                field.onChange(checked);
                                setIsDirty(true);
                              }}
                              disabled={readOnly}
                            />
                          </FormControl>
                        </FormItem>
                      )}
                    />

                    {watch('useTakeProfit') && (
                      <FormField
                        control={control}
                        name="takeProfitPercent"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Take Profit : {field.value}%</FormLabel>
                            <FormControl>
                              <Slider
                                min={1}
                                max={100}
                                step={1}
                                value={[field.value]}
                                onValueChange={(value) => {
                                  field.onChange(value[0]);
                                  setIsDirty(true);
                                }}
                                disabled={readOnly}
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    )}
                  </div>
                </div>

                {/* Trailing Stop */}
                <div className="space-y-2">
                  <FormField
                    control={control}
                    name="useTrailingStop"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel>Trailing Stop</FormLabel>
                          <FormDescription>
                            Activer le trailing stop
                          </FormDescription>
                        </div>
                        <FormControl>
                          <Switch
                            checked={field.value}
                            onCheckedChange={(checked) => {
                              field.onChange(checked);
                              setIsDirty(true);
                            }}
                            disabled={readOnly}
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />

                  {watch('useTrailingStop') && (
                    <FormField
                      control={control}
                      name="trailingStopPercent"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Trailing Stop : {field.value}%</FormLabel>
                          <FormControl>
                            <Slider
                              min={0.1}
                              max={10}
                              step={0.1}
                              value={[field.value]}
                              onValueChange={(value) => {
                                field.onChange(value[0]);
                                setIsDirty(true);
                              }}
                              disabled={readOnly}
                            />
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  )}
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ============================================================
              ONGLET 3 : PARAMÈTRES AVANCÉS
          ============================================================ */}
          <TabsContent value="advanced" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Paramètres avancés</CardTitle>
                <CardDescription>
                  Options avancées pour les backtests complexes
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Paramètres de simulation */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField
                    control={control}
                    name="useDynamicPositionSizing"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel>Dimensionnement dynamique</FormLabel>
                          <FormDescription>
                            Ajuste la taille selon les performances
                          </FormDescription>
                        </div>
                        <FormControl>
                          <Switch
                            checked={field.value}
                            onCheckedChange={(checked) => {
                              field.onChange(checked);
                              setIsDirty(true);
                            }}
                            disabled={readOnly}
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />

                  <FormField
                    control={control}
                    name="allowShortSelling"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel>Vente à découvert</FormLabel>
                          <FormDescription>
                            Autoriser les positions courtes
                          </FormDescription>
                        </div>
                        <FormControl>
                          <Switch
                            checked={field.value}
                            onCheckedChange={(checked) => {
                              field.onChange(checked);
                              setIsDirty(true);
                            }}
                            disabled={readOnly}
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                </div>

                {/* Marge */}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <FormField
                    control={control}
                    name="useMargin"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel>Utilisation de la marge</FormLabel>
                          <FormDescription>
                            Autoriser l'utilisation de la marge
                          </FormDescription>
                        </div>
                        <FormControl>
                          <Switch
                            checked={field.value}
                            onCheckedChange={(checked) => {
                              field.onChange(checked);
                              setIsDirty(true);
                            }}
                            disabled={readOnly}
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />

                  {watch('useMargin') && (
                    <FormField
                      control={control}
                      name="marginRatio"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Ratio de marge : {field.value}%</FormLabel>
                          <FormControl>
                            <Slider
                              min={1}
                              max={100}
                              step={1}
                              value={[field.value]}
                              onValueChange={(value) => {
                                field.onChange(value[0]);
                                setIsDirty(true);
                              }}
                              disabled={readOnly}
                            />
                          </FormControl>
                          <FormDescription>
                            Pourcentage de marge disponible
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  )}
                </div>

                {/* Paramètres spécifiques au type de backtest */}
                <Accordion type="single" collapsible className="w-full">
                  {watch('backtestType') === 'MONTE_CARLO' && (
                    <AccordionItem value="monte-carlo">
                      <AccordionTrigger>
                        <div className="flex items-center gap-2">
                          <span>Simulations Monte Carlo</span>
                          <Badge variant="secondary">Optionnel</Badge>
                        </div>
                      </AccordionTrigger>
                      <AccordionContent>
                        <FormField
                          control={control}
                          name="numberOfSimulations"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>
                                Nombre de simulations : {field.value}
                              </FormLabel>
                              <FormControl>
                                <Slider
                                  min={10}
                                  max={1000}
                                  step={10}
                                  value={[field.value]}
                                  onValueChange={(value) => {
                                    field.onChange(value[0]);
                                    setIsDirty(true);
                                  }}
                                  disabled={readOnly}
                                />
                              </FormControl>
                              <FormDescription>
                                Nombre de simulations à exécuter
                              </FormDescription>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </AccordionContent>
                    </AccordionItem>
                  )}

                  {watch('backtestType') === 'WALK_FORWARD' && (
                    <AccordionItem value="walk-forward">
                      <AccordionTrigger>
                        <div className="flex items-center gap-2">
                          <span>Walk Forward</span>
                          <Badge variant="secondary">Optionnel</Badge>
                        </div>
                      </AccordionTrigger>
                      <AccordionContent>
                        <FormField
                          control={control}
                          name="walkForwardWindow"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>
                                Fenêtre glissante : {field.value} périodes
                              </FormLabel>
                              <FormControl>
                                <Slider
                                  min={10}
                                  max={100}
                                  step={5}
                                  value={[field.value]}
                                  onValueChange={(value) => {
                                    field.onChange(value[0]);
                                    setIsDirty(true);
                                  }}
                                  disabled={readOnly}
                                />
                              </FormControl>
                              <FormDescription>
                                Taille de la fenêtre pour le walk forward
                              </FormDescription>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      </AccordionContent>
                    </AccordionItem>
                  )}
                </Accordion>

                {/* Métriques à suivre */}
                <FormField
                  control={control}
                  name="metricsToTrack"
                  render={() => (
                    <FormItem>
                      <div className="mb-4">
                        <FormLabel>Métriques à suivre</FormLabel>
                        <FormDescription>
                          Sélectionnez les métriques à calculer
                        </FormDescription>
                      </div>
                      <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                        {PERFORMANCE_METRICS.map((metric) => (
                          <FormField
                            key={metric.value}
                            control={control}
                            name="metricsToTrack"
                            render={({ field }) => {
                              return (
                                <FormItem
                                  key={metric.value}
                                  className="flex flex-row items-start space-x-3 space-y-0"
                                >
                                  <FormControl>
                                    <Checkbox
                                      checked={field.value?.includes(metric.value)}
                                      onCheckedChange={(checked) => {
                                        return checked
                                          ? field.onChange([...field.value, metric.value])
                                          : field.onChange(
                                              field.value?.filter(
                                                (value) => value !== metric.value
                                              )
                                            );
                                      }}
                                      disabled={readOnly}
                                    />
                                  </FormControl>
                                  <FormLabel className="font-normal">
                                    <div className="flex items-center gap-1">
                                      <span>{metric.icon}</span>
                                      <span>{metric.label}</span>
                                    </div>
                                  </FormLabel>
                                </FormItem>
                              );
                            }}
                          />
                        ))}
                      </div>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <Separator />

                {/* Options d'export */}
                <div className="space-y-2">
                  <FormLabel>Options d'export</FormLabel>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    <FormField
                      control={control}
                      name="generateReport"
                      render={({ field }) => (
                        <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                          <div className="space-y-0.5">
                            <FormLabel>Générer un rapport</FormLabel>
                            <FormDescription>
                              Créer un rapport détaillé
                            </FormDescription>
                          </div>
                          <FormControl>
                            <Switch
                              checked={field.value}
                              onCheckedChange={(checked) => {
                                field.onChange(checked);
                                setIsDirty(true);
                              }}
                              disabled={readOnly}
                            />
                          </FormControl>
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={control}
                      name="includeTrades"
                      render={({ field }) => (
                        <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                          <div className="space-y-0.5">
                            <FormLabel>Inclure les trades</FormLabel>
                            <FormDescription>
                              Liste détaillée des trades
                            </FormDescription>
                          </div>
                          <FormControl>
                            <Switch
                              checked={field.value}
                              onCheckedChange={(checked) => {
                                field.onChange(checked);
                                setIsDirty(true);
                              }}
                              disabled={readOnly}
                            />
                          </FormControl>
                        </FormItem>
                      )}
                    />
                  </div>

                  <FormField
                    control={control}
                    name="includeCharts"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel>Inclure les graphiques</FormLabel>
                          <FormDescription>
                            Graphiques de performance
                          </FormDescription>
                        </div>
                        <FormControl>
                          <Switch
                            checked={field.value}
                            onCheckedChange={(checked) => {
                              field.onChange(checked);
                              setIsDirty(true);
                            }}
                            disabled={readOnly}
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />
                </div>
              </CardContent>
            </Card>
          </TabsContent>

          {/* ============================================================
              ONGLET 4 : RÉSULTATS
          ============================================================ */}
          {results && (
            <TabsContent value="results" className="space-y-4">
              <Card>
                <CardHeader>
                  <div className="flex items-center justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        <TrendingUp className="w-5 h-5" />
                        Résultats du backtest
                      </CardTitle>
                      <CardDescription>
                        Analyse détaillée des performances du backtest
                      </CardDescription>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handleExportResults}
                      className="gap-2"
                    >
                      <Download className="w-4 h-4" />
                      Exporter
                    </Button>
                  </div>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Métriques de performance */}
                  {results.metrics && renderMetrics(results.metrics)}

                  <Separator />

                  {/* Statistiques supplémentaires */}
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div className="p-3 bg-muted rounded-lg">
                      <p className="text-xs text-muted-foreground">Total de trades</p>
                      <p className="text-lg font-mono font-bold">
                        {results.trades?.length || 0}
                      </p>
                    </div>
                    <div className="p-3 bg-muted rounded-lg">
                      <p className="text-xs text-muted-foreground">Gains totaux</p>
                      <p className="text-lg font-mono font-bold text-green-500">
                        ${results.totalGain?.toFixed(2) || '0.00'}
                      </p>
                    </div>
                    <div className="p-3 bg-muted rounded-lg">
                      <p className="text-xs text-muted-foreground">Pertes totales</p>
                      <p className="text-lg font-mono font-bold text-red-500">
                        ${results.totalLoss?.toFixed(2) || '0.00'}
                      </p>
                    </div>
                    <div className="p-3 bg-muted rounded-lg">
                      <p className="text-xs text-muted-foreground">Capital final</p>
                      <p className="text-lg font-mono font-bold">
                        ${results.finalCapital?.toFixed(2) || '0.00'}
                      </p>
                    </div>
                  </div>

                  {/* Derniers trades */}
                  {results.trades && results.trades.length > 0 && (
                    <div>
                      <h4 className="text-sm font-medium mb-2">
                        Derniers trades
                      </h4>
                      <ScrollArea className="h-[200px]">
                        <div className="space-y-1">
                          {results.trades.slice(-10).map((trade: Trade, index) => (
                            <div
                              key={index}
                              className="flex items-center justify-between p-2 bg-muted/50 rounded text-sm"
                            >
                              <div className="flex items-center gap-2">
                                <Badge
                                  variant={trade.type === 'BUY' ? 'success' : 'destructive'}
                                  className="text-xs"
                                >
                                  {trade.type}
                                </Badge>
                                <span className="font-mono">{trade.symbol}</span>
                                <span className="text-xs text-muted-foreground">
                                  {new Date(trade.timestamp).toLocaleDateString('fr-FR')}
                                </span>
                              </div>
                              <div className="flex items-center gap-2">
                                <span className="font-mono">
                                  ${trade.price.toFixed(2)}
                                </span>
                                <span
                                  className={`font-mono font-bold ${
                                    trade.pnl > 0 ? 'text-green-500' : 'text-red-500'
                                  }`}
                                >
                                  {trade.pnl > 0 ? '+' : ''}
                                  {trade.pnl.toFixed(2)}$
                                </span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </ScrollArea>
                    </div>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          )}
        </Tabs>

        {/* ============================================================
            PIED DE PAGE
        ============================================================ */}
        <Card>
          <CardFooter className="flex justify-between py-4">
            <div className="flex items-center gap-2">
              {isDirty && (
                <span className="text-sm text-yellow-500">
                  <Settings className="w-3 h-3 inline mr-1" />
                  Modifications non sauvegardées
                </span>
              )}
              {validationErrors.length > 0 && (
                <span className="text-sm text-red-500">
                  <AlertTriangle className="w-3 h-3 inline mr-1" />
                  {validationErrors.length} erreur(s)
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={handleCancel}
                disabled={isSaving || isRunning}
              >
                Annuler
              </Button>
              {!readOnly && (
                <>
                  {backtestId && (
                    <Button
                      type="button"
                      variant="destructive"
                      size="sm"
                      onClick={async () => {
                        if (confirm('Supprimer ce backtest ?')) {
                          try {
                            await deleteBacktest(backtestId);
                            toast.success('Backtest supprimé');
                            if (onCancel) onCancel();
                          } catch (error) {
                            toast.error('Erreur de suppression');
                          }
                        }
                      }}
                      disabled={isSaving || isRunning}
                    >
                      Supprimer
                    </Button>
                  )}
                  <Button
                    type="submit"
                    disabled={!isValid || isSaving || isRunning}
                  >
                    {isSaving ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        Sauvegarde...
                      </>
                    ) : (
                      <>
                        <Save className="w-4 h-4 mr-2" />
                        {backtestId ? 'Mettre à jour' : 'Créer'}
                      </>
                    )}
                  </Button>
                </>
              )}
            </div>
          </CardFooter>
        </Card>
      </form>
    </Form>
  );
}

// ============================================================
// EXPORT PAR DÉFAUT
// ============================================================
export default BacktestForm;

// ============================================================
// TYPES & UTILITAIRES (exportés pour réutilisation)
// ============================================================
export type { BacktestFormProps, BacktestFormValues };
export { backtestSchema };

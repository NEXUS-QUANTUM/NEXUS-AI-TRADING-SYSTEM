// apps/web/src/components/forms/trading/AllocationForm.tsx
/**
 * NEXUS AI TRADING SYSTEM - Allocation Form Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * Ce composant gère l'allocation de capital pour les stratégies de trading.
 * Il permet de définir, modifier et visualiser les allocations de portefeuille.
 */

'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useForm, useFieldArray, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import { Loader2, Plus, Trash2, Edit2, Save, X, AlertCircle } from 'lucide-react';

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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';

// NEXUS Hooks & Services
import { useAllocation } from '@/hooks/trading/useAllocation';
import { usePortfolio } from '@/hooks/portfolio/usePortfolio';
import { useStrategies } from '@/hooks/trading/useStrategies';
import { useWebSocket } from '@/hooks/websocket/useWebSocket';
import { useDebounce } from '@/hooks/utils/useDebounce';

// NEXUS Types
import type {
  AllocationRequest,
  AllocationResponse,
  StrategyAllocation,
  RiskProfile,
  PortfolioSummary,
} from '@/types/trading';

// NEXUS Constants
import { 
  ALLOCATION_TYPES, 
  RISK_PROFILES, 
  MAX_ALLOCATION_PERCENTAGE,
  MIN_ALLOCATION_PERCENTAGE,
  DEFAULT_ALLOCATION_CONFIG 
} from '@/constants/trading';

// Styles
import '@/styles/forms/trading/allocation-form.css';

/**
 * SCHÉMA DE VALIDATION
 * Zod schema pour la validation du formulaire d'allocation
 */
const allocationSchema = z.object({
  // Informations générales
  name: z.string()
    .min(3, 'Le nom doit contenir au moins 3 caractères')
    .max(50, 'Le nom ne peut pas dépasser 50 caractères')
    .regex(/^[a-zA-Z0-9\s\-_]+$/, 'Caractères invalides détectés'),
  
  description: z.string()
    .max(200, 'La description ne peut pas dépasser 200 caractères')
    .optional(),
  
  // Paramètres d'allocation
  allocationType: z.enum(['PERCENTAGE', 'FIXED_AMOUNT', 'DYNAMIC']),
  riskProfile: z.enum(['CONSERVATIVE', 'MODERATE', 'AGGRESSIVE', 'CUSTOM']),
  
  // Allocations par stratégie
  allocations: z.array(
    z.object({
      strategyId: z.string().uuid('ID de stratégie invalide'),
      percentage: z.number()
        .min(MIN_ALLOCATION_PERCENTAGE, `Le minimum est de ${MIN_ALLOCATION_PERCENTAGE}%`)
        .max(MAX_ALLOCATION_PERCENTAGE, `Le maximum est de ${MAX_ALLOCATION_PERCENTAGE}%'),
      priority: z.number().int().min(0).max(10).optional(),
      enabled: z.boolean().default(true),
      minAmount: z.number().min(0).optional(),
      maxAmount: z.number().min(0).optional(),
    })
  ).refine(
    (allocations) => {
      // Validation : La somme des pourcentages doit être égale à 100%
      const total = allocations
        .filter(a => a.enabled)
        .reduce((sum, a) => sum + a.percentage, 0);
      return Math.abs(total - 100) < 0.01;
    },
    {
      message: 'La somme des allocations doit être égale à 100%',
      path: ['allocations'],
    }
  ),
  
  // Paramètres avancés
  rebalanceThreshold: z.number()
    .min(0.1, 'Le seuil minimum est de 0.1%')
    .max(10, 'Le seuil maximum est de 10%')
    .default(2),
  
  autoRebalance: z.boolean().default(false),
  rebalanceFrequency: z.enum(['REAL_TIME', 'HOURLY', 'DAILY', 'WEEKLY']).optional(),
  
  // Paramètres de risque
  maxDrawdown: z.number()
    .min(1, 'Le drawdown minimum est de 1%')
    .max(50, 'Le drawdown maximum est de 50%')
    .default(20),
  
  stopLoss: z.number()
    .min(0.1, 'Le stop-loss minimum est de 0.1%')
    .max(20, 'Le stop-loss maximum est de 20%')
    .default(5),
  
  takeProfit: z.number()
    .min(1, 'Le take-profit minimum est de 1%')
    .max(100, 'Le take-profit maximum est de 100%')
    .default(15),
  
  // Options supplémentaires
  useDynamicAllocation: z.boolean().default(false),
  allowShortSelling: z.boolean().default(false),
  allowMargin: z.boolean().default(false),
  maxLeverage: z.number().min(1).max(10).default(1),
});

type AllocationFormValues = z.infer<typeof allocationSchema>;

/**
 * PROPS DU COMPOSANT
 */
interface AllocationFormProps {
  /** ID de l'allocation à éditer (null pour une nouvelle allocation) */
  allocationId?: string | null;
  /** Mode de visualisation (lecture seule) */
  readOnly?: boolean;
  /** Fonction de callback après sauvegarde */
  onSave?: (data: AllocationResponse) => void;
  /** Fonction de callback après annulation */
  onCancel?: () => void;
  /** Portefeuille par défaut */
  defaultPortfolioId?: string;
  /** Classe CSS additionnelle */
  className?: string;
}

/**
 * COMPOSANT PRINCIPAL
 */
export function AllocationForm({
  allocationId = null,
  readOnly = false,
  onSave,
  onCancel,
  defaultPortfolioId,
  className = '',
}: AllocationFormProps) {
  // ============================================================
  // ÉTATS & HOOKS
  // ============================================================
  
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [activeTab, setActiveTab] = useState('basic');
  const [totalAllocation, setTotalAllocation] = useState(0);
  const [validationErrors, setValidationErrors] = useState<string[]>([]);
  const [isDirty, setIsDirty] = useState(false);

  // Hooks personnalisés
  const { 
    getAllocation, 
    createAllocation, 
    updateAllocation, 
    deleteAllocation 
  } = useAllocation();
  
  const { portfolio } = usePortfolio(defaultPortfolioId);
  const { strategies, isLoading: strategiesLoading } = useStrategies();
  const { sendMessage, lastMessage } = useWebSocket('/ws/trading/allocation');

  // Debounce pour les calculs lourds
  const debouncedTotalAllocation = useDebounce(totalAllocation, 300);

  // ============================================================
  // FORMULAIRE REACT-HOOK-FORM
  // ============================================================
  
  const form = useForm<AllocationFormValues>({
    resolver: zodResolver(allocationSchema),
    defaultValues: {
      name: '',
      description: '',
      allocationType: 'PERCENTAGE',
      riskProfile: 'MODERATE',
      allocations: [
        {
          strategyId: '',
          percentage: 100,
          priority: 1,
          enabled: true,
          minAmount: 0,
          maxAmount: 0,
        },
      ],
      rebalanceThreshold: 2,
      autoRebalance: false,
      rebalanceFrequency: 'DAILY',
      maxDrawdown: 20,
      stopLoss: 5,
      takeProfit: 15,
      useDynamicAllocation: false,
      allowShortSelling: false,
      allowMargin: false,
      maxLeverage: 1,
    },
    mode: 'onChange',
  });

  const { control, handleSubmit, watch, setValue, getValues, formState, reset } = form;
  const { errors, isValid } = formState;

  // Field array pour les allocations
  const { 
    fields, 
    append, 
    remove, 
    update,
    replace 
  } = useFieldArray({
    control,
    name: 'allocations',
  });

  // ============================================================
  // EFFETS
  // ============================================================
  
  // Chargement des données si édition
  useEffect(() => {
    if (allocationId) {
      loadAllocationData(allocationId);
    }
  }, [allocationId]);

  // Calcul du total d'allocation
  useEffect(() => {
    const total = watch('allocations')
      ?.filter(a => a.enabled)
      ?.reduce((sum, a) => sum + (a.percentage || 0), 0) || 0;
    setTotalAllocation(total);
    
    // Validation en temps réel
    const errors: string[] = [];
    if (Math.abs(total - 100) > 0.01) {
      errors.push(`Total : ${total.toFixed(1)}% (doit être 100%)`);
    }
    setValidationErrors(errors);
  }, [watch('allocations')]);

  // Monitoring WebSocket
  useEffect(() => {
    if (lastMessage) {
      try {
        const data = JSON.parse(lastMessage);
        if (data.type === 'ALLOCATION_UPDATE') {
          toast.info('Mise à jour de l\'allocation en temps réel', {
            description: `Allocation mise à jour par ${data.user}`,
          });
          // Recharger les données si nécessaire
          if (allocationId && data.allocationId === allocationId) {
            loadAllocationData(allocationId);
          }
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
   * Charge les données d'une allocation existante
   */
  const loadAllocationData = useCallback(async (id: string) => {
    setIsLoading(true);
    try {
      const data = await getAllocation(id);
      if (data) {
        // Transformation des données pour le formulaire
        const formData: AllocationFormValues = {
          name: data.name,
          description: data.description || '',
          allocationType: data.allocationType as any,
          riskProfile: data.riskProfile as any,
          allocations: data.allocations.map((a: StrategyAllocation) => ({
            strategyId: a.strategyId,
            percentage: a.percentage,
            priority: a.priority || 1,
            enabled: a.enabled !== false,
            minAmount: a.minAmount || 0,
            maxAmount: a.maxAmount || 0,
          })),
          rebalanceThreshold: data.rebalanceThreshold || 2,
          autoRebalance: data.autoRebalance || false,
          rebalanceFrequency: data.rebalanceFrequency || 'DAILY',
          maxDrawdown: data.maxDrawdown || 20,
          stopLoss: data.stopLoss || 5,
          takeProfit: data.takeProfit || 15,
          useDynamicAllocation: data.useDynamicAllocation || false,
          allowShortSelling: data.allowShortSelling || false,
          allowMargin: data.allowMargin || false,
          maxLeverage: data.maxLeverage || 1,
        };
        reset(formData);
        setIsDirty(false);
      }
    } catch (error) {
      console.error('Erreur de chargement:', error);
      toast.error('Erreur de chargement', {
        description: 'Impossible de charger les données d\'allocation',
      });
    } finally {
      setIsLoading(false);
    }
  }, [getAllocation, reset]);

  /**
   * Sauvegarde le formulaire
   */
  const onSubmit = useCallback(async (data: AllocationFormValues) => {
    setIsSaving(true);
    try {
      // Préparation des données
      const payload: AllocationRequest = {
        ...data,
        portfolioId: defaultPortfolioId || portfolio?.id || '',
        allocations: data.allocations.map(a => ({
          ...a,
          strategyId: a.strategyId,
        })),
      };

      let response: AllocationResponse;
      if (allocationId) {
        response = await updateAllocation(allocationId, payload);
        toast.success('Allocation mise à jour', {
          description: 'Les modifications ont été sauvegardées',
        });
      } else {
        response = await createAllocation(payload);
        toast.success('Allocation créée', {
          description: 'Nouvelle allocation ajoutée avec succès',
        });
      }

      // Envoi via WebSocket pour mise à jour en temps réel
      sendMessage(JSON.stringify({
        type: 'ALLOCATION_SAVED',
        allocationId: response.id,
        data: response,
      }));

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
  }, [allocationId, createAllocation, updateAllocation, defaultPortfolioId, portfolio, onSave, sendMessage]);

  /**
   * Ajoute une nouvelle allocation
   */
  const addAllocation = useCallback(() => {
    const availableStrategy = strategies?.find(s => 
      !fields.some(f => f.strategyId === s.id)
    );
    
    append({
      strategyId: availableStrategy?.id || '',
      percentage: 0,
      priority: fields.length + 1,
      enabled: true,
      minAmount: 0,
      maxAmount: 0,
    });
    
    setIsDirty(true);
    toast.info('Nouvelle stratégie ajoutée');
  }, [append, fields, strategies]);

  /**
   * Supprime une allocation
   */
  const removeAllocation = useCallback((index: number) => {
    if (fields.length <= 1) {
      toast.warning('Allocation minimale', {
        description: 'Il doit y avoir au moins une stratégie allouée',
      });
      return;
    }
    remove(index);
    setIsDirty(true);
    toast.info('Stratégie retirée');
  }, [fields.length, remove]);

  /**
   * Rééquilibrage automatique
   */
  const handleRebalance = useCallback(async () => {
    const values = getValues();
    const total = values.allocations.reduce((sum, a) => sum + a.percentage, 0);
    
    if (Math.abs(total - 100) > 0.01) {
      toast.warning('Rééquilibrage impossible', {
        description: 'Le total doit être de 100%',
      });
      return;
    }

    setIsLoading(true);
    try {
      // Simulation de rééquilibrage
      await new Promise(resolve => setTimeout(resolve, 1000));
      
      // Répartition équitable
      const nbActive = values.allocations.filter(a => a.enabled).length;
      const equalShare = 100 / nbActive;
      
      values.allocations.forEach((_, index) => {
        if (values.allocations[index].enabled) {
          update(index, {
            ...values.allocations[index],
            percentage: Math.round(equalShare * 100) / 100,
          });
        }
      });
      
      toast.success('Rééquilibrage effectué', {
        description: 'Les allocations ont été réparties équitablement',
      });
      setIsDirty(true);
    } catch (error) {
      toast.error('Erreur de rééquilibrage');
    } finally {
      setIsLoading(false);
    }
  }, [getValues, update]);

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
    if (onCancel) {
      onCancel();
    }
  }, [isDirty, reset, onCancel]);

  // ============================================================
  // RENDU
  // ============================================================
  
  if (isLoading && allocationId) {
    return (
      <div className="flex flex-col items-center justify-center p-12 space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <p className="text-muted-foreground">Chargement de l'allocation...</p>
      </div>
    );
  }

  return (
    <Form {...form}>
      <form 
        onSubmit={handleSubmit(onSubmit)}
        className={`allocation-form space-y-6 ${className}`}
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
                  {allocationId ? 'Modifier l\'allocation' : 'Nouvelle allocation'}
                  {isDirty && (
                    <Badge variant="outline" className="text-yellow-500 border-yellow-500">
                      <Edit2 className="w-3 h-3 mr-1" />
                      Modifié
                    </Badge>
                  )}
                </CardTitle>
                <CardDescription>
                  {allocationId 
                    ? 'Modifiez les paramètres de votre allocation de capital'
                    : 'Créez une nouvelle allocation pour vos stratégies de trading'}
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Badge variant="secondary" className="text-xs">
                  {fields.filter(f => f.enabled).length} stratégie(s)
                </Badge>
                <Badge 
                  variant={Math.abs(totalAllocation - 100) < 0.01 ? 'success' : 'destructive'}
                  className="text-xs"
                >
                  {totalAllocation.toFixed(1)}%
                </Badge>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {/* ============================================================
                CHAMPS DE BASE
            ============================================================ */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <FormField
                control={control}
                name="name"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Nom de l'allocation</FormLabel>
                    <FormControl>
                      <Input 
                        {...field} 
                        placeholder="Ex: Portfolio Principal" 
                        disabled={readOnly}
                        className="font-mono"
                      />
                    </FormControl>
                    <FormDescription>
                      Nom descriptif pour cette allocation
                    </FormDescription>
                    <FormMessage />
                  </FormItem>
                )}
              />
              
              <FormField
                control={control}
                name="riskProfile"
                render={({ field }) => (
                  <FormItem>
                    <FormLabel>Profil de risque</FormLabel>
                    <Select
                      disabled={readOnly}
                      onValueChange={field.onChange}
                      defaultValue={field.value}
                      value={field.value}
                    >
                      <FormControl>
                        <SelectTrigger>
                          <SelectValue placeholder="Sélectionnez un profil" />
                        </SelectTrigger>
                      </FormControl>
                      <SelectContent>
                        {RISK_PROFILES.map(profile => (
                          <SelectItem key={profile.value} value={profile.value}>
                            <div className="flex items-center gap-2">
                              <span>{profile.icon}</span>
                              <span>{profile.label}</span>
                              <span className="text-xs text-muted-foreground">
                                - {profile.description}
                              </span>
                            </div>
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <FormDescription>
                      Détermine les paramètres de risque par défaut
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
                      placeholder="Description de l'allocation..." 
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
          <TabsList className="grid w-full grid-cols-3">
            <TabsTrigger value="basic" className="relative">
              Allocations
              {fields.some(f => f.enabled && !f.percentage) && (
                <span className="absolute top-0 right-0 w-2 h-2 bg-destructive rounded-full" />
              )}
            </TabsTrigger>
            <TabsTrigger value="risk">
              Gestion du risque
            </TabsTrigger>
            <TabsTrigger value="advanced">
              Paramètres avancés
            </TabsTrigger>
          </TabsList>

          {/* ============================================================
              ONGLET 1 : ALLOCATIONS
          ============================================================ */}
          <TabsContent value="basic" className="space-y-4">
            <Card>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div>
                    <CardTitle className="text-lg">Répartition des stratégies</CardTitle>
                    <CardDescription>
                      Définissez le pourcentage de capital alloué à chaque stratégie
                    </CardDescription>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={handleRebalance}
                      disabled={isLoading || readOnly}
                    >
                      <Loader2 className={`w-4 h-4 mr-2 ${isLoading ? 'animate-spin' : ''}`} />
                      Rééquilibrer
                    </Button>
                    <Button
                      type="button"
                      variant="default"
                      size="sm"
                      onClick={addAllocation}
                      disabled={readOnly}
                    >
                      <Plus className="w-4 h-4 mr-2" />
                      Ajouter
                    </Button>
                  </div>
                </div>
              </CardHeader>
              <CardContent>
                {/* Barre de progression du total */}
                <div className="mb-6">
                  <div className="flex justify-between text-sm mb-1">
                    <span>Total alloué</span>
                    <span className={Math.abs(totalAllocation - 100) < 0.01 ? 'text-green-500' : 'text-red-500'}>
                      {totalAllocation.toFixed(1)}%
                    </span>
                  </div>
                  <Progress 
                    value={Math.min(totalAllocation, 100)} 
                    className="h-2"
                    indicatorClassName={Math.abs(totalAllocation - 100) < 0.01 ? 'bg-green-500' : 'bg-red-500'}
                  />
                  {validationErrors.length > 0 && (
                    <Alert variant="destructive" className="mt-2">
                      <AlertCircle className="w-4 h-4" />
                      <AlertTitle>Erreur de validation</AlertTitle>
                      <AlertDescription>
                        {validationErrors.join(', ')}
                      </AlertDescription>
                    </Alert>
                  )}
                </div>

                {/* Liste des allocations */}
                <div className="space-y-3">
                  {fields.map((field, index) => {
                    const strategy = strategies?.find(s => s.id === field.strategyId);
                    return (
                      <div key={field.id} className="allocation-item">
                        <div className="flex items-start gap-4 p-3 border rounded-lg">
                          {/* Indicateur de priorité */}
                          <div className="flex items-center justify-center w-8 h-8 text-xs font-mono bg-muted rounded-full">
                            #{index + 1}
                          </div>

                          {/* Champs de la stratégie */}
                          <div className="flex-1 grid grid-cols-1 md:grid-cols-3 gap-3">
                            <FormField
                              control={control}
                              name={`allocations.${index}.strategyId`}
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Stratégie</FormLabel>
                                  <Select
                                    disabled={readOnly || strategiesLoading}
                                    onValueChange={(value) => {
                                      field.onChange(value);
                                      setIsDirty(true);
                                    }}
                                    value={field.value}
                                  >
                                    <FormControl>
                                      <SelectTrigger>
                                        <SelectValue placeholder="Sélectionner..." />
                                      </SelectTrigger>
                                    </FormControl>
                                    <SelectContent>
                                      {strategies?.map(s => (
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
                                  <FormMessage />
                                </FormItem>
                              )}
                            />

                            <FormField
                              control={control}
                              name={`allocations.${index}.percentage`}
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel>Pourcentage</FormLabel>
                                  <FormControl>
                                    <div className="flex items-center gap-2">
                                      <Input
                                        {...field}
                                        type="number"
                                        step="0.1"
                                        min={MIN_ALLOCATION_PERCENTAGE}
                                        max={MAX_ALLOCATION_PERCENTAGE}
                                        disabled={readOnly}
                                        onChange={(e) => {
                                          field.onChange(parseFloat(e.target.value) || 0);
                                          setIsDirty(true);
                                        }}
                                      />
                                      <span className="text-sm text-muted-foreground">%</span>
                                    </div>
                                  </FormControl>
                                  <FormDescription>
                                    {field.value ? `${field.value}% du capital` : 'Définir le pourcentage'}
                                  </FormDescription>
                                  <FormMessage />
                                </FormItem>
                              )}
                            />

                            <FormField
                              control={control}
                              name={`allocations.${index}.enabled`}
                              render={({ field }) => (
                                <FormItem className="flex items-center justify-end space-x-2">
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
                                  <FormLabel className="!mt-0 text-sm">
                                    {field.value ? 'Activée' : 'Désactivée'}
                                  </FormLabel>
                                </FormItem>
                              )}
                            />
                          </div>

                          {/* Boutons d'action */}
                          <div className="flex items-start gap-1">
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              onClick={() => removeAllocation(index)}
                              disabled={readOnly || fields.length <= 1}
                              className="text-destructive hover:text-destructive"
                            >
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </div>
                        </div>

                        {/* Champs optionnels */}
                        {field.enabled && (
                          <div className="grid grid-cols-2 gap-2 mt-2 ml-12">
                            <FormField
                              control={control}
                              name={`allocations.${index}.minAmount`}
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel className="text-xs">Montant minimum</FormLabel>
                                  <FormControl>
                                    <Input
                                      {...field}
                                      type="number"
                                      step="1"
                                      placeholder="$0"
                                      disabled={readOnly}
                                      onChange={(e) => {
                                        field.onChange(parseFloat(e.target.value) || 0);
                                        setIsDirty(true);
                                      }}
                                      className="h-8"
                                    />
                                  </FormControl>
                                </FormItem>
                              )}
                            />
                            <FormField
                              control={control}
                              name={`allocations.${index}.maxAmount`}
                              render={({ field }) => (
                                <FormItem>
                                  <FormLabel className="text-xs">Montant maximum</FormLabel>
                                  <FormControl>
                                    <Input
                                      {...field}
                                      type="number"
                                      step="1"
                                      placeholder="$∞"
                                      disabled={readOnly}
                                      onChange={(e) => {
                                        field.onChange(parseFloat(e.target.value) || 0);
                                        setIsDirty(true);
                                      }}
                                      className="h-8"
                                    />
                                  </FormControl>
                                </FormItem>
                              )}
                            />
                          </div>
                        )}
                      </div>
                    );
                  })}
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
                  Configurez les limites de risque pour cette allocation
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                {/* Drawdown */}
                <FormField
                  control={control}
                  name="maxDrawdown"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Drawdown maximum : {field.value}%</FormLabel>
                      <FormControl>
                        <Slider
                          min={1}
                          max={50}
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
                        Le drawdown maximum autorisé avant arrêt des trades
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {/* Stop Loss */}
                <FormField
                  control={control}
                  name="stopLoss"
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
                      <FormDescription>
                        Pourcentage de perte maximum par trade
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {/* Take Profit */}
                <FormField
                  control={control}
                  name="takeProfit"
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
                      <FormDescription>
                        Pourcentage de gain cible par trade
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                {/* Rebalancement */}
                <div className="grid grid-cols-2 gap-4">
                  <FormField
                    control={control}
                    name="autoRebalance"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel>Rééquilibrage automatique</FormLabel>
                          <FormDescription>
                            Activer le rééquilibrage automatique
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
                    name="rebalanceThreshold"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Seuil de rééquilibrage : {field.value}%</FormLabel>
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
                            disabled={readOnly || !form.watch('autoRebalance')}
                          />
                        </FormControl>
                        <FormDescription>
                          Écart en % déclenchant un rééquilibrage
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
              ONGLET 3 : PARAMÈTRES AVANCÉS
          ============================================================ */}
          <TabsContent value="advanced" className="space-y-4">
            <Card>
              <CardHeader>
                <CardTitle>Paramètres avancés</CardTitle>
                <CardDescription>
                  Options avancées pour les traders expérimentés
                </CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Allocation dynamique */}
                  <FormField
                    control={control}
                    name="useDynamicAllocation"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel>Allocation dynamique</FormLabel>
                          <FormDescription>
                            Ajuste selon les performances
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

                  {/* Vente à découvert */}
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

                  {/* Marge */}
                  <FormField
                    control={control}
                    name="allowMargin"
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

                  {/* Effet de levier */}
                  <FormField
                    control={control}
                    name="maxLeverage"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Effet de levier maximum : {field.value}x</FormLabel>
                        <FormControl>
                          <Slider
                            min={1}
                            max={10}
                            step={1}
                            value={[field.value]}
                            onValueChange={(value) => {
                              field.onChange(value[0]);
                              setIsDirty(true);
                            }}
                            disabled={readOnly || !form.watch('allowMargin')}
                          />
                        </FormControl>
                        <FormDescription>
                          Effet de levier maximal autorisé
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </div>

                {/* Fréquence de rééquilibrage */}
                <FormField
                  control={control}
                  name="rebalanceFrequency"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Fréquence de rééquilibrage</FormLabel>
                      <Select
                        disabled={readOnly || !form.watch('autoRebalance')}
                        onValueChange={(value) => {
                          field.onChange(value);
                          setIsDirty(true);
                        }}
                        value={field.value}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Sélectionner une fréquence" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          <SelectItem value="REAL_TIME">Temps réel</SelectItem>
                          <SelectItem value="HOURLY">Horaire</SelectItem>
                          <SelectItem value="DAILY">Quotidien</SelectItem>
                          <SelectItem value="WEEKLY">Hebdomadaire</SelectItem>
                        </SelectContent>
                      </Select>
                      <FormDescription>
                        À quelle fréquence le rééquilibrage est effectué
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>

        {/* ============================================================
            PIED DE PAGE
        ============================================================ */}
        <Card>
          <CardFooter className="flex justify-between py-4">
            <div className="flex items-center gap-2">
              {isDirty && (
                <span className="text-sm text-yellow-500">
                  Modifications non sauvegardées
                </span>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={handleCancel}
                disabled={isSaving}
              >
                <X className="w-4 h-4 mr-2" />
                Annuler
              </Button>
              {!readOnly && (
                <Button 
                  type="submit" 
                  disabled={!isValid || isSaving || Math.abs(totalAllocation - 100) > 0.01}
                >
                  {isSaving ? (
                    <>
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                      Sauvegarde...
                    </>
                  ) : (
                    <>
                      <Save className="w-4 h-4 mr-2" />
                      {allocationId ? 'Mettre à jour' : 'Créer'}
                    </>
                  )}
                </Button>
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
export default AllocationForm;

// ============================================================
// TYPES & UTILITAIRES (exportés pour réutilisation)
// ============================================================
export type { AllocationFormProps, AllocationFormValues };
export { allocationSchema };

'use client';

import React, { useState, useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Switch } from '@/components/ui/switch';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from '@/components/ui/use-toast';
import { Loader2, Save, RefreshCw, Settings } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

// Schema complet selon le Prompt NEXUS V3.0
const dashboardConfigSchema = z.object({
  theme: z.enum(['light', 'dark', 'system']),
  refreshInterval: z.number().min(1000).max(60000),
  defaultTimeframe: z.enum(['1m', '5m', '15m', '30m', '1h', '4h', '1d', '1w']),
  autoRefresh: z.boolean(),
  showPortfolioValue: z.boolean(),
  showPnL: z.boolean(),
  showRiskMetrics: z.boolean(),
  riskTolerance: z.enum(['low', 'medium', 'high', 'aggressive']),
  defaultCurrency: z.string().min(3).max(10),
  notificationsEnabled: z.boolean(),
  alertThreshold: z.number().min(0).max(100),
  chartType: z.enum(['candlestick', 'line', 'area', 'heikinashi', 'bar']),
  language: z.enum(['en', 'fr', 'es', 'zh']),
  soundAlerts: z.boolean(),
  compactMode: z.boolean(),
  showOrderBook: z.boolean(),
  defaultExchange: z.enum(['binance', 'bybit', 'coinbase', 'kraken', 'alpaca', 'oanda']),
  enableAIInsights: z.boolean(),
  enableSentimentAnalysis: z.boolean(),
  maxOpenPositions: z.number().min(1).max(50),
  defaultLeverage: z.number().min(1).max(100),
});

type DashboardConfigFormValues = z.infer<typeof dashboardConfigSchema>;

// API Calls (conforme au prompt : données réelles)
const dashboardApi = {
  getConfig: async (): Promise<DashboardConfigFormValues> => {
    const response = await fetch('/api/dashboard/config', {
      method: 'GET',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
    });
    if (!response.ok) throw new Error('Impossible de charger la configuration');
    return response.json();
  },

  updateConfig: async (data: DashboardConfigFormValues): Promise<void> => {
    const response = await fetch('/api/dashboard/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(data),
    });
    if (!response.ok) throw new Error('Échec de la sauvegarde');
  },
};

export default function DashboardConfigForm() {
  const queryClient = useQueryClient();
  const [isInitialized, setIsInitialized] = useState(false);

  // Récupération des données réelles
  const { data: serverConfig, isLoading: isFetching } = useQuery({
    queryKey: ['nexusDashboardConfig'],
    queryFn: dashboardApi.getConfig,
    staleTime: 1000 * 60 * 5,
  });

  const form = useForm<DashboardConfigFormValues>({
    resolver: zodResolver(dashboardConfigSchema),
    defaultValues: {
      theme: 'dark',
      refreshInterval: 5000,
      defaultTimeframe: '5m',
      autoRefresh: true,
      showPortfolioValue: true,
      showPnL: true,
      showRiskMetrics: true,
      riskTolerance: 'medium',
      defaultCurrency: 'USD',
      notificationsEnabled: true,
      alertThreshold: 5,
      chartType: 'candlestick',
      language: 'fr',
      soundAlerts: true,
      compactMode: false,
      showOrderBook: true,
      defaultExchange: 'binance',
      enableAIInsights: true,
      enableSentimentAnalysis: true,
      maxOpenPositions: 10,
      defaultLeverage: 10,
    },
  });

  const { register, handleSubmit, watch, setValue, reset } = form;
  const watchedValues = watch();

  // Chargement des données du serveur
  useEffect(() => {
    if (serverConfig && !isInitialized) {
      reset(serverConfig);
      setIsInitialized(true);
    }
  }, [serverConfig, reset, isInitialized]);

  const mutation = useMutation({
    mutationFn: dashboardApi.updateConfig,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['nexusDashboardConfig'] });
      toast({
        title: "✅ Configuration sauvegardée",
        description: "Les paramètres du Dashboard NEXUS ont été mis à jour avec succès.",
      });
    },
    onError: (error: any) => {
      toast({
        title: "❌ Erreur",
        description: error.message || "Impossible de sauvegarder la configuration.",
        variant: "destructive",
      });
    },
  });

  const onSubmit = (data: DashboardConfigFormValues) => {
    mutation.mutate(data);
  };

  const resetToDefaults = () => {
    form.reset();
    toast({
      title: "🔄 Réinitialisation",
      description: "Configuration restaurée aux valeurs par défaut NEXUS.",
    });
  };

  if (isFetching) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-10 w-10 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <Card className="w-full border-border shadow-2xl">
      <CardHeader>
        <div className="flex items-center gap-3">
          <Settings className="h-8 w-8 text-primary" />
          <div>
            <CardTitle className="text-2xl">Configuration du Dashboard</CardTitle>
            <CardDescription className="text-base">
              NEXUS TRADING IA — Paramètres complets (V3.0)
            </CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent className="pt-6">
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-8">
          <Tabs defaultValue="general" className="w-full">
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="general">Général</TabsTrigger>
              <TabsTrigger value="display">Affichage</TabsTrigger>
              <TabsTrigger value="trading">Trading</TabsTrigger>
              <TabsTrigger value="alerts">Alertes &amp; IA</TabsTrigger>
            </TabsList>

            {/* GENERAL */}
            <TabsContent value="general" className="space-y-6 pt-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <Label>Thème</Label>
                  <Select value={watchedValues.theme} onValueChange={(v) => setValue('theme', v as any)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="dark">Sombre</SelectItem>
                      <SelectItem value="light">Clair</SelectItem>
                      <SelectItem value="system">Système</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label>Langue</Label>
                  <Select value={watchedValues.language} onValueChange={(v) => setValue('language', v as any)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="fr">Français</SelectItem>
                      <SelectItem value="en">English</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label>Exchange par défaut</Label>
                  <Select value={watchedValues.defaultExchange} onValueChange={(v) => setValue('defaultExchange', v as any)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="binance">Binance</SelectItem>
                      <SelectItem value="bybit">Bybit</SelectItem>
                      <SelectItem value="kraken">Kraken</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label>Intervalle de rafraîchissement (ms)</Label>
                  <Input type="number" {...register('refreshInterval', { valueAsNumber: true })} />
                </div>
              </div>
            </TabsContent>

            {/* DISPLAY */}
            <TabsContent value="display" className="space-y-6 pt-4">
              {[
                { label: "Rafraîchissement automatique", key: "autoRefresh" as const },
                { label: "Valeur du Portfolio", key: "showPortfolioValue" as const },
                { label: "PnL en temps réel", key: "showPnL" as const },
                { label: "Métriques de risque", key: "showRiskMetrics" as const },
                { label: "Mode compact", key: "compactMode" as const },
                { label: "Order Book", key: "showOrderBook" as const },
              ].map(({ label, key }) => (
                <div key={key} className="flex items-center justify-between">
                  <Label>{label}</Label>
                  <Switch checked={watchedValues[key]} onCheckedChange={(checked) => setValue(key, checked)} />
                </div>
              ))}

              <div>
                <Label>Type de graphique</Label>
                <Select value={watchedValues.chartType} onValueChange={(v) => setValue('chartType', v as any)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="candlestick">Candlestick</SelectItem>
                    <SelectItem value="heikinashi">Heikin Ashi</SelectItem>
                    <SelectItem value="line">Ligne</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </TabsContent>

            {/* TRADING */}
            <TabsContent value="trading" className="space-y-6 pt-4">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <Label>Tolérance au risque</Label>
                  <Select value={watchedValues.riskTolerance} onValueChange={(v) => setValue('riskTolerance', v as any)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="low">Faible</SelectItem>
                      <SelectItem value="medium">Moyenne</SelectItem>
                      <SelectItem value="high">Élevée</SelectItem>
                      <SelectItem value="aggressive">Agressive</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div>
                  <Label>Devise</Label>
                  <Input {...register('defaultCurrency')} />
                </div>
                <div>
                  <Label>Positions max ouvertes</Label>
                  <Input type="number" {...register('maxOpenPositions', { valueAsNumber: true })} />
                </div>
                <div>
                  <Label>Levier par défaut</Label>
                  <Input type="number" {...register('defaultLeverage', { valueAsNumber: true })} />
                </div>
              </div>
            </TabsContent>

            {/* ALERTS & IA */}
            <TabsContent value="alerts" className="space-y-6 pt-4">
              <div className="space-y-4">
                <div className="flex justify-between">
                  <Label>Notifications</Label>
                  <Switch checked={watchedValues.notificationsEnabled} onCheckedChange={(c) => setValue('notificationsEnabled', c)} />
                </div>
                <div className="flex justify-between">
                  <Label>Alertes sonores</Label>
                  <Switch checked={watchedValues.soundAlerts} onCheckedChange={(c) => setValue('soundAlerts', c)} />
                </div>
                <div className="flex justify-between">
                  <Label>Insights IA</Label>
                  <Switch checked={watchedValues.enableAIInsights} onCheckedChange={(c) => setValue('enableAIInsights', c)} />
                </div>
                <div className="flex justify-between">
                  <Label>Analyse de sentiment</Label>
                  <Switch checked={watchedValues.enableSentimentAnalysis} onCheckedChange={(c) => setValue('enableSentimentAnalysis', c)} />
                </div>
              </div>
            </TabsContent>
          </Tabs>

          <div className="flex gap-4 pt-8 border-t">
            <Button type="button" variant="outline" onClick={resetToDefaults} className="flex-1">
              <RefreshCw className="mr-2 h-4 w-4" /> Réinitialiser
            </Button>
            <Button type="submit" className="flex-1" disabled={mutation.isPending}>
              {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              <Save className="mr-2 h-4 w-4" /> Sauvegarder
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

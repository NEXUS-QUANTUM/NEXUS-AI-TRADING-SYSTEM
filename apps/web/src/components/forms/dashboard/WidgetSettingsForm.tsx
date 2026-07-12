'use client';

import React from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { Button } from '@/components/ui/button';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from '@/components/ui/use-toast';
import { Loader2, Save, RefreshCw, Grid3X3 } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

const widgetSettingsSchema = z.object({
  showPriceTicker: z.boolean(),
  showOrderBook: z.boolean(),
  showRecentTrades: z.boolean(),
  showPortfolioSummary: z.boolean(),
  showAIInsights: z.boolean(),
  showSentimentGauge: z.boolean(),
  showRiskRadar: z.boolean(),
  showMarketHeatmap: z.boolean(),
  showVolumeProfile: z.boolean(),
  showNewsWidget: z.boolean(),
  widgetRefreshRate: z.number().min(1000).max(30000),
  widgetLayout: z.enum(['grid', 'flex', 'masonry']),
  defaultWidgetSize: z.enum(['small', 'medium', 'large']),
  enableWidgetDrag: z.boolean(),
  showWidgetHeaders: z.boolean(),
  autoHideInactiveWidgets: z.boolean(),
});

type WidgetSettingsFormValues = z.infer<typeof widgetSettingsSchema>;

const widgetApi = {
  getWidgets: async () => {
    const res = await fetch('/api/dashboard/widgets', {
      method: 'GET',
      credentials: 'include',
    });
    if (!res.ok) throw new Error('Failed to load widget settings');
    return res.json();
  },

  saveWidgets: async (data: WidgetSettingsFormValues) => {
    const res = await fetch('/api/dashboard/widgets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to save widget settings');
  },
};

export default function WidgetSettingsForm() {
  const queryClient = useQueryClient();

  const { data: initialData, isLoading } = useQuery({
    queryKey: ['dashboardWidgets'],
    queryFn: widgetApi.getWidgets,
  });

  const form = useForm<WidgetSettingsFormValues>({
    resolver: zodResolver(widgetSettingsSchema),
    defaultValues: {
      showPriceTicker: true,
      showOrderBook: true,
      showRecentTrades: true,
      showPortfolioSummary: true,
      showAIInsights: true,
      showSentimentGauge: true,
      showRiskRadar: true,
      showMarketHeatmap: false,
      showVolumeProfile: true,
      showNewsWidget: true,
      widgetRefreshRate: 5000,
      widgetLayout: 'grid',
      defaultWidgetSize: 'medium',
      enableWidgetDrag: true,
      showWidgetHeaders: true,
      autoHideInactiveWidgets: false,
    },
  });

  const { register, handleSubmit, watch, setValue, reset } = form;
  const values = watch();

  const mutation = useMutation({
    mutationFn: widgetApi.saveWidgets,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboardWidgets'] });
      toast({
        title: "✅ Widgets configurés",
        description: "Les paramètres des widgets ont été sauvegardés avec succès.",
      });
    },
    onError: () => toast({
      title: "❌ Erreur",
      description: "Impossible de sauvegarder les paramètres des widgets.",
      variant: "destructive",
    }),
  });

  React.useEffect(() => {
    if (initialData) reset(initialData);
  }, [initialData, reset]);

  const onSubmit = (data: WidgetSettingsFormValues) => mutation.mutate(data);

  const resetToDefaults = () => {
    form.reset();
    toast({ title: "🔄 Réinitialisé", description: "Paramètres des widgets restaurés par défaut." });
  };

  if (isLoading) {
    return <div className="flex justify-center py-12"><Loader2 className="h-8 w-8 animate-spin" /></div>;
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center gap-3">
          <Grid3X3 className="h-8 w-8 text-primary" />
          <div>
            <CardTitle>Configuration des Widgets</CardTitle>
            <CardDescription>Personnalisez les widgets du dashboard NEXUS AI Trading</CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-8">
          <Tabs defaultValue="visible" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="visible">Visibilité</TabsTrigger>
              <TabsTrigger value="layout">Disposition</TabsTrigger>
              <TabsTrigger value="advanced">Avancé</TabsTrigger>
            </TabsList>

            <TabsContent value="visible" className="pt-6 space-y-5">
              {[
                { label: "Ticker de prix en temps réel", key: "showPriceTicker" },
                { label: "Order Book", key: "showOrderBook" },
                { label: "Derniers trades", key: "showRecentTrades" },
                { label: "Résumé du Portfolio", key: "showPortfolioSummary" },
                { label: "Insights IA", key: "showAIInsights" },
                { label: "Jauge de Sentiment", key: "showSentimentGauge" },
                { label: "Radar de Risque", key: "showRiskRadar" },
                { label: "Heatmap du Marché", key: "showMarketHeatmap" },
                { label: "Profil de Volume", key: "showVolumeProfile" },
                { label: "Flux d'Actualités", key: "showNewsWidget" },
              ].map(({ label, key }) => (
                <div key={key} className="flex items-center justify-between border-b pb-3">
                  <Label className="text-sm font-medium">{label}</Label>
                  <Switch 
                    checked={values[key as keyof WidgetSettingsFormValues] as boolean} 
                    onCheckedChange={(checked) => setValue(key as any, checked)} 
                  />
                </div>
              ))}
            </TabsContent>

            <TabsContent value="layout" className="pt-6 space-y-6">
              <div>
                <Label>Disposition des widgets</Label>
                <Select value={values.widgetLayout} onValueChange={(v: any) => setValue('widgetLayout', v)}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="grid">Grille</SelectItem>
                    <SelectItem value="flex">Flexible</SelectItem>
                    <SelectItem value="masonry">Masonry</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label>Taille par défaut des widgets</Label>
                <Select value={values.defaultWidgetSize} onValueChange={(v: any) => setValue('defaultWidgetSize', v)}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="small">Petit</SelectItem>
                    <SelectItem value="medium">Moyen</SelectItem>
                    <SelectItem value="large">Grand</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label>Fréquence de rafraîchissement des widgets (ms)</Label>
                <input 
                  type="range" 
                  min="1000" 
                  max="30000" 
                  step="1000"
                  {...register('widgetRefreshRate', { valueAsNumber: true })} 
                  className="w-full"
                />
                <div className="text-center text-sm text-muted-foreground">{values.widgetRefreshRate} ms</div>
              </div>
            </TabsContent>

            <TabsContent value="advanced" className="pt-6 space-y-6">
              <div className="flex justify-between">
                <Label>Glisser-déposer des widgets</Label>
                <Switch checked={values.enableWidgetDrag} onCheckedChange={(c) => setValue('enableWidgetDrag', c)} />
              </div>
              <div className="flex justify-between">
                <Label>Afficher les en-têtes des widgets</Label>
                <Switch checked={values.showWidgetHeaders} onCheckedChange={(c) => setValue('showWidgetHeaders', c)} />
              </div>
              <div className="flex justify-between">
                <Label>Masquer automatiquement les widgets inactifs</Label>
                <Switch checked={values.autoHideInactiveWidgets} onCheckedChange={(c) => setValue('autoHideInactiveWidgets', c)} />
              </div>
            </TabsContent>
          </Tabs>

          <div className="flex gap-4 pt-8 border-t">
            <Button type="button" variant="outline" onClick={resetToDefaults}>
              <RefreshCw className="mr-2 h-4 w-4" /> Réinitialiser
            </Button>
            <Button type="submit" disabled={mutation.isPending} className="flex-1">
              {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Sauvegarder Configuration des Widgets
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

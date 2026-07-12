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
import { Loader2, Save, RefreshCw, LayoutDashboard } from 'lucide-react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

const layoutSettingsSchema = z.object({
  sidebarPosition: z.enum(['left', 'right']),
  sidebarCollapsed: z.boolean(),
  showHeader: z.boolean(),
  showFooter: z.boolean(),
  enableAnimations: z.boolean(),
  chartSize: z.enum(['small', 'medium', 'large']),
  widgetLayout: z.enum(['default', 'compact', 'expanded']),
  darkModeEnabled: z.boolean(),
  showMarketOverview: z.boolean(),
  showRecentTrades: z.boolean(),
  showOpenPositions: z.boolean(),
  showNewsFeed: z.boolean(),
  gridColumns: z.number().min(1).max(4),
});

type LayoutSettingsFormValues = z.infer<typeof layoutSettingsSchema>;

const layoutApi = {
  getLayout: async () => {
    const res = await fetch('/api/dashboard/layout', { 
      method: 'GET', 
      credentials: 'include' 
    });
    if (!res.ok) throw new Error('Failed to fetch layout');
    return res.json();
  },

  saveLayout: async (data: LayoutSettingsFormValues) => {
    const res = await fetch('/api/dashboard/layout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Failed to save layout');
  },
};

export default function LayoutSettingsForm() {
  const queryClient = useQueryClient();

  const { data: initialData, isLoading: isFetching } = useQuery({
    queryKey: ['dashboardLayout'],
    queryFn: layoutApi.getLayout,
  });

  const form = useForm<LayoutSettingsFormValues>({
    resolver: zodResolver(layoutSettingsSchema),
    defaultValues: {
      sidebarPosition: 'left',
      sidebarCollapsed: false,
      showHeader: true,
      showFooter: true,
      enableAnimations: true,
      chartSize: 'medium',
      widgetLayout: 'default',
      darkModeEnabled: true,
      showMarketOverview: true,
      showRecentTrades: true,
      showOpenPositions: true,
      showNewsFeed: false,
      gridColumns: 3,
    },
  });

  const { register, handleSubmit, watch, setValue, reset } = form;
  const values = watch();

  const mutation = useMutation({
    mutationFn: layoutApi.saveLayout,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboardLayout'] });
      toast({
        title: "✅ Layout sauvegardé",
        description: "La disposition du dashboard a été mise à jour.",
      });
    },
    onError: () => toast({ 
      title: "❌ Erreur", 
      description: "Impossible de sauvegarder la disposition.", 
      variant: "destructive" 
    }),
  });

  React.useEffect(() => {
    if (initialData) reset(initialData);
  }, [initialData, reset]);

  const onSubmit = (data: LayoutSettingsFormValues) => mutation.mutate(data);

  const resetDefaults = () => {
    form.reset();
    toast({ title: "🔄 Réinitialisé", description: "Disposition par défaut restaurée." });
  };

  if (isFetching) {
    return <div className="flex justify-center py-12"><Loader2 className="animate-spin h-8 w-8" /></div>;
  }

  return (
    <Card className="w-full">
      <CardHeader>
        <div className="flex items-center gap-3">
          <LayoutDashboard className="h-8 w-8 text-primary" />
          <div>
            <CardTitle>Disposition &amp; Layout du Dashboard</CardTitle>
            <CardDescription>Personnalisez l’interface selon vos préférences NEXUS</CardDescription>
          </div>
        </div>
      </CardHeader>

      <CardContent>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-8">
          <Tabs defaultValue="layout" className="w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="layout">Disposition</TabsTrigger>
              <TabsTrigger value="widgets">Widgets</TabsTrigger>
              <TabsTrigger value="advanced">Avancé</TabsTrigger>
            </TabsList>

            <TabsContent value="layout" className="space-y-6 pt-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <Label>Position de la Sidebar</Label>
                  <Select value={values.sidebarPosition} onValueChange={(v: any) => setValue('sidebarPosition', v)}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="left">Gauche</SelectItem>
                      <SelectItem value="right">Droite</SelectItem>
                    </SelectContent>
                  </Select>
                </div>

                <div>
                  <Label>Taille des graphiques</Label>
                  <Select value={values.chartSize} onValueChange={(v: any) => setValue('chartSize', v)}>
                    <SelectTrigger><SelectValue /></SelectTrigger>
                    <SelectContent>
                      <SelectItem value="small">Petit</SelectItem>
                      <SelectItem value="medium">Moyen</SelectItem>
                      <SelectItem value="large">Grand</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
              </div>

              <div className="flex items-center justify-between">
                <Label>Sidebar réduite par défaut</Label>
                <Switch checked={values.sidebarCollapsed} onCheckedChange={(c) => setValue('sidebarCollapsed', c)} />
              </div>
            </TabsContent>

            <TabsContent value="widgets" className="space-y-6 pt-6">
              {[
                { label: "Aperçu du marché", key: "showMarketOverview" },
                { label: "Trades récents", key: "showRecentTrades" },
                { label: "Positions ouvertes", key: "showOpenPositions" },
                { label: "Flux d’actualités", key: "showNewsFeed" },
              ].map(({ label, key }) => (
                <div key={key} className="flex justify-between items-center">
                  <Label>{label}</Label>
                  <Switch 
                    checked={values[key as keyof LayoutSettingsFormValues] as boolean} 
                    onCheckedChange={(c) => setValue(key as any, c)} 
                  />
                </div>
              ))}
            </TabsContent>

            <TabsContent value="advanced" className="space-y-6 pt-6">
              <div className="flex justify-between">
                <Label>Animations</Label>
                <Switch checked={values.enableAnimations} onCheckedChange={(c) => setValue('enableAnimations', c)} />
              </div>
              <div className="flex justify-between">
                <Label>Mode sombre forcé</Label>
                <Switch checked={values.darkModeEnabled} onCheckedChange={(c) => setValue('darkModeEnabled', c)} />
              </div>
            </TabsContent>
          </Tabs>

          <div className="flex gap-4 pt-6 border-t">
            <Button type="button" variant="outline" onClick={resetDefaults}>
              <RefreshCw className="mr-2 h-4 w-4" /> Par défaut
            </Button>
            <Button type="submit" disabled={mutation.isPending} className="flex-1">
              {mutation.isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
              Sauvegarder Layout
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}

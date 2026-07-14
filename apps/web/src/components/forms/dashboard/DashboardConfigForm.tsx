// apps/web/src/components/forms/dashboard/DashboardConfigForm.tsx
'use client';

import React, {
  useState,
  useCallback,
  useRef,
  useEffect,
  forwardRef,
  Ref,
  useMemo,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Squares2X2Icon,
  ListBulletIcon,
  ViewColumnsIcon,
  AdjustmentsHorizontalIcon,
  PlusIcon,
  MinusIcon,
  XMarkIcon,
  CheckIcon,
  ArrowPathIcon,
  ArrowUpIcon,
  ArrowDownIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  DragHandleDots2Icon,
  EyeIcon,
  EyeSlashIcon,
  TrashIcon,
  DuplicateIcon,
  PencilIcon,
  Cog6ToothIcon,
  ChartBarIcon,
  ChartPieIcon,
  ChartLineIcon,
  TableCellsIcon,
  DocumentTextIcon,
  UserGroupIcon,
  BellIcon,
  ClockIcon,
  CalendarIcon,
  WalletIcon,
  BanknotesIcon,
  CurrencyDollarIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  ShieldCheckIcon,
  CpuChipIcon,
  ServerIcon,
  CloudIcon,
  WifiIcon,
  SignalIcon,
  CircleStackIcon,
  SquaresPlusIcon,
  RectangleGroupIcon,
  Square3Stack3DIcon,
  CommandLineIcon,
  CodeBracketIcon,
  PhotoIcon,
  VideoCameraIcon,
  MusicalNoteIcon,
  PaintBrushIcon,
  GlobeAltIcon,
  LinkIcon,
  ShareIcon,
  BookmarkIcon,
  HeartIcon,
  StarIcon,
  FlagIcon,
} from '@heroicons/react/24/outline';
import {
  DragDropContext,
  Droppable,
  Draggable,
  DropResult,
} from '@hello-pangea/dnd';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/common/Card';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Select } from '@/components/common/Select';
import { Switch } from '@/components/common/Switch';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/common/Tabs';
import { Separator } from '@/components/common/Separator';
import { Badge } from '@/components/common/Badge';
import { Tooltip } from '@/components/common/Tooltip';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type WidgetSize = '1x1' | '1x2' | '2x1' | '2x2' | '3x2' | '2x3' | '3x3' | '4x2' | '2x4' | '4x4';
export type WidgetCategory = 'trading' | 'analytics' | 'portfolio' | 'market' | 'system' | 'social' | 'custom';
export type DashboardLayout = 'grid' | 'list' | 'columns' | 'custom';
export type DashboardTheme = 'light' | 'dark' | 'system' | 'auto';

export interface WidgetConfig {
  /** Identifiant unique du widget */
  id: string;
  /** Type/Nom du widget */
  type: string;
  /** Titre affiché */
  title: string;
  /** Description */
  description?: string;
  /** Icône */
  icon?: React.ReactNode;
  /** Catégorie */
  category: WidgetCategory;
  /** Taille */
  size: WidgetSize;
  /** Position dans la grille */
  position: { x: number; y: number };
  /** Est visible */
  visible: boolean;
  /** Est verrouillé */
  locked?: boolean;
  /** Configuration spécifique au widget */
  config?: Record<string, any>;
  /** Données du widget (cachées, stockées) */
  data?: any;
}

export interface DashboardConfigData {
  /** Layout du dashboard */
  layout: DashboardLayout;
  /** Thème du dashboard */
  theme: DashboardTheme;
  /** Nombre de colonnes */
  columns: number;
  /** Widgets configurés */
  widgets: WidgetConfig[];
  /** Widgets disponibles */
  availableWidgets: WidgetConfig[];
  /** Préférences utilisateur */
  preferences: {
    /** Auto-refresh */
    autoRefresh: boolean;
    /** Intervalle de refresh (ms) */
    refreshInterval: number;
    /** Animations */
    animations: boolean;
    /** Compact view */
    compactView: boolean;
    /** Show labels */
    showLabels: boolean;
    /** Show borders */
    showBorders: boolean;
    /** Background opacity */
    backgroundOpacity: number;
    /** Font size */
    fontSize: 'small' | 'medium' | 'large';
    /** Color scheme */
    colorScheme: string;
  };
}

export interface DashboardConfigFormProps {
  // --- Contrôle ---
  /** Données initiales */
  initialData?: Partial<DashboardConfigData>;
  /** Callback de soumission */
  onSubmit?: (data: DashboardConfigData) => void | Promise<void>;
  /** Callback de succès */
  onSuccess?: (data: DashboardConfigData) => void;
  /** Callback d'erreur */
  onError?: (error: string) => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de changement */
  onChange?: (data: DashboardConfigData) => void;

  // --- Apparence ---
  /** Titre du formulaire */
  title?: string;
  /** Sous-titre */
  subtitle?: string;
  /** Classes additionnelles */
  className?: string;
  /** Variante de la carte */
  variant?: 'default' | 'glass' | 'solid' | 'outlined';
  /** Onglet initial */
  defaultTab?: 'layout' | 'widgets' | 'preferences';

  // --- Configuration ---
  /** Widgets disponibles par défaut */
  defaultAvailableWidgets?: WidgetConfig[];
  /** Nombre maximal de widgets */
  maxWidgets?: number;
  /** Nombre minimal de widgets */
  minWidgets?: number;
  /** Colonnes disponibles */
  availableColumns?: number[];
  /** Thèmes disponibles */
  availableThemes?: DashboardTheme[];
  /** Tailles de police disponibles */
  availableFontSizes?: ('small' | 'medium' | 'large')[];

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

const WIDGET_SIZE_MAP: Record<WidgetSize, { width: number; height: number; label: string }> = {
  '1x1': { width: 1, height: 1, label: '1×1' },
  '1x2': { width: 1, height: 2, label: '1×2' },
  '2x1': { width: 2, height: 1, label: '2×1' },
  '2x2': { width: 2, height: 2, label: '2×2' },
  '3x2': { width: 3, height: 2, label: '3×2' },
  '2x3': { width: 2, height: 3, label: '2×3' },
  '3x3': { width: 3, height: 3, label: '3×3' },
  '4x2': { width: 4, height: 2, label: '4×2' },
  '2x4': { width: 2, height: 4, label: '2×4' },
  '4x4': { width: 4, height: 4, label: '4×4' },
};

const WIDGET_CATEGORY_COLORS: Record<WidgetCategory, string> = {
  trading: 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-400',
  analytics: 'bg-purple-100 dark:bg-purple-900/30 text-purple-700 dark:text-purple-400',
  portfolio: 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-400',
  market: 'bg-yellow-100 dark:bg-yellow-900/30 text-yellow-700 dark:text-yellow-400',
  system: 'bg-gray-100 dark:bg-gray-800 text-gray-700 dark:text-gray-400',
  social: 'bg-pink-100 dark:bg-pink-900/30 text-pink-700 dark:text-pink-400',
  custom: 'bg-indigo-100 dark:bg-indigo-900/30 text-indigo-700 dark:text-indigo-400',
};

const DEFAULT_WIDGETS: WidgetConfig[] = [
  {
    id: 'welcome',
    type: 'welcome',
    title: 'Bienvenue',
    description: 'Message de bienvenue personnalisé',
    category: 'custom',
    size: '2x1',
    position: { x: 0, y: 0 },
    visible: true,
  },
  {
    id: 'market-overview',
    type: 'market-overview',
    title: 'Aperçu du marché',
    description: 'Vue d\'ensemble des marchés',
    category: 'market',
    size: '2x2',
    position: { x: 0, y: 1 },
    visible: true,
  },
  {
    id: 'portfolio-performance',
    type: 'portfolio-performance',
    title: 'Performance du portfolio',
    description: 'Suivi des performances',
    category: 'portfolio',
    size: '3x2',
    position: { x: 2, y: 1 },
    visible: true,
  },
  {
    id: 'recent-trades',
    type: 'recent-trades',
    title: 'Trades récents',
    description: 'Historique des trades',
    category: 'trading',
    size: '2x2',
    position: { x: 0, y: 3 },
    visible: true,
  },
  {
    id: 'system-health',
    type: 'system-health',
    title: 'Santé du système',
    description: 'État des services',
    category: 'system',
    size: '2x2',
    position: { x: 2, y: 3 },
    visible: true,
  },
  {
    id: 'ai-insights',
    type: 'ai-insights',
    title: 'Insights IA',
    description: 'Recommandations IA',
    category: 'analytics',
    size: '2x1',
    position: { x: 4, y: 1 },
    visible: true,
  },
];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const DashboardConfigForm = forwardRef<HTMLDivElement, DashboardConfigFormProps>(
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
      title = 'Configuration du tableau de bord',
      subtitle = 'Personnalisez votre espace de travail',
      className,
      variant = 'default',
      defaultTab = 'layout',

      // Configuration
      defaultAvailableWidgets = DEFAULT_WIDGETS,
      maxWidgets = 20,
      minWidgets = 1,
      availableColumns = [2, 3, 4, 6],
      availableThemes = ['light', 'dark', 'system', 'auto'],
      availableFontSizes = ['small', 'medium', 'large'],

      // États
      isLoading = false,
      error = null,
      success = null,
      disabled = false,

      // Accessibilité
      ariaLabel = 'Configuration du tableau de bord',
      id,

      // Avancé
      debug = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const formRef = useRef<HTMLFormElement>(null);
    const dragRef = useRef<HTMLDivElement>(null);

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [activeTab, setActiveTab] = useState<'layout' | 'widgets' | 'preferences'>(defaultTab);
    const [config, setConfig] = useState<DashboardConfigData>({
      layout: 'grid',
      theme: 'system',
      columns: 4,
      widgets: [],
      availableWidgets: defaultAvailableWidgets,
      preferences: {
        autoRefresh: true,
        refreshInterval: 30000,
        animations: true,
        compactView: false,
        showLabels: true,
        showBorders: true,
        backgroundOpacity: 100,
        fontSize: 'medium',
        colorScheme: 'default',
      },
      ...initialData,
    });

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [isDragging, setIsDragging] = useState(false);
    const [selectedWidget, setSelectedWidget] = useState<string | null>(null);
    const [widgetSearch, setWidgetSearch] = useState('');
    const [filterCategory, setFilterCategory] = useState<WidgetCategory | 'all'>('all');

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validate = useCallback((): boolean => {
      const errors: Record<string, string> = {};

      if (config.widgets.length < minWidgets) {
        errors.widgets = `Vous devez avoir au moins ${minWidgets} widget${minWidgets > 1 ? 's' : ''}`;
      }

      if (config.widgets.length > maxWidgets) {
        errors.widgets = `Vous ne pouvez pas avoir plus de ${maxWidgets} widgets`;
      }

      if (config.columns < 1 || config.columns > 12) {
        errors.columns = 'Le nombre de colonnes doit être entre 1 et 12';
      }

      // Vérifier les positions de widgets
      const positions = config.widgets.map((w) => `${w.position.x},${w.position.y}`);
      const uniquePositions = new Set(positions);
      if (positions.length !== uniquePositions.size) {
        errors.widgets = 'Des widgets se chevauchent ou partagent la même position';
      }

      setFormErrors(errors);
      return Object.keys(errors).length === 0;
    }, [config, minWidgets, maxWidgets]);

    // ========================================================================
    // GESTION DES WIDGETS
    // ========================================================================

    const addWidget = useCallback((widget: WidgetConfig) => {
      setConfig((prev) => {
        const newWidget = {
          ...widget,
          id: `${widget.type}-${Date.now()}`,
          position: { x: 0, y: prev.widgets.length },
        };
        return {
          ...prev,
          widgets: [...prev.widgets, newWidget],
        };
      });
    }, []);

    const removeWidget = useCallback((widgetId: string) => {
      setConfig((prev) => ({
        ...prev,
        widgets: prev.widgets.filter((w) => w.id !== widgetId),
      }));
    }, []);

    const toggleWidgetVisibility = useCallback((widgetId: string) => {
      setConfig((prev) => ({
        ...prev,
        widgets: prev.widgets.map((w) =>
          w.id === widgetId ? { ...w, visible: !w.visible } : w
        ),
      }));
    }, []);

    const updateWidgetSize = useCallback((widgetId: string, size: WidgetSize) => {
      setConfig((prev) => ({
        ...prev,
        widgets: prev.widgets.map((w) =>
          w.id === widgetId ? { ...w, size } : w
        ),
      }));
    }, []);

    const updateWidgetTitle = useCallback((widgetId: string, title: string) => {
      setConfig((prev) => ({
        ...prev,
        widgets: prev.widgets.map((w) =>
          w.id === widgetId ? { ...w, title } : w
        ),
      }));
    }, []);

    // ========================================================================
    // DRAG & DROP
    // ========================================================================

    const handleDragStart = useCallback(() => {
      setIsDragging(true);
    }, []);

    const handleDragEnd = useCallback((result: DropResult) => {
      setIsDragging(false);

      if (!result.destination) return;

      const items = Array.from(config.widgets);
      const [reorderedItem] = items.splice(result.source.index, 1);
      items.splice(result.destination.index, 0, reorderedItem);

      // Mettre à jour les positions
      const updatedItems = items.map((item, index) => ({
        ...item,
        position: {
          x: (index * 2) % config.columns,
          y: Math.floor((index * 2) / config.columns),
        },
      }));

      setConfig((prev) => ({
        ...prev,
        widgets: updatedItems,
      }));
    }, [config.widgets, config.columns]);

    // ========================================================================
    // WIDGETS FILTRÉS
    // ========================================================================

    const filteredAvailableWidgets = useMemo(() => {
      let filtered = config.availableWidgets;

      // Filtrer par recherche
      if (widgetSearch) {
        const searchLower = widgetSearch.toLowerCase();
        filtered = filtered.filter(
          (w) =>
            w.title.toLowerCase().includes(searchLower) ||
            w.type.toLowerCase().includes(searchLower) ||
            w.description?.toLowerCase().includes(searchLower)
        );
      }

      // Filtrer par catégorie
      if (filterCategory !== 'all') {
        filtered = filtered.filter((w) => w.category === filterCategory);
      }

      // Exclure les widgets déjà ajoutés
      const existingTypes = new Set(config.widgets.map((w) => w.type));
      filtered = filtered.filter((w) => !existingTypes.has(w.type));

      return filtered;
    }, [config.availableWidgets, config.widgets, widgetSearch, filterCategory]);

    // ========================================================================
    // SOUMISSION
    // ========================================================================

    const handleSubmit = useCallback(async (e: React.FormEvent) => {
      e.preventDefault();

      if (isSubmitting || isLoading || disabled) return;

      if (!validate()) {
        toast({
          title: 'Erreur de validation',
          description: Object.values(formErrors).join('\n'),
          variant: 'destructive',
        });
        return;
      }

      setIsSubmitting(true);

      try {
        if (onSubmit) {
          await onSubmit(config);
        }

        if (onSuccess) onSuccess(config);

        toast({
          title: 'Configuration sauvegardée',
          description: 'Votre tableau de bord a été configuré avec succès',
          variant: 'success',
        });

        if (debug) {
          console.log('Dashboard config:', config);
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
    }, [isSubmitting, isLoading, disabled, config, validate, formErrors, onSubmit, onSuccess, onError, toast, debug]);

    // ========================================================================
    // NOTIFICATION DES CHANGEMENTS
    // ========================================================================

    useEffect(() => {
      if (onChange) {
        onChange(config);
      }
    }, [config, onChange]);

    // ========================================================================
    // RENDU
    // ========================================================================

    // --- Rendu de l'onglet Layout ---
    const renderLayoutTab = () => (
      <div className="space-y-6">
        {/* Layout et Colonnes */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Layout
            </label>
            <div className="flex gap-2">
              {(['grid', 'list', 'columns', 'custom'] as DashboardLayout[]).map((layout) => (
                <button
                  key={layout}
                  type="button"
                  className={cn(
                    'flex-1 rounded-lg border-2 p-3 text-center transition-all capitalize',
                    config.layout === layout
                      ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                  )}
                  onClick={() => setConfig((prev) => ({ ...prev, layout }))}
                  disabled={disabled || isSubmitting || isLoading}
                >
                  {layout === 'grid' && <Squares2X2Icon className="mx-auto h-5 w-5" />}
                  {layout === 'list' && <ListBulletIcon className="mx-auto h-5 w-5" />}
                  {layout === 'columns' && <ViewColumnsIcon className="mx-auto h-5 w-5" />}
                  {layout === 'custom' && <AdjustmentsHorizontalIcon className="mx-auto h-5 w-5" />}
                  <span className="mt-1 block text-xs">{layout}</span>
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Colonnes
            </label>
            <div className="flex flex-wrap gap-2">
              {availableColumns.map((col) => (
                <button
                  key={col}
                  type="button"
                  className={cn(
                    'h-10 w-10 rounded-lg border-2 transition-all',
                    config.columns === col
                      ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-400'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                  )}
                  onClick={() => setConfig((prev) => ({ ...prev, columns: col }))}
                  disabled={disabled || isSubmitting || isLoading}
                >
                  {col}
                </button>
              ))}
            </div>
          </div>
        </div>

        <Separator />

        {/* Thème */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Thème
          </label>
          <div className="flex flex-wrap gap-2">
            {availableThemes.map((theme) => (
              <button
                key={theme}
                type="button"
                className={cn(
                  'flex items-center gap-2 rounded-lg border-2 px-4 py-2 transition-all capitalize',
                  config.theme === theme
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
                onClick={() => setConfig((prev) => ({ ...prev, theme }))}
                disabled={disabled || isSubmitting || isLoading}
              >
                {theme === 'light' && '☀️'}
                {theme === 'dark' && '🌙'}
                {theme === 'system' && '🔄'}
                {theme === 'auto' && '🎨'}
                {theme}
              </button>
            ))}
          </div>
        </div>

        {/* Aperçu du layout */}
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 bg-gray-50 dark:bg-gray-800/50">
          <p className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
            Aperçu du layout
          </p>
          <div
            className="grid gap-2"
            style={{
              gridTemplateColumns: `repeat(${config.columns}, 1fr)`,
            }}
          >
            {config.widgets.filter((w) => w.visible).slice(0, 6).map((widget) => {
              const size = WIDGET_SIZE_MAP[widget.size] || WIDGET_SIZE_MAP['1x1'];
              return (
                <div
                  key={widget.id}
                  className="rounded bg-brand-100 dark:bg-brand-900/30 p-2 text-center text-xs"
                  style={{
                    gridColumn: `span ${Math.min(size.width, config.columns)}`,
                  }}
                >
                  {widget.title}
                </div>
              );
            })}
            {config.widgets.filter((w) => w.visible).length === 0 && (
              <div className="col-span-full text-center text-sm text-gray-500 dark:text-gray-400 py-4">
                Aucun widget visible
              </div>
            )}
          </div>
        </div>
      </div>
    );

    // --- Rendu de l'onglet Widgets ---
    const renderWidgetsTab = () => (
      <div className="space-y-6">
        {/* Filtres et recherche */}
        <div className="flex flex-wrap gap-2">
          <div className="flex-1 min-w-[200px]">
            <Input
              type="text"
              placeholder="Rechercher un widget..."
              value={widgetSearch}
              onChange={(e) => setWidgetSearch(e.target.value)}
              className="h-9"
              prefix={<MagnifyingGlassIcon className="h-4 w-4 text-gray-400" />}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <Select
            options={[
              { value: 'all', label: 'Toutes les catégories' },
              ...Object.entries(WIDGET_CATEGORY_COLORS).map(([key]) => ({
                value: key,
                label: key.charAt(0).toUpperCase() + key.slice(1),
              })),
            ]}
            value={filterCategory}
            onChange={(value) => setFilterCategory(value as WidgetCategory | 'all')}
            size="sm"
            className="w-48"
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {/* Widgets disponibles */}
          <div>
            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
              Widgets disponibles ({filteredAvailableWidgets.length})
            </h4>
            <div className="space-y-2 max-h-96 overflow-y-auto">
              {filteredAvailableWidgets.length === 0 ? (
                <div className="rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 p-8 text-center">
                  <PlusIcon className="mx-auto h-8 w-8 text-gray-400" />
                  <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                    Aucun widget disponible
                  </p>
                </div>
              ) : (
                filteredAvailableWidgets.map((widget) => (
                  <div
                    key={widget.id}
                    className={cn(
                      'flex items-center gap-3 rounded-lg border border-gray-200 dark:border-gray-700 p-3 transition-all',
                      'hover:border-gray-300 dark:hover:border-gray-600'
                    )}
                  >
                    <div className={cn(
                      'flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full',
                      WIDGET_CATEGORY_COLORS[widget.category]
                    )}>
                      {widget.icon || <SquaresPlusIcon className="h-5 w-5" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="font-medium text-gray-900 dark:text-white">
                        {widget.title}
                      </p>
                      {widget.description && (
                        <p className="text-sm text-gray-500 dark:text-gray-400 truncate">
                          {widget.description}
                        </p>
                      )}
                      <Badge variant="outline" size="xs" className="mt-1">
                        {widget.category}
                      </Badge>
                    </div>
                    <Button
                      type="button"
                      variant="primary"
                      size="sm"
                      onClick={() => addWidget(widget)}
                      disabled={disabled || isSubmitting || isLoading || config.widgets.length >= maxWidgets}
                    >
                      <PlusIcon className="h-4 w-4" />
                    </Button>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Widgets actifs */}
          <div>
            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3 flex items-center justify-between">
              <span>Widgets actifs ({config.widgets.length})</span>
              {config.widgets.length > 0 && (
                <span className="text-xs text-gray-400">
                  {config.widgets.filter((w) => w.visible).length} visibles
                </span>
              )}
            </h4>

            {config.widgets.length === 0 ? (
              <div className="rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 p-8 text-center">
                <Square3Stack3DIcon className="mx-auto h-8 w-8 text-gray-400" />
                <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
                  Aucun widget ajouté
                </p>
                <p className="text-xs text-gray-400 dark:text-gray-500">
                  Ajoutez des widgets depuis la liste de gauche
                </p>
              </div>
            ) : (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {config.widgets.map((widget) => (
                  <div
                    key={widget.id}
                    className={cn(
                      'flex items-center gap-3 rounded-lg border p-3 transition-all',
                      widget.visible
                        ? 'border-gray-200 dark:border-gray-700'
                        : 'border-gray-200 dark:border-gray-700 opacity-50'
                    )}
                  >
                    <div className={cn(
                      'flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full',
                      WIDGET_CATEGORY_COLORS[widget.category]
                    )}>
                      {widget.icon || <SquaresPlusIcon className="h-5 w-5" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="font-medium text-gray-900 dark:text-white">
                          {widget.title}
                        </p>
                        <Badge variant="outline" size="xs">
                          {WIDGET_SIZE_MAP[widget.size]?.label || '1×1'}
                        </Badge>
                      </div>
                      <div className="flex items-center gap-2 mt-1">
                        <Select
                          options={Object.entries(WIDGET_SIZE_MAP).map(([value, { label }]) => ({
                            value,
                            label,
                          }))}
                          value={widget.size}
                          onChange={(value) => updateWidgetSize(widget.id, value as WidgetSize)}
                          size="xs"
                          className="w-20"
                          disabled={disabled || isSubmitting || isLoading || widget.locked}
                        />
                        {widget.locked && (
                          <Badge variant="outline" size="xs" className="text-gray-400">
                            🔒 Verrouillé
                          </Badge>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Tooltip content={widget.visible ? 'Masquer' : 'Afficher'}>
                        <Button
                          type="button"
                          variant="ghost"
                          size="xs"
                          onClick={() => toggleWidgetVisibility(widget.id)}
                          disabled={disabled || isSubmitting || isLoading || widget.locked}
                          className="h-7 w-7 p-0"
                        >
                          {widget.visible ? (
                            <EyeIcon className="h-4 w-4" />
                          ) : (
                            <EyeSlashIcon className="h-4 w-4" />
                          )}
                        </Button>
                      </Tooltip>
                      <Tooltip content="Supprimer">
                        <Button
                          type="button"
                          variant="ghost"
                          size="xs"
                          onClick={() => removeWidget(widget.id)}
                          disabled={disabled || isSubmitting || isLoading || widget.locked}
                          className="h-7 w-7 p-0 text-red-500 hover:text-red-600"
                        >
                          <TrashIcon className="h-4 w-4" />
                        </Button>
                      </Tooltip>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="mt-2 text-xs text-gray-500 dark:text-gray-400">
              {config.widgets.length} / {maxWidgets} widgets
            </div>
          </div>
        </div>
      </div>
    );

    // --- Rendu de l'onglet Préférences ---
    const renderPreferencesTab = () => (
      <div className="space-y-6">
        {/* Auto-refresh */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Rafraîchissement automatique
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Mettre à jour les données automatiquement
            </p>
          </div>
          <Switch
            checked={config.preferences.autoRefresh}
            onCheckedChange={(checked) =>
              setConfig((prev) => ({
                ...prev,
                preferences: { ...prev.preferences, autoRefresh: checked },
              }))
            }
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        {config.preferences.autoRefresh && (
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Intervalle de rafraîchissement
            </label>
            <Select
              options={[
                { value: '5000', label: '5 secondes' },
                { value: '10000', label: '10 secondes' },
                { value: '30000', label: '30 secondes' },
                { value: '60000', label: '1 minute' },
                { value: '120000', label: '2 minutes' },
                { value: '300000', label: '5 minutes' },
              ]}
              value={String(config.preferences.refreshInterval)}
              onChange={(value) =>
                setConfig((prev) => ({
                  ...prev,
                  preferences: { ...prev.preferences, refreshInterval: parseInt(value) },
                }))
              }
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        )}

        <Separator />

        {/* Animations */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Animations
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Activer les animations fluides
            </p>
          </div>
          <Switch
            checked={config.preferences.animations}
            onCheckedChange={(checked) =>
              setConfig((prev) => ({
                ...prev,
                preferences: { ...prev.preferences, animations: checked },
              }))
            }
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        {/* Vue compacte */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Vue compacte
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Réduire l'espacement entre les éléments
            </p>
          </div>
          <Switch
            checked={config.preferences.compactView}
            onCheckedChange={(checked) =>
              setConfig((prev) => ({
                ...prev,
                preferences: { ...prev.preferences, compactView: checked },
              }))
            }
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <Separator />

        {/* Afficher les labels */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Afficher les labels
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Afficher les titres des widgets
            </p>
          </div>
          <Switch
            checked={config.preferences.showLabels}
            onCheckedChange={(checked) =>
              setConfig((prev) => ({
                ...prev,
                preferences: { ...prev.preferences, showLabels: checked },
              }))
            }
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        {/* Afficher les bordures */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Afficher les bordures
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Afficher les bordures des widgets
            </p>
          </div>
          <Switch
            checked={config.preferences.showBorders}
            onCheckedChange={(checked) =>
              setConfig((prev) => ({
                ...prev,
                preferences: { ...prev.preferences, showBorders: checked },
              }))
            }
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <Separator />

        {/* Taille de police */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Taille de police
          </label>
          <div className="flex gap-2">
            {availableFontSizes.map((size) => (
              <button
                key={size}
                type="button"
                className={cn(
                  'flex-1 rounded-lg border-2 p-2 text-center transition-all capitalize',
                  config.preferences.fontSize === size
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
                onClick={() =>
                  setConfig((prev) => ({
                    ...prev,
                    preferences: { ...prev.preferences, fontSize: size },
                  }))
                }
                disabled={disabled || isSubmitting || isLoading}
              >
                {size === 'small' && 'Petite'}
                {size === 'medium' && 'Moyenne'}
                {size === 'large' && 'Grande'}
              </button>
            ))}
          </div>
        </div>

        {/* Opacité du fond */}
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Opacité du fond
            </label>
            <span className="text-sm font-mono">
              {config.preferences.backgroundOpacity}%
            </span>
          </div>
          <input
            type="range"
            min="0"
            max="100"
            value={config.preferences.backgroundOpacity}
            onChange={(e) =>
              setConfig((prev) => ({
                ...prev,
                preferences: {
                  ...prev.preferences,
                  backgroundOpacity: parseInt(e.target.value),
                },
              }))
            }
            className="w-full"
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>
      </div>
    );

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

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
              <CardTitle>{title}</CardTitle>
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
          <div className="flex">
            <button
              type="button"
              className={cn(
                'px-4 py-2.5 text-sm font-medium transition-colors border-b-2',
                activeTab === 'layout'
                  ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
              )}
              onClick={() => setActiveTab('layout')}
              disabled={disabled || isSubmitting || isLoading}
            >
              <Squares2X2Icon className="inline h-4 w-4 mr-2" />
              Layout
            </button>
            <button
              type="button"
              className={cn(
                'px-4 py-2.5 text-sm font-medium transition-colors border-b-2',
                activeTab === 'widgets'
                  ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
              )}
              onClick={() => setActiveTab('widgets')}
              disabled={disabled || isSubmitting || isLoading}
            >
              <SquaresPlusIcon className="inline h-4 w-4 mr-2" />
              Widgets
            </button>
            <button
              type="button"
              className={cn(
                'px-4 py-2.5 text-sm font-medium transition-colors border-b-2',
                activeTab === 'preferences'
                  ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                  : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
              )}
              onClick={() => setActiveTab('preferences')}
              disabled={disabled || isSubmitting || isLoading}
            >
              <AdjustmentsHorizontalIcon className="inline h-4 w-4 mr-2" />
              Préférences
            </button>
          </div>
        </div>

        {/* Contenu */}
        <CardContent className="p-6">
          <form ref={formRef} onSubmit={handleSubmit} noValidate>
            {/* Erreur globale */}
            {formErrors._form && (
              <div className="mb-4 flex items-start gap-2 rounded-lg bg-red-50 dark:bg-red-900/20 p-3 text-sm text-red-600 dark:text-red-400">
                <ExclamationTriangleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />
                <span>{formErrors._form}</span>
              </div>
            )}

            {/* Succès */}
            {success && (
              <div className="mb-4 flex items-start gap-2 rounded-lg bg-green-50 dark:bg-green-900/20 p-3 text-sm text-green-600 dark:text-green-400">
                <CheckIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />
                <span>{success}</span>
              </div>
            )}

            {/* Erreur */}
            {error && (
              <div className="mb-4 flex items-start gap-2 rounded-lg bg-red-50 dark:bg-red-900/20 p-3 text-sm text-red-600 dark:text-red-400">
                <ExclamationCircleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />
                <span>{error}</span>
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
                {activeTab === 'layout' && renderLayoutTab()}
                {activeTab === 'widgets' && renderWidgetsTab()}
                {activeTab === 'preferences' && renderPreferencesTab()}
              </motion.div>
            </AnimatePresence>

            {/* Actions */}
            <div className="mt-6 flex items-center justify-end gap-3 pt-6 border-t border-gray-200 dark:border-gray-700">
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  // Réinitialiser aux valeurs par défaut
                  setConfig({
                    layout: 'grid',
                    theme: 'system',
                    columns: 4,
                    widgets: [],
                    availableWidgets: defaultAvailableWidgets,
                    preferences: {
                      autoRefresh: true,
                      refreshInterval: 30000,
                      animations: true,
                      compactView: false,
                      showLabels: true,
                      showBorders: true,
                      backgroundOpacity: 100,
                      fontSize: 'medium',
                      colorScheme: 'default',
                    },
                    ...initialData,
                  });
                  toast({
                    title: 'Réinitialisé',
                    description: 'La configuration a été réinitialisée',
                    duration: 2000,
                  });
                }}
                disabled={disabled || isSubmitting || isLoading}
              >
                Réinitialiser
              </Button>
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
      </Card>
    );
  }
);

DashboardConfigForm.displayName = 'DashboardConfigForm';

export default DashboardConfigForm;

// apps/web/src/components/forms/dashboard/LayoutSettingsForm.tsx
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
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
  RectangleStackIcon,
  ViewFinderCircleIcon,
} from '@heroicons/react/24/outline';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/common/Card';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Select } from '@/components/common/Select';
import { Switch } from '@/components/common/Switch';
import { Slider } from '@/components/common/Slider';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/common/Tabs';
import { Separator } from '@/components/common/Separator';
import { Badge } from '@/components/common/Badge';
import { Tooltip } from '@/components/common/Tooltip';
import { RadioGroup } from '@/components/common/RadioGroup';
import { ColorPicker } from '@/components/common/ColorPicker';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type LayoutType = 'grid' | 'list' | 'columns' | 'masonry' | 'freeform' | 'compact';
export type LayoutTheme = 'light' | 'dark' | 'system' | 'auto' | 'custom';
export type LayoutSpacing = 'compact' | 'normal' | 'relaxed' | 'spacious';
export type LayoutCornerRadius = 'none' | 'small' | 'medium' | 'large' | 'extra-large' | 'full';
export type LayoutShadow = 'none' | 'subtle' | 'medium' | 'strong' | 'extra-strong';
export type LayoutAnimation = 'fade' | 'slide' | 'scale' | 'bounce' | 'none';
export type LayoutBackground = 'solid' | 'gradient' | 'image' | 'video' | 'transparent';

export interface LayoutSettingsData {
  /** Type de layout */
  type: LayoutType;
  /** Thème */
  theme: LayoutTheme;
  /** Nombre de colonnes */
  columns: number;
  /** Espacement */
  spacing: LayoutSpacing;
  /** Rayon de bordure */
  cornerRadius: LayoutCornerRadius;
  /** Ombre */
  shadow: LayoutShadow;
  /** Animation */
  animation: LayoutAnimation;
  /** Fond */
  background: {
    type: LayoutBackground;
    color?: string;
    gradient?: {
      from: string;
      to: string;
      angle: number;
    };
    image?: string;
    video?: string;
    opacity: number;
    blur: number;
  };
  /** Police */
  typography: {
    fontFamily: string;
    fontSize: 'small' | 'medium' | 'large' | 'extra-large';
    fontWeight: 'light' | 'normal' | 'medium' | 'semibold' | 'bold';
    letterSpacing: 'tight' | 'normal' | 'wide' | 'extra-wide';
    lineHeight: 'tight' | 'normal' | 'relaxed' | 'spacious';
  };
  /** Personnalisation */
  custom: {
    /** Couleur primaire personnalisée */
    primaryColor?: string;
    /** Couleur secondaire personnalisée */
    secondaryColor?: string;
    /** Couleur d'accent personnalisée */
    accentColor?: string;
    /** Couleur de fond personnalisée */
    backgroundColor?: string;
    /** Couleur de texte personnalisée */
    textColor?: string;
    /** Police personnalisée */
    customFont?: string;
    /** CSS personnalisé */
    customCss?: string;
  };
  /** Widgets */
  widgets: {
    /** Taille des widgets */
    size: 'small' | 'medium' | 'large';
    /** Espacement entre les widgets */
    gap: number;
    /** Padding des widgets */
    padding: number;
    /** Afficher les titres */
    showTitles: boolean;
    /** Afficher les bordures */
    showBorders: boolean;
    /** Afficher les ombres */
    showShadows: boolean;
    /** Afficher les icônes */
    showIcons: boolean;
    /** Afficher les animations */
    showAnimations: boolean;
  };
  /** Préférences */
  preferences: {
    /** Auto-refresh */
    autoRefresh: boolean;
    /** Intervalle de refresh (ms) */
    refreshInterval: number;
    /** Mode lecture */
    readingMode: boolean;
    /** Mode focus */
    focusMode: boolean;
    /** Barre latérale visible */
    sidebarVisible: boolean;
    /** Barre de navigation visible */
    navbarVisible: boolean;
    /** Pied de page visible */
    footerVisible: boolean;
    /** Fullscreen */
    fullscreen: boolean;
    /** Zoom */
    zoom: number;
  };
}

export interface LayoutSettingsFormProps {
  // --- Contrôle ---
  /** Données initiales */
  initialData?: Partial<LayoutSettingsData>;
  /** Callback de soumission */
  onSubmit?: (data: LayoutSettingsData) => void | Promise<void>;
  /** Callback de succès */
  onSuccess?: (data: LayoutSettingsData) => void;
  /** Callback d'erreur */
  onError?: (error: string) => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de changement */
  onChange?: (data: LayoutSettingsData) => void;

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
  defaultTab?: 'layout' | 'theme' | 'typography' | 'widgets' | 'preferences' | 'advanced';

  // --- Configuration ---
  /** Colonnes disponibles */
  availableColumns?: number[];
  /** Thèmes disponibles */
  availableThemes?: LayoutTheme[];
  /** Espacements disponibles */
  availableSpacings?: LayoutSpacing[];
  /** Rayons disponibles */
  availableCornerRadius?: LayoutCornerRadius[];
  /** Ombres disponibles */
  availableShadows?: LayoutShadow[];
  /** Animations disponibles */
  availableAnimations?: LayoutAnimation[];
  /** Tailles de police disponibles */
  availableFontSizes?: ('small' | 'medium' | 'large' | 'extra-large')[];
  /** Polices disponibles */
  availableFonts?: string[];
  /** Types de fond disponibles */
  availableBackgroundTypes?: LayoutBackground[];

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
  /** Aperçu en direct */
  livePreview?: boolean;
  /** URL de l'aperçu */
  previewUrl?: string;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const SPACING_MAP: Record<LayoutSpacing, { value: number; label: string; description: string }> = {
  compact: { value: 4, label: 'Compact', description: 'Espacement minimal' },
  normal: { value: 8, label: 'Normal', description: 'Espacement standard' },
  relaxed: { value: 12, label: 'Détendu', description: 'Espacement confortable' },
  spacious: { value: 16, label: 'Spacieux', description: 'Espacement généreux' },
};

const CORNER_RADIUS_MAP: Record<LayoutCornerRadius, { value: string; label: string }> = {
  none: { value: '0px', label: 'Aucun' },
  small: { value: '4px', label: 'Petit' },
  medium: { value: '8px', label: 'Moyen' },
  large: { value: '12px', label: 'Grand' },
  'extra-large': { value: '16px', label: 'Très grand' },
  full: { value: '9999px', label: 'Complet' },
};

const SHADOW_MAP: Record<LayoutShadow, { value: string; label: string }> = {
  none: { value: 'none', label: 'Aucune' },
  subtle: { value: '0 1px 3px rgba(0,0,0,0.12)', label: 'Subtile' },
  medium: { value: '0 4px 12px rgba(0,0,0,0.15)', label: 'Moyenne' },
  strong: { value: '0 8px 24px rgba(0,0,0,0.2)', label: 'Forte' },
  'extra-strong': { value: '0 16px 48px rgba(0,0,0,0.25)', label: 'Très forte' },
};

const ANIMATION_LABELS: Record<LayoutAnimation, string> = {
  fade: 'Fondu',
  slide: 'Glissement',
  scale: 'Zoom',
  bounce: 'Rebond',
  none: 'Aucune',
};

const FONT_SIZES = {
  small: '12px',
  medium: '14px',
  large: '16px',
  'extra-large': '20px',
};

const DEFAULT_LAYOUT: LayoutSettingsData = {
  type: 'grid',
  theme: 'system',
  columns: 4,
  spacing: 'normal',
  cornerRadius: 'medium',
  shadow: 'medium',
  animation: 'fade',
  background: {
    type: 'solid',
    color: '#ffffff',
    opacity: 100,
    blur: 0,
    gradient: {
      from: '#ffffff',
      to: '#f5f5f5',
      angle: 135,
    },
  },
  typography: {
    fontFamily: 'Inter, sans-serif',
    fontSize: 'medium',
    fontWeight: 'normal',
    letterSpacing: 'normal',
    lineHeight: 'normal',
  },
  custom: {},
  widgets: {
    size: 'medium',
    gap: 16,
    padding: 16,
    showTitles: true,
    showBorders: true,
    showShadows: true,
    showIcons: true,
    showAnimations: true,
  },
  preferences: {
    autoRefresh: true,
    refreshInterval: 30000,
    readingMode: false,
    focusMode: false,
    sidebarVisible: true,
    navbarVisible: true,
    footerVisible: true,
    fullscreen: false,
    zoom: 100,
  },
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const LayoutSettingsForm = forwardRef<HTMLDivElement, LayoutSettingsFormProps>(
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
      title = 'Paramètres de mise en page',
      subtitle = 'Personnalisez l\'apparence de votre tableau de bord',
      className,
      variant = 'default',
      defaultTab = 'layout',

      // Configuration
      availableColumns = [2, 3, 4, 6, 8, 12],
      availableThemes = ['light', 'dark', 'system', 'auto', 'custom'],
      availableSpacings = ['compact', 'normal', 'relaxed', 'spacious'],
      availableCornerRadius = ['none', 'small', 'medium', 'large', 'extra-large', 'full'],
      availableShadows = ['none', 'subtle', 'medium', 'strong', 'extra-strong'],
      availableAnimations = ['fade', 'slide', 'scale', 'bounce', 'none'],
      availableFontSizes = ['small', 'medium', 'large', 'extra-large'],
      availableFonts = ['Inter, sans-serif', 'Roboto, sans-serif', 'Poppins, sans-serif', 'Merriweather, serif', 'Mono, monospace'],
      availableBackgroundTypes = ['solid', 'gradient', 'image', 'video', 'transparent'],

      // États
      isLoading = false,
      error = null,
      success = null,
      disabled = false,

      // Accessibilité
      ariaLabel = 'Paramètres de mise en page',
      id,

      // Avancé
      debug = false,
      livePreview = false,
      previewUrl = '',
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const formRef = useRef<HTMLFormElement>(null);
    const previewRef = useRef<HTMLDivElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [activeTab, setActiveTab] = useState<'layout' | 'theme' | 'typography' | 'widgets' | 'preferences' | 'advanced'>(defaultTab);
    const [config, setConfig] = useState<LayoutSettingsData>({
      ...DEFAULT_LAYOUT,
      ...initialData,
    });
    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [showAdvanced, setShowAdvanced] = useState(false);
    const [previewImage, setPreviewImage] = useState<string | null>(null);
    const [isLivePreview, setIsLivePreview] = useState(livePreview);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validate = useCallback((): boolean => {
      const errors: Record<string, string> = {};

      if (config.columns < 1 || config.columns > 12) {
        errors.columns = 'Le nombre de colonnes doit être entre 1 et 12';
      }

      if (config.widgets.gap < 0 || config.widgets.gap > 32) {
        errors.gap = 'L\'espacement entre les widgets doit être entre 0 et 32px';
      }

      if (config.widgets.padding < 0 || config.widgets.padding > 32) {
        errors.padding = 'Le padding des widgets doit être entre 0 et 32px';
      }

      if (config.preferences.zoom < 50 || config.preferences.zoom > 200) {
        errors.zoom = 'Le zoom doit être entre 50% et 200%';
      }

      setFormErrors(errors);
      return Object.keys(errors).length === 0;
    }, [config]);

    // ========================================================================
    // GESTIONNAIRES
    // ========================================================================

    const handleFieldChange = useCallback(<K extends keyof LayoutSettingsData>(
      field: K,
      value: LayoutSettingsData[K]
    ) => {
      setConfig((prev) => ({ ...prev, [field]: value }));
    }, []);

    const handleNestedFieldChange = useCallback((
      parent: 'background' | 'typography' | 'custom' | 'widgets' | 'preferences',
      field: string,
      value: any
    ) => {
      setConfig((prev) => ({
        ...prev,
        [parent]: {
          ...prev[parent],
          [field]: value,
        },
      }));
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
          title: 'Paramètres sauvegardés',
          description: 'La mise en page a été configurée avec succès',
          variant: 'success',
        });

        if (debug) {
          console.log('Layout settings saved:', config);
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
    // RENDU DES PRÉVISUALISATIONS
    // ========================================================================

    const renderPreview = useCallback(() => {
      if (!isLivePreview) return null;

      const widgetBg = config.widgets.showShadows ? 'shadow-lg' : '';

      return (
        <div className="mb-6 rounded-lg border border-gray-200 dark:border-gray-700 p-4 bg-gray-50 dark:bg-gray-800/50">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">Aperçu en direct</h4>
            <div className="flex items-center gap-2">
              <Badge variant="outline" size="sm" className="text-green-500">
                <div className="mr-1 h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                Live
              </Badge>
              <button
                type="button"
                onClick={() => setIsLivePreview(false)}
                className="text-sm text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
              >
                <XMarkIcon className="h-4 w-4" />
              </button>
            </div>
          </div>

          <div
            className="rounded-lg overflow-hidden"
            style={{
              backgroundColor: config.background.type === 'solid' ? config.background.color : undefined,
              opacity: config.background.opacity / 100,
              ...(config.background.type === 'gradient' && config.background.gradient && {
                backgroundImage: `linear-gradient(${config.background.gradient.angle}deg, ${config.background.gradient.from}, ${config.background.gradient.to})`,
              }),
            }}
          >
            <div
              className="p-4"
              style={{
                fontFamily: config.typography.fontFamily,
                fontSize: FONT_SIZES[config.typography.fontSize] || '14px',
                fontWeight: config.typography.fontWeight,
                letterSpacing: config.typography.letterSpacing === 'tight' ? '-0.02em' :
                              config.typography.letterSpacing === 'wide' ? '0.02em' :
                              config.typography.letterSpacing === 'extra-wide' ? '0.04em' : 'normal',
                lineHeight: config.typography.lineHeight === 'tight' ? '1.25' :
                            config.typography.lineHeight === 'relaxed' ? '1.75' :
                            config.typography.lineHeight === 'spacious' ? '2' : '1.5',
              }}
            >
              <div
                className="grid gap-4"
                style={{
                  gridTemplateColumns: `repeat(${Math.min(config.columns, 4)}, 1fr)`,
                }}
              >
                {Array.from({ length: Math.min(4, config.columns) }).map((_, i) => (
                  <div
                    key={i}
                    className={cn(
                      'h-16 rounded bg-white dark:bg-gray-800',
                      widgetBg,
                      config.widgets.showBorders && 'border border-gray-200 dark:border-gray-700'
                    )}
                    style={{
                      borderRadius: CORNER_RADIUS_MAP[config.cornerRadius]?.value || '8px',
                      padding: config.widgets.padding,
                      gap: config.widgets.gap,
                    }}
                  >
                    <div className="flex items-center gap-2">
                      {config.widgets.showIcons && (
                        <div className="h-4 w-4 rounded-full bg-brand-500" />
                      )}
                      {config.widgets.showTitles && (
                        <div className="h-2 w-16 rounded bg-gray-300 dark:bg-gray-600" />
                      )}
                    </div>
                    <div className="mt-2 h-2 w-3/4 rounded bg-gray-200 dark:bg-gray-700" />
                    <div className="mt-1 h-2 w-1/2 rounded bg-gray-200 dark:bg-gray-700" />
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      );
    }, [isLivePreview, config]);

    // ========================================================================
    // RENDU DES ONGLETS
    // ========================================================================

    const renderLayoutTab = () => (
      <div className="space-y-6">
        {/* Type de Layout */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Type de mise en page
          </label>
          <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
            {(['grid', 'list', 'columns', 'masonry', 'freeform', 'compact'] as LayoutType[]).map((type) => (
              <button
                key={type}
                type="button"
                className={cn(
                  'rounded-lg border-2 p-3 text-center transition-all capitalize',
                  config.type === type
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
                onClick={() => handleFieldChange('type', type)}
                disabled={disabled || isSubmitting || isLoading}
              >
                {type === 'grid' && <Squares2X2Icon className="mx-auto h-5 w-5" />}
                {type === 'list' && <ListBulletIcon className="mx-auto h-5 w-5" />}
                {type === 'columns' && <ViewColumnsIcon className="mx-auto h-5 w-5" />}
                {type === 'masonry' && <RectangleStackIcon className="mx-auto h-5 w-5" />}
                {type === 'freeform' && <AdjustmentsHorizontalIcon className="mx-auto h-5 w-5" />}
                {type === 'compact' && <SquaresPlusIcon className="mx-auto h-5 w-5" />}
                <span className="mt-1 block text-xs">{type}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Colonnes */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Nombre de colonnes
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
                onClick={() => handleFieldChange('columns', col)}
                disabled={disabled || isSubmitting || isLoading}
              >
                {col}
              </button>
            ))}
          </div>
        </div>

        {/* Espacement */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Espacement
          </label>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            {availableSpacings.map((spacing) => {
              const info = SPACING_MAP[spacing];
              return (
                <button
                  key={spacing}
                  type="button"
                  className={cn(
                    'rounded-lg border-2 p-3 text-center transition-all',
                    config.spacing === spacing
                      ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                  )}
                  onClick={() => handleFieldChange('spacing', spacing)}
                  disabled={disabled || isSubmitting || isLoading}
                >
                  <div className="flex justify-center gap-0.5">
                    {Array.from({ length: Math.ceil(info.value / 2) }).map((_, i) => (
                      <div
                        key={i}
                        className="h-1 w-1 rounded-full bg-gray-400 dark:bg-gray-500"
                      />
                    ))}
                  </div>
                  <span className="mt-1 block text-xs">{info.label}</span>
                </button>
              );
            })}
          </div>
        </div>
      </div>
    );

    const renderThemeTab = () => (
      <div className="space-y-6">
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
                onClick={() => handleFieldChange('theme', theme)}
                disabled={disabled || isSubmitting || isLoading}
              >
                {theme === 'light' && '☀️'}
                {theme === 'dark' && '🌙'}
                {theme === 'system' && '🔄'}
                {theme === 'auto' && '🎨'}
                {theme === 'custom' && '🎯'}
                {theme}
              </button>
            ))}
          </div>
        </div>

        {/* Fond */}
        <Separator />
        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">Fond</h4>

        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Type de fond
          </label>
          <div className="flex flex-wrap gap-2">
            {availableBackgroundTypes.map((type) => (
              <button
                key={type}
                type="button"
                className={cn(
                  'rounded-lg border-2 px-3 py-1.5 text-sm transition-all capitalize',
                  config.background.type === type
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
                onClick={() => handleNestedFieldChange('background', 'type', type)}
                disabled={disabled || isSubmitting || isLoading}
              >
                {type}
              </button>
            ))}
          </div>
        </div>

        {config.background.type === 'solid' && (
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Couleur
            </label>
            <div className="flex items-center gap-4">
              <input
                type="color"
                value={config.background.color || '#ffffff'}
                onChange={(e) => handleNestedFieldChange('background', 'color', e.target.value)}
                className="h-10 w-10 rounded border border-gray-200 dark:border-gray-700 cursor-pointer"
                disabled={disabled || isSubmitting || isLoading}
              />
              <Input
                type="text"
                value={config.background.color || '#ffffff'}
                onChange={(e) => handleNestedFieldChange('background', 'color', e.target.value)}
                className="flex-1 font-mono"
                disabled={disabled || isSubmitting || isLoading}
              />
            </div>
          </div>
        )}

        {config.background.type === 'gradient' && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Couleur de début
                </label>
                <input
                  type="color"
                  value={config.background.gradient?.from || '#ffffff'}
                  onChange={(e) => handleNestedFieldChange('background', 'gradient', {
                    ...config.background.gradient,
                    from: e.target.value,
                  })}
                  className="h-10 w-full rounded border border-gray-200 dark:border-gray-700 cursor-pointer"
                  disabled={disabled || isSubmitting || isLoading}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Couleur de fin
                </label>
                <input
                  type="color"
                  value={config.background.gradient?.to || '#f5f5f5'}
                  onChange={(e) => handleNestedFieldChange('background', 'gradient', {
                    ...config.background.gradient,
                    to: e.target.value,
                  })}
                  className="h-10 w-full rounded border border-gray-200 dark:border-gray-700 cursor-pointer"
                  disabled={disabled || isSubmitting || isLoading}
                />
              </div>
            </div>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Angle ({config.background.gradient?.angle || 135}°)
                </label>
              </div>
              <Slider
                min={0}
                max={360}
                step={1}
                value={[config.background.gradient?.angle || 135]}
                onValueChange={(value) => handleNestedFieldChange('background', 'gradient', {
                  ...config.background.gradient,
                  angle: value[0],
                })}
                disabled={disabled || isSubmitting || isLoading}
              />
            </div>
            <div
              className="h-12 w-full rounded-lg border border-gray-200 dark:border-gray-700"
              style={{
                backgroundImage: `linear-gradient(${config.background.gradient?.angle || 135}deg, ${config.background.gradient?.from || '#ffffff'}, ${config.background.gradient?.to || '#f5f5f5'})`,
              }}
            />
          </div>
        )}

        {(config.background.type === 'image' || config.background.type === 'video') && (
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              {config.background.type === 'image' ? 'URL de l\'image' : 'URL de la vidéo'}
            </label>
            <div className="flex gap-2">
              <Input
                type="text"
                placeholder={config.background.type === 'image' ? 'https://exemple.com/image.jpg' : 'https://exemple.com/video.mp4'}
                value={config.background.type === 'image' ? config.background.image || '' : config.background.video || ''}
                onChange={(e) => handleNestedFieldChange(
                  'background',
                  config.background.type === 'image' ? 'image' : 'video',
                  e.target.value
                )}
                className="flex-1"
                disabled={disabled || isSubmitting || isLoading}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => fileInputRef.current?.click()}
                disabled={disabled || isSubmitting || isLoading}
              >
                <CloudArrowUpIcon className="h-4 w-4" />
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept={config.background.type === 'image' ? 'image/*' : 'video/*'}
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    const reader = new FileReader();
                    reader.onloadend = () => {
                      handleNestedFieldChange(
                        'background',
                        config.background.type === 'image' ? 'image' : 'video',
                        reader.result as string
                      );
                    };
                    reader.readAsDataURL(file);
                  }
                }}
                disabled={disabled || isSubmitting || isLoading}
              />
            </div>
          </div>
        )}

        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Opacité ({config.background.opacity}%)
              </label>
            </div>
            <Slider
              min={0}
              max={100}
              step={1}
              value={[config.background.opacity]}
              onValueChange={(value) => handleNestedFieldChange('background', 'opacity', value[0])}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Flou ({config.background.blur}px)
              </label>
            </div>
            <Slider
              min={0}
              max={20}
              step={1}
              value={[config.background.blur]}
              onValueChange={(value) => handleNestedFieldChange('background', 'blur', value[0])}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        {/* Rayon */}
        <Separator />
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Rayon de bordure
          </label>
          <div className="flex flex-wrap gap-2">
            {availableCornerRadius.map((radius) => (
              <button
                key={radius}
                type="button"
                className={cn(
                  'rounded-lg border-2 px-3 py-1.5 text-sm transition-all capitalize',
                  config.cornerRadius === radius
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
                onClick={() => handleFieldChange('cornerRadius', radius)}
                disabled={disabled || isSubmitting || isLoading}
              >
                {CORNER_RADIUS_MAP[radius].label}
              </button>
            ))}
          </div>
        </div>

        {/* Ombre */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Ombre
          </label>
          <div className="flex flex-wrap gap-2">
            {availableShadows.map((shadow) => (
              <button
                key={shadow}
                type="button"
                className={cn(
                  'rounded-lg border-2 px-3 py-1.5 text-sm transition-all capitalize',
                  config.shadow === shadow
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
                onClick={() => handleFieldChange('shadow', shadow)}
                disabled={disabled || isSubmitting || isLoading}
              >
                {SHADOW_MAP[shadow].label}
              </button>
            ))}
          </div>
        </div>

        {/* Animation */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Animation
          </label>
          <div className="flex flex-wrap gap-2">
            {availableAnimations.map((animation) => (
              <button
                key={animation}
                type="button"
                className={cn(
                  'rounded-lg border-2 px-3 py-1.5 text-sm transition-all capitalize',
                  config.animation === animation
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
                onClick={() => handleFieldChange('animation', animation)}
                disabled={disabled || isSubmitting || isLoading}
              >
                {ANIMATION_LABELS[animation]}
              </button>
            ))}
          </div>
        </div>
      </div>
    );

    const renderTypographyTab = () => (
      <div className="space-y-6">
        {/* Police */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Police
          </label>
          <Select
            options={availableFonts.map((font) => ({
              value: font,
              label: font.split(',')[0],
            }))}
            value={config.typography.fontFamily}
            onChange={(value) => handleNestedFieldChange('typography', 'fontFamily', value)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        {/* Taille de police */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Taille de police
          </label>
          <div className="flex flex-wrap gap-2">
            {availableFontSizes.map((size) => (
              <button
                key={size}
                type="button"
                className={cn(
                  'rounded-lg border-2 px-3 py-1.5 text-sm transition-all capitalize',
                  config.typography.fontSize === size
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
                onClick={() => handleNestedFieldChange('typography', 'fontSize', size)}
                disabled={disabled || isSubmitting || isLoading}
              >
                {size}
              </button>
            ))}
          </div>
        </div>

        {/* Poids */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Poids de la police
          </label>
          <div className="flex flex-wrap gap-2">
            {(['light', 'normal', 'medium', 'semibold', 'bold'] as const).map((weight) => (
              <button
                key={weight}
                type="button"
                className={cn(
                  'rounded-lg border-2 px-3 py-1.5 text-sm transition-all capitalize',
                  config.typography.fontWeight === weight
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
                onClick={() => handleNestedFieldChange('typography', 'fontWeight', weight)}
                disabled={disabled || isSubmitting || isLoading}
                style={{ fontWeight: weight === 'light' ? 300 : weight === 'medium' ? 500 : weight === 'semibold' ? 600 : weight === 'bold' ? 700 : 400 }}
              >
                {weight}
              </button>
            ))}
          </div>
        </div>

        {/* Interlettrage */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Interlettrage
          </label>
          <div className="flex flex-wrap gap-2">
            {(['tight', 'normal', 'wide', 'extra-wide'] as const).map((spacing) => (
              <button
                key={spacing}
                type="button"
                className={cn(
                  'rounded-lg border-2 px-3 py-1.5 text-sm transition-all capitalize',
                  config.typography.letterSpacing === spacing
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
                onClick={() => handleNestedFieldChange('typography', 'letterSpacing', spacing)}
                disabled={disabled || isSubmitting || isLoading}
                style={{
                  letterSpacing: spacing === 'tight' ? '-0.02em' :
                                  spacing === 'wide' ? '0.02em' :
                                  spacing === 'extra-wide' ? '0.04em' : 'normal',
                }}
              >
                {spacing}
              </button>
            ))}
          </div>
        </div>

        {/* Hauteur de ligne */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Hauteur de ligne
          </label>
          <div className="flex flex-wrap gap-2">
            {(['tight', 'normal', 'relaxed', 'spacious'] as const).map((height) => (
              <button
                key={height}
                type="button"
                className={cn(
                  'rounded-lg border-2 px-3 py-1.5 text-sm transition-all capitalize',
                  config.typography.lineHeight === height
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
                onClick={() => handleNestedFieldChange('typography', 'lineHeight', height)}
                disabled={disabled || isSubmitting || isLoading}
                style={{
                  lineHeight: height === 'tight' ? '1.25' :
                              height === 'relaxed' ? '1.75' :
                              height === 'spacious' ? '2' : '1.5',
                }}
              >
                {height}
              </button>
            ))}
          </div>
        </div>

        {/* Aperçu */}
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <p className="text-sm text-gray-500 dark:text-gray-400 mb-2">Aperçu de la police</p>
          <div
            style={{
              fontFamily: config.typography.fontFamily,
              fontSize: FONT_SIZES[config.typography.fontSize] || '14px',
              fontWeight: config.typography.fontWeight === 'light' ? 300 :
                          config.typography.fontWeight === 'medium' ? 500 :
                          config.typography.fontWeight === 'semibold' ? 600 :
                          config.typography.fontWeight === 'bold' ? 700 : 400,
              letterSpacing: config.typography.letterSpacing === 'tight' ? '-0.02em' :
                              config.typography.letterSpacing === 'wide' ? '0.02em' :
                              config.typography.letterSpacing === 'extra-wide' ? '0.04em' : 'normal',
              lineHeight: config.typography.lineHeight === 'tight' ? '1.25' :
                          config.typography.lineHeight === 'relaxed' ? '1.75' :
                          config.typography.lineHeight === 'spacious' ? '2' : '1.5',
            }}
          >
            <p className="text-lg font-medium">Lorem ipsum dolor sit amet</p>
            <p className="text-sm">Consectetur adipiscing elit. Sed do eiusmod tempor incididunt ut labore et dolore magna aliqua.</p>
          </div>
        </div>
      </div>
    );

    const renderWidgetsTab = () => (
      <div className="space-y-6">
        {/* Taille des widgets */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Taille des widgets
          </label>
          <div className="flex gap-2">
            {(['small', 'medium', 'large'] as const).map((size) => (
              <button
                key={size}
                type="button"
                className={cn(
                  'flex-1 rounded-lg border-2 p-3 text-center transition-all capitalize',
                  config.widgets.size === size
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
                onClick={() => handleNestedFieldChange('widgets', 'size', size)}
                disabled={disabled || isSubmitting || isLoading}
              >
                {size === 'small' && '🟩'}
                {size === 'medium' && '🟨'}
                {size === 'large' && '🟥'}
                <span className="mt-1 block text-xs">{size}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Espacement et padding */}
        <div className="grid grid-cols-2 gap-4">
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Espacement ({config.widgets.gap}px)
              </label>
            </div>
            <Slider
              min={0}
              max={32}
              step={2}
              value={[config.widgets.gap]}
              onValueChange={(value) => handleNestedFieldChange('widgets', 'gap', value[0])}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Padding ({config.widgets.padding}px)
              </label>
            </div>
            <Slider
              min={0}
              max={32}
              step={2}
              value={[config.widgets.padding]}
              onValueChange={(value) => handleNestedFieldChange('widgets', 'padding', value[0])}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <Separator />

        {/* Options d'affichage */}
        <div className="space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Afficher les titres</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Afficher les titres des widgets</p>
            </div>
            <Switch
              checked={config.widgets.showTitles}
              onCheckedChange={(checked) => handleNestedFieldChange('widgets', 'showTitles', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Afficher les bordures</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Afficher les bordures des widgets</p>
            </div>
            <Switch
              checked={config.widgets.showBorders}
              onCheckedChange={(checked) => handleNestedFieldChange('widgets', 'showBorders', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Afficher les ombres</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Afficher les ombres des widgets</p>
            </div>
            <Switch
              checked={config.widgets.showShadows}
              onCheckedChange={(checked) => handleNestedFieldChange('widgets', 'showShadows', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Afficher les icônes</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Afficher les icônes des widgets</p>
            </div>
            <Switch
              checked={config.widgets.showIcons}
              onCheckedChange={(checked) => handleNestedFieldChange('widgets', 'showIcons', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>

          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-gray-700 dark:text-gray-300">Afficher les animations</p>
              <p className="text-xs text-gray-500 dark:text-gray-400">Animer les widgets à l'affichage</p>
            </div>
            <Switch
              checked={config.widgets.showAnimations}
              onCheckedChange={(checked) => handleNestedFieldChange('widgets', 'showAnimations', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>
      </div>
    );

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
            onCheckedChange={(checked) => handleNestedFieldChange('preferences', 'autoRefresh', checked)}
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
              onChange={(value) => handleNestedFieldChange('preferences', 'refreshInterval', parseInt(value))}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        )}

        <Separator />

        {/* Modes */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Mode lecture
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Optimiser l'affichage pour la lecture
            </p>
          </div>
          <Switch
            checked={config.preferences.readingMode}
            onCheckedChange={(checked) => handleNestedFieldChange('preferences', 'readingMode', checked)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Mode focus
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Masquer les éléments non essentiels
            </p>
          </div>
          <Switch
            checked={config.preferences.focusMode}
            onCheckedChange={(checked) => handleNestedFieldChange('preferences', 'focusMode', checked)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <Separator />

        {/* Éléments visibles */}
        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Barre latérale visible
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Afficher la barre latérale du tableau de bord
            </p>
          </div>
          <Switch
            checked={config.preferences.sidebarVisible}
            onCheckedChange={(checked) => handleNestedFieldChange('preferences', 'sidebarVisible', checked)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Barre de navigation visible
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Afficher la barre de navigation principale
            </p>
          </div>
          <Switch
            checked={config.preferences.navbarVisible}
            onCheckedChange={(checked) => handleNestedFieldChange('preferences', 'navbarVisible', checked)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Pied de page visible
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Afficher le pied de page du tableau de bord
            </p>
          </div>
          <Switch
            checked={config.preferences.footerVisible}
            onCheckedChange={(checked) => handleNestedFieldChange('preferences', 'footerVisible', checked)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Zoom ({config.preferences.zoom}%)
            </label>
          </div>
          <Slider
            min={50}
            max={200}
            step={5}
            value={[config.preferences.zoom]}
            onValueChange={(value) => handleNestedFieldChange('preferences', 'zoom', value[0])}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>
      </div>
    );

    const renderAdvancedTab = () => (
      <div className="space-y-6">
        {/* CSS personnalisé */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            CSS personnalisé
          </label>
          <textarea
            className="w-full rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-3 font-mono text-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20 dark:focus:ring-brand-500/20"
            rows={6}
            placeholder=".custom-class { ... }"
            value={config.custom.customCss || ''}
            onChange={(e) => handleNestedFieldChange('custom', 'customCss', e.target.value)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <Separator />

        {/* Couleurs personnalisées */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Couleur primaire
            </label>
            <div className="flex items-center gap-4">
              <input
                type="color"
                value={config.custom.primaryColor || '#6366f1'}
                onChange={(e) => handleNestedFieldChange('custom', 'primaryColor', e.target.value)}
                className="h-10 w-10 rounded border border-gray-200 dark:border-gray-700 cursor-pointer"
                disabled={disabled || isSubmitting || isLoading}
              />
              <Input
                type="text"
                value={config.custom.primaryColor || '#6366f1'}
                onChange={(e) => handleNestedFieldChange('custom', 'primaryColor', e.target.value)}
                className="flex-1 font-mono"
                disabled={disabled || isSubmitting || isLoading}
              />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Couleur secondaire
            </label>
            <div className="flex items-center gap-4">
              <input
                type="color"
                value={config.custom.secondaryColor || '#8b5cf6'}
                onChange={(e) => handleNestedFieldChange('custom', 'secondaryColor', e.target.value)}
                className="h-10 w-10 rounded border border-gray-200 dark:border-gray-700 cursor-pointer"
                disabled={disabled || isSubmitting || isLoading}
              />
              <Input
                type="text"
                value={config.custom.secondaryColor || '#8b5cf6'}
                onChange={(e) => handleNestedFieldChange('custom', 'secondaryColor', e.target.value)}
                className="flex-1 font-mono"
                disabled={disabled || isSubmitting || isLoading}
              />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Couleur d'accent
            </label>
            <div className="flex items-center gap-4">
              <input
                type="color"
                value={config.custom.accentColor || '#f43f5e'}
                onChange={(e) => handleNestedFieldChange('custom', 'accentColor', e.target.value)}
                className="h-10 w-10 rounded border border-gray-200 dark:border-gray-700 cursor-pointer"
                disabled={disabled || isSubmitting || isLoading}
              />
              <Input
                type="text"
                value={config.custom.accentColor || '#f43f5e'}
                onChange={(e) => handleNestedFieldChange('custom', 'accentColor', e.target.value)}
                className="flex-1 font-mono"
                disabled={disabled || isSubmitting || isLoading}
              />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Couleur de fond
            </label>
            <div className="flex items-center gap-4">
              <input
                type="color"
                value={config.custom.backgroundColor || '#ffffff'}
                onChange={(e) => handleNestedFieldChange('custom', 'backgroundColor', e.target.value)}
                className="h-10 w-10 rounded border border-gray-200 dark:border-gray-700 cursor-pointer"
                disabled={disabled || isSubmitting || isLoading}
              />
              <Input
                type="text"
                value={config.custom.backgroundColor || '#ffffff'}
                onChange={(e) => handleNestedFieldChange('custom', 'backgroundColor', e.target.value)}
                className="flex-1 font-mono"
                disabled={disabled || isSubmitting || isLoading}
              />
            </div>
          </div>
        </div>

        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Police personnalisée
          </label>
          <Input
            type="text"
            placeholder="'Custom Font', sans-serif"
            value={config.custom.customFont || ''}
            onChange={(e) => handleNestedFieldChange('custom', 'customFont', e.target.value)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <div className="rounded-lg bg-yellow-50 dark:bg-yellow-900/20 p-4 border border-yellow-200 dark:border-yellow-800">
          <div className="flex items-start gap-3">
            <ExclamationTriangleIcon className="h-5 w-5 text-yellow-600 dark:text-yellow-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200">
                Note sur les personnalisations avancées
              </p>
              <p className="text-xs text-yellow-700 dark:text-yellow-300 mt-1">
                Les modifications apportées ici peuvent affecter l'affichage de votre tableau de bord. 
                Assurez-vous de tester vos changements avant de les sauvegarder.
              </p>
            </div>
          </div>
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
            <div className="flex items-center gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => setIsLivePreview(!isLivePreview)}
                disabled={disabled || isSubmitting || isLoading}
              >
                {isLivePreview ? (
                  <>
                    <EyeSlashIcon className="h-4 w-4 mr-1" />
                    Masquer l'aperçu
                  </>
                ) : (
                  <>
                    <EyeIcon className="h-4 w-4 mr-1" />
                    Aperçu
                  </>
                )}
              </Button>
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
          </div>
        </CardHeader>

        {/* Tabs */}
        <div className="border-b border-gray-200 dark:border-gray-700">
          <div className="flex overflow-x-auto">
            {[
              { id: 'layout', label: '📐 Mise en page' },
              { id: 'theme', label: '🎨 Thème' },
              { id: 'typography', label: '✏️ Typographie' },
              { id: 'widgets', label: '🧩 Widgets' },
              { id: 'preferences', label: '⚙️ Préférences' },
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

        {/* Aperçu */}
        {renderPreview()}

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
                {activeTab === 'theme' && renderThemeTab()}
                {activeTab === 'typography' && renderTypographyTab()}
                {activeTab === 'widgets' && renderWidgetsTab()}
                {activeTab === 'preferences' && renderPreferencesTab()}
                {activeTab === 'advanced' && renderAdvancedTab()}
              </motion.div>
            </AnimatePresence>

            {/* Actions */}
            <div className="mt-6 flex items-center justify-end gap-3 pt-6 border-t border-gray-200 dark:border-gray-700">
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setConfig(DEFAULT_LAYOUT);
                  toast({
                    title: 'Réinitialisé',
                    description: 'Les paramètres ont été réinitialisés',
                    duration: 2000,
                  });
                }}
                disabled={disabled || isSubmitting || isLoading}
              >
                <ArrowPathIcon className="h-4 w-4 mr-2" />
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

LayoutSettingsForm.displayName = 'LayoutSettingsForm';

export default LayoutSettingsForm;

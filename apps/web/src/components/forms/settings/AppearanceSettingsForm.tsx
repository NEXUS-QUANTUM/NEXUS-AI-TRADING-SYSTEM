// apps/web/src/components/forms/settings/AppearanceSettingsForm.tsx
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
  SunIcon,
  MoonIcon,
  ComputerDesktopIcon,
  PaintBrushIcon,
  SwatchIcon,
  AdjustmentsHorizontalIcon,
  CheckIcon,
  XMarkIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  EyeIcon,
  EyeSlashIcon,
  PencilIcon,
  TrashIcon,
  DocumentDuplicateIcon,
  ShareIcon,
  LinkIcon,
  BookmarkIcon,
  HeartIcon,
  StarIcon,
  FlagIcon,
  PrinterIcon,
  EnvelopeIcon,
  ClipboardIcon,
  PlusIcon,
  MinusIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  GlobeAltIcon,
  SparklesIcon,
  RocketLaunchIcon,
  ShieldCheckIcon,
  Cog6ToothIcon,
  Squares2X2Icon,
  ListBulletIcon,
  ViewColumnsIcon,
  RectangleGroupIcon,
} from '@heroicons/react/24/outline';
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
import { useTheme } from 'next-themes';

// ============================================================================
// TYPES
// ============================================================================

export type ThemeMode = 'light' | 'dark' | 'system' | 'auto';
export type ThemeVariant = 'default' | 'brand' | 'minimal' | 'glass' | 'gradient' | 'custom';
export type ColorScheme = 'blue' | 'purple' | 'green' | 'red' | 'orange' | 'pink' | 'teal' | 'indigo' | 'gray';
export type FontSize = 'small' | 'medium' | 'large' | 'extra-large';
export type FontWeight = 'light' | 'normal' | 'medium' | 'semibold' | 'bold';
export type LayoutStyle = 'compact' | 'comfortable' | 'spacious';
export type SidebarPosition = 'left' | 'right';
export type NavigationStyle = 'top' | 'side' | 'both' | 'minimal';
export type CardStyle = 'default' | 'glass' | 'outlined' | 'shadow' | 'borderless';
export type ButtonStyle = 'default' | 'rounded' | 'pill' | 'outlined' | 'ghost';

export interface AppearanceSettingsData {
  /** Thème */
  theme: {
    /** Mode du thème */
    mode: ThemeMode;
    /** Variante du thème */
    variant: ThemeVariant;
    /** Schéma de couleurs */
    colorScheme: ColorScheme;
    /** Couleur personnalisée (hex) */
    customColor?: string;
    /** Police */
    fontFamily: string;
    /** Taille de police */
    fontSize: FontSize;
    /** Poids de police */
    fontWeight: FontWeight;
    /** Rayon de bordure */
    borderRadius: number;
    /** Opacité de fond */
    backgroundOpacity: number;
  };
  /** Layout */
  layout: {
    /** Style de layout */
    style: LayoutStyle;
    /** Position de la sidebar */
    sidebar: SidebarPosition;
    /** Style de navigation */
    navigation: NavigationStyle;
    /** Style des cartes */
    cardStyle: CardStyle;
    /** Style des boutons */
    buttonStyle: ButtonStyle;
    /** Afficher les ombres */
    showShadows: boolean;
    /** Afficher les animations */
    showAnimations: boolean;
    /** Afficher les bordures */
    showBorders: boolean;
    /** Afficher les séparateurs */
    showSeparators: boolean;
    /** Afficher les icônes */
    showIcons: boolean;
    /** Afficher les labels */
    showLabels: boolean;
    /** Afficher les badges */
    showBadges: boolean;
    /** Afficher les tooltips */
    showTooltips: boolean;
  };
  /** Personnalisation avancée */
  custom: {
    /** CSS personnalisé */
    customCss?: string;
    /** Couleur de fond */
    backgroundColor?: string;
    /** Couleur de texte */
    textColor?: string;
    /** Couleur de lien */
    linkColor?: string;
    /** Couleur d'accent */
    accentColor?: string;
    /** Police personnalisée */
    customFont?: string;
    /** Logo personnalisé */
    customLogo?: string;
    /** Favicon personnalisé */
    customFavicon?: string;
  };
}

export interface AppearanceSettingsFormProps {
  // --- Contrôle ---
  /** Données initiales */
  initialData?: Partial<AppearanceSettingsData>;
  /** Callback de soumission */
  onSubmit?: (data: AppearanceSettingsData) => void | Promise<void>;
  /** Callback de succès */
  onSuccess?: (data: AppearanceSettingsData) => void;
  /** Callback d'erreur */
  onError?: (error: string) => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de changement */
  onChange?: (data: AppearanceSettingsData) => void;

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

const COLOR_SCHEMES: Record<ColorScheme, { label: string; color: string; light: string; dark: string }> = {
  blue: { label: 'Bleu', color: '#3B82F6', light: '#EFF6FF', dark: '#1E3A5F' },
  purple: { label: 'Violet', color: '#8B5CF6', light: '#F5F3FF', dark: '#2D1B4E' },
  green: { label: 'Vert', color: '#22C55E', light: '#F0FDF4', dark: '#1A3A2A' },
  red: { label: 'Rouge', color: '#EF4444', light: '#FEF2F2', dark: '#3A1A1A' },
  orange: { label: 'Orange', color: '#F59E0B', light: '#FFFBEB', dark: '#3A2A1A' },
  pink: { label: 'Rose', color: '#EC4899', light: '#FDF2F8', dark: '#3A1A2A' },
  teal: { label: 'Teal', color: '#14B8A6', light: '#F0FDFA', dark: '#1A3A35' },
  indigo: { label: 'Indigo', color: '#6366F1', light: '#EEF2FF', dark: '#1A1A3A' },
  gray: { label: 'Gris', color: '#6B7280', light: '#F9FAFB', dark: '#2A2A2A' },
};

const FONTS = [
  { value: 'Inter, sans-serif', label: 'Inter' },
  { value: 'Roboto, sans-serif', label: 'Roboto' },
  { value: 'Poppins, sans-serif', label: 'Poppins' },
  { value: 'Open Sans, sans-serif', label: 'Open Sans' },
  { value: 'Lato, sans-serif', label: 'Lato' },
  { value: 'Montserrat, sans-serif', label: 'Montserrat' },
  { value: 'Nunito, sans-serif', label: 'Nunito' },
  { value: 'Merriweather, serif', label: 'Merriweather' },
  { value: 'Playfair Display, serif', label: 'Playfair Display' },
  { value: 'JetBrains Mono, monospace', label: 'JetBrains Mono' },
];

const FONT_SIZES: { value: FontSize; label: string; size: string }[] = [
  { value: 'small', label: 'Petite', size: '12px' },
  { value: 'medium', label: 'Moyenne', size: '14px' },
  { value: 'large', label: 'Grande', size: '16px' },
  { value: 'extra-large', label: 'Très grande', size: '18px' },
];

const FONT_WEIGHTS: { value: FontWeight; label: string }[] = [
  { value: 'light', label: 'Léger' },
  { value: 'normal', label: 'Normal' },
  { value: 'medium', label: 'Moyen' },
  { value: 'semibold', label: 'Semi-gras' },
  { value: 'bold', label: 'Gras' },
];

const LAYOUT_STYLES: { value: LayoutStyle; label: string; description: string }[] = [
  { value: 'compact', label: 'Compact', description: 'Espacement minimal' },
  { value: 'comfortable', label: 'Confortable', description: 'Espacement standard' },
  { value: 'spacious', label: 'Spacieux', description: 'Espacement généreux' },
];

const THEME_VARIANTS: { value: ThemeVariant; label: string; icon: React.ReactNode }[] = [
  { value: 'default', label: 'Défaut', icon: <SwatchIcon className="h-4 w-4" /> },
  { value: 'brand', label: 'Marque', icon: <SparklesIcon className="h-4 w-4" /> },
  { value: 'minimal', label: 'Minimal', icon: <AdjustmentsHorizontalIcon className="h-4 w-4" /> },
  { value: 'glass', label: 'Verre', icon: <EyeIcon className="h-4 w-4" /> },
  { value: 'gradient', label: 'Dégradé', icon: <PaintBrushIcon className="h-4 w-4" /> },
  { value: 'custom', label: 'Personnalisé', icon: <PencilIcon className="h-4 w-4" /> },
];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const AppearanceSettingsForm = forwardRef<HTMLDivElement, AppearanceSettingsFormProps>(
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
      title = 'Apparence',
      subtitle = 'Personnalisez l\'apparence de l\'application',
      className,
      variant = 'default',

      // États
      isLoading = false,
      error = null,
      success = null,
      disabled = false,

      // Accessibilité
      ariaLabel = 'Paramètres d\'apparence',
      id,

      // Avancé
      debug = false,
    } = props;

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // THEME
    // ========================================================================

    const { theme, setTheme } = useTheme();

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const formRef = useRef<HTMLFormElement>(null);
    const fileInputRef = useRef<HTMLInputElement>(null);

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [formData, setFormData] = useState<AppearanceSettingsData>({
      theme: {
        mode: 'system',
        variant: 'default',
        colorScheme: 'blue',
        fontFamily: 'Inter, sans-serif',
        fontSize: 'medium',
        fontWeight: 'normal',
        borderRadius: 8,
        backgroundOpacity: 100,
      },
      layout: {
        style: 'comfortable',
        sidebar: 'left',
        navigation: 'top',
        cardStyle: 'default',
        buttonStyle: 'default',
        showShadows: true,
        showAnimations: true,
        showBorders: true,
        showSeparators: true,
        showIcons: true,
        showLabels: true,
        showBadges: true,
        showTooltips: true,
      },
      custom: {},
      ...initialData,
    });

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [activeTab, setActiveTab] = useState<'theme' | 'layout' | 'advanced'>('theme');
    const [previewMode, setPreviewMode] = useState<'light' | 'dark'>('light');
    const [colorPickerOpen, setColorPickerOpen] = useState(false);
    const [selectedColor, setSelectedColor] = useState<string>(COLOR_SCHEMES.blue.color);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validate = useCallback((): boolean => {
      const errors: Record<string, string> = {};

      if (formData.theme.borderRadius < 0 || formData.theme.borderRadius > 32) {
        errors.borderRadius = 'Le rayon de bordure doit être entre 0 et 32px';
      }

      if (formData.theme.backgroundOpacity < 0 || formData.theme.backgroundOpacity > 100) {
        errors.backgroundOpacity = 'L\'opacité doit être entre 0% et 100%';
      }

      setFormErrors(errors);
      return Object.keys(errors).length === 0;
    }, [formData]);

    // ========================================================================
    // GESTIONNAIRES DE CHAMPS
    // ========================================================================

    const handleThemeChange = useCallback(<K extends keyof AppearanceSettingsData['theme']>(
      field: K,
      value: AppearanceSettingsData['theme'][K]
    ) => {
      setFormData(prev => ({
        ...prev,
        theme: { ...prev.theme, [field]: value },
      }));
      setFormErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });

      // Appliquer le thème globalement
      if (field === 'mode') {
        setTheme(value as string);
      }
    }, [setTheme]);

    const handleLayoutChange = useCallback(<K extends keyof AppearanceSettingsData['layout']>(
      field: K,
      value: AppearanceSettingsData['layout'][K]
    ) => {
      setFormData(prev => ({
        ...prev,
        layout: { ...prev.layout, [field]: value },
      }));
    }, []);

    const handleCustomChange = useCallback(<K extends keyof AppearanceSettingsData['custom']>(
      field: K,
      value: AppearanceSettingsData['custom'][K]
    ) => {
      setFormData(prev => ({
        ...prev,
        custom: { ...prev.custom, [field]: value },
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
          title: 'Apparence mise à jour',
          description: 'Les paramètres d\'apparence ont été sauvegardés',
          variant: 'success',
        });

        if (debug) {
          console.log('Appearance settings saved:', formData);
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
    // RENDU DE L'APERÇU
    // ========================================================================

    const renderPreview = () => {
      const colorScheme = COLOR_SCHEMES[formData.theme.colorScheme] || COLOR_SCHEMES.blue;
      const isDark = previewMode === 'dark';

      return (
        <div
          className={cn(
            'rounded-lg p-4 transition-colors',
            isDark ? 'bg-gray-900' : 'bg-white',
            'border border-gray-200 dark:border-gray-700'
          )}
          style={{
            fontFamily: formData.theme.fontFamily,
            fontSize: FONT_SIZES.find(f => f.value === formData.theme.fontSize)?.size || '14px',
            fontWeight: formData.theme.fontWeight === 'light' ? 300 :
                        formData.theme.fontWeight === 'medium' ? 500 :
                        formData.theme.fontWeight === 'semibold' ? 600 :
                        formData.theme.fontWeight === 'bold' ? 700 : 400,
          }}
        >
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2">
              <div
                className="h-8 w-8 rounded-full"
                style={{ backgroundColor: colorScheme.color }}
              />
              <span className={cn('font-medium', isDark ? 'text-white' : 'text-gray-900')}>
                Aperçu en {previewMode}
              </span>
            </div>
            <div className="flex gap-1">
              <button
                type="button"
                className={cn(
                  'rounded p-1 text-xs transition-colors',
                  previewMode === 'light'
                    ? 'bg-brand-500 text-white'
                    : isDark ? 'text-gray-400 hover:text-gray-300' : 'text-gray-400 hover:text-gray-600'
                )}
                onClick={() => setPreviewMode('light')}
              >
                ☀️
              </button>
              <button
                type="button"
                className={cn(
                  'rounded p-1 text-xs transition-colors',
                  previewMode === 'dark'
                    ? 'bg-brand-500 text-white'
                    : isDark ? 'text-gray-400 hover:text-gray-300' : 'text-gray-400 hover:text-gray-600'
                )}
                onClick={() => setPreviewMode('dark')}
              >
                🌙
              </button>
            </div>
          </div>

          <div className="space-y-3">
            <div className={cn(
              'rounded-lg p-3',
              formData.layout.cardStyle === 'glass' ? 'bg-white/20 backdrop-blur' :
              formData.layout.cardStyle === 'outlined' ? 'border-2' :
              formData.layout.cardStyle === 'shadow' ? 'shadow-lg' :
              formData.layout.cardStyle === 'borderless' ? '' :
              'bg-gray-50 dark:bg-gray-800',
              formData.layout.showBorders && 'border border-gray-200 dark:border-gray-700'
            )}>
              <div className="flex items-center gap-2">
                <div
                  className="h-6 w-6 rounded"
                  style={{ backgroundColor: colorScheme.color }}
                />
                <span className={cn('font-medium', isDark ? 'text-white' : 'text-gray-900')}>
                  Carte d'aperçu
                </span>
                <Badge
                  variant="primary"
                  size="xs"
                  style={{ backgroundColor: colorScheme.color }}
                >
                  Badge
                </Badge>
              </div>
              <p className={cn('text-sm mt-1', isDark ? 'text-gray-300' : 'text-gray-600')}>
                Ceci est un aperçu de l'apparence avec vos paramètres.
              </p>
              <div className="flex gap-2 mt-2">
                <button
                  className={cn(
                    'px-3 py-1 text-sm transition-colors',
                    formData.layout.buttonStyle === 'rounded' ? 'rounded-md' :
                    formData.layout.buttonStyle === 'pill' ? 'rounded-full' :
                    'rounded',
                    formData.layout.buttonStyle === 'outlined'
                      ? 'border-2 border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800'
                      : formData.layout.buttonStyle === 'ghost'
                      ? 'hover:bg-gray-100 dark:hover:bg-gray-800'
                      : 'bg-brand-500 text-white hover:bg-brand-600'
                  )}
                  style={{ backgroundColor: colorScheme.color }}
                >
                  Bouton
                </button>
                <button
                  className={cn(
                    'px-3 py-1 text-sm transition-colors',
                    formData.layout.buttonStyle === 'rounded' ? 'rounded-md' :
                    formData.layout.buttonStyle === 'pill' ? 'rounded-full' :
                    'rounded',
                    'border border-gray-300 dark:border-gray-600 hover:bg-gray-50 dark:hover:bg-gray-800'
                  )}
                >
                  Secondaire
                </button>
              </div>
            </div>
          </div>
        </div>
      );
    };

    // ========================================================================
    // RENDU DE L'ONGLET THEME
    // ========================================================================

    const renderThemeTab = () => (
      <div className="space-y-6">
        {/* Aperçu */}
        {renderPreview()}

        <Separator />

        {/* Mode et Variante */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Mode
            </label>
            <div className="flex gap-2">
              {([
                { value: 'light', icon: <SunIcon className="h-4 w-4" />, label: 'Clair' },
                { value: 'dark', icon: <MoonIcon className="h-4 w-4" />, label: 'Sombre' },
                { value: 'system', icon: <ComputerDesktopIcon className="h-4 w-4" />, label: 'Système' },
              ] as { value: ThemeMode; icon: React.ReactNode; label: string }[]).map((mode) => (
                <button
                  key={mode.value}
                  type="button"
                  className={cn(
                    'flex flex-1 items-center justify-center gap-2 rounded-lg border-2 p-2 transition-all',
                    formData.theme.mode === mode.value
                      ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                  )}
                  onClick={() => handleThemeChange('mode', mode.value)}
                  disabled={disabled || isSubmitting || isLoading}
                >
                  {mode.icon}
                  <span className="text-sm">{mode.label}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Variante
            </label>
            <div className="grid grid-cols-2 gap-2">
              {THEME_VARIANTS.map((variant) => (
                <button
                  key={variant.value}
                  type="button"
                  className={cn(
                    'flex items-center gap-2 rounded-lg border-2 p-2 transition-all',
                    formData.theme.variant === variant.value
                      ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                  )}
                  onClick={() => handleThemeChange('variant', variant.value)}
                  disabled={disabled || isSubmitting || isLoading}
                >
                  {variant.icon}
                  <span className="text-sm">{variant.label}</span>
                </button>
              ))}
            </div>
          </div>
        </div>

        {/* Schéma de couleurs */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Schéma de couleurs
          </label>
          <div className="flex flex-wrap gap-2">
            {Object.entries(COLOR_SCHEMES).map(([key, scheme]) => (
              <button
                key={key}
                type="button"
                className={cn(
                  'flex items-center gap-2 rounded-lg border-2 p-2 transition-all',
                  formData.theme.colorScheme === key
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
                onClick={() => {
                  handleThemeChange('colorScheme', key as ColorScheme);
                  setSelectedColor(scheme.color);
                }}
                disabled={disabled || isSubmitting || isLoading}
              >
                <div
                  className="h-5 w-5 rounded-full border border-gray-200 dark:border-gray-600"
                  style={{ backgroundColor: scheme.color }}
                />
                <span className="text-sm">{scheme.label}</span>
              </button>
            ))}
          </div>
        </div>

        {/* Couleur personnalisée */}
        {formData.theme.variant === 'custom' && (
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Couleur personnalisée
            </label>
            <div className="flex items-center gap-4">
              <input
                type="color"
                value={formData.theme.customColor || selectedColor}
                onChange={(e) => {
                  handleThemeChange('customColor', e.target.value);
                  setSelectedColor(e.target.value);
                }}
                className="h-10 w-10 rounded border border-gray-200 dark:border-gray-700 cursor-pointer"
                disabled={disabled || isSubmitting || isLoading}
              />
              <Input
                type="text"
                value={formData.theme.customColor || selectedColor}
                onChange={(e) => handleThemeChange('customColor', e.target.value)}
                className="flex-1 font-mono"
                disabled={disabled || isSubmitting || isLoading}
              />
            </div>
          </div>
        )}

        <Separator />

        {/* Typographie */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Police
            </label>
            <Select
              options={FONTS}
              value={formData.theme.fontFamily}
              onChange={(value) => handleThemeChange('fontFamily', value)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Taille de police
            </label>
            <div className="flex gap-2">
              {FONT_SIZES.map((size) => (
                <button
                  key={size.value}
                  type="button"
                  className={cn(
                    'flex-1 rounded-lg border-2 p-2 text-center transition-all',
                    formData.theme.fontSize === size.value
                      ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                  )}
                  onClick={() => handleThemeChange('fontSize', size.value)}
                  disabled={disabled || isSubmitting || isLoading}
                  style={{ fontSize: size.size }}
                >
                  {size.label}
                </button>
              ))}
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Poids de police
            </label>
            <Select
              options={FONT_WEIGHTS}
              value={formData.theme.fontWeight}
              onChange={(value) => handleThemeChange('fontWeight', value as FontWeight)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Rayon de bordure ({formData.theme.borderRadius}px)
              </label>
            </div>
            <Slider
              min={0}
              max={32}
              step={1}
              value={[formData.theme.borderRadius]}
              onValueChange={(value) => handleThemeChange('borderRadius', value[0])}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Opacité de fond ({formData.theme.backgroundOpacity}%)
            </label>
          </div>
          <Slider
            min={0}
            max={100}
            step={1}
            value={[formData.theme.backgroundOpacity]}
            onValueChange={(value) => handleThemeChange('backgroundOpacity', value[0])}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>
      </div>
    );

    // ========================================================================
    // RENDU DE L'ONGLET LAYOUT
    // ========================================================================

    const renderLayoutTab = () => (
      <div className="space-y-6">
        {/* Style de layout */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Style de layout
          </label>
          <div className="grid grid-cols-3 gap-2">
            {LAYOUT_STYLES.map((style) => (
              <button
                key={style.value}
                type="button"
                className={cn(
                  'rounded-lg border-2 p-3 text-center transition-all',
                  formData.layout.style === style.value
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
                onClick={() => handleLayoutChange('style', style.value)}
                disabled={disabled || isSubmitting || isLoading}
              >
                <div className="flex justify-center gap-0.5">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <div
                      key={i}
                      className={cn(
                        'h-1 w-4 rounded-full',
                        formData.layout.style === style.value
                          ? 'bg-brand-500'
                          : 'bg-gray-300 dark:bg-gray-600'
                      )}
                    />
                  ))}
                </div>
                <p className="mt-1 text-sm font-medium">{style.label}</p>
                <p className="text-xs text-gray-500 dark:text-gray-400">{style.description}</p>
              </button>
            ))}
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Position de la sidebar
            </label>
            <div className="flex gap-2">
              {(['left', 'right'] as SidebarPosition[]).map((pos) => (
                <button
                  key={pos}
                  type="button"
                  className={cn(
                    'flex-1 rounded-lg border-2 p-2 text-center transition-all',
                    formData.layout.sidebar === pos
                      ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                  )}
                  onClick={() => handleLayoutChange('sidebar', pos)}
                  disabled={disabled || isSubmitting || isLoading}
                >
                  <span className="capitalize">{pos}</span>
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Style de navigation
            </label>
            <Select
              options={[
                { value: 'top', label: 'En haut' },
                { value: 'side', label: 'Sur le côté' },
                { value: 'both', label: 'Les deux' },
                { value: 'minimal', label: 'Minimal' },
              ]}
              value={formData.layout.navigation}
              onChange={(value) => handleLayoutChange('navigation', value as NavigationStyle)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Style des cartes
            </label>
            <Select
              options={[
                { value: 'default', label: 'Défaut' },
                { value: 'glass', label: 'Verre' },
                { value: 'outlined', label: 'Contour' },
                { value: 'shadow', label: 'Ombre' },
                { value: 'borderless', label: 'Sans bordure' },
              ]}
              value={formData.layout.cardStyle}
              onChange={(value) => handleLayoutChange('cardStyle', value as CardStyle)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Style des boutons
            </label>
            <Select
              options={[
                { value: 'default', label: 'Défaut' },
                { value: 'rounded', label: 'Arrondi' },
                { value: 'pill', label: 'Pilule' },
                { value: 'outlined', label: 'Contour' },
                { value: 'ghost', label: 'Fantôme' },
              ]}
              value={formData.layout.buttonStyle}
              onChange={(value) => handleLayoutChange('buttonStyle', value as ButtonStyle)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <Separator />

        {/* Options d'affichage */}
        <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">Options d'affichage</h4>

        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <div className="flex items-center justify-between">
            <span className="text-sm">Ombres</span>
            <Switch
              checked={formData.layout.showShadows}
              onCheckedChange={(checked) => handleLayoutChange('showShadows', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm">Animations</span>
            <Switch
              checked={formData.layout.showAnimations}
              onCheckedChange={(checked) => handleLayoutChange('showAnimations', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm">Bordures</span>
            <Switch
              checked={formData.layout.showBorders}
              onCheckedChange={(checked) => handleLayoutChange('showBorders', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm">Séparateurs</span>
            <Switch
              checked={formData.layout.showSeparators}
              onCheckedChange={(checked) => handleLayoutChange('showSeparators', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm">Icônes</span>
            <Switch
              checked={formData.layout.showIcons}
              onCheckedChange={(checked) => handleLayoutChange('showIcons', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm">Labels</span>
            <Switch
              checked={formData.layout.showLabels}
              onCheckedChange={(checked) => handleLayoutChange('showLabels', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm">Badges</span>
            <Switch
              checked={formData.layout.showBadges}
              onCheckedChange={(checked) => handleLayoutChange('showBadges', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="flex items-center justify-between">
            <span className="text-sm">Tooltips</span>
            <Switch
              checked={formData.layout.showTooltips}
              onCheckedChange={(checked) => handleLayoutChange('showTooltips', checked)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>
      </div>
    );

    // ========================================================================
    // RENDU DE L'ONGLET AVANCÉ
    // ========================================================================

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
            value={formData.custom.customCss || ''}
            onChange={(e) => handleCustomChange('customCss', e.target.value)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <Separator />

        {/* Couleurs personnalisées */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Couleur de fond
            </label>
            <div className="flex items-center gap-4">
              <input
                type="color"
                value={formData.custom.backgroundColor || '#ffffff'}
                onChange={(e) => handleCustomChange('backgroundColor', e.target.value)}
                className="h-10 w-10 rounded border border-gray-200 dark:border-gray-700 cursor-pointer"
                disabled={disabled || isSubmitting || isLoading}
              />
              <Input
                type="text"
                value={formData.custom.backgroundColor || '#ffffff'}
                onChange={(e) => handleCustomChange('backgroundColor', e.target.value)}
                className="flex-1 font-mono"
                disabled={disabled || isSubmitting || isLoading}
              />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Couleur de texte
            </label>
            <div className="flex items-center gap-4">
              <input
                type="color"
                value={formData.custom.textColor || '#000000'}
                onChange={(e) => handleCustomChange('textColor', e.target.value)}
                className="h-10 w-10 rounded border border-gray-200 dark:border-gray-700 cursor-pointer"
                disabled={disabled || isSubmitting || isLoading}
              />
              <Input
                type="text"
                value={formData.custom.textColor || '#000000'}
                onChange={(e) => handleCustomChange('textColor', e.target.value)}
                className="flex-1 font-mono"
                disabled={disabled || isSubmitting || isLoading}
              />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Couleur de lien
            </label>
            <div className="flex items-center gap-4">
              <input
                type="color"
                value={formData.custom.linkColor || '#3B82F6'}
                onChange={(e) => handleCustomChange('linkColor', e.target.value)}
                className="h-10 w-10 rounded border border-gray-200 dark:border-gray-700 cursor-pointer"
                disabled={disabled || isSubmitting || isLoading}
              />
              <Input
                type="text"
                value={formData.custom.linkColor || '#3B82F6'}
                onChange={(e) => handleCustomChange('linkColor', e.target.value)}
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
                value={formData.custom.accentColor || '#8B5CF6'}
                onChange={(e) => handleCustomChange('accentColor', e.target.value)}
                className="h-10 w-10 rounded border border-gray-200 dark:border-gray-700 cursor-pointer"
                disabled={disabled || isSubmitting || isLoading}
              />
              <Input
                type="text"
                value={formData.custom.accentColor || '#8B5CF6'}
                onChange={(e) => handleCustomChange('accentColor', e.target.value)}
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
            value={formData.custom.customFont || ''}
            onChange={(e) => handleCustomChange('customFont', e.target.value)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>

        <Separator />

        {/* Logo et Favicon */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Logo personnalisé
            </label>
            <div className="flex gap-2">
              <Input
                type="text"
                placeholder="URL du logo"
                value={formData.custom.customLogo || ''}
                onChange={(e) => handleCustomChange('customLogo', e.target.value)}
                disabled={disabled || isSubmitting || isLoading}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => fileInputRef.current?.click()}
                disabled={disabled || isSubmitting || isLoading}
              >
                Parcourir
              </Button>
              <input
                ref={fileInputRef}
                type="file"
                accept="image/*"
                className="hidden"
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    const reader = new FileReader();
                    reader.onloadend = () => {
                      handleCustomChange('customLogo', reader.result as string);
                    };
                    reader.readAsDataURL(file);
                  }
                }}
                disabled={disabled || isSubmitting || isLoading}
              />
            </div>
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Favicon personnalisé
            </label>
            <div className="flex gap-2">
              <Input
                type="text"
                placeholder="URL du favicon"
                value={formData.custom.customFavicon || ''}
                onChange={(e) => handleCustomChange('customFavicon', e.target.value)}
                disabled={disabled || isSubmitting || isLoading}
              />
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => fileInputRef.current?.click()}
                disabled={disabled || isSubmitting || isLoading}
              >
                Parcourir
              </Button>
            </div>
          </div>
        </div>

        <div className="rounded-lg bg-yellow-50 dark:bg-yellow-900/20 p-4 border border-yellow-200 dark:border-yellow-800">
          <div className="flex items-start gap-3">
            <ExclamationTriangleIcon className="h-5 w-5 text-yellow-600 dark:text-yellow-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-yellow-800 dark:text-yellow-200">
                Note sur les personnalisations avancées
              </p>
              <p className="text-xs text-yellow-700 dark:text-yellow-300 mt-1">
                Les modifications apportées ici peuvent affecter l'affichage de l'application.
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
                  <PaintBrushIcon className="h-3 w-3" />
                  Personnalisation
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
              { id: 'theme', label: '🎨 Thème' },
              { id: 'layout', label: '📐 Layout' },
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
                {activeTab === 'theme' && renderThemeTab()}
                {activeTab === 'layout' && renderLayoutTab()}
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
              Thème: {formData.theme.mode} • {formData.theme.colorScheme}
            </span>
            <span>
              Police: {formData.theme.fontFamily.split(',')[0]}
            </span>
          </div>
        </CardFooter>
      </Card>
    );
  }
);

AppearanceSettingsForm.displayName = 'AppearanceSettingsForm';

// ============================================================================
// EXPORTS
// ============================================================================

export default AppearanceSettingsForm;

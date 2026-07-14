// apps/web/src/components/forms/dashboard/index.ts

// ============================================================================
// EXPORTS PRINCIPAUX - FORMULAIRES DE CONFIGURATION DU TABLEAU DE BORD
// ============================================================================

// --- Formulaire de Configuration du Tableau de Bord ---
export { default as DashboardConfigForm } from './DashboardConfigForm';
export type {
  DashboardConfigFormProps,
  DashboardConfigData,
  WidgetConfig,
  WidgetSize,
  WidgetCategory,
  DashboardLayout,
  DashboardTheme,
} from './DashboardConfigForm';

// --- Formulaire de Configuration de la Mise en Page ---
export { default as LayoutSettingsForm } from './LayoutSettingsForm';
export type {
  LayoutSettingsFormProps,
  LayoutSettingsData,
  LayoutType,
  LayoutTheme,
  LayoutSpacing,
  LayoutCornerRadius,
  LayoutShadow,
  LayoutAnimation,
  LayoutBackground,
} from './LayoutSettingsForm';

// --- Formulaire de Configuration des Widgets ---
export { default as WidgetSettingsForm } from './WidgetSettingsForm';
export type {
  WidgetSettingsFormProps,
  WidgetSettingsData,
  WidgetDisplayMode,
  WidgetRefreshStrategy,
  WidgetDataRange,
} from './WidgetSettingsForm';

// ============================================================================
// EXPORTS DE TYPE - CONSTANTES ET UTILITAIRES
// ============================================================================

// --- Types Génériques pour la Configuration du Dashboard ---
export type DashboardFormVariant = 'default' | 'glass' | 'solid' | 'outlined';
export type DashboardFormSize = 'sm' | 'md' | 'lg';

// --- Interface de Base pour les Formulaires de Configuration ---
export interface BaseDashboardFormProps {
  /** Titre du formulaire */
  title?: string;
  /** Sous-titre du formulaire */
  subtitle?: string;
  /** Classes additionnelles */
  className?: string;
  /** Variante de la carte */
  variant?: DashboardFormVariant;
  /** Taille du formulaire */
  size?: DashboardFormSize;
  /** État de chargement */
  isLoading?: boolean;
  /** État d'erreur */
  error?: string | null;
  /** Message de succès */
  success?: string | null;
  /** Désactiver le formulaire */
  disabled?: boolean;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** ARIA label */
  ariaLabel?: string;
  /** ID */
  id?: string;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONFIGURATIONS PRÉDÉFINIES - WIDGETS
// ============================================================================

export const DEFAULT_WIDGETS = [
  {
    id: 'welcome',
    type: 'welcome',
    title: 'Bienvenue',
    description: 'Message de bienvenue personnalisé',
    category: 'custom' as WidgetCategory,
    size: '2x1' as WidgetSize,
    position: { x: 0, y: 0 },
    visible: true,
  },
  {
    id: 'market-overview',
    type: 'market-overview',
    title: 'Aperçu du marché',
    description: 'Vue d\'ensemble des marchés',
    category: 'market' as WidgetCategory,
    size: '2x2' as WidgetSize,
    position: { x: 0, y: 1 },
    visible: true,
  },
  {
    id: 'portfolio-performance',
    type: 'portfolio-performance',
    title: 'Performance du portfolio',
    description: 'Suivi des performances',
    category: 'portfolio' as WidgetCategory,
    size: '3x2' as WidgetSize,
    position: { x: 2, y: 1 },
    visible: true,
  },
  {
    id: 'recent-trades',
    type: 'recent-trades',
    title: 'Trades récents',
    description: 'Historique des trades',
    category: 'trading' as WidgetCategory,
    size: '2x2' as WidgetSize,
    position: { x: 0, y: 3 },
    visible: true,
  },
  {
    id: 'system-health',
    type: 'system-health',
    title: 'Santé du système',
    description: 'État des services',
    category: 'system' as WidgetCategory,
    size: '2x2' as WidgetSize,
    position: { x: 2, y: 3 },
    visible: true,
  },
  {
    id: 'ai-insights',
    type: 'ai-insights',
    title: 'Insights IA',
    description: 'Recommandations IA',
    category: 'analytics' as WidgetCategory,
    size: '2x1' as WidgetSize,
    position: { x: 4, y: 1 },
    visible: true,
  },
];

// ============================================================================
// CONFIGURATIONS PRÉDÉFINIES - LAYOUT
// ============================================================================

export const DEFAULT_LAYOUT_CONFIG: LayoutSettingsData = {
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
// CONSTANTES - TAILLES DES WIDGETS
// ============================================================================

export const WIDGET_SIZE_MAP: Record<WidgetSize, { width: number; height: number; label: string }> = {
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

// ============================================================================
// CONSTANTES - CATÉGORIES DE WIDGETS
// ============================================================================

export const WIDGET_CATEGORIES: WidgetCategory[] = [
  'trading',
  'analytics',
  'portfolio',
  'market',
  'system',
  'social',
  'custom',
];

export const WIDGET_CATEGORY_LABELS: Record<WidgetCategory, string> = {
  trading: 'Trading',
  analytics: 'Analytique',
  portfolio: 'Portfolio',
  market: 'Marché',
  system: 'Système',
  social: 'Social',
  custom: 'Personnalisé',
};

export const WIDGET_CATEGORY_ICONS: Record<WidgetCategory, string> = {
  trading: '📈',
  analytics: '📊',
  portfolio: '💼',
  market: '🌍',
  system: '⚙️',
  social: '👥',
  custom: '🎨',
};

export const WIDGET_CATEGORY_COLORS: Record<WidgetCategory, string> = {
  trading: 'text-blue-600 dark:text-blue-400 bg-blue-50 dark:bg-blue-900/20',
  analytics: 'text-purple-600 dark:text-purple-400 bg-purple-50 dark:bg-purple-900/20',
  portfolio: 'text-green-600 dark:text-green-400 bg-green-50 dark:bg-green-900/20',
  market: 'text-yellow-600 dark:text-yellow-400 bg-yellow-50 dark:bg-yellow-900/20',
  system: 'text-gray-600 dark:text-gray-400 bg-gray-50 dark:bg-gray-800/50',
  social: 'text-pink-600 dark:text-pink-400 bg-pink-50 dark:bg-pink-900/20',
  custom: 'text-indigo-600 dark:text-indigo-400 bg-indigo-50 dark:bg-indigo-900/20',
};

// ============================================================================
// CONSTANTES - OPTIONS DE CONFIGURATION
// ============================================================================

export const AVAILABLE_COLUMNS = [2, 3, 4, 6, 8, 12];
export const AVAILABLE_THEMES: LayoutTheme[] = ['light', 'dark', 'system', 'auto', 'custom'];
export const AVAILABLE_SPACINGS: LayoutSpacing[] = ['compact', 'normal', 'relaxed', 'spacious'];
export const AVAILABLE_CORNER_RADIUS: LayoutCornerRadius[] = ['none', 'small', 'medium', 'large', 'extra-large', 'full'];
export const AVAILABLE_SHADOWS: LayoutShadow[] = ['none', 'subtle', 'medium', 'strong', 'extra-strong'];
export const AVAILABLE_ANIMATIONS: LayoutAnimation[] = ['fade', 'slide', 'scale', 'bounce', 'none'];
export const AVAILABLE_FONT_SIZES: ('small' | 'medium' | 'large' | 'extra-large')[] = ['small', 'medium', 'large', 'extra-large'];
export const AVAILABLE_FONTS = [
  'Inter, sans-serif',
  'Roboto, sans-serif',
  'Poppins, sans-serif',
  'Merriweather, serif',
  'Mono, monospace',
  'System, sans-serif',
];
export const AVAILABLE_BACKGROUND_TYPES: LayoutBackground[] = ['solid', 'gradient', 'image', 'video', 'transparent'];

// ============================================================================
// UTILITAIRES - VALIDATION
// ============================================================================

export const validateWidgetConfig = (widget: WidgetConfig): { valid: boolean; errors: string[] } => {
  const errors: string[] = [];

  if (!widget.id) errors.push('ID du widget requis');
  if (!widget.type) errors.push('Type du widget requis');
  if (!widget.title) errors.push('Titre du widget requis');
  if (!widget.category) errors.push('Catégorie du widget requise');
  if (!widget.size) errors.push('Taille du widget requise');
  if (widget.position.x < 0 || widget.position.y < 0) {
    errors.push('Position du widget invalide');
  }
  if (typeof widget.visible !== 'boolean') {
    errors.push('Visibilité du widget invalide');
  }

  return { valid: errors.length === 0, errors };
};

export const validateLayoutConfig = (config: LayoutSettingsData): { valid: boolean; errors: string[] } => {
  const errors: string[] = [];

  if (config.columns < 1 || config.columns > 12) {
    errors.push('Le nombre de colonnes doit être entre 1 et 12');
  }
  if (config.widgets.gap < 0 || config.widgets.gap > 32) {
    errors.push('L\'espacement entre les widgets doit être entre 0 et 32px');
  }
  if (config.widgets.padding < 0 || config.widgets.padding > 32) {
    errors.push('Le padding des widgets doit être entre 0 et 32px');
  }
  if (config.preferences.zoom < 50 || config.preferences.zoom > 200) {
    errors.push('Le zoom doit être entre 50% et 200%');
  }
  if (config.background.opacity < 0 || config.background.opacity > 100) {
    errors.push('L\'opacité doit être entre 0% et 100%');
  }
  if (config.background.blur < 0 || config.background.blur > 20) {
    errors.push('Le flou doit être entre 0px et 20px');
  }

  return { valid: errors.length === 0, errors };
};

// ============================================================================
// UTILITAIRES - DÉFAUTS
// ============================================================================

export const getDefaultWidgetConfig = (type: string, title?: string): WidgetConfig => {
  const defaultWidget = DEFAULT_WIDGETS.find((w) => w.type === type);
  if (defaultWidget) {
    return {
      ...defaultWidget,
      title: title || defaultWidget.title,
      id: `${type}-${Date.now()}`,
    };
  }
  return {
    id: `${type}-${Date.now()}`,
    type,
    title: title || type.charAt(0).toUpperCase() + type.slice(1),
    category: 'custom',
    size: '2x2',
    position: { x: 0, y: 0 },
    visible: true,
  };
};

export const getDefaultLayoutConfig = (): LayoutSettingsData => {
  return { ...DEFAULT_LAYOUT_CONFIG };
};

// ============================================================================
// UTILITAIRES - STOCKAGE
// ============================================================================

export const saveDashboardConfig = (config: DashboardConfigData): void => {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem('nexus_dashboard_config', JSON.stringify(config));
  } catch (error) {
    console.error('Erreur lors de la sauvegarde de la configuration:', error);
  }
};

export const loadDashboardConfig = (): DashboardConfigData | null => {
  if (typeof window === 'undefined') return null;
  try {
    const data = localStorage.getItem('nexus_dashboard_config');
    return data ? JSON.parse(data) : null;
  } catch (error) {
    console.error('Erreur lors du chargement de la configuration:', error);
    return null;
  }
};

export const saveLayoutConfig = (config: LayoutSettingsData): void => {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem('nexus_layout_config', JSON.stringify(config));
  } catch (error) {
    console.error('Erreur lors de la sauvegarde de la mise en page:', error);
  }
};

export const loadLayoutConfig = (): LayoutSettingsData | null => {
  if (typeof window === 'undefined') return null;
  try {
    const data = localStorage.getItem('nexus_layout_config');
    return data ? JSON.parse(data) : null;
  } catch (error) {
    console.error('Erreur lors du chargement de la mise en page:', error);
    return null;
  }
};

// ============================================================================
// HOOKS DE CONFIGURATION
// ============================================================================

export { useDashboardConfig } from '@/hooks/useDashboardConfig';
export { useLayoutConfig } from '@/hooks/useLayoutConfig';
export { useWidgetConfig } from '@/hooks/useWidgetConfig';

// ============================================================================
// EXPORTATION PAR DÉFAUT - TOUS LES FORMULAIRES
// ============================================================================

/**
 * Exportation groupée de tous les formulaires de configuration du dashboard
 */
const DashboardForms = {
  DashboardConfig: DashboardConfigForm,
  LayoutSettings: LayoutSettingsForm,
  WidgetSettings: WidgetSettingsForm,
};

export default DashboardForms;

// ============================================================================
// TYPES DÉRIVÉS POUR UNE UTILISATION FACILE
// ============================================================================

/**
 * Type union de tous les noms de formulaires de configuration
 */
export type DashboardFormName = 
  | 'DashboardConfig'
  | 'LayoutSettings'
  | 'WidgetSettings';

/**
 * Mapping des props pour chaque formulaire de configuration
 */
export interface DashboardFormPropsMap {
  DashboardConfig: DashboardConfigFormProps;
  LayoutSettings: LayoutSettingsFormProps;
  WidgetSettings: WidgetSettingsFormProps;
}

/**
 * Type générique pour obtenir les props d'un formulaire spécifique
 */
export type DashboardFormProps<T extends DashboardFormName> = DashboardFormPropsMap[T];

/**
 * Type générique pour les données d'un formulaire spécifique
 */
export type DashboardFormDataMap = {
  DashboardConfig: DashboardConfigData;
  LayoutSettings: LayoutSettingsData;
  WidgetSettings: WidgetSettingsData;
};

export type DashboardFormData<T extends DashboardFormName> = DashboardFormDataMap[T];

// ============================================================================
// ROUTES DE CONFIGURATION
// ============================================================================

export const DASHBOARD_ROUTES = {
  CONFIG: '/dashboard/settings',
  LAYOUT: '/dashboard/settings/layout',
  WIDGETS: '/dashboard/settings/widgets',
  PREFERENCES: '/dashboard/settings/preferences',
  ADVANCED: '/dashboard/settings/advanced',
} as const;

export type DashboardRoute = typeof DASHBOARD_ROUTES[keyof typeof DASHBOARD_ROUTES];

// ============================================================================
// MESSAGES DE CONFIGURATION
// ============================================================================

export const DASHBOARD_MESSAGES = {
  // Succès
  SAVE_SUCCESS: 'Configuration sauvegardée avec succès',
  LAYOUT_SAVED: 'Mise en page sauvegardée avec succès',
  WIDGETS_SAVED: 'Configuration des widgets sauvegardée avec succès',
  RESET_SUCCESS: 'Configuration réinitialisée avec succès',

  // Erreurs
  SAVE_ERROR: 'Erreur lors de la sauvegarde de la configuration',
  LOAD_ERROR: 'Erreur lors du chargement de la configuration',
  VALIDATION_ERROR: 'Erreur de validation de la configuration',
  WIDGET_LIMIT_ERROR: 'Nombre maximal de widgets atteint',
  WIDGET_MIN_ERROR: 'Nombre minimal de widgets requis',

  // Confirmations
  CONFIRM_RESET: 'Êtes-vous sûr de vouloir réinitialiser la configuration ?',
  CONFIRM_DELETE: 'Êtes-vous sûr de vouloir supprimer ce widget ?',
} as const;

// ============================================================================
// EXPORTATION DES VALIDATEURS
// ============================================================================

export * from '../validators/dashboardValidators';

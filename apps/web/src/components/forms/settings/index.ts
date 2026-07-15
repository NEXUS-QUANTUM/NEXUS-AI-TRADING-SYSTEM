// apps/web/src/components/forms/settings/index.ts

// ============================================================================
// EXPORTS PRINCIPAUX - FORMULAIRES DE PARAMÈTRES
// ============================================================================

// --- Paramètres Généraux ---
export { default as GeneralSettingsForm } from './GeneralSettingsForm';
export type {
  GeneralSettingsFormProps,
  GeneralSettingsData,
  Language,
  Timezone,
  DateFormat,
  TimeFormat,
  WeekStart,
  Currency,
  NotificationLevel,
} from './GeneralSettingsForm';

// --- Paramètres d'Apparence ---
export { default as AppearanceSettingsForm } from './AppearanceSettingsForm';
export type {
  AppearanceSettingsFormProps,
  AppearanceSettingsData,
  ThemeMode,
  ThemeVariant,
  ColorScheme,
  FontSize,
  FontWeight,
  LayoutStyle,
  SidebarPosition,
  NavigationStyle,
  CardStyle,
  ButtonStyle,
} from './AppearanceSettingsForm';

// --- Paramètres de Sécurité ---
export { default as SecuritySettingsForm } from './SecuritySettingsForm';
export type {
  SecuritySettingsFormProps,
  SecuritySettingsData,
  TwoFactorMethod,
  SessionStatus,
  DeviceType,
  SecurityLevel,
  PasswordPolicy,
  Device,
  Session,
} from './SecuritySettingsForm';

// --- Paramètres de Notification ---
export { default as NotificationSettingsForm } from './NotificationSettingsForm';
export type {
  NotificationSettingsFormProps,
  NotificationSettingsData,
  NotificationChannel,
  NotificationPriority,
  NotificationType,
  NotificationSchedule,
  NotificationSound,
  NotificationFrequency,
  NotificationRule,
} from './NotificationSettingsForm';

// --- Paramètres de Trading ---
export { default as TradingSettingsForm } from './TradingSettingsForm';
export type {
  TradingSettingsFormProps,
  TradingSettingsData,
  TradingMode,
  OrderType,
  TimeInForce,
  TradingStrategy,
  TradingSymbol,
  TradingAlert,
} from './TradingSettingsForm';

// --- Paramètres de Gestion des Risques ---
export { default as RiskSettingsForm } from './RiskSettingsForm';
export type {
  RiskSettingsFormProps,
  RiskSettingsData,
  RiskLevel,
  StopLossType,
  TakeProfitType,
  PositionSizing,
  RiskMetric,
  DrawdownAction,
  RiskRule,
} from './RiskSettingsForm';

// --- Paramètres des Brokers ---
export { default as BrokerSettingsForm } from './BrokerSettingsForm';
export type {
  BrokerSettingsFormProps,
  BrokerSettingsFormData,
  BrokerProvider,
  BrokerStatus,
  BrokerType,
  BrokerAccountType,
  BrokerConfig,
  BrokerAccount,
} from './BrokerSettingsForm';

// --- Paramètres de Facturation ---
export { default as BillingSettingsForm } from './BillingSettingsForm';
export type {
  BillingSettingsFormProps,
  BillingSettingsData,
  BillingPlan,
  BillingPeriod,
  PaymentMethod,
  InvoiceStatus,
  BillingStatus,
  PaymentMethodConfig,
  Invoice,
  BillingAddress,
} from './BillingSettingsForm';

// --- Paramètres API ---
export { default as APISettingsForm } from './APISettingsForm';
export type {
  APISettingsFormProps,
  APISettingsFormData,
  APIProvider,
  APIStatus,
  APIAuthType,
  APIRateLimitUnit,
  APIEndpoint,
  APIConfig,
} from './APISettingsForm';

// ============================================================================
// EXPORTS DE TYPE - TYPES GÉNÉRIQUES
// ============================================================================

export type SettingsFormName = 
  | 'General'
  | 'Appearance'
  | 'Security'
  | 'Notification'
  | 'Trading'
  | 'Risk'
  | 'Broker'
  | 'Billing'
  | 'API';

export type SettingsFormPropsMap = {
  General: GeneralSettingsFormProps;
  Appearance: AppearanceSettingsFormProps;
  Security: SecuritySettingsFormProps;
  Notification: NotificationSettingsFormProps;
  Trading: TradingSettingsFormProps;
  Risk: RiskSettingsFormProps;
  Broker: BrokerSettingsFormProps;
  Billing: BillingSettingsFormProps;
  API: APISettingsFormProps;
};

export type SettingsFormDataMap = {
  General: GeneralSettingsData;
  Appearance: AppearanceSettingsData;
  Security: SecuritySettingsData;
  Notification: NotificationSettingsData;
  Trading: TradingSettingsData;
  Risk: RiskSettingsData;
  Broker: BrokerSettingsFormData;
  Billing: BillingSettingsData;
  API: APISettingsFormData;
};

/**
 * Type générique pour obtenir les props d'un formulaire de paramètres spécifique
 */
export type SettingsFormProps<T extends SettingsFormName> = SettingsFormPropsMap[T];

/**
 * Type générique pour obtenir les données d'un formulaire de paramètres spécifique
 */
export type SettingsFormData<T extends SettingsFormName> = SettingsFormDataMap[T];

// ============================================================================
// CONSTANTES - CONFIGURATIONS PAR DÉFAUT
// ============================================================================

export const DEFAULT_SETTINGS = {
  general: {
    language: 'fr' as Language,
    timezone: 'Europe/Paris' as Timezone,
    dateFormat: 'DD/MM/YYYY' as DateFormat,
    timeFormat: '24h' as TimeFormat,
    weekStart: 'monday' as WeekStart,
    currency: 'EUR' as Currency,
    notificationLevel: 'all' as NotificationLevel,
    emailNotifications: true,
    pushNotifications: true,
    smsNotifications: false,
    autoDarkMode: true,
    animations: true,
    keyboardShortcuts: true,
    offlineMode: false,
    dataCompression: true,
    debugMode: false,
    analytics: true,
    cookies: true,
    autoUpdates: true,
  },
  appearance: {
    theme: {
      mode: 'system' as ThemeMode,
      variant: 'default' as ThemeVariant,
      colorScheme: 'blue' as ColorScheme,
      fontFamily: 'Inter, sans-serif',
      fontSize: 'medium' as FontSize,
      fontWeight: 'normal' as FontWeight,
      borderRadius: 8,
      backgroundOpacity: 100,
    },
    layout: {
      style: 'comfortable' as LayoutStyle,
      sidebar: 'left' as SidebarPosition,
      navigation: 'top' as NavigationStyle,
      cardStyle: 'default' as CardStyle,
      buttonStyle: 'default' as ButtonStyle,
      showShadows: true,
      showAnimations: true,
      showBorders: true,
      showSeparators: true,
      showIcons: true,
      showLabels: true,
      showBadges: true,
      showTooltips: true,
    },
  },
  security: {
    passwordPolicy: 'standard' as PasswordPolicy,
    twoFactor: {
      method: 'authenticator' as TwoFactorMethod,
      enabled: false,
      verified: false,
    },
    settings: {
      sessionTimeout: 60,
      singleSession: false,
      ipVerification: true,
      locationVerification: false,
      newDeviceNotification: true,
      autoLock: true,
      autoLockDelay: 15,
      autoCleanup: true,
      autoCleanupDelay: 30,
      allowedIPs: [],
      blockedIPs: [],
    },
  },
  notification: {
    channels: {
      email: true,
      push: true,
      sms: false,
      webhook: false,
      slack: false,
      telegram: false,
      discord: false,
    },
    preferences: {
      frequency: 'realtime' as NotificationFrequency,
      quietHoursEnabled: false,
      quietHoursMute: true,
      groupNotifications: true,
      groupDelay: 5000,
    },
    rules: [],
  },
  trading: {
    mode: 'semi_automatic' as TradingMode,
    defaultOrderType: 'limit' as OrderType,
    defaultTimeInForce: 'GTC' as TimeInForce,
    defaultStrategy: 'swing' as TradingStrategy,
    defaultPositionSize: 1,
    maxLeverage: 10,
    slippageTolerance: 0.5,
    maxSpread: 0.2,
    activeSymbols: [],
    alerts: [],
    preferences: {
      confirmOrders: true,
      showNotifications: true,
      notificationSound: 'default' as const,
      autoAdjustPositions: false,
      useTrailingStop: false,
      trailingStopDistance: 2,
      autoTradingEnabled: false,
      paperTradingEnabled: true,
      paperTradingCapital: 10000,
      tradingLogsEnabled: true,
      technicalAnalysisEnabled: true,
      backtestingEnabled: true,
      analysisBars: 100,
      analysisPeriod: '1h' as const,
    },
  },
  risk: {
    level: 'moderate' as RiskLevel,
    stopLoss: {
      type: 'percentage' as StopLossType,
      value: 2,
      unit: 'percent',
    },
    takeProfit: {
      type: 'risk_reward' as TakeProfitType,
      value: 2,
      riskRewardRatio: 2,
    },
    positionSizing: {
      type: 'risk_based' as PositionSizing,
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
      action: 'alert' as DrawdownAction,
    },
    metrics: {
      metrics: ['sharpe' as RiskMetric, 'max_drawdown' as RiskMetric],
      thresholds: {
        sharpe: 1,
        max_drawdown: 20,
      },
    },
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
    rules: [],
  },
  broker: {
    preferences: {
      autoReconnect: true,
      retryOnFailure: true,
      logRequests: true,
      cacheResponses: true,
      cacheDuration: 300000,
      websocketEnabled: true,
      websocketAutoReconnect: true,
    },
    brokers: [],
  },
  billing: {
    plan: 'free' as BillingPlan,
    period: 'monthly' as BillingPeriod,
    status: 'active' as BillingStatus,
    defaultCurrency: 'EUR',
    autoRenew: true,
    billingEmailsEnabled: true,
    testMode: false,
    paymentMethods: [],
    invoices: [],
    billingAddress: {
      line1: '',
      city: '',
      postalCode: '',
      country: 'FR',
    },
  },
  api: {
    config: {
      provider: 'nexus' as APIProvider,
      name: 'API Nexus',
      baseUrl: 'https://api.nexus.com/v1',
      authType: 'api_key' as APIAuthType,
      rateLimit: {
        requests: 100,
        period: 1,
        unit: 'minute' as APIRateLimitUnit,
      },
      enabled: true,
      timeout: 30000,
      retries: 3,
      loggingEnabled: true,
      cacheEnabled: true,
      cacheDuration: 300000,
      endpoints: [],
    },
  },
} as const;

// ============================================================================
// UTILITAIRES - CRÉATEURS DE PARAMÈTRES
// ============================================================================

import { GeneralSettingsForm } from './GeneralSettingsForm';
import { AppearanceSettingsForm } from './AppearanceSettingsForm';
import { SecuritySettingsForm } from './SecuritySettingsForm';
import { NotificationSettingsForm } from './NotificationSettingsForm';
import { TradingSettingsForm } from './TradingSettingsForm';
import { RiskSettingsForm } from './RiskSettingsForm';
import { BrokerSettingsForm } from './BrokerSettingsForm';
import { BillingSettingsForm } from './BillingSettingsForm';
import { APISettingsForm } from './APISettingsForm';

/**
 * Créer un formulaire de paramètres général personnalisé
 */
export const createGeneralSettings = <T extends GeneralSettingsFormProps>(
  defaultProps?: Partial<T>
) => {
  return (props: T) => {
    return <GeneralSettingsForm {...defaultProps} {...props} />;
  };
};

/**
 * Créer un formulaire de paramètres d'apparence personnalisé
 */
export const createAppearanceSettings = <T extends AppearanceSettingsFormProps>(
  defaultProps?: Partial<T>
) => {
  return (props: T) => {
    return <AppearanceSettingsForm {...defaultProps} {...props} />;
  };
};

/**
 * Créer un formulaire de paramètres de sécurité personnalisé
 */
export const createSecuritySettings = <T extends SecuritySettingsFormProps>(
  defaultProps?: Partial<T>
) => {
  return (props: T) => {
    return <SecuritySettingsForm {...defaultProps} {...props} />;
  };
};

/**
 * Créer un formulaire de paramètres de notification personnalisé
 */
export const createNotificationSettings = <T extends NotificationSettingsFormProps>(
  defaultProps?: Partial<T>
) => {
  return (props: T) => {
    return <NotificationSettingsForm {...defaultProps} {...props} />;
  };
};

/**
 * Créer un formulaire de paramètres de trading personnalisé
 */
export const createTradingSettings = <T extends TradingSettingsFormProps>(
  defaultProps?: Partial<T>
) => {
  return (props: T) => {
    return <TradingSettingsForm {...defaultProps} {...props} />;
  };
};

/**
 * Créer un formulaire de paramètres de risque personnalisé
 */
export const createRiskSettings = <T extends RiskSettingsFormProps>(
  defaultProps?: Partial<T>
) => {
  return (props: T) => {
    return <RiskSettingsForm {...defaultProps} {...props} />;
  };
};

/**
 * Créer un formulaire de paramètres de broker personnalisé
 */
export const createBrokerSettings = <T extends BrokerSettingsFormProps>(
  defaultProps?: Partial<T>
) => {
  return (props: T) => {
    return <BrokerSettingsForm {...defaultProps} {...props} />;
  };
};

/**
 * Créer un formulaire de paramètres de facturation personnalisé
 */
export const createBillingSettings = <T extends BillingSettingsFormProps>(
  defaultProps?: Partial<T>
) => {
  return (props: T) => {
    return <BillingSettingsForm {...defaultProps} {...props} />;
  };
};

/**
 * Créer un formulaire de paramètres API personnalisé
 */
export const createAPISettings = <T extends APISettingsFormProps>(
  defaultProps?: Partial<T>
) => {
  return (props: T) => {
    return <APISettingsForm {...defaultProps} {...props} />;
  };
};

// ============================================================================
// UTILITAIRES - COMBINAISON DE PARAMÈTRES
// ============================================================================

export const SETTINGS_SECTIONS = [
  { id: 'general', label: 'Général', icon: '⚙️', component: GeneralSettingsForm },
  { id: 'appearance', label: 'Apparence', icon: '🎨', component: AppearanceSettingsForm },
  { id: 'security', label: 'Sécurité', icon: '🔒', component: SecuritySettingsForm },
  { id: 'notification', label: 'Notifications', icon: '🔔', component: NotificationSettingsForm },
  { id: 'trading', label: 'Trading', icon: '📈', component: TradingSettingsForm },
  { id: 'risk', label: 'Risques', icon: '🛡️', component: RiskSettingsForm },
  { id: 'broker', label: 'Brokers', icon: '🔌', component: BrokerSettingsForm },
  { id: 'billing', label: 'Facturation', icon: '💳', component: BillingSettingsForm },
  { id: 'api', label: 'API', icon: '🔗', component: APISettingsForm },
] as const;

export type SettingsSectionId = typeof SETTINGS_SECTIONS[number]['id'];

export const getSettingsSection = (id: SettingsSectionId) => {
  return SETTINGS_SECTIONS.find(section => section.id === id);
};

export const getSettingsComponent = (id: SettingsSectionId) => {
  const section = getSettingsSection(id);
  return section?.component;
};

export const getSettingsLabel = (id: SettingsSectionId) => {
  const section = getSettingsSection(id);
  return section?.label;
};

// ============================================================================
// UTILITAIRES - VALIDATION
// ============================================================================

export const validateSettings = <T extends SettingsFormName>(
  section: T,
  data: SettingsFormData<T>
): { valid: boolean; errors: Record<string, string> } => {
  const errors: Record<string, string> = {};

  switch (section) {
    case 'General':
      if (!(data as GeneralSettingsData).username) {
        errors.username = 'Le nom d\'utilisateur est requis';
      }
      if (!(data as GeneralSettingsData).email) {
        errors.email = 'L\'email est requis';
      }
      break;
    case 'Security':
      if ((data as SecuritySettingsData).newPassword) {
        const pwd = (data as SecuritySettingsData).newPassword;
        if (pwd.length < 8) {
          errors.newPassword = 'Le mot de passe doit contenir au moins 8 caractères';
        }
        if (pwd !== (data as SecuritySettingsData).confirmPassword) {
          errors.confirmPassword = 'Les mots de passe ne correspondent pas';
        }
      }
      break;
    case 'Trading':
      if ((data as TradingSettingsData).defaultPositionSize <= 0) {
        errors.defaultPositionSize = 'La taille de position doit être positive';
      }
      if ((data as TradingSettingsData).maxLeverage < 1 || (data as TradingSettingsData).maxLeverage > 100) {
        errors.maxLeverage = 'Le levier doit être entre 1 et 100';
      }
      break;
    case 'Risk':
      if ((data as RiskSettingsData).stopLoss.value <= 0) {
        errors.stopLoss = 'Le stop-loss doit être supérieur à 0';
      }
      if ((data as RiskSettingsData).takeProfit.value <= 0) {
        errors.takeProfit = 'Le take-profit doit être supérieur à 0';
      }
      break;
    case 'Billing':
      if (!(data as BillingSettingsData).billingEmail) {
        errors.billingEmail = 'L\'email de facturation est requis';
      }
      if (!(data as BillingSettingsData).billingAddress.line1) {
        errors.billingAddressLine1 = 'L\'adresse est requise';
      }
      break;
    case 'API':
      if (!(data as APISettingsFormData).config.name) {
        errors.name = 'Le nom de l\'API est requis';
      }
      if (!(data as APISettingsFormData).config.baseUrl) {
        errors.baseUrl = 'L\'URL de base est requise';
      }
      break;
    default:
      break;
  }

  return { valid: Object.keys(errors).length === 0, errors };
};

// ============================================================================
// UTILITAIRES - PERSISTANCE
// ============================================================================

export const saveSettings = <T extends SettingsFormName>(
  section: T,
  data: SettingsFormData<T>
): void => {
  if (typeof window === 'undefined') return;
  try {
    localStorage.setItem(`nexus_settings_${section}`, JSON.stringify(data));
  } catch (error) {
    console.error(`Erreur de sauvegarde des paramètres ${section}:`, error);
  }
};

export const loadSettings = <T extends SettingsFormName>(
  section: T
): SettingsFormData<T> | null => {
  if (typeof window === 'undefined') return null;
  try {
    const data = localStorage.getItem(`nexus_settings_${section}`);
    return data ? JSON.parse(data) : null;
  } catch (error) {
    console.error(`Erreur de chargement des paramètres ${section}:`, error);
    return null;
  }
};

export const clearSettings = (section?: SettingsFormName): void => {
  if (typeof window === 'undefined') return;
  try {
    if (section) {
      localStorage.removeItem(`nexus_settings_${section}`);
    } else {
      SETTINGS_SECTIONS.forEach(s => {
        localStorage.removeItem(`nexus_settings_${s.id}`);
      });
    }
  } catch (error) {
    console.error('Erreur de suppression des paramètres:', error);
  }
};

// ============================================================================
// EXPORTATION PAR DÉFAUT - TOUS LES PARAMÈTRES
// ============================================================================

/**
 * Exportation groupée de tous les formulaires de paramètres
 */
const SettingsForms = {
  General: GeneralSettingsForm,
  Appearance: AppearanceSettingsForm,
  Security: SecuritySettingsForm,
  Notification: NotificationSettingsForm,
  Trading: TradingSettingsForm,
  Risk: RiskSettingsForm,
  Broker: BrokerSettingsForm,
  Billing: BillingSettingsForm,
  API: APISettingsForm,
  // Utilitaires
  getSection: getSettingsSection,
  getComponent: getSettingsComponent,
  getLabel: getSettingsLabel,
  validate: validateSettings,
  save: saveSettings,
  load: loadSettings,
  clear: clearSettings,
};

export default SettingsForms;

// ============================================================================
// EXPORTATION DES VALIDATEURS
// ============================================================================

export * from '../validators/settingsValidators';

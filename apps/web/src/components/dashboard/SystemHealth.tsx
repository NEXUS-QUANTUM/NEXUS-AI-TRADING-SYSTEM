// apps/web/src/components/dashboard/SystemHealth.tsx
'use client';

import React, {
  useState,
  useEffect,
  useCallback,
  useMemo,
  forwardRef,
  Ref,
  useRef,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ClockIcon,
  ArrowPathIcon,
  CpuChipIcon,
  ServerIcon,
  DatabaseIcon,
  WifiIcon,
  CloudIcon,
  ShieldCheckIcon,
  BoltIcon,
  SignalIcon,
  CircleStackIcon,
  DocumentTextIcon,
  Square3Stack3DIcon,
  ChartBarIcon,
  UserGroupIcon,
  GlobeAltIcon,
  LinkIcon,
  LockClosedIcon,
  EyeIcon,
  EyeSlashIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ChevronRightIcon,
  ChevronLeftIcon,
  ArrowsUpDownIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  EllipsisHorizontalIcon,
  PlusIcon,
  MinusIcon,
  RefreshIcon,
  PlayIcon,
  PauseIcon,
  StopIcon,
  TrashIcon,
  PencilIcon,
  DuplicateIcon,
  ShareIcon,
  BookmarkIcon,
  HeartIcon,
  StarIcon,
  FlagIcon,
  DocumentArrowDownIcon,
  DocumentDuplicateIcon,
  PrinterIcon,
  EnvelopeIcon,
  BellIcon,
  BellSlashIcon,
} from '@heroicons/react/24/outline';
import {
  CheckCircleIcon as CheckCircleSolid,
  XCircleIcon as XCircleSolid,
  ExclamationTriangleIcon as ExclamationTriangleSolid,
  InformationCircleIcon as InformationCircleSolid,
} from '@heroicons/react/24/solid';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Progress } from '@/components/common/Progress';
import { Separator } from '@/components/common/Separator';
import { Skeleton } from '@/components/common/Skeleton';
import { Tooltip } from '@/components/common/Tooltip';
import { ScrollArea } from '@/components/common/ScrollArea';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type SystemHealthStatus = 'healthy' | 'warning' | 'critical' | 'unknown' | 'offline';

export type SystemComponentType = 
  | 'api'
  | 'database'
  | 'cache'
  | 'queue'
  | 'websocket'
  | 'broker'
  | 'ai'
  | 'trading'
  | 'risk'
  | 'monitoring'
  | 'auth'
  | 'payment'
  | 'storage'
  | 'network'
  | 'security';

export interface SystemMetric {
  /** Nom de la métrique */
  name: string;
  /** Valeur */
  value: number;
  /** Unité */
  unit?: string;
  /** Seuil d'alerte */
  threshold?: number;
  /** Statut */
  status?: SystemHealthStatus;
  /** Tendance */
  trend?: 'up' | 'down' | 'stable';
  /** Historique */
  history?: number[];
  /** Description */
  description?: string;
}

export interface SystemComponent {
  /** Identifiant */
  id: string;
  /** Nom */
  name: string;
  /** Type */
  type: SystemComponentType;
  /** Statut */
  status: SystemHealthStatus;
  /** Message */
  message?: string;
  /** Métriques */
  metrics?: SystemMetric[];
  /** Sous-composants */
  children?: SystemComponent[];
  /** Dernière vérification */
  lastCheck?: Date;
  /** Temps de réponse (ms) */
  responseTime?: number;
  /** Disponibilité (%) */
  availability?: number;
  /** Version */
  version?: string;
  /** Uptime */
  uptime?: number;
  /** Dernière erreur */
  lastError?: string;
  /** Erreurs par minute */
  errorsPerMinute?: number;
  /** Requêtes par minute */
  requestsPerMinute?: number;
  /** Actions disponibles */
  actions?: SystemAction[];
}

export interface SystemAction {
  /** Identifiant */
  id: string;
  /** Libellé */
  label: string;
  /** Icône */
  icon?: React.ReactNode;
  /** Callback */
  onClick: () => void;
  /** Variante */
  variant?: 'primary' | 'success' | 'danger' | 'warning' | 'ghost';
}

export interface SystemAlert {
  /** Identifiant */
  id: string;
  /** Niveau */
  level: 'info' | 'warning' | 'error' | 'critical';
  /** Message */
  message: string;
  /** Composant concerné */
  componentId?: string;
  /** Date */
  date: Date;
  /** Lu */
  read: boolean;
  /** Actions disponibles */
  actions?: SystemAction[];
}

export interface SystemHealthProps {
  // --- Données ---
  /** Composants du système */
  components?: SystemComponent[];
  /** Alertes */
  alerts?: SystemAlert[];
  /** Métriques globales */
  metrics?: SystemMetric[];
  /** Chargement en cours */
  isLoading?: boolean;
  /** Erreur */
  error?: string | null;

  // --- Apparence ---
  /** Titre */
  title?: string;
  /** Sous-titre */
  subtitle?: string;
  /** Classes additionnelles */
  className?: string;
  /** Afficher le header */
  showHeader?: boolean;
  /** Afficher les métriques */
  showMetrics?: boolean;
  /** Afficher les alertes */
  showAlerts?: boolean;
  /** Afficher les composants */
  showComponents?: boolean;
  /** Nombre maximal d'alertes */
  maxAlerts?: number;
  /** Niveau minimal d'alerte */
  minAlertLevel?: 'info' | 'warning' | 'error' | 'critical';

  // --- Actions ---
  /** Callback pour rafraîchir */
  onRefresh?: () => void;
  /** Callback pour une action */
  onAction?: (componentId: string, actionId: string) => void;
  /** Callback pour une alerte */
  onAlertClick?: (alert: SystemAlert) => void;
  /** Callback pour marquer comme lu */
  onAlertRead?: (alertId: string) => void;
  /** Callback pour effacer une alerte */
  onAlertDismiss?: (alertId: string) => void;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ID */
  id?: string;

  // --- Avancé ---
  /** Intervalle de rafraîchissement (ms) */
  refreshInterval?: number;
  /** Désactiver le rafraîchissement automatique */
  disableAutoRefresh?: boolean;
  /** Formater le temps */
  formatTime?: (date: Date) => string;
  /** Formater la durée */
  formatDuration?: (seconds: number) => string;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const STATUS_CONFIG: Record<SystemHealthStatus, { label: string; color: string; icon: React.ReactNode }> = {
  healthy: {
    label: 'Sain',
    color: 'bg-green-500 text-white dark:bg-green-400 dark:text-green-950',
    icon: <CheckCircleIcon className="h-4 w-4" />,
  },
  warning: {
    label: 'Avertissement',
    color: 'bg-yellow-500 text-white dark:bg-yellow-400 dark:text-yellow-950',
    icon: <ExclamationTriangleIcon className="h-4 w-4" />,
  },
  critical: {
    label: 'Critique',
    color: 'bg-red-500 text-white dark:bg-red-400 dark:text-red-950',
    icon: <XCircleIcon className="h-4 w-4" />,
  },
  unknown: {
    label: 'Inconnu',
    color: 'bg-gray-500 text-white dark:bg-gray-400 dark:text-gray-950',
    icon: <InformationCircleIcon className="h-4 w-4" />,
  },
  offline: {
    label: 'Hors ligne',
    color: 'bg-gray-700 text-white dark:bg-gray-600 dark:text-gray-300',
    icon: <XCircleIcon className="h-4 w-4" />,
  },
};

const COMPONENT_ICONS: Record<SystemComponentType, React.ReactNode> = {
  api: <ServerIcon className="h-5 w-5" />,
  database: <DatabaseIcon className="h-5 w-5" />,
  cache: <CircleStackIcon className="h-5 w-5" />,
  queue: <Square3Stack3DIcon className="h-5 w-5" />,
  websocket: <WifiIcon className="h-5 w-5" />,
  broker: <LinkIcon className="h-5 w-5" />,
  ai: <CpuChipIcon className="h-5 w-5" />,
  trading: <ChartBarIcon className="h-5 w-5" />,
  risk: <ShieldCheckIcon className="h-5 w-5" />,
  monitoring: <SignalIcon className="h-5 w-5" />,
  auth: <LockClosedIcon className="h-5 w-5" />,
  payment: <CreditCardIcon className="h-5 w-5" />,
  storage: <CircleStackIcon className="h-5 w-5" />,
  network: <GlobeAltIcon className="h-5 w-5" />,
  security: <ShieldCheckIcon className="h-5 w-5" />,
};

const COMPONENT_LABELS: Record<SystemComponentType, string> = {
  api: 'API',
  database: 'Base de données',
  cache: 'Cache',
  queue: 'File d\'attente',
  websocket: 'WebSocket',
  broker: 'Broker',
  ai: 'IA',
  trading: 'Trading',
  risk: 'Gestion des risques',
  monitoring: 'Monitoring',
  auth: 'Authentification',
  payment: 'Paiements',
  storage: 'Stockage',
  network: 'Réseau',
  security: 'Sécurité',
};

const ALERT_LEVEL_CONFIG: Record<SystemAlert['level'], { color: string; icon: React.ReactNode }> = {
  info: {
    color: 'text-blue-600 dark:text-blue-400',
    icon: <InformationCircleIcon className="h-4 w-4" />,
  },
  warning: {
    color: 'text-yellow-600 dark:text-yellow-400',
    icon: <ExclamationTriangleIcon className="h-4 w-4" />,
  },
  error: {
    color: 'text-red-600 dark:text-red-400',
    icon: <XCircleIcon className="h-4 w-4" />,
  },
  critical: {
    color: 'text-red-700 dark:text-red-500',
    icon: <ExclamationTriangleIcon className="h-4 w-4" />,
  },
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const SystemHealth = forwardRef<HTMLDivElement, SystemHealthProps>(
  (props, ref) => {
    const {
      // Données
      components: externalComponents = [],
      alerts: externalAlerts = [],
      metrics: externalMetrics = [],
      isLoading: externalLoading = false,
      error: externalError = null,

      // Apparence
      title = 'Santé du Système',
      subtitle = 'État des services et métriques en temps réel',
      className,
      showHeader = true,
      showMetrics = true,
      showAlerts = true,
      showComponents = true,
      maxAlerts = 5,
      minAlertLevel = 'warning',

      // Actions
      onRefresh,
      onAction,
      onAlertClick,
      onAlertRead,
      onAlertDismiss,

      // Accessibilité
      ariaLabel = 'Santé du système',
      id,

      // Avancé
      refreshInterval = 30000,
      disableAutoRefresh = false,
      formatTime,
      formatDuration,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const containerRef = useRef<HTMLDivElement>(null);
    const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [components, setComponents] = useState<SystemComponent[]>(externalComponents);
    const [alerts, setAlerts] = useState<SystemAlert[]>(externalAlerts);
    const [metrics, setMetrics] = useState<SystemMetric[]>(externalMetrics);
    const [isLoading, setIsLoading] = useState(externalLoading);
    const [error, setError] = useState<string | null>(externalError);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [expandedComponents, setExpandedComponents] = useState<Set<string>>(new Set());
    const [selectedComponent, setSelectedComponent] = useState<string | null>(null);

    // ========================================================================
    // SYNC AVEC LES PROPS EXTERNES
    // ========================================================================

    useEffect(() => {
      setComponents(externalComponents);
    }, [externalComponents]);

    useEffect(() => {
      setAlerts(externalAlerts);
    }, [externalAlerts]);

    useEffect(() => {
      setMetrics(externalMetrics);
    }, [externalMetrics]);

    useEffect(() => {
      setIsLoading(externalLoading);
    }, [externalLoading]);

    useEffect(() => {
      setError(externalError);
    }, [externalError]);

    // ========================================================================
    // CALCUL DES STATUTS GLOBAUX
    // ========================================================================

    const overallStatus = useMemo((): SystemHealthStatus => {
      if (components.length === 0) return 'unknown';

      const hasCritical = components.some((c) => c.status === 'critical');
      if (hasCritical) return 'critical';

      const hasWarning = components.some((c) => c.status === 'warning');
      if (hasWarning) return 'warning';

      const hasOffline = components.some((c) => c.status === 'offline');
      if (hasOffline) return 'offline';

      const allHealthy = components.every((c) => c.status === 'healthy');
      if (allHealthy) return 'healthy';

      return 'unknown';
    }, [components]);

    const unreadAlerts = useMemo(() => {
      return alerts.filter((a) => !a.read);
    }, [alerts]);

    const criticalAlerts = useMemo(() => {
      return alerts.filter((a) => a.level === 'critical' || a.level === 'error');
    }, [alerts]);

    // ========================================================================
    // STATISTIQUES
    // ========================================================================

    const stats = useMemo(() => {
      const total = components.length;
      const healthy = components.filter((c) => c.status === 'healthy').length;
      const warning = components.filter((c) => c.status === 'warning').length;
      const critical = components.filter((c) => c.status === 'critical').length;
      const offline = components.filter((c) => c.status === 'offline').length;
      const unknown = components.filter((c) => c.status === 'unknown').length;

      const avgResponseTime = components
        .filter((c) => c.responseTime !== undefined)
        .reduce((acc, c) => acc + (c.responseTime || 0), 0) / components.length || 0;

      const avgAvailability = components
        .filter((c) => c.availability !== undefined)
        .reduce((acc, c) => acc + (c.availability || 0), 0) / components.length || 0;

      return {
        total,
        healthy,
        warning,
        critical,
        offline,
        unknown,
        avgResponseTime,
        avgAvailability,
        uptime: components.reduce((acc, c) => acc + (c.uptime || 0), 0),
        errorsPerMinute: components.reduce((acc, c) => acc + (c.errorsPerMinute || 0), 0),
        requestsPerMinute: components.reduce((acc, c) => acc + (c.requestsPerMinute || 0), 0),
      };
    }, [components]);

    // ========================================================================
    // FILTRAGE DES ALERTES
    // ========================================================================

    const filteredAlerts = useMemo(() => {
      const levels: SystemAlert['level'][] = [];
      if (minAlertLevel === 'info') {
        levels.push('info', 'warning', 'error', 'critical');
      } else if (minAlertLevel === 'warning') {
        levels.push('warning', 'error', 'critical');
      } else if (minAlertLevel === 'error') {
        levels.push('error', 'critical');
      } else {
        levels.push('critical');
      }

      return alerts
        .filter((a) => levels.includes(a.level))
        .slice(0, maxAlerts);
    }, [alerts, minAlertLevel, maxAlerts]);

    // ========================================================================
    // RAFRAÎCHISSEMENT
    // ========================================================================

    const handleRefresh = useCallback(async () => {
      if (isRefreshing) return;

      setIsRefreshing(true);
      if (onRefresh) {
        await onRefresh();
      }
      setIsRefreshing(false);
    }, [onRefresh, isRefreshing]);

    // ========================================================================
    // AUTO-REFRESH
    // ========================================================================

    useEffect(() => {
      if (disableAutoRefresh) return;

      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
      }

      refreshTimerRef.current = setInterval(() => {
        handleRefresh();
      }, refreshInterval);

      return () => {
        if (refreshTimerRef.current) {
          clearInterval(refreshTimerRef.current);
        }
      };
    }, [refreshInterval, disableAutoRefresh, handleRefresh]);

    // ========================================================================
    // GESTION DES COMPOSANTS
    // ========================================================================

    const toggleComponent = useCallback((componentId: string) => {
      setExpandedComponents((prev) => {
        const next = new Set(prev);
        if (next.has(componentId)) {
          next.delete(componentId);
        } else {
          next.add(componentId);
        }
        return next;
      });
    }, []);

    const handleComponentAction = useCallback((componentId: string, actionId: string) => {
      if (onAction) {
        onAction(componentId, actionId);
      }
    }, [onAction]);

    // ========================================================================
    // GESTION DES ALERTES
    // ========================================================================

    const handleAlertRead = useCallback((alertId: string) => {
      if (onAlertRead) {
        onAlertRead(alertId);
      } else {
        setAlerts((prev) =>
          prev.map((a) =>
            a.id === alertId ? { ...a, read: true } : a
          )
        );
      }
    }, [onAlertRead]);

    const handleAlertDismiss = useCallback((alertId: string) => {
      if (onAlertDismiss) {
        onAlertDismiss(alertId);
      } else {
        setAlerts((prev) => prev.filter((a) => a.id !== alertId));
      }
    }, [onAlertDismiss]);

    // ========================================================================
    // FORMATAGE
    // ========================================================================

    const defaultFormatTime = useCallback((date: Date): string => {
      return new Intl.DateTimeFormat('fr-FR', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
      }).format(date);
    }, []);

    const defaultFormatDuration = useCallback((seconds: number): string => {
      if (seconds < 60) return `${Math.round(seconds)}s`;
      if (seconds < 3600) return `${Math.floor(seconds / 60)}m ${Math.round(seconds % 60)}s`;
      if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`;
      return `${Math.floor(seconds / 86400)}j ${Math.floor((seconds % 86400) / 3600)}h`;
    }, []);

    const formatTimeFn = formatTime || defaultFormatTime;
    const formatDurationFn = formatDuration || defaultFormatDuration;

    // ========================================================================
    // RENDU
    // ========================================================================

    // --- Rendu du statut ---
    const renderStatus = useCallback((status: SystemHealthStatus, size: 'sm' | 'md' | 'lg' = 'md') => {
      const config = STATUS_CONFIG[status] || STATUS_CONFIG.unknown;
      const sizeClasses = {
        sm: 'text-xs px-2 py-0.5 gap-1',
        md: 'text-sm px-3 py-1 gap-1.5',
        lg: 'text-base px-4 py-2 gap-2',
      };

      return (
        <Badge
          className={cn(
            'flex items-center font-medium border-0',
            config.color,
            sizeClasses[size]
          )}
        >
          {config.icon}
          {config.label}
        </Badge>
      );
    }, []);

    // --- Rendu des métriques ---
    const renderMetrics = useCallback(() => {
      if (!showMetrics || metrics.length === 0) return null;

      return (
        <div className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-3 lg:grid-cols-4">
          {metrics.map((metric) => (
            <div
              key={metric.name}
              className="rounded-lg border border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50 p-3"
            >
              <div className="flex items-center justify-between">
                <span className="text-xs text-gray-500 dark:text-gray-400">
                  {metric.name}
                </span>
                {metric.status && (
                  <span className="flex-shrink-0">
                    {STATUS_CONFIG[metric.status]?.icon}
                  </span>
                )}
              </div>
              <div className="mt-1 flex items-end gap-1">
                <span className="text-lg font-semibold">
                  {metric.value}
                </span>
                {metric.unit && (
                  <span className="text-xs text-gray-500 dark:text-gray-400">
                    {metric.unit}
                  </span>
                )}
              </div>
              {metric.trend && (
                <div className="mt-1 flex items-center gap-1 text-xs">
                  {metric.trend === 'up' && (
                    <ArrowUpIcon className="h-3 w-3 text-green-500" />
                  )}
                  {metric.trend === 'down' && (
                    <ArrowDownIcon className="h-3 w-3 text-red-500" />
                  )}
                  {metric.trend === 'stable' && (
                    <MinusIcon className="h-3 w-3 text-gray-400" />
                  )}
                  <span className={cn(
                    metric.trend === 'up' && 'text-green-600 dark:text-green-400',
                    metric.trend === 'down' && 'text-red-600 dark:text-red-400',
                    metric.trend === 'stable' && 'text-gray-500 dark:text-gray-400'
                  )}>
                    {metric.trend === 'up' ? 'Hausse' :
                     metric.trend === 'down' ? 'Baisse' : 'Stable'}
                  </span>
                </div>
              )}
              {metric.description && (
                <p className="mt-1 text-xs text-gray-400 dark:text-gray-500">
                  {metric.description}
                </p>
              )}
            </div>
          ))}
        </div>
      );
    }, [showMetrics, metrics]);

    // --- Rendu des alertes ---
    const renderAlerts = useCallback(() => {
      if (!showAlerts || filteredAlerts.length === 0) return null;

      return (
        <div className="p-4 border-t border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Alertes
              {unreadAlerts.length > 0 && (
                <Badge variant="danger" size="sm" className="ml-2">
                  {unreadAlerts.length}
                </Badge>
              )}
            </h4>
            {alerts.length > maxAlerts && (
              <Button variant="ghost" size="sm">
                Voir toutes
              </Button>
            )}
          </div>

          <div className="space-y-2">
            {filteredAlerts.map((alert) => {
              const config = ALERT_LEVEL_CONFIG[alert.level] || ALERT_LEVEL_CONFIG.info;
              const component = components.find((c) => c.id === alert.componentId);

              return (
                <div
                  key={alert.id}
                  className={cn(
                    'flex items-start gap-3 rounded-lg p-3 transition-colors cursor-pointer',
                    alert.read
                      ? 'bg-gray-50 dark:bg-gray-800/30'
                      : 'bg-blue-50 dark:bg-blue-900/20',
                    'hover:bg-gray-100 dark:hover:bg-gray-800/50'
                  )}
                  onClick={() => {
                    if (!alert.read) handleAlertRead(alert.id);
                    if (onAlertClick) onAlertClick(alert);
                  }}
                >
                  <div className={cn('flex-shrink-0 mt-0.5', config.color)}>
                    {config.icon}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-gray-900 dark:text-white">
                        {alert.message}
                      </span>
                      {!alert.read && (
                        <span className="inline-block h-1.5 w-1.5 rounded-full bg-blue-500" />
                      )}
                    </div>
                    <div className="mt-0.5 flex items-center gap-2 text-xs text-gray-500 dark:text-gray-400">
                      <span>{formatTimeFn(alert.date)}</span>
                      {component && (
                        <>
                          <span>•</span>
                          <span>{component.name}</span>
                        </>
                      )}
                    </div>
                  </div>
                  <div className="flex-shrink-0">
                    <Button
                      variant="ghost"
                      size="xs"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleAlertDismiss(alert.id);
                      }}
                    >
                      <XMarkIcon className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      );
    }, [
      showAlerts,
      filteredAlerts,
      unreadAlerts,
      alerts,
      maxAlerts,
      components,
      formatTimeFn,
      handleAlertRead,
      handleAlertDismiss,
      onAlertClick,
    ]);

    // --- Rendu des composants ---
    const renderComponents = useCallback(() => {
      if (!showComponents || components.length === 0) return null;

      return (
        <div className="p-4 border-t border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between mb-3">
            <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Composants
              <Badge variant="outline" size="sm" className="ml-2">
                {stats.total}
              </Badge>
            </h4>
          </div>

          <div className="space-y-2">
            {components.map((component) => {
              const isExpanded = expandedComponents.has(component.id);
              const Icon = COMPONENT_ICONS[component.type] || <ServerIcon className="h-5 w-5" />;
              const typeLabel = COMPONENT_LABELS[component.type] || component.type;

              return (
                <div
                  key={component.id}
                  className={cn(
                    'rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden',
                    component.status === 'critical' && 'border-red-300 dark:border-red-700',
                    component.status === 'warning' && 'border-yellow-300 dark:border-yellow-700'
                  )}
                >
                  {/* Header du composant */}
                  <div
                    className={cn(
                      'flex items-center gap-3 p-3 cursor-pointer transition-colors',
                      'hover:bg-gray-50 dark:hover:bg-gray-800/50'
                    )}
                    onClick={() => toggleComponent(component.id)}
                  >
                    <div className="flex-shrink-0 text-gray-400">
                      {Icon}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-gray-900 dark:text-white">
                          {component.name}
                        </span>
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {typeLabel}
                        </span>
                        {component.version && (
                          <Badge variant="outline" size="xs">
                            v{component.version}
                          </Badge>
                        )}
                      </div>
                      {component.message && (
                        <p className="text-sm text-gray-500 dark:text-gray-400">
                          {component.message}
                        </p>
                      )}
                    </div>
                    <div className="flex items-center gap-2">
                      {component.responseTime !== undefined && (
                        <span className="text-xs text-gray-500 dark:text-gray-400">
                          {component.responseTime}ms
                        </span>
                      )}
                      {renderStatus(component.status, 'sm')}
                      <Button variant="ghost" size="xs">
                        {isExpanded ? (
                          <ChevronUpIcon className="h-4 w-4" />
                        ) : (
                          <ChevronDownIcon className="h-4 w-4" />
                        )}
                      </Button>
                    </div>
                  </div>

                  {/* Détails du composant */}
                  {isExpanded && (
                    <div className="border-t border-gray-200 dark:border-gray-700 p-3 space-y-3">
                      {/* Métriques du composant */}
                      {component.metrics && component.metrics.length > 0 && (
                        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
                          {component.metrics.map((metric) => (
                            <div
                              key={metric.name}
                              className="rounded bg-gray-50 dark:bg-gray-800/50 p-2"
                            >
                              <div className="text-xs text-gray-500 dark:text-gray-400">
                                {metric.name}
                              </div>
                              <div className="flex items-end gap-1">
                                <span className="font-medium">
                                  {metric.value}
                                </span>
                                {metric.unit && (
                                  <span className="text-xs text-gray-400">
                                    {metric.unit}
                                  </span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      )}

                      {/* Informations supplémentaires */}
                      <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4">
                        {component.availability !== undefined && (
                          <div>
                            <span className="text-gray-500 dark:text-gray-400">
                              Disponibilité
                            </span>
                            <div className="font-medium">
                              {component.availability}%
                            </div>
                          </div>
                        )}
                        {component.uptime !== undefined && (
                          <div>
                            <span className="text-gray-500 dark:text-gray-400">
                              Uptime
                            </span>
                            <div className="font-medium">
                              {formatDurationFn(component.uptime)}
                            </div>
                          </div>
                        )}
                        {component.errorsPerMinute !== undefined && (
                          <div>
                            <span className="text-gray-500 dark:text-gray-400">
                              Erreurs/min
                            </span>
                            <div className="font-medium">
                              {component.errorsPerMinute}
                            </div>
                          </div>
                        )}
                        {component.requestsPerMinute !== undefined && (
                          <div>
                            <span className="text-gray-500 dark:text-gray-400">
                              Requêtes/min
                            </span>
                            <div className="font-medium">
                              {component.requestsPerMinute}
                            </div>
                          </div>
                        )}
                      </div>

                      {/* Dernière erreur */}
                      {component.lastError && (
                        <div className="rounded bg-red-50 dark:bg-red-900/20 p-2 text-sm text-red-600 dark:text-red-400">
                          <span className="font-medium">Dernière erreur: </span>
                          {component.lastError}
                        </div>
                      )}

                      {/* Actions */}
                      {component.actions && component.actions.length > 0 && (
                        <div className="flex flex-wrap gap-2 pt-2 border-t border-gray-200 dark:border-gray-700">
                          {component.actions.map((action) => (
                            <Button
                              key={action.id}
                              variant={action.variant || 'ghost'}
                              size="sm"
                              onClick={() => handleComponentAction(component.id, action.id)}
                            >
                              {action.icon}
                              {action.label}
                            </Button>
                          ))}
                        </div>
                      )}

                      {/* Sous-composants */}
                      {component.children && component.children.length > 0 && (
                        <div className="pl-4 border-l-2 border-gray-200 dark:border-gray-700">
                          {component.children.map((child) => (
                            <div
                              key={child.id}
                              className="flex items-center gap-3 py-2"
                            >
                              <div className="flex-1">
                                <span className="text-sm">{child.name}</span>
                              </div>
                              {renderStatus(child.status, 'sm')}
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      );
    }, [
      showComponents,
      components,
      stats,
      expandedComponents,
      renderStatus,
      toggleComponent,
      formatDurationFn,
      handleComponentAction,
    ]);

    // --- Rendu des squelettes ---
    const renderSkeletons = useCallback(() => {
      return (
        <div className="p-4 space-y-4">
          {/* Métriques */}
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-20 w-full" />
            ))}
          </div>

          {/* Composants */}
          <div className="space-y-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        </div>
      );
    }, []);

    // --- Rendu des statistiques globales ---
    const renderStats = useCallback(() => {
      if (components.length === 0) return null;

      return (
        <div className="grid grid-cols-2 gap-2 p-4 sm:grid-cols-4">
          <div className="text-center">
            <div className="text-2xl font-bold text-green-600 dark:text-green-400">
              {stats.healthy}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Sains</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-yellow-600 dark:text-yellow-400">
              {stats.warning}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Avertissements</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-red-600 dark:text-red-400">
              {stats.critical + stats.offline}
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Critiques</div>
          </div>
          <div className="text-center">
            <div className="text-2xl font-bold text-gray-600 dark:text-gray-400">
              {stats.avgAvailability}%
            </div>
            <div className="text-xs text-gray-500 dark:text-gray-400">Disponibilité</div>
          </div>
        </div>
      );
    }, [components, stats]);

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const statusConfig = STATUS_CONFIG[overallStatus] || STATUS_CONFIG.unknown;

    return (
      <Card
        ref={ref}
        id={id}
        className={cn('overflow-hidden', className)}
        aria-label={ariaLabel}
      >
        {/* Header */}
        {showHeader && (
          <CardHeader className="flex flex-row items-center justify-between border-b border-gray-200 dark:border-gray-700">
            <div>
              <CardTitle className="flex items-center gap-2">
                {title}
                <Badge className={statusConfig.color}>
                  {statusConfig.icon}
                  {statusConfig.label}
                </Badge>
              </CardTitle>
              {subtitle && (
                <p className="text-sm text-gray-500 dark:text-gray-400">{subtitle}</p>
              )}
            </div>
            <div className="flex items-center gap-2">
              {!disableAutoRefresh && (
                <span className="text-xs text-gray-400 flex items-center gap-1">
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                  Live
                </span>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRefresh}
                disabled={isRefreshing}
              >
                <ArrowPathIcon className={cn('h-4 w-4', isRefreshing && 'animate-spin')} />
              </Button>
            </div>
          </CardHeader>
        )}

        {/* Contenu */}
        {error ? (
          <div className="flex flex-col items-center justify-center py-12 text-center text-red-600 dark:text-red-400">
            <ExclamationTriangleIcon className="h-12 w-12" />
            <p className="mt-3 text-sm">{error}</p>
            <Button
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={handleRefresh}
            >
              Réessayer
            </Button>
          </div>
        ) : isLoading ? (
          renderSkeletons()
        ) : (
          <>
            {/* Statistiques globales */}
            {renderStats()}

            {/* Métriques */}
            {renderMetrics()}

            {/* Alertes */}
            {renderAlerts()}

            {/* Composants */}
            {renderComponents()}
          </>
        )}

        {/* Footer */}
        {showHeader && (
          <CardFooter className="border-t border-gray-200 dark:border-gray-700 px-4 py-2 text-xs text-gray-400">
            <div className="flex items-center justify-between w-full">
              <span>
                Dernière mise à jour: {formatTimeFn(new Date())}
              </span>
              <span>
                {components.length} composants • {alerts.length} alertes
                {unreadAlerts.length > 0 && ` • ${unreadAlerts.length} non lues`}
              </span>
            </div>
          </CardFooter>
        )}
      </Card>
    );
  }
);

SystemHealth.displayName = 'SystemHealth';

// ============================================================================
// EXPORTS
// ============================================================================

export default SystemHealth;

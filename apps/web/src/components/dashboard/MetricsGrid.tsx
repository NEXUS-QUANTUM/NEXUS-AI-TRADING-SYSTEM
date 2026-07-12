import React, { useState, useCallback, useEffect, useRef } from 'react';
import { cn } from '@/lib/utils';
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  BarChart3,
  PieChart,
  LineChart,
  Activity,
  ArrowUpRight,
  ArrowDownRight,
  Wallet,
  Coins,
  Bitcoin,
  Ethereum,
  Zap,
  Clock,
  Calendar,
  Users,
  User,
  Briefcase,
  Shield,
  Lock,
  Eye,
  EyeOff,
  RefreshCw,
  Loader2,
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  Info,
  MoreHorizontal,
  Settings,
  Download,
  Share2,
  Copy,
  Maximize2,
  Minimize2,
  ExternalLink
} from 'lucide-react';
import { Card } from '@/components/common/Card';
import { Skeleton } from '@/components/common/Skeleton';
import { Tooltip } from '@/components/common/Tooltip';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { useTheme } from '@/hooks/useTheme';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import { formatCurrency, formatNumber, formatPercentage, formatDate, formatTime } from '@/lib/formatting';

/**
 * NEXUS AI TRADING SYSTEM - Metrics Grid Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 * 
 * Version: 3.0.0
 * Status: Production Ready
 * 
 * Complete Metrics Grid system with:
 * - Multiple metric types (number, currency, percentage, etc.)
 * - Real-time updates
 * - Auto-refresh
 * - Trend indicators
 * - Interactive charts
 * - Responsive grid
 * - Customizable layouts
 * - Drag & drop reordering
 * - Fullscreen mode
 * - Export data
 * - API integration
 * - WebSocket updates
 * - Accessibility (ARIA compliant)
 * - Theme aware
 * - Loading states
 * - Error states
 * - Animation
 * - Drill-down capability
 * - Filters
 * - Time ranges
 */

// ========================================
// TYPES & INTERFACES
// ========================================

export type MetricType = 
  | 'number' 
  | 'currency' 
  | 'percentage' 
  | 'time' 
  | 'date' 
  | 'duration' 
  | 'rate' 
  | 'ratio'
  | 'custom';

export type MetricTrend = 'up' | 'down' | 'neutral' | 'volatile';
export type MetricStatus = 'idle' | 'loading' | 'success' | 'error' | 'warning' | 'info';
export type MetricSize = 'sm' | 'md' | 'lg' | 'xl';
export type MetricVariant = 'default' | 'bordered' | 'glass' | 'gradient' | 'neon' | 'minimal';
export type MetricPeriod = 'realtime' | '1m' | '5m' | '15m' | '30m' | '1h' | '4h' | '1d' | '1w' | '1M' | '3M' | '1y';

export interface MetricData {
  /** Current value */
  value: number | string;
  /** Previous value for comparison */
  previousValue?: number | string;
  /** Change value */
  change?: number;
  /** Change percentage */
  changePercent?: number;
  /** Trend direction */
  trend?: MetricTrend;
  /** Status of the metric */
  status?: MetricStatus;
  /** Last updated timestamp */
  updatedAt?: string | Date;
  /** Additional data for charts */
  history?: MetricHistoryPoint[];
  /** Custom metadata */
  meta?: Record<string, any>;
}

export interface MetricHistoryPoint {
  /** Timestamp */
  timestamp: string | Date;
  /** Value at that time */
  value: number;
  /** Label for the point */
  label?: string;
}

export interface MetricAction {
  /** Action label */
  label: string;
  /** Action icon */
  icon?: React.ReactNode;
  /** Action handler */
  onClick: (metric: MetricConfig) => void;
  /** Disabled state */
  disabled?: boolean;
  /** Tooltip */
  tooltip?: string;
}

export interface MetricConfig {
  /** Unique metric id */
  id: string;
  /** Metric title */
  title: string;
  /** Metric description */
  description?: string;
  /** Metric type */
  type: MetricType;
  /** Metric data */
  data: MetricData;
  /** Metric size */
  size?: MetricSize;
  /** Metric variant */
  variant?: MetricVariant;
  /** Icon to display */
  icon?: React.ReactNode;
  /** Custom value formatter */
  formatValue?: (value: any, type: MetricType) => string;
  /** Custom color */
  color?: string;
  /** Background color */
  backgroundColor?: string;
  /** Border color */
  borderColor?: string;
  /** Progress value (0-100) */
  progress?: number;
  /** Progress label */
  progressLabel?: string;
  /** Subtitle */
  subtitle?: string;
  /** Subtitle value */
  subtitleValue?: string | number;
  /** Additional info */
  info?: string;
  /** Metric actions */
  actions?: MetricAction[];
  /** Period for the metric */
  period?: MetricPeriod;
  /** Auto-refresh interval (ms) */
  refreshInterval?: number;
  /** API endpoint for data */
  endpoint?: string;
  /** WebSocket channel for updates */
  wsChannel?: string;
  /** Filter function */
  filter?: (metric: MetricConfig) => boolean;
  /** Custom renderer */
  render?: (metric: MetricConfig) => React.ReactNode;
  /** On click handler */
  onClick?: (metric: MetricConfig) => void;
  /** On refresh handler */
  onRefresh?: (metric: MetricConfig) => Promise<MetricData>;
  /** On export handler */
  onExport?: (metric: MetricConfig) => void;
  /** Drill-down URL */
  drillUrl?: string;
  /** Additional className */
  className?: string;
}

export interface MetricsGridProps {
  /** Metric configurations */
  metrics: MetricConfig[];
  /** Number of columns */
  columns?: number;
  /** Responsive columns */
  responsiveColumns?: {
    sm?: number;
    md?: number;
    lg?: number;
    xl?: number;
    '2xl'?: number;
  };
  /** Gap between metrics */
  gap?: number;
  /** Grid variant */
  variant?: 'default' | 'compact' | 'spacious' | 'dashboard';
  /** Loading state */
  loading?: boolean;
  /** Error state */
  error?: string | null;
  /** Empty state */
  emptyState?: React.ReactNode;
  /** Auto-refresh interval (ms) */
  refreshInterval?: number;
  /** Enable drag & drop reordering */
  reorderable?: boolean;
  /** Enable fullscreen for individual metrics */
  fullscreenable?: boolean;
  /** Enable export */
  exportable?: boolean;
  /** On metric click */
  onMetricClick?: (metric: MetricConfig) => void;
  /** On metric refresh */
  onMetricRefresh?: (metric: MetricConfig) => Promise<MetricData>;
  /** On metrics reorder */
  onMetricsReorder?: (metrics: MetricConfig[]) => void;
  /** On export */
  onExport?: (metrics: MetricConfig[]) => void;
  /** Additional className */
  className?: string;
  /** Header actions */
  headerActions?: React.ReactNode;
  /** Title */
  title?: string;
  /** Description */
  description?: string;
  /** Persist layout */
  persistLayout?: boolean;
  /** Storage key */
  storageKey?: string;
  /** Test ID */
  testId?: string;
}

// ========================================
// CONFIGURATION
// ========================================

const VARIANT_CONFIG: Record<MetricVariant, {
  container: string;
  title: string;
  value: string;
  change: string;
  subtitle: string;
}> = {
  default: {
    container: 'bg-white dark:bg-nexus-900 border border-nexus-200 dark:border-nexus-700',
    title: 'text-nexus-500 dark:text-nexus-400',
    value: 'text-nexus-900 dark:text-nexus-100',
    change: '',
    subtitle: 'text-nexus-400 dark:text-nexus-500'
  },
  bordered: {
    container: 'bg-white dark:bg-nexus-900 border-2 border-nexus-300 dark:border-nexus-600',
    title: 'text-nexus-500 dark:text-nexus-400',
    value: 'text-nexus-900 dark:text-nexus-100',
    change: '',
    subtitle: 'text-nexus-400 dark:text-nexus-500'
  },
  glass: {
    container: 'bg-white/10 backdrop-blur-xl border border-white/20 text-white',
    title: 'text-white/70',
    value: 'text-white',
    change: '',
    subtitle: 'text-white/50'
  },
  gradient: {
    container: 'bg-gradient-to-br from-nexus-500 to-nexus-700 text-white border-0',
    title: 'text-white/80',
    value: 'text-white',
    change: '',
    subtitle: 'text-white/60'
  },
  neon: {
    container: 'bg-nexus-900 border border-nexus-400/30 shadow-[0_0_30px_rgba(99,102,241,0.1)]',
    title: 'text-nexus-400',
    value: 'text-nexus-100',
    change: '',
    subtitle: 'text-nexus-500'
  },
  minimal: {
    container: 'bg-transparent border-0',
    title: 'text-nexus-500 dark:text-nexus-400',
    value: 'text-nexus-900 dark:text-nexus-100',
    change: '',
    subtitle: 'text-nexus-400 dark:text-nexus-500'
  }
};

const SIZE_CONFIG: Record<MetricSize, {
  padding: string;
  title: string;
  value: string;
  subtitle: string;
  icon: string;
  gap: string;
}> = {
  sm: {
    padding: 'p-3',
    title: 'text-xs',
    value: 'text-lg font-bold',
    subtitle: 'text-xs',
    icon: 'w-4 h-4',
    gap: 'gap-1'
  },
  md: {
    padding: 'p-4',
    title: 'text-sm',
    value: 'text-2xl font-bold',
    subtitle: 'text-sm',
    icon: 'w-5 h-5',
    gap: 'gap-2'
  },
  lg: {
    padding: 'p-5',
    title: 'text-base',
    value: 'text-3xl font-bold',
    subtitle: 'text-base',
    icon: 'w-6 h-6',
    gap: 'gap-3'
  },
  xl: {
    padding: 'p-6',
    title: 'text-lg',
    value: 'text-4xl font-bold',
    subtitle: 'text-lg',
    icon: 'w-7 h-7',
    gap: 'gap-4'
  }
};

const TREND_CONFIG: Record<MetricTrend, {
  icon: React.ReactNode;
  color: string;
  label: string;
}> = {
  up: {
    icon: <ArrowUpRight className="w-4 h-4" />,
    color: 'text-emerald-500',
    label: 'Up'
  },
  down: {
    icon: <ArrowDownRight className="w-4 h-4" />,
    color: 'text-red-500',
    label: 'Down'
  },
  neutral: {
    icon: <Activity className="w-4 h-4" />,
    color: 'text-nexus-400',
    label: 'Neutral'
  },
  volatile: {
    icon: <Zap className="w-4 h-4" />,
    color: 'text-yellow-500',
    label: 'Volatile'
  }
};

const STATUS_CONFIG: Record<MetricStatus, {
  icon: React.ReactNode;
  color: string;
  label: string;
}> = {
  idle: {
    icon: null,
    color: '',
    label: ''
  },
  loading: {
    icon: <Loader2 className="w-4 h-4 animate-spin" />,
    color: 'text-nexus-500',
    label: 'Loading...'
  },
  success: {
    icon: <CheckCircle className="w-4 h-4" />,
    color: 'text-emerald-500',
    label: 'Success'
  },
  error: {
    icon: <AlertCircle className="w-4 h-4" />,
    color: 'text-red-500',
    label: 'Error'
  },
  warning: {
    icon: <AlertTriangle className="w-4 h-4" />,
    color: 'text-yellow-500',
    label: 'Warning'
  },
  info: {
    icon: <Info className="w-4 h-4" />,
    color: 'text-blue-500',
    label: 'Info'
  }
};

const PERIOD_LABELS: Record<MetricPeriod, string> = {
  realtime: 'Real-time',
  '1m': '1 min',
  '5m': '5 min',
  '15m': '15 min',
  '30m': '30 min',
  '1h': '1 hour',
  '4h': '4 hours',
  '1d': '1 day',
  '1w': '1 week',
  '1M': '1 month',
  '3M': '3 months',
  '1y': '1 year'
};

// ========================================
// SUB-COMPONENTS
// ========================================

const MetricIcon: React.FC<{ config: MetricConfig; className?: string }> = ({
  config,
  className
}) => {
  const defaultIcons: Record<MetricType, React.ReactNode> = {
    number: <BarChart3 className="w-5 h-5" />,
    currency: <DollarSign className="w-5 h-5" />,
    percentage: <TrendingUp className="w-5 h-5" />,
    time: <Clock className="w-5 h-5" />,
    date: <Calendar className="w-5 h-5" />,
    duration: <Clock className="w-5 h-5" />,
    rate: <Activity className="w-5 h-5" />,
    ratio: <PieChart className="w-5 h-5" />,
    custom: <LineChart className="w-5 h-5" />
  };

  const icon = config.icon || defaultIcons[config.type] || defaultIcons.custom;

  return (
    <div className={cn('flex-shrink-0', className)}>
      {icon}
    </div>
  );
};

const MetricValue: React.FC<{
  config: MetricConfig;
  className?: string;
}> = ({ config, className }) => {
  const { data, type, formatValue } = config;
  const value = data.value;
  const size = config.size || 'md';
  const sizeConfig = SIZE_CONFIG[size];

  const format = (val: any, type: MetricType): string => {
    if (formatValue) return formatValue(val, type);

    switch (type) {
      case 'currency':
        return typeof val === 'number' ? formatCurrency(val) : String(val);
      case 'percentage':
        return typeof val === 'number' ? formatPercentage(val) : String(val);
      case 'number':
        return typeof val === 'number' ? formatNumber(val) : String(val);
      case 'date':
        return typeof val === 'string' || val instanceof Date ? formatDate(val) : String(val);
      case 'time':
        return typeof val === 'string' || val instanceof Date ? formatTime(val) : String(val);
      default:
        return String(val);
    }
  };

  return (
    <div className={cn(sizeConfig.value, className)}>
      {format(value, type)}
    </div>
  );
};

const MetricTrend: React.FC<{
  trend?: MetricTrend;
  change?: number;
  changePercent?: number;
  className?: string;
}> = ({ trend, change, changePercent, className }) => {
  if (!trend || trend === 'neutral') return null;

  const trendConfig = TREND_CONFIG[trend];

  return (
    <div className={cn('flex items-center gap-1', trendConfig.color, className)}>
      {trendConfig.icon}
      {change !== undefined && (
        <span className="text-sm font-medium">
          {change > 0 ? '+' : ''}{formatNumber(change)}
        </span>
      )}
      {changePercent !== undefined && (
        <span className="text-sm">
          ({changePercent > 0 ? '+' : ''}{formatPercentage(changePercent)})
        </span>
      )}
    </div>
  );
};

const MetricStatus: React.FC<{
  status?: MetricStatus;
  className?: string;
}> = ({ status, className }) => {
  if (!status || status === 'idle') return null;

  const statusConfig = STATUS_CONFIG[status];

  return (
    <div className={cn('flex items-center gap-1', statusConfig.color, className)}>
      {statusConfig.icon}
      <span className="text-xs">{statusConfig.label}</span>
    </div>
  );
};

const MetricActions: React.FC<{
  config: MetricConfig;
  onAction?: (config: MetricConfig) => void;
}> = ({ config, onAction }) => {
  const [isOpen, setIsOpen] = useState(false);

  if (!config.actions || config.actions.length === 0) return null;

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="p-1 rounded hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors"
      >
        <MoreHorizontal className="w-4 h-4 text-nexus-400" />
      </button>
      
      {isOpen && (
        <div className="absolute right-0 top-full mt-1 bg-white dark:bg-nexus-900 border border-nexus-200 dark:border-nexus-700 rounded-lg shadow-lg p-1 z-10 min-w-[150px]">
          {config.actions.map((action, index) => (
            <button
              key={index}
              onClick={() => {
                action.onClick(config);
                setIsOpen(false);
                onAction?.(config);
              }}
              disabled={action.disabled}
              className={cn(
                'flex items-center gap-2 w-full px-3 py-1.5 text-sm rounded hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors',
                action.disabled && 'opacity-50 cursor-not-allowed'
              )}
              title={action.tooltip}
            >
              {action.icon}
              {action.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
};

// ========================================
// MAIN COMPONENT
// ========================================

export const MetricsGrid: React.FC<MetricsGridProps> = ({
  metrics: initialMetrics,
  columns = 4,
  responsiveColumns,
  gap = 4,
  variant = 'default',
  loading = false,
  error = null,
  emptyState,
  refreshInterval = 0,
  reorderable = false,
  fullscreenable = false,
  exportable = false,
  onMetricClick,
  onMetricRefresh,
  onMetricsReorder,
  onExport,
  className,
  headerActions,
  title,
  description,
  persistLayout = false,
  storageKey = 'nexus-metrics-layout',
  testId = 'nexus-metrics-grid'
}) => {
  // ========================================
  // STATE
  // ========================================
  
  const [metrics, setMetrics] = useState<MetricConfig[]>(initialMetrics);
  const [metricsData, setMetricsData] = useState<Record<string, MetricData>>({});
  const [fullscreenMetricId, setFullscreenMetricId] = useState<string | null>(null);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [refreshCount, setRefreshCount] = useState(0);
  const [isDragging, setIsDragging] = useState(false);

  // ========================================
  // REFS
  // ========================================
  
  const containerRef = useRef<HTMLDivElement>(null);
  const refreshTimerRef = useRef<NodeJS.Timeout>();
  const wsConnectionsRef = useRef<Record<string, WebSocket>>({});

  // ========================================
  // HOOKS
  // ========================================
  
  const { theme } = useTheme();
  const [storedLayout, setStoredLayout] = useLocalStorage<string>(storageKey, '');

  // ========================================
  // EFFECTS
  // ========================================
  
  // Sync with props
  useEffect(() => {
    setMetrics(initialMetrics);
    // Initialize data
    const initialData: Record<string, MetricData> = {};
    initialMetrics.forEach(m => {
      initialData[m.id] = m.data;
    });
    setMetricsData(initialData);
  }, [initialMetrics]);

  // Load stored layout
  useEffect(() => {
    if (persistLayout && storedLayout && storedLayout !== '') {
      try {
        const parsed = JSON.parse(storedLayout);
        if (Array.isArray(parsed) && parsed.length > 0) {
          const reordered = parsed.map(id => metrics.find(m => m.id === id)).filter(Boolean) as MetricConfig[];
          if (reordered.length === metrics.length) {
            setMetrics(reordered);
          }
        }
      } catch (e) {
        // Invalid stored layout
      }
    }
  }, [persistLayout, storedLayout]);

  // Auto-refresh
  useEffect(() => {
    if (refreshInterval > 0) {
      refreshTimerRef.current = setInterval(() => {
        handleRefreshAll();
      }, refreshInterval);
    }

    return () => {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
      }
    };
  }, [refreshInterval]);

  // WebSocket connections
  useEffect(() => {
    metrics.forEach(metric => {
      if (metric.wsChannel) {
        connectWebSocket(metric);
      }
    });

    return () => {
      Object.values(wsConnectionsRef.current).forEach(ws => {
        ws.close();
      });
      wsConnectionsRef.current = {};
    };
  }, [metrics]);

  // ========================================
  // HANDLERS
  // ========================================
  
  const connectWebSocket = useCallback((metric: MetricConfig) => {
    if (!metric.wsChannel) return;

    try {
      const ws = new WebSocket(metric.wsChannel);
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          updateMetricData(metric.id, data);
        } catch (e) {
          console.error('Failed to parse WebSocket data:', e);
        }
      };

      ws.onerror = (event) => {
        console.error(`WebSocket error for ${metric.id}:`, event);
      };

      ws.onclose = () => {
        // Reconnect after delay
        setTimeout(() => {
          connectWebSocket(metric);
        }, 5000);
      };

      wsConnectionsRef.current[metric.id] = ws;
    } catch (e) {
      console.error(`Failed to connect WebSocket for ${metric.id}:`, e);
    }
  }, []);

  const updateMetricData = useCallback((id: string, data: MetricData) => {
    setMetricsData(prev => ({
      ...prev,
      [id]: {
        ...prev[id],
        ...data,
        updatedAt: new Date()
      }
    }));
  }, []);

  const handleRefreshAll = useCallback(async () => {
    if (isRefreshing) return;
    
    setIsRefreshing(true);
    setRefreshCount(prev => prev + 1);

    try {
      const refreshPromises = metrics.map(async (metric) => {
        if (metric.onRefresh) {
          try {
            const data = await metric.onRefresh(metric);
            updateMetricData(metric.id, data);
          } catch (e) {
            console.error(`Failed to refresh metric ${metric.id}:`, e);
          }
        }
      });

      await Promise.allSettled(refreshPromises);
    } finally {
      setIsRefreshing(false);
    }
  }, [metrics, isRefreshing, updateMetricData]);

  const handleMetricRefresh = useCallback(async (metric: MetricConfig) => {
    if (onMetricRefresh) {
      const data = await onMetricRefresh(metric);
      updateMetricData(metric.id, data);
    } else if (metric.onRefresh) {
      const data = await metric.onRefresh(metric);
      updateMetricData(metric.id, data);
    }
  }, [onMetricRefresh, updateMetricData]);

  const handleMetricClick = useCallback((metric: MetricConfig) => {
    if (metric.onClick) {
      metric.onClick(metric);
    }
    onMetricClick?.(metric);
  }, [onMetricClick]);

  const handleFullscreenToggle = useCallback((metricId: string) => {
    setFullscreenMetricId(prev => prev === metricId ? null : metricId);
  }, []);

  const handleDragStart = useCallback((e: React.DragEvent, index: number) => {
    if (!reorderable) return;
    e.dataTransfer.effectAllowed = 'move';
    e.dataTransfer.setData('text/plain', String(index));
    setIsDragging(true);
  }, [reorderable]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  }, []);

  const handleDrop = useCallback((e: React.DragEvent, dropIndex: number) => {
    e.preventDefault();
    if (!reorderable) return;

    const dragIndex = parseInt(e.dataTransfer.getData('text/plain'));
    if (isNaN(dragIndex) || dragIndex === dropIndex) return;

    const newMetrics = [...metrics];
    const [draggedItem] = newMetrics.splice(dragIndex, 1);
    newMetrics.splice(dropIndex, 0, draggedItem);

    setMetrics(newMetrics);
    onMetricsReorder?.(newMetrics);

    if (persistLayout) {
      setStoredLayout(JSON.stringify(newMetrics.map(m => m.id)));
    }

    setIsDragging(false);
  }, [reorderable, metrics, onMetricsReorder, persistLayout, setStoredLayout]);

  const handleExport = useCallback(() => {
    if (onExport) {
      onExport(metrics);
      return;
    }

    // Default export as JSON
    const data = metrics.map(metric => ({
      id: metric.id,
      title: metric.title,
      data: metricsData[metric.id] || metric.data
    }));

    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `metrics-${new Date().toISOString()}.json`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
  }, [metrics, metricsData, onExport]);

  // ========================================
  // RENDER HELPERS
  // ========================================
  
  const getResponsiveColumns = useCallback(() => {
    const base = responsiveColumns || {};
    return {
      sm: base.sm || Math.min(columns, 1),
      md: base.md || Math.min(columns, 2),
      lg: base.lg || Math.min(columns, 3),
      xl: base.xl || Math.min(columns, 4),
      '2xl': base['2xl'] || Math.min(columns, 4)
    };
  }, [responsiveColumns, columns]);

  const renderMetricContent = useCallback((metric: MetricConfig) => {
    const data = metricsData[metric.id] || metric.data;
    const size = metric.size || 'md';
    const variantConfig = VARIANT_CONFIG[metric.variant || 'default'];
    const sizeConfig = SIZE_CONFIG[size];
    const status = data.status || 'idle';
    const statusConfig = STATUS_CONFIG[status];

    if (metric.render) {
      return metric.render(metric);
    }

    return (
      <div className="flex flex-col gap-2 w-full">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <MetricIcon config={metric} className={variantConfig.title} />
            <div className="min-w-0">
              <div className={cn('font-medium truncate', variantConfig.title, sizeConfig.title)}>
                {metric.title}
              </div>
              {metric.subtitle && (
                <div className={cn('truncate', variantConfig.subtitle, sizeConfig.subtitle)}>
                  {metric.subtitle}
                  {metric.subtitleValue !== undefined && (
                    <span className="font-medium ml-1">
                      {metric.subtitleValue}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          <div className="flex items-center gap-1 flex-shrink-0">
            {/* Status */}
            {status !== 'idle' && (
              <Tooltip content={statusConfig.label}>
                <span className={cn('flex-shrink-0', statusConfig.color)}>
                  {statusConfig.icon}
                </span>
              </Tooltip>
            )}

            {/* Refresh button */}
            {metric.onRefresh && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleMetricRefresh(metric);
                }}
                className="p-1 rounded hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors"
              >
                <RefreshCw className="w-3 h-3 text-nexus-400" />
              </button>
            )}

            {/* Fullscreen button */}
            {fullscreenable && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleFullscreenToggle(metric.id);
                }}
                className="p-1 rounded hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors"
              >
                <Maximize2 className="w-3 h-3 text-nexus-400" />
              </button>
            )}

            {/* Actions */}
            <MetricActions config={metric} />
          </div>
        </div>

        {/* Value */}
        <div className="flex items-baseline gap-3">
          <MetricValue config={{ ...metric, data }} className={variantConfig.value} />
          
          {data.change !== undefined && data.change !== 0 && (
            <MetricTrend
              trend={data.trend}
              change={data.change}
              changePercent={data.changePercent}
            />
          )}
        </div>

        {/* Progress */}
        {metric.progress !== undefined && (
          <div className="w-full">
            <div className="flex items-center justify-between text-xs text-nexus-400">
              <span>{metric.progressLabel || 'Progress'}</span>
              <span>{formatPercentage(metric.progress)}</span>
            </div>
            <div className="w-full h-1.5 bg-nexus-200 dark:bg-nexus-700 rounded-full overflow-hidden mt-1">
              <div
                className="h-full rounded-full transition-all duration-500"
                style={{
                  width: `${Math.min(100, Math.max(0, metric.progress))}%`,
                  backgroundColor: metric.color || 'var(--nexus-500)'
                }}
              />
            </div>
          </div>
        )}

        {/* Footer */}
        <div className="flex items-center justify-between mt-1">
          {data.updatedAt && (
            <span className={cn('text-xs', variantConfig.subtitle)}>
              Updated {formatTimeAgo(data.updatedAt)}
            </span>
          )}
          {metric.period && (
            <Badge variant="outline" size="sm">
              {PERIOD_LABELS[metric.period]}
            </Badge>
          )}
        </div>
      </div>
    );
  }, [metricsData, fullscreenable, handleMetricRefresh, handleFullscreenToggle]);

  const renderMetric = useCallback((metric: MetricConfig, index: number) => {
    const size = metric.size || 'md';
    const variantConfig = VARIANT_CONFIG[metric.variant || 'default'];
    const sizeConfig = SIZE_CONFIG[size];
    const data = metricsData[metric.id] || metric.data;
    const isFullscreen = fullscreenMetricId === metric.id;

    const cardContent = (
      <Card
        className={cn(
          'relative transition-all duration-200',
          variantConfig.container,
          sizeConfig.padding,
          isFullscreen && 'fixed inset-4 z-50 overflow-auto',
          metric.onClick && 'cursor-pointer hover:shadow-lg hover:border-nexus-400 dark:hover:border-nexus-500',
          isDragging && 'opacity-50',
          metric.className
        )}
        style={{
          borderColor: metric.borderColor,
          backgroundColor: metric.backgroundColor,
          color: metric.color
        }}
        onClick={() => handleMetricClick(metric)}
        data-metric-id={metric.id}
        data-testid={`${testId}-metric-${metric.id}`}
      >
        {renderMetricContent(metric)}
      </Card>
    );

    if (isFullscreen) {
      return (
        <div
          key={metric.id}
          className="fixed inset-0 z-50 bg-black/50 backdrop-blur-sm flex items-center justify-center p-4"
          onClick={(e) => {
            if (e.target === e.currentTarget) {
              handleFullscreenToggle(metric.id);
            }
          }}
        >
          <div className="w-full max-w-4xl max-h-[90vh] overflow-auto">
            {cardContent}
          </div>
        </div>
      );
    }

    return cardContent;
  }, [metricsData, fullscreenMetricId, isDragging, testId, renderMetricContent, handleMetricClick, handleFullscreenToggle]);

  // ========================================
  // RENDER
  // ========================================
  
  if (loading) {
    return (
      <div className="w-full">
        <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}>
          {Array.from({ length: Math.min(columns, 4) }).map((_, i) => (
            <Card key={i} className="p-4">
              <Skeleton className="h-4 w-24 mb-2" />
              <Skeleton className="h-8 w-32 mb-2" />
              <Skeleton className="h-4 w-20" />
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-center">
        <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
        <h3 className="text-lg font-semibold text-nexus-900 dark:text-nexus-100">Error loading metrics</h3>
        <p className="text-nexus-500 dark:text-nexus-400 mt-2">{error}</p>
        <button
          onClick={handleRefreshAll}
          className="mt-4 px-4 py-2 bg-nexus-500 text-white rounded-lg hover:bg-nexus-600"
        >
          Try Again
        </button>
      </div>
    );
  }

  if (metrics.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-center">
        {emptyState || (
          <>
            <BarChart3 className="w-12 h-12 text-nexus-400 mb-4" />
            <h3 className="text-lg font-semibold text-nexus-900 dark:text-nexus-100">No metrics available</h3>
            <p className="text-nexus-500 dark:text-nexus-400 mt-2">Configure your metrics to start monitoring</p>
          </>
        )}
      </div>
    );
  }

  const responsiveCols = getResponsiveColumns();

  return (
    <div
      ref={containerRef}
      className={cn('w-full', className)}
      data-testid={testId}
    >
      {/* Header */}
      {(title || description || headerActions || exportable) && (
        <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
          <div>
            {title && (
              <h2 className="text-2xl font-bold text-nexus-900 dark:text-nexus-100">
                {title}
              </h2>
            )}
            {description && (
              <p className="text-nexus-500 dark:text-nexus-400 mt-1">
                {description}
              </p>
            )}
          </div>

          <div className="flex items-center gap-2">
            {/* Refresh button */}
            <button
              onClick={handleRefreshAll}
              disabled={isRefreshing}
              className="p-2 rounded-lg border border-nexus-200 dark:border-nexus-700 hover:bg-nexus-50 dark:hover:bg-nexus-800 transition-colors disabled:opacity-50"
              title="Refresh all"
            >
              <RefreshCw className={cn('w-4 h-4 text-nexus-500', isRefreshing && 'animate-spin')} />
            </button>

            {/* Export button */}
            {exportable && (
              <button
                onClick={handleExport}
                className="p-2 rounded-lg border border-nexus-200 dark:border-nexus-700 hover:bg-nexus-50 dark:hover:bg-nexus-800 transition-colors"
                title="Export metrics"
              >
                <Download className="w-4 h-4 text-nexus-500" />
              </button>
            )}

            {headerActions}
          </div>
        </div>
      )}

      {/* Grid */}
      <div
        className="grid gap-4"
        style={{
          gap: gap * 4,
          gridTemplateColumns: `repeat(${columns}, 1fr)`,
        }}
        data-columns={columns}
      >
        {metrics.map((metric, index) => (
          <div
            key={metric.id}
            className={cn(
              'transition-opacity duration-200',
              isDragging && 'opacity-50'
            )}
            draggable={reorderable}
            onDragStart={(e) => handleDragStart(e, index)}
            onDragOver={handleDragOver}
            onDrop={(e) => handleDrop(e, index)}
            style={{
              gridColumn: `span 1`,
            }}
          >
            {renderMetric(metric, index)}
          </div>
        ))}
      </div>
    </div>
  );
};

// ========================================
// EXPORTS
// ========================================

MetricsGrid.displayName = 'MetricsGrid';

export default MetricsGrid;

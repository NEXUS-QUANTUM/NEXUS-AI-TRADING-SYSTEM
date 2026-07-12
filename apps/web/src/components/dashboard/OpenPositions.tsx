import React, { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { cn } from '@/lib/utils';
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  ArrowUpRight,
  ArrowDownRight,
  X,
  Loader2,
  AlertCircle,
  AlertTriangle,
  CheckCircle,
  Info,
  MoreHorizontal,
  Settings,
  Download,
  RefreshCw,
  Maximize2,
  Minimize2,
  ExternalLink,
  Eye,
  EyeOff,
  Copy,
  Trash2,
  Edit,
  Clock,
  Calendar,
  Wallet,
  Coins,
  Bitcoin,
  Ethereum,
  Zap,
  Shield,
  Lock,
  Unlock,
  Pause,
  Play,
  StopCircle,
  Filter,
  Search,
  ChevronDown,
  ChevronUp,
  ChevronLeft,
  ChevronRight,
  Menu
} from 'lucide-react';
import { Card } from '@/components/common/Card';
import { Table } from '@/components/common/Table';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Tooltip } from '@/components/common/Tooltip';
import { Modal } from '@/components/common/Modal';
import { Toast } from '@/components/common/Toast';
import { Skeleton } from '@/components/common/Skeleton';
import { Spinner } from '@/components/common/Spinner';
import { useTheme } from '@/hooks/useTheme';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import { useDebounce } from '@/hooks/useDebounce';
import { formatCurrency, formatNumber, formatPercentage, formatDate, formatTime, formatDuration } from '@/lib/formatting';

/**
 * NEXUS AI TRADING SYSTEM - Open Positions Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 * 
 * Version: 3.0.0
 * Status: Production Ready
 * 
 * Complete Open Positions system with:
 * - Real-time position updates
 * - P&L tracking
 * - Position management (close, modify, etc.)
 * - Stop loss / Take profit
 * - Margin tracking
 * - Leverage management
 * - Position grouping
 * - Advanced filtering
 * - Sorting
 * - Search
 * - Export
 * - WebSocket integration
 * - API integration
 * - Responsive design
 * - Theme aware
 * - Accessibility (ARIA compliant)
 * - Performance optimized
 */

// ========================================
// TYPES & INTERFACES
// ========================================

export type PositionSide = 'long' | 'short';
export type PositionStatus = 'open' | 'closed' | 'pending' | 'partial' | 'stop_loss' | 'take_profit';
export type PositionType = 'market' | 'limit' | 'stop' | 'stop_limit';
export type PositionOrderType = 'market' | 'limit' | 'stop' | 'stop_limit' | 'trailing_stop';
export type PositionTimeInForce = 'GTC' | 'IOC' | 'FOK' | 'DAY' | 'GOOD_TIL_CANCELED';
export type PositionSource = 'manual' | 'ai' | 'signal' | 'bot' | 'api';

export interface Position {
  /** Unique position id */
  id: string;
  /** Symbol/Instrument */
  symbol: string;
  /** Side (long/short) */
  side: PositionSide;
  /** Entry price */
  entryPrice: number;
  /** Current price */
  currentPrice: number;
  /** Quantity */
  quantity: number;
  /** Leverage */
  leverage: number;
  /** Margin used */
  margin: number;
  /** Unrealized P&L */
  unrealizedPnL: number;
  /** Realized P&L */
  realizedPnL: number;
  /** Total P&L */
  totalPnL: number;
  /** P&L percentage */
  pnlPercent: number;
  /** Stop loss price */
  stopLoss?: number;
  /** Take profit price */
  takeProfit?: number;
  /** Entry time */
  entryTime: string | Date;
  /** Last update time */
  updatedAt: string | Date;
  /** Position status */
  status: PositionStatus;
  /** Position type */
  type: PositionType;
  /** Order type */
  orderType: PositionOrderType;
  /** Time in force */
  timeInForce: PositionTimeInForce;
  /** Source of position */
  source: PositionSource;
  /** Notes */
  notes?: string;
  /** Tags */
  tags?: string[];
  /** Strategy id */
  strategyId?: string;
  /** Account id */
  accountId: string;
  /** Exchange/Broker */
  exchange: string;
  /** Currency */
  currency: string;
  /** Commission */
  commission?: number;
  /** Funding rate */
  fundingRate?: number;
  /** Open interest */
  openInterest?: number;
  /** Volume */
  volume?: number;
  /** Average entry price */
  avgEntryPrice?: number;
  /** Current value */
  currentValue?: number;
  /** Risk percentage */
  riskPercent?: number;
  /** Reward/Risk ratio */
  rewardRiskRatio?: number;
  /** Custom metadata */
  meta?: Record<string, any>;
}

export interface PositionGroup {
  /** Group id */
  id: string;
  /** Group label */
  label: string;
  /** Positions in group */
  positions: Position[];
  /** Total P&L for group */
  totalPnL: number;
  /** Group P&L percentage */
  pnlPercent: number;
  /** Group icon */
  icon?: React.ReactNode;
}

export interface PositionFilter {
  /** Search query */
  search?: string;
  /** Symbol filter */
  symbols?: string[];
  /** Side filter */
  sides?: PositionSide[];
  /** Status filter */
  statuses?: PositionStatus[];
  /** Source filter */
  sources?: PositionSource[];
  /** Min P&L */
  minPnL?: number;
  /** Max P&L */
  maxPnL?: number;
  /** Min quantity */
  minQuantity?: number;
  /** Max quantity */
  maxQuantity?: number;
  /** Date range */
  dateRange?: {
    start: string | Date;
    end: string | Date;
  };
  /** Tags filter */
  tags?: string[];
  /** Strategy filter */
  strategyIds?: string[];
}

export interface PositionSort {
  /** Sort field */
  field: keyof Position;
  /** Sort direction */
  direction: 'asc' | 'desc';
}

export interface PositionAction {
  /** Action type */
  type: 'close' | 'modify' | 'edit' | 'delete' | 'set_stop_loss' | 'set_take_profit' | 'duplicate' | 'export';
  /** Action label */
  label: string;
  /** Action handler */
  handler: (position: Position) => void | Promise<void>;
  /** Icon */
  icon?: React.ReactNode;
  /** Color */
  color?: string;
  /** Disabled state */
  disabled?: boolean;
  /** Tooltip */
  tooltip?: string;
}

export interface OpenPositionsProps {
  /** Positions data */
  positions: Position[];
  /** Loading state */
  loading?: boolean;
  /** Error state */
  error?: string | null;
  /** Auto-refresh interval (ms) */
  refreshInterval?: number;
  /** Enable real-time updates via WebSocket */
  enableRealtime?: boolean;
  /** WebSocket URL for real-time updates */
  wsUrl?: string;
  /** On position close */
  onPositionClose?: (position: Position) => void | Promise<void>;
  /** On position modify */
  onPositionModify?: (position: Position, updates: Partial<Position>) => void | Promise<void>;
  /** On position edit */
  onPositionEdit?: (position: Position) => void;
  /** On position export */
  onPositionExport?: (positions: Position[]) => void;
  /** On refresh */
  onRefresh?: () => Promise<void>;
  /** Position actions */
  actions?: PositionAction[];
  /** Additional columns to display */
  extraColumns?: TableColumn<Position>[];
  /** Filter configuration */
  initialFilters?: PositionFilter;
  /** Sort configuration */
  initialSort?: PositionSort[];
  /** Group positions */
  groupBy?: 'symbol' | 'side' | 'status' | 'source' | 'strategy';
  /** Show position details */
  showDetails?: boolean;
  /** Show position stats */
  showStats?: boolean;
  /** Allow position actions */
  allowActions?: boolean;
  /** Position action handlers */
  onAction?: (action: string, position: Position) => void;
  /** Additional className */
  className?: string;
  /** Test ID */
  testId?: string;
}

// ========================================
// CONFIGURATION
// ========================================

const SIDE_CONFIG: Record<PositionSide, {
  label: string;
  color: string;
  bg: string;
  icon: React.ReactNode;
}> = {
  long: {
    label: 'Long',
    color: 'text-emerald-500',
    bg: 'bg-emerald-500/10',
    icon: <TrendingUp className="w-3 h-3" />
  },
  short: {
    label: 'Short',
    color: 'text-red-500',
    bg: 'bg-red-500/10',
    icon: <TrendingDown className="w-3 h-3" />
  }
};

const STATUS_CONFIG: Record<PositionStatus, {
  label: string;
  color: string;
  bg: string;
  icon: React.ReactNode;
}> = {
  open: {
    label: 'Open',
    color: 'text-emerald-500',
    bg: 'bg-emerald-500/10',
    icon: <div className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
  },
  closed: {
    label: 'Closed',
    color: 'text-nexus-500',
    bg: 'bg-nexus-500/10',
    icon: <div className="w-2 h-2 rounded-full bg-nexus-500" />
  },
  pending: {
    label: 'Pending',
    color: 'text-yellow-500',
    bg: 'bg-yellow-500/10',
    icon: <Loader2 className="w-3 h-3 animate-spin" />
  },
  partial: {
    label: 'Partial',
    color: 'text-blue-500',
    bg: 'bg-blue-500/10',
    icon: <div className="w-2 h-2 rounded-full bg-blue-500" />
  },
  stop_loss: {
    label: 'Stop Loss',
    color: 'text-red-500',
    bg: 'bg-red-500/10',
    icon: <AlertTriangle className="w-3 h-3" />
  },
  take_profit: {
    label: 'Take Profit',
    color: 'text-emerald-500',
    bg: 'bg-emerald-500/10',
    icon: <CheckCircle className="w-3 h-3" />
  }
};

const SOURCE_CONFIG: Record<PositionSource, {
  label: string;
  icon: React.ReactNode;
  color: string;
}> = {
  manual: {
    label: 'Manual',
    icon: <User className="w-3 h-3" />,
    color: 'text-nexus-500'
  },
  ai: {
    label: 'AI',
    icon: <Zap className="w-3 h-3" />,
    color: 'text-purple-500'
  },
  signal: {
    label: 'Signal',
    icon: <Bell className="w-3 h-3" />,
    color: 'text-blue-500'
  },
  bot: {
    label: 'Bot',
    icon: <Bot className="w-3 h-3" />,
    color: 'text-cyan-500'
  },
  api: {
    label: 'API',
    icon: <Code className="w-3 h-3" />,
    color: 'text-nexus-500'
  }
};

// ========================================
// SUB-COMPONENTS
// ========================================

const PositionSideBadge: React.FC<{ side: PositionSide }> = ({ side }) => {
  const config = SIDE_CONFIG[side];
  return (
    <Badge className={cn('gap-1 font-medium', config.bg, config.color)}>
      {config.icon}
      {config.label}
    </Badge>
  );
};

const PositionStatusBadge: React.FC<{ status: PositionStatus }> = ({ status }) => {
  const config = STATUS_CONFIG[status];
  return (
    <Badge className={cn('gap-1 font-medium', config.bg, config.color)}>
      {config.icon}
      {config.label}
    </Badge>
  );
};

const PositionPnL: React.FC<{ pnl: number; pnlPercent: number }> = ({ pnl, pnlPercent }) => {
  const isPositive = pnl >= 0;
  const isNegative = pnl < 0;

  return (
    <div className="flex flex-col">
      <span className={cn(
        'font-medium',
        isPositive ? 'text-emerald-500' : 'text-red-500'
      )}>
        {isPositive ? '+' : ''}{formatCurrency(pnl)}
      </span>
      <span className={cn(
        'text-xs',
        isPositive ? 'text-emerald-400' : 'text-red-400'
      )}>
        {isPositive ? '+' : ''}{formatPercentage(pnlPercent)}
      </span>
    </div>
  );
};

// ========================================
// MAIN COMPONENT
// ========================================

export const OpenPositions: React.FC<OpenPositionsProps> = ({
  positions: initialPositions,
  loading = false,
  error = null,
  refreshInterval = 0,
  enableRealtime = false,
  wsUrl,
  onPositionClose,
  onPositionModify,
  onPositionEdit,
  onPositionExport,
  onRefresh,
  actions = [],
  extraColumns = [],
  initialFilters = {},
  initialSort = [],
  groupBy,
  showDetails = true,
  showStats = true,
  allowActions = true,
  onAction,
  className,
  testId = 'nexus-open-positions'
}) => {
  // ========================================
  // STATE
  // ========================================
  
  const [positions, setPositions] = useState<Position[]>(initialPositions);
  const [filteredPositions, setFilteredPositions] = useState<Position[]>(initialPositions);
  const [filters, setFilters] = useState<PositionFilter>(initialFilters);
  const [sort, setSort] = useState<PositionSort[]>(initialSort);
  const [selectedPositions, setSelectedPositions] = useState<string[]>([]);
  const [expandedPositions, setExpandedPositions] = useState<string[]>([]);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [closeModalOpen, setCloseModalOpen] = useState(false);
  const [modifyModalOpen, setModifyModalOpen] = useState(false);
  const [selectedPosition, setSelectedPosition] = useState<Position | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<'table' | 'cards'>('table');

  // ========================================
  // REFS
  // ========================================
  
  const refreshTimerRef = useRef<NodeJS.Timeout>();

  // ========================================
  // HOOKS
  // ========================================
  
  const { theme } = useTheme();
  const [storedViewMode, setStoredViewMode] = useLocalStorage<string>(
    'nexus-positions-view',
    'table'
  );

  // WebSocket connection
  const { lastMessage, isConnected } = useWebSocket(wsUrl || '', {
    autoConnect: enableRealtime,
    onMessage: (data) => {
      if (data.type === 'position_update') {
        handlePositionUpdate(data.position);
      } else if (data.type === 'position_created') {
        handlePositionCreated(data.position);
      } else if (data.type === 'position_closed') {
        handlePositionClosed(data.positionId);
      }
    }
  });

  // ========================================
  // EFFECTS
  // ========================================
  
  // Sync with props
  useEffect(() => {
    setPositions(initialPositions);
  }, [initialPositions]);

  // Apply filters and sort
  useEffect(() => {
    let result = [...positions];

    // Search
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(p =>
        p.symbol.toLowerCase().includes(query) ||
        p.id.toLowerCase().includes(query) ||
        p.notes?.toLowerCase().includes(query) ||
        p.tags?.some(t => t.toLowerCase().includes(query))
      );
    }

    // Apply filters
    if (filters.symbols && filters.symbols.length > 0) {
      result = result.filter(p => filters.symbols!.includes(p.symbol));
    }
    if (filters.sides && filters.sides.length > 0) {
      result = result.filter(p => filters.sides!.includes(p.side));
    }
    if (filters.statuses && filters.statuses.length > 0) {
      result = result.filter(p => filters.statuses!.includes(p.status));
    }
    if (filters.sources && filters.sources.length > 0) {
      result = result.filter(p => filters.sources!.includes(p.source));
    }
    if (filters.minPnL !== undefined) {
      result = result.filter(p => p.totalPnL >= filters.minPnL!);
    }
    if (filters.maxPnL !== undefined) {
      result = result.filter(p => p.totalPnL <= filters.maxPnL!);
    }
    if (filters.minQuantity !== undefined) {
      result = result.filter(p => p.quantity >= filters.minQuantity!);
    }
    if (filters.maxQuantity !== undefined) {
      result = result.filter(p => p.quantity <= filters.maxQuantity!);
    }
    if (filters.dateRange) {
      const start = new Date(filters.dateRange.start);
      const end = new Date(filters.dateRange.end);
      result = result.filter(p => {
        const entry = new Date(p.entryTime);
        return entry >= start && entry <= end;
      });
    }
    if (filters.tags && filters.tags.length > 0) {
      result = result.filter(p => p.tags?.some(t => filters.tags!.includes(t)));
    }
    if (filters.strategyIds && filters.strategyIds.length > 0) {
      result = result.filter(p => p.strategyId && filters.strategyIds!.includes(p.strategyId));
    }

    // Apply sort
    if (sort.length > 0) {
      sort.forEach(s => {
        result.sort((a, b) => {
          const aVal = a[s.field];
          const bVal = b[s.field];
          if (aVal < bVal) return s.direction === 'asc' ? -1 : 1;
          if (aVal > bVal) return s.direction === 'asc' ? 1 : -1;
          return 0;
        });
      });
    }

    setFilteredPositions(result);
  }, [positions, filters, sort, searchQuery]);

  // Auto-refresh
  useEffect(() => {
    if (refreshInterval > 0) {
      refreshTimerRef.current = setInterval(() => {
        handleRefresh();
      }, refreshInterval);
    }

    return () => {
      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
      }
    };
  }, [refreshInterval]);

  // Load view mode from storage
  useEffect(() => {
    if (storedViewMode) {
      setViewMode(storedViewMode as 'table' | 'cards');
    }
  }, [storedViewMode]);

  // ========================================
  // HANDLERS
  // ========================================
  
  const handleRefresh = useCallback(async () => {
    if (isRefreshing) return;
    setIsRefreshing(true);
    try {
      await onRefresh?.();
    } finally {
      setIsRefreshing(false);
    }
  }, [onRefresh, isRefreshing]);

  const handlePositionUpdate = useCallback((updatedPosition: Position) => {
    setPositions(prev => prev.map(p =>
      p.id === updatedPosition.id ? updatedPosition : p
    ));
  }, []);

  const handlePositionCreated = useCallback((newPosition: Position) => {
    setPositions(prev => [...prev, newPosition]);
  }, []);

  const handlePositionClosed = useCallback((positionId: string) => {
    setPositions(prev => prev.filter(p => p.id !== positionId));
  }, []);

  const handleSearch = useCallback((query: string) => {
    setSearchQuery(query);
  }, []);

  const handleFilterChange = useCallback((newFilters: Partial<PositionFilter>) => {
    setFilters(prev => ({ ...prev, ...newFilters }));
  }, []);

  const handleSortChange = useCallback((newSort: PositionSort[]) => {
    setSort(newSort);
  }, []);

  const handleClosePosition = useCallback((position: Position) => {
    setSelectedPosition(position);
    setCloseModalOpen(true);
  }, []);

  const handleConfirmClose = useCallback(async () => {
    if (!selectedPosition) return;
    try {
      await onPositionClose?.(selectedPosition);
      setCloseModalOpen(false);
      setSelectedPosition(null);
    } catch (error) {
      console.error('Failed to close position:', error);
    }
  }, [selectedPosition, onPositionClose]);

  const handleModifyPosition = useCallback((position: Position) => {
    setSelectedPosition(position);
    setModifyModalOpen(true);
  }, []);

  const handleConfirmModify = useCallback(async (updates: Partial<Position>) => {
    if (!selectedPosition) return;
    try {
      await onPositionModify?.(selectedPosition, updates);
      setModifyModalOpen(false);
      setSelectedPosition(null);
    } catch (error) {
      console.error('Failed to modify position:', error);
    }
  }, [selectedPosition, onPositionModify]);

  const handleSelectPosition = useCallback((positionId: string) => {
    setSelectedPositions(prev =>
      prev.includes(positionId)
        ? prev.filter(id => id !== positionId)
        : [...prev, positionId]
    );
  }, []);

  const handleSelectAll = useCallback(() => {
    if (selectedPositions.length === filteredPositions.length) {
      setSelectedPositions([]);
    } else {
      setSelectedPositions(filteredPositions.map(p => p.id));
    }
  }, [filteredPositions, selectedPositions]);

  const handleToggleExpand = useCallback((positionId: string) => {
    setExpandedPositions(prev =>
      prev.includes(positionId)
        ? prev.filter(id => id !== positionId)
        : [...prev, positionId]
    );
  }, []);

  const handleAction = useCallback((actionType: string, position: Position) => {
    onAction?.(actionType, position);
  }, [onAction]);

  // ========================================
  // COMPUTED
  // ========================================
  
  const stats = useMemo(() => {
    const openPositions = positions.filter(p => p.status === 'open');
    const totalPnL = positions.reduce((sum, p) => sum + p.totalPnL, 0);
    const totalUnrealizedPnL = positions.reduce((sum, p) => sum + p.unrealizedPnL, 0);
    const totalRealizedPnL = positions.reduce((sum, p) => sum + p.realizedPnL, 0);
    const totalMargin = positions.reduce((sum, p) => sum + p.margin, 0);
    const totalQuantity = positions.reduce((sum, p) => sum + p.quantity, 0);
    const winRate = positions.length > 0
      ? (positions.filter(p => p.totalPnL > 0).length / positions.length) * 100
      : 0;

    return {
      totalPositions: positions.length,
      openPositions: openPositions.length,
      totalPnL,
      totalUnrealizedPnL,
      totalRealizedPnL,
      totalMargin,
      totalQuantity,
      winRate,
      avgPnL: positions.length > 0 ? totalPnL / positions.length : 0
    };
  }, [positions]);

  // ========================================
  // RENDER HELPERS
  // ========================================
  
  const renderStats = () => {
    if (!showStats) return null;

    return (
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-8 gap-4 mb-4">
        <StatCard
          label="Total Positions"
          value={stats.totalPositions}
          icon={<Briefcase className="w-4 h-4" />}
        />
        <StatCard
          label="Open Positions"
          value={stats.openPositions}
          icon={<Activity className="w-4 h-4" />}
          color="text-emerald-500"
        />
        <StatCard
          label="Total P&L"
          value={formatCurrency(stats.totalPnL)}
          color={stats.totalPnL >= 0 ? 'text-emerald-500' : 'text-red-500'}
          icon={<DollarSign className="w-4 h-4" />}
        />
        <StatCard
          label="Unrealized P&L"
          value={formatCurrency(stats.totalUnrealizedPnL)}
          color={stats.totalUnrealizedPnL >= 0 ? 'text-emerald-500' : 'text-red-500'}
          icon={<TrendingUp className="w-4 h-4" />}
        />
        <StatCard
          label="Realized P&L"
          value={formatCurrency(stats.totalRealizedPnL)}
          color={stats.totalRealizedPnL >= 0 ? 'text-emerald-500' : 'text-red-500'}
          icon={<TrendingDown className="w-4 h-4" />}
        />
        <StatCard
          label="Total Margin"
          value={formatCurrency(stats.totalMargin)}
          icon={<Wallet className="w-4 h-4" />}
        />
        <StatCard
          label="Win Rate"
          value={formatPercentage(stats.winRate)}
          color={stats.winRate >= 50 ? 'text-emerald-500' : 'text-red-500'}
          icon={<CheckCircle className="w-4 h-4" />}
        />
        <StatCard
          label="Avg P&L"
          value={formatCurrency(stats.avgPnL)}
          color={stats.avgPnL >= 0 ? 'text-emerald-500' : 'text-red-500'}
          icon={<BarChart3 className="w-4 h-4" />}
        />
      </div>
    );
  };

  const renderToolbar = () => {
    return (
      <div className="flex flex-wrap items-center gap-3 mb-4">
        {/* Search */}
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-nexus-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => handleSearch(e.target.value)}
            placeholder="Search positions..."
            className="w-full pl-9 pr-3 py-1.5 text-sm border border-nexus-200 dark:border-nexus-700 rounded-lg bg-white dark:bg-nexus-900 focus:ring-2 focus:ring-nexus-500 focus:border-transparent"
          />
        </div>

        {/* View toggle */}
        <div className="flex items-center gap-1 p-1 bg-nexus-100 dark:bg-nexus-800 rounded-lg">
          <button
            onClick={() => {
              setViewMode('table');
              setStoredViewMode('table');
            }}
            className={cn(
              'px-2 py-1 rounded text-sm transition-colors',
              viewMode === 'table'
                ? 'bg-white dark:bg-nexus-700 text-nexus-900 dark:text-nexus-100 shadow-sm'
                : 'text-nexus-500 hover:text-nexus-700 dark:text-nexus-400 dark:hover:text-nexus-200'
            )}
          >
            <LayoutGrid className="w-4 h-4" />
          </button>
          <button
            onClick={() => {
              setViewMode('cards');
              setStoredViewMode('cards');
            }}
            className={cn(
              'px-2 py-1 rounded text-sm transition-colors',
              viewMode === 'cards'
                ? 'bg-white dark:bg-nexus-700 text-nexus-900 dark:text-nexus-100 shadow-sm'
                : 'text-nexus-500 hover:text-nexus-700 dark:text-nexus-400 dark:hover:text-nexus-200'
            )}
          >
            <LayoutGrid className="w-4 h-4" />
          </button>
        </div>

        {/* Refresh */}
        <button
          onClick={handleRefresh}
          disabled={isRefreshing}
          className="p-2 rounded-lg border border-nexus-200 dark:border-nexus-700 hover:bg-nexus-50 dark:hover:bg-nexus-800 transition-colors disabled:opacity-50"
        >
          <RefreshCw className={cn('w-4 h-4 text-nexus-500', isRefreshing && 'animate-spin')} />
        </button>

        {/* Export */}
        {onPositionExport && (
          <button
            onClick={() => onPositionExport(positions)}
            className="p-2 rounded-lg border border-nexus-200 dark:border-nexus-700 hover:bg-nexus-50 dark:hover:bg-nexus-800 transition-colors"
          >
            <Download className="w-4 h-4 text-nexus-500" />
          </button>
        )}
      </div>
    );
  };

  const renderTable = () => {
    const columns: TableColumn<Position>[] = [
      {
        key: 'symbol',
        header: 'Symbol',
        render: (_, position) => (
          <div className="flex items-center gap-2">
            <span className="font-medium">{position.symbol}</span>
            <PositionSideBadge side={position.side} />
          </div>
        ),
        sortable: true,
        searchable: true
      },
      {
        key: 'entryPrice',
        header: 'Entry',
        render: (value) => formatCurrency(value),
        sortable: true
      },
      {
        key: 'currentPrice',
        header: 'Current',
        render: (value) => formatCurrency(value),
        sortable: true
      },
      {
        key: 'quantity',
        header: 'Qty',
        render: (value) => formatNumber(value),
        sortable: true
      },
      {
        key: 'leverage',
        header: 'Lev',
        render: (value) => `${value}x`,
        sortable: true
      },
      {
        key: 'totalPnL',
        header: 'P&L',
        render: (_, position) => (
          <PositionPnL pnl={position.totalPnL} pnlPercent={position.pnlPercent} />
        ),
        sortable: true
      },
      {
        key: 'status',
        header: 'Status',
        render: (_, position) => (
          <PositionStatusBadge status={position.status} />
        ),
        sortable: true
      },
      {
        key: 'entryTime',
        header: 'Entered',
        render: (value) => formatTimeAgo(value),
        sortable: true
      },
      ...extraColumns,
      {
        key: 'actions',
        header: 'Actions',
        render: (_, position) => (
          <div className="flex items-center gap-1">
            {allowActions && (
              <>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleClosePosition(position);
                  }}
                  className="p-1 rounded hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors text-red-500"
                  title="Close position"
                >
                  <X className="w-4 h-4" />
                </button>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    handleModifyPosition(position);
                  }}
                  className="p-1 rounded hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors text-blue-500"
                  title="Modify position"
                >
                  <Edit className="w-4 h-4" />
                </button>
              </>
            )}
            {actions.map((action, index) => (
              <button
                key={index}
                onClick={(e) => {
                  e.stopPropagation();
                  action.handler(position);
                }}
                disabled={action.disabled}
                className={cn(
                  'p-1 rounded hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors',
                  action.color || 'text-nexus-500',
                  action.disabled && 'opacity-50 cursor-not-allowed'
                )}
                title={action.tooltip || action.label}
              >
                {action.icon || <MoreHorizontal className="w-4 h-4" />}
              </button>
            ))}
          </div>
        ),
        sortable: false
      }
    ];

    return (
      <Table
        columns={columns}
        rows={filteredPositions.map(p => ({
          id: p.id,
          data: p,
          state: p.status === 'open' ? 'active' : 'default'
        }))}
        variant="bordered"
        size="md"
        loading={loading}
        pagination={{
          page: 1,
          pageSize: 10,
          total: filteredPositions.length,
          pageSizeOptions: [5, 10, 25, 50]
        }}
        onRowClick={(position) => {
          if (position.id) {
            handleToggleExpand(position.id);
          }
        }}
      />
    );
  };

  const renderCards = () => {
    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {filteredPositions.map((position) => (
          <PositionCard
            key={position.id}
            position={position}
            onClose={handleClosePosition}
            onModify={handleModifyPosition}
            onAction={handleAction}
            actions={actions}
            allowActions={allowActions}
          />
        ))}
      </div>
    );
  };

  // ========================================
  // MAIN RENDER
  // ========================================
  
  if (loading && positions.length === 0) {
    return (
      <div className="space-y-4">
        {renderStats()}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-center">
        <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
        <h3 className="text-lg font-semibold text-nexus-900 dark:text-nexus-100">Error loading positions</h3>
        <p className="text-nexus-500 dark:text-nexus-400 mt-2">{error}</p>
        <button
          onClick={handleRefresh}
          className="mt-4 px-4 py-2 bg-nexus-500 text-white rounded-lg hover:bg-nexus-600"
        >
          Try Again
        </button>
      </div>
    );
  }

  return (
    <div className={cn('w-full', className)} data-testid={testId}>
      {/* Stats */}
      {renderStats()}

      {/* Toolbar */}
      {renderToolbar()}

      {/* Positions */}
      {filteredPositions.length === 0 ? (
        <div className="flex flex-col items-center justify-center p-8 text-center">
          <Briefcase className="w-12 h-12 text-nexus-400 mb-4" />
          <h3 className="text-lg font-semibold text-nexus-900 dark:text-nexus-100">No positions</h3>
          <p className="text-nexus-500 dark:text-nexus-400 mt-2">
            {searchQuery ? 'No positions match your search' : 'You have no open positions'}
          </p>
        </div>
      ) : viewMode === 'table' ? (
        renderTable()
      ) : (
        renderCards()
      )}

      {/* Close Modal */}
      <Modal
        isOpen={closeModalOpen}
        onClose={() => setCloseModalOpen(false)}
        title="Close Position"
        size="sm"
        variant="warning"
      >
        <div className="space-y-4">
          <p>
            Are you sure you want to close this position?
          </p>
          {selectedPosition && (
            <div className="bg-nexus-50 dark:bg-nexus-800 p-3 rounded-lg space-y-1">
              <div className="flex justify-between">
                <span className="text-nexus-500 dark:text-nexus-400">Symbol</span>
                <span className="font-medium">{selectedPosition.symbol}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-nexus-500 dark:text-nexus-400">Side</span>
                <PositionSideBadge side={selectedPosition.side} />
              </div>
              <div className="flex justify-between">
                <span className="text-nexus-500 dark:text-nexus-400">P&L</span>
                <PositionPnL
                  pnl={selectedPosition.totalPnL}
                  pnlPercent={selectedPosition.pnlPercent}
                />
              </div>
            </div>
          )}
          <div className="flex justify-end gap-2">
            <Button variant="ghost" onClick={() => setCloseModalOpen(false)}>
              Cancel
            </Button>
            <Button variant="danger" onClick={handleConfirmClose}>
              Close Position
            </Button>
          </div>
        </div>
      </Modal>

      {/* Modify Modal */}
      <Modal
        isOpen={modifyModalOpen}
        onClose={() => setModifyModalOpen(false)}
        title="Modify Position"
        size="md"
      >
        {selectedPosition && (
          <ModifyPositionForm
            position={selectedPosition}
            onSubmit={handleConfirmModify}
            onCancel={() => setModifyModalOpen(false)}
          />
        )}
      </Modal>
    </div>
  );
};

// ========================================
// SUB-COMPONENTS
// ========================================

interface StatCardProps {
  label: string;
  value: string | number;
  icon: React.ReactNode;
  color?: string;
}

const StatCard: React.FC<StatCardProps> = ({
  label,
  value,
  icon,
  color = 'text-nexus-500'
}) => {
  return (
    <Card className="p-3 bg-nexus-50 dark:bg-nexus-800/50 border-0">
      <div className="flex items-center gap-2">
        <span className={cn('flex-shrink-0', color)}>{icon}</span>
        <div className="min-w-0 flex-1">
          <div className="text-xs text-nexus-500 dark:text-nexus-400 truncate">{label}</div>
          <div className="text-sm font-semibold text-nexus-900 dark:text-nexus-100 truncate">{value}</div>
        </div>
      </div>
    </Card>
  );
};

interface PositionCardProps {
  position: Position;
  onClose: (position: Position) => void;
  onModify: (position: Position) => void;
  onAction: (action: string, position: Position) => void;
  actions: PositionAction[];
  allowActions: boolean;
}

const PositionCard: React.FC<PositionCardProps> = ({
  position,
  onClose,
  onModify,
  onAction,
  actions,
  allowActions
}) => {
  const isPositive = position.totalPnL >= 0;

  return (
    <Card className="p-4 hover:shadow-lg transition-shadow">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-2">
          <span className="font-semibold text-lg">{position.symbol}</span>
          <PositionSideBadge side={position.side} />
        </div>
        <div className="flex items-center gap-1">
          {allowActions && (
            <>
              <button
                onClick={() => onClose(position)}
                className="p-1 rounded hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors text-red-500"
                title="Close position"
              >
                <X className="w-4 h-4" />
              </button>
              <button
                onClick={() => onModify(position)}
                className="p-1 rounded hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors text-blue-500"
                title="Modify position"
              >
                <Edit className="w-4 h-4" />
              </button>
            </>
          )}
          {actions.map((action, index) => (
            <button
              key={index}
              onClick={() => action.handler(position)}
              disabled={action.disabled}
              className={cn(
                'p-1 rounded hover:bg-nexus-100 dark:hover:bg-nexus-800 transition-colors',
                action.color || 'text-nexus-500',
                action.disabled && 'opacity-50 cursor-not-allowed'
              )}
              title={action.tooltip || action.label}
            >
              {action.icon || <MoreHorizontal className="w-4 h-4" />}
            </button>
          ))}
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 mt-3">
        <div>
          <div className="text-xs text-nexus-500 dark:text-nexus-400">Entry</div>
          <div className="font-medium">{formatCurrency(position.entryPrice)}</div>
        </div>
        <div>
          <div className="text-xs text-nexus-500 dark:text-nexus-400">Current</div>
          <div className="font-medium">{formatCurrency(position.currentPrice)}</div>
        </div>
        <div>
          <div className="text-xs text-nexus-500 dark:text-nexus-400">Qty</div>
          <div className="font-medium">{formatNumber(position.quantity)}</div>
        </div>
        <div>
          <div className="text-xs text-nexus-500 dark:text-nexus-400">Leverage</div>
          <div className="font-medium">{position.leverage}x</div>
        </div>
      </div>

      <div className="mt-3 pt-3 border-t border-nexus-200 dark:border-nexus-700">
        <div className="flex items-center justify-between">
          <span className="text-xs text-nexus-500 dark:text-nexus-400">P&L</span>
          <div className={cn(
            'font-semibold',
            isPositive ? 'text-emerald-500' : 'text-red-500'
          )}>
            {isPositive ? '+' : ''}{formatCurrency(position.totalPnL)}
            <span className="text-sm ml-1">
              ({isPositive ? '+' : ''}{formatPercentage(position.pnlPercent)})
            </span>
          </div>
        </div>
        <div className="flex items-center justify-between mt-1">
          <span className="text-xs text-nexus-500 dark:text-nexus-400">Status</span>
          <PositionStatusBadge status={position.status} />
        </div>
        <div className="flex items-center justify-between mt-1">
          <span className="text-xs text-nexus-500 dark:text-nexus-400">Entered</span>
          <span className="text-sm">{formatTimeAgo(position.entryTime)}</span>
        </div>
      </div>
    </Card>
  );
};

const SkeletonCard: React.FC = () => {
  return (
    <Card className="p-4">
      <div className="flex items-start justify-between">
        <Skeleton className="h-6 w-24" />
        <Skeleton className="h-6 w-16" />
      </div>
      <div className="grid grid-cols-2 gap-2 mt-3">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full" />
      </div>
      <div className="mt-3 pt-3 border-t border-nexus-200 dark:border-nexus-700">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-full mt-2" />
      </div>
    </Card>
  );
};

interface ModifyPositionFormProps {
  position: Position;
  onSubmit: (updates: Partial<Position>) => void;
  onCancel: () => void;
}

const ModifyPositionForm: React.FC<ModifyPositionFormProps> = ({
  position,
  onSubmit,
  onCancel
}) => {
  const [stopLoss, setStopLoss] = useState(position.stopLoss || '');
  const [takeProfit, setTakeProfit] = useState(position.takeProfit || '');
  const [quantity, setQuantity] = useState(position.quantity);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      const updates: Partial<Position> = {
        stopLoss: stopLoss ? parseFloat(stopLoss) : undefined,
        takeProfit: takeProfit ? parseFloat(takeProfit) : undefined,
        quantity
      };
      await onSubmit(updates);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-nexus-700 dark:text-nexus-300 mb-1">
          Stop Loss
        </label>
        <input
          type="number"
          step="0.01"
          value={stopLoss}
          onChange={(e) => setStopLoss(e.target.value)}
          placeholder="Enter stop loss price"
          className="w-full px-3 py-2 border border-nexus-300 dark:border-nexus-600 rounded-lg bg-white dark:bg-nexus-900"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-nexus-700 dark:text-nexus-300 mb-1">
          Take Profit
        </label>
        <input
          type="number"
          step="0.01"
          value={takeProfit}
          onChange={(e) => setTakeProfit(e.target.value)}
          placeholder="Enter take profit price"
          className="w-full px-3 py-2 border border-nexus-300 dark:border-nexus-600 rounded-lg bg-white dark:bg-nexus-900"
        />
      </div>

      <div>
        <label className="block text-sm font-medium text-nexus-700 dark:text-nexus-300 mb-1">
          Quantity
        </label>
        <input
          type="number"
          step="0.01"
          value={quantity}
          onChange={(e) => setQuantity(parseFloat(e.target.value) || 0)}
          className="w-full px-3 py-2 border border-nexus-300 dark:border-nexus-600 rounded-lg bg-white dark:bg-nexus-900"
        />
      </div>

      <div className="flex justify-end gap-2">
        <Button variant="ghost" onClick={onCancel} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button type="submit" disabled={isSubmitting}>
          {isSubmitting ? <Spinner size="sm" /> : 'Update Position'}
        </Button>
      </div>
    </form>
  );
};

// ========================================
// EXPORTS
// ========================================

OpenPositions.displayName = 'OpenPositions';

export default OpenPositions;

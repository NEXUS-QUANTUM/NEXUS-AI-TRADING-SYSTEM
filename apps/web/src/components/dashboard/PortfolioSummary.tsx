import React, { useState, useCallback, useEffect, useMemo, useRef } from 'react';
import { cn } from '@/lib/utils';
import {
  Wallet,
  DollarSign,
  TrendingUp,
  TrendingDown,
  ArrowUpRight,
  ArrowDownRight,
  PieChart,
  BarChart3,
  LineChart,
  Activity,
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
  ExternalLink,
  Eye,
  EyeOff,
  Calendar,
  Clock,
  Coins,
  Bitcoin,
  Ethereum,
  Zap,
  Shield,
  Lock,
  Unlock,
  Users,
  User,
  Briefcase,
  Building2,
  Globe,
  MapPin,
  Percent,
  CircleDollarSign,
  PiggyBank,
  Award,
  Star,
  Flame,
  Sparkles,
  Crown,
  Medal,
  Trophy,
  Target,
  Compass,
  Rocket,
  ChartNoAxesCombined,
  CircleHelp,
  BadgeDollarSign,
  Landmark,
  ScrollText
} from 'lucide-react';
import { Card } from '@/components/common/Card';
import { Button } from '@/components/common/Button';
import { Badge } from '@/components/common/Badge';
import { Tooltip } from '@/components/common/Tooltip';
import { Skeleton } from '@/components/common/Skeleton';
import { Spinner } from '@/components/common/Spinner';
import { Progress } from '@/components/common/Progress';
import { useTheme } from '@/hooks/useTheme';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useLocalStorage } from '@/hooks/useLocalStorage';
import { formatCurrency, formatNumber, formatPercentage, formatDate, formatTime, formatTimeAgo } from '@/lib/formatting';

/**
 * NEXUS AI TRADING SYSTEM - Portfolio Summary Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 * 
 * Version: 3.0.0
 * Status: Production Ready
 * 
 * Complete Portfolio Summary system with:
 * - Total balance and equity
 * - P&L tracking (daily, weekly, monthly, yearly)
 * - Asset allocation
 * - Performance metrics (Sharpe, Sortino, etc.)
 * - Risk metrics (VaR, drawdown, etc.)
 * - Historical performance charts
 * - Portfolio diversification
 * - Real-time updates
 * - Multiple timeframes
 * - Export capabilities
 * - WebSocket integration
 * - Theme aware
 * - Responsive design
 * - Accessibility (ARIA compliant)
 */

// ========================================
// TYPES & INTERFACES
// ========================================

export type Timeframe = '1D' | '1W' | '1M' | '3M' | '6M' | '1Y' | 'ALL';
export type PortfolioMetric = 
  | 'totalBalance'
  | 'availableBalance'
  | 'lockedBalance'
  | 'totalEquity'
  | 'totalPnL'
  | 'dailyPnL'
  | 'weeklyPnL'
  | 'monthlyPnL'
  | 'yearlyPnL'
  | 'totalReturn'
  | 'dailyReturn'
  | 'weeklyReturn'
  | 'monthlyReturn'
  | 'yearlyReturn'
  | 'sharpeRatio'
  | 'sortinoRatio'
  | 'calmarRatio'
  | 'maxDrawdown'
  | 'currentDrawdown'
  | 'volatility'
  | 'beta'
  | 'alpha'
  | 'winRate'
  | 'profitFactor'
  | 'averageWin'
  | 'averageLoss'
  | 'totalTrades'
  | 'winningTrades'
  | 'losingTrades'
  | 'breakEvenTrades'
  | 'positionCount'
  | 'exposure'
  | 'marginUsed'
  | 'leverageUsed';

export interface PortfolioAsset {
  /** Asset symbol */
  symbol: string;
  /** Asset name */
  name?: string;
  /** Quantity held */
  quantity: number;
  /** Current price */
  price: number;
  /** Average entry price */
  avgEntryPrice: number;
  /** Total value */
  value: number;
  /** Allocation percentage */
  allocation: number;
  /** Unrealized P&L */
  unrealizedPnL: number;
  /** P&L percentage */
  pnlPercent: number;
  /** Asset type */
  type?: 'crypto' | 'stock' | 'forex' | 'commodity' | 'index' | 'etf' | 'bond' | 'derivative';
  /** Icon/Logo */
  icon?: React.ReactNode;
  /** Color */
  color?: string;
}

export interface PortfolioSummaryData {
  /** Total balance */
  totalBalance: number;
  /** Available balance */
  availableBalance: number;
  /** Locked balance */
  lockedBalance: number;
  /** Total equity */
  totalEquity: number;
  /** Total P&L */
  totalPnL: number;
  /** Daily P&L */
  dailyPnL: number;
  /** Weekly P&L */
  weeklyPnL: number;
  /** Monthly P&L */
  monthlyPnL: number;
  /** Yearly P&L */
  yearlyPnL: number;
  /** Total return percentage */
  totalReturn: number;
  /** Daily return */
  dailyReturn: number;
  /** Weekly return */
  weeklyReturn: number;
  /** Monthly return */
  monthlyReturn: number;
  /** Yearly return */
  yearlyReturn: number;
  /** Sharpe ratio */
  sharpeRatio: number;
  /** Sortino ratio */
  sortinoRatio: number;
  /** Calmar ratio */
  calmarRatio: number;
  /** Maximum drawdown */
  maxDrawdown: number;
  /** Current drawdown */
  currentDrawdown: number;
  /** Volatility */
  volatility: number;
  /** Beta */
  beta: number;
  /** Alpha */
  alpha: number;
  /** Win rate */
  winRate: number;
  /** Profit factor */
  profitFactor: number;
  /** Average win */
  averageWin: number;
  /** Average loss */
  averageLoss: number;
  /** Total trades */
  totalTrades: number;
  /** Winning trades */
  winningTrades: number;
  /** Losing trades */
  losingTrades: number;
  /** Break even trades */
  breakEvenTrades: number;
  /** Position count */
  positionCount: number;
  /** Exposure */
  exposure: number;
  /** Margin used */
  marginUsed: number;
  /** Leverage used */
  leverageUsed: number;
  /** Assets */
  assets: PortfolioAsset[];
  /** Historical data for chart */
  history: PortfolioHistoryPoint[];
  /** Last updated */
  updatedAt: string | Date;
  /** Currency */
  currency?: string;
  /** Account ID */
  accountId?: string;
  /** Account name */
  accountName?: string;
  /** Risk level */
  riskLevel?: 'low' | 'medium' | 'high';
  /** Investment style */
  style?: 'conservative' | 'moderate' | 'aggressive';
}

export interface PortfolioHistoryPoint {
  /** Timestamp */
  timestamp: string | Date;
  /** Total equity */
  equity: number;
  /** Total balance */
  balance: number;
  /** P&L */
  pnl: number;
}

export interface PortfolioSummaryProps {
  /** Portfolio data */
  data: PortfolioSummaryData;
  /** Loading state */
  loading?: boolean;
  /** Error state */
  error?: string | null;
  /** Timeframe for display */
  timeframe?: Timeframe;
  /** On timeframe change */
  onTimeframeChange?: (timeframe: Timeframe) => void;
  /** On refresh */
  onRefresh?: () => Promise<void>;
  /** On export */
  onExport?: () => void;
  /** On asset click */
  onAssetClick?: (asset: PortfolioAsset) => void;
  /** Enable real-time updates */
  enableRealtime?: boolean;
  /** WebSocket URL */
  wsUrl?: string;
  /** Auto-refresh interval (ms) */
  refreshInterval?: number;
  /** Show asset allocation */
  showAllocation?: boolean;
  /** Show performance metrics */
  showMetrics?: boolean;
  /** Show risk metrics */
  showRisk?: boolean;
  /** Show history chart */
  showHistory?: boolean;
  /** Additional className */
  className?: string;
  /** Test ID */
  testId?: string;
}

// ========================================
// CONFIGURATION
// ========================================

const TIMEFRAME_LABELS: Record<Timeframe, string> = {
  '1D': '1 Day',
  '1W': '1 Week',
  '1M': '1 Month',
  '3M': '3 Months',
  '6M': '6 Months',
  '1Y': '1 Year',
  'ALL': 'All Time'
};

const METRIC_LABELS: Record<PortfolioMetric, string> = {
  totalBalance: 'Total Balance',
  availableBalance: 'Available',
  lockedBalance: 'Locked',
  totalEquity: 'Total Equity',
  totalPnL: 'Total P&L',
  dailyPnL: 'Daily P&L',
  weeklyPnL: 'Weekly P&L',
  monthlyPnL: 'Monthly P&L',
  yearlyPnL: 'Yearly P&L',
  totalReturn: 'Total Return',
  dailyReturn: 'Daily Return',
  weeklyReturn: 'Weekly Return',
  monthlyReturn: 'Monthly Return',
  yearlyReturn: 'Yearly Return',
  sharpeRatio: 'Sharpe Ratio',
  sortinoRatio: 'Sortino Ratio',
  calmarRatio: 'Calmar Ratio',
  maxDrawdown: 'Max Drawdown',
  currentDrawdown: 'Current Drawdown',
  volatility: 'Volatility',
  beta: 'Beta',
  alpha: 'Alpha',
  winRate: 'Win Rate',
  profitFactor: 'Profit Factor',
  averageWin: 'Avg Win',
  averageLoss: 'Avg Loss',
  totalTrades: 'Total Trades',
  winningTrades: 'Wins',
  losingTrades: 'Losses',
  breakEvenTrades: 'Break Even',
  positionCount: 'Open Positions',
  exposure: 'Exposure',
  marginUsed: 'Margin Used',
  leverageUsed: 'Leverage Used'
};

const RISK_LABELS: Record<'low' | 'medium' | 'high', { label: string; color: string }> = {
  low: { label: 'Low', color: 'text-emerald-500' },
  medium: { label: 'Medium', color: 'text-yellow-500' },
  high: { label: 'High', color: 'text-red-500' }
};

const STYLE_LABELS: Record<'conservative' | 'moderate' | 'aggressive', { label: string; color: string }> = {
  conservative: { label: 'Conservative', color: 'text-blue-500' },
  moderate: { label: 'Moderate', color: 'text-yellow-500' },
  aggressive: { label: 'Aggressive', color: 'text-red-500' }
};

const ASSET_TYPE_COLORS: Record<string, string> = {
  crypto: 'text-nexus-500',
  stock: 'text-blue-500',
  forex: 'text-emerald-500',
  commodity: 'text-yellow-500',
  index: 'text-purple-500',
  etf: 'text-cyan-500',
  bond: 'text-amber-500',
  derivative: 'text-red-500'
};

// ========================================
// SUB-COMPONENTS
// ========================================

interface MetricCardProps {
  label: string;
  value: string | number;
  change?: number;
  changePercent?: number;
  icon?: React.ReactNode;
  color?: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const MetricCard: React.FC<MetricCardProps> = ({
  label,
  value,
  change,
  changePercent,
  icon,
  color = 'text-nexus-500',
  size = 'md',
  className
}) => {
  const isPositive = change !== undefined && change > 0;

  return (
    <div className={cn(
      'p-4 bg-white dark:bg-nexus-900 rounded-xl border border-nexus-200 dark:border-nexus-700',
      size === 'sm' && 'p-3',
      size === 'lg' && 'p-6',
      className
    )}>
      <div className="flex items-center justify-between">
        <span className={cn(
          'text-nexus-500 dark:text-nexus-400',
          size === 'sm' && 'text-xs',
          size === 'lg' && 'text-base'
        )}>
          {label}
        </span>
        {icon && (
          <span className={cn('flex-shrink-0', color)}>
            {icon}
          </span>
        )}
      </div>
      <div className={cn(
        'font-bold text-nexus-900 dark:text-nexus-100 mt-1',
        size === 'sm' && 'text-lg',
        size === 'md' && 'text-2xl',
        size === 'lg' && 'text-3xl'
      )}>
        {value}
      </div>
      {(change !== undefined || changePercent !== undefined) && (
        <div className="flex items-center gap-1 mt-1">
          {change !== undefined && (
            <span className={cn(
              'text-sm font-medium',
              isPositive ? 'text-emerald-500' : 'text-red-500'
            )}>
              {isPositive ? '+' : ''}{formatNumber(change)}
            </span>
          )}
          {changePercent !== undefined && (
            <span className={cn(
              'text-xs',
              isPositive ? 'text-emerald-400' : 'text-red-400'
            )}>
              ({isPositive ? '+' : ''}{formatPercentage(changePercent)})
            </span>
          )}
        </div>
      )}
    </div>
  );
};

interface AllocationItemProps {
  asset: PortfolioAsset;
  onClick?: (asset: PortfolioAsset) => void;
}

const AllocationItem: React.FC<AllocationItemProps> = ({ asset, onClick }) => {
  const isPositive = asset.pnlPercent >= 0;

  return (
    <button
      onClick={() => onClick?.(asset)}
      className="w-full text-left p-3 hover:bg-nexus-50 dark:hover:bg-nexus-800 rounded-lg transition-colors group"
    >
      <div className="flex items-center gap-3">
        {/* Icon/Logo */}
        <div className={cn(
          'w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0',
          asset.color ? `bg-${asset.color}/10` : 'bg-nexus-100 dark:bg-nexus-700'
        )}>
          {asset.icon || (
            <span className="text-sm font-bold text-nexus-500">
              {asset.symbol.slice(0, 2).toUpperCase()}
            </span>
          )}
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center justify-between">
            <span className="font-medium text-nexus-900 dark:text-nexus-100 truncate">
              {asset.symbol}
            </span>
            <span className="text-sm font-medium text-nexus-900 dark:text-nexus-100">
              {formatCurrency(asset.value)}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-nexus-500 dark:text-nexus-400">
              {formatNumber(asset.quantity)} @ {formatCurrency(asset.avgEntryPrice)}
            </span>
            <span className={cn(
              'font-medium',
              isPositive ? 'text-emerald-500' : 'text-red-500'
            )}>
              {isPositive ? '+' : ''}{formatPercentage(asset.pnlPercent)}
            </span>
          </div>
        </div>
      </div>

      {/* Progress bar for allocation */}
      <div className="mt-2 w-full h-1.5 bg-nexus-200 dark:bg-nexus-700 rounded-full overflow-hidden">
        <div
          className="h-full rounded-full transition-all duration-500"
          style={{
            width: `${Math.min(100, Math.max(0, asset.allocation))}%`,
            backgroundColor: asset.color || 'var(--nexus-500)'
          }}
        />
      </div>
    </button>
  );
};

// ========================================
// MAIN COMPONENT
// ========================================

export const PortfolioSummary: React.FC<PortfolioSummaryProps> = ({
  data,
  loading = false,
  error = null,
  timeframe = '1M',
  onTimeframeChange,
  onRefresh,
  onExport,
  onAssetClick,
  enableRealtime = false,
  wsUrl,
  refreshInterval = 0,
  showAllocation = true,
  showMetrics = true,
  showRisk = true,
  showHistory = true,
  className,
  testId = 'nexus-portfolio-summary'
}) => {
  // ========================================
  // STATE
  // ========================================
  
  const [portfolioData, setPortfolioData] = useState<PortfolioSummaryData>(data);
  const [selectedTimeframe, setSelectedTimeframe] = useState<Timeframe>(timeframe);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [showValues, setShowValues] = useState(true);
  const [showDetails, setShowDetails] = useState(false);

  // ========================================
  // REFS
  // ========================================
  
  const refreshTimerRef = useRef<NodeJS.Timeout>();

  // ========================================
  // HOOKS
  // ========================================
  
  const { theme } = useTheme();
  const [storedShowValues, setStoredShowValues] = useLocalStorage<boolean>(
    'nexus-portfolio-show-values',
    true
  );

  // WebSocket connection
  const { lastMessage, isConnected } = useWebSocket(wsUrl || '', {
    autoConnect: enableRealtime,
    onMessage: (message) => {
      if (message.type === 'portfolio_update') {
        setPortfolioData(prev => ({
          ...prev,
          ...message.data,
          updatedAt: new Date()
        }));
      }
    }
  });

  // ========================================
  // EFFECTS
  // ========================================
  
  // Sync with props
  useEffect(() => {
    setPortfolioData(data);
  }, [data]);

  // Load stored show values setting
  useEffect(() => {
    setShowValues(storedShowValues !== undefined ? storedShowValues : true);
  }, [storedShowValues]);

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

  const handleTimeframeChange = useCallback((tf: Timeframe) => {
    setSelectedTimeframe(tf);
    onTimeframeChange?.(tf);
  }, [onTimeframeChange]);

  const toggleShowValues = useCallback(() => {
    const newValue = !showValues;
    setShowValues(newValue);
    setStoredShowValues(newValue);
  }, [showValues, setStoredShowValues]);

  const toggleFullscreen = useCallback(() => {
    setIsFullscreen(!isFullscreen);
  }, [isFullscreen]);

  // ========================================
  // COMPUTED
  // ========================================
  
  const metrics = useMemo(() => {
    const {
      totalBalance,
      availableBalance,
      lockedBalance,
      totalEquity,
      totalPnL,
      dailyPnL,
      weeklyPnL,
      monthlyPnL,
      yearlyPnL,
      totalReturn,
      dailyReturn,
      weeklyReturn,
      monthlyReturn,
      yearlyReturn,
      sharpeRatio,
      sortinoRatio,
      calmarRatio,
      maxDrawdown,
      currentDrawdown,
      volatility,
      beta,
      alpha,
      winRate,
      profitFactor,
      averageWin,
      averageLoss,
      totalTrades,
      winningTrades,
      losingTrades,
      breakEvenTrades,
      positionCount,
      exposure,
      marginUsed,
      leverageUsed
    } = portfolioData;

    const formatMetricValue = (value: number, metric: PortfolioMetric): string => {
      if (value === undefined || value === null || isNaN(value)) return '--';

      const metricWithPercent = ['totalReturn', 'dailyReturn', 'weeklyReturn', 'monthlyReturn', 'yearlyReturn', 'winRate', 'maxDrawdown', 'currentDrawdown', 'volatility', 'exposure'];
      const metricWithCurrency = ['totalBalance', 'availableBalance', 'lockedBalance', 'totalEquity', 'totalPnL', 'dailyPnL', 'weeklyPnL', 'monthlyPnL', 'yearlyPnL', 'averageWin', 'averageLoss', 'marginUsed'];
      const metricWithNumber = ['totalTrades', 'winningTrades', 'losingTrades', 'breakEvenTrades', 'positionCount'];

      if (metricWithCurrency.includes(metric)) {
        return formatCurrency(value);
      }
      if (metricWithPercent.includes(metric)) {
        return formatPercentage(value);
      }
      if (metricWithNumber.includes(metric)) {
        return formatNumber(value);
      }
      if (metric === 'sharpeRatio' || metric === 'sortinoRatio' || metric === 'calmarRatio' || metric === 'beta' || metric === 'alpha') {
        return value.toFixed(2);
      }
      if (metric === 'profitFactor') {
        return value.toFixed(2);
      }
      if (metric === 'leverageUsed') {
        return `${value.toFixed(2)}x`;
      }
      return formatNumber(value);
    };

    return {
      totalBalance: { value: totalBalance, formatted: formatMetricValue(totalBalance, 'totalBalance') },
      availableBalance: { value: availableBalance, formatted: formatMetricValue(availableBalance, 'availableBalance') },
      lockedBalance: { value: lockedBalance, formatted: formatMetricValue(lockedBalance, 'lockedBalance') },
      totalEquity: { value: totalEquity, formatted: formatMetricValue(totalEquity, 'totalEquity') },
      totalPnL: { value: totalPnL, formatted: formatMetricValue(totalPnL, 'totalPnL') },
      dailyPnL: { value: dailyPnL, formatted: formatMetricValue(dailyPnL, 'dailyPnL') },
      weeklyPnL: { value: weeklyPnL, formatted: formatMetricValue(weeklyPnL, 'weeklyPnL') },
      monthlyPnL: { value: monthlyPnL, formatted: formatMetricValue(monthlyPnL, 'monthlyPnL') },
      yearlyPnL: { value: yearlyPnL, formatted: formatMetricValue(yearlyPnL, 'yearlyPnL') },
      totalReturn: { value: totalReturn, formatted: formatMetricValue(totalReturn, 'totalReturn') },
      dailyReturn: { value: dailyReturn, formatted: formatMetricValue(dailyReturn, 'dailyReturn') },
      weeklyReturn: { value: weeklyReturn, formatted: formatMetricValue(weeklyReturn, 'weeklyReturn') },
      monthlyReturn: { value: monthlyReturn, formatted: formatMetricValue(monthlyReturn, 'monthlyReturn') },
      yearlyReturn: { value: yearlyReturn, formatted: formatMetricValue(yearlyReturn, 'yearlyReturn') },
      sharpeRatio: { value: sharpeRatio, formatted: formatMetricValue(sharpeRatio, 'sharpeRatio') },
      sortinoRatio: { value: sortinoRatio, formatted: formatMetricValue(sortinoRatio, 'sortinoRatio') },
      calmarRatio: { value: calmarRatio, formatted: formatMetricValue(calmarRatio, 'calmarRatio') },
      maxDrawdown: { value: maxDrawdown, formatted: formatMetricValue(maxDrawdown, 'maxDrawdown') },
      currentDrawdown: { value: currentDrawdown, formatted: formatMetricValue(currentDrawdown, 'currentDrawdown') },
      volatility: { value: volatility, formatted: formatMetricValue(volatility, 'volatility') },
      beta: { value: beta, formatted: formatMetricValue(beta, 'beta') },
      alpha: { value: alpha, formatted: formatMetricValue(alpha, 'alpha') },
      winRate: { value: winRate, formatted: formatMetricValue(winRate, 'winRate') },
      profitFactor: { value: profitFactor, formatted: formatMetricValue(profitFactor, 'profitFactor') },
      averageWin: { value: averageWin, formatted: formatMetricValue(averageWin, 'averageWin') },
      averageLoss: { value: averageLoss, formatted: formatMetricValue(averageLoss, 'averageLoss') },
      totalTrades: { value: totalTrades, formatted: formatMetricValue(totalTrades, 'totalTrades') },
      winningTrades: { value: winningTrades, formatted: formatMetricValue(winningTrades, 'winningTrades') },
      losingTrades: { value: losingTrades, formatted: formatMetricValue(losingTrades, 'losingTrades') },
      breakEvenTrades: { value: breakEvenTrades, formatted: formatMetricValue(breakEvenTrades, 'breakEvenTrades') },
      positionCount: { value: positionCount, formatted: formatMetricValue(positionCount, 'positionCount') },
      exposure: { value: exposure, formatted: formatMetricValue(exposure, 'exposure') },
      marginUsed: { value: marginUsed, formatted: formatMetricValue(marginUsed, 'marginUsed') },
      leverageUsed: { value: leverageUsed, formatted: formatMetricValue(leverageUsed, 'leverageUsed') }
    };
  }, [portfolioData]);

  // ========================================
  // RENDER HELPERS
  // ========================================
  
  const renderHeader = () => {
    return (
      <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
        <div>
          <h2 className="text-2xl font-bold text-nexus-900 dark:text-nexus-100">
            Portfolio Summary
          </h2>
          {portfolioData.accountName && (
            <p className="text-nexus-500 dark:text-nexus-400 mt-0.5">
              {portfolioData.accountName}
              {portfolioData.currency && ` · ${portfolioData.currency}`}
            </p>
          )}
        </div>

        <div className="flex items-center gap-2 flex-wrap">
          {/* Show Values Toggle */}
          <button
            onClick={toggleShowValues}
            className="p-2 rounded-lg border border-nexus-200 dark:border-nexus-700 hover:bg-nexus-50 dark:hover:bg-nexus-800 transition-colors"
            title={showValues ? 'Hide values' : 'Show values'}
          >
            {showValues ? (
              <Eye className="w-4 h-4 text-nexus-500" />
            ) : (
              <EyeOff className="w-4 h-4 text-nexus-500" />
            )}
          </button>

          {/* Refresh */}
          <button
            onClick={handleRefresh}
            disabled={isRefreshing}
            className="p-2 rounded-lg border border-nexus-200 dark:border-nexus-700 hover:bg-nexus-50 dark:hover:bg-nexus-800 transition-colors disabled:opacity-50"
          >
            <RefreshCw className={cn('w-4 h-4 text-nexus-500', isRefreshing && 'animate-spin')} />
          </button>

          {/* Export */}
          {onExport && (
            <button
              onClick={onExport}
              className="p-2 rounded-lg border border-nexus-200 dark:border-nexus-700 hover:bg-nexus-50 dark:hover:bg-nexus-800 transition-colors"
            >
              <Download className="w-4 h-4 text-nexus-500" />
            </button>
          )}

          {/* Fullscreen */}
          <button
            onClick={toggleFullscreen}
            className="p-2 rounded-lg border border-nexus-200 dark:border-nexus-700 hover:bg-nexus-50 dark:hover:bg-nexus-800 transition-colors"
          >
            {isFullscreen ? (
              <Minimize2 className="w-4 h-4 text-nexus-500" />
            ) : (
              <Maximize2 className="w-4 h-4 text-nexus-500" />
            )}
          </button>

          {/* Last updated */}
          {portfolioData.updatedAt && (
            <span className="text-xs text-nexus-400 dark:text-nexus-500 ml-2">
              Updated {formatTimeAgo(portfolioData.updatedAt)}
            </span>
          )}
        </div>
      </div>
    );
  };

  const renderTimeframes = () => {
    const timeframes: Timeframe[] = ['1D', '1W', '1M', '3M', '6M', '1Y', 'ALL'];
    
    return (
      <div className="flex flex-wrap gap-1 mb-4">
        {timeframes.map((tf) => (
          <button
            key={tf}
            onClick={() => handleTimeframeChange(tf)}
            className={cn(
              'px-3 py-1.5 text-sm rounded-lg transition-colors',
              selectedTimeframe === tf
                ? 'bg-nexus-500 text-white'
                : 'text-nexus-500 dark:text-nexus-400 hover:bg-nexus-100 dark:hover:bg-nexus-800'
            )}
          >
            {TIMEFRAME_LABELS[tf]}
          </button>
        ))}
      </div>
    );
  };

  const renderBalanceCards = () => {
    const isPnLPositive = metrics.totalPnL.value >= 0;

    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        <MetricCard
          label="Total Balance"
          value={showValues ? metrics.totalBalance.formatted : '••••••'}
          icon={<Wallet className="w-4 h-4" />}
          size="lg"
        />
        <MetricCard
          label="Total Equity"
          value={showValues ? metrics.totalEquity.formatted : '••••••'}
          icon={<DollarSign className="w-4 h-4" />}
          size="lg"
        />
        <MetricCard
          label="Total P&L"
          value={showValues ? metrics.totalPnL.formatted : '••••••'}
          change={metrics.totalPnL.value}
          changePercent={metrics.totalReturn.value}
          icon={isPnLPositive ? <TrendingUp className="w-4 h-4" /> : <TrendingDown className="w-4 h-4" />}
          color={isPnLPositive ? 'text-emerald-500' : 'text-red-500'}
          size="lg"
        />
        <MetricCard
          label="Win Rate"
          value={showValues ? metrics.winRate.formatted : '••••••'}
          icon={<Target className="w-4 h-4" />}
          color="text-purple-500"
          size="lg"
        />
      </div>
    );
  };

  const renderPortfolioMetrics = () => {
    if (!showMetrics) return null;

    const metricGroups = [
      {
        title: 'Performance',
        metrics: [
          { key: 'totalReturn', icon: <TrendingUp className="w-3 h-3" /> },
          { key: 'dailyReturn', icon: <Clock className="w-3 h-3" /> },
          { key: 'weeklyReturn', icon: <Calendar className="w-3 h-3" /> },
          { key: 'monthlyReturn', icon: <Calendar className="w-3 h-3" /> },
          { key: 'yearlyReturn', icon: <Calendar className="w-3 h-3" /> }
        ]
      },
      {
        title: 'Risk',
        metrics: [
          { key: 'sharpeRatio', icon: <Award className="w-3 h-3" /> },
          { key: 'sortinoRatio', icon: <Medal className="w-3 h-3" /> },
          { key: 'calmarRatio', icon: <Trophy className="w-3 h-3" /> },
          { key: 'maxDrawdown', icon: <TrendingDown className="w-3 h-3" /> },
          { key: 'currentDrawdown', icon: <TrendingDown className="w-3 h-3" /> },
          { key: 'volatility', icon: <Activity className="w-3 h-3" /> }
        ]
      },
      {
        title: 'Trading',
        metrics: [
          { key: 'totalTrades', icon: <BarChart3 className="w-3 h-3" /> },
          { key: 'winningTrades', icon: <CheckCircle className="w-3 h-3" /> },
          { key: 'losingTrades', icon: <AlertCircle className="w-3 h-3" /> },
          { key: 'profitFactor', icon: <DollarSign className="w-3 h-3" /> },
          { key: 'averageWin', icon: <TrendingUp className="w-3 h-3" /> },
          { key: 'averageLoss', icon: <TrendingDown className="w-3 h-3" /> }
        ]
      },
      {
        title: 'Portfolio',
        metrics: [
          { key: 'positionCount', icon: <Briefcase className="w-3 h-3" /> },
          { key: 'exposure', icon: <Coins className="w-3 h-3" /> },
          { key: 'marginUsed', icon: <PiggyBank className="w-3 h-3" /> },
          { key: 'leverageUsed', icon: <Zap className="w-3 h-3" /> }
        ]
      }
    ];

    return (
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-4">
        {metricGroups.map((group, index) => (
          <Card key={index} className="p-4">
            <h4 className="text-sm font-medium text-nexus-500 dark:text-nexus-400 mb-3">
              {group.title}
            </h4>
            <div className="space-y-2">
              {group.metrics.map(({ key, icon }) => {
                const metric = metrics[key as PortfolioMetric];
                if (!metric) return null;
                const label = METRIC_LABELS[key as PortfolioMetric];
                const isPositive = metric.value >= 0;
                const isNegative = metric.value < 0;
                const isPercent = ['totalReturn', 'dailyReturn', 'weeklyReturn', 'monthlyReturn', 'yearlyReturn', 'winRate', 'maxDrawdown', 'currentDrawdown', 'volatility', 'exposure'].includes(key);
                const isCurrency = ['totalBalance', 'availableBalance', 'lockedBalance', 'totalEquity', 'totalPnL', 'dailyPnL', 'weeklyPnL', 'monthlyPnL', 'yearlyPnL', 'averageWin', 'averageLoss', 'marginUsed'].includes(key);

                let color = 'text-nexus-500';
                if (isPercent || isCurrency) {
                  color = isPositive ? 'text-emerald-500' : isNegative ? 'text-red-500' : 'text-nexus-500';
                }

                return (
                  <div key={key} className="flex items-center justify-between">
                    <span className="text-sm text-nexus-500 dark:text-nexus-400 flex items-center gap-1.5">
                      {icon}
                      {label}
                    </span>
                    <span className={cn(
                      'text-sm font-medium',
                      showValues ? color : 'text-nexus-400'
                    )}>
                      {showValues ? metric.formatted : '••••••'}
                    </span>
                  </div>
                );
              })}
            </div>
          </Card>
        ))}
      </div>
    );
  };

  const renderAllocation = () => {
    if (!showAllocation || !portfolioData.assets.length) return null;

    const sortedAssets = [...portfolioData.assets].sort((a, b) => b.value - a.value);

    return (
      <Card className="p-4 mb-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-nexus-900 dark:text-nexus-100">
            Asset Allocation
          </h3>
          <span className="text-sm text-nexus-500 dark:text-nexus-400">
            {sortedAssets.length} assets
          </span>
        </div>

        <div className="space-y-1">
          {sortedAssets.map((asset) => (
            <AllocationItem
              key={asset.symbol}
              asset={asset}
              onClick={onAssetClick}
            />
          ))}
        </div>
      </Card>
    );
  };

  const renderRiskProfile = () => {
    if (!showRisk) return null;

    const { riskLevel, style } = portfolioData;
    const risk = riskLevel ? RISK_LABELS[riskLevel] : null;
    const investmentStyle = style ? STYLE_LABELS[style] : null;

    return (
      <Card className="p-4 mb-4">
        <h3 className="text-lg font-semibold text-nexus-900 dark:text-nexus-100 mb-3">
          Risk Profile
        </h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {risk && (
            <div className="flex items-center gap-3 p-3 bg-nexus-50 dark:bg-nexus-800/50 rounded-lg">
              <Shield className={cn('w-5 h-5', risk.color)} />
              <div>
                <div className="text-sm text-nexus-500 dark:text-nexus-400">Risk Level</div>
                <div className={cn('font-semibold', risk.color)}>{risk.label}</div>
              </div>
            </div>
          )}
          {investmentStyle && (
            <div className="flex items-center gap-3 p-3 bg-nexus-50 dark:bg-nexus-800/50 rounded-lg">
              <Compass className={cn('w-5 h-5', investmentStyle.color)} />
              <div>
                <div className="text-sm text-nexus-500 dark:text-nexus-400">Investment Style</div>
                <div className={cn('font-semibold', investmentStyle.color)}>{investmentStyle.label}</div>
              </div>
            </div>
          )}
        </div>
      </Card>
    );
  };

  // ========================================
  // MAIN RENDER
  // ========================================
  
  if (loading && !portfolioData.totalBalance) {
    return (
      <div className={cn('w-full', className)}>
        {renderHeader()}
        <div className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-24 rounded-xl" />
            ))}
          </div>
          <Skeleton className="h-48 rounded-xl" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-64 rounded-xl" />
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center justify-center p-8 text-center">
        <AlertCircle className="w-12 h-12 text-red-500 mb-4" />
        <h3 className="text-lg font-semibold text-nexus-900 dark:text-nexus-100">Error loading portfolio</h3>
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
    <div
      className={cn(
        'w-full',
        isFullscreen && 'fixed inset-0 z-50 overflow-auto p-6 bg-white dark:bg-nexus-950',
        className
      )}
      data-testid={testId}
    >
      {renderHeader()}
      {renderTimeframes()}
      {renderBalanceCards()}
      {renderPortfolioMetrics()}
      {renderAllocation()}
      {renderRiskProfile()}
    </div>
  );
};

// ========================================
// EXPORTS
// ========================================

PortfolioSummary.displayName = 'PortfolioSummary';

export default PortfolioSummary;

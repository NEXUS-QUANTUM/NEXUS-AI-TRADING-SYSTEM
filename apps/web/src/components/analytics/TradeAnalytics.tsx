/**
 * NEXUS AI TRADING SYSTEM - TradeAnalytics Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This component provides comprehensive trade analytics including:
 * - Trade performance metrics
 * - Win rate and profit factor
 * - Average trade statistics
 * - Trade distribution by type
 * - P&L analysis
 * - Trade duration analysis
 * - Entry/Exit analysis
 * - Trade clustering
 * - Performance by symbol
 * - Performance by strategy
 * - Trade timeline
 * - Cumulative P&L
 * - Risk-adjusted returns
 * - Real-time updates
 * - Responsive design
 * - Accessibility features
 * - Customizable appearance
 */

'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  TrendingUp,
  TrendingDown,
  Activity,
  BarChart3,
  PieChart,
  LineChart,
  Target,
  Award,
  Crown,
  Star,
  Rocket,
  Zap,
  Brain,
  Shield,
  DollarSign,
  Percent,
  Clock,
  Calendar,
  Filter,
  Search,
  Download,
  RefreshCw,
  Settings,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Plus,
  Minus,
  X,
  Check,
  AlertCircle,
  Info,
  HelpCircle,
  Eye,
  EyeOff,
  Maximize2,
  Minimize2,
  ExternalLink,
  Copy,
  Share2,
  Bookmark,
  Flag,
  Heart,
  MessageSquare,
  BellRing,
  Mail,
  Phone,
  MapPin,
  Globe,
  Sun,
  Moon,
  Monitor,
  Layout,
  Columns,
  Rows,
  PanelTop,
  PanelBottom,
  PanelLeft,
  PanelRight,
  Square,
  Circle,
  Triangle,
  Hexagon,
  Octagon,
  Pentagon,
} from 'lucide-react';

// Components
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Switch } from '@/components/ui/Switch';
import { Modal } from '@/components/ui/Modal';
import { Progress } from '@/components/ui/Progress';
import { Tooltip } from '@/components/ui/Tooltip';
import { Toast } from '@/components/ui/Toast';
import { Spinner } from '@/components/ui/Spinner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import { Table } from '@/components/ui/Table';

// Charts
import { BarChart, LineChart, PieChart, ScatterChart, AreaChart } from '@/components/charts';

// Types
import type {
  TradeAnalytics as TradeAnalyticsType,
  Trade,
  TradePerformance,
  TradeDistribution,
  TradeMetrics,
  TradeCluster,
  TradeTimeline,
  TradeStats,
} from '@/types/analytics';

// Constants
import {
  TRADE_TYPES,
  TRADE_STATUSES,
  TRADE_ORDER_TYPES,
  TRADE_METRICS,
  DEFAULT_TRADE_ANALYTICS,
} from '@/constants/analytics';

// Utils
import { formatCurrency, formatPercentage, formatNumber, formatDate, formatTime } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

// ============================================
// Props Interface
// ============================================

interface TradeAnalyticsProps {
  analytics: TradeAnalyticsType;
  trades: Trade[];
  performance?: TradePerformance;
  distribution?: TradeDistribution;
  metrics?: TradeMetrics;
  clusters?: TradeCluster[];
  timeline?: TradeTimeline[];
  isLoading?: boolean;
  className?: string;
  showDistribution?: boolean;
  showClusters?: boolean;
  showTimeline?: boolean;
  compact?: boolean;
  onRefresh?: () => void;
  onExport?: () => void;
  onFilterChange?: (filter: any) => void;
}

// ============================================
// Metric Card Component
// ============================================

interface MetricCardProps {
  label: string;
  value: string | number;
  change?: number;
  status?: 'positive' | 'negative' | 'neutral';
  icon?: React.ReactNode;
  tooltip?: string;
  className?: string;
  onClick?: () => void;
}

function MetricCard({
  label,
  value,
  change,
  status = 'neutral',
  icon,
  tooltip,
  className,
  onClick,
}: MetricCardProps) {
  const statusColors = {
    positive: 'border-green-500/30 bg-green-500/5',
    negative: 'border-red-500/30 bg-red-500/5',
    neutral: 'border-gray-500/30 bg-gray-500/5',
  };

  const statusTextColors = {
    positive: 'text-green-500',
    negative: 'text-red-500',
    neutral: 'text-gray-400',
  };

  return (
    <div
      className={cn(
        "p-3 rounded-lg border transition-all cursor-pointer hover:border-gray-500",
        statusColors[status],
        className
      )}
      onClick={onClick}
    >
      <div className="flex items-start justify-between">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">{label}</span>
            {tooltip && (
              <Tooltip content={tooltip}>
                <HelpCircle className="w-3 h-3 text-gray-500" />
              </Tooltip>
            )}
          </div>
          <div className={cn(
            "text-lg font-bold mt-1",
            statusTextColors[status]
          )}>
            {value}
          </div>
          {change !== undefined && (
            <div className={cn(
              "text-xs mt-1",
              change >= 0 ? 'text-green-500' : 'text-red-500'
            )}>
              {change >= 0 ? '▲' : '▼'} {formatPercentage(Math.abs(change))}
            </div>
          )}
        </div>
        {icon && (
          <div className="flex-shrink-0 mt-1">
            {icon}
          </div>
        )}
      </div>
    </div>
  );
}

// ============================================
// Main Component
// ============================================

export function TradeAnalytics({
  analytics,
  trades,
  performance,
  distribution,
  metrics,
  clusters = [],
  timeline = [],
  isLoading = false,
  className,
  showDistribution = true,
  showClusters = true,
  showTimeline = true,
  compact = false,
  onRefresh,
  onExport,
  onFilterChange,
}: TradeAnalyticsProps) {
  // State
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [selectedSymbol, setSelectedSymbol] = useState<string>('all');
  const [selectedStrategy, setSelectedStrategy] = useState<string>('all');
  const [selectedType, setSelectedType] = useState<string>('all');
  const [dateRange, setDateRange] = useState<{ start: Date; end: Date }>({
    start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
    end: new Date(),
  });
  const [showSettings, setShowSettings] = useState<boolean>(false);
  const [showDetailsModal, setShowDetailsModal] = useState<boolean>(false);
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null);
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');

  // Refs
  const containerRef = useRef<HTMLDivElement>(null);

  // ============================================
  // Handlers
  // ============================================

  const handleRefresh = useCallback(async () => {
    setIsRefreshing(true);
    try {
      await onRefresh?.();
      setShowToast({
        message: 'Trade analytics refreshed!',
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to refresh analytics.',
        type: 'error',
      });
    } finally {
      setIsRefreshing(false);
    }
  }, [onRefresh]);

  const handleExport = useCallback(async () => {
    setIsExporting(true);
    try {
      if (onExport) {
        await onExport();
      } else {
        const exportData = {
          timestamp: new Date().toISOString(),
          analytics,
          trades,
          performance,
          distribution,
          metrics,
          clusters,
          timeline,
        };
        const blob = new Blob([JSON.stringify(exportData, null, 2)], {
          type: 'application/json',
        });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `trade-analytics-${Date.now()}.json`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        setShowToast({
          message: 'Trade analytics exported successfully!',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to export analytics.',
        type: 'error',
      });
    } finally {
      setIsExporting(false);
    }
  }, [onExport, analytics, trades, performance, distribution, metrics, clusters, timeline]);

  const handleViewDetails = useCallback((metric: string) => {
    setSelectedMetric(metric);
    setShowDetailsModal(true);
  }, []);

  const handleFilterChange = useCallback((key: string, value: any) => {
    switch (key) {
      case 'symbol':
        setSelectedSymbol(value);
        break;
      case 'strategy':
        setSelectedStrategy(value);
        break;
      case 'type':
        setSelectedType(value);
        break;
      default:
        break;
    }
    onFilterChange?.({ [key]: value });
  }, [onFilterChange]);

  // ============================================
  // Memoized Computations
  // ============================================

  const filteredTrades = useMemo(() => {
    return trades.filter(trade => {
      if (selectedSymbol !== 'all' && trade.symbol !== selectedSymbol) return false;
      if (selectedStrategy !== 'all' && trade.strategy !== selectedStrategy) return false;
      if (selectedType !== 'all' && trade.type !== selectedType) return false;
      const tradeDate = new Date(trade.timestamp);
      if (tradeDate < dateRange.start || tradeDate > dateRange.end) return false;
      return true;
    });
  }, [trades, selectedSymbol, selectedStrategy, selectedType, dateRange]);

  const symbols = useMemo(() => {
    const unique = new Set(trades.map(t => t.symbol));
    return ['all', ...Array.from(unique)];
  }, [trades]);

  const strategies = useMemo(() => {
    const unique = new Set(trades.map(t => t.strategy));
    return ['all', ...Array.from(unique)];
  }, [trades]);

  const types = useMemo(() => {
    const unique = new Set(trades.map(t => t.type));
    return ['all', ...Array.from(unique)];
  }, [trades]);

  const totalPnL = useMemo(() => {
    return filteredTrades.reduce((sum, t) => sum + (t.pnl || 0), 0);
  }, [filteredTrades]);

  const winRate = useMemo(() => {
    const wins = filteredTrades.filter(t => t.pnl > 0).length;
    return filteredTrades.length > 0 ? wins / filteredTrades.length : 0;
  }, [filteredTrades]);

  const profitFactor = useMemo(() => {
    const grossProfit = filteredTrades.filter(t => t.pnl > 0).reduce((sum, t) => sum + t.pnl, 0);
    const grossLoss = filteredTrades.filter(t => t.pnl < 0).reduce((sum, t) => sum + Math.abs(t.pnl), 0);
    return grossLoss > 0 ? grossProfit / grossLoss : grossProfit > 0 ? Infinity : 0;
  }, [filteredTrades]);

  const averageWin = useMemo(() => {
    const wins = filteredTrades.filter(t => t.pnl > 0);
    return wins.length > 0 ? wins.reduce((sum, t) => sum + t.pnl, 0) / wins.length : 0;
  }, [filteredTrades]);

  const averageLoss = useMemo(() => {
    const losses = filteredTrades.filter(t => t.pnl < 0);
    return losses.length > 0 ? losses.reduce((sum, t) => sum + Math.abs(t.pnl), 0) / losses.length : 0;
  }, [filteredTrades]);

  const averageTrade = useMemo(() => {
    return filteredTrades.length > 0 ? filteredTrades.reduce((sum, t) => sum + t.pnl, 0) / filteredTrades.length : 0;
  }, [filteredTrades]);

  const largestWin = useMemo(() => {
    return filteredTrades.reduce((max, t) => t.pnl > max ? t.pnl : max, 0);
  }, [filteredTrades]);

  const largestLoss = useMemo(() => {
    return filteredTrades.reduce((min, t) => t.pnl < min ? t.pnl : min, 0);
  }, [filteredTrades]);

  const tradeDistributionByType = useMemo(() => {
    const distribution: Record<string, number> = {};
    filteredTrades.forEach(t => {
      distribution[t.type] = (distribution[t.type] || 0) + 1;
    });
    return Object.entries(distribution).map(([key, value]) => ({
      name: key,
      value: value,
      color: `hsl(${Object.keys(distribution).indexOf(key) * 45}, 70%, 50%)`,
    }));
  }, [filteredTrades]);

  const performanceBySymbol = useMemo(() => {
    const performance: Record<string, { total: number; count: number; winRate: number }> = {};
    filteredTrades.forEach(t => {
      if (!performance[t.symbol]) {
        performance[t.symbol] = { total: 0, count: 0, wins: 0 };
      }
      performance[t.symbol].total += t.pnl || 0;
      performance[t.symbol].count += 1;
      if (t.pnl > 0) performance[t.symbol].wins = (performance[t.symbol].wins || 0) + 1;
    });
    return Object.entries(performance).map(([symbol, data]) => ({
      symbol,
      totalPnL: data.total,
      count: data.count,
      winRate: data.count > 0 ? data.wins / data.count : 0,
    }));
  }, [filteredTrades]);

  // ============================================
  // Render
  // ============================================

  if (isLoading) {
    return (
      <Card className={cn("p-6 bg-gray-800 border-gray-700", className)}>
        <div className="flex items-center justify-center h-64">
          <Spinner size="lg" className="text-cyan-500" />
        </div>
      </Card>
    );
  }

  // Compact Mode
  if (compact) {
    return (
      <Card className={cn("p-4 bg-gray-800 border-gray-700", className)}>
        <div className="flex items-center justify-between mb-3">
          <span className="text-sm font-medium text-white">Trade Analytics</span>
          <div className="flex items-center gap-2">
            <Badge className="bg-cyan-500/20 text-cyan-400 text-xs border-cyan-500/30">
              {filteredTrades.length} trades
            </Badge>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRefresh}
              isLoading={isRefreshing}
              className="text-gray-400 hover:text-white p-1"
            >
              <RefreshCw className="w-4 h-4" />
            </Button>
          </div>
        </div>
        <div className="space-y-3">
          <div className="grid grid-cols-2 gap-2">
            <MetricCard
              label="Total P&L"
              value={formatCurrency(totalPnL)}
              status={totalPnL >= 0 ? 'positive' : 'negative'}
            />
            <MetricCard
              label="Win Rate"
              value={formatPercentage(winRate)}
              status={winRate > 0.5 ? 'positive' : 'negative'}
            />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <MetricCard
              label="Avg Trade"
              value={formatCurrency(averageTrade)}
              status={averageTrade >= 0 ? 'positive' : 'negative'}
            />
            <MetricCard
              label="Profit Factor"
              value={profitFactor === Infinity ? '∞' : profitFactor.toFixed(2)}
              status={profitFactor > 1 ? 'positive' : 'negative'}
            />
          </div>
        </div>
      </Card>
    );
  }

  return (
    <Card className={cn("p-6 bg-gray-800 border-gray-700", className)}>
      {/* ============================================ */}
      {/* Header */}
      {/* ============================================ */}
      <div className="flex flex-wrap items-center justify-between mb-6 gap-4">
        <div className="flex items-center gap-3">
          <div className="p-2 rounded-lg bg-cyan-500/20">
            <Activity className="w-5 h-5 text-cyan-500" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">Trade Analytics</h3>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-sm text-gray-400">{filteredTrades.length} trades</span>
              <span className="text-xs text-gray-500">•</span>
              <span className="text-sm text-gray-400">
                {formatDate(dateRange.start)} - {formatDate(dateRange.end)}
              </span>
            </div>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Select
            value={selectedSymbol}
            onValueChange={(value) => handleFilterChange('symbol', value)}
            className="w-28 bg-gray-700 border-gray-600 text-sm"
          >
            {symbols.map((symbol) => (
              <option key={symbol} value={symbol}>{symbol === 'all' ? 'All Symbols' : symbol}</option>
            ))}
          </Select>
          <Select
            value={selectedStrategy}
            onValueChange={(value) => handleFilterChange('strategy', value)}
            className="w-28 bg-gray-700 border-gray-600 text-sm"
          >
            {strategies.map((strategy) => (
              <option key={strategy} value={strategy}>{strategy === 'all' ? 'All Strategies' : strategy}</option>
            ))}
          </Select>
          <Select
            value={selectedType}
            onValueChange={(value) => handleFilterChange('type', value)}
            className="w-24 bg-gray-700 border-gray-600 text-sm"
          >
            {types.map((type) => (
              <option key={type} value={type}>{type === 'all' ? 'All Types' : type}</option>
            ))}
          </Select>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleRefresh}
            isLoading={isRefreshing}
            className="text-gray-400 hover:text-white"
          >
            <RefreshCw className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleExport}
            isLoading={isExporting}
            className="text-gray-400 hover:text-white"
          >
            <Download className="w-4 h-4" />
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowSettings(true)}
            className="text-gray-400 hover:text-white"
          >
            <Settings className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* ============================================ */}
      {/* Key Metrics */}
      {/* ============================================ */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3 mb-6">
        <MetricCard
          label="Total P&L"
          value={formatCurrency(totalPnL)}
          status={totalPnL >= 0 ? 'positive' : 'negative'}
          icon={<DollarSign className="w-4 h-4" />}
          onClick={() => handleViewDetails('pnl')}
        />
        <MetricCard
          label="Win Rate"
          value={formatPercentage(winRate)}
          status={winRate > 0.5 ? 'positive' : 'negative'}
          icon={<Target className="w-4 h-4" />}
          onClick={() => handleViewDetails('winRate')}
        />
        <MetricCard
          label="Profit Factor"
          value={profitFactor === Infinity ? '∞' : profitFactor.toFixed(2)}
          status={profitFactor > 1 ? 'positive' : 'negative'}
          icon={<Award className="w-4 h-4" />}
          onClick={() => handleViewDetails('profitFactor')}
        />
        <MetricCard
          label="Avg Trade"
          value={formatCurrency(averageTrade)}
          status={averageTrade >= 0 ? 'positive' : 'negative'}
          icon={<Activity className="w-4 h-4" />}
          onClick={() => handleViewDetails('avgTrade')}
        />
        <MetricCard
          label="Avg Win"
          value={formatCurrency(averageWin)}
          status="positive"
          icon={<TrendingUp className="w-4 h-4" />}
          onClick={() => handleViewDetails('avgWin')}
        />
        <MetricCard
          label="Avg Loss"
          value={formatCurrency(averageLoss)}
          status="negative"
          icon={<TrendingDown className="w-4 h-4" />}
          onClick={() => handleViewDetails('avgLoss')}
        />
      </div>

      {/* ============================================ */}
      {/* Main Tabs */}
      {/* ============================================ */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-gray-700/30 rounded-lg p-1 mb-6">
          <TabsTrigger value="overview" className="text-xs">Overview</TabsTrigger>
          {showDistribution && (
            <TabsTrigger value="distribution" className="text-xs">Distribution</TabsTrigger>
          )}
          {showClusters && clusters.length > 0 && (
            <TabsTrigger value="clusters" className="text-xs">Clusters</TabsTrigger>
          )}
          {showTimeline && timeline.length > 0 && (
            <TabsTrigger value="timeline" className="text-xs">Timeline</TabsTrigger>
          )}
          <TabsTrigger value="trades" className="text-xs">All Trades</TabsTrigger>
        </TabsList>

        {/* ========================================== */}
        {/* OVERVIEW TAB */}
        {/* ========================================== */}
        <TabsContent value="overview">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Cumulative P&L Chart */}
            <Card className="p-4 bg-gray-700/30 border-gray-600">
              <h4 className="text-sm font-medium text-gray-300 mb-3">Cumulative P&L</h4>
              <div className="h-64">
                <AreaChart
                  data={timeline}
                  xKey="date"
                  yKey="cumulativePnL"
                  color={totalPnL >= 0 ? '#10b981' : '#ef4444'}
                  height={240}
                  gradient
                  tooltip
                />
              </div>
            </Card>

            {/* Distribution by Type */}
            {showDistribution && (
              <Card className="p-4 bg-gray-700/30 border-gray-600">
                <h4 className="text-sm font-medium text-gray-300 mb-3">Distribution by Type</h4>
                <div className="h-64">
                  <PieChart
                    data={tradeDistributionByType}
                    height={240}
                    tooltip
                    legend
                  />
                </div>
              </Card>
            )}
          </div>

          {/* Performance by Symbol */}
          <div className="mt-6">
            <Card className="p-4 bg-gray-700/30 border-gray-600">
              <h4 className="text-sm font-medium text-gray-300 mb-3">Performance by Symbol</h4>
              <div className="space-y-2">
                {performanceBySymbol.slice(0, 10).map((item) => (
                  <div key={item.symbol} className="flex items-center gap-3">
                    <div className="w-20 font-mono text-white text-sm">{item.symbol}</div>
                    <div className="flex-1">
                      <div className="flex items-center justify-between text-sm">
                        <span className="text-gray-400">{item.count} trades</span>
                        <span className={cn(
                          "font-mono",
                          item.totalPnL >= 0 ? 'text-green-500' : 'text-red-500'
                        )}>
                          {formatCurrency(item.totalPnL)}
                        </span>
                      </div>
                      <div className="mt-1">
                        <div className="flex items-center gap-2">
                          <Progress value={item.winRate * 100} className="h-1.5 flex-1" />
                          <span className="text-xs text-gray-400">{formatPercentage(item.winRate)}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* DISTRIBUTION TAB */}
        {/* ========================================== */}
        {showDistribution && (
          <TabsContent value="distribution">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <Card className="p-4 bg-gray-700/30 border-gray-600">
                <h4 className="text-sm font-medium text-gray-300 mb-3">P&L Distribution</h4>
                <div className="h-64">
                  <BarChart
                    data={analytics.distribution?.pnlDistribution || []}
                    xKey="range"
                    yKey="count"
                    color="#8b5cf6"
                    height={240}
                    tooltip
                  />
                </div>
              </Card>

              <Card className="p-4 bg-gray-700/30 border-gray-600">
                <h4 className="text-sm font-medium text-gray-300 mb-3">Duration Distribution</h4>
                <div className="h-64">
                  <BarChart
                    data={analytics.distribution?.durationDistribution || []}
                    xKey="range"
                    yKey="count"
                    color="#06b6d4"
                    height={240}
                    tooltip
                  />
                </div>
              </Card>
            </div>

            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
              <Card className="p-4 bg-gray-700/30 border-gray-600">
                <h4 className="text-sm font-medium text-gray-300 mb-3">Win/Loss Distribution</h4>
                <div className="h-48">
                  <PieChart
                    data={[
                      { name: 'Wins', value: filteredTrades.filter(t => t.pnl > 0).length },
                      { name: 'Losses', value: filteredTrades.filter(t => t.pnl < 0).length },
                      { name: 'Breakeven', value: filteredTrades.filter(t => t.pnl === 0).length },
                    ]}
                    height={180}
                    tooltip
                    legend
                  />
                </div>
              </Card>

              <Card className="p-4 bg-gray-700/30 border-gray-600">
                <h4 className="text-sm font-medium text-gray-300 mb-3">Trade Size Distribution</h4>
                <div className="h-48">
                  <BarChart
                    data={analytics.distribution?.sizeDistribution || []}
                    xKey="range"
                    yKey="count"
                    color="#10b981"
                    height={180}
                    tooltip
                  />
                </div>
              </Card>
            </div>
          </TabsContent>
        )}

        {/* ========================================== */}
        {/* CLUSTERS TAB */}
        {/* ========================================== */}
        {showClusters && clusters.length > 0 && (
          <TabsContent value="clusters">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {clusters.map((cluster, index) => (
                <Card key={index} className="p-4 bg-gray-700/30 border-gray-600">
                  <div className="flex items-center justify-between mb-3">
                    <h4 className="text-sm font-medium text-white">{cluster.name}</h4>
                    <Badge className="bg-cyan-500/20 text-cyan-400 text-xs border-cyan-500/30">
                      {cluster.count} trades
                    </Badge>
                  </div>
                  <div className="space-y-2">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Total P&L</span>
                      <span className={cn(
                        "font-mono",
                        cluster.totalPnL >= 0 ? 'text-green-500' : 'text-red-500'
                      )}>
                        {formatCurrency(cluster.totalPnL)}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Win Rate</span>
                      <span className="text-white">{formatPercentage(cluster.winRate)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Avg Trade</span>
                      <span className={cn(
                        "font-mono",
                        cluster.avgTrade >= 0 ? 'text-green-500' : 'text-red-500'
                      )}>
                        {formatCurrency(cluster.avgTrade)}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Description</span>
                      <span className="text-gray-300 text-xs">{cluster.description}</span>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          </TabsContent>
        )}

        {/* ========================================== */}
        {/* TIMELINE TAB */}
        {/* ========================================== */}
        {showTimeline && timeline.length > 0 && (
          <TabsContent value="timeline">
            <Card className="p-4 bg-gray-700/30 border-gray-600">
              <h4 className="text-sm font-medium text-gray-300 mb-3">Trade Timeline</h4>
              <div className="h-64">
                <ScatterChart
                  data={timeline}
                  xKey="date"
                  yKey="pnl"
                  color="#06b6d4"
                  height={240}
                  tooltip
                />
              </div>
            </Card>

            <div className="mt-6 max-h-96 overflow-y-auto">
              <Table>
                <thead>
                  <tr className="border-b border-gray-700">
                    <th className="text-left text-xs text-gray-400 p-3">Date</th>
                    <th className="text-left text-xs text-gray-400 p-3">Symbol</th>
                    <th className="text-left text-xs text-gray-400 p-3">Type</th>
                    <th className="text-right text-xs text-gray-400 p-3">P&L</th>
                    <th className="text-right text-xs text-gray-400 p-3">Duration</th>
                    <th className="text-right text-xs text-gray-400 p-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTrades.slice(0, 50).map((trade, index) => (
                    <tr key={index} className="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
                      <td className="p-3 text-gray-400 text-xs">{formatTime(trade.timestamp)}</td>
                      <td className="p-3 text-white font-mono">{trade.symbol}</td>
                      <td className="p-3 text-white">{trade.type}</td>
                      <td className={cn(
                        "p-3 text-right font-mono",
                        trade.pnl >= 0 ? 'text-green-500' : 'text-red-500'
                      )}>
                        {formatCurrency(trade.pnl || 0)}
                      </td>
                      <td className="p-3 text-right text-gray-400">{trade.duration || 'N/A'}</td>
                      <td className="p-3 text-right">
                        <Badge className={cn(
                          "text-xs",
                          trade.status === 'completed' ? 'bg-green-500/20 text-green-500' :
                          trade.status === 'open' ? 'bg-yellow-500/20 text-yellow-500' :
                          'bg-gray-500/20 text-gray-400'
                        )}>
                          {trade.status?.toUpperCase()}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              {filteredTrades.length > 50 && (
                <div className="text-center text-sm text-gray-500 mt-4">
                  Showing 50 of {filteredTrades.length} trades
                </div>
              )}
            </div>
          </TabsContent>
        )}

        {/* ========================================== */}
        {/* ALL TRADES TAB */}
        {/* ========================================== */}
        <TabsContent value="trades">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <Input
                  type="text"
                  placeholder="Search trades..."
                  className="w-full pl-9 bg-gray-700 border-gray-600 text-white text-sm"
                  onChange={(e) => {
                    // Implement search
                  }}
                />
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              className="border-gray-600 hover:border-cyan-500"
            >
              <Filter className="w-4 h-4 mr-2" />
              Filter
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleExport}
              isLoading={isExporting}
              className="border-gray-600 hover:border-cyan-500"
            >
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>
          </div>

          <div className="max-h-[600px] overflow-y-auto">
            <Table>
              <thead>
                <tr className="border-b border-gray-700 sticky top-0 bg-gray-800 z-10">
                  <th className="text-left text-xs text-gray-400 p-3">Time</th>
                  <th className="text-left text-xs text-gray-400 p-3">Symbol</th>
                  <th className="text-left text-xs text-gray-400 p-3">Type</th>
                  <th className="text-left text-xs text-gray-400 p-3">Side</th>
                  <th className="text-right text-xs text-gray-400 p-3">Quantity</th>
                  <th className="text-right text-xs text-gray-400 p-3">Price</th>
                  <th className="text-right text-xs text-gray-400 p-3">Total</th>
                  <th className="text-right text-xs text-gray-400 p-3">P&L</th>
                  <th className="text-right text-xs text-gray-400 p-3">Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredTrades.map((trade, index) => (
                  <tr key={index} className="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
                    <td className="p-3 text-gray-400 text-xs">{formatTime(trade.timestamp)}</td>
                    <td className="p-3 text-white font-mono">{trade.symbol}</td>
                    <td className="p-3 text-white">{trade.type}</td>
                    <td className={cn(
                      "p-3 font-medium",
                      trade.side === 'buy' ? 'text-green-500' : 'text-red-500'
                    )}>
                      {trade.side?.toUpperCase() || 'N/A'}
                    </td>
                    <td className="p-3 text-right text-white font-mono">{formatNumber(trade.quantity || 0)}</td>
                    <td className="p-3 text-right text-white font-mono">{formatCurrency(trade.price || 0)}</td>
                    <td className="p-3 text-right text-white font-mono">{formatCurrency(trade.total || 0)}</td>
                    <td className={cn(
                      "p-3 text-right font-mono",
                      trade.pnl >= 0 ? 'text-green-500' : 'text-red-500'
                    )}>
                      {formatCurrency(trade.pnl || 0)}
                    </td>
                    <td className="p-3 text-right">
                      <Badge className={cn(
                        "text-xs",
                        trade.status === 'completed' ? 'bg-green-500/20 text-green-500' :
                        trade.status === 'open' ? 'bg-yellow-500/20 text-yellow-500' :
                        'bg-gray-500/20 text-gray-400'
                      )}>
                        {trade.status?.toUpperCase() || 'N/A'}
                      </Badge>
                    </td>
                  </tr>
                ))}
              </tbody>
            </Table>
            {filteredTrades.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                <Activity className="w-16 h-16 mx-auto mb-4 text-gray-600" />
                <p className="text-lg font-medium">No trades found</p>
                <p className="text-sm">Try adjusting your filters</p>
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>

      {/* ============================================ */}
      {/* Settings Modal */}
      {/* ============================================ */}
      <Modal
        open={showSettings}
        onOpenChange={setShowSettings}
        title="Trade Analytics Settings"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Date Range</label>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-500">Start</label>
                <Input
                  type="date"
                  value={formatDate(dateRange.start)}
                  onChange={(e) => setDateRange(prev => ({ ...prev, start: new Date(e.target.value) }))}
                  className="w-full bg-gray-700 border-gray-600 text-white"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-500">End</label>
                <Input
                  type="date"
                  value={formatDate(dateRange.end)}
                  onChange={(e) => setDateRange(prev => ({ ...prev, end: new Date(e.target.value) }))}
                  className="w-full bg-gray-700 border-gray-600 text-white"
                />
              </div>
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Display Options</label>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300">Show Distribution Charts</span>
                <Switch
                  checked={showDistribution}
                  onCheckedChange={() => {}}
                  className="data-[state=checked]:bg-cyan-500"
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300">Show Clusters</span>
                <Switch
                  checked={showClusters}
                  onCheckedChange={() => {}}
                  className="data-[state=checked]:bg-cyan-500"
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300">Show Timeline</span>
                <Switch
                  checked={showTimeline}
                  onCheckedChange={() => {}}
                  className="data-[state=checked]:bg-cyan-500"
                />
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
            <Button
              variant="outline"
              onClick={() => setShowSettings(false)}
              className="border-gray-600 hover:border-gray-500"
            >
              Close
            </Button>
          </div>
        </div>
      </Modal>

      {/* ============================================ */}
      {/* Details Modal */}
      {/* ============================================ */}
      <Modal
        open={showDetailsModal}
        onOpenChange={setShowDetailsModal}
        title={`${selectedMetric?.toUpperCase()} Details`}
        className="max-w-md"
      >
        <div className="space-y-4">
          {selectedMetric === 'pnl' && (
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-400">Total P&L</span>
                <span className={cn(
                  "font-mono font-bold",
                  totalPnL >= 0 ? 'text-green-500' : 'text-red-500'
                )}>
                  {formatCurrency(totalPnL)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Average P&L</span>
                <span className="text-white font-mono">{formatCurrency(averageTrade)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Largest Win</span>
                <span className="text-green-500 font-mono">{formatCurrency(largestWin)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Largest Loss</span>
                <span className="text-red-500 font-mono">{formatCurrency(largestLoss)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Total Trades</span>
                <span className="text-white">{filteredTrades.length}</span>
              </div>
            </div>
          )}
          {selectedMetric === 'winRate' && (
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-400">Win Rate</span>
                <span className="text-white font-bold">{formatPercentage(winRate)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Winning Trades</span>
                <span className="text-green-500">{filteredTrades.filter(t => t.pnl > 0).length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Losing Trades</span>
                <span className="text-red-500">{filteredTrades.filter(t => t.pnl < 0).length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Breakeven Trades</span>
                <span className="text-yellow-500">{filteredTrades.filter(t => t.pnl === 0).length}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Win/Loss Ratio</span>
                <span className="text-white">
                  {filteredTrades.filter(t => t.pnl > 0).length / (filteredTrades.filter(t => t.pnl < 0).length || 1)}
                </span>
              </div>
            </div>
          )}
          {selectedMetric === 'profitFactor' && (
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-400">Profit Factor</span>
                <span className="text-white font-bold">
                  {profitFactor === Infinity ? '∞' : profitFactor.toFixed(2)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Gross Profit</span>
                <span className="text-green-500 font-mono">
                  {formatCurrency(filteredTrades.filter(t => t.pnl > 0).reduce((sum, t) => sum + t.pnl, 0))}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Gross Loss</span>
                <span className="text-red-500 font-mono">
                  {formatCurrency(filteredTrades.filter(t => t.pnl < 0).reduce((sum, t) => sum + Math.abs(t.pnl), 0))}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Net Profit</span>
                <span className={cn(
                  "font-mono",
                  totalPnL >= 0 ? 'text-green-500' : 'text-red-500'
                )}>
                  {formatCurrency(totalPnL)}
                </span>
              </div>
            </div>
          )}
          <div className="flex justify-end pt-4 border-t border-gray-700">
            <Button
              variant="outline"
              onClick={() => setShowDetailsModal(false)}
              className="border-gray-600 hover:border-gray-500"
            >
              Close
            </Button>
          </div>
        </div>
      </Modal>

      {/* ============================================ */}
      {/* Toast Notifications */}
      {/* ============================================ */}
      <AnimatePresence>
        {showToast && (
          <Toast
            message={showToast.message}
            type={showToast.type}
            onClose={() => setShowToast(null)}
            className="fixed bottom-4 right-4 z-50 max-w-md"
            duration={5000}
          />
        )}
      </AnimatePresence>
    </Card>
  );
}

// ============================================
// Export
// ============================================

export default TradeAnalytics;/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */


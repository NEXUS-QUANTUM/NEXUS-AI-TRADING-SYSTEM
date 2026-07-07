/**
 * NEXUS AI TRADING SYSTEM - RiskMetrics Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This component provides comprehensive risk metrics display including:
 * - Value at Risk (VaR) calculation
 * - Expected Shortfall (CVaR)
 * - Volatility metrics
 * - Sharpe Ratio
 * - Sortino Ratio
 * - Calmar Ratio
 * - Maximum Drawdown
 * - Beta and Alpha
 * - Risk/Reward ratio
 * - Risk score
 * - Risk distribution
 * - Heatmap visualization
 * - Risk breakdown by asset
 * - Stress test results
 * - Real-time updates
 * - Responsive design
 * - Accessibility features
 * - Customizable appearance
 */

'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Shield,
  ShieldCheck,
  ShieldAlert,
  ShieldQuestion,
  TrendingUp,
  TrendingDown,
  AlertTriangle,
  CheckCircle,
  XCircle,
  Info,
  HelpCircle,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Plus,
  Minus,
  Download,
  RefreshCw,
  Settings,
  Eye,
  EyeOff,
  BarChart3,
  PieChart,
  LineChart,
  Activity,
  Zap,
  Target,
  Award,
  Crown,
  Star,
  Rocket,
  Sparkles,
  Brain,
  Cpu,
  Server,
  Database,
  Network,
  Globe,
  MapPin,
  Clock,
  Calendar,
  DollarSign,
  Percent,
  Award as AwardIcon,
  Trophy,
  Medal,
  Gift,
} from 'lucide-react';

// Components
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Progress } from '@/components/ui/Progress';
import { Tooltip } from '@/components/ui/Tooltip';
import { Modal } from '@/components/ui/Modal';
import { Toast } from '@/components/ui/Toast';
import { Spinner } from '@/components/ui/Spinner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import { Select } from '@/components/ui/Select';
import { Switch } from '@/components/ui/Switch';

// Charts
import { BarChart, LineChart, PieChart, HeatMap } from '@/components/charts';

// Types
import type {
  RiskMetrics as RiskMetricsType,
  RiskScore,
  RiskDistribution,
  RiskBreakdown,
  StressTestResult,
  RiskThreshold,
  ValueAtRisk,
} from '@/types/analytics';

// Constants
import {
  RISK_LEVELS,
  RISK_SCORES,
  RISK_THRESHOLDS,
  VAR_CONFIDENCE_LEVELS,
  STRESS_TEST_SCENARIOS,
} from '@/constants/analytics';

// Utils
import { formatCurrency, formatPercentage, formatNumber, formatDate } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

// ============================================
// Props Interface
// ============================================

interface RiskMetricsProps {
  metrics: RiskMetricsType;
  riskScore?: RiskScore;
  distribution?: RiskDistribution;
  breakdown?: RiskBreakdown;
  stressTests?: StressTestResult[];
  thresholds?: RiskThreshold[];
  isLoading?: boolean;
  className?: string;
  showVaR?: boolean;
  showDrawdown?: boolean;
  showHeatmap?: boolean;
  showStressTests?: boolean;
  compact?: boolean;
  onRefresh?: () => void;
  onExport?: () => void;
  onUpdateThresholds?: (thresholds: RiskThreshold[]) => void;
}

// ============================================
// Metric Card Component
// ============================================

interface MetricCardProps {
  label: string;
  value: string | number;
  change?: number;
  status?: 'good' | 'warning' | 'danger' | 'neutral';
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
    good: 'border-green-500/30 bg-green-500/5',
    warning: 'border-yellow-500/30 bg-yellow-500/5',
    danger: 'border-red-500/30 bg-red-500/5',
    neutral: 'border-gray-500/30 bg-gray-500/5',
  };

  const statusTextColors = {
    good: 'text-green-500',
    warning: 'text-yellow-500',
    danger: 'text-red-500',
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

export function RiskMetrics({
  metrics,
  riskScore,
  distribution,
  breakdown,
  stressTests = [],
  thresholds = [],
  isLoading = false,
  className,
  showVaR = true,
  showDrawdown = true,
  showHeatmap = true,
  showStressTests = true,
  compact = false,
  onRefresh,
  onExport,
  onUpdateThresholds,
}: RiskMetricsProps) {
  // State
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [showSettings, setShowSettings] = useState<boolean>(false);
  const [selectedVarConfidence, setSelectedVarConfidence] = useState<number>(0.95);
  const [showDetailsModal, setShowDetailsModal] = useState<boolean>(false);
  const [selectedMetric, setSelectedMetric] = useState<string | null>(null);
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isExporting, setIsExporting] = useState<boolean>(false);

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
        message: 'Risk metrics refreshed!',
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to refresh metrics.',
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
          metrics,
          riskScore,
          distribution,
          breakdown,
          stressTests,
        };
        const blob = new Blob([JSON.stringify(exportData, null, 2)], {
          type: 'application/json',
        });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `risk-metrics-${Date.now()}.json`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        setShowToast({
          message: 'Risk metrics exported successfully!',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to export metrics.',
        type: 'error',
      });
    } finally {
      setIsExporting(false);
    }
  }, [onExport, metrics, riskScore, distribution, breakdown, stressTests]);

  const handleViewDetails = useCallback((metric: string) => {
    setSelectedMetric(metric);
    setShowDetailsModal(true);
  }, []);

  // ============================================
  // Memoized Computations
  // ============================================

  const riskLevel = useMemo(() => {
    if (!riskScore) return 'neutral';
    const score = riskScore.total || 0;
    if (score <= 20) return 'low';
    if (score <= 40) return 'moderate';
    if (score <= 60) return 'medium';
    if (score <= 80) return 'high';
    return 'critical';
  }, [riskScore]);

  const riskLevelConfig = useMemo(() => {
    const configs = {
      low: { color: 'text-green-500', bg: 'bg-green-500/10', border: 'border-green-500/30', label: 'Low Risk' },
      moderate: { color: 'text-blue-500', bg: 'bg-blue-500/10', border: 'border-blue-500/30', label: 'Moderate Risk' },
      medium: { color: 'text-yellow-500', bg: 'bg-yellow-500/10', border: 'border-yellow-500/30', label: 'Medium Risk' },
      high: { color: 'text-orange-500', bg: 'bg-orange-500/10', border: 'border-orange-500/30', label: 'High Risk' },
      critical: { color: 'text-red-500', bg: 'bg-red-500/10', border: 'border-red-500/30', label: 'Critical Risk' },
      neutral: { color: 'text-gray-400', bg: 'bg-gray-500/10', border: 'border-gray-500/30', label: 'Neutral' },
    };
    return configs[riskLevel] || configs.neutral;
  }, [riskLevel]);

  const varData = useMemo(() => {
    if (!metrics.var) return null;
    return {
      value: metrics.var.value,
      confidence: metrics.var.confidence || 0.95,
      period: metrics.var.period || '1d',
      historical: metrics.var.historical || [],
    };
  }, [metrics]);

  const drawdownData = useMemo(() => {
    if (!metrics.drawdown) return null;
    return {
      max: metrics.drawdown.max,
      current: metrics.drawdown.current,
      duration: metrics.drawdown.duration,
      historical: metrics.drawdown.historical || [],
    };
  }, [metrics]);

  const riskBreakdown = useMemo(() => {
    if (!breakdown) return [];
    return Object.entries(breakdown).map(([key, value]) => ({
      name: key,
      value: value,
      color: `hsl(${Object.keys(breakdown).indexOf(key) * 45}, 70%, 50%)`,
    }));
  }, [breakdown]);

  const stressTestResults = useMemo(() => {
    return stressTests.map(test => ({
      ...test,
      impact: test.impact || 0,
      probability: test.probability || 0,
    }));
  }, [stressTests]);

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
          <span className="text-sm font-medium text-white">Risk Overview</span>
          <div className="flex items-center gap-2">
            <Badge className={cn("text-xs", riskLevelConfig.bg, riskLevelConfig.color, riskLevelConfig.border)}>
              {riskLevelConfig.label}
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
              label="VaR (95%)"
              value={formatCurrency(metrics.var?.value || 0)}
              status={metrics.var?.value > 10000 ? 'danger' : 'good'}
            />
            <MetricCard
              label="Sharpe Ratio"
              value={metrics.sharpeRatio?.toFixed(2) || 'N/A'}
              status={metrics.sharpeRatio > 1 ? 'good' : 'warning'}
            />
          </div>
          <div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-400">Risk Score</span>
              <span className={cn(
                "font-bold",
                riskLevelConfig.color
              )}>
                {riskScore?.total || 0}/100
              </span>
            </div>
            <Progress
              value={riskScore?.total || 0}
              className="h-2 mt-1"
              color={riskLevel === 'low' ? 'green' : riskLevel === 'moderate' ? 'blue' : riskLevel === 'medium' ? 'yellow' : riskLevel === 'high' ? 'orange' : 'red'}
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
          <div className={cn(
            "p-2 rounded-lg",
            riskLevelConfig.bg,
            riskLevelConfig.border
          )}>
            <Shield className={cn(
              "w-5 h-5",
              riskLevelConfig.color
            )} />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-white">Risk Metrics</h3>
            <div className="flex items-center gap-2 mt-1">
              <Badge className={cn("text-xs", riskLevelConfig.bg, riskLevelConfig.color, riskLevelConfig.border)}>
                {riskLevelConfig.label}
              </Badge>
              <span className="text-xs text-gray-500">
                Score: {riskScore?.total || 0}/100
              </span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
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
      {/* Main Tabs */}
      {/* ============================================ */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-gray-700/30 rounded-lg p-1 mb-6">
          <TabsTrigger value="overview" className="text-xs">Overview</TabsTrigger>
          <TabsTrigger value="var" className="text-xs">VaR</TabsTrigger>
          <TabsTrigger value="drawdown" className="text-xs">Drawdown</TabsTrigger>
          {showHeatmap && (
            <TabsTrigger value="heatmap" className="text-xs">Heatmap</TabsTrigger>
          )}
          {showStressTests && stressTests.length > 0 && (
            <TabsTrigger value="stress" className="text-xs">Stress Tests</TabsTrigger>
          )}
        </TabsList>

        {/* ========================================== */}
        {/* OVERVIEW TAB */}
        {/* ========================================== */}
        <TabsContent value="overview">
          <div className="space-y-6">
            {/* Key Metrics Grid */}
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-3">
              <MetricCard
                label="VaR (95%)"
                value={formatCurrency(metrics.var?.value || 0)}
                status={metrics.var?.value > 10000 ? 'danger' : 'good'}
                icon={<Shield className="w-4 h-4 text-cyan-500" />}
                tooltip="Value at Risk at 95% confidence level"
                onClick={() => handleViewDetails('var')}
              />
              <MetricCard
                label="Sharpe Ratio"
                value={metrics.sharpeRatio?.toFixed(2) || 'N/A'}
                status={metrics.sharpeRatio > 1 ? 'good' : 'warning'}
                icon={<Target className="w-4 h-4 text-purple-500" />}
                tooltip="Risk-adjusted return measure"
                onClick={() => handleViewDetails('sharpe')}
              />
              <MetricCard
                label="Max Drawdown"
                value={formatPercentage(metrics.drawdown?.max || 0)}
                status={metrics.drawdown?.max < 0.2 ? 'good' : 'danger'}
                icon={<TrendingDown className="w-4 h-4 text-red-500" />}
                tooltip="Maximum peak-to-trough decline"
                onClick={() => handleViewDetails('drawdown')}
              />
              <MetricCard
                label="Volatility"
                value={formatPercentage(metrics.volatility || 0)}
                status={metrics.volatility < 0.3 ? 'good' : 'warning'}
                icon={<Activity className="w-4 h-4 text-yellow-500" />}
                tooltip="Annualized volatility"
                onClick={() => handleViewDetails('volatility')}
              />
              <MetricCard
                label="Sortino Ratio"
                value={metrics.sortinoRatio?.toFixed(2) || 'N/A'}
                status={metrics.sortinoRatio > 0.5 ? 'good' : 'warning'}
                icon={<Zap className="w-4 h-4 text-blue-500" />}
                tooltip="Downside risk-adjusted return"
                onClick={() => handleViewDetails('sortino')}
              />
              <MetricCard
                label="Calmar Ratio"
                value={metrics.calmarRatio?.toFixed(2) || 'N/A'}
                status={metrics.calmarRatio > 0.5 ? 'good' : 'warning'}
                icon={<AwardIcon className="w-4 h-4 text-green-500" />}
                tooltip="Return to max drawdown ratio"
                onClick={() => handleViewDetails('calmar')}
              />
              <MetricCard
                label="Beta"
                value={metrics.beta?.toFixed(2) || 'N/A'}
                status={metrics.beta <= 1 ? 'good' : 'warning'}
                icon={<TrendingUp className="w-4 h-4 text-orange-500" />}
                tooltip="Market sensitivity measure"
                onClick={() => handleViewDetails('beta')}
              />
              <MetricCard
                label="Alpha"
                value={formatPercentage(metrics.alpha || 0)}
                status={metrics.alpha > 0 ? 'good' : 'warning'}
                icon={<Star className="w-4 h-4 text-yellow-500" />}
                tooltip="Excess return over benchmark"
                onClick={() => handleViewDetails('alpha')}
              />
            </div>

            {/* Risk Distribution */}
            {distribution && (
              <div className="p-4 bg-gray-700/30 rounded-lg">
                <h4 className="text-sm font-medium text-gray-300 mb-3">Risk Distribution</h4>
                <div className="space-y-2">
                  {Object.entries(distribution).map(([key, value]) => (
                    <div key={key}>
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-400 capitalize">{key}</span>
                        <span className="text-white">{formatPercentage(value)}</span>
                      </div>
                      <Progress value={value * 100} className="h-1.5 mt-1" />
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Risk Breakdown */}
            {breakdown && (
              <div className="p-4 bg-gray-700/30 rounded-lg">
                <h4 className="text-sm font-medium text-gray-300 mb-3">Risk Breakdown by Asset</h4>
                <div className="space-y-2">
                  {riskBreakdown.map((item) => (
                    <div key={item.name}>
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-400">{item.name}</span>
                        <span className="text-white">{formatPercentage(item.value)}</span>
                      </div>
                      <div className="w-full h-1.5 bg-gray-700 rounded-full overflow-hidden mt-1">
                        <div
                          className="h-full rounded-full"
                          style={{
                            width: `${item.value * 100}%`,
                            backgroundColor: item.color,
                          }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* VAR TAB */}
        {/* ========================================== */}
        {showVaR && (
          <TabsContent value="var">
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 bg-gray-700/30 rounded-lg text-center">
                  <div className="text-sm text-gray-400">VaR (95%)</div>
                  <div className="text-2xl font-bold text-white mt-1">
                    {formatCurrency(metrics.var?.value || 0)}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">Confidence: 95%</div>
                </div>
                <div className="p-4 bg-gray-700/30 rounded-lg text-center">
                  <div className="text-sm text-gray-400">CVaR (95%)</div>
                  <div className="text-2xl font-bold text-red-500 mt-1">
                    {formatCurrency(metrics.var?.cvar || 0)}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">Expected Shortfall</div>
                </div>
                <div className="p-4 bg-gray-700/30 rounded-lg text-center">
                  <div className="text-sm text-gray-400">VaR (99%)</div>
                  <div className="text-2xl font-bold text-orange-500 mt-1">
                    {formatCurrency(metrics.var?.var99 || 0)}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">Confidence: 99%</div>
                </div>
              </div>

              {/* Historical VaR Chart */}
              {varData?.historical && varData.historical.length > 0 && (
                <div className="p-4 bg-gray-700/30 rounded-lg">
                  <h4 className="text-sm font-medium text-gray-300 mb-3">Historical VaR</h4>
                  <div className="h-48">
                    <LineChart
                      data={varData.historical}
                      xKey="date"
                      yKey="value"
                      color="#06b6d4"
                      height={180}
                      tooltip
                    />
                  </div>
                </div>
              )}
            </div>
          </TabsContent>
        )}

        {/* ========================================== */}
        {/* DRAWDOWN TAB */}
        {/* ========================================== */}
        {showDrawdown && (
          <TabsContent value="drawdown">
            <div className="space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="p-4 bg-gray-700/30 rounded-lg text-center">
                  <div className="text-sm text-gray-400">Max Drawdown</div>
                  <div className="text-2xl font-bold text-red-500 mt-1">
                    {formatPercentage(drawdownData?.max || 0)}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">All-time high</div>
                </div>
                <div className="p-4 bg-gray-700/30 rounded-lg text-center">
                  <div className="text-sm text-gray-400">Current Drawdown</div>
                  <div className="text-2xl font-bold text-yellow-500 mt-1">
                    {formatPercentage(drawdownData?.current || 0)}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">Current drawdown</div>
                </div>
                <div className="p-4 bg-gray-700/30 rounded-lg text-center">
                  <div className="text-sm text-gray-400">Drawdown Duration</div>
                  <div className="text-2xl font-bold text-white mt-1">
                    {drawdownData?.duration || 0}d
                  </div>
                  <div className="text-xs text-gray-500 mt-1">Days since peak</div>
                </div>
              </div>

              {/* Drawdown Chart */}
              {drawdownData?.historical && drawdownData.historical.length > 0 && (
                <div className="p-4 bg-gray-700/30 rounded-lg">
                  <h4 className="text-sm font-medium text-gray-300 mb-3">Drawdown History</h4>
                  <div className="h-48">
                    <AreaChart
                      data={drawdownData.historical}
                      xKey="date"
                      yKey="drawdown"
                      color="#ef4444"
                      height={180}
                      tooltip
                      negative
                    />
                  </div>
                </div>
              )}
            </div>
          </TabsContent>
        )}

        {/* ========================================== */}
        {/* HEATMAP TAB */}
        {/* ========================================== */}
        {showHeatmap && (
          <TabsContent value="heatmap">
            <div className="space-y-4">
              <div className="p-4 bg-gray-700/30 rounded-lg">
                <h4 className="text-sm font-medium text-gray-300 mb-3">Risk Correlation Heatmap</h4>
                <div className="h-64">
                  <HeatMap
                    data={metrics.correlationMatrix || []}
                    height={240}
                    tooltip
                  />
                </div>
              </div>

              <div className="p-4 bg-gray-700/30 rounded-lg">
                <h4 className="text-sm font-medium text-gray-300 mb-3">Risk Contribution by Asset</h4>
                <div className="h-48">
                  <PieChart
                    data={riskBreakdown}
                    height={180}
                    tooltip
                    legend
                  />
                </div>
              </div>
            </div>
          </TabsContent>
        )}

        {/* ========================================== */}
        {/* STRESS TESTS TAB */}
        {/* ========================================== */}
        {showStressTests && stressTests.length > 0 && (
          <TabsContent value="stress">
            <div className="space-y-4">
              {stressTestResults.map((test, index) => (
                <div key={index} className="p-4 bg-gray-700/30 rounded-lg">
                  <div className="flex items-center justify-between mb-3">
                    <div>
                      <h4 className="text-sm font-medium text-white">{test.scenario}</h4>
                      <p className="text-xs text-gray-400 mt-1">{test.description}</p>
                    </div>
                    <Badge className={cn(
                      "text-xs",
                      test.impact > 0.2 ? 'bg-red-500/20 text-red-500' :
                      test.impact > 0.1 ? 'bg-yellow-500/20 text-yellow-500' :
                      'bg-green-500/20 text-green-500'
                    )}>
                      Impact: {formatPercentage(test.impact)}
                    </Badge>
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <span className="text-gray-400">Probability</span>
                      <div className="text-white">{formatPercentage(test.probability)}</div>
                    </div>
                    <div>
                      <span className="text-gray-400">Estimated Loss</span>
                      <div className="text-red-500">{formatCurrency(test.estimatedLoss || 0)}</div>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </TabsContent>
        )}
      </Tabs>

      {/* ============================================ */}
      {/* Settings Modal */}
      {/* ============================================ */}
      <Modal
        open={showSettings}
        onOpenChange={setShowSettings}
        title="Risk Settings"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">VaR Confidence Level</label>
            <Select
              value={String(selectedVarConfidence)}
              onValueChange={(value) => setSelectedVarConfidence(parseFloat(value))}
              className="w-full bg-gray-700 border-gray-600"
            >
              {VAR_CONFIDENCE_LEVELS.map((level) => (
                <option key={level} value={String(level)}>{formatPercentage(level)}</option>
              ))}
            </Select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Risk Thresholds</label>
            <div className="space-y-2">
              {RISK_THRESHOLDS.map((threshold) => (
                <div key={threshold.level} className="flex items-center justify-between">
                  <span className="text-sm text-gray-300 capitalize">{threshold.level}</span>
                  <span className="text-sm text-gray-400">{formatPercentage(threshold.value)}</span>
                </div>
              ))}
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
          {selectedMetric === 'var' && metrics.var && (
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-400">VaR (95%)</span>
                <span className="text-white font-mono">{formatCurrency(metrics.var.value)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">CVaR (95%)</span>
                <span className="text-red-500 font-mono">{formatCurrency(metrics.var.cvar || 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">VaR (99%)</span>
                <span className="text-orange-500 font-mono">{formatCurrency(metrics.var.var99 || 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Period</span>
                <span className="text-white">{metrics.var.period || '1d'}</span>
              </div>
            </div>
          )}
          {selectedMetric === 'sharpe' && (
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-400">Sharpe Ratio</span>
                <span className="text-white font-mono">{metrics.sharpeRatio?.toFixed(2) || 'N/A'}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Annualized Return</span>
                <span className="text-green-500 font-mono">{formatPercentage(metrics.annualizedReturn || 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Risk-Free Rate</span>
                <span className="text-white font-mono">{formatPercentage(metrics.riskFreeRate || 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Volatility</span>
                <span className="text-yellow-500 font-mono">{formatPercentage(metrics.volatility || 0)}</span>
              </div>
            </div>
          )}
          {selectedMetric === 'drawdown' && (
            <div className="space-y-3">
              <div className="flex justify-between">
                <span className="text-gray-400">Max Drawdown</span>
                <span className="text-red-500 font-mono">{formatPercentage(metrics.drawdown?.max || 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Current Drawdown</span>
                <span className="text-yellow-500 font-mono">{formatPercentage(metrics.drawdown?.current || 0)}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Duration</span>
                <span className="text-white font-mono">{metrics.drawdown?.duration || 0} days</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-400">Peak Date</span>
                <span className="text-white">{formatDate(metrics.drawdown?.peakDate || new Date())}</span>
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
          <Toast            message={showToast.message}
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

export default RiskMetrics;

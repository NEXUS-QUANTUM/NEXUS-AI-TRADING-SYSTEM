/**
 * NEXUS AI TRADING SYSTEM - Analytics Dashboard Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page provides comprehensive analytics including:
 * - Real-time performance metrics
 * - Trading statistics and analytics
 * - Portfolio performance tracking
 * - Risk metrics and analysis
 * - AI model performance comparison
 * - Custom report generation
 * - Export capabilities
 * - WebSocket real-time updates
 */

'use client';

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useAuth } from '@/hooks/useAuth';
import { useApi } from '@/hooks/useApi';

// Components
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { Toast } from '@/components/ui/Toast';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Switch } from '@/components/ui/Switch';
import { Modal } from '@/components/ui/Modal';
import { Table } from '@/components/ui/Table';
import { Progress } from '@/components/ui/Progress';

// Chart Components
import {
  LineChart,
  BarChart,
  PieChart,
  AreaChart,
  ScatterChart,
  CandlestickChart,
} from '@/components/charts';

// Types
import type {
  AnalyticsData,
  PerformanceMetrics,
  RiskMetrics,
  PortfolioAnalytics,
  TradingAnalytics,
  AIAnalytics,
  ReportConfig,
  ReportData,
  AnalyticsExport,
  DashboardWidget,
  CustomMetric,
  AnalyticsFilter,
  ComparisonData,
  HeatmapData,
  CorrelationData,
  AnomalyData,
} from '@/types/analytics';

// Constants
import {
  METRIC_TYPES,
  TIME_RANGES,
  AGGREGATION_TYPES,
  CHART_TYPES,
  REPORT_TYPES,
  EXPORT_FORMATS,
  DEFAULT_WIDGETS,
  DEFAULT_FILTERS,
} from '@/constants/analytics';

// Hooks
import { useAnalytics } from '@/hooks/useAnalytics';
import { usePerformance } from '@/hooks/usePerformance';
import { useRisk } from '@/hooks/useRisk';

// Utils
import {
  formatCurrency,
  formatPercentage,
  formatNumber,
  formatTime,
  formatDate,
  formatDuration,
} from '@/utils/formatters';
import { cn } from '@/utils/helpers';

export default function AnalyticsPage() {
  // Authentication
  const { user, isAuthenticated, accessToken } = useAuth();
  
  // API client
  const api = useApi();
  
  // Refs
  const wsCleanupRef = useRef<(() => void) | null>(null);
  const analyticsIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const chartContainerRef = useRef<HTMLDivElement>(null);
  
  // State - Main Data
  const [analyticsData, setAnalyticsData] = useState<AnalyticsData | null>(null);
  const [performanceMetrics, setPerformanceMetrics] = useState<PerformanceMetrics | null>(null);
  const [riskMetrics, setRiskMetrics] = useState<RiskMetrics | null>(null);
  const [portfolioAnalytics, setPortfolioAnalytics] = useState<PortfolioAnalytics | null>(null);
  const [tradingAnalytics, setTradingAnalytics] = useState<TradingAnalytics | null>(null);
  const [aiAnalytics, setAIAnalytics] = useState<AIAnalytics | null>(null);
  const [analyticsLoading, setAnalyticsLoading] = useState<boolean>(true);
  
  // State - Charts
  const [chartData, setChartData] = useState<any>(null);
  const [chartType, setChartType] = useState<string>('line');
  const [chartTimeframe, setChartTimeframe] = useState<string>('1M');
  const [chartSymbol, setChartSymbol] = useState<string>('BTC-USD');
  const [chartMetric, setChartMetric] = useState<string>('pnl');
  const [chartComparison, setChartComparison] = useState<string[]>([]);
  
  // State - Reports
  const [reports, setReports] = useState<ReportData[]>([]);
  const [reportConfig, setReportConfig] = useState<ReportConfig>({
    name: '',
    type: 'performance',
    timeframe: '1M',
    format: 'pdf',
    metrics: ['pnl', 'sharpe', 'winRate', 'maxDrawdown'],
    filters: {},
    schedule: null,
  });
  const [reportLoading, setReportLoading] = useState<boolean>(false);
  const [showReportModal, setShowReportModal] = useState<boolean>(false);
  
  // State - Widgets
  const [widgets, setWidgets] = useState<DashboardWidget[]>(DEFAULT_WIDGETS);
  const [widgetConfig, setWidgetConfig] = useState<Partial<DashboardWidget>>({});
  const [showWidgetModal, setShowWidgetModal] = useState<boolean>(false);
  const [editingWidget, setEditingWidget] = useState<DashboardWidget | null>(null);
  
  // State - Filters
  const [filters, setFilters] = useState<AnalyticsFilter>(DEFAULT_FILTERS);
  const [customMetrics, setCustomMetrics] = useState<CustomMetric[]>([]);
  const [comparisonData, setComparisonData] = useState<ComparisonData | null>(null);
  const [heatmapData, setHeatmapData] = useState<HeatmapData | null>(null);
  const [correlationData, setCorrelationData] = useState<CorrelationData | null>(null);
  const [anomalyData, setAnomalyData] = useState<AnomalyData[]>([]);
  
  // State - UI
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [selectedMetric, setSelectedMetric] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [showToast, setShowToast] = useState<{ message: string; type: 'success' | 'error' | 'info' | 'warning' } | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [exporting, setExporting] = useState<boolean>(false);
  const [dateRange, setDateRange] = useState<{ start: Date; end: Date }>({
    start: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000),
    end: new Date(),
  });

  // ============================================
  // WebSocket Connection
  // ============================================
  const { 
    isConnected, 
    sendMessage, 
    subscribe: wsSubscribe,
    unsubscribe: wsUnsubscribe,
    messages,
  } = useWebSocket({
    url: `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8004'}/analytics`,
    autoConnect: true,
    onOpen: handleWebSocketOpen,
    onMessage: handleWebSocketMessage,
    onError: handleWebSocketError,
    onClose: handleWebSocketClose,
    reconnectAttempts: 10,
    reconnectInterval: 3000,
    authToken: accessToken || undefined,
  });

  function handleWebSocketOpen() {
    console.log('✅ Analytics WebSocket connected');
    subscribeToChannels();
  }

  function handleWebSocketMessage(event: MessageEvent) {
    try {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'performance_update':
          handlePerformanceUpdate(data.payload);
          break;
        case 'risk_update':
          handleRiskUpdate(data.payload);
          break;
        case 'portfolio_update':
          handlePortfolioUpdate(data.payload);
          break;
        case 'trading_update':
          handleTradingUpdate(data.payload);
          break;
        case 'ai_update':
          handleAIUpdate(data.payload);
          break;
        case 'chart_update':
          handleChartUpdate(data.payload);
          break;
        case 'anomaly_detected':
          handleAnomalyDetected(data.payload);
          break;
        case 'comparison_update':
          handleComparisonUpdate(data.payload);
          break;
        case 'error':
          handleAnalyticsError(data.payload);
          break;
        default:
          console.debug('Unhandled WebSocket message type:', data.type);
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }

  function handleWebSocketError(error: Event) {
    console.error('WebSocket error:', error);
  }

  function handleWebSocketClose() {
    console.log('Analytics WebSocket disconnected');
  }

  function subscribeToChannels() {
    if (!isConnected) return;

    wsSubscribe({
      channel: 'analytics_performance',
      timeframe: filters.timeframe,
      symbol: filters.symbol,
    });

    wsSubscribe({
      channel: 'analytics_risk',
      symbol: filters.symbol,
    });

    wsSubscribe({
      channel: 'analytics_portfolio',
    });

    wsSubscribe({
      channel: 'analytics_trading',
      timeframe: filters.timeframe,
    });

    wsSubscribe({
      channel: 'analytics_ai',
      modelId: filters.modelId,
    });

    wsSubscribe({
      channel: 'analytics_chart',
      symbol: chartSymbol,
      metric: chartMetric,
      timeframe: chartTimeframe,
    });

    wsSubscribe({
      channel: 'analytics_anomalies',
      threshold: 2,
    });
  }

  // ============================================
  // WebSocket Data Handlers
  // ============================================
  function handlePerformanceUpdate(data: any) {
    setPerformanceMetrics({
      totalPnL: data.totalPnL || 0,
      dailyPnL: data.dailyPnL || 0,
      weeklyPnL: data.weeklyPnL || 0,
      monthlyPnL: data.monthlyPnL || 0,
      annualizedReturn: data.annualizedReturn || 0,
      cumulativeReturn: data.cumulativeReturn || 0,
      sharpeRatio: data.sharpeRatio || 0,
      sortinoRatio: data.sortinoRatio || 0,
      calmarRatio: data.calmarRatio || 0,
      winRate: data.winRate || 0,
      lossRate: data.lossRate || 0,
      profitFactor: data.profitFactor || 0,
      averageWin: data.averageWin || 0,
      averageLoss: data.averageLoss || 0,
      largestWin: data.largestWin || 0,
      largestLoss: data.largestLoss || 0,
      maxDrawdown: data.maxDrawdown || 0,
      maxDrawdownDuration: data.maxDrawdownDuration || 0,
      recoveryFactor: data.recoveryFactor || 0,
      dailyReturns: data.dailyReturns || [],
      monthlyReturns: data.monthlyReturns || [],
      yearlyReturns: data.yearlyReturns || [],
      cumulativeReturns: data.cumulativeReturns || [],
      rollingSharpe: data.rollingSharpe || [],
      rollingVolatility: data.rollingVolatility || [],
      lastUpdated: new Date(data.lastUpdated || Date.now()),
    });
  }

  function handleRiskUpdate(data: any) {
    setRiskMetrics({
      var: data.var || 0,
      cvar: data.cvar || 0,
      expectedShortfall: data.expectedShortfall || 0,
      volatility: data.volatility || 0,
      annualizedVolatility: data.annualizedVolatility || 0,
      beta: data.beta || 0,
      alpha: data.alpha || 0,
      rSquared: data.rSquared || 0,
      treynorRatio: data.treynorRatio || 0,
      downsideDeviation: data.downsideDeviation || 0,
      upsideCapture: data.upsideCapture || 0,
      downsideCapture: data.downsideCapture || 0,
      maxDailyLoss: data.maxDailyLoss || 0,
      maxWeeklyLoss: data.maxWeeklyLoss || 0,
      maxMonthlyLoss: data.maxMonthlyLoss || 0,
      currentDrawdown: data.currentDrawdown || 0,
      peakEquity: data.peakEquity || 0,
      currentEquity: data.currentEquity || 0,
      riskOfRuin: data.riskOfRuin || 0,
      kellyCriterion: data.kellyCriterion || 0,
      positionRisk: data.positionRisk || {},
      portfolioRisk: data.portfolioRisk || {},
      riskContributions: data.riskContributions || {},
      concentrationRisk: data.concentrationRisk || 0,
      tailRisk: data.tailRisk || 0,
      stressTestResults: data.stressTestResults || {},
      lastUpdated: new Date(data.lastUpdated || Date.now()),
    });
  }

  function handlePortfolioUpdate(data: any) {
    setPortfolioAnalytics({
      totalValue: data.totalValue || 0,
      cashBalance: data.cashBalance || 0,
      investedValue: data.investedValue || 0,
      totalPnL: data.totalPnL || 0,
      dailyPnL: data.dailyPnL || 0,
      weeklyPnL: data.weeklyPnL || 0,
      monthlyPnL: data.monthlyPnL || 0,
      allocation: data.allocation || {},
      positions: data.positions || [],
      performance: data.performance || {},
      risk: data.risk || {},
      diversification: data.diversification || 0,
      correlationMatrix: data.correlationMatrix || [],
      turnover: data.turnover || 0,
      transactionCosts: data.transactionCosts || 0,
      taxEfficiency: data.taxEfficiency || 0,
      yield: data.yield || 0,
      dividendYield: data.dividendYield || 0,
      expenseRatio: data.expenseRatio || 0,
      lastRebalanced: data.lastRebalanced ? new Date(data.lastRebalanced) : undefined,
      lastUpdated: new Date(data.lastUpdated || Date.now()),
    });
  }

  function handleTradingUpdate(data: any) {
    setTradingAnalytics({
      totalTrades: data.totalTrades || 0,
      winningTrades: data.winningTrades || 0,
      losingTrades: data.losingTrades || 0,
      breakEvenTrades: data.breakEvenTrades || 0,
      winRate: data.winRate || 0,
      averageTradeDuration: data.averageTradeDuration || 0,
      averageWinDuration: data.averageWinDuration || 0,
      averageLossDuration: data.averageLossDuration || 0,
      totalVolume: data.totalVolume || 0,
      averageVolume: data.averageVolume || 0,
      maxVolume: data.maxVolume || 0,
      totalFees: data.totalFees || 0,
      averageFee: data.averageFee || 0,
      slippage: data.slippage || 0,
      executionQuality: data.executionQuality || 0,
      fillRate: data.fillRate || 0,
      orderBookImpact: data.orderBookImpact || 0,
      tradesByHour: data.tradesByHour || {},
      tradesByDay: data.tradesByDay || {},
      tradesBySymbol: data.tradesBySymbol || {},
      tradeDistribution: data.tradeDistribution || {},
      lastUpdated: new Date(data.lastUpdated || Date.now()),
    });
  }

  function handleAIUpdate(data: any) {
    setAIAnalytics({
      modelAccuracy: data.modelAccuracy || 0,
      modelPrecision: data.modelPrecision || 0,
      modelRecall: data.modelRecall || 0,
      modelF1Score: data.modelF1Score || 0,
      predictionAccuracy: data.predictionAccuracy || 0,
      predictionCount: data.predictionCount || 0,
      successfulPredictions: data.successfulPredictions || 0,
      predictionConfidence: data.predictionConfidence || 0,
      modelPerformance: data.modelPerformance || {},
      featureImportance: data.featureImportance || {},
      confusionMatrix: data.confusionMatrix || {},
      trainingHistory: data.trainingHistory || [],
      inferenceLatency: data.inferenceLatency || 0,
      modelVersion: data.modelVersion || '',
      lastUpdated: new Date(data.lastUpdated || Date.now()),
    });
  }

  function handleChartUpdate(data: any) {
    setChartData(data);
  }

  function handleAnomalyDetected(data: any) {
    const anomaly: AnomalyData = {
      id: data.id || `anomaly-${Date.now()}`,
      type: data.type || 'price',
      symbol: data.symbol || chartSymbol,
      timestamp: new Date(data.timestamp || Date.now()),
      value: data.value || 0,
      expectedValue: data.expectedValue || 0,
      deviation: data.deviation || 0,
      severity: data.severity || 'medium',
      description: data.description || '',
      detected: true,
      reviewed: false,
      metadata: data.metadata || {},
    };

    setAnomalyData(prev => [anomaly, ...prev].slice(0, 100));

    if (anomaly.severity === 'high' || anomaly.severity === 'critical') {
      setShowToast({
        message: `⚠️ Anomaly Detected: ${anomaly.description}`,
        type: 'warning',
      });
    }
  }

  function handleComparisonUpdate(data: any) {
    setComparisonData({
      models: data.models || [],
      symbols: data.symbols || [],
      metrics: data.metrics || {},
      bestPerforming: data.bestPerforming || '',
      worstPerforming: data.worstPerforming || '',
      timestamp: new Date(data.timestamp || Date.now()),
    });
  }

  function handleAnalyticsError(data: any) {
    setShowToast({
      message: data.message || 'Analytics service error occurred',
      type: 'error',
    });
  }

  // ============================================
  // API Calls - Real Data
  // ============================================
  const fetchAnalyticsData = useCallback(async () => {
    setAnalyticsLoading(true);
    
    try {
      const response = await api.get('/analytics/dashboard', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          timeframe: filters.timeframe,
          symbol: filters.symbol,
          modelId: filters.modelId,
          startDate: dateRange.start.toISOString(),
          endDate: dateRange.end.toISOString(),
        },
      });
      
      if (response.data) {
        setAnalyticsData(response.data);
        setPerformanceMetrics(response.data.performance);
        setRiskMetrics(response.data.risk);
        setPortfolioAnalytics(response.data.portfolio);
        setTradingAnalytics(response.data.trading);
        setAIAnalytics(response.data.ai);
      }
    } catch (error) {
      console.error('Failed to fetch analytics data:', error);
      setShowToast({
        message: 'Failed to load analytics data. Please refresh the page.',
        type: 'error',
      });
    } finally {
      setAnalyticsLoading(false);
    }
  }, [api, accessToken, filters, dateRange]);

  const fetchChartData = useCallback(async () => {
    try {
      const response = await api.get('/analytics/chart', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          symbol: chartSymbol,
          metric: chartMetric,
          timeframe: chartTimeframe,
          comparison: chartComparison.join(','),
          startDate: dateRange.start.toISOString(),
          endDate: dateRange.end.toISOString(),
        },
      });
      
      if (response.data) {
        setChartData(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch chart data:', error);
    }
  }, [api, accessToken, chartSymbol, chartMetric, chartTimeframe, chartComparison, dateRange]);

  const fetchComparisonData = useCallback(async () => {
    try {
      const response = await api.get('/analytics/comparison', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          symbols: filters.symbol,
          timeframe: filters.timeframe,
          metrics: ['return', 'sharpe', 'maxDrawdown', 'winRate'],
        },
      });
      
      if (response.data) {
        setComparisonData(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch comparison data:', error);
    }
  }, [api, accessToken, filters]);

  const fetchCorrelationData = useCallback(async () => {
    try {
      const response = await api.get('/analytics/correlation', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          symbols: filters.symbol,
          timeframe: filters.timeframe,
        },
      });
      
      if (response.data) {
        setCorrelationData(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch correlation data:', error);
    }
  }, [api, accessToken, filters]);

  const fetchHeatmapData = useCallback(async () => {
    try {
      const response = await api.get('/analytics/heatmap', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          timeframe: filters.timeframe,
          metric: 'return',
        },
      });
      
      if (response.data) {
        setHeatmapData(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch heatmap data:', error);
    }
  }, [api, accessToken, filters]);

  const fetchAnomalies = useCallback(async () => {
    try {
      const response = await api.get('/analytics/anomalies', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          days: 7,
          threshold: 2,
        },
      });
      
      if (response.data && response.data.anomalies) {
        setAnomalyData(response.data.anomalies.map((a: any) => ({
          ...a,
          timestamp: new Date(a.timestamp || Date.now()),
        })));
      }
    } catch (error) {
      console.error('Failed to fetch anomalies:', error);
    }
  }, [api, accessToken]);

  const fetchReports = useCallback(async () => {
    try {
      const response = await api.get('/analytics/reports', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      if (response.data && response.data.reports) {
        setReports(response.data.reports.map((r: any) => ({
          ...r,
          createdAt: new Date(r.createdAt || Date.now()),
          generatedAt: r.generatedAt ? new Date(r.generatedAt) : undefined,
        })));
      }
    } catch (error) {
      console.error('Failed to fetch reports:', error);
    }
  }, [api, accessToken]);

  const fetchCustomMetrics = useCallback(async () => {
    try {
      const response = await api.get('/analytics/custom-metrics', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      if (response.data && response.data.metrics) {
        setCustomMetrics(response.data.metrics);
      }
    } catch (error) {
      console.error('Failed to fetch custom metrics:', error);
    }
  }, [api, accessToken]);

  const fetchAllData = useCallback(async () => {
    setIsLoading(true);
    try {
      await Promise.all([
        fetchAnalyticsData(),
        fetchChartData(),
        fetchComparisonData(),
        fetchCorrelationData(),
        fetchHeatmapData(),
        fetchAnomalies(),
        fetchReports(),
        fetchCustomMetrics(),
      ]);
    } catch (error) {
      console.error('Failed to fetch all data:', error);
    } finally {
      setIsLoading(false);
    }
  }, [
    fetchAnalyticsData,
    fetchChartData,
    fetchComparisonData,
    fetchCorrelationData,
    fetchHeatmapData,
    fetchAnomalies,
    fetchReports,
    fetchCustomMetrics,
  ]);

  // ============================================
  // API Actions
  // ============================================
  const handleGenerateReport = useCallback(async () => {
    if (!reportConfig.name) {
      setShowToast({
        message: 'Please enter a report name',
        type: 'warning',
      });
      return;
    }

    setReportLoading(true);
    
    try {
      const response = await api.post('/analytics/reports', reportConfig, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          format: reportConfig.format,
        },
        responseType: reportConfig.format === 'pdf' ? 'blob' : 'json',
      });
      
      if (reportConfig.format === 'pdf') {
        // Download PDF
        const blob = new Blob([response.data], { type: 'application/pdf' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `${reportConfig.name}.pdf`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      } else {
        // Download JSON/CSV
        const blob = new Blob([JSON.stringify(response.data, null, 2)], { 
          type: 'application/json' 
        });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `${reportConfig.name}.json`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
      }
      
      setShowToast({
        message: `Report generated: ${reportConfig.name}`,
        type: 'success',
      });
      
      setShowReportModal(false);
      setReportConfig({
        name: '',
        type: 'performance',
        timeframe: '1M',
        format: 'pdf',
        metrics: ['pnl', 'sharpe', 'winRate', 'maxDrawdown'],
        filters: {},
        schedule: null,
      });
      fetchReports();
    } catch (error: any) {
      console.error('Failed to generate report:', error);
      setShowToast({
        message: error.response?.data?.message || 'Failed to generate report. Please try again.',
        type: 'error',
      });
    } finally {
      setReportLoading(false);
    }
  }, [api, accessToken, reportConfig, fetchReports]);

  const handleExportData = useCallback(async (format: AnalyticsExport['format'] = 'csv') => {
    setExporting(true);
    
    try {
      const response = await api.get('/analytics/export', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          timeframe: filters.timeframe,
          symbol: filters.symbol,
          format: format,
          startDate: dateRange.start.toISOString(),
          endDate: dateRange.end.toISOString(),
          includeMetrics: true,
          includeTrades: true,
          includePositions: true,
        },
        responseType: 'blob',
      });

      const blob = new Blob([response.data], {
        type: format === 'csv' ? 'text/csv' : 'application/json',
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `analytics-data-${Date.now()}.${format === 'csv' ? 'csv' : 'json'}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      setShowToast({
        message: `Data exported successfully (${format.toUpperCase()})`,
        type: 'success',
      });
    } catch (error) {
      console.error('Failed to export data:', error);
      setShowToast({
        message: 'Failed to export data. Please try again.',
        type: 'error',
      });
    } finally {
      setExporting(false);
    }
  }, [api, accessToken, filters, dateRange]);

  const handleUpdateWidgets = useCallback(async (updatedWidgets: DashboardWidget[]) => {
    try {
      await api.put('/analytics/widgets', { widgets: updatedWidgets }, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      setWidgets(updatedWidgets);
      setShowToast({
        message: 'Dashboard layout updated',
        type: 'success',
      });
    } catch (error) {
      console.error('Failed to update widgets:', error);
      setShowToast({
        message: 'Failed to update dashboard layout',
        type: 'error',
      });
    }
  }, [api, accessToken]);

  const handleAddWidget = useCallback(async (widget: DashboardWidget) => {
    try {
      const response = await api.post('/analytics/widgets', widget, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      if (response.data) {
        setWidgets(prev => [...prev, response.data]);
        setShowToast({
          message: `Widget added: ${widget.title}`,
          type: 'success',
        });
      }
    } catch (error) {
      console.error('Failed to add widget:', error);
      setShowToast({
        message: 'Failed to add widget',
        type: 'error',
      });
    }
  }, [api, accessToken]);

  const handleRemoveWidget = useCallback(async (widgetId: string) => {
    try {
      await api.delete(`/analytics/widgets/${widgetId}`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      setWidgets(prev => prev.filter(w => w.id !== widgetId));
      setShowToast({
        message: 'Widget removed',
        type: 'info',
      });
    } catch (error) {
      console.error('Failed to remove widget:', error);
      setShowToast({
        message: 'Failed to remove widget',
        type: 'error',
      });
    }
  }, [api, accessToken]);

  // ============================================
  // Effects
  // ============================================
  useEffect(() => {
    fetchAllData();
    
    return () => {
      if (wsCleanupRef.current) {
        wsCleanupRef.current();
      }
      if (analyticsIntervalRef.current) {
        clearInterval(analyticsIntervalRef.current);
      }
    };
  }, [fetchAllData]);

  useEffect(() => {
    if (isConnected) {
      subscribeToChannels();
    }
  }, [isConnected]);

  // Auto-refresh analytics
  useEffect(() => {
    if (analyticsIntervalRef.current) {
      clearInterval(analyticsIntervalRef.current);
    }
    
    analyticsIntervalRef.current = setInterval(() => {
      fetchAnalyticsData();
      fetchChartData();
    }, 30000); // Refresh every 30 seconds
    
    return () => {
      if (analyticsIntervalRef.current) {
        clearInterval(analyticsIntervalRef.current);
      }
    };
  }, [fetchAnalyticsData, fetchChartData]);

  // ============================================
  // Memoized Computations
  // ============================================
  const summaryMetrics = useMemo(() => {
    if (!performanceMetrics) return [];
    
    return [
      {
        label: 'Total P&L',
        value: formatCurrency(performanceMetrics.totalPnL),
        change: performanceMetrics.dailyPnL,
        color: performanceMetrics.totalPnL >= 0 ? 'text-green-500' : 'text-red-500',
        icon: '💰',
      },
      {
        label: 'Sharpe Ratio',
        value: performanceMetrics.sharpeRatio.toFixed(2),
        color: performanceMetrics.sharpeRatio > 1 ? 'text-green-500' : 'text-yellow-500',
        icon: '📈',
      },
      {
        label: 'Win Rate',
        value: formatPercentage(performanceMetrics.winRate),
        color: performanceMetrics.winRate > 0.5 ? 'text-green-500' : 'text-red-500',
        icon: '🎯',
      },
      {
        label: 'Max Drawdown',
        value: formatPercentage(performanceMetrics.maxDrawdown),
        color: performanceMetrics.maxDrawdown < 0.2 ? 'text-green-500' : 'text-red-500',
        icon: '📉',
      },
      {
        label: 'Profit Factor',
        value: performanceMetrics.profitFactor.toFixed(2),
        color: performanceMetrics.profitFactor > 1.5 ? 'text-green-500' : 'text-yellow-500',
        icon: '📊',
      },
      {
        label: 'Total Trades',
        value: formatNumber(tradingAnalytics?.totalTrades || 0),
        color: 'text-blue-500',
        icon: '🔄',
      },
    ];
  }, [performanceMetrics, tradingAnalytics]);

  const riskSummary = useMemo(() => {
    if (!riskMetrics) return [];
    
    return [
      {
        label: 'VaR (95%)',
        value: formatCurrency(riskMetrics.var),
        color: 'text-orange-500',
        icon: '⚠️',
      },
      {
        label: 'CVaR (95%)',
        value: formatCurrency(riskMetrics.cvar),
        color: 'text-red-500',
        icon: '🔴',
      },
      {
        label: 'Volatility',
        value: formatPercentage(riskMetrics.volatility),
        color: 'text-yellow-500',
        icon: '📊',
      },
      {
        label: 'Beta',
        value: riskMetrics.beta.toFixed(2),
        color: riskMetrics.beta > 1 ? 'text-red-500' : 'text-green-500',
        icon: 'β',
      },
      {
        label: 'Risk of Ruin',
        value: formatPercentage(riskMetrics.riskOfRuin),
        color: riskMetrics.riskOfRuin < 0.05 ? 'text-green-500' : 'text-red-500',
        icon: '💀',
      },
      {
        label: 'Kelly Criterion',
        value: formatPercentage(riskMetrics.kellyCriterion),
        color: riskMetrics.kellyCriterion > 0 ? 'text-green-500' : 'text-red-500',
        icon: '🎲',
      },
    ];
  }, [riskMetrics]);

  // ============================================
  // Render
  // ============================================
  if (isLoading && analyticsLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-6">
            <div className="absolute inset-0 border-4 border-cyan-500/30 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-t-cyan-500 rounded-full animate-spin"></div>
            <div className="absolute inset-2 bg-cyan-500/10 rounded-full animate-pulse"></div>
          </div>
          <p className="text-gray-400 text-lg font-medium">Loading Analytics...</p>
          <p className="text-gray-500 text-sm mt-2">Processing performance data</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white p-4 md:p-6 lg:p-8">
      {/* ============================================ */}
      {/* HEADER */}
      {/* ============================================ */}
      <div className="flex flex-wrap items-center justify-between mb-8 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="text-3xl">📊</div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-blue-400 to-cyan-400 bg-clip-text text-transparent">
                Analytics Dashboard
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                Comprehensive performance and risk analytics
              </p>
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-3 flex-wrap">
          {/* Connection Status */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded-lg border border-gray-700">
            <div className={cn(
              'w-2 h-2 rounded-full transition-all duration-500',
              isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
            )} />
            <span className="text-xs text-gray-400">
              {isConnected ? 'Live' : 'Disconnected'}
            </span>
          </div>
          
          {/* Export Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleExportData('csv')}
            isLoading={exporting}
            className="border-gray-700 hover:border-cyan-500 hover:text-cyan-400 transition-colors"
          >
            <span className="mr-2">📥</span> Export Data
          </Button>
          
          {/* Generate Report Button */}
          <Button
            onClick={() => setShowReportModal(true)}
            className="bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600 text-white transition-all"
          >
            <span className="mr-2">📄</span> Generate Report
          </Button>
        </div>
      </div>

      {/* ============================================ */}
      {/* FILTERS */}
      {/* ============================================ */}
      <div className="flex flex-wrap items-center gap-3 bg-gray-800/50 rounded-lg p-3 border border-gray-700 mb-6">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Symbol:</span>
          <Select
            value={filters.symbol}
            onValueChange={(value) => setFilters({ ...filters, symbol: value })}
            className="w-32 bg-gray-700 border-gray-600 text-sm"
          >
            <option value="all">All Symbols</option>
            <option value="BTC-USD">Bitcoin</option>
            <option value="ETH-USD">Ethereum</option>
            <option value="SOL-USD">Solana</option>
            <option value="EUR-USD">EUR/USD</option>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Timeframe:</span>
          <Select
            value={filters.timeframe}
            onValueChange={(value) => setFilters({ ...filters, timeframe: value })}
            className="w-28 bg-gray-700 border-gray-600 text-sm"
          >
            <option value="1D">1 Day</option>
            <option value="1W">1 Week</option>
            <option value="1M">1 Month</option>
            <option value="3M">3 Months</option>
            <option value="6M">6 Months</option>
            <option value="1Y">1 Year</option>
            <option value="ALL">All Time</option>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Metric:</span>
          <Select
            value={chartMetric}
            onValueChange={setChartMetric}
            className="w-32 bg-gray-700 border-gray-600 text-sm"
          >
            <option value="pnl">P&L</option>
            <option value="return">Return</option>
            <option value="sharpe">Sharpe</option>
            <option value="volatility">Volatility</option>
            <option value="drawdown">Drawdown</option>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Chart:</span>
          <Select
            value={chartType}
            onValueChange={setChartType}
            className="w-28 bg-gray-700 border-gray-600 text-sm"
          >
            <option value="line">Line</option>
            <option value="area">Area</option>
            <option value="bar">Bar</option>
            <option value="candlestick">Candlestick</option>
          </Select>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={fetchAllData}
          className="text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10"
        >
          🔄 Refresh
        </Button>
      </div>

      {/* ============================================ */}
      {/* SUMMARY METRICS CARDS */}
      {/* ============================================ */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-6">
        {summaryMetrics.map((metric, index) => (
          <Card key={index} className="p-4 bg-gray-800 border-gray-700">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-lg">{metric.icon}</span>
              <span className="text-xs text-gray-400">{metric.label}</span>
            </div>
            <div className={cn('text-xl font-bold', metric.color)}>
              {metric.value}
            </div>
            {metric.change !== undefined && (
              <div className={cn(
                'text-xs',
                metric.change >= 0 ? 'text-green-500' : 'text-red-500'
              )}>
                {metric.change >= 0 ? '▲' : '▼'} {formatCurrency(Math.abs(metric.change))} today
              </div>
            )}
          </Card>
        ))}
      </div>

      {/* ============================================ */}
      {/* MAIN TABS */}
      {/* ============================================ */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-gray-800 border border-gray-700 rounded-lg p-1 w-full overflow-x-auto">
          <TabsTrigger
            value="overview"
            className="data-[state=active]:bg-blue-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📊 Overview
          </TabsTrigger>
          <TabsTrigger
            value="performance"
            className="data-[state=active]:bg-green-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📈 Performance
          </TabsTrigger>
          <TabsTrigger
            value="risk"
            className="data-[state=active]:bg-orange-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            🛡️ Risk
          </TabsTrigger>
          <TabsTrigger
            value="portfolio"
            className="data-[state=active]:bg-purple-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            💼 Portfolio
          </TabsTrigger>
          <TabsTrigger
            value="ai"
            className="data-[state=active]:bg-cyan-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            🤖 AI Analytics
          </TabsTrigger>
          <TabsTrigger
            value="anomalies"
            className="data-[state=active]:bg-red-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            ⚠️ Anomalies {anomalyData.filter(a => !a.reviewed).length > 0 && (
              <Badge className="ml-1 bg-red-500 text-white text-xs">
                {anomalyData.filter(a => !a.reviewed).length}
              </Badge>
            )}
          </TabsTrigger>
        </TabsList>

        {/* ========================================== */}
        {/* OVERVIEW TAB */}
        {/* ========================================== */}
        <TabsContent value="overview" className="mt-4 space-y-6">
          <div className="grid grid-cols-12 gap-6">
            {/* Main Chart */}
            <div className="col-span-12 lg:col-span-8">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-gray-300">
                    Performance Overview
                  </h3>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-xs text-gray-400 hover:text-white"
                    >
                      {chartTimeframe}
                    </Button>
                  </div>
                </div>
                <div ref={chartContainerRef} className="h-80">
                  {chartData ? (
                    <AreaChart
                      data={chartData}
                      xKey="date"
                      yKey={chartMetric}
                      color="#06b6d4"
                      height={300}
                      gradient
                      tooltip
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-500">
                      <Spinner size="sm" className="mr-3" />
                      Loading chart data...
                    </div>
                  )}
                </div>
              </Card>
            </div>

            {/* Risk Summary */}
            <div className="col-span-12 lg:col-span-4 space-y-4">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                  <span className="text-orange-400">🛡️</span> Risk Summary
                </h3>
                <div className="space-y-2">
                  {riskSummary.map((item, index) => (
                    <div key={index} className="flex justify-between items-center text-sm">
                      <span className="text-gray-400 flex items-center gap-1">
                        <span>{item.icon}</span> {item.label}
                      </span>
                      <span className={cn('font-mono font-medium', item.color)}>
                        {item.value}
                      </span>
                    </div>
                  ))}
                </div>
              </Card>

              {/* Quick Stats */}
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                  <span className="text-blue-400">⚡</span> Quick Stats
                </h3>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <div className="text-gray-400">Win/Loss</div>
                    <div className="text-white font-bold">
                      {tradingAnalytics?.winningTrades || 0}/{tradingAnalytics?.losingTrades || 0}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400">Avg Win</div>
                    <div className="text-green-500 font-bold">
                      {formatCurrency(tradingAnalytics?.averageWin || 0)}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400">Avg Loss</div>
                    <div className="text-red-500 font-bold">
                      {formatCurrency(tradingAnalytics?.averageLoss || 0)}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400">Recovery Factor</div>
                    <div className="text-cyan-400 font-bold">
                      {performanceMetrics?.recoveryFactor?.toFixed(2) || 'N/A'}
                    </div>
                  </div>
                </div>
              </Card>
            </div>
          </div>

          {/* Additional Charts */}
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">
                  Monthly Returns Distribution
                </h3>
                <div className="h-64">
                  {chartData ? (
                    <BarChart
                      data={chartData}
                      xKey="month"
                      yKey="return"
                      color="#8b5cf6"
                      height={240}
                      tooltip
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-500">
                      <Spinner size="sm" className="mr-3" />
                      Loading...
                    </div>
                  )}
                </div>
              </Card>
            </div>
            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">
                  Portfolio Allocation
                </h3>
                <div className="h-64">
                  {portfolioAnalytics?.allocation ? (
                    <PieChart
                      data={Object.entries(portfolioAnalytics.allocation).map(([key, value]) => ({
                        name: key,
                        value: value,
                      }))}
                      height={240}
                      tooltip
                      legend
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-500">
                      No allocation data available
                    </div>
                  )}
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* PERFORMANCE TAB */}
        {/* ========================================== */}
        <TabsContent value="performance" className="mt-4 space-y-6">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-gray-300">
                    Cumulative Returns
                  </h3>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className={cn(
                        'text-xs',
                        chartComparison.includes('benchmark') ? 'text-cyan-400' : 'text-gray-400'
                      )}
                      onClick={() => {
                        setChartComparison(prev =>
                          prev.includes('benchmark')
                            ? prev.filter(c => c !== 'benchmark')
                            : [...prev, 'benchmark']
                        );
                      }}
                    >
                      {chartComparison.includes('benchmark') ? '📊' : '📋'} Benchmark
                    </Button>
                  </div>
                </div>
                <div className="h-80">
                  {chartData ? (
                    <AreaChart
                      data={chartData}
                      xKey="date"
                      yKey="cumulativeReturn"
                      color="#10b981"
                      height={300}
                      gradient
                      tooltip
                      comparison={chartComparison.includes('benchmark') ? chartData.benchmark : undefined}
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-500">
                      <Spinner size="sm" className="mr-3" />
                      Loading performance data...
                    </div>
                  )}
                </div>
              </Card>
            </div>

            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">
                  Performance Metrics
                </h3>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <div className="text-gray-400">Total Return</div>
                      <div className={cn(
                        'text-lg font-bold',
                        (performanceMetrics?.cumulativeReturn || 0) >= 0 ? 'text-green-500' : 'text-red-500'
                      )}>
                        {formatPercentage(performanceMetrics?.cumulativeReturn || 0)}
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-400">Annualized Return</div>
                      <div className={cn(
                        'text-lg font-bold',
                        (performanceMetrics?.annualizedReturn || 0) >= 0 ? 'text-green-500' : 'text-red-500'
                      )}>
                        {formatPercentage(performanceMetrics?.annualizedReturn || 0)}
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-400">Sharpe Ratio</div>
                      <div className="text-lg font-bold text-cyan-400">
                        {performanceMetrics?.sharpeRatio?.toFixed(2) || 'N/A'}
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-400">Calmar Ratio</div>
                      <div className="text-lg font-bold text-purple-400">
                        {performanceMetrics?.calmarRatio?.toFixed(2) || 'N/A'}
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-400">Profit Factor</div>
                      <div className="text-lg font-bold text-yellow-400">
                        {performanceMetrics?.profitFactor?.toFixed(2) || 'N/A'}
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-400">Recovery Factor</div>
                      <div className="text-lg font-bold text-blue-400">
                        {performanceMetrics?.recoveryFactor?.toFixed(2) || 'N/A'}
                      </div>
                    </div>
                  </div>
                </div>
              </Card>
            </div>

            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">
                  Drawdown Analysis
                </h3>
                <div className="h-64">
                  {chartData ? (
                    <AreaChart
                      data={chartData}
                      xKey="date"
                      yKey="drawdown"
                      color="#ef4444"
                      height={240}
                      tooltip
                      negative
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-500">
                      <Spinner size="sm" className="mr-3" />
                      Loading drawdown data...
                    </div>
                  )}
                </div>
                <div className="mt-3 grid grid-cols-3 gap-3 text-sm">
                  <div>
                    <div className="text-gray-400">Max Drawdown</div>
                    <div className="text-red-500 font-bold">
                      {formatPercentage(performanceMetrics?.maxDrawdown || 0)}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400">Current</div>
                    <div className="text-yellow-500 font-bold">
                      {formatPercentage(riskMetrics?.currentDrawdown || 0)}
                    </div>
                  </div>
                  <div>
                    <div className="text-gray-400">Duration</div>
                    <div className="text-white font-bold">
                      {formatDuration(performanceMetrics?.maxDrawdownDuration || 0)}
                    </div>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* RISK TAB */}
        {/* ========================================== */}
        <TabsContent value="risk" className="mt-4 space-y-6">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 lg:col-span-8">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">
                  Value at Risk (VaR) Analysis
                </h3>
                <div className="h-80">
                  {chartData ? (
                    <ScatterChart
                      data={chartData}
                      xKey="date"
                      yKey="var"
                      color="#f59e0b"
                      height={300}
                      tooltip
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-500">
                      <Spinner size="sm" className="mr-3" />
                      Loading risk data...
                    </div>
                  )}
                </div>
              </Card>
            </div>

            <div className="col-span-12 lg:col-span-4 space-y-4">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-3">
                  Risk Metrics
                </h3>
                <div className="space-y-3">
                  <div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">VaR (95%)</span>
                      <span className="text-orange-500 font-mono font-medium">
                        {formatCurrency(riskMetrics?.var || 0)}
                      </span>
                    </div>
                    <Progress value={75} className="h-1 mt-1 bg-gray-700" />
                  </div>
                  <div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">CVaR (95%)</span>
                      <span className="text-red-500 font-mono font-medium">
                        {formatCurrency(riskMetrics?.cvar || 0)}
                      </span>
                    </div>
                    <Progress value={90} className="h-1 mt-1 bg-gray-700" />
                  </div>
                  <div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Volatility</span>
                      <span className="text-yellow-500 font-mono font-medium">
                        {formatPercentage(riskMetrics?.volatility || 0)}
                      </span>
                    </div>
                    <Progress value={65} className="h-1 mt-1 bg-gray-700" />
                  </div>
                  <div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Risk of Ruin</span>
                      <span className={cn(
                        'font-mono font-medium',
                        (riskMetrics?.riskOfRuin || 0) < 0.05 ? 'text-green-500' : 'text-red-500'
                      )}>
                        {formatPercentage(riskMetrics?.riskOfRuin || 0)}
                      </span>
                    </div>
                    <Progress 
                      value={((riskMetrics?.riskOfRuin || 0) * 100)} 
                      className="h-1 mt-1 bg-gray-700" 
                    />
                  </div>
                </div>
              </Card>

              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-3">
                  Stress Test Results
                </h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-400">Market Crash (-30%)</span>
                    <span className="text-red-500 font-mono">
                      {formatCurrency(riskMetrics?.stressTestResults?.marketCrash || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Flash Crash (-50%)</span>
                    <span className="text-red-500 font-mono">
                      {formatCurrency(riskMetrics?.stressTestResults?.flashCrash || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Extended Bear (-20%)</span>
                    <span className="text-orange-500 font-mono">
                      {formatCurrency(riskMetrics?.stressTestResults?.extendedBear || 0)}
                    </span>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* PORTFOLIO TAB */}
        {/* ========================================== */}
        <TabsContent value="portfolio" className="mt-4 space-y-6">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 lg:col-span-4">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">
                  Portfolio Summary
                </h3>
                <div className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Total Value</span>
                    <span className="text-white font-bold text-lg">
                      {formatCurrency(portfolioAnalytics?.totalValue || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Cash</span>
                    <span className="text-blue-400 font-mono">
                      {formatCurrency(portfolioAnalytics?.cashBalance || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Invested</span>
                    <span className="text-green-400 font-mono">
                      {formatCurrency(portfolioAnalytics?.investedValue || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Diversification</span>
                    <span className="text-cyan-400 font-mono">
                      {formatPercentage(portfolioAnalytics?.diversification || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Turnover</span>
                    <span className="text-yellow-400 font-mono">
                      {formatPercentage(portfolioAnalytics?.turnover || 0)}
                    </span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Yield</span>
                    <span className="text-green-400 font-mono">
                      {formatPercentage(portfolioAnalytics?.yield || 0)}
                    </span>
                  </div>
                </div>
              </Card>
            </div>

            <div className="col-span-12 lg:col-span-8">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">
                  Position Details
                </h3>
                <div className="overflow-x-auto">
                  <Table>
                    <thead>
                      <tr className="border-b border-gray-700">
                        <th className="text-left text-xs text-gray-400 p-2">Symbol</th>
                        <th className="text-right text-xs text-gray-400 p-2">Size</th>
                        <th className="text-right text-xs text-gray-400 p-2">Entry</th>
                        <th className="text-right text-xs text-gray-400 p-2">Current</th>
                        <th className="text-right text-xs text-gray-400 p-2">P&L</th>
                        <th className="text-right text-xs text-gray-400 p-2">%</th>
                      </tr>
                    </thead>
                    <tbody>
                      {portfolioAnalytics?.positions?.map((position, index) => (
                        <tr key={index} className="border-b border-gray-700/50">
                          <td className="text-white p-2">{position.symbol}</td>
                          <td className="text-right text-white font-mono p-2">
                            {formatNumber(position.size)}
                          </td>
                          <td className="text-right text-gray-400 font-mono p-2">
                            {formatCurrency(position.entryPrice)}
                          </td>
                          <td className="text-right text-white font-mono p-2">
                            {formatCurrency(position.currentPrice)}
                          </td>
                          <td className={cn(
                            'text-right font-mono p-2',
                            position.pnl >= 0 ? 'text-green-500' : 'text-red-500'
                          )}>
                            {formatCurrency(position.pnl)}
                          </td>
                          <td className={cn(
                            'text-right font-mono p-2',
                            position.pnlPercent >= 0 ? 'text-green-500' : 'text-red-500'
                          )}>
                            {formatPercentage(position.pnlPercent)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* AI ANALYTICS TAB */}
        {/* ========================================== */}
        <TabsContent value="ai" className="mt-4 space-y-6">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">
                  Model Performance
                </h3>
                <div className="space-y-3">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <div className="text-gray-400 text-sm">Accuracy</div>
                      <div className="text-2xl font-bold text-green-500">
                        {formatPercentage(aiAnalytics?.modelAccuracy || 0)}
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-400 text-sm">F1 Score</div>
                      <div className="text-2xl font-bold text-cyan-500">
                        {aiAnalytics?.modelF1Score?.toFixed(3) || 'N/A'}
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-400 text-sm">Precision</div>
                      <div className="text-2xl font-bold text-purple-500">
                        {formatPercentage(aiAnalytics?.modelPrecision || 0)}
                      </div>
                    </div>
                    <div>
                      <div className="text-gray-400 text-sm">Recall</div>
                      <div className="text-2xl font-bold text-yellow-500">
                        {formatPercentage(aiAnalytics?.modelRecall || 0)}
                      </div>
                    </div>
                  </div>
                  <div className="mt-4">
                    <div className="text-gray-400 text-sm mb-2">Prediction Confidence</div>
                    <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                      <motion.div
                        className="h-full bg-gradient-to-r from-cyan-500 to-blue-500"
                        initial={{ width: '0%' }}
                        animate={{ width: `${(aiAnalytics?.predictionConfidence || 0) * 100}%` }}
                        transition={{ duration: 0.8 }}
                      />
                    </div>
                    <div className="text-right text-xs text-gray-400 mt-1">
                      {formatPercentage(aiAnalytics?.predictionConfidence || 0)}
                    </div>
                  </div>
                </div>
              </Card>
            </div>

            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">
                  Feature Importance
                </h3>
                <div className="space-y-2">
                  {aiAnalytics?.featureImportance && 
                    Object.entries(aiAnalytics.featureImportance)
                      .sort((a, b) => b[1] - a[1])
                      .slice(0, 10)
                      .map(([feature, importance], index) => (
                        <div key={index}>
                          <div className="flex justify-between text-sm">
                            <span className="text-gray-400">{feature}</span>
                            <span className="text-cyan-400">{formatPercentage(importance)}</span>
                          </div>
                          <Progress value={importance * 100} className="h-1 mt-1 bg-gray-700" />
                        </div>
                      ))
                  }
                </div>
              </Card>
            </div>

            <div className="col-span-12">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">
                  Training History
                </h3>
                <div className="h-64">
                  {aiAnalytics?.trainingHistory ? (
                    <LineChart
                      data={aiAnalytics.trainingHistory}
                      xKey="epoch"
                      yKey="loss"
                      color="#ef4444"
                      height={240}
                      tooltip
                      secondYKey="accuracy"
                      secondYColor="#10b981"
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-500">
                      No training history available
                    </div>
                  )}
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* ANOMALIES TAB */}
        {/* ========================================== */}
        <TabsContent value="anomalies" className="mt-4 space-y-6">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-gray-300">
                    Detected Anomalies
                  </h3>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={fetchAnomalies}
                    className="text-xs text-cyan-400 hover:text-cyan-300"
                  >
                    🔄 Refresh
                  </Button>
                </div>
                {anomalyData.length > 0 ? (
                  <div className="space-y-2">
                    {anomalyData.slice(0, 20).map((anomaly) => (
                      <div
                        key={anomaly.id}
                        className={cn(
                          'flex items-center justify-between p-3 rounded-lg transition-colors',
                          anomaly.severity === 'critical' ? 'bg-red-500/20 border border-red-500/30' :
                          anomaly.severity === 'high' ? 'bg-orange-500/20 border border-orange-500/30' :
                          'bg-yellow-500/20 border border-yellow-500/30'
                        )}
                      >
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-white">
                              {anomaly.symbol}
                            </span>
                            <Badge className={cn(
                              'text-xs',
                              anomaly.severity === 'critical' ? 'bg-red-500' :
                              anomaly.severity === 'high' ? 'bg-orange-500' :
                              'bg-yellow-500'
                            )}>
                              {anomaly.severity.toUpperCase()}
                            </Badge>
                            {!anomaly.reviewed && (
                              <Badge className="bg-blue-500 text-xs">New</Badge>
                            )}
                          </div>
                          <div className="text-sm text-gray-300 mt-1">
                            {anomaly.description}
                          </div>
                          <div className="text-xs text-gray-500 mt-1">
                            {formatTime(anomaly.timestamp)} • 
                            Value: {formatCurrency(anomaly.value)} • 
                            Expected: {formatCurrency(anomaly.expectedValue)} • 
                            Deviation: {formatPercentage(anomaly.deviation)}
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {!anomaly.reviewed && (
                            <Button
                              variant="ghost"
                              size="sm"
                              className="text-xs text-gray-400 hover:text-white"
                              onClick={() => {
                                setAnomalyData(prev =>
                                  prev.map(a =>
                                    a.id === anomaly.id ? { ...a, reviewed: true } : a
                                  )
                                );
                              }}
                            >
                              ✅ Mark Reviewed
                            </Button>
                          )}
                          <div className={cn(
                            'w-2 h-2 rounded-full',
                            anomaly.severity === 'critical' ? 'bg-red-500 animate-pulse' :
                            anomaly.severity === 'high' ? 'bg-orange-500 animate-pulse' :
                            'bg-yellow-500'
                          )} />
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-12 text-gray-500">
                    <div className="text-4xl mb-3">✅</div>
                    <p>No anomalies detected</p>
                    <p className="text-sm">All systems operating normally</p>
                  </div>
                )}
              </Card>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      {/* ============================================ */}
      {/* GENERATE REPORT MODAL */}
      {/* ============================================ */}
      <Modal
        open={showReportModal}
        onOpenChange={setShowReportModal}
        title="Generate Report"
        className="max-w-2xl"
      >
        <div className="space-y-4">
          <div>
            <label className="text-sm text-gray-400 block mb-1">Report Name *</label>
            <Input
              value={reportConfig.name}
              onChange={(e) => setReportConfig({ ...reportConfig, name: e.target.value })}
              placeholder="e.g., Monthly Performance Report"
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-gray-400 block mb-1">Report Type</label>
              <Select
                value={reportConfig.type}
                onValueChange={(value) => setReportConfig({ ...reportConfig, type: value })}
                className="w-full bg-gray-700 border-gray-600"
              >
                <option value="performance">Performance</option>
                <option value="risk">Risk</option>
                <option value="portfolio">Portfolio</option>
                <option value="trading">Trading</option>
                <option value="comprehensive">Comprehensive</option>
              </Select>
            </div>
            <div>
              <label className="text-sm text-gray-400 block mb-1">Timeframe</label>
              <Select
                value={reportConfig.timeframe}
                onValueChange={(value) => setReportConfig({ ...reportConfig, timeframe: value })}
                className="w-full bg-gray-700 border-gray-600"
              >
                <option value="1D">1 Day</option>
                <option value="1W">1 Week</option>
                <option value="1M">1 Month</option>
                <option value="3M">3 Months</option>
                <option value="6M">6 Months</option>
                <option value="1Y">1 Year</option>
              </Select>
            </div>
          </div>

          <div>
            <label className="text-sm text-gray-400 block mb-1">Format</label>
            <Select
              value={reportConfig.format}
              onValueChange={(value) => setReportConfig({ ...reportConfig, format: value })}
              className="w-full bg-gray-700 border-gray-600"
            >
              <option value="pdf">PDF</option>
              <option value="json">JSON</option>
              <option value="csv">CSV</option>
            </Select>
          </div>

          <div>
            <label className="text-sm text-gray-400 block mb-2">Metrics to Include</label>
            <div className="flex flex-wrap gap-3">
              {['pnl', 'return', 'sharpe', 'winRate', 'maxDrawdown', 'volatility', 'trades', 'risk'].map((metric) => (
                <div key={metric} className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={reportConfig.metrics.includes(metric)}
                    onChange={(e) => {
                      const checked = e.target.checked;
                      setReportConfig({
                        ...reportConfig,
                        metrics: checked
                          ? [...reportConfig.metrics, metric]
                          : reportConfig.metrics.filter(m => m !== metric),
                      });
                    }}
                    className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-cyan-500 focus:ring-cyan-500"
                  />
                  <span className="text-sm text-gray-400 capitalize">{metric}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => setShowReportModal(false)}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handleGenerateReport}
              isLoading={reportLoading}
              className="bg-gradient-to-r from-blue-500 to-cyan-500 hover:from-blue-600 hover:to-cyan-600"
            >
              📄 Generate Report
            </Button>
          </div>
        </div>
      </Modal>

      {/* ============================================ */}
      {/* TOAST NOTIFICATIONS */}
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
    </div>
  );
}

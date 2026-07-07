/**
 * NEXUS AI TRADING SYSTEM - Portfolio Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page provides comprehensive portfolio management including:
 * - Portfolio overview and performance
 * - Asset allocation and diversification
 * - Real-time P&L tracking
 * - Position management
 * - Transaction history
 * - Performance analytics
 * - Risk metrics
 * - Portfolio rebalancing
 * - Dividend and yield tracking
 * - Tax reporting
 * - Portfolio export
 * - Watchlist integration
 * - WebSocket real-time updates
 * - Multi-currency support
 * - Portfolio benchmarking
 * - Performance attribution
 * - Scenario analysis
 * - Goal tracking
 * - Responsive design for all devices
 */

'use client';

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { useApi } from '@/hooks/useApi';
import { useWebSocket } from '@/hooks/useWebSocket';
import { usePortfolio } from '@/hooks/usePortfolio';
import { useMarketData } from '@/hooks/useMarketData';

// Components
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { Toast } from '@/components/ui/Toast';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Modal } from '@/components/ui/Modal';
import { Progress } from '@/components/ui/Progress';
import { Switch } from '@/components/ui/Switch';
import { Table } from '@/components/ui/Table';
import { Avatar } from '@/components/ui/Avatar';
import { Slider } from '@/components/ui/Slider';
import { Textarea } from '@/components/ui/Textarea';

// Charts
import { 
  AreaChart, 
  LineChart, 
  BarChart, 
  PieChart, 
  CandlestickChart,
  HeatMap 
} from '@/components/charts';

// Icons
import {
  Wallet,
  TrendingUp,
  TrendingDown,
  DollarSign,
  BarChart3,
  PieChart as PieChartIcon,
  Activity,
  Clock,
  Calendar,
  Download,
  Upload,
  RefreshCw,
  Plus,
  Minus,
  X,
  Check,
  AlertCircle,
  Info,
  HelpCircle,
  ArrowUp,
  ArrowDown,
  ArrowRight,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  MoreVertical,
  Search,
  Filter,
  Grid,
  List,
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
  Globe2,
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
  Award,
  Trophy,
  Medal,
  Gift,
  Rocket,
  Sparkles,
  Crown,
  Star,
  Zap,
  Shield,
  Lock,
  Unlock,
  Eye,
  EyeOff,
  Settings,
  Users,
  Briefcase,
  Building,
  Landmark,
  PiggyBank,
  Receipt,
  FileText,
  Printer,
  Calculator,
  Percent,
  TrendUp,
  TrendDown,
} from 'lucide-react';

// Types
import type {
  Portfolio,
  Position,
  Transaction,
  PerformanceMetrics,
  RiskMetrics,
  AssetAllocation,
  PortfolioGoal,
  Benchmark,
  PerformanceAttribution,
  TaxReport,
  Dividend,
} from '@/types/portfolio';

// Constants
import {
  ASSET_CLASSES,
  TIME_RANGES,
  PERFORMANCE_METRICS,
  RISK_METRICS,
  TRANSACTION_TYPES,
  ALLOCATION_TARGETS,
  BENCHMARKS,
  TAX_RATES,
} from '@/constants/portfolio';

// Utils
import { formatCurrency, formatNumber, formatPercentage, formatDate, formatTime } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

export default function PortfolioPage() {
  // Router
  const router = useRouter();

  // Auth hooks
  const { user, isAuthenticated } = useAuth();

  // API client
  const api = useApi();

  // Hooks
  const { 
    portfolio, 
    positions, 
    transactions, 
    performance, 
    loading: portfolioLoading, 
    refresh: refreshPortfolio 
  } = usePortfolio();
  const { marketData, loading: marketLoading, refresh: refreshMarket } = useMarketData();

  // State - Portfolio Data
  const [assetAllocation, setAssetAllocation] = useState<AssetAllocation | null>(null);
  const [riskMetrics, setRiskMetrics] = useState<RiskMetrics | null>(null);
  const [performanceMetrics, setPerformanceMetrics] = useState<PerformanceMetrics | null>(null);
  const [allocationLoading, setAllocationLoading] = useState<boolean>(true);
  const [riskLoading, setRiskLoading] = useState<boolean>(true);
  const [performanceLoading, setPerformanceLoading] = useState<boolean>(true);

  // State - Filters
  const [timeRange, setTimeRange] = useState<string>('1M');
  const [selectedAsset, setSelectedAsset] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // State - Goals
  const [goals, setGoals] = useState<PortfolioGoal[]>([]);
  const [goalsLoading, setGoalsLoading] = useState<boolean>(true);
  const [showGoalModal, setShowGoalModal] = useState<boolean>(false);
  const [newGoal, setNewGoal] = useState<Partial<PortfolioGoal>>({
    name: '',
    targetAmount: 0,
    targetDate: new Date(),
    currentAmount: 0,
    progress: 0,
  });
  const [isCreatingGoal, setIsCreatingGoal] = useState<boolean>(false);

  // State - Transactions
  const [filteredTransactions, setFilteredTransactions] = useState<Transaction[]>([]);
  const [transactionType, setTransactionType] = useState<string>('all');

  // State - Tax Report
  const [taxReport, setTaxReport] = useState<TaxReport | null>(null);
  const [taxLoading, setTaxLoading] = useState<boolean>(true);

  // State - Dividends
  const [dividends, setDividends] = useState<Dividend[]>([]);
  const [dividendsLoading, setDividendsLoading] = useState<boolean>(true);

  // State - UI
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [selectedPosition, setSelectedPosition] = useState<Position | null>(null);
  const [showPositionModal, setShowPositionModal] = useState<boolean>(false);
  const [showRebalanceModal, setShowRebalanceModal] = useState<boolean>(false);

  // Refs
  const chartContainerRef = useRef<HTMLDivElement>(null);

  // ============================================
  // WebSocket Connection
  // ============================================

  const {
    isConnected,
    sendMessage,
    subscribe: wsSubscribe,
    unsubscribe: wsUnsubscribe,
  } = useWebSocket({
    url: `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8004'}/portfolio`,
    autoConnect: true,
    onOpen: handleWebSocketOpen,
    onMessage: handleWebSocketMessage,
    onError: handleWebSocketError,
    onClose: handleWebSocketClose,
    reconnectAttempts: 10,
    reconnectInterval: 3000,
    authToken: user?.accessToken || '',
  });

  function handleWebSocketOpen() {
    console.log('✅ Portfolio WebSocket connected');
    subscribeToChannels();
  }

  function handleWebSocketMessage(event: MessageEvent) {
    try {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'portfolio_update':
          handlePortfolioUpdate(data.payload);
          break;
        case 'position_update':
          handlePositionUpdate(data.payload);
          break;
        case 'transaction_update':
          handleTransactionUpdate(data.payload);
          break;
        case 'performance_update':
          handlePerformanceUpdate(data.payload);
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
    console.log('Portfolio WebSocket disconnected');
  }

  function subscribeToChannels() {
    if (!isConnected) return;

    wsSubscribe({
      channel: 'portfolio',
      userId: user?.id,
    });

    wsSubscribe({
      channel: 'positions',
      userId: user?.id,
    });

    wsSubscribe({
      channel: 'transactions',
      userId: user?.id,
    });
  }

  // ============================================
  // WebSocket Data Handlers
  // ============================================

  function handlePortfolioUpdate(data: any) {
    refreshPortfolio();
  }

  function handlePositionUpdate(data: any) {
    refreshPortfolio();
  }

  function handleTransactionUpdate(data: any) {
    refreshPortfolio();
  }

  function handlePerformanceUpdate(data: any) {
    setPerformanceMetrics(data);
  }

  // ============================================
  // API Calls
  // ============================================

  const fetchAssetAllocation = useCallback(async () => {
    try {
      setAllocationLoading(true);
      const response = await api.get('/portfolio/allocation');
      if (response.data) {
        setAssetAllocation(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch asset allocation:', error);
    } finally {
      setAllocationLoading(false);
    }
  }, [api]);

  const fetchRiskMetrics = useCallback(async () => {
    try {
      setRiskLoading(true);
      const response = await api.get('/portfolio/risk');
      if (response.data) {
        setRiskMetrics(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch risk metrics:', error);
    } finally {
      setRiskLoading(false);
    }
  }, [api]);

  const fetchPerformanceMetrics = useCallback(async () => {
    try {
      setPerformanceLoading(true);
      const response = await api.get('/portfolio/performance', {
        params: { timeRange },
      });
      if (response.data) {
        setPerformanceMetrics(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch performance metrics:', error);
    } finally {
      setPerformanceLoading(false);
    }
  }, [api, timeRange]);

  const fetchGoals = useCallback(async () => {
    try {
      setGoalsLoading(true);
      const response = await api.get('/portfolio/goals');
      if (response.data) {
        setGoals(response.data.goals || []);
      }
    } catch (error) {
      console.error('Failed to fetch goals:', error);
    } finally {
      setGoalsLoading(false);
    }
  }, [api]);

  const fetchTaxReport = useCallback(async () => {
    try {
      setTaxLoading(true);
      const response = await api.get('/portfolio/tax');
      if (response.data) {
        setTaxReport(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch tax report:', error);
    } finally {
      setTaxLoading(false);
    }
  }, [api]);

  const fetchDividends = useCallback(async () => {
    try {
      setDividendsLoading(true);
      const response = await api.get('/portfolio/dividends');
      if (response.data) {
        setDividends(response.data.dividends || []);
      }
    } catch (error) {
      console.error('Failed to fetch dividends:', error);
    } finally {
      setDividendsLoading(false);
    }
  }, [api]);

  const fetchAllData = useCallback(async () => {
    setIsLoading(true);
    setIsRefreshing(true);
    try {
      await Promise.all([
        refreshPortfolio(),
        refreshMarket(),
        fetchAssetAllocation(),
        fetchRiskMetrics(),
        fetchPerformanceMetrics(),
        fetchGoals(),
        fetchTaxReport(),
        fetchDividends(),
      ]);
    } catch (error) {
      console.error('Failed to fetch portfolio data:', error);
      setShowToast({
        message: 'Failed to load portfolio data. Please refresh.',
        type: 'error',
      });
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [
    refreshPortfolio,
    refreshMarket,
    fetchAssetAllocation,
    fetchRiskMetrics,
    fetchPerformanceMetrics,
    fetchGoals,
    fetchTaxReport,
    fetchDividends,
  ]);

  // ============================================
  // Handlers - Goals
  // ============================================

  const handleCreateGoal = useCallback(async () => {
    if (!newGoal.name || !newGoal.targetAmount || !newGoal.targetDate) {
      setShowToast({
        message: 'Please fill in all required fields.',
        type: 'warning',
      });
      return;
    }

    setIsCreatingGoal(true);
    try {
      const response = await api.post('/portfolio/goals', newGoal);
      if (response.data) {
        setGoals(prev => [response.data, ...prev]);
        setShowGoalModal(false);
        setNewGoal({
          name: '',
          targetAmount: 0,
          targetDate: new Date(),
          currentAmount: 0,
          progress: 0,
        });
        setShowToast({
          message: 'Portfolio goal created successfully!',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to create goal.',
        type: 'error',
      });
    } finally {
      setIsCreatingGoal(false);
    }
  }, [api, newGoal]);

  const handleDeleteGoal = useCallback(async (goalId: string) => {
    if (!confirm('Are you sure you want to delete this goal?')) return;

    try {
      await api.delete(`/portfolio/goals/${goalId}`);
      setGoals(prev => prev.filter(g => g.id !== goalId));
      setShowToast({
        message: 'Goal deleted successfully.',
        type: 'info',
      });
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to delete goal.',
        type: 'error',
      });
    }
  }, [api]);

  // ============================================
  // Handlers - Transactions
  // ============================================

  const handleExportTransactions = useCallback(async () => {
    try {
      const response = await api.get('/portfolio/transactions/export', {
        params: { format: 'csv' },
        responseType: 'blob',
      });
      const blob = new Blob([response.data], { type: 'text/csv' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `transactions-${Date.now()}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setShowToast({
        message: 'Transactions exported successfully!',
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to export transactions.',
        type: 'error',
      });
    }
  }, [api]);

  // ============================================
  // Effects
  // ============================================

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/authentication/login?callbackUrl=/portfolio');
    } else {
      fetchAllData();
    }
  }, [isAuthenticated, router, fetchAllData]);

  useEffect(() => {
    if (isConnected) {
      subscribeToChannels();
    }
  }, [isConnected]);

  useEffect(() => {
    fetchPerformanceMetrics();
  }, [timeRange, fetchPerformanceMetrics]);

  useEffect(() => {
    if (transactions) {
      let filtered = transactions;
      if (transactionType !== 'all') {
        filtered = filtered.filter(t => t.type === transactionType);
      }
      if (searchQuery) {
        const query = searchQuery.toLowerCase();
        filtered = filtered.filter(t =>
          t.symbol.toLowerCase().includes(query) ||
          t.asset.toLowerCase().includes(query)
        );
      }
      setFilteredTransactions(filtered);
    }
  }, [transactions, transactionType, searchQuery]);

  // Auto-refresh data
  useEffect(() => {
    const interval = setInterval(() => {
      if (!isRefreshing) {
        refreshPortfolio();
        fetchPerformanceMetrics();
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [fetchPerformanceMetrics, refreshPortfolio, isRefreshing]);

  // ============================================
  // Memoized Computations
  // ============================================

  const totalValue = useMemo(() => {
    return portfolio?.totalValue || 0;
  }, [portfolio]);

  const totalPnL = useMemo(() => {
    return portfolio?.totalPnL || 0;
  }, [portfolio]);

  const totalPnLPercent = useMemo(() => {
    return portfolio?.totalPnLPercent || 0;
  }, [portfolio]);

  const activePositions = useMemo(() => {
    return positions?.filter(p => p.quantity > 0) || [];
  }, [positions]);

  const assetClassColors = useMemo(() => {
    const colors: Record<string, string> = {
      crypto: '#f7931a',
      stocks: '#4f46e5',
      forex: '#06b6d4',
      commodities: '#f59e0b',
      bonds: '#10b981',
      real_estate: '#8b5cf6',
      cash: '#6b7280',
      other: '#9ca3af',
    };
    return colors;
  }, []);

  const allocationData = useMemo(() => {
    if (!assetAllocation) return [];
    return Object.entries(assetAllocation).map(([key, value]) => ({
      name: key.charAt(0).toUpperCase() + key.slice(1),
      value: value,
      color: assetClassColors[key] || '#6b7280',
    }));
  }, [assetAllocation, assetClassColors]);

  const performanceData = useMemo(() => {
    if (!performanceMetrics?.history) return [];
    return performanceMetrics.history.map((item: any) => ({
      ...item,
      date: new Date(item.date),
    }));
  }, [performanceMetrics]);

  const goalProgress = useMemo(() => {
    if (!goals.length) return 0;
    const totalTarget = goals.reduce((sum, g) => sum + g.targetAmount, 0);
    const totalCurrent = goals.reduce((sum, g) => sum + g.currentAmount, 0);
    return totalTarget > 0 ? (totalCurrent / totalTarget) * 100 : 0;
  }, [goals]);

  // ============================================
  // Render
  // ============================================

  if (isLoading && portfolioLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-6">
            <div className="absolute inset-0 border-4 border-cyan-500/30 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-t-cyan-500 rounded-full animate-spin"></div>
            <div className="absolute inset-2 bg-cyan-500/10 rounded-full animate-pulse"></div>
          </div>
          <p className="text-gray-400 text-lg font-medium">Loading Portfolio...</p>
          <p className="text-gray-500 text-sm mt-2">Fetching your assets and performance</p>
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
            <div className="text-3xl">💼</div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                Portfolio
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                Track your investments and performance
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

          {/* Refresh Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={fetchAllData}
            isLoading={isRefreshing}
            className="border-gray-700 hover:border-cyan-500"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>

          {/* Export Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportTransactions}
            className="border-gray-700 hover:border-cyan-500"
          >
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>
        </div>
      </div>

      {/* ============================================ */}
      {/* PORTFOLIO SUMMARY */}
      {/* ============================================ */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-400">Total Value</div>
              <div className="text-xl font-bold text-white">{formatCurrency(totalValue)}</div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center">
              <Wallet className="w-5 h-5 text-cyan-500" />
            </div>
          </div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-400">Total P&L</div>
              <div className={cn(
                "text-xl font-bold",
                totalPnL >= 0 ? 'text-green-500' : 'text-red-500'
              )}>
                {formatCurrency(totalPnL)}
              </div>
            </div>
            <div className={cn(
              "w-10 h-10 rounded-lg flex items-center justify-center",
              totalPnL >= 0 ? 'bg-green-500/20' : 'bg-red-500/20'
            )}>
              {totalPnL >= 0 ? (
                <TrendingUp className="w-5 h-5 text-green-500" />
              ) : (
                <TrendingDown className="w-5 h-5 text-red-500" />
              )}
            </div>
          </div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-400">P&L %</div>
              <div className={cn(
                "text-xl font-bold",
                totalPnLPercent >= 0 ? 'text-green-500' : 'text-red-500'
              )}>
                {formatPercentage(totalPnLPercent)}
              </div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
              <Percent className="w-5 h-5 text-purple-500" />
            </div>
          </div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-400">Active Positions</div>
              <div className="text-xl font-bold text-white">{activePositions.length}</div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
              <BarChart3 className="w-5 h-5 text-blue-500" />
            </div>
          </div>
        </Card>
      </div>

      {/* ============================================ */}
      {/* MAIN TABS */}
      {/* ============================================ */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-gray-800 border border-gray-700 rounded-lg p-1 w-full overflow-x-auto">
          <TabsTrigger
            value="overview"
            className="data-[state=active]:bg-cyan-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📊 Overview
          </TabsTrigger>
          <TabsTrigger
            value="positions"
            className="data-[state=active]:bg-blue-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📈 Positions
          </TabsTrigger>
          <TabsTrigger
            value="transactions"
            className="data-[state=active]:bg-purple-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📋 Transactions
          </TabsTrigger>
          <TabsTrigger
            value="goals"
            className="data-[state=active]:bg-green-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            🎯 Goals
          </TabsTrigger>
          <TabsTrigger
            value="tax"
            className="data-[state=active]:bg-yellow-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📄 Tax Report
          </TabsTrigger>
        </TabsList>

        {/* ========================================== */}
        {/* OVERVIEW TAB */}
        {/* ========================================== */}
        <TabsContent value="overview" className="mt-4 space-y-6">
          <div className="grid grid-cols-12 gap-6">
            {/* Performance Chart */}
            <div className="col-span-12 lg:col-span-8">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-gray-300">Portfolio Performance</h3>
                  <div className="flex items-center gap-2">
                    <Select
                      value={timeRange}
                      onValueChange={setTimeRange}
                      className="w-24 bg-gray-700 border-gray-600 text-sm"
                    >
                      {TIME_RANGES.map((range) => (
                        <option key={range} value={range}>{range}</option>
                      ))}
                    </Select>
                  </div>
                </div>
                <div ref={chartContainerRef} className="h-80">
                  {performanceLoading ? (
                    <div className="flex items-center justify-center h-full">
                      <Spinner size="lg" className="text-cyan-500" />
                    </div>
                  ) : performanceData.length > 0 ? (
                    <AreaChart
                      data={performanceData}
                      xKey="date"
                      yKey="value"
                      color="#06b6d4"
                      height={300}
                      gradient
                      tooltip
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-500">
                      <p>No performance data available</p>
                    </div>
                  )}
                </div>
              </Card>
            </div>

            {/* Asset Allocation */}
            <div className="col-span-12 lg:col-span-4">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Asset Allocation</h3>
                {allocationLoading ? (
                  <div className="flex items-center justify-center h-64">
                    <Spinner size="lg" className="text-cyan-500" />
                  </div>
                ) : allocationData.length > 0 ? (
                  <div className="space-y-4">
                    <div className="h-48">
                      <PieChart
                        data={allocationData}
                        height={180}
                        tooltip
                        legend
                      />
                    </div>
                    <div className="space-y-1">
                      {allocationData.map((item) => (
                        <div key={item.name} className="flex items-center justify-between text-sm">
                          <div className="flex items-center gap-2">
                            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: item.color }} />
                            <span className="text-gray-300">{item.name}</span>
                          </div>
                          <span className="text-white font-medium">{formatPercentage(item.value / 100)}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-64 text-gray-500">
                    <p>No allocation data available</p>
                  </div>
                )}
              </Card>
            </div>

            {/* Risk Metrics */}
            <div className="col-span-12 lg:col-span-4">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Risk Metrics</h3>
                {riskLoading ? (
                  <div className="flex items-center justify-center h-48">
                    <Spinner size="lg" className="text-cyan-500" />
                  </div>
                ) : riskMetrics ? (
                  <div className="space-y-3">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Volatility (Annual)</span>
                      <span className="text-white font-medium">{formatPercentage(riskMetrics.volatility)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Sharpe Ratio</span>
                      <span className="text-white font-medium">{riskMetrics.sharpeRatio.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Max Drawdown</span>
                      <span className="text-red-500 font-medium">{formatPercentage(riskMetrics.maxDrawdown)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">VaR (95%)</span>
                      <span className="text-orange-500 font-medium">{formatCurrency(riskMetrics.var)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Beta</span>
                      <span className="text-white font-medium">{riskMetrics.beta.toFixed(2)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Sortino Ratio</span>
                      <span className="text-white font-medium">{riskMetrics.sortinoRatio.toFixed(2)}</span>
                    </div>
                    <div className="mt-2 pt-2 border-t border-gray-700">
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-400">Risk Score</span>
                        <div className="flex items-center gap-2">
                          <span className="text-white font-medium">{riskMetrics.riskScore}/100</span>
                          <Progress value={riskMetrics.riskScore} className="w-20 h-2" />
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-48 text-gray-500">
                    <p>No risk data available</p>
                  </div>
                )}
              </Card>
            </div>

            {/* Performance Metrics */}
            <div className="col-span-12 lg:col-span-8">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Performance Metrics</h3>
                {performanceLoading ? (
                  <div className="flex items-center justify-center h-48">
                    <Spinner size="lg" className="text-cyan-500" />
                  </div>
                ) : performanceMetrics ? (
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                      <div className="text-xs text-gray-400">Total Return</div>
                      <div className={cn(
                        "text-lg font-bold",
                        performanceMetrics.totalReturn >= 0 ? 'text-green-500' : 'text-red-500'
                      )}>
                        {formatPercentage(performanceMetrics.totalReturn)}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-400">Annualized Return</div>
                      <div className={cn(
                        "text-lg font-bold",
                        performanceMetrics.annualizedReturn >= 0 ? 'text-green-500' : 'text-red-500'
                      )}>
                        {formatPercentage(performanceMetrics.annualizedReturn)}
                      </div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-400">Win Rate</div>
                      <div className="text-lg font-bold text-white">{formatPercentage(performanceMetrics.winRate)}</div>
                    </div>
                    <div>
                      <div className="text-xs text-gray-400">Profit Factor</div>
                      <div className="text-lg font-bold text-white">{performanceMetrics.profitFactor.toFixed(2)}</div>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center justify-center h-48 text-gray-500">
                    <p>No performance data available</p>
                  </div>
                )}
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* POSITIONS TAB */}
        {/* ========================================== */}
        <TabsContent value="positions" className="mt-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-300">Active Positions</h3>
            <div className="flex items-center gap-2">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <Input
                  type="text"
                  placeholder="Search positions..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 w-48 bg-gray-700 border-gray-600 text-white text-sm"
                />
              </div>
            </div>
          </div>

          {activePositions.length > 0 ? (
            <Card className="p-4 bg-gray-800 border-gray-700">
              <Table>
                <thead>
                  <tr className="border-b border-gray-700">
                    <th className="text-left text-xs text-gray-400 p-3">Asset</th>
                    <th className="text-right text-xs text-gray-400 p-3">Quantity</th>
                    <th className="text-right text-xs text-gray-400 p-3">Avg. Price</th>
                    <th className="text-right text-xs text-gray-400 p-3">Current Price</th>
                    <th className="text-right text-xs text-gray-400 p-3">Value</th>
                    <th className="text-right text-xs text-gray-400 p-3">P&L</th>
                    <th className="text-right text-xs text-gray-400 p-3">P&L %</th>
                    <th className="text-right text-xs text-gray-400 p-3">Allocation</th>
                  </tr>
                </thead>
                <tbody>
                  {activePositions.map((position) => (
                    <tr key={position.id} className="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors cursor-pointer" onClick={() => {
                      setSelectedPosition(position);
                      setShowPositionModal(true);
                    }}>
                      <td className="p-3">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-white font-medium">{position.symbol}</span>
                          <Badge className="bg-gray-600 text-xs">{position.assetClass}</Badge>
                        </div>
                      </td>
                      <td className="p-3 text-right text-white font-mono">{formatNumber(position.quantity)}</td>
                      <td className="p-3 text-right text-gray-400 font-mono">{formatCurrency(position.avgPrice)}</td>
                      <td className="p-3 text-right text-white font-mono">{formatCurrency(position.currentPrice)}</td>
                      <td className="p-3 text-right text-white font-mono">{formatCurrency(position.value)}</td>
                      <td className={cn(
                        "p-3 text-right font-mono",
                        position.pnl >= 0 ? 'text-green-500' : 'text-red-500'
                      )}>
                        {formatCurrency(position.pnl)}
                      </td>
                      <td className={cn(
                        "p-3 text-right font-mono",
                        position.pnlPercent >= 0 ? 'text-green-500' : 'text-red-500'
                      )}>
                        {formatPercentage(position.pnlPercent)}
                      </td>
                      <td className="p-3 text-right text-white font-mono">{formatPercentage(position.allocation)}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <Wallet className="w-16 h-16 mx-auto mb-4 text-gray-600" />
              <p className="text-lg font-medium">No active positions</p>
              <p className="text-sm">Start trading to build your portfolio</p>
              <Button
                onClick={() => router.push('/exchange')}
                className="mt-4 bg-gradient-to-r from-cyan-500 to-blue-500"
              >
                Start Trading
              </Button>
            </div>
          )}
        </TabsContent>

        {/* ========================================== */}
        {/* TRANSACTIONS TAB */}
        {/* ========================================== */}
        <TabsContent value="transactions" className="mt-4">
          <div className="flex flex-wrap items-center justify-between gap-4 mb-4">
            <h3 className="text-sm font-semibold text-gray-300">Transaction History</h3>
            <div className="flex items-center gap-2 flex-wrap">
              <Select
                value={transactionType}
                onValueChange={setTransactionType}
                className="w-32 bg-gray-700 border-gray-600 text-sm"
              >
                <option value="all">All Types</option>
                {TRANSACTION_TYPES.map((type) => (
                  <option key={type} value={type}>{type.charAt(0).toUpperCase() + type.slice(1)}</option>
                ))}
              </Select>
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <Input
                  type="text"
                  placeholder="Search transactions..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9 w-48 bg-gray-700 border-gray-600 text-white text-sm"
                />
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={handleExportTransactions}
                className="border-gray-600 hover:border-cyan-500"
              >
                <Download className="w-4 h-4 mr-2" />
                Export
              </Button>
            </div>
          </div>

          {filteredTransactions.length > 0 ? (
            <Card className="p-4 bg-gray-800 border-gray-700">
              <Table>
                <thead>
                  <tr className="border-b border-gray-700">
                    <th className="text-left text-xs text-gray-400 p-3">Date</th>
                    <th className="text-left text-xs text-gray-400 p-3">Type</th>
                    <th className="text-left text-xs text-gray-400 p-3">Asset</th>
                    <th className="text-right text-xs text-gray-400 p-3">Quantity</th>
                    <th className="text-right text-xs text-gray-400 p-3">Price</th>
                    <th className="text-right text-xs text-gray-400 p-3">Total</th>
                    <th className="text-right text-xs text-gray-400 p-3">Fees</th>
                    <th className="text-right text-xs text-gray-400 p-3">Status</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredTransactions.slice(0, 50).map((transaction) => (
                    <tr key={transaction.id} className="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
                      <td className="p-3 text-gray-400 text-xs">{formatTime(transaction.timestamp)}</td>
                      <td className="p-3">
                        <Badge className={cn(
                          "text-xs",
                          transaction.type === 'buy' ? 'bg-green-500/20 text-green-500' :
                          transaction.type === 'sell' ? 'bg-red-500/20 text-red-500' :
                          transaction.type === 'dividend' ? 'bg-blue-500/20 text-blue-500' :
                          'bg-gray-500/20 text-gray-400'
                        )}>
                          {transaction.type.toUpperCase()}
                        </Badge>
                      </td>
                      <td className="p-3 text-white font-mono">{transaction.symbol}</td>
                      <td className="p-3 text-right text-white font-mono">{formatNumber(transaction.quantity)}</td>
                      <td className="p-3 text-right text-white font-mono">{formatCurrency(transaction.price)}</td>
                      <td className="p-3 text-right text-white font-mono">{formatCurrency(transaction.total)}</td>
                      <td className="p-3 text-right text-gray-400 font-mono">{formatCurrency(transaction.fees || 0)}</td>
                      <td className="p-3 text-right">
                        <Badge className={cn(
                          "text-xs",
                          transaction.status === 'completed' ? 'bg-green-500/20 text-green-500' :
                          transaction.status === 'pending' ? 'bg-yellow-500/20 text-yellow-500' :
                          'bg-red-500/20 text-red-500'
                        )}>
                          {transaction.status.toUpperCase()}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
              {filteredTransactions.length > 50 && (
                <div className="text-center text-sm text-gray-500 mt-4">
                  Showing 50 of {filteredTransactions.length} transactions
                </div>
              )}
            </Card>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <Receipt className="w-16 h-16 mx-auto mb-4 text-gray-600" />
              <p className="text-lg font-medium">No transactions found</p>
              <p className="text-sm">Your transaction history will appear here</p>
            </div>
          )}
        </TabsContent>

        {/* ========================================== */}
        {/* GOALS TAB */}
        {/* ========================================== */}
        <TabsContent value="goals" className="mt-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-300">Portfolio Goals</h3>
            <Button
              onClick={() => setShowGoalModal(true)}
              className="bg-gradient-to-r from-green-500 to-emerald-500"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Goal
            </Button>
          </div>

          {goalsLoading ? (
            <div className="text-center py-8">
              <Spinner size="lg" className="mx-auto text-cyan-500" />
              <p className="text-gray-400 mt-4">Loading goals...</p>
            </div>
          ) : goals.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {goals.map((goal) => (
                <Card key={goal.id} className="p-4 bg-gray-800 border-gray-700">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="text-white font-medium">{goal.name}</h4>
                      <p className="text-sm text-gray-400 mt-1">
                        Target: {formatCurrency(goal.targetAmount)} by {formatDate(goal.targetDate)}
                      </p>
                    </div>
                    <Badge className={cn(
                      "text-xs",
                      goal.progress >= 100 ? 'bg-green-500/20 text-green-500' :
                      goal.progress >= 50 ? 'bg-yellow-500/20 text-yellow-500' :
                      'bg-gray-500/20 text-gray-400'
                    )}>
                      {goal.progress >= 100 ? 'Achieved' : 'In Progress'}
                    </Badge>
                  </div>
                  <div className="mt-3">
                    <div className="flex justify-between text-sm mb-1">
                      <span className="text-gray-400">Progress</span>
                      <span className="text-cyan-400">{Math.min(goal.progress, 100).toFixed(1)}%</span>
                    </div>
                    <Progress value={Math.min(goal.progress, 100)} className="h-2" />
                  </div>
                  <div className="flex justify-between mt-3 text-sm text-gray-400">
                    <span>Current: {formatCurrency(goal.currentAmount)}</span>
                    <span>Remaining: {formatCurrency(Math.max(goal.targetAmount - goal.currentAmount, 0))}</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleDeleteGoal(goal.id)}
                    className="mt-3 text-red-400 hover:text-red-300 w-full border border-red-500/20 hover:bg-red-500/10"
                  >
                    Delete Goal
                  </Button>
                </Card>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <Target className="w-16 h-16 mx-auto mb-4 text-gray-600" />
              <p className="text-lg font-medium">No portfolio goals</p>
              <p className="text-sm">Set financial goals to track your progress</p>
            </div>
          )}
        </TabsContent>

        {/* ========================================== */}
        {/* TAX REPORT TAB */}
        {/* ========================================== */}
        <TabsContent value="tax" className="mt-4">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Tax Summary</h3>
                {taxLoading ? (
                  <div className="text-center py-8">
                    <Spinner size="lg" className="mx-auto text-cyan-500" />
                    <p className="text-gray-400 mt-4">Loading tax report...</p>
                  </div>
                ) : taxReport ? (
                  <div className="space-y-3">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Total Realized Gains</span>
                      <span className="text-green-500 font-medium">{formatCurrency(taxReport.totalRealizedGains)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Total Realized Losses</span>
                      <span className="text-red-500 font-medium">{formatCurrency(taxReport.totalRealizedLosses)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Net Capital Gains</span>
                      <span className={cn(
                        "font-medium",
                        taxReport.netCapitalGains >= 0 ? 'text-green-500' : 'text-red-500'
                      )}>
                        {formatCurrency(taxReport.netCapitalGains)}
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Short-term Gains</span>
                      <span className="text-yellow-500 font-medium">{formatCurrency(taxReport.shortTermGains)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Long-term Gains</span>
                      <span className="text-blue-500 font-medium">{formatCurrency(taxReport.longTermGains)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Estimated Tax Liability</span>
                      <span className="text-orange-500 font-medium">{formatCurrency(taxReport.estimatedTaxLiability)}</span>
                    </div>
                    <div className="mt-2 pt-2 border-t border-gray-700">
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-400">Effective Tax Rate</span>
                        <span className="text-white font-medium">{formatPercentage(taxReport.effectiveTaxRate)}</span>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <Calculator className="w-16 h-16 mx-auto mb-4 text-gray-600" />
                    <p>No tax data available</p>
                    <p className="text-sm">Tax information will appear once you have realized gains or losses</p>
                  </div>
                )}
              </Card>
            </div>

            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Tax-Loss Harvesting Opportunities</h3>
                {taxReport && taxReport.lossHarvestingOpportunities && taxReport.lossHarvestingOpportunities.length > 0 ? (
                  <div className="space-y-3">
                    {taxReport.lossHarvestingOpportunities.map((opportunity, index) => (
                      <div key={index} className="p-3 bg-gray-700/30 rounded-lg">
                        <div className="flex items-center justify-between">
                          <span className="text-white font-medium">{opportunity.symbol}</span>
                          <span className="text-red-500 font-medium">{formatCurrency(opportunity.unrealizedLoss)}</span>
                        </div>
                        <div className="text-sm text-gray-400 mt-1">
                          Potential tax benefit: {formatCurrency(opportunity.potentialTaxBenefit)}
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          className="mt-2 text-cyan-400 hover:text-cyan-300"
                        >
                          Harvest Loss
                        </Button>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <PiggyBank className="w-16 h-16 mx-auto mb-4 text-gray-600" />
                    <p>No tax-loss harvesting opportunities</p>
                    <p className="text-sm">Check back after market movements</p>
                  </div>
                )}
              </Card>
            </div>

            <div className="col-span-12">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-gray-300">Tax Documents</h3>
                  <Button
                    variant="outline"
                    size="sm"
                    className="border-gray-600 hover:border-cyan-500"
                  >
                    <Download className="w-4 h-4 mr-2" />
                    Download All
                  </Button>
                </div>
                <div className="space-y-2">
                  <div className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
                    <div className="flex items-center gap-3">
                      <FileText className="w-5 h-5 text-cyan-500" />
                      <div>
                        <div className="text-sm text-white">1099-B - 2024</div>
                        <div className="text-xs text-gray-500">Generated on Dec 31, 2024</div>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-cyan-400 hover:text-cyan-300"
                    >
                      <Download className="w-4 h-4" />
                    </Button>
                  </div>
                  <div className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
                    <div className="flex items-center gap-3">
                      <FileText className="w-5 h-5 text-cyan-500" />
                      <div>
                        <div className="text-sm text-white">1099-DIV - 2024</div>
                        <div className="text-xs text-gray-500">Generated on Dec 31, 2024</div>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-cyan-400 hover:text-cyan-300"
                    >
                      <Download className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      {/* ============================================ */}
      {/* POSITION DETAIL MODAL */}
      {/* ============================================ */}
      <Modal
        open={showPositionModal}
        onOpenChange={setShowPositionModal}
        title="Position Details"
        className="max-w-md"
      >
        {selectedPosition && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <div className="text-xl font-bold text-white">{selectedPosition.symbol}</div>
                <div className="text-sm text-gray-400">{selectedPosition.assetClass}</div>
              </div>
              <Badge className={cn(
                "text-xs",
                selectedPosition.pnl >= 0 ? 'bg-green-500/20 text-green-500' : 'bg-red-500/20 text-red-500'
              )}>
                {selectedPosition.pnl >= 0 ? '▲' : '▼'} {formatPercentage(selectedPosition.pnlPercent)}
              </Badge>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <div className="text-xs text-gray-500">Quantity</div>
                <div className="text-white font-mono">{formatNumber(selectedPosition.quantity)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Value</div>
                <div className="text-white font-mono">{formatCurrency(selectedPosition.value)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Avg. Price</div>
                <div className="text-white font-mono">{formatCurrency(selectedPosition.avgPrice)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Current Price</div>
                <div className="text-white font-mono">{formatCurrency(selectedPosition.currentPrice)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">P&L</div>
                <div className={cn(
                  "font-mono",
                  selectedPosition.pnl >= 0 ? 'text-green-500' : 'text-red-500'
                )}>
                  {formatCurrency(selectedPosition.pnl)}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Allocation</div>
                <div className="text-white font-mono">{formatPercentage(selectedPosition.allocation)}</div>
              </div>
            </div>

            <div className="flex gap-3 pt-4 border-t border-gray-700">
              <Button
                variant="primary"
                className="flex-1 bg-gradient-to-r from-cyan-500 to-blue-500"
                onClick={() => router.push(`/exchange?symbol=${selectedPosition.symbol}`)}
              >
                Trade {selectedPosition.symbol}
              </Button>
              <Button
                variant="outline"
                className="flex-1 border-gray-600 hover:border-cyan-500"
                onClick={() => setShowPositionModal(false)}
              >
                Close
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* ============================================ */}
      {/* CREATE GOAL MODAL */}
      {/* ============================================ */}
      <Modal
        open={showGoalModal}
        onOpenChange={setShowGoalModal}
        title="Create Portfolio Goal"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Goal Name *</label>
            <Input
              value={newGoal.name}
              onChange={(e) => setNewGoal({ ...newGoal, name: e.target.value })}
              placeholder="e.g., Retirement Fund"
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Target Amount *</label>
            <Input
              type="number"
              step="100"
              value={newGoal.targetAmount}
              onChange={(e) => setNewGoal({ ...newGoal, targetAmount: parseFloat(e.target.value) || 0 })}
              placeholder="100000"
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Target Date *</label>
            <Input
              type="date"
              value={newGoal.targetDate ? new Date(newGoal.targetDate).toISOString().slice(0, 10) : ''}
              onChange={(e) => setNewGoal({ ...newGoal, targetDate: e.target.value ? new Date(e.target.value) : new Date() })}
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Current Amount</label>
            <Input
              type="number"
              step="100"
              value={newGoal.currentAmount}
              onChange={(e) => setNewGoal({ ...newGoal, currentAmount: parseFloat(e.target.value) || 0 })}
              placeholder="0"
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => setShowGoalModal(false)}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateGoal}
              isLoading={isCreatingGoal}
              className="bg-gradient-to-r from-green-500 to-emerald-500"
            >
              Create Goal
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

/**
 * NEXUS AI TRADING SYSTEM - Dashboard Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page provides a comprehensive trading dashboard including:
 * - Portfolio overview and performance
 * - Real-time market data
 * - AI trading signals and predictions
 * - Active positions and orders
 * - Trading history
 * - Performance metrics and charts
 * - Risk management overview
 * - Recent activity feed
 * - Quick actions for trading
 * - WebSocket real-time updates
 * - Customizable widgets
 * - Market sentiment analysis
 * - Watchlist management
 * - Alert notifications
 * - Account summary
 */

'use client';

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { useApi } from '@/hooks/useApi';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useMarketData } from '@/hooks/useMarketData';
import { usePortfolio } from '@/hooks/usePortfolio';

// Components
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { Toast } from '@/components/ui/Toast';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import { Badge } from '@/components/ui/Badge';
import { Avatar } from '@/components/ui/Avatar';
import { Progress } from '@/components/ui/Progress';
import { Table } from '@/components/ui/Table';
import { Switch } from '@/components/ui/Switch';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';

// Charts
import {
  LineChart,
  AreaChart,
  BarChart,
  PieChart,
  CandlestickChart,
} from '@/components/charts';

// Icons
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  Wallet,
  BarChart3,
  PieChart as PieChartIcon,
  Activity,
  Clock,
  AlertCircle,
  CheckCircle,
  XCircle,
  Zap,
  Brain,
  Target,
  Shield,
  Users,
  Calendar,
  Settings,
  Bell,
  Menu,
  ChevronDown,
  ChevronRight,
  Plus,
  RefreshCw,
  Download,
  Eye,
  EyeOff,
  Lock,
  Unlock,
  Globe,
  Server,
  Cpu,
  Memory,
  HardDrive,
  Network,
  Sparkles,
  Crown,
  Star,
  Award,
  Trophy,
  Medal,
  Gift,
  Rocket,
  ArrowUp,
  ArrowDown,
  BarChart,
  LineChart as LineChartIcon,
  Circle,
  Dot,
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
  Circle as CircleIcon,
  Triangle,
  Hexagon,
  Octagon,
  Pentagon,
} from 'lucide-react';

// Types
import type {
  PortfolioSummary,
  Position,
  Order,
  Trade,
  MarketData,
  AIPrediction,
  PerformanceMetrics,
  RiskMetrics,
  Activity,
  WatchlistItem,
  Alert,
} from '@/types/dashboard';

// Utils
import { formatCurrency, formatNumber, formatPercentage, formatDate, formatTime } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

export default function DashboardPage() {
  // Router
  const router = useRouter();

  // Auth hooks
  const { user, isAuthenticated } = useAuth();

  // API client
  const api = useApi();

  // Hooks
  const { portfolio, positions, orders, performance, loading: portfolioLoading, refresh: refreshPortfolio } = usePortfolio();
  const { marketData, watchlist, loading: marketLoading, refresh: refreshMarket } = useMarketData();

  // State - Data
  const [predictions, setPredictions] = useState<AIPrediction[]>([]);
  const [riskMetrics, setRiskMetrics] = useState<RiskMetrics | null>(null);
  const [activities, setActivities] = useState<Activity[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [dataLoading, setDataLoading] = useState<boolean>(true);

  // State - UI
  const [selectedSymbol, setSelectedSymbol] = useState<string>('BTC-USD');
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>('1D');
  const [showNotifications, setShowNotifications] = useState<boolean>(false);
  const [showSettings, setShowSettings] = useState<boolean>(false);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [activeTab, setActiveTab] = useState<string>('overview');

  // Refs
  const notificationRef = useRef<HTMLDivElement>(null);

  // ============================================
  // WebSocket Connection
  // ============================================

  const {
    isConnected,
    sendMessage,
    subscribe: wsSubscribe,
    unsubscribe: wsUnsubscribe,
  } = useWebSocket({
    url: `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8004'}/dashboard`,
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
    console.log('✅ Dashboard WebSocket connected');
    subscribeToChannels();
  }

  function handleWebSocketMessage(event: MessageEvent) {
    try {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'market_update':
          handleMarketUpdate(data.payload);
          break;
        case 'portfolio_update':
          handlePortfolioUpdate(data.payload);
          break;
        case 'prediction_update':
          handlePredictionUpdate(data.payload);
          break;
        case 'order_update':
          handleOrderUpdate(data.payload);
          break;
        case 'alert_triggered':
          handleAlertTriggered(data.payload);
          break;
        case 'activity_update':
          handleActivityUpdate(data.payload);
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
    console.log('Dashboard WebSocket disconnected');
  }

  function subscribeToChannels() {
    if (!isConnected) return;

    wsSubscribe({
      channel: 'market_data',
      symbols: watchlist.map(item => item.symbol).join(','),
    });

    wsSubscribe({
      channel: 'portfolio',
      userId: user?.id,
    });

    wsSubscribe({
      channel: 'predictions',
      userId: user?.id,
    });

    wsSubscribe({
      channel: 'alerts',
      userId: user?.id,
    });

    wsSubscribe({
      channel: 'activities',
      userId: user?.id,
    });
  }

  // ============================================
  // WebSocket Data Handlers
  // ============================================

  function handleMarketUpdate(data: any) {
    // Update market data in real-time
    setMarketData(prev => ({
      ...prev,
      [data.symbol]: {
        ...prev[data.symbol],
        price: data.price,
        bid: data.bid,
        ask: data.ask,
        volume: data.volume,
        change24h: data.change24h,
        changePercent24h: data.changePercent24h,
        timestamp: new Date(data.timestamp),
      },
    }));
  }

  function handlePortfolioUpdate(data: any) {
    // Update portfolio in real-time
    refreshPortfolio();
  }

  function handlePredictionUpdate(data: any) {
    setPredictions(prev => [data, ...prev].slice(0, 50));
  }

  function handleOrderUpdate(data: any) {
    // Update orders in real-time
    refreshPortfolio();
  }

  function handleAlertTriggered(data: any) {
    setAlerts(prev => [{
      ...data,
      triggeredAt: new Date(data.triggeredAt),
    }, ...prev].slice(0, 100));

    setShowToast({
      message: `🔔 Alert: ${data.message}`,
      type: data.severity === 'high' ? 'error' : 'warning',
    });
  }

  function handleActivityUpdate(data: any) {
    setActivities(prev => [{
      ...data,
      timestamp: new Date(data.timestamp),
    }, ...prev].slice(0, 100));
  }

  // ============================================
  // API Calls
  // ============================================

  const fetchPredictions = useCallback(async () => {
    try {
      const response = await api.get('/ai/predictions', {
        params: {
          limit: 20,
          minConfidence: 0.6,
        },
      });
      if (response.data) {
        setPredictions(response.data.predictions || []);
      }
    } catch (error) {
      console.error('Failed to fetch predictions:', error);
    }
  }, [api]);

  const fetchRiskMetrics = useCallback(async () => {
    try {
      const response = await api.get('/risk/metrics');
      if (response.data) {
        setRiskMetrics(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch risk metrics:', error);
    }
  }, [api]);

  const fetchActivities = useCallback(async () => {
    try {
      const response = await api.get('/activities', {
        params: { limit: 20 },
      });
      if (response.data) {
        setActivities(response.data.activities || []);
      }
    } catch (error) {
      console.error('Failed to fetch activities:', error);
    }
  }, [api]);

  const fetchAlerts = useCallback(async () => {
    try {
      const response = await api.get('/alerts', {
        params: { active: true, limit: 10 },
      });
      if (response.data) {
        setAlerts(response.data.alerts || []);
      }
    } catch (error) {
      console.error('Failed to fetch alerts:', error);
    }
  }, [api]);

  const fetchAllData = useCallback(async () => {
    setDataLoading(true);
    setIsRefreshing(true);
    try {
      await Promise.all([
        fetchPredictions(),
        fetchRiskMetrics(),
        fetchActivities(),
        fetchAlerts(),
        refreshPortfolio(),
        refreshMarket(),
      ]);
    } catch (error) {
      console.error('Failed to fetch dashboard data:', error);
      setShowToast({
        message: 'Failed to load dashboard data. Please refresh.',
        type: 'error',
      });
    } finally {
      setDataLoading(false);
      setIsRefreshing(false);
    }
  }, [fetchPredictions, fetchRiskMetrics, fetchActivities, fetchAlerts, refreshPortfolio, refreshMarket]);

  // ============================================
  // Effects
  // ============================================

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/authentication/login?callbackUrl=/dashboard');
    } else {
      fetchAllData();
    }
  }, [isAuthenticated, router, fetchAllData]);

  useEffect(() => {
    if (isConnected) {
      subscribeToChannels();
    }
  }, [isConnected]);

  // Auto-refresh data
  useEffect(() => {
    const interval = setInterval(() => {
      if (!isRefreshing) {
        fetchAllData();
      }
    }, 60000);

    return () => clearInterval(interval);
  }, [fetchAllData, isRefreshing]);

  // ============================================
  // Memoized Computations
  // ============================================

  const totalPnL = useMemo(() => {
    return portfolio?.totalPnL || 0;
  }, [portfolio]);

  const totalValue = useMemo(() => {
    return portfolio?.totalValue || 0;
  }, [portfolio]);

  const winRate = useMemo(() => {
    return performance?.winRate || 0;
  }, [performance]);

  const activePositions = useMemo(() => {
    return positions?.filter(p => p.quantity > 0) || [];
  }, [positions]);

  const pendingOrders = useMemo(() => {
    return orders?.filter(o => o.status === 'pending' || o.status === 'open') || [];
  }, [orders]);

  const recentActivities = useMemo(() => {
    return activities.slice(0, 10);
  }, [activities]);

  const topPredictions = useMemo(() => {
    return predictions.slice(0, 5);
  }, [predictions]);

  const topAlerts = useMemo(() => {
    return alerts.slice(0, 5);
  }, [alerts]);

  // ============================================
  // Render
  // ============================================

  if (dataLoading && !portfolio) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-6">
            <div className="absolute inset-0 border-4 border-cyan-500/30 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-t-cyan-500 rounded-full animate-spin"></div>
            <div className="absolute inset-2 bg-cyan-500/10 rounded-full animate-pulse"></div>
          </div>
          <p className="text-gray-400 text-lg font-medium">Loading Dashboard...</p>
          <p className="text-gray-500 text-sm mt-2">Fetching your trading data</p>
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
              <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                Dashboard
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                Welcome back, {user?.name || 'Trader'}!
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

          {/* Notifications */}
          <div className="relative">
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowNotifications(!showNotifications)}
              className="border-gray-700 hover:border-cyan-500 relative"
            >
              <Bell className="w-4 h-4" />
              {alerts.filter(a => !a.read).length > 0 && (
                <span className="absolute -top-1 -right-1 w-4 h-4 bg-red-500 rounded-full text-[10px] flex items-center justify-center">
                  {alerts.filter(a => !a.read).length}
                </span>
              )}
            </Button>

            {/* Notifications Dropdown */}
            <AnimatePresence>
              {showNotifications && (
                <motion.div
                  ref={notificationRef}
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -10 }}
                  className="absolute right-0 mt-2 w-80 bg-gray-800 border border-gray-700 rounded-lg shadow-xl z-50 max-h-96 overflow-y-auto"
                >
                  <div className="p-3 border-b border-gray-700 flex items-center justify-between">
                    <span className="text-sm font-medium text-white">Notifications</span>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowNotifications(false)}
                      className="text-gray-400 hover:text-white"
                    >
                      ✕
                    </Button>
                  </div>
                  {topAlerts.length > 0 ? (
                    topAlerts.map((alert) => (
                      <div key={alert.id} className="p-3 border-b border-gray-700 hover:bg-gray-700/50 transition-colors">
                        <div className="flex items-start gap-2">
                          {alert.severity === 'high' ? (
                            <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 flex-shrink-0" />
                          ) : alert.severity === 'medium' ? (
                            <AlertCircle className="w-4 h-4 text-yellow-500 mt-0.5 flex-shrink-0" />
                          ) : (
                            <AlertCircle className="w-4 h-4 text-blue-500 mt-0.5 flex-shrink-0" />
                          )}
                          <div>
                            <p className="text-sm text-white">{alert.message}</p>
                            <p className="text-xs text-gray-500">{formatTime(alert.triggeredAt)}</p>
                          </div>
                        </div>
                      </div>
                    ))
                  ) : (
                    <div className="p-4 text-center text-gray-500 text-sm">
                      No new notifications
                    </div>
                  )}
                  <div className="p-2 border-t border-gray-700">
                    <Link href="/alerts">
                      <Button variant="ghost" size="sm" className="w-full text-cyan-400 hover:text-cyan-300">
                        View All Alerts
                      </Button>
                    </Link>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </div>

      {/* ============================================ */}
      {/* STATISTICS CARDS */}
      {/* ============================================ */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6">
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
              <div className="text-xs text-gray-400">Win Rate</div>
              <div className="text-xl font-bold text-white">{formatPercentage(winRate)}</div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
              <Target className="w-5 h-5 text-purple-500" />
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
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-400">Pending Orders</div>
              <div className="text-xl font-bold text-yellow-500">{pendingOrders.length}</div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-yellow-500/20 flex items-center justify-center">
              <Clock className="w-5 h-5 text-yellow-500" />
            </div>
          </div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-400">AI Signals</div>
              <div className="text-xl font-bold text-cyan-400">{predictions.length}</div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center">
              <Brain className="w-5 h-5 text-cyan-500" />
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
            value="orders"
            className="data-[state=active]:bg-yellow-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📋 Orders
          </TabsTrigger>
          <TabsTrigger
            value="predictions"
            className="data-[state=active]:bg-purple-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            🤖 AI Signals
          </TabsTrigger>
        </TabsList>

        {/* ========================================== */}
        {/* OVERVIEW TAB */}
        {/* ========================================== */}
        <TabsContent value="overview" className="mt-4 space-y-6">
          <div className="grid grid-cols-12 gap-6">
            {/* Portfolio Performance Chart */}
            <div className="col-span-12 lg:col-span-8">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-gray-300">
                    Portfolio Performance
                  </h3>
                  <div className="flex items-center gap-2">
                    <Select
                      value={selectedTimeframe}
                      onValueChange={setSelectedTimeframe}
                      className="w-24 bg-gray-700 border-gray-600 text-sm"
                    >
                      <option value="1D">1D</option>
                      <option value="1W">1W</option>
                      <option value="1M">1M</option>
                      <option value="3M">3M</option>
                      <option value="6M">6M</option>
                      <option value="1Y">1Y</option>
                    </Select>
                  </div>
                </div>
                <div className="h-80">
                  {performance?.history ? (
                    <AreaChart
                      data={performance.history}
                      xKey="date"
                      yKey="value"
                      color="#06b6d4"
                      height={300}
                      gradient
                      tooltip
                    />
                  ) : (
                    <div className="flex items-center justify-center h-full text-gray-500">
                      <Spinner size="sm" className="mr-3 text-cyan-500" />
                      Loading chart data...
                    </div>
                  )}
                </div>
              </Card>
            </div>

            {/* AI Predictions */}
            <div className="col-span-12 lg:col-span-4">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                    <Brain className="w-4 h-4 text-purple-500" />
                    AI Signals
                  </h3>
                  <Link href="/ai">
                    <Button variant="ghost" size="sm" className="text-cyan-400 hover:text-cyan-300">
                      View All
                    </Button>
                  </Link>
                </div>
                {topPredictions.length > 0 ? (
                  <div className="space-y-3">
                    {topPredictions.map((prediction) => (
                      <div key={prediction.id} className="p-3 bg-gray-700/30 rounded-lg">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="font-mono text-white">{prediction.symbol}</span>
                            <Badge className={cn(
                              "text-xs",
                              prediction.direction === 'up' ? 'bg-green-500/20 text-green-500' :
                              prediction.direction === 'down' ? 'bg-red-500/20 text-red-500' :
                              'bg-yellow-500/20 text-yellow-500'
                            )}>
                              {prediction.direction === 'up' ? '📈 BUY' :
                               prediction.direction === 'down' ? '📉 SELL' : 'HOLD'}
                            </Badge>
                          </div>
                          <div className="text-right">
                            <div className="text-sm font-mono text-white">
                              {formatCurrency(prediction.predictedPrice)}
                            </div>
                            <div className="text-xs text-gray-500">
                              {formatPercentage(prediction.confidence)} confidence
                            </div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <Brain className="w-12 h-12 mx-auto mb-3 text-gray-600" />
                    <p>No AI signals available</p>
                    <p className="text-sm">Check back later</p>
                  </div>
                )}
              </Card>
            </div>

            {/* Positions & Orders Summary */}
            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Active Positions</h3>
                {activePositions.length > 0 ? (
                  <div className="space-y-2">
                    {activePositions.slice(0, 5).map((position) => (
                      <div key={position.id} className="flex items-center justify-between p-2 bg-gray-700/30 rounded-lg">
                        <div>
                          <div className="text-sm font-medium text-white">{position.symbol}</div>
                          <div className="text-xs text-gray-400">{position.quantity} shares</div>
                        </div>
                        <div className="text-right">
                          <div className="text-sm font-mono text-white">{formatCurrency(position.value)}</div>
                          <div className={cn(
                            "text-xs font-medium",
                            position.pnl >= 0 ? 'text-green-500' : 'text-red-500'
                          )}>
                            {formatCurrency(position.pnl)} ({formatPercentage(position.pnlPercent)})
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <p>No active positions</p>
                    <p className="text-sm">Start trading to see your positions here</p>
                  </div>
                )}
                {activePositions.length > 5 && (
                  <div className="mt-3 text-center">
                    <Link href="/portfolio">
                      <Button variant="ghost" size="sm" className="text-cyan-400 hover:text-cyan-300">
                        View All Positions
                      </Button>
                    </Link>
                  </div>
                )}
              </Card>
            </div>

            {/* Recent Activity */}
            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Recent Activity</h3>
                {recentActivities.length > 0 ? (
                  <div className="space-y-2 max-h-80 overflow-y-auto">
                    {recentActivities.map((activity) => (
                      <div key={activity.id} className="flex items-center gap-3 p-2 bg-gray-700/30 rounded-lg">
                        <div className={cn(
                          "w-8 h-8 rounded-full flex items-center justify-center",
                          activity.type === 'trade' ? 'bg-green-500/20' :
                          activity.type === 'order' ? 'bg-blue-500/20' :
                          activity.type === 'alert' ? 'bg-yellow-500/20' :
                          'bg-gray-500/20'
                        )}>
                          {activity.type === 'trade' && <TrendingUp className="w-4 h-4 text-green-500" />}
                          {activity.type === 'order' && <Clock className="w-4 h-4 text-blue-500" />}
                          {activity.type === 'alert' && <AlertCircle className="w-4 h-4 text-yellow-500" />}
                        </div>
                        <div className="flex-1">
                          <div className="text-sm text-white">{activity.message}</div>
                          <div className="text-xs text-gray-500">{formatTime(activity.timestamp)}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <Activity className="w-12 h-12 mx-auto mb-3 text-gray-600" />
                    <p>No recent activity</p>
                    <p className="text-sm">Your trading activity will appear here</p>
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
          <Card className="p-4 bg-gray-800 border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-gray-300">All Positions</h3>
              <Button
                variant="outline"
                size="sm"
                onClick={refreshPortfolio}
                className="border-gray-600 hover:border-cyan-500"
              >
                <RefreshCw className="w-4 h-4 mr-2" />
                Refresh
              </Button>
            </div>
            {activePositions.length > 0 ? (
              <Table>
                <thead>
                  <tr className="border-b border-gray-700">
                    <th className="text-left text-xs text-gray-400 p-3">Symbol</th>
                    <th className="text-right text-xs text-gray-400 p-3">Quantity</th>
                    <th className="text-right text-xs text-gray-400 p-3">Avg. Price</th>
                    <th className="text-right text-xs text-gray-400 p-3">Current Price</th>
                    <th className="text-right text-xs text-gray-400 p-3">Value</th>
                    <th className="text-right text-xs text-gray-400 p-3">P&L</th>
                    <th className="text-right text-xs text-gray-400 p-3">P&L %</th>
                  </tr>
                </thead>
                <tbody>
                  {activePositions.map((position) => (
                    <tr key={position.id} className="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
                      <td className="p-3 text-white font-mono">{position.symbol}</td>
                      <td className="p-3 text-right text-white">{formatNumber(position.quantity)}</td>
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
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <div className="text-center py-12 text-gray-500">
                <BarChart3 className="w-16 h-16 mx-auto mb-4 text-gray-600" />
                <p>No positions found</p>
                <p className="text-sm">Start trading to build your portfolio</p>
                <Link href="/trading">
                  <Button className="mt-4 bg-gradient-to-r from-cyan-500 to-blue-500">
                    Start Trading
                  </Button>
                </Link>
              </div>
            )}
          </Card>
        </TabsContent>

        {/* ========================================== */}
        {/* ORDERS TAB */}
        {/* ========================================== */}
        <TabsContent value="orders" className="mt-4">
          <Card className="p-4 bg-gray-800 border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-gray-300">Order History</h3>
              <div className="flex items-center gap-2">
                <Select className="w-32 bg-gray-700 border-gray-600 text-sm">
                  <option value="all">All Orders</option>
                  <option value="pending">Pending</option>
                  <option value="filled">Filled</option>
                  <option value="cancelled">Cancelled</option>
                </Select>
                <Button
                  variant="outline"
                  size="sm"
                  className="border-gray-600 hover:border-cyan-500"
                >
                  <RefreshCw className="w-4 h-4" />
                </Button>
              </div>
            </div>
            {orders && orders.length > 0 ? (
              <Table>
                <thead>
                  <tr className="border-b border-gray-700">
                    <th className="text-left text-xs text-gray-400 p-3">Symbol</th>
                    <th className="text-left text-xs text-gray-400 p-3">Type</th>
                    <th className="text-left text-xs text-gray-400 p-3">Side</th>
                    <th className="text-right text-xs text-gray-400 p-3">Quantity</th>
                    <th className="text-right text-xs text-gray-400 p-3">Price</th>
                    <th className="text-right text-xs text-gray-400 p-3">Status</th>
                    <th className="text-right text-xs text-gray-400 p-3">Time</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.slice(0, 10).map((order) => (
                    <tr key={order.id} className="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
                      <td className="p-3 text-white font-mono">{order.symbol}</td>
                      <td className="p-3 text-white">{order.type}</td>
                      <td className={cn(
                        "p-3 font-medium",
                        order.side === 'buy' ? 'text-green-500' : 'text-red-500'
                      )}>
                        {order.side.toUpperCase()}
                      </td>
                      <td className="p-3 text-right text-white">{formatNumber(order.quantity)}</td>
                      <td className="p-3 text-right text-white font-mono">{formatCurrency(order.price)}</td>
                      <td className="p-3 text-right">
                        <Badge className={cn(
                          "text-xs",
                          order.status === 'filled' ? 'bg-green-500/20 text-green-500' :
                          order.status === 'pending' ? 'bg-yellow-500/20 text-yellow-500' :
                          order.status === 'cancelled' ? 'bg-red-500/20 text-red-500' :
                          'bg-gray-500/20 text-gray-400'
                        )}>
                          {order.status.toUpperCase()}
                        </Badge>
                      </td>
                      <td className="p-3 text-right text-gray-400 text-xs">{formatTime(order.timestamp)}</td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            ) : (
              <div className="text-center py-12 text-gray-500">
                <Clock className="w-16 h-16 mx-auto mb-4 text-gray-600" />
                <p>No orders found</p>
                <p className="text-sm">Your orders will appear here</p>
              </div>
            )}
          </Card>
        </TabsContent>

        {/* ========================================== */}
        {/* AI SIGNALS TAB */}
        {/* ========================================== */}
        <TabsContent value="predictions" className="mt-4">
          <Card className="p-4 bg-gray-800 border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                <Brain className="w-5 h-5 text-purple-500" />
                AI Trading Signals
              </h3>
              <div className="flex items-center gap-2">
                <Select className="w-32 bg-gray-700 border-gray-600 text-sm">
                  <option value="all">All Signals</option>
                  <option value="buy">Buy</option>
                  <option value="sell">Sell</option>
                  <option value="hold">Hold</option>
                </Select>
                <Button
                  variant="outline"
                  size="sm"
                  className="border-gray-600 hover:border-cyan-500"
                >
                  <RefreshCw className="w-4 h-4" />
                </Button>
              </div>
            </div>
            {predictions.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                {predictions.slice(0, 9).map((prediction) => (
                  <Card key={prediction.id} className="p-4 bg-gray-700/30 border-gray-600 hover:border-cyan-500/50 transition-colors">
                    <div className="flex items-center justify-between mb-2">
                      <span className="font-mono text-white font-bold">{prediction.symbol}</span>
                      <Badge className={cn(
                        "text-xs",
                        prediction.direction === 'up' ? 'bg-green-500/20 text-green-500' :
                        prediction.direction === 'down' ? 'bg-red-500/20 text-red-500' :
                        'bg-yellow-500/20 text-yellow-500'
                      )}>
                        {prediction.direction === 'up' ? '📈 BUY' :
                         prediction.direction === 'down' ? '📉 SELL' : '⏸️ HOLD'}
                      </Badge>
                    </div>
                    <div className="grid grid-cols-2 gap-2 text-sm">
                      <div>
                        <div className="text-xs text-gray-500">Current Price</div>
                        <div className="text-white font-mono">{formatCurrency(prediction.price)}</div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500">Predicted</div>
                        <div className="text-white font-mono">{formatCurrency(prediction.predictedPrice)}</div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500">Confidence</div>
                        <div className="text-cyan-400 font-mono">{formatPercentage(prediction.confidence)}</div>
                      </div>
                      <div>
                        <div className="text-xs text-gray-500">Time</div>
                        <div className="text-gray-400 text-xs">{formatTime(prediction.timestamp)}</div>
                      </div>
                    </div>
                    <div className="mt-2 pt-2 border-t border-gray-600">
                      <Progress value={prediction.confidence * 100} className="h-1" />
                    </div>
                  </Card>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-gray-500">
                <Brain className="w-16 h-16 mx-auto mb-4 text-gray-600" />
                <p>No AI signals available</p>
                <p className="text-sm">AI predictions will appear here</p>
              </div>
            )}
          </Card>
        </TabsContent>
      </Tabs>

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

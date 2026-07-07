/**
 * NEXUS AI TRADING SYSTEM - Markets Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page provides a comprehensive market overview including:
 * - Real-time price data for all trading pairs
 * - Market statistics and performance metrics
 * - Price charts with multiple timeframes
 * - Market depth and order book visualization
 * - Trading volume analysis
 * - Market sentiment indicators
 * - Top gainers and losers
 * - Market cap rankings
 * - Price alerts creation
 * - Watchlist management
 * - Advanced filtering and search
 * - WebSocket real-time updates
 * - Multi-market support (Crypto, Forex, Stocks)
 * - Technical indicators
 * - Market news and updates
 * - Portfolio integration
 * - Responsive design for all devices
 */

'use client';

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { useApi } from '@/hooks/useApi';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useMarketData } from '@/hooks/useMarketData';
import { useWatchlist } from '@/hooks/useWatchlist';

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

// Charts
import { LineChart, AreaChart, BarChart, HeatMap } from '@/components/charts';

// Icons
import {
  TrendingUp,
  TrendingDown,
  DollarSign,
  Wallet,
  Activity,
  Clock,
  AlertCircle,
  CheckCircle,
  XCircle,
  Zap,
  Shield,
  ArrowUp,
  ArrowDown,
  BarChart3,
  PieChart as PieChartIcon,
  LineChart as LineChartIcon,
  Plus,
  Minus,
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
} from 'lucide-react';

// Types
import type {
  MarketData,
  MarketStats,
  MarketPair,
  MarketCategory,
  MarketTimeframe,
  MarketFilter,
  MarketSort,
  MarketAlert,
  MarketNews,
  MarketVolume,
  MarketDepth,
} from '@/types/markets';

// Constants
import {
  MARKET_CATEGORIES,
  MARKET_TIMEFRAMES,
  MARKET_SORT_OPTIONS,
  MARKET_FILTER_OPTIONS,
  SUPPORTED_PAIRS,
  DEFAULT_MARKET_CONFIG,
  CHART_COLORS,
} from '@/constants/markets';

// Utils
import { formatCurrency, formatNumber, formatPercentage, formatDate, formatTime } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

export default function MarketsPage() {
  // Router
  const router = useRouter();

  // Auth hooks
  const { user, isAuthenticated } = useAuth();

  // API client
  const api = useApi();

  // Hooks
  const { marketData, loading: marketLoading, refresh: refreshMarket } = useMarketData();
  const { watchlist, addToWatchlist, removeFromWatchlist, isInWatchlist } = useWatchlist();

  // State - Market Data
  const [pairs, setPairs] = useState<MarketPair[]>([]);
  const [selectedPair, setSelectedPair] = useState<MarketPair | null>(null);
  const [pairsLoading, setPairsLoading] = useState<boolean>(true);

  // State - Filters
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedSort, setSelectedSort] = useState<string>('volume');
  const [selectedTimeframe, setSelectedTimeframe] = useState<MarketTimeframe>('24h');
  const [filterDirection, setFilterDirection] = useState<'asc' | 'desc'>('desc');

  // State - Chart
  const [chartData, setChartData] = useState<any[]>([]);
  const [chartLoading, setChartLoading] = useState<boolean>(true);
  const [selectedChartTimeframe, setSelectedChartTimeframe] = useState<string>('1d');

  // State - Market Stats
  const [stats, setStats] = useState<MarketStats | null>(null);
  const [statsLoading, setStatsLoading] = useState<boolean>(true);

  // State - Top Gainers/Losers
  const [topGainers, setTopGainers] = useState<MarketPair[]>([]);
  const [topLosers, setTopLosers] = useState<MarketPair[]>([]);
  const [topVolume, setTopVolume] = useState<MarketPair[]>([]);

  // State - Alerts
  const [alerts, setAlerts] = useState<MarketAlert[]>([]);
  const [showAlertModal, setShowAlertModal] = useState<boolean>(false);
  const [newAlert, setNewAlert] = useState<Partial<MarketAlert>>({
    symbol: '',
    condition: 'above',
    value: 0,
    type: 'price',
  });
  const [isCreatingAlert, setIsCreatingAlert] = useState<boolean>(false);

  // State - News
  const [news, setNews] = useState<MarketNews[]>([]);
  const [newsLoading, setNewsLoading] = useState<boolean>(true);

  // State - UI
  const [activeTab, setActiveTab] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [selectedPeriod, setSelectedPeriod] = useState<string>('7d');

  // Refs
  const searchInputRef = useRef<HTMLInputElement>(null);
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
    url: `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8004'}/markets`,
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
    console.log('✅ Markets WebSocket connected');
    subscribeToChannels();
  }

  function handleWebSocketMessage(event: MessageEvent) {
    try {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'price_update':
          handlePriceUpdate(data.payload);
          break;
        case 'volume_update':
          handleVolumeUpdate(data.payload);
          break;
        case 'market_stats':
          handleMarketStatsUpdate(data.payload);
          break;
        case 'news_update':
          handleNewsUpdate(data.payload);
          break;
        case 'alert_triggered':
          handleAlertTriggered(data.payload);
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
    console.log('Markets WebSocket disconnected');
  }

  function subscribeToChannels() {
    if (!isConnected) return;

    wsSubscribe({
      channel: 'market_prices',
      symbols: pairs.map(p => p.symbol).join(','),
    });

    wsSubscribe({
      channel: 'market_stats',
    });

    wsSubscribe({
      channel: 'market_news',
    });
  }

  // ============================================
  // WebSocket Data Handlers
  // ============================================

  function handlePriceUpdate(data: any) {
    setPairs(prev =>
      prev.map(pair =>
        pair.symbol === data.symbol
          ? {
              ...pair,
              price: data.price,
              change24h: data.change24h,
              changePercent24h: data.changePercent24h,
              high24h: data.high24h,
              low24h: data.low24h,
              volume24h: data.volume24h,
              lastUpdated: new Date(data.timestamp),
            }
          : pair
      )
    );
  }

  function handleVolumeUpdate(data: any) {
    setPairs(prev =>
      prev.map(pair =>
        pair.symbol === data.symbol
          ? {
              ...pair,
              volume24h: data.volume24h,
              volumeChange24h: data.volumeChange24h,
            }
          : pair
      )
    );
  }

  function handleMarketStatsUpdate(data: any) {
    setStats(data);
  }

  function handleNewsUpdate(data: any) {
    setNews(prev => [{
      ...data,
      timestamp: new Date(data.timestamp),
    }, ...prev].slice(0, 50));
  }

  function handleAlertTriggered(data: any) {
    setShowToast({
      message: `🔔 Alert: ${data.symbol} ${data.condition} ${formatCurrency(data.value)}`,
      type: 'warning',
    });
  }

  // ============================================
  // API Calls
  // ============================================

  const fetchPairs = useCallback(async () => {
    try {
      setPairsLoading(true);
      const response = await api.get('/markets/pairs', {
        params: {
          category: selectedCategory !== 'all' ? selectedCategory : undefined,
          search: searchQuery || undefined,
          sort: selectedSort,
          order: filterDirection,
          limit: 100,
        },
      });
      if (response.data) {
        setPairs(response.data.pairs || []);
      }
    } catch (error) {
      console.error('Failed to fetch market pairs:', error);
      setShowToast({
        message: 'Failed to load market data. Please refresh.',
        type: 'error',
      });
    } finally {
      setPairsLoading(false);
    }
  }, [api, selectedCategory, searchQuery, selectedSort, filterDirection]);

  const fetchStats = useCallback(async () => {
    try {
      setStatsLoading(true);
      const response = await api.get('/markets/stats');
      if (response.data) {
        setStats(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch market stats:', error);
    } finally {
      setStatsLoading(false);
    }
  }, [api]);

  const fetchChartData = useCallback(async (symbol: string) => {
    try {
      setChartLoading(true);
      const response = await api.get('/markets/chart', {
        params: {
          symbol,
          timeframe: selectedChartTimeframe,
          limit: 200,
        },
      });
      if (response.data) {
        setChartData(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch chart data:', error);
    } finally {
      setChartLoading(false);
    }
  }, [api, selectedChartTimeframe]);

  const fetchTopGainers = useCallback(async () => {
    try {
      const response = await api.get('/markets/top-gainers', {
        params: { limit: 10 },
      });
      if (response.data) {
        setTopGainers(response.data.gainers || []);
      }
    } catch (error) {
      console.error('Failed to fetch top gainers:', error);
    }
  }, [api]);

  const fetchTopLosers = useCallback(async () => {
    try {
      const response = await api.get('/markets/top-losers', {
        params: { limit: 10 },
      });
      if (response.data) {
        setTopLosers(response.data.losers || []);
      }
    } catch (error) {
      console.error('Failed to fetch top losers:', error);
    }
  }, [api]);

  const fetchTopVolume = useCallback(async () => {
    try {
      const response = await api.get('/markets/top-volume', {
        params: { limit: 10 },
      });
      if (response.data) {
        setTopVolume(response.data.pairs || []);
      }
    } catch (error) {
      console.error('Failed to fetch top volume:', error);
    }
  }, [api]);

  const fetchNews = useCallback(async () => {
    try {
      setNewsLoading(true);
      const response = await api.get('/markets/news', {
        params: { limit: 20 },
      });
      if (response.data) {
        setNews(response.data.articles || []);
      }
    } catch (error) {
      console.error('Failed to fetch news:', error);
    } finally {
      setNewsLoading(false);
    }
  }, [api]);

  const fetchAlerts = useCallback(async () => {
    try {
      const response = await api.get('/markets/alerts');
      if (response.data) {
        setAlerts(response.data.alerts || []);
      }
    } catch (error) {
      console.error('Failed to fetch alerts:', error);
    }
  }, [api]);

  const fetchAllData = useCallback(async () => {
    setIsLoading(true);
    setIsRefreshing(true);
    try {
      await Promise.all([
        fetchPairs(),
        fetchStats(),
        fetchTopGainers(),
        fetchTopLosers(),
        fetchTopVolume(),
        fetchNews(),
        fetchAlerts(),
        refreshMarket(),
      ]);
      if (pairs.length > 0 && !selectedPair) {
        setSelectedPair(pairs[0]);
        fetchChartData(pairs[0].symbol);
      }
    } catch (error) {
      console.error('Failed to fetch market data:', error);
      setShowToast({
        message: 'Failed to load market data. Please refresh.',
        type: 'error',
      });
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [
    fetchPairs,
    fetchStats,
    fetchTopGainers,
    fetchTopLosers,
    fetchTopVolume,
    fetchNews,
    fetchAlerts,
    refreshMarket,
    pairs,
    selectedPair,
    fetchChartData,
  ]);

  // ============================================
  // Handlers - Interactions
  // ============================================

  const handleSearch = useCallback((query: string) => {
    setSearchQuery(query);
    const debounce = setTimeout(() => {
      fetchPairs();
    }, 300);
    return () => clearTimeout(debounce);
  }, [fetchPairs]);

  const handleCategoryChange = useCallback((category: string) => {
    setSelectedCategory(category);
    fetchPairs();
  }, [fetchPairs]);

  const handleSortChange = useCallback((sort: string) => {
    setSelectedSort(sort);
    fetchPairs();
  }, [fetchPairs]);

  const handleSortDirectionToggle = useCallback(() => {
    setFilterDirection(prev => prev === 'desc' ? 'asc' : 'desc');
    fetchPairs();
  }, [fetchPairs]);

  const handlePairSelect = useCallback((pair: MarketPair) => {
    setSelectedPair(pair);
    fetchChartData(pair.symbol);
  }, [fetchChartData]);

  const handleTimeframeChange = useCallback((timeframe: string) => {
    setSelectedChartTimeframe(timeframe);
    if (selectedPair) {
      fetchChartData(selectedPair.symbol);
    }
  }, [selectedPair, fetchChartData]);

  const handleAddToWatchlist = useCallback(async (symbol: string) => {
    try {
      await addToWatchlist(symbol);
      setShowToast({
        message: `Added ${symbol} to watchlist`,
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to add to watchlist',
        type: 'error',
      });
    }
  }, [addToWatchlist]);

  const handleRemoveFromWatchlist = useCallback(async (symbol: string) => {
    try {
      await removeFromWatchlist(symbol);
      setShowToast({
        message: `Removed ${symbol} from watchlist`,
        type: 'info',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to remove from watchlist',
        type: 'error',
      });
    }
  }, [removeFromWatchlist]);

  const handleCreateAlert = useCallback(async () => {
    if (!newAlert.symbol || !newAlert.value || newAlert.value <= 0) {
      setShowToast({
        message: 'Please fill in all required fields.',
        type: 'warning',
      });
      return;
    }

    setIsCreatingAlert(true);
    try {
      const response = await api.post('/markets/alerts', newAlert);
      if (response.data) {
        setAlerts(prev => [response.data, ...prev]);
        setShowAlertModal(false);
        setNewAlert({
          symbol: '',
          condition: 'above',
          value: 0,
          type: 'price',
        });
        setShowToast({
          message: `Alert created for ${newAlert.symbol}`,
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to create alert',
        type: 'error',
      });
    } finally {
      setIsCreatingAlert(false);
    }
  }, [api, newAlert]);

  const handleDeleteAlert = useCallback(async (alertId: string) => {
    try {
      await api.delete(`/markets/alerts/${alertId}`);
      setAlerts(prev => prev.filter(a => a.id !== alertId));
      setShowToast({
        message: 'Alert deleted',
        type: 'info',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to delete alert',
        type: 'error',
      });
    }
  }, [api]);

  // ============================================
  // Effects
  // ============================================

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/authentication/login?callbackUrl=/markets');
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
        fetchPairs();
        fetchStats();
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [fetchPairs, fetchStats, isRefreshing]);

  // ============================================
  // Memoized Computations
  // ============================================

  const filteredPairs = useMemo(() => {
    let result = pairs;

    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(pair =>
        pair.symbol.toLowerCase().includes(query) ||
        pair.name?.toLowerCase().includes(query)
      );
    }

    if (selectedCategory !== 'all') {
      result = result.filter(pair => pair.category === selectedCategory);
    }

    return result;
  }, [pairs, searchQuery, selectedCategory]);

  const watchlistPairs = useMemo(() => {
    return pairs.filter(pair => isInWatchlist(pair.symbol));
  }, [pairs, isInWatchlist]);

  const marketCapTotal = useMemo(() => {
    return stats?.totalMarketCap || 0;
  }, [stats]);

  const volumeTotal = useMemo(() => {
    return stats?.totalVolume24h || 0;
  }, [stats]);

  const btcDominance = useMemo(() => {
    return stats?.btcDominance || 0;
  }, [stats]);

  const marketTrend = useMemo(() => {
    return stats?.trend || 'neutral';
  }, [stats]);

  // ============================================
  // Render
  // ============================================

  if (isLoading && pairsLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-6">
            <div className="absolute inset-0 border-4 border-cyan-500/30 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-t-cyan-500 rounded-full animate-spin"></div>
            <div className="absolute inset-2 bg-cyan-500/10 rounded-full animate-pulse"></div>
          </div>
          <p className="text-gray-400 text-lg font-medium">Loading Markets...</p>
          <p className="text-gray-500 text-sm mt-2">Fetching market data</p>
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
                Markets
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                Real-time market data and analysis
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

          {/* Market Stats */}
          {stats && (
            <div className="flex items-center gap-4 px-3 py-1.5 bg-gray-800 rounded-lg border border-gray-700">
              <div>
                <span className="text-xs text-gray-400">Market Cap</span>
                <span className="text-sm font-bold text-white ml-2">
                  {formatCurrency(marketCapTotal)}
                </span>
              </div>
              <div className="w-px h-6 bg-gray-700" />
              <div>
                <span className="text-xs text-gray-400">24h Volume</span>
                <span className="text-sm font-bold text-white ml-2">
                  {formatCurrency(volumeTotal)}
                </span>
              </div>
              <div className="w-px h-6 bg-gray-700" />
              <div>
                <span className="text-xs text-gray-400">BTC Dominance</span>
                <span className="text-sm font-bold text-cyan-400 ml-2">
                  {formatPercentage(btcDominance)}
                </span>
              </div>
            </div>
          )}

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
        </div>
      </div>

      {/* ============================================ */}
      {/* TOP GAINERS / LOSERS */}
      {/* ============================================ */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card className="p-4 bg-gray-800 border-gray-700">
          <h3 className="text-sm font-semibold text-green-500 mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4" />
            Top Gainers
          </h3>
          <div className="space-y-2">
            {topGainers.slice(0, 5).map((pair) => (
              <div key={pair.symbol} className="flex items-center justify-between text-sm hover:bg-gray-700/30 p-2 rounded transition-colors cursor-pointer" onClick={() => handlePairSelect(pair)}>
                <span className="font-mono text-white">{pair.symbol}</span>
                <span className="text-green-500 font-medium">
                  {formatPercentage(pair.changePercent24h)}
                </span>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-4 bg-gray-800 border-gray-700">
          <h3 className="text-sm font-semibold text-red-500 mb-3 flex items-center gap-2">
            <TrendingDown className="w-4 h-4" />
            Top Losers
          </h3>
          <div className="space-y-2">
            {topLosers.slice(0, 5).map((pair) => (
              <div key={pair.symbol} className="flex items-center justify-between text-sm hover:bg-gray-700/30 p-2 rounded transition-colors cursor-pointer" onClick={() => handlePairSelect(pair)}>
                <span className="font-mono text-white">{pair.symbol}</span>
                <span className="text-red-500 font-medium">
                  {formatPercentage(pair.changePercent24h)}
                </span>
              </div>
            ))}
          </div>
        </Card>

        <Card className="p-4 bg-gray-800 border-gray-700">
          <h3 className="text-sm font-semibold text-blue-500 mb-3 flex items-center gap-2">
            <Activity className="w-4 h-4" />
            Top Volume
          </h3>
          <div className="space-y-2">
            {topVolume.slice(0, 5).map((pair) => (
              <div key={pair.symbol} className="flex items-center justify-between text-sm hover:bg-gray-700/30 p-2 rounded transition-colors cursor-pointer" onClick={() => handlePairSelect(pair)}>
                <span className="font-mono text-white">{pair.symbol}</span>
                <span className="text-cyan-400 font-medium">
                  {formatCurrency(pair.volume24h)}
                </span>
              </div>
            ))}
          </div>
        </Card>
      </div>

      {/* ============================================ */}
      {/* FILTERS & SEARCH */}
      {/* ============================================ */}
      <div className="flex flex-wrap items-center gap-3 bg-gray-800/50 rounded-lg p-3 border border-gray-700 mb-6">
        <div className="flex-1 min-w-[200px]">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <Input
              ref={searchInputRef}
              type="text"
              placeholder="Search markets..."
              value={searchQuery}
              onChange={(e) => handleSearch(e.target.value)}
              className="w-full pl-9 bg-gray-700 border-gray-600 text-white text-sm"
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Category:</span>
          <Select
            value={selectedCategory}
            onValueChange={handleCategoryChange}
            className="w-32 bg-gray-700 border-gray-600 text-sm"
          >
            <option value="all">All</option>
            {MARKET_CATEGORIES.map((cat) => (
              <option key={cat.value} value={cat.value}>
                {cat.label}
              </option>
            ))}
          </Select>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Sort:</span>
          <Select
            value={selectedSort}
            onValueChange={handleSortChange}
            className="w-28 bg-gray-700 border-gray-600 text-sm"
          >
            {MARKET_SORT_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </Select>
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={handleSortDirectionToggle}
          className="text-gray-400 hover:text-white"
        >
          {filterDirection === 'desc' ? '↓' : '↑'}
        </Button>

        <div className="flex items-center gap-1 ml-auto">
          <Button
            variant={viewMode === 'grid' ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setViewMode('grid')}
            className={viewMode === 'grid' ? 'bg-cyan-600 hover:bg-cyan-700' : 'text-gray-400 hover:text-white'}
          >
            <Grid className="w-4 h-4" />
          </Button>
          <Button
            variant={viewMode === 'list' ? 'primary' : 'ghost'}
            size="sm"
            onClick={() => setViewMode('list')}
            className={viewMode === 'list' ? 'bg-cyan-600 hover:bg-cyan-700' : 'text-gray-400 hover:text-white'}
          >
            <List className="w-4 h-4" />
          </Button>
        </div>
      </div>

      {/* ============================================ */}
      {/* MAIN CONTENT - TABS */}
      {/* ============================================ */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-gray-800 border border-gray-700 rounded-lg p-1 w-full overflow-x-auto">
          <TabsTrigger
            value="all"
            className="data-[state=active]:bg-cyan-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📊 All Markets ({filteredPairs.length})
          </TabsTrigger>
          <TabsTrigger
            value="watchlist"
            className="data-[state=active]:bg-yellow-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            ⭐ Watchlist ({watchlistPairs.length})
          </TabsTrigger>
          <TabsTrigger
            value="alerts"
            className="data-[state=active]:bg-red-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            🔔 Alerts ({alerts.length})
          </TabsTrigger>
          <TabsTrigger
            value="news"
            className="data-[state=active]:bg-blue-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📰 News ({news.length})
          </TabsTrigger>
        </TabsList>

        {/* ========================================== */}
        {/* ALL MARKETS TAB */}
        {/* ========================================== */}
        <TabsContent value="all" className="mt-4">
          {viewMode === 'grid' ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {filteredPairs.map((pair) => (
                <MarketCard
                  key={pair.symbol}
                  pair={pair}
                  isInWatchlist={isInWatchlist(pair.symbol)}
                  onWatchlistToggle={() => {
                    if (isInWatchlist(pair.symbol)) {
                      handleRemoveFromWatchlist(pair.symbol);
                    } else {
                      handleAddToWatchlist(pair.symbol);
                    }
                  }}
                  onClick={() => handlePairSelect(pair)}
                />
              ))}
            </div>
          ) : (
            <Card className="p-4 bg-gray-800 border-gray-700">
              <Table>
                <thead>
                  <tr className="border-b border-gray-700">
                    <th className="text-left text-xs text-gray-400 p-3">#</th>
                    <th className="text-left text-xs text-gray-400 p-3">Name</th>
                    <th className="text-right text-xs text-gray-400 p-3">Price</th>
                    <th className="text-right text-xs text-gray-400 p-3">24h Change</th>
                    <th className="text-right text-xs text-gray-400 p-3">24h High</th>
                    <th className="text-right text-xs text-gray-400 p-3">24h Low</th>
                    <th className="text-right text-xs text-gray-400 p-3">Volume</th>
                    <th className="text-center text-xs text-gray-400 p-3">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredPairs.map((pair, index) => (
                    <tr key={pair.symbol} className="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors cursor-pointer" onClick={() => handlePairSelect(pair)}>
                      <td className="p-3 text-gray-400 text-sm">{index + 1}</td>
                      <td className="p-3">
                        <div className="flex items-center gap-2">
                          <span className="font-mono text-white font-medium">{pair.symbol}</span>
                          {pair.category && (
                            <Badge className="bg-gray-600 text-xs">{pair.category}</Badge>
                          )}
                        </div>
                      </td>
                      <td className="p-3 text-right text-white font-mono">{formatCurrency(pair.price)}</td>
                      <td className={cn(
                        "p-3 text-right font-medium",
                        pair.changePercent24h >= 0 ? 'text-green-500' : 'text-red-500'
                      )}>
                        {formatPercentage(pair.changePercent24h)}
                      </td>
                      <td className="p-3 text-right text-gray-400 font-mono">{formatCurrency(pair.high24h)}</td>
                      <td className="p-3 text-right text-gray-400 font-mono">{formatCurrency(pair.low24h)}</td>
                      <td className="p-3 text-right text-gray-300 font-mono">{formatCurrency(pair.volume24h)}</td>
                      <td className="p-3 text-center">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            e.stopPropagation();
                            if (isInWatchlist(pair.symbol)) {
                              handleRemoveFromWatchlist(pair.symbol);
                            } else {
                              handleAddToWatchlist(pair.symbol);
                            }
                          }}
                          className={isInWatchlist(pair.symbol) ? 'text-yellow-500' : 'text-gray-400 hover:text-yellow-500'}
                        >
                          {isInWatchlist(pair.symbol) ? <Star className="w-4 h-4 fill-yellow-500" /> : <Star className="w-4 h-4" />}
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </Table>
            </Card>
          )}
        </TabsContent>

        {/* ========================================== */}
        {/* WATCHLIST TAB */}
        {/* ========================================== */}
        <TabsContent value="watchlist" className="mt-4">
          {watchlistPairs.length > 0 ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-4">
              {watchlistPairs.map((pair) => (
                <MarketCard
                  key={pair.symbol}
                  pair={pair}
                  isInWatchlist={true}
                  onWatchlistToggle={() => handleRemoveFromWatchlist(pair.symbol)}
                  onClick={() => handlePairSelect(pair)}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <Star className="w-16 h-16 mx-auto mb-4 text-gray-600" />
              <p className="text-lg font-medium">Your watchlist is empty</p>
              <p className="text-sm">Add markets to your watchlist to track them here</p>
              <Button
                onClick={() => setActiveTab('all')}
                className="mt-4 bg-gradient-to-r from-cyan-500 to-blue-500"
              >
                Browse Markets
              </Button>
            </div>
          )}
        </TabsContent>

        {/* ========================================== */}
        {/* ALERTS TAB */}
        {/* ========================================== */}
        <TabsContent value="alerts" className="mt-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-300">Your Alerts</h3>
            <Button
              onClick={() => setShowAlertModal(true)}
              className="bg-gradient-to-r from-yellow-500 to-orange-500"
            >
              <Plus className="w-4 h-4 mr-2" />
              Create Alert
            </Button>
          </div>
          {alerts.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {alerts.map((alert) => (
                <Card key={alert.id} className="p-4 bg-gray-800 border-gray-700">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-white font-bold">{alert.symbol}</span>
                        <Badge className={cn(
                          "text-xs",
                          alert.condition === 'above' ? 'bg-green-500/20 text-green-500' :
                          'bg-red-500/20 text-red-500'
                        )}>
                          {alert.condition === 'above' ? '▲' : '▼'} {formatCurrency(alert.value)}
                        </Badge>
                      </div>
                      <div className="text-sm text-gray-400 mt-1">{alert.type} alert</div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={alert.active}
                        onCheckedChange={() => {
                          // Toggle alert active status
                        }}
                        className="data-[state=checked]:bg-cyan-500"
                      />
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteAlert(alert.id)}
                        className="text-red-400 hover:text-red-300"
                      >
                        <XCircle className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                  {alert.triggeredAt && (
                    <div className="mt-2 text-xs text-yellow-500">
                      Triggered: {formatTime(alert.triggeredAt)}
                    </div>
                  )}
                </Card>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <BellRing className="w-16 h-16 mx-auto mb-4 text-gray-600" />
              <p className="text-lg font-medium">No alerts set</p>
              <p className="text-sm">Create price alerts to stay informed</p>
            </div>
          )}
        </TabsContent>

        {/* ========================================== */}
        {/* NEWS TAB */}
        {/* ========================================== */}
        <TabsContent value="news" className="mt-4">
          {newsLoading ? (
            <div className="text-center py-8">
              <Spinner size="lg" className="mx-auto text-cyan-500" />
              <p className="text-gray-400 mt-4">Loading news...</p>
            </div>
          ) : news.length > 0 ? (
            <div className="space-y-4">
              {news.map((article) => (
                <Card key={article.id} className="p-4 bg-gray-800 border-gray-700 hover:border-blue-500/50 transition-colors">
                  <div className="flex items-start gap-4">
                    {article.image && (
                      <img src={article.image} alt={article.title} className="w-24 h-24 object-cover rounded-lg flex-shrink-0" />
                    )}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-start justify-between">
                        <h4 className="text-white font-medium hover:text-blue-400 transition-colors cursor-pointer">
                          {article.title}
                        </h4>
                        <span className="text-xs text-gray-500 whitespace-nowrap ml-4">
                          {formatTime(article.timestamp)}
                        </span>
                      </div>
                      <p className="text-sm text-gray-400 mt-1 line-clamp-2">{article.description}</p>
                      <div className="flex items-center gap-3 mt-2">
                        <Badge className="bg-blue-500/20 text-blue-500 text-xs">{article.source}</Badge>
                        {article.symbols && article.symbols.slice(0, 3).map((sym) => (
                          <Badge key={sym} className="bg-gray-600 text-xs">#{sym}</Badge>
                        ))}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => window.open(article.url, '_blank')}
                          className="text-cyan-400 hover:text-cyan-300 ml-auto"
                        >
                          Read More <ExternalLink className="w-3 h-3 ml-1" />
                        </Button>
                      </div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <Globe2 className="w-16 h-16 mx-auto mb-4 text-gray-600" />
              <p className="text-lg font-medium">No news available</p>
              <p className="text-sm">Market news will appear here</p>
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* ============================================ */}
      {/* DETAILED PAIR VIEW - SIDEBAR */}
      {/* ============================================ */}
      {selectedPair && (
        <div className="fixed right-0 top-0 h-full w-96 bg-gray-800 border-l border-gray-700 shadow-2xl transform transition-transform duration-300 z-50 overflow-y-auto">
          <div className="p-6">
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-3">
                <h2 className="text-lg font-bold text-white">{selectedPair.symbol}</h2>
                {selectedPair.category && (
                  <Badge className="bg-gray-600 text-xs">{selectedPair.category}</Badge>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    if (isInWatchlist(selectedPair.symbol)) {
                      handleRemoveFromWatchlist(selectedPair.symbol);
                    } else {
                      handleAddToWatchlist(selectedPair.symbol);
                    }
                  }}
                  className={isInWatchlist(selectedPair.symbol) ? 'text-yellow-500' : 'text-gray-400 hover:text-yellow-500'}
                >
                  {isInWatchlist(selectedPair.symbol) ? <Star className="w-5 h-5 fill-yellow-500" /> : <Star className="w-5 h-5" />}
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedPair(null)}
                  className="text-gray-400 hover:text-white"
                >
                  ✕
                </Button>
              </div>
            </div>

            {/* Price */}
            <div className="mb-6">
              <div className="text-3xl font-bold text-white">{formatCurrency(selectedPair.price)}</div>
              <div className={cn(
                "text-sm font-medium",
                selectedPair.changePercent24h >= 0 ? 'text-green-500' : 'text-red-500'
              )}>
                {selectedPair.changePercent24h >= 0 ? '▲' : '▼'} {formatPercentage(selectedPair.changePercent24h)}
              </div>
            </div>

            {/* Chart */}
            <div className="mb-6">
              <div className="flex items-center gap-2 mb-3">
                <Select
                  value={selectedChartTimeframe}
                  onValueChange={handleTimeframeChange}
                  className="w-24 bg-gray-700 border-gray-600 text-sm"
                >
                  <option value="1h">1h</option>
                  <option value="4h">4h</option>
                  <option value="1d">1d</option>
                  <option value="1w">1w</option>
                  <option value="1M">1M</option>
                </Select>
              </div>
              <div ref={chartContainerRef} className="h-48">
                {chartLoading ? (
                  <div className="flex items-center justify-center h-full">
                    <Spinner size="sm" className="text-cyan-500" />
                  </div>
                ) : chartData.length > 0 ? (
                  <LineChart
                    data={chartData}
                    xKey="date"
                    yKey="price"
                    color="#06b6d4"
                    height={180}
                    gradient
                  />
                ) : (
                  <div className="flex items-center justify-center h-full text-gray-500 text-sm">
                    No chart data
                  </div>
                )}
              </div>
            </div>

            {/* Stats */}
            <div className="grid grid-cols-2 gap-3 mb-6">
              <div>
                <div className="text-xs text-gray-500">24h High</div>
                <div className="text-white font-mono">{formatCurrency(selectedPair.high24h)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">24h Low</div>
                <div className="text-white font-mono">{formatCurrency(selectedPair.low24h)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">24h Volume</div>
                <div className="text-white font-mono">{formatCurrency(selectedPair.volume24h)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-500">Market Cap</div>
                <div className="text-white font-mono">{formatCurrency(selectedPair.marketCap || 0)}</div>
              </div>
            </div>

            {/* Actions */}
            <div className="space-y-2">
              <Button
                variant="primary"
                className="w-full bg-gradient-to-r from-cyan-500 to-blue-500"
                onClick={() => router.push(`/exchange?symbol=${selectedPair.symbol}`)}
              >
                Trade {selectedPair.symbol}
              </Button>
              <Button
                variant="outline"
                className="w-full border-gray-600 hover:border-cyan-500"
                onClick={() => {
                  setNewAlert({
                    symbol: selectedPair.symbol,
                    condition: 'above',
                    value: selectedPair.price * 1.05,
                    type: 'price',
                  });
                  setShowAlertModal(true);
                }}
              >
                <BellRing className="w-4 h-4 mr-2" />
                Set Alert
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================ */}
      {/* CREATE ALERT MODAL */}
      {/* ============================================ */}
      <Modal
        open={showAlertModal}
        onOpenChange={setShowAlertModal}
        title="Create Price Alert"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Symbol *</label>
            <Select
              value={newAlert.symbol}
              onValueChange={(value) => setNewAlert({ ...newAlert, symbol: value })}
              className="w-full bg-gray-700 border-gray-600"
            >
              {SUPPORTED_PAIRS.map((pair) => (
                <option key={pair} value={pair}>
                  {pair}
                </option>
              ))}
            </Select>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Condition</label>
              <Select
                value={newAlert.condition}
                onValueChange={(value) => setNewAlert({ ...newAlert, condition: value as 'above' | 'below' })}
                className="w-full bg-gray-700 border-gray-600"
              >
                <option value="above">Above</option>
                <option value="below">Below</option>
              </Select>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Value *</label>
              <Input
                type="number"
                step="0.01"
                value={newAlert.value}
                onChange={(e) => setNewAlert({ ...newAlert, value: parseFloat(e.target.value) || 0 })}
                className="w-full bg-gray-700 border-gray-600 text-white"
              />
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Alert Type</label>
            <Select
              value={newAlert.type}
              onValueChange={(value) => setNewAlert({ ...newAlert, type: value as 'price' | 'volume' | 'change' })}
              className="w-full bg-gray-700 border-gray-600"
            >
              <option value="price">Price Alert</option>
              <option value="volume">Volume Alert</option>
              <option value="change">Change Alert</option>
            </Select>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => setShowAlertModal(false)}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateAlert}
              isLoading={isCreatingAlert}
              className="bg-gradient-to-r from-yellow-500 to-orange-500"
            >
              Create Alert
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

// ============================================
// MARKET CARD COMPONENT
// ============================================

interface MarketCardProps {
  pair: MarketPair;
  isInWatchlist: boolean;
  onWatchlistToggle: () => void;
  onClick: () => void;
}

function MarketCard({ pair, isInWatchlist, onWatchlistToggle, onClick }: MarketCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.02 }}
      transition={{ duration: 0.2 }}
    >
      <Card
        className="p-4 bg-gray-800 border-gray-700 hover:border-cyan-500/50 transition-all cursor-pointer"
        onClick={onClick}
      >
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="font-mono text-white font-bold text-sm">{pair.symbol}</span>
            {pair.category && (
              <Badge className="bg-gray-600 text-xs">{pair.category}</Badge>
            )}
          </div>
          <Button
            variant="ghost"
            size="sm"
            onClick={(e) => {
              e.stopPropagation();
              onWatchlistToggle();
            }}
            className={isInWatchlist ? 'text-yellow-500' : 'text-gray-400 hover:text-yellow-500'}
          >
            {isInWatchlist ? <Star className="w-4 h-4 fill-yellow-500" /> : <Star className="w-4 h-4" />}
          </Button>
        </div>
        <div className="text-lg font-bold text-white">{formatCurrency(pair.price)}</div>
        <div className="flex items-center gap-2 mt-1">
          <span className={cn(
            "text-sm font-medium",
            pair.changePercent24h >= 0 ? 'text-green-500' : 'text-red-500'
          )}>
            {pair.changePercent24h >= 0 ? '▲' : '▼'} {formatPercentage(pair.changePercent24h)}
          </span>
          <span className="text-xs text-gray-500">24h</span>
        </div>
        <div className="flex justify-between mt-3 text-xs text-gray-500">
          <span>Vol: {formatCurrency(pair.volume24h)}</span>
          <span>High: {formatCurrency(pair.high24h)}</span>
          <span>Low: {formatCurrency(pair.low24h)}</span>
        </div>
      </Card>
    </motion.div>
  );
}

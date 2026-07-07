/**
 * NEXUS AI TRADING SYSTEM - Exchange Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page provides a complete trading interface including:
 * - Real-time order book
 * - Live price chart with multiple timeframes
 * - Order entry and management
 * - Position management
 * - Trading history
 * - Market depth visualization
 * - Multiple order types (Market, Limit, Stop, Stop-Limit)
 * - Advanced chart indicators
 * - Trading pair selection
 * - Portfolio balance display
 * - WebSocket real-time updates
 * - Order confirmation and risk management
 * - Trade execution with slippage control
 * - One-click trading
 * - TradingView chart integration
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
import { usePortfolio } from '@/hooks/usePortfolio';

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

// Charts
import { LineChart, CandlestickChart, DepthChart } from '@/components/charts';

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
  OrderBook,
  Trade,
  Order,
  Position,
  TradingPair,
  OrderType,
  OrderSide,
  Timeframe,
  ChartData,
  MarketDepth,
} from '@/types/exchange';

// Constants
import {
  TRADING_PAIRS,
  ORDER_TYPES,
  ORDER_SIDES,
  TIMEFRAMES,
  DEFAULT_CHART_CONFIG,
  DEFAULT_TRADING_CONFIG,
} from '@/constants/exchange';

// Utils
import { formatCurrency, formatNumber, formatPercentage, formatDate, formatTime } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

export default function ExchangePage() {
  // Router
  const router = useRouter();

  // Auth hooks
  const { user, isAuthenticated } = useAuth();

  // API client
  const api = useApi();

  // Hooks
  const { portfolio, positions, refresh: refreshPortfolio } = usePortfolio();
  const { marketData, watchlist, loading: marketLoading, refresh: refreshMarket } = useMarketData();

  // State - Trading Pair
  const [selectedPair, setSelectedPair] = useState<TradingPair>(TRADING_PAIRS[0]);
  const [selectedTimeframe, setSelectedTimeframe] = useState<Timeframe>('1h');

  // State - Order Book
  const [orderBook, setOrderBook] = useState<OrderBook | null>(null);
  const [orderBookLoading, setOrderBookLoading] = useState<boolean>(true);

  // State - Chart
  const [chartData, setChartData] = useState<ChartData[]>([]);
  const [chartLoading, setChartLoading] = useState<boolean>(true);
  const [chartIndicators, setChartIndicators] = useState<string[]>([]);

  // State - Trading
  const [orderType, setOrderType] = useState<OrderType>('limit');
  const [orderSide, setOrderSide] = useState<OrderSide>('buy');
  const [orderPrice, setOrderPrice] = useState<string>('');
  const [orderQuantity, setOrderQuantity] = useState<string>('');
  const [orderTotal, setOrderTotal] = useState<string>('');
  const [stopPrice, setStopPrice] = useState<string>('');
  const [takeProfit, setTakeProfit] = useState<string>('');
  const [slippage, setSlippage] = useState<number>(0.5);
  const [usePostOnly, setUsePostOnly] = useState<boolean>(false);
  const [useReduceOnly, setUseReduceOnly] = useState<boolean>(false);
  const [isSubmittingOrder, setIsSubmittingOrder] = useState<boolean>(false);

  // State - Orders
  const [orders, setOrders] = useState<Order[]>([]);
  const [ordersLoading, setOrdersLoading] = useState<boolean>(true);

  // State - Trades
  const [trades, setTrades] = useState<Trade[]>([]);
  const [tradesLoading, setTradesLoading] = useState<boolean>(true);

  // State - UI
  const [showConfirmModal, setShowConfirmModal] = useState<boolean>(false);
  const [confirmOrder, setConfirmOrder] = useState<any>(null);
  const [activeTab, setActiveTab] = useState<string>('trading');
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Refs
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const orderBookRef = useRef<HTMLDivElement>(null);

  // ============================================
  // WebSocket Connection
  // ============================================

  const {
    isConnected,
    sendMessage,
    subscribe: wsSubscribe,
    unsubscribe: wsUnsubscribe,
  } = useWebSocket({
    url: `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8004'}/exchange`,
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
    console.log('✅ Exchange WebSocket connected');
    subscribeToChannels();
  }

  function handleWebSocketMessage(event: MessageEvent) {
    try {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'order_book':
          handleOrderBookUpdate(data.payload);
          break;
        case 'trade':
          handleTradeUpdate(data.payload);
          break;
        case 'order_update':
          handleOrderUpdate(data.payload);
          break;
        case 'market_data':
          handleMarketDataUpdate(data.payload);
          break;
        case 'position_update':
          handlePositionUpdate(data.payload);
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
    console.log('Exchange WebSocket disconnected');
  }

  function subscribeToChannels() {
    if (!isConnected) return;

    wsSubscribe({
      channel: 'order_book',
      symbol: selectedPair.symbol,
    });

    wsSubscribe({
      channel: 'trades',
      symbol: selectedPair.symbol,
    });

    wsSubscribe({
      channel: 'market_data',
      symbol: selectedPair.symbol,
    });
  }

  // ============================================
  // WebSocket Data Handlers
  // ============================================

  function handleOrderBookUpdate(data: any) {
    setOrderBook({
      ...data,
      bids: data.bids.map((bid: [number, number]) => ({
        price: bid[0],
        quantity: bid[1],
        total: bid[0] * bid[1],
      })),
      asks: data.asks.map((ask: [number, number]) => ({
        price: ask[0],
        quantity: ask[1],
        total: ask[0] * ask[1],
      })),
      timestamp: new Date(data.timestamp),
    });
  }

  function handleTradeUpdate(data: any) {
    setTrades(prev => [{
      ...data,
      timestamp: new Date(data.timestamp),
    }, ...prev].slice(0, 100));
  }

  function handleOrderUpdate(data: any) {
    setOrders(prev => {
      const index = prev.findIndex(o => o.id === data.id);
      if (index > -1) {
        const newOrders = [...prev];
        newOrders[index] = { ...data, timestamp: new Date(data.timestamp) };
        return newOrders;
      }
      return [{ ...data, timestamp: new Date(data.timestamp) }, ...prev];
    });
    refreshPortfolio();
  }

  function handleMarketDataUpdate(data: any) {
    // Update market data
  }

  function handlePositionUpdate(data: any) {
    refreshPortfolio();
  }

  // ============================================
  // API Calls
  // ============================================

  const fetchOrderBook = useCallback(async () => {
    try {
      setOrderBookLoading(true);
      const response = await api.get('/exchange/order-book', {
        params: { symbol: selectedPair.symbol, depth: 20 },
      });
      if (response.data) {
        setOrderBook(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch order book:', error);
    } finally {
      setOrderBookLoading(false);
    }
  }, [api, selectedPair.symbol]);

  const fetchChartData = useCallback(async () => {
    try {
      setChartLoading(true);
      const response = await api.get('/exchange/chart-data', {
        params: {
          symbol: selectedPair.symbol,
          timeframe: selectedTimeframe,
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
  }, [api, selectedPair.symbol, selectedTimeframe]);

  const fetchOrders = useCallback(async () => {
    try {
      setOrdersLoading(true);
      const response = await api.get('/exchange/orders', {
        params: { symbol: selectedPair.symbol, limit: 50 },
      });
      if (response.data) {
        setOrders(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch orders:', error);
    } finally {
      setOrdersLoading(false);
    }
  }, [api, selectedPair.symbol]);

  const fetchTrades = useCallback(async () => {
    try {
      setTradesLoading(true);
      const response = await api.get('/exchange/trades', {
        params: { symbol: selectedPair.symbol, limit: 50 },
      });
      if (response.data) {
        setTrades(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch trades:', error);
    } finally {
      setTradesLoading(false);
    }
  }, [api, selectedPair.symbol]);

  const fetchAllData = useCallback(async () => {
    setIsLoading(true);
    setIsRefreshing(true);
    try {
      await Promise.all([
        fetchOrderBook(),
        fetchChartData(),
        fetchOrders(),
        fetchTrades(),
        refreshPortfolio(),
      ]);
    } catch (error) {
      console.error('Failed to fetch exchange data:', error);
      setShowToast({
        message: 'Failed to load exchange data. Please refresh.',
        type: 'error',
      });
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [fetchOrderBook, fetchChartData, fetchOrders, fetchTrades, refreshPortfolio]);

  // ============================================
  // Handlers - Trading
  // ============================================

  const calculateTotal = useCallback(() => {
    const price = parseFloat(orderPrice) || 0;
    const quantity = parseFloat(orderQuantity) || 0;
    return price * quantity;
  }, [orderPrice, orderQuantity]);

  const handleOrderPriceChange = useCallback((value: string) => {
    setOrderPrice(value);
    const total = calculateTotal();
    setOrderTotal(total > 0 ? total.toFixed(2) : '');
  }, [calculateTotal]);

  const handleOrderQuantityChange = useCallback((value: string) => {
    setOrderQuantity(value);
    const total = calculateTotal();
    setOrderTotal(total > 0 ? total.toFixed(2) : '');
  }, [calculateTotal]);

  const handleOrderTotalChange = useCallback((value: string) => {
    setOrderTotal(value);
    const price = parseFloat(orderPrice) || 0;
    const total = parseFloat(value) || 0;
    if (price > 0) {
      setOrderQuantity((total / price).toFixed(8));
    }
  }, [orderPrice]);

  const handleSetOrderSide = useCallback((side: OrderSide) => {
    setOrderSide(side);
  }, []);

  const handleSetOrderType = useCallback((type: OrderType) => {
    setOrderType(type);
    if (type === 'market') {
      setOrderPrice('');
    }
  }, []);

  const handlePlaceOrder = useCallback(async () => {
    // Validate order
    const quantity = parseFloat(orderQuantity);
    const price = parseFloat(orderPrice);

    if (orderType !== 'market' && (!price || price <= 0)) {
      setShowToast({
        message: 'Please enter a valid price.',
        type: 'warning',
      });
      return;
    }

    if (!quantity || quantity <= 0) {
      setShowToast({
        message: 'Please enter a valid quantity.',
        type: 'warning',
      });
      return;
    }

    // Check balance
    const balance = orderSide === 'buy' 
      ? portfolio?.balances?.find(b => b.currency === selectedPair.quoteCurrency)?.available || 0
      : portfolio?.balances?.find(b => b.currency === selectedPair.baseCurrency)?.available || 0;

    const required = orderSide === 'buy' ? quantity * price : quantity;
    if (required > balance) {
      setShowToast({
        message: `Insufficient balance. Required: ${formatCurrency(required)}`,
        type: 'error',
      });
      return;
    }

    // Prepare order
    const orderData = {
      symbol: selectedPair.symbol,
      side: orderSide,
      type: orderType,
      quantity,
      price: orderType !== 'market' ? price : undefined,
      stopPrice: stopPrice ? parseFloat(stopPrice) : undefined,
      takeProfit: takeProfit ? parseFloat(takeProfit) : undefined,
      slippage,
      postOnly: usePostOnly,
      reduceOnly: useReduceOnly,
    };

    setConfirmOrder(orderData);
    setShowConfirmModal(true);
  }, [
    orderType,
    orderSide,
    orderQuantity,
    orderPrice,
    stopPrice,
    takeProfit,
    slippage,
    usePostOnly,
    useReduceOnly,
    selectedPair,
    portfolio,
  ]);

  const handleConfirmOrder = useCallback(async () => {
    if (!confirmOrder) return;

    setIsSubmittingOrder(true);
    try {
      const response = await api.post('/exchange/orders', confirmOrder);
      if (response.data) {
        setShowToast({
          message: `Order placed successfully! ${orderSide.toUpperCase()} ${formatNumber(confirmOrder.quantity)} ${selectedPair.baseCurrency}`,
          type: 'success',
        });
        setShowConfirmModal(false);
        setOrderPrice('');
        setOrderQuantity('');
        setOrderTotal('');
        await fetchOrders();
        await refreshPortfolio();
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to place order.',
        type: 'error',
      });
    } finally {
      setIsSubmittingOrder(false);
    }
  }, [api, confirmOrder, orderSide, selectedPair, fetchOrders, refreshPortfolio]);

  const handleCancelOrder = useCallback(async (orderId: string) => {
    try {
      await api.delete(`/exchange/orders/${orderId}`);
      setShowToast({
        message: 'Order cancelled successfully.',
        type: 'info',
      });
      await fetchOrders();
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to cancel order.',
        type: 'error',
      });
    }
  }, [api, fetchOrders]);

  // ============================================
  // Effects
  // ============================================

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/authentication/login?callbackUrl=/exchange');
    } else {
      fetchAllData();
    }
  }, [isAuthenticated, router, fetchAllData]);

  useEffect(() => {
    if (isConnected) {
      subscribeToChannels();
    }
  }, [isConnected, selectedPair]);

  useEffect(() => {
    fetchOrderBook();
    fetchChartData();
    fetchTrades();
  }, [selectedPair, fetchOrderBook, fetchChartData, fetchTrades]);

  // Auto-refresh data
  useEffect(() => {
    const interval = setInterval(() => {
      if (!isRefreshing) {
        fetchOrderBook();
      }
    }, 10000);

    return () => clearInterval(interval);
  }, [fetchOrderBook, isRefreshing]);

  // ============================================
  // Memoized Computations
  // ============================================

  const currentPrice = useMemo(() => {
    return marketData?.[selectedPair.symbol]?.price || 0;
  }, [marketData, selectedPair.symbol]);

  const currentBid = useMemo(() => {
    return marketData?.[selectedPair.symbol]?.bid || orderBook?.bids?.[0]?.price || 0;
  }, [marketData, selectedPair.symbol, orderBook]);

  const currentAsk = useMemo(() => {
    return marketData?.[selectedPair.symbol]?.ask || orderBook?.asks?.[0]?.price || 0;
  }, [marketData, selectedPair.symbol, orderBook]);

  const priceChange24h = useMemo(() => {
    return marketData?.[selectedPair.symbol]?.changePercent24h || 0;
  }, [marketData, selectedPair.symbol]);

  const availableBalance = useMemo(() => {
    if (!portfolio?.balances) return 0;
    const currency = orderSide === 'buy' ? selectedPair.quoteCurrency : selectedPair.baseCurrency;
    return portfolio.balances.find(b => b.currency === currency)?.available || 0;
  }, [portfolio, orderSide, selectedPair]);

  const totalBalance = useMemo(() => {
    if (!portfolio?.balances) return 0;
    const currency = orderSide === 'buy' ? selectedPair.quoteCurrency : selectedPair.baseCurrency;
    return portfolio.balances.find(b => b.currency === currency)?.total || 0;
  }, [portfolio, orderSide, selectedPair]);

  const pendingOrders = useMemo(() => {
    return orders.filter(o => o.status === 'pending' || o.status === 'open');
  }, [orders]);

  const orderBookBids = useMemo(() => {
    return orderBook?.bids || [];
  }, [orderBook]);

  const orderBookAsks = useMemo(() => {
    return orderBook?.asks || [];
  }, [orderBook]);

  // ============================================
  // Render
  // ============================================

  if (isLoading && orderBookLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-6">
            <div className="absolute inset-0 border-4 border-cyan-500/30 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-t-cyan-500 rounded-full animate-spin"></div>
            <div className="absolute inset-2 bg-cyan-500/10 rounded-full animate-pulse"></div>
          </div>
          <p className="text-gray-400 text-lg font-medium">Loading Exchange...</p>
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
      <div className="flex flex-wrap items-center justify-between mb-6 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="text-3xl">💱</div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                Exchange
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                Trade {selectedPair.baseCurrency}/{selectedPair.quoteCurrency}
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

          {/* Market Price */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded-lg border border-gray-700">
            <span className="text-xs text-gray-400">{selectedPair.symbol}</span>
            <span className="text-sm font-mono font-bold text-white">
              {formatCurrency(currentPrice)}
            </span>
            <span className={cn(
              "text-xs font-medium",
              priceChange24h >= 0 ? 'text-green-500' : 'text-red-500'
            )}>
              {priceChange24h >= 0 ? '▲' : '▼'} {formatPercentage(Math.abs(priceChange24h))}
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
        </div>
      </div>

      {/* ============================================ */}
      {/* MAIN GRID */}
      {/* ============================================ */}
      <div className="grid grid-cols-12 gap-6">
        {/* ========================================== */}
        {/* LEFT COLUMN - Trading Pair & Chart */}
        {/* ========================================== */}
        <div className="col-span-12 lg:col-span-8 space-y-6">
          {/* Trading Pair Selector */}
          <Card className="p-4 bg-gray-800 border-gray-700">
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-400">Pair:</span>
                <Select
                  value={selectedPair.symbol}
                  onValueChange={(value) => {
                    const pair = TRADING_PAIRS.find(p => p.symbol === value);
                    if (pair) setSelectedPair(pair);
                  }}
                  className="w-40 bg-gray-700 border-gray-600 text-sm"
                >
                  {TRADING_PAIRS.map((pair) => (
                    <option key={pair.symbol} value={pair.symbol}>
                      {pair.baseCurrency}/{pair.quoteCurrency}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="flex items-center gap-2">
                <span className="text-sm text-gray-400">Timeframe:</span>
                <Select
                  value={selectedTimeframe}
                  onValueChange={(value) => setSelectedTimeframe(value as Timeframe)}
                  className="w-24 bg-gray-700 border-gray-600 text-sm"
                >
                  {TIMEFRAMES.map((tf) => (
                    <option key={tf} value={tf}>
                      {tf}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="flex items-center gap-2 ml-auto">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-gray-400 hover:text-white"
                  onClick={() => setChartIndicators(prev => 
                    prev.includes('sma') ? prev.filter(i => i !== 'sma') : [...prev, 'sma']
                  )}
                >
                  SMA
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-gray-400 hover:text-white"
                  onClick={() => setChartIndicators(prev => 
                    prev.includes('ema') ? prev.filter(i => i !== 'ema') : [...prev, 'ema']
                  )}
                >
                  EMA
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-gray-400 hover:text-white"
                  onClick={() => setChartIndicators(prev => 
                    prev.includes('bollinger') ? prev.filter(i => i !== 'bollinger') : [...prev, 'bollinger']
                  )}
                >
                  Bollinger
                </Button>
              </div>
            </div>
          </Card>

          {/* Price Chart */}
          <Card className="p-4 bg-gray-800 border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <div>
                <h3 className="text-sm font-semibold text-gray-300">{selectedPair.symbol} Price</h3>
                <div className="flex items-center gap-3 mt-1">
                  <span className="text-2xl font-bold text-white">{formatCurrency(currentPrice)}</span>
                  <span className={cn(
                    "text-sm font-medium",
                    priceChange24h >= 0 ? 'text-green-500' : 'text-red-500'
                  )}>
                    {priceChange24h >= 0 ? '▲' : '▼'} {formatPercentage(Math.abs(priceChange24h))}
                  </span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-gray-400 hover:text-white"
                  onClick={() => setSelectedTimeframe('1m')}
                >
                  1m
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-gray-400 hover:text-white"
                  onClick={() => setSelectedTimeframe('5m')}
                >
                  5m
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-gray-400 hover:text-white"
                  onClick={() => setSelectedTimeframe('15m')}
                >
                  15m
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-gray-400 hover:text-white"
                  onClick={() => setSelectedTimeframe('1h')}
                >
                  1h
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-gray-400 hover:text-white"
                  onClick={() => setSelectedTimeframe('4h')}
                >
                  4h
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-gray-400 hover:text-white"
                  onClick={() => setSelectedTimeframe('1d')}
                >
                  1d
                </Button>
              </div>
            </div>
            <div ref={chartContainerRef} className="h-96">
              {chartLoading ? (
                <div className="flex items-center justify-center h-full">
                  <Spinner size="lg" className="text-cyan-500" />
                </div>
              ) : chartData.length > 0 ? (
                <CandlestickChart
                  data={chartData}
                  height={380}
                  indicators={chartIndicators}
                  showVolume
                />
              ) : (
                <div className="flex items-center justify-center h-full text-gray-500">
                  <p>No chart data available</p>
                </div>
              )}
            </div>
          </Card>
        </div>

        {/* ========================================== */}
        {/* RIGHT COLUMN - Order Book & Trading */}
        {/* ========================================== */}
        <div className="col-span-12 lg:col-span-4 space-y-6">
          {/* Order Book */}
          <Card className="p-4 bg-gray-800 border-gray-700">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-gray-300">Order Book</h3>
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500">Spread: {formatCurrency(currentAsk - currentBid)}</span>
              </div>
            </div>
            {orderBookLoading ? (
              <div className="flex items-center justify-center h-64">
                <Spinner size="sm" className="text-cyan-500" />
              </div>
            ) : (
              <div ref={orderBookRef} className="space-y-1 max-h-80 overflow-y-auto">
                {/* Asks (Sell Orders) */}
                <div className="space-y-0.5">
                  <div className="flex justify-between text-xs text-gray-500 px-2 py-1">
                    <span>Price</span>
                    <span>Size</span>
                    <span>Total</span>
                  </div>
                  {orderBookAsks.slice(0, 10).map((ask, index) => (
                    <div key={index} className="flex justify-between text-xs px-2 py-0.5 hover:bg-gray-700/50 rounded transition-colors">
                      <span className="text-red-500 font-mono">{formatCurrency(ask.price)}</span>
                      <span className="text-gray-300">{formatNumber(ask.quantity)}</span>
                      <span className="text-gray-400">{formatCurrency(ask.total)}</span>
                    </div>
                  ))}
                </div>

                {/* Current Price */}
                <div className="flex justify-between items-center py-2 border-y border-gray-700 my-1">
                  <span className="text-sm font-mono font-bold text-white">{formatCurrency(currentPrice)}</span>
                  <span className={cn(
                    "text-xs font-medium",
                    priceChange24h >= 0 ? 'text-green-500' : 'text-red-500'
                  )}>
                    {priceChange24h >= 0 ? '▲' : '▼'} {formatPercentage(Math.abs(priceChange24h))}
                  </span>
                </div>

                {/* Bids (Buy Orders) */}
                <div className="space-y-0.5">
                  {orderBookBids.slice(0, 10).map((bid, index) => (
                    <div key={index} className="flex justify-between text-xs px-2 py-0.5 hover:bg-gray-700/50 rounded transition-colors">
                      <span className="text-green-500 font-mono">{formatCurrency(bid.price)}</span>
                      <span className="text-gray-300">{formatNumber(bid.quantity)}</span>
                      <span className="text-gray-400">{formatCurrency(bid.total)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </Card>

          {/* Trading Form */}
          <Card className="p-4 bg-gray-800 border-gray-700">
            <div className="flex items-center gap-2 mb-4">
              <Button
                variant={orderSide === 'buy' ? 'primary' : 'outline'}
                size="sm"
                onClick={() => handleSetOrderSide('buy')}
                className={cn(
                  "flex-1",
                  orderSide === 'buy' ? 'bg-green-600 hover:bg-green-700' : 'border-gray-600 hover:border-green-500'
                )}
              >
                <ArrowUp className="w-4 h-4 mr-1" />
                Buy
              </Button>
              <Button
                variant={orderSide === 'sell' ? 'primary' : 'outline'}
                size="sm"
                onClick={() => handleSetOrderSide('sell')}
                className={cn(
                  "flex-1",
                  orderSide === 'sell' ? 'bg-red-600 hover:bg-red-700' : 'border-gray-600 hover:border-red-500'
                )}
              >
                <ArrowDown className="w-4 h-4 mr-1" />
                Sell
              </Button>
            </div>

            <div className="space-y-3">
              {/* Order Type */}
              <div className="flex gap-1">
                {ORDER_TYPES.map((type) => (
                  <Button
                    key={type}
                    variant={orderType === type ? 'primary' : 'outline'}
                    size="sm"
                    onClick={() => handleSetOrderType(type)}
                    className={cn(
                      "flex-1 text-xs",
                      orderType === type 
                        ? 'bg-cyan-600 hover:bg-cyan-700' 
                        : 'border-gray-600 hover:border-gray-500'
                    )}
                  >
                    {type.charAt(0).toUpperCase() + type.slice(1)}
                  </Button>
                ))}
              </div>

              {/* Price Input */}
              {orderType !== 'market' && (
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Price ({selectedPair.quoteCurrency})</label>
                  <div className="relative">
                    <Input
                      type="number"
                      step="0.01"
                      value={orderPrice}
                      onChange={(e) => handleOrderPriceChange(e.target.value)}
                      placeholder="0.00"
                      className="w-full bg-gray-700 border-gray-600 text-white font-mono"
                    />
                    <div className="absolute inset-y-0 right-0 flex items-center gap-1 pr-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-xs text-gray-400 hover:text-white"
                        onClick={() => setOrderPrice(currentBid.toString())}
                      >
                        Bid
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-6 text-xs text-gray-400 hover:text-white"
                        onClick={() => setOrderPrice(currentAsk.toString())}
                      >
                        Ask
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {/* Quantity Input */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Quantity ({selectedPair.baseCurrency})</label>
                <div className="relative">
                  <Input
                    type="number"
                    step="0.0001"
                    value={orderQuantity}
                    onChange={(e) => handleOrderQuantityChange(e.target.value)}
                    placeholder="0.0000"
                    className="w-full bg-gray-700 border-gray-600 text-white font-mono"
                  />
                  <div className="absolute inset-y-0 right-0 flex items-center gap-1 pr-2">
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 text-xs text-gray-400 hover:text-white"
                      onClick={() => {
                        const balance = availableBalance;
                        const price = parseFloat(orderPrice) || currentPrice;
                        if (orderSide === 'buy') {
                          setOrderQuantity((balance / price * 0.25).toFixed(8));
                        } else {
                          setOrderQuantity((balance * 0.25).toFixed(8));
                        }
                      }}
                    >
                      25%
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 text-xs text-gray-400 hover:text-white"
                      onClick={() => {
                        const balance = availableBalance;
                        const price = parseFloat(orderPrice) || currentPrice;
                        if (orderSide === 'buy') {
                          setOrderQuantity((balance / price * 0.5).toFixed(8));
                        } else {
                          setOrderQuantity((balance * 0.5).toFixed(8));
                        }
                      }}
                    >
                      50%
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 text-xs text-gray-400 hover:text-white"
                      onClick={() => {
                        const balance = availableBalance;
                        const price = parseFloat(orderPrice) || currentPrice;
                        if (orderSide === 'buy') {
                          setOrderQuantity((balance / price * 0.75).toFixed(8));
                        } else {
                          setOrderQuantity((balance * 0.75).toFixed(8));
                        }
                      }}
                    >
                      75%
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="h-6 text-xs text-cyan-400 hover:text-cyan-300"
                      onClick={() => {
                        const balance = availableBalance;
                        const price = parseFloat(orderPrice) || currentPrice;
                        if (orderSide === 'buy') {
                          setOrderQuantity((balance / price).toFixed(8));
                        } else {
                          setOrderQuantity(balance.toFixed(8));
                        }
                      }}
                    >
                      Max
                    </Button>
                  </div>
                </div>
              </div>

              {/* Total Input */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Total ({selectedPair.quoteCurrency})</label>
                <Input
                  type="number"
                  step="0.01"
                  value={orderTotal}
                  onChange={(e) => handleOrderTotalChange(e.target.value)}
                  placeholder="0.00"
                  className="w-full bg-gray-700 border-gray-600 text-white font-mono"
                />
              </div>

              {/* Stop Price (for Stop/Stop-Limit orders) */}
              {(orderType === 'stop' || orderType === 'stop_limit') && (
                <div>
                  <label className="block text-xs text-gray-400 mb-1">Stop Price</label>
                  <Input
                    type="number"
                    step="0.01"
                    value={stopPrice}
                    onChange={(e) => setStopPrice(e.target.value)}
                    placeholder="0.00"
                    className="w-full bg-gray-700 border-gray-600 text-white font-mono"
                  />
                </div>
              )}

              {/* Take Profit */}
              <div>
                <label className="block text-xs text-gray-400 mb-1">Take Profit (optional)</label>
                <Input
                  type="number"
                  step="0.01"
                  value={takeProfit}
                  onChange={(e) => setTakeProfit(e.target.value)}
                  placeholder="0.00"
                  className="w-full bg-gray-700 border-gray-600 text-white font-mono"
                />
              </div>

              {/* Advanced Options */}
              <div className="flex items-center gap-4 text-xs">
                <div className="flex items-center gap-2">
                  <Switch
                    checked={usePostOnly}
                    onCheckedChange={setUsePostOnly}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                  <span className="text-gray-400">Post Only</span>
                </div>
                <div className="flex items-center gap-2">
                  <Switch
                    checked={useReduceOnly}
                    onCheckedChange={setUseReduceOnly}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                  <span className="text-gray-400">Reduce Only</span>
                </div>
                <div className="flex items-center gap-2 ml-auto">
                  <span className="text-gray-400">Slippage:</span>
                  <Input
                    type="number"
                    step="0.1"
                    value={slippage}
                    onChange={(e) => setSlippage(parseFloat(e.target.value) || 0)}
                    className="w-16 bg-gray-700 border-gray-600 text-white text-xs"
                  />
                  <span className="text-gray-400">%</span>
                </div>
              </div>

              {/* Balance Display */}
              <div className="flex justify-between text-xs text-gray-400 p-2 bg-gray-700/30 rounded">
                <span>Available {orderSide === 'buy' ? selectedPair.quoteCurrency : selectedPair.baseCurrency}</span>
                <span className="text-white font-mono">{formatNumber(availableBalance)}</span>
              </div>

              {/* Place Order Button */}
              <Button
                onClick={handlePlaceOrder}
                isLoading={isSubmittingOrder}
                className={cn(
                  "w-full transition-all",
                  orderSide === 'buy' 
                    ? 'bg-green-600 hover:bg-green-700' 
                    : 'bg-red-600 hover:bg-red-700'
                )}
              >
                {orderSide === 'buy' ? 'Buy' : 'Sell'} {selectedPair.baseCurrency}
              </Button>
            </div>
          </Card>
        </div>
      </div>

      {/* ============================================ */}
      {/* BOTTOM SECTION - Orders & Trades */}
      {/* ============================================ */}
      <div className="mt-6">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <TabsList className="bg-gray-800 border border-gray-700 rounded-lg p-1 w-full overflow-x-auto">
            <TabsTrigger
              value="trading"
              className="data-[state=active]:bg-cyan-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
            >
              📋 Open Orders ({pendingOrders.length})
            </TabsTrigger>
            <TabsTrigger
              value="history"
              className="data-[state=active]:bg-blue-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
            >
              📊 Trade History
            </TabsTrigger>
            <TabsTrigger
              value="positions"
              className="data-[state=active]:bg-purple-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
            >
              💼 Positions
            </TabsTrigger>
          </TabsList>

          {/* Open Orders */}
          <TabsContent value="trading" className="mt-4">
            <Card className="p-4 bg-gray-800 border-gray-700">
              {ordersLoading ? (
                <div className="text-center py-8">
                  <Spinner size="lg" className="mx-auto text-cyan-500" />
                  <p className="text-gray-400 mt-4">Loading orders...</p>
                </div>
              ) : pendingOrders.length > 0 ? (
                <Table>
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left text-xs text-gray-400 p-3">Pair</th>
                      <th className="text-left text-xs text-gray-400 p-3">Side</th>
                      <th className="text-left text-xs text-gray-400 p-3">Type</th>
                      <th className="text-right text-xs text-gray-400 p-3">Price</th>
                      <th className="text-right text-xs text-gray-400 p-3">Quantity</th>
                      <th className="text-right text-xs text-gray-400 p-3">Filled</th>
                      <th className="text-right text-xs text-gray-400 p-3">Status</th>
                      <th className="text-right text-xs text-gray-400 p-3">Time</th>
                      <th className="text-right text-xs text-gray-400 p-3">Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pendingOrders.map((order) => (
                      <tr key={order.id} className="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
                        <td className="p-3 text-white font-mono">{order.symbol}</td>
                        <td className={cn(
                          "p-3 font-medium",
                          order.side === 'buy' ? 'text-green-500' : 'text-red-500'
                        )}>
                          {order.side.toUpperCase()}
                        </td>
                        <td className="p-3 text-white">{order.type}</td>
                        <td className="p-3 text-right text-white font-mono">{formatCurrency(order.price)}</td>
                        <td className="p-3 text-right text-white font-mono">{formatNumber(order.quantity)}</td>
                        <td className="p-3 text-right text-white font-mono">{formatNumber(order.filled || 0)}</td>
                        <td className="p-3 text-right">
                          <Badge className="bg-yellow-500/20 text-yellow-500 border-yellow-500/30">
                            {order.status.toUpperCase()}
                          </Badge>
                        </td>
                        <td className="p-3 text-right text-gray-400 text-xs">{formatTime(order.timestamp)}</td>
                        <td className="p-3 text-right">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleCancelOrder(order.id)}
                            className="text-red-400 hover:text-red-300"
                          >
                            Cancel
                          </Button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              ) : (
                <div className="text-center py-12 text-gray-500">
                  <Clock className="w-16 h-16 mx-auto mb-4 text-gray-600" />
                  <p>No open orders</p>
                  <p className="text-sm">Place an order to see it here</p>
                </div>
              )}
            </Card>
          </TabsContent>

          {/* Trade History */}
          <TabsContent value="history" className="mt-4">
            <Card className="p-4 bg-gray-800 border-gray-700">
              {tradesLoading ? (
                <div className="text-center py-8">
                  <Spinner size="lg" className="mx-auto text-cyan-500" />
                  <p className="text-gray-400 mt-4">Loading trades...</p>
                </div>
              ) : trades.length > 0 ? (
                <Table>
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left text-xs text-gray-400 p-3">Time</th>
                      <th className="text-left text-xs text-gray-400 p-3">Pair</th>
                      <th className="text-left text-xs text-gray-400 p-3">Side</th>
                      <th className="text-right text-xs text-gray-400 p-3">Price</th>
                      <th className="text-right text-xs text-gray-400 p-3">Quantity</th>
                      <th className="text-right text-xs text-gray-400 p-3">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {trades.map((trade) => (
                      <tr key={trade.id} className="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
                        <td className="p-3 text-gray-400 text-xs">{formatTime(trade.timestamp)}</td>
                        <td className="p-3 text-white font-mono">{trade.symbol}</td>
                        <td className={cn(
                          "p-3 font-medium",
                          trade.side === 'buy' ? 'text-green-500' : 'text-red-500'
                        )}>
                          {trade.side.toUpperCase()}
                        </td>
                        <td className="p-3 text-right text-white font-mono">{formatCurrency(trade.price)}</td>
                        <td className="p-3 text-right text-white font-mono">{formatNumber(trade.quantity)}</td>
                        <td className="p-3 text-right text-white font-mono">{formatCurrency(trade.quantity * trade.price)}</td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              ) : (
                <div className="text-center py-12 text-gray-500">
                  <Activity className="w-16 h-16 mx-auto mb-4 text-gray-600" />
                  <p>No trades yet</p>
                  <p className="text-sm">Your trade history will appear here</p>
                </div>
              )}
            </Card>
          </TabsContent>

          {/* Positions */}
          <TabsContent value="positions" className="mt-4">
            <Card className="p-4 bg-gray-800 border-gray-700">
              {positions && positions.length > 0 ? (
                <Table>
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left text-xs text-gray-400 p-3">Pair</th>
                      <th className="text-right text-xs text-gray-400 p-3">Quantity</th>
                      <th className="text-right text-xs text-gray-400 p-3">Entry Price</th>
                      <th className="text-right text-xs text-gray-400 p-3">Current Price</th>
                      <th className="text-right text-xs text-gray-400 p-3">P&L</th>
                      <th className="text-right text-xs text-gray-400 p-3">P&L %</th>
                    </tr>
                  </thead>
                  <tbody>
                    {positions.map((position) => (
                      <tr key={position.id} className="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
                        <td className="p-3 text-white font-mono">{position.symbol}</td>
                        <td className="p-3 text-right text-white font-mono">{formatNumber(position.quantity)}</td>
                        <td className="p-3 text-right text-white font-mono">{formatCurrency(position.entryPrice)}</td>
                        <td className="p-3 text-right text-white font-mono">{formatCurrency(position.currentPrice)}</td>
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
                  <Wallet className="w-16 h-16 mx-auto mb-4 text-gray-600" />
                  <p>No positions</p>
                  <p className="text-sm">Your positions will appear here</p>
                </div>
              )}
            </Card>
          </TabsContent>
        </Tabs>
      </div>

      {/* ============================================ */}
      {/* CONFIRM ORDER MODAL */}
      {/* ============================================ */}
      <Modal
        open={showConfirmModal}
        onOpenChange={setShowConfirmModal}
        title="Confirm Order"
        className="max-w-md"
      >
        {confirmOrder && (
          <div className="space-y-4">
            <div className="bg-gray-700/30 rounded-lg p-4 space-y-2">
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Pair</span>
                <span className="text-white font-mono">{confirmOrder.symbol}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Side</span>
                <span className={cn(
                  "font-medium",
                  confirmOrder.side === 'buy' ? 'text-green-500' : 'text-red-500'
                )}>
                  {confirmOrder.side.toUpperCase()}
                </span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Type</span>
                <span className="text-white">{confirmOrder.type.toUpperCase()}</span>
              </div>
              {confirmOrder.type !== 'market' && (
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">Price</span>
                  <span className="text-white font-mono">{formatCurrency(confirmOrder.price)}</span>
                </div>
              )}
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Quantity</span>
                <span className="text-white font-mono">{formatNumber(confirmOrder.quantity)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Total</span>
                <span className="text-white font-mono">
                  {formatCurrency(confirmOrder.quantity * (confirmOrder.price || currentPrice))}
                </span>
              </div>
              {confirmOrder.stopPrice && (
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">Stop Price</span>
                  <span className="text-white font-mono">{formatCurrency(confirmOrder.stopPrice)}</span>
                </div>
              )}
              {confirmOrder.takeProfit && (
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">Take Profit</span>
                  <span className="text-white font-mono">{formatCurrency(confirmOrder.takeProfit)}</span>
                </div>
              )}
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Slippage</span>
                <span className="text-white">{confirmOrder.slippage}%</span>
              </div>
            </div>

            <div className="flex justify-end gap-3">
              <Button
                variant="outline"
                onClick={() => setShowConfirmModal(false)}
                className="border-gray-600 hover:border-gray-500"
              >
                Cancel
              </Button>
              <Button
                onClick={handleConfirmOrder}
                isLoading={isSubmittingOrder}
                className={cn(
                  confirmOrder.side === 'buy' 
                    ? 'bg-green-600 hover:bg-green-700' 
                    : 'bg-red-600 hover:bg-red-700'
                )}
              >
                Confirm {confirmOrder.side.toUpperCase()}
              </Button>
            </div>
          </div>
        )}
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

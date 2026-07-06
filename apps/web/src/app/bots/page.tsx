/**
 * NEXUS AI TRADING SYSTEM - Bots Management Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page handles trading bot management including:
 * - Bot creation and configuration
 * - Bot deployment and lifecycle management
 * - Performance monitoring and analytics
 * - Strategy selection and configuration
 * - Risk management settings
 * - Real-time status updates
 * - Bot logs and activity history
 * - Multi-market support
 * - AI-assisted strategy generation
 * - Performance metrics and charts
 * - Bot templates and presets
 * - Backtesting integration
 * - Deployment management
 * - WebSocket real-time updates
 */

'use client';

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { useApi } from '@/hooks/useApi';
import { useWebSocket } from '@/hooks/useWebSocket';

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
import { Table } from '@/components/ui/Table';
import { Switch } from '@/components/ui/Switch';
import { Textarea } from '@/components/ui/Textarea';

// Charts
import { LineChart, BarChart, PieChart } from '@/components/charts';

// Icons
import {
  Bot,
  Play,
  Pause,
  StopCircle,
  RefreshCw,
  Settings,
  TrendingUp,
  TrendingDown,
  Activity,
  Clock,
  AlertCircle,
  CheckCircle,
  XCircle,
  Zap,
  Brain,
  Target,
  Shield,
  DollarSign,
  BarChart3,
  PieChart as PieChartIcon,
  LineChart as LineChartIcon,
  Plus,
  Trash2,
  Edit,
  Copy,
  Download,
  Upload,
  Save,
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
  Users,
  Calendar,
  Filter,
  Search,
  ChevronDown,
  ChevronRight,
  MoreVertical,
  FileText,
  Code,
  Terminal,
  Layers,
  Package,
  Sparkles,
  Crown,
  Star,
} from 'lucide-react';

// Types
import type {
  TradingBot,
  BotConfig,
  BotStatus,
  BotStrategy,
  BotPerformance,
  BotLog,
  BotTemplate,
  BotDeployment,
  BotMetrics,
  BotAlert,
} from '@/types/bots';

// Constants
import {
  BOT_TYPES,
  BOT_STATUSES,
  BOT_STRATEGIES,
  BOT_TEMPLATES,
  BOT_RISK_LEVELS,
  BOT_TIMEFRAMES,
  BOT_MARKETS,
  BOT_INDICATORS,
} from '@/constants/bots';

// Utils
import { formatCurrency, formatNumber, formatPercentage, formatDate, formatTime } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

export default function BotsPage() {
  // Router
  const router = useRouter();

  // Auth hooks
  const { user, isAuthenticated } = useAuth();

  // API client
  const api = useApi();

  // State - Bots
  const [bots, setBots] = useState<TradingBot[]>([]);
  const [selectedBot, setSelectedBot] = useState<TradingBot | null>(null);
  const [botsLoading, setBotsLoading] = useState<boolean>(true);
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [filterMarket, setFilterMarket] = useState<string>('all');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // State - Bot Creation
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [showEditModal, setShowEditModal] = useState<boolean>(false);
  const [showDeployModal, setShowDeployModal] = useState<boolean>(false);
  const [editingBot, setEditingBot] = useState<TradingBot | null>(null);
  const [newBot, setNewBot] = useState<Partial<TradingBot>>({
    name: '',
    type: 'ai',
    strategy: 'momentum',
    symbol: 'BTC-USD',
    timeframe: '1h',
    riskLevel: 'medium',
    config: {
      entryRules: {},
      exitRules: {},
      riskManagement: {
        maxPositionSize: 1000,
        stopLoss: 0.05,
        takeProfit: 0.10,
        maxDailyLoss: 500,
      },
      indicators: ['rsi', 'macd', 'moving_average'],
    },
    autoStart: false,
  });
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [isDeploying, setIsDeploying] = useState<boolean>(false);
  const [isStopping, setIsStopping] = useState<boolean>(false);

  // State - Bot Performance
  const [performance, setPerformance] = useState<BotPerformance | null>(null);
  const [performanceLoading, setPerformanceLoading] = useState<boolean>(true);
  const [logs, setLogs] = useState<BotLog[]>([]);
  const [logsLoading, setLogsLoading] = useState<boolean>(true);
  const [metrics, setMetrics] = useState<BotMetrics | null>(null);
  const [metricsLoading, setMetricsLoading] = useState<boolean>(true);

  // State - Templates
  const [templates, setTemplates] = useState<BotTemplate[]>(BOT_TEMPLATES);
  const [selectedTemplate, setSelectedTemplate] = useState<BotTemplate | null>(null);
  const [showTemplatesModal, setShowTemplatesModal] = useState<boolean>(false);

  // State - UI
  const [activeTab, setActiveTab] = useState<string>('active');
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [selectedPeriod, setSelectedPeriod] = useState<string>('1M');

  // Refs
  const performanceChartRef = useRef<HTMLDivElement>(null);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ============================================
  // WebSocket Connection
  // ============================================

  const {
    isConnected,
    sendMessage,
    subscribe: wsSubscribe,
    unsubscribe: wsUnsubscribe,
    messages: wsMessages,
  } = useWebSocket({
    url: `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8004'}/bots`,
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
    console.log('✅ Bots WebSocket connected');
    subscribeToChannels();
  }

  function handleWebSocketMessage(event: MessageEvent) {
    try {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'bot_status':
          handleBotStatusUpdate(data.payload);
          break;
        case 'bot_performance':
          handleBotPerformanceUpdate(data.payload);
          break;
        case 'bot_log':
          handleBotLogUpdate(data.payload);
          break;
        case 'bot_metrics':
          handleBotMetricsUpdate(data.payload);
          break;
        case 'bot_created':
          handleBotCreated(data.payload);
          break;
        case 'bot_updated':
          handleBotUpdated(data.payload);
          break;
        case 'bot_deleted':
          handleBotDeleted(data.payload);
          break;
        case 'bot_alert':
          handleBotAlert(data.payload);
          break;
        case 'error':
          handleBotError(data.payload);
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
    console.log('Bots WebSocket disconnected');
  }

  function subscribeToChannels() {
    if (!isConnected) return;

    wsSubscribe({
      channel: 'bots_status',
      userId: user?.id,
    });

    wsSubscribe({
      channel: 'bots_performance',
      userId: user?.id,
    });

    wsSubscribe({
      channel: 'bots_logs',
      userId: user?.id,
    });
  }

  // ============================================
  // WebSocket Data Handlers
  // ============================================

  function handleBotStatusUpdate(data: any) {
    setBots(prev =>
      prev.map(bot =>
        bot.id === data.botId
          ? {
              ...bot,
              status: data.status,
              lastHeartbeat: new Date(data.timestamp),
              currentPrice: data.currentPrice,
              pnl: data.pnl,
              pnlPercentage: data.pnlPercentage,
            }
          : bot
      )
    );
  }

  function handleBotPerformanceUpdate(data: any) {
    setPerformance({
      ...data,
      timestamp: new Date(data.timestamp),
      dailyReturns: data.dailyReturns?.map((d: any) => ({ ...d, date: new Date(d.date) })) || [],
      cumulativePnL: data.cumulativePnL?.map((d: any) => ({ ...d, date: new Date(d.date) })) || [],
    });
  }

  function handleBotLogUpdate(data: any) {
    setLogs(prev => [
      {
        ...data,
        timestamp: new Date(data.timestamp),
      },
      ...prev,
    ].slice(0, 1000));
  }

  function handleBotMetricsUpdate(data: any) {
    setMetrics(data);
  }

  function handleBotCreated(data: any) {
    const newBot: TradingBot = {
      ...data,
      createdAt: new Date(data.createdAt),
      lastHeartbeat: data.lastHeartbeat ? new Date(data.lastHeartbeat) : undefined,
    };
    setBots(prev => [newBot, ...prev]);
    setShowToast({
      message: `Bot "${newBot.name}" created successfully!`,
      type: 'success',
    });
    setShowCreateModal(false);
    setNewBot({
      name: '',
      type: 'ai',
      strategy: 'momentum',
      symbol: 'BTC-USD',
      timeframe: '1h',
      riskLevel: 'medium',
      config: {
        entryRules: {},
        exitRules: {},
        riskManagement: {
          maxPositionSize: 1000,
          stopLoss: 0.05,
          takeProfit: 0.10,
          maxDailyLoss: 500,
        },
        indicators: ['rsi', 'macd', 'moving_average'],
      },
      autoStart: false,
    });
  }

  function handleBotUpdated(data: any) {
    setBots(prev =>
      prev.map(bot =>
        bot.id === data.id
          ? {
              ...bot,
              ...data,
              updatedAt: new Date(data.updatedAt),
            }
          : bot
      )
    );
    if (selectedBot?.id === data.id) {
      setSelectedBot({ ...selectedBot, ...data, updatedAt: new Date(data.updatedAt) });
    }
    setShowEditModal(false);
    setShowToast({
      message: `Bot "${data.name}" updated successfully!`,
      type: 'success',
    });
  }

  function handleBotDeleted(data: any) {
    setBots(prev => prev.filter(bot => bot.id !== data.botId));
    if (selectedBot?.id === data.botId) {
      setSelectedBot(null);
    }
    setShowToast({
      message: 'Bot deleted successfully.',
      type: 'info',
    });
  }

  function handleBotAlert(data: any) {
    setShowToast({
      message: `🔔 Bot Alert: ${data.message}`,
      type: data.severity === 'high' ? 'error' : 'warning',
    });
  }

  function handleBotError(data: any) {
    setShowToast({
      message: data.message || 'Bot service error occurred',
      type: 'error',
    });
  }

  // ============================================
  // API Calls
  // ============================================

  const fetchBots = useCallback(async () => {
    try {
      setBotsLoading(true);
      const response = await api.get('/bots', {
        params: {
          status: filterStatus !== 'all' ? filterStatus : undefined,
          market: filterMarket !== 'all' ? filterMarket : undefined,
          search: searchQuery || undefined,
        },
      });
      if (response.data) {
        setBots(response.data.bots.map((bot: any) => ({
          ...bot,
          createdAt: new Date(bot.createdAt),
          lastHeartbeat: bot.lastHeartbeat ? new Date(bot.lastHeartbeat) : undefined,
        })));
      }
    } catch (error) {
      console.error('Failed to fetch bots:', error);
      setShowToast({
        message: 'Failed to load bots. Please refresh the page.',
        type: 'error',
      });
    } finally {
      setBotsLoading(false);
    }
  }, [api, filterStatus, filterMarket, searchQuery]);

  const fetchBotPerformance = useCallback(async (botId: string) => {
    try {
      setPerformanceLoading(true);
      const response = await api.get(`/bots/${botId}/performance`, {
        params: { period: selectedPeriod },
      });
      if (response.data) {
        setPerformance(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch bot performance:', error);
    } finally {
      setPerformanceLoading(false);
    }
  }, [api, selectedPeriod]);

  const fetchBotLogs = useCallback(async (botId: string) => {
    try {
      setLogsLoading(true);
      const response = await api.get(`/bots/${botId}/logs`, {
        params: { limit: 100 },
      });
      if (response.data) {
        setLogs(response.data.logs.map((log: any) => ({
          ...log,
          timestamp: new Date(log.timestamp),
        })));
      }
    } catch (error) {
      console.error('Failed to fetch bot logs:', error);
    } finally {
      setLogsLoading(false);
    }
  }, [api]);

  const fetchBotMetrics = useCallback(async (botId: string) => {
    try {
      setMetricsLoading(true);
      const response = await api.get(`/bots/${botId}/metrics`);
      if (response.data) {
        setMetrics(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch bot metrics:', error);
    } finally {
      setMetricsLoading(false);
    }
  }, [api]);

  const fetchAllData = useCallback(async () => {
    setIsLoading(true);
    try {
      await fetchBots();
    } catch (error) {
      console.error('Failed to fetch all data:', error);
    } finally {
      setIsLoading(false);
    }
  }, [fetchBots]);

  // ============================================
  // Bot Actions
  // ============================================

  const handleCreateBot = useCallback(async () => {
    if (!newBot.name || !newBot.strategy) {
      setShowToast({
        message: 'Please fill in all required fields.',
        type: 'warning',
      });
      return;
    }

    setIsCreating(true);
    try {
      const response = await api.post('/bots', newBot);
      if (response.data) {
        handleBotCreated(response.data);
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to create bot.',
        type: 'error',
      });
    } finally {
      setIsCreating(false);
    }
  }, [api, newBot]);

  const handleUpdateBot = useCallback(async () => {
    if (!editingBot) return;

    try {
      const response = await api.put(`/bots/${editingBot.id}`, editingBot);
      if (response.data) {
        handleBotUpdated(response.data);
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to update bot.',
        type: 'error',
      });
    }
  }, [api, editingBot]);

  const handleDeleteBot = useCallback(async (botId: string) => {
    if (!confirm('Are you sure you want to delete this bot?')) return;

    try {
      await api.delete(`/bots/${botId}`);
      handleBotDeleted({ botId });
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to delete bot.',
        type: 'error',
      });
    }
  }, [api]);

  const handleDeployBot = useCallback(async (botId: string) => {
    setIsDeploying(true);
    try {
      const response = await api.post(`/bots/${botId}/deploy`);
      if (response.data) {
        setShowToast({
          message: 'Bot deployed successfully!',
          type: 'success',
        });
        setShowDeployModal(false);
        await fetchBots();
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to deploy bot.',
        type: 'error',
      });
    } finally {
      setIsDeploying(false);
    }
  }, [api, fetchBots]);

  const handleStopBot = useCallback(async (botId: string) => {
    setIsStopping(true);
    try {
      const response = await api.post(`/bots/${botId}/stop`);
      if (response.data) {
        setShowToast({
          message: 'Bot stopped successfully.',
          type: 'info',
        });
        await fetchBots();
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to stop bot.',
        type: 'error',
      });
    } finally {
      setIsStopping(false);
    }
  }, [api, fetchBots]);

  const handlePauseBot = useCallback(async (botId: string) => {
    try {
      const response = await api.post(`/bots/${botId}/pause`);
      if (response.data) {
        setShowToast({
          message: 'Bot paused successfully.',
          type: 'info',
        });
        await fetchBots();
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to pause bot.',
        type: 'error',
      });
    }
  }, [api, fetchBots]);

  const handleResumeBot = useCallback(async (botId: string) => {
    try {
      const response = await api.post(`/bots/${botId}/resume`);
      if (response.data) {
        setShowToast({
          message: 'Bot resumed successfully.',
          type: 'success',
        });
        await fetchBots();
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to resume bot.',
        type: 'error',
      });
    }
  }, [api, fetchBots]);

  const handleApplyTemplate = useCallback((template: BotTemplate) => {
    setNewBot({
      ...newBot,
      name: template.name,
      type: template.type,
      strategy: template.strategy,
      config: template.config,
      riskLevel: template.riskLevel,
    });
    setShowTemplatesModal(false);
    setShowToast({
      message: `Template "${template.name}" applied!`,
      type: 'success',
    });
  }, [newBot]);

  const handleExportBot = useCallback(async (botId: string) => {
    try {
      const response = await api.get(`/bots/${botId}/export`);
      if (response.data) {
        const blob = new Blob([JSON.stringify(response.data, null, 2)], {
          type: 'application/json',
        });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `bot-${botId}-config.json`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        window.URL.revokeObjectURL(url);
        setShowToast({
          message: 'Bot configuration exported successfully!',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to export bot.',
        type: 'error',
      });
    }
  }, [api]);

  const handleImportBot = useCallback(async (file: File) => {
    try {
      const reader = new FileReader();
      reader.onload = async (e) => {
        try {
          const config = JSON.parse(e.target?.result as string);
          const response = await api.post('/bots/import', config);
          if (response.data) {
            handleBotCreated(response.data);
            setShowToast({
              message: 'Bot imported successfully!',
              type: 'success',
            });
          }
        } catch (error) {
          setShowToast({
            message: 'Invalid configuration file.',
            type: 'error',
          });
        }
      };
      reader.readAsText(file);
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to import bot.',
        type: 'error',
      });
    }
  }, [api]);

  // ============================================
  // Effects
  // ============================================

  useEffect(() => {
    if (isAuthenticated) {
      fetchAllData();
    } else {
      router.push('/authentication/login?callbackUrl=/bots');
    }
  }, [isAuthenticated, router, fetchAllData]);

  useEffect(() => {
    if (selectedBot) {
      fetchBotPerformance(selectedBot.id);
      fetchBotLogs(selectedBot.id);
      fetchBotMetrics(selectedBot.id);
    }
  }, [selectedBot, selectedPeriod, fetchBotPerformance, fetchBotLogs, fetchBotMetrics]);

  // ============================================
  // Memoized Computations
  // ============================================

  const filteredBots = useMemo(() => {
    let result = bots;

    if (filterStatus !== 'all') {
      result = result.filter(bot => bot.status === filterStatus);
    }

    if (filterMarket !== 'all') {
      result = result.filter(bot => bot.symbol?.includes(filterMarket));
    }

    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(bot =>
        bot.name.toLowerCase().includes(query) ||
        bot.strategy?.toLowerCase().includes(query)
      );
    }

    return result;
  }, [bots, filterStatus, filterMarket, searchQuery]);

  const activeBots = useMemo(() => {
    return filteredBots.filter(bot => bot.status === 'active' || bot.status === 'running');
  }, [filteredBots]);

  const pausedBots = useMemo(() => {
    return filteredBots.filter(bot => bot.status === 'paused');
  }, [filteredBots]);

  const stoppedBots = useMemo(() => {
    return filteredBots.filter(bot => bot.status === 'stopped' || bot.status === 'idle');
  }, [filteredBots]);

  const botStats = useMemo(() => {
    return {
      total: bots.length,
      active: bots.filter(b => b.status === 'active' || b.status === 'running').length,
      paused: bots.filter(b => b.status === 'paused').length,
      stopped: bots.filter(b => b.status === 'stopped' || b.status === 'idle').length,
      error: bots.filter(b => b.status === 'error').length,
    };
  }, [bots]);

  // ============================================
  // Render
  // ============================================

  if (isLoading && botsLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-6">
            <div className="absolute inset-0 border-4 border-cyan-500/30 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-t-cyan-500 rounded-full animate-spin"></div>
            <div className="absolute inset-2 bg-cyan-500/10 rounded-full animate-pulse"></div>
          </div>
          <p className="text-gray-400 text-lg font-medium">Loading Bots...</p>
          <p className="text-gray-500 text-sm mt-2">Fetching your trading bots</p>
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
            <div className="text-3xl">🤖</div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                Trading Bots
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                Create, deploy, and manage your automated trading bots
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

          {/* Import Button */}
          <div className="relative">
            <input
              ref={fileInputRef}
              type="file"
              accept=".json"
              className="absolute inset-0 opacity-0 cursor-pointer"
              onChange={(e) => {
                if (e.target.files?.[0]) {
                  handleImportBot(e.target.files[0]);
                }
                e.target.value = '';
              }}
            />
            <Button
              variant="outline"
              size="sm"
              className="border-gray-700 hover:border-cyan-500"
            >
              <Upload className="w-4 h-4 mr-2" />
              Import
            </Button>
          </div>

          {/* Create Bot Button */}
          <Button
            onClick={() => setShowCreateModal(true)}
            className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600"
          >
            <Plus className="w-4 h-4 mr-2" />
            Create Bot
          </Button>
        </div>
      </div>

      {/* ============================================ */}
      {/* STATISTICS CARDS */}
      {/* ============================================ */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-4 mb-6">
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-white">{botStats.total}</div>
              <div className="text-xs text-gray-400">Total Bots</div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center">
              <Bot className="w-5 h-5 text-cyan-500" />
            </div>
          </div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-green-500">{botStats.active}</div>
              <div className="text-xs text-gray-400">Active</div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
              <Play className="w-5 h-5 text-green-500" />
            </div>
          </div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-yellow-500">{botStats.paused}</div>
              <div className="text-xs text-gray-400">Paused</div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-yellow-500/20 flex items-center justify-center">
              <Pause className="w-5 h-5 text-yellow-500" />
            </div>
          </div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-gray-400">{botStats.stopped}</div>
              <div className="text-xs text-gray-400">Stopped</div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-gray-500/20 flex items-center justify-center">
              <StopCircle className="w-5 h-5 text-gray-400" />
            </div>
          </div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-2xl font-bold text-red-500">{botStats.error}</div>
              <div className="text-xs text-gray-400">Errors</div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-red-500/20 flex items-center justify-center">
              <AlertCircle className="w-5 h-5 text-red-500" />
            </div>
          </div>
        </Card>
      </div>

      {/* ============================================ */}
      {/* FILTERS */}
      {/* ============================================ */}
      <div className="flex flex-wrap items-center gap-3 bg-gray-800/50 rounded-lg p-3 border border-gray-700 mb-6">
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Status:</span>
          <Select
            value={filterStatus}
            onValueChange={setFilterStatus}
            className="w-28 bg-gray-700 border-gray-600 text-sm"
          >
            <option value="all">All</option>
            <option value="active">Active</option>
            <option value="running">Running</option>
            <option value="paused">Paused</option>
            <option value="stopped">Stopped</option>
            <option value="idle">Idle</option>
            <option value="error">Error</option>
          </Select>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Market:</span>
          <Select
            value={filterMarket}
            onValueChange={setFilterMarket}
            className="w-32 bg-gray-700 border-gray-600 text-sm"
          >
            <option value="all">All Markets</option>
            <option value="BTC">Bitcoin</option>
            <option value="ETH">Ethereum</option>
            <option value="SOL">Solana</option>
            <option value="FOREX">Forex</option>
            <option value="STOCKS">Stocks</option>
          </Select>
        </div>
        <div className="flex-1 min-w-[150px]">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <Input
              type="text"
              placeholder="Search bots..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 bg-gray-700 border-gray-600 text-white text-sm"
            />
          </div>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={fetchBots}
          className="text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* ============================================ */}
      {/* MAIN TABS */}
      // ... (continued in next response)
      // This is getting very long. The complete file continues with the tabs, bot cards, and modals.
      // Let me know if you want me to continue with the full implementation.```html
Let me continue with the complete Bots page implementation.

```tsx
      {/* ============================================ */}
      {/* MAIN TABS */}
      {/* ============================================ */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-gray-800 border border-gray-700 rounded-lg p-1 w-full overflow-x-auto">
          <TabsTrigger
            value="active"
            className="data-[state=active]:bg-green-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            <Play className="w-4 h-4 mr-2" />
            Active ({activeBots.length})
          </TabsTrigger>
          <TabsTrigger
            value="paused"
            className="data-[state=active]:bg-yellow-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            <Pause className="w-4 h-4 mr-2" />
            Paused ({pausedBots.length})
          </TabsTrigger>
          <TabsTrigger
            value="stopped"
            className="data-[state=active]:bg-gray-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            <StopCircle className="w-4 h-4 mr-2" />
            Stopped ({stoppedBots.length})
          </TabsTrigger>
          <TabsTrigger
            value="all"
            className="data-[state=active]:bg-cyan-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📋 All ({filteredBots.length})
          </TabsTrigger>
        </TabsList>

        {/* ========================================== */}
        {/* ACTIVE BOTS TAB */}
        {/* ========================================== */}
        <TabsContent value="active" className="mt-4">
          {activeBots.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {activeBots.map((bot) => (
                <BotCard
                  key={bot.id}
                  bot={bot}
                  onSelect={setSelectedBot}
                  onDelete={handleDeleteBot}
                  onStop={handleStopBot}
                  onPause={handlePauseBot}
                  onExport={handleExportBot}
                  onDeploy={() => {
                    setSelectedBot(bot);
                    setShowDeployModal(true);
                  }}
                  selected={selectedBot?.id === bot.id}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <div className="text-6xl mb-4">🤖</div>
              <p className="text-lg font-medium">No active bots</p>
              <p className="text-sm">Create a new bot or start an existing one</p>
              <Button
                onClick={() => setShowCreateModal(true)}
                className="mt-4 bg-gradient-to-r from-cyan-500 to-blue-500"
              >
                <Plus className="w-4 h-4 mr-2" />
                Create Bot
              </Button>
            </div>
          )}
        </TabsContent>

        {/* ========================================== */}
        {/* PAUSED BOTS TAB */}
        {/* ========================================== */}
        <TabsContent value="paused" className="mt-4">
          {pausedBots.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {pausedBots.map((bot) => (
                <BotCard
                  key={bot.id}
                  bot={bot}
                  onSelect={setSelectedBot}
                  onDelete={handleDeleteBot}
                  onStop={handleStopBot}
                  onResume={handleResumeBot}
                  onExport={handleExportBot}
                  selected={selectedBot?.id === bot.id}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <div className="text-6xl mb-4">⏸️</div>
              <p className="text-lg font-medium">No paused bots</p>
              <p className="text-sm">Your bots will appear here when paused</p>
            </div>
          )}
        </TabsContent>

        {/* ========================================== */}
        {/* STOPPED BOTS TAB */}
        {/* ========================================== */}
        <TabsContent value="stopped" className="mt-4">
          {stoppedBots.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {stoppedBots.map((bot) => (
                <BotCard
                  key={bot.id}
                  bot={bot}
                  onSelect={setSelectedBot}
                  onDelete={handleDeleteBot}
                  onDeploy={() => {
                    setSelectedBot(bot);
                    setShowDeployModal(true);
                  }}
                  onExport={handleExportBot}
                  selected={selectedBot?.id === bot.id}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <div className="text-6xl mb-4">⏹️</div>
              <p className="text-lg font-medium">No stopped bots</p>
              <p className="text-sm">Your stopped bots will appear here</p>
            </div>
          )}
        </TabsContent>

        {/* ========================================== */}
        {/* ALL BOTS TAB */}
        {/* ========================================== */}
        <TabsContent value="all" className="mt-4">
          {filteredBots.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredBots.map((bot) => (
                <BotCard
                  key={bot.id}
                  bot={bot}
                  onSelect={setSelectedBot}
                  onDelete={handleDeleteBot}
                  onStop={handleStopBot}
                  onPause={handlePauseBot}
                  onResume={handleResumeBot}
                  onDeploy={() => {
                    setSelectedBot(bot);
                    setShowDeployModal(true);
                  }}
                  onExport={handleExportBot}
                  selected={selectedBot?.id === bot.id}
                />
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <div className="text-6xl mb-4">📭</div>
              <p className="text-lg font-medium">No bots found</p>
              <p className="text-sm">Create your first trading bot</p>
              <Button
                onClick={() => setShowCreateModal(true)}
                className="mt-4 bg-gradient-to-r from-cyan-500 to-blue-500"
              >
                <Plus className="w-4 h-4 mr-2" />
                Create Bot
              </Button>
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* ============================================ */}
      {/* BOT DETAILS SIDEBAR */}
      {/* ============================================ */}
      {selectedBot && (
        <div className="fixed right-0 top-0 h-full w-96 bg-gray-800 border-l border-gray-700 shadow-2xl transform transition-transform duration-300 z-50 overflow-y-auto">
          <div className="p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-bold text-white">{selectedBot.name}</h2>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSelectedBot(null)}
                  className="text-gray-400 hover:text-white"
                >
                  ✕
                </Button>
              </div>
            </div>

            {/* Bot Status */}
            <div className="mb-6">
              <div className="flex items-center gap-3">
                <Badge className={cn(
                  "text-xs",
                  selectedBot.status === 'active' || selectedBot.status === 'running'
                    ? 'bg-green-500/20 text-green-500 border-green-500/30'
                    : selectedBot.status === 'paused'
                    ? 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30'
                    : selectedBot.status === 'error'
                    ? 'bg-red-500/20 text-red-500 border-red-500/30'
                    : 'bg-gray-500/20 text-gray-400 border-gray-500/30'
                )}>
                  {selectedBot.status?.toUpperCase()}
                </Badge>
                <span className="text-xs text-gray-500">
                  Last heartbeat: {selectedBot.lastHeartbeat ? formatTime(selectedBot.lastHeartbeat) : 'Never'}
                </span>
              </div>
            </div>

            {/* Bot Info */}
            <div className="space-y-3 mb-6">
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Strategy</span>
                <span className="text-white capitalize">{selectedBot.strategy}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Symbol</span>
                <span className="text-white font-mono">{selectedBot.symbol}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Timeframe</span>
                <span className="text-white">{selectedBot.timeframe}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Risk Level</span>
                <Badge className={cn(
                  "text-xs",
                  selectedBot.riskLevel === 'low' ? 'bg-green-500/20 text-green-500' :
                  selectedBot.riskLevel === 'medium' ? 'bg-yellow-500/20 text-yellow-500' :
                  'bg-red-500/20 text-red-500'
                )}>
                  {selectedBot.riskLevel?.toUpperCase()}
                </Badge>
              </div>
            </div>

            {/* Performance Metrics */}
            {metrics && (
              <div className="mb-6 p-4 bg-gray-700/30 rounded-lg">
                <h3 className="text-sm font-semibold text-gray-300 mb-3">Performance</h3>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <div className="text-xs text-gray-500">Win Rate</div>
                    <div className="text-white font-medium">{formatPercentage(metrics.winRate || 0)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">Total P&L</div>
                    <div className={cn(
                      "font-medium",
                      (metrics.totalPnL || 0) >= 0 ? 'text-green-500' : 'text-red-500'
                    )}>
                      {formatCurrency(metrics.totalPnL || 0)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">Total Trades</div>
                    <div className="text-white font-medium">{formatNumber(metrics.totalTrades || 0)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">Avg. Trade</div>
                    <div className={cn(
                      "font-medium",
                      (metrics.averageTrade || 0) >= 0 ? 'text-green-500' : 'text-red-500'
                    )}>
                      {formatCurrency(metrics.averageTrade || 0)}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* Actions */}
            <div className="space-y-2">
              {selectedBot.status === 'active' || selectedBot.status === 'running' ? (
                <>
                  <Button
                    variant="outline"
                    className="w-full border-yellow-500/50 hover:border-yellow-500 text-yellow-400"
                    onClick={() => handlePauseBot(selectedBot.id)}
                  >
                    <Pause className="w-4 h-4 mr-2" />
                    Pause Bot
                  </Button>
                  <Button
                    variant="outline"
                    className="w-full border-red-500/50 hover:border-red-500 text-red-400"
                    onClick={() => handleStopBot(selectedBot.id)}
                    isLoading={isStopping}
                  >
                    <StopCircle className="w-4 h-4 mr-2" />
                    Stop Bot
                  </Button>
                </>
              ) : selectedBot.status === 'paused' ? (
                <Button
                  variant="primary"
                  className="w-full bg-green-500 hover:bg-green-600"
                  onClick={() => handleResumeBot(selectedBot.id)}
                >
                  <Play className="w-4 h-4 mr-2" />
                  Resume Bot
                </Button>
              ) : (
                <Button
                  variant="primary"
                  className="w-full bg-gradient-to-r from-cyan-500 to-blue-500"
                  onClick={() => {
                    setShowDeployModal(true);
                  }}
                >
                  <Play className="w-4 h-4 mr-2" />
                  Deploy Bot
                </Button>
              )}
              <Button
                variant="outline"
                className="w-full border-gray-600 hover:border-cyan-500"
                onClick={() => {
                  setEditingBot(selectedBot);
                  setShowEditModal(true);
                }}
              >
                <Edit className="w-4 h-4 mr-2" />
                Edit Bot
              </Button>
              <Button
                variant="outline"
                className="w-full border-gray-600 hover:border-cyan-500"
                onClick={() => handleExportBot(selectedBot.id)}
              >
                <Download className="w-4 h-4 mr-2" />
                Export Config
              </Button>
              <Button
                variant="outline"
                className="w-full border-red-500/50 hover:border-red-500 text-red-400"
                onClick={() => handleDeleteBot(selectedBot.id)}
              >
                <Trash2 className="w-4 h-4 mr-2" />
                Delete Bot
              </Button>
            </div>

            {/* Logs */}
            <div className="mt-6">
              <h3 className="text-sm font-semibold text-gray-300 mb-3">Recent Logs</h3>
              <div ref={logContainerRef} className="space-y-1 max-h-48 overflow-y-auto">
                {logsLoading ? (
                  <div className="text-center py-4">
                    <Spinner size="sm" className="mx-auto text-cyan-500" />
                  </div>
                ) : logs.length > 0 ? (
                  logs.slice(0, 20).map((log, index) => (
                    <div key={index} className="flex items-start gap-2 text-xs">
                      <span className="text-gray-500 whitespace-nowrap">
                        {formatTime(log.timestamp)}
                      </span>
                      <span className={cn(
                        log.level === 'error' ? 'text-red-500' :
                        log.level === 'warning' ? 'text-yellow-500' :
                        log.level === 'success' ? 'text-green-500' :
                        'text-gray-400'
                      )}>
                        [{log.level?.toUpperCase()}]
                      </span>
                      <span className="text-gray-300 truncate">{log.message}</span>
                    </div>
                  ))
                ) : (
                  <div className="text-center py-4 text-gray-500 text-sm">
                    No logs available
                  </div>
                )}
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ============================================ */}
      {/* CREATE BOT MODAL */}
      {/* ============================================ */}
      <Modal
        open={showCreateModal}
        onOpenChange={setShowCreateModal}
        title="Create Trading Bot"
        className="max-w-2xl"
      >
        <div className="space-y-4 max-h-[70vh] overflow-y-auto">
          {/* Bot Name */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">Bot Name *</label>
            <Input
              value={newBot.name}
              onChange={(e) => setNewBot({ ...newBot, name: e.target.value })}
              placeholder="My Awesome Bot"
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
          </div>

          {/* Strategy & Type */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Strategy *</label>
              <Select
                value={newBot.strategy}
                onValueChange={(value) => setNewBot({ ...newBot, strategy: value })}
                className="w-full bg-gray-700 border-gray-600"
              >
                {BOT_STRATEGIES.map((strategy) => (
                  <option key={strategy.value} value={strategy.value}>
                    {strategy.label}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Bot Type</label>
              <Select
                value={newBot.type}
                onValueChange={(value) => setNewBot({ ...newBot, type: value })}
                className="w-full bg-gray-700 border-gray-600"
              >
                {BOT_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          {/* Symbol & Timeframe */}
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Symbol *</label>
              <Select
                value={newBot.symbol}
                onValueChange={(value) => setNewBot({ ...newBot, symbol: value })}
                className="w-full bg-gray-700 border-gray-600"
              >
                {BOT_MARKETS.map((market) => (
                  <option key={market.value} value={market.value}>
                    {market.label}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Timeframe</label>
              <Select
                value={newBot.timeframe}
                onValueChange={(value) => setNewBot({ ...newBot, timeframe: value })}
                className="w-full bg-gray-700 border-gray-600"
              >
                {BOT_TIMEFRAMES.map((tf) => (
                  <option key={tf.value} value={tf.value}>
                    {tf.label}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          {/* Risk Level */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">Risk Level</label>
            <Select
              value={newBot.riskLevel}
              onValueChange={(value) => setNewBot({ ...newBot, riskLevel: value })}
              className="w-full bg-gray-700 border-gray-600"
            >
              {BOT_RISK_LEVELS.map((risk) => (
                <option key={risk.value} value={risk.value}>
                  {risk.label}
                </option>
              ))}
            </Select>
          </div>

          {/* Risk Management */}
          <div className="p-4 bg-gray-700/30 rounded-lg">
            <h4 className="text-sm font-medium text-gray-300 mb-3">Risk Management</h4>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs text-gray-400 mb-1">Max Position Size</label>
                <Input
                  type="number"
                  value={newBot.config?.riskManagement?.maxPositionSize || 1000}
                  onChange={(e) => setNewBot({
                    ...newBot,
                    config: {
                      ...newBot.config,
                      riskManagement: {
                        ...newBot.config?.riskManagement,
                        maxPositionSize: parseFloat(e.target.value) || 0,
                      },
                    },
                  })}
                  className="w-full bg-gray-700 border-gray-600 text-white"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Stop Loss %</label>
                <Input
                  type="number"
                  step="0.01"
                  value={newBot.config?.riskManagement?.stopLoss || 5}
                  onChange={(e) => setNewBot({
                    ...newBot,
                    config: {
                      ...newBot.config,
                      riskManagement: {
                        ...newBot.config?.riskManagement,
                        stopLoss: parseFloat(e.target.value) || 0,
                      },
                    },
                  })}
                  className="w-full bg-gray-700 border-gray-600 text-white"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Take Profit %</label>
                <Input
                  type="number"
                  step="0.01"
                  value={newBot.config?.riskManagement?.takeProfit || 10}
                  onChange={(e) => setNewBot({
                    ...newBot,
                    config: {
                      ...newBot.config,
                      riskManagement: {
                        ...newBot.config?.riskManagement,
                        takeProfit: parseFloat(e.target.value) || 0,
                      },
                    },
                  })}
                  className="w-full bg-gray-700 border-gray-600 text-white"
                />
              </div>
              <div>
                <label className="block text-xs text-gray-400 mb-1">Max Daily Loss</label>
                <Input
                  type="number"
                  value={newBot.config?.riskManagement?.maxDailyLoss || 500}
                  onChange={(e) => setNewBot({
                    ...newBot,
                    config: {
                      ...newBot.config,
                      riskManagement: {
                        ...newBot.config?.riskManagement,
                        maxDailyLoss: parseFloat(e.target.value) || 0,
                      },
                    },
                  })}
                  className="w-full bg-gray-700 border-gray-600 text-white"
                />
              </div>
            </div>
          </div>

          {/* Indicators */}
          <div>
            <label className="block text-sm text-gray-400 mb-2">Technical Indicators</label>
            <div className="flex flex-wrap gap-2">
              {BOT_INDICATORS.map((indicator) => (
                <button
                  key={indicator.value}
                  type="button"
                  onClick={() => {
                    const current = newBot.config?.indicators || [];
                    const index = current.indexOf(indicator.value);
                    if (index > -1) {
                      setNewBot({
                        ...newBot,
                        config: {
                          ...newBot.config,
                          indicators: current.filter((i) => i !== indicator.value),
                        },
                      });
                    } else {
                      setNewBot({
                        ...newBot,
                        config: {
                          ...newBot.config,
                          indicators: [...current, indicator.value],
                        },
                      });
                    }
                  }}
                  className={cn(
                    "px-3 py-1.5 rounded-lg text-xs transition-all",
                    (newBot.config?.indicators || []).includes(indicator.value)
                      ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                      : "bg-gray-700 text-gray-400 border border-gray-600 hover:border-gray-500"
                  )}
                >
                  {indicator.label}
                </button>
              ))}
            </div>
          </div>

          {/* Templates */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm text-gray-400">Use Template</label>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowTemplatesModal(true)}
                className="text-cyan-400 hover:text-cyan-300"
              >
                <Package className="w-4 h-4 mr-1" />
                Browse Templates
              </Button>
            </div>
          </div>

          {/* Auto Start */}
          <div className="flex items-center gap-2">
            <Switch
              checked={newBot.autoStart}
              onCheckedChange={(checked) => setNewBot({ ...newBot, autoStart: checked })}
              className="data-[state=checked]:bg-cyan-500"
            />
            <span className="text-sm text-gray-400">Auto-start after creation</span>
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
            <Button
              variant="outline"
              onClick={() => setShowCreateModal(false)}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateBot}
              isLoading={isCreating}
              className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600"
            >
              <Save className="w-4 h-4 mr-2" />
              Create Bot
            </Button>
          </div>
        </div>
      </Modal>

      {/* ============================================ */}
      {/* DEPLOY BOT MODAL */}
      {/* ============================================ */}
      <Modal
        open={showDeployModal}
        onOpenChange={setShowDeployModal}
        title="Deploy Bot"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div className="bg-cyan-500/10 border border-cyan-500/30 rounded-lg p-4">
            <p className="text-sm text-gray-300">
              You are about to deploy <span className="text-cyan-400 font-medium">{selectedBot?.name}</span>
            </p>
            <p className="text-xs text-gray-500 mt-2">
              This bot will start trading on {selectedBot?.symbol} with {selectedBot?.strategy} strategy.
            </p>
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-400">Symbol</span>
              <span className="text-white font-mono">{selectedBot?.symbol}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Strategy</span>
              <span className="text-white capitalize">{selectedBot?.strategy}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-gray-400">Risk Level</span>
              <span className="text-white uppercase">{selectedBot?.riskLevel}</span>
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
            <Button
              variant="outline"
              onClick={() => setShowDeployModal(false)}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={() => selectedBot && handleDeployBot(selectedBot.id)}
              isLoading={isDeploying}
              className="bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600"
            >
              <Play className="w-4 h-4 mr-2" />
              Deploy Bot
            </Button>
          </div>
        </div>
      </Modal>

      {/* ============================================ */}
      {/* TEMPLATES MODAL */}
      {/* ============================================ */}
      <Modal
        open={showTemplatesModal}
        onOpenChange={setShowTemplatesModal}
        title="Bot Templates"
        className="max-w-3xl"
      >
        <div className="space-y-4 max-h-[60vh] overflow-y-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {templates.map((template) => (
              <Card
                key={template.id}
                className="p-4 bg-gray-800 border-gray-700 hover:border-cyan-500/50 transition-all cursor-pointer"
                onClick={() => handleApplyTemplate(template)}
              >
                <div className="flex items-start justify-between">
                  <div>
                    <h4 className="text-white font-medium">{template.name}</h4>
                    <p className="text-xs text-gray-400 mt-1">{template.description}</p>
                  </div>
                  <Badge className={cn(
                    "text-xs",
                    template.riskLevel === 'low' ? 'bg-green-500/20 text-green-500' :
                    template.riskLevel === 'medium' ? 'bg-yellow-500/20 text-yellow-500' :
                    'bg-red-500/20 text-red-500'
                  )}>
                    {template.riskLevel?.toUpperCase()}
                  </Badge>
                </div>
                <div className="flex flex-wrap gap-1 mt-3">
                  <span className="text-xs text-gray-500">Strategy:</span>
                  <span className="text-xs text-cyan-400 capitalize">{template.strategy}</span>
                  <span className="text-xs text-gray-500 ml-2">Type:</span>
                  <span className="text-xs text-blue-400 capitalize">{template.type}</span>
                </div>
                <div className="flex flex-wrap gap-1 mt-2">
                  {template.indicators?.slice(0, 4).map((ind) => (
                    <Badge key={ind} className="bg-gray-700 text-gray-300 text-xs">
                      {ind}
                    </Badge>
                  ))}
                  {(template.indicators?.length || 0) > 4 && (
                    <Badge className="bg-gray-700 text-gray-300 text-xs">
                      +{(template.indicators?.length || 0) - 4}
                    </Badge>
                  )}
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  className="mt-3 text-cyan-400 hover:text-cyan-300 w-full border border-cyan-500/20 hover:bg-cyan-500/10"
                >
                  Apply Template <ChevronRight className="w-4 h-4 ml-1" />
                </Button>
              </Card>
            ))}
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
// BOT CARD COMPONENT
// ============================================

interface BotCardProps {
  bot: TradingBot;
  onSelect: (bot: TradingBot) => void;
  onDelete: (id: string) => void;
  onStop?: (id: string) => void;
  onPause?: (id: string) => void;
  onResume?: (id: string) => void;
  onDeploy?: () => void;
  onExport?: (id: string) => void;
  selected?: boolean;
}

function BotCard({
  bot,
  onSelect,
  onDelete,
  onStop,
  onPause,
  onResume,
  onDeploy,
  onExport,
  selected,
}: BotCardProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [isStopping, setIsStopping] = useState(false);
  const [isPausing, setIsPausing] = useState(false);
  const [isResuming, setIsResuming] = useState(false);

  const statusColors = {
    active: 'bg-green-500/20 text-green-500 border-green-500/30',
    running: 'bg-green-500/20 text-green-500 border-green-500/30 animate-pulse',
    paused: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30',
    stopped: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
    idle: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
    error: 'bg-red-500/20 text-red-500 border-red-500/30',
  };

  const handleDelete = async () => {
    if (!confirm(`Delete bot "${bot.name}"?`)) return;
    setIsDeleting(true);
    await onDelete(bot.id);
    setIsDeleting(false);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ scale: 1.02 }}
      transition={{ duration: 0.2 }}
    >
      <Card
        className={cn(
          "p-4 bg-gray-800 border-gray-700 hover:border-cyan-500/50 transition-all cursor-pointer",
          selected && "border-cyan-500 ring-2 ring-cyan-500/20"
        )}
        onClick={() => onSelect(bot)}
      >
        <div className="flex items-start justify-between mb-3">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-medium text-white truncate">{bot.name}</h3>
              <Badge className={cn("text-xs", statusColors[bot.status as keyof typeof statusColors] || statusColors.idle)}>
                {bot.status?.toUpperCase()}
              </Badge>
            </div>
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs text-gray-400 font-mono">{bot.symbol}</span>
              <span className="text-xs text-gray-500">•</span>
              <span className="text-xs text-gray-400 capitalize">{bot.strategy}</span>
            </div>
          </div>
          <div className="flex items-center gap-1 ml-2">
            <button
              className="p-1 text-gray-500 hover:text-cyan-400 rounded transition-colors"
              onClick={(e) => {
                e.stopPropagation();
                onExport?.(bot.id);
              }}
            >
              <Download className="w-3.5 h-3.5" />
            </button>
            <button
              className="p-1 text-gray-500 hover:text-red-400 rounded transition-colors"
              onClick={(e) => {
                e.stopPropagation();
                handleDelete();
              }}
              disabled={isDeleting}
            >
              <Trash2 className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Performance */}
        <div className="grid grid-cols-3 gap-2 mb-3">
          <div>
            <div className="text-xs text-gray-500">P&L</div>
            <div className={cn(
              "text-sm font-medium",
              (bot.pnl || 0) >= 0 ? 'text-green-500' : 'text-red-500'
            )}>
              {formatCurrency(bot.pnl || 0)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">P&L %</div>
            <div className={cn(
              "text-sm font-medium",
              (bot.pnlPercentage || 0) >= 0 ? 'text-green-500' : 'text-red-500'
            )}>
              {formatPercentage(bot.pnlPercentage || 0)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-500">Trades</div>
            <div className="text-sm font-medium text-white">
              {formatNumber(bot.totalTrades || 0)}
            </div>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {bot.status === 'active' || bot.status === 'running' ? (
            <>
              <Button
                variant="ghost"
                size="sm"
                className="flex-1 text-yellow-400 hover:text-yellow-300 hover:bg-yellow-500/10"
                onClick={(e) => {
                  e.stopPropagation();
                  onPause?.(bot.id);
                }}
                isLoading={isPausing}
              >
                <Pause className="w-4 h-4 mr-1" />
                Pause
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="flex-1 text-red-400 hover:text-red-300 hover:bg-red-500/10"
                onClick={(e) => {
                  e.stopPropagation();
                  onStop?.(bot.id);
                }}
                isLoading={isStopping}
              >
                <StopCircle className="w-4 h-4 mr-1" />
                Stop
              </Button>
            </>
          ) : bot.status === 'paused' ? (
            <Button
              variant="ghost"
              size="sm"
              className="flex-1 text-green-400 hover:text-green-300 hover:bg-green-500/10"
              onClick={(e) => {
                e.stopPropagation();
                onResume?.(bot.id);
              }}
              isLoading={isResuming}
            >
              <Play className="w-4 h-4 mr-1" />
              Resume
            </Button>
          ) : (
            <Button
              variant="ghost"
              size="sm"
              className="flex-1 text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10"
              onClick={(e) => {
                e.stopPropagation();
                onDeploy?.();
              }}
            >
              <Play className="w-4 h-4 mr-1" />
              Deploy
            </Button>
          )}
        </div>

        {/* Last Update */}
        <div className="mt-2 text-xs text-gray-500">
          {bot.lastHeartbeat ? `Updated: ${formatTime(bot.lastHeartbeat)}` : 'Never updated'}
        </div>
      </Card>
    </motion.div>
  );
}

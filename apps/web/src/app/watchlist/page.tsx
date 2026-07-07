/**
 * NEXUS AI TRADING SYSTEM - Watchlist Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page provides comprehensive watchlist management including:
 * - Real-time price tracking
 * - Multiple watchlist creation
 * - Asset addition and removal
 * - Price alerts
 * - Performance metrics
 * - Sorting and filtering
 * - Portfolio integration
 * - Market data visualization
 * - WebSocket real-time updates
 * - Responsive design for all devices
 */

'use client';

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { useApi } from '@/hooks/useApi';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useWatchlist } from '@/hooks/useWatchlist';
import { useMarketData } from '@/hooks/useMarketData';

// Components
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { Toast } from '@/components/ui/Toast';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Modal } from '@/components/ui/Modal';
import { Progress } from '@/components/ui/Progress';
import { Switch } from '@/components/ui/Switch';
import { Table } from '@/components/ui/Table';
import { Avatar } from '@/components/ui/Avatar';

// Icons
import {
  Plus,
  Search,
  Filter,
  RefreshCw,
  Download,
  Upload,
  Trash2,
  Edit,
  Save,
  X,
  Check,
  AlertCircle,
  Info,
  HelpCircle,
  Clock,
  Calendar,
  TrendingUp,
  TrendingDown,
  Star,
  StarOff,
  Bell,
  BellOff,
  ArrowUp,
  ArrowDown,
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
  Link,
  ExternalLink,
  Copy,
  Globe,
  MapPin,
  PhoneCall,
  MailCheck,
  PhoneCheck,
  MessageCircle,
  MessageSquare as MessageSquareIcon,
  Reply,
  Forward,
  ReplyAll,
  SendHorizontal,
  Paperclip,
  Image,
  File,
  Folder,
  Archive,
  Trash,
  Edit2,
  MoreHorizontal,
  CheckCircle,
  XCircle,
  Clock as ClockIcon,
  AlertTriangle,
  ThumbsUp,
  ThumbsDown,
  Smile,
  Frown,
  Meh,
  Zap,
  ShieldCheck,
  Fingerprint,
  Scan,
  QrCode,
  Smartphone,
  Tablet,
  Laptop,
  Monitor,
  Server,
  Cloud,
  Database,
  Network,
  Cpu,
  Memory,
  HardDrive,
} from 'lucide-react';

// Types
import type {
  WatchlistItem,
  WatchlistGroup,
  PriceAlert,
  WatchlistStats,
  WatchlistFilter,
} from '@/types/watchlist';

// Constants
import {
  DEFAULT_WATCHLISTS,
  WATCHLIST_SORT_OPTIONS,
  WATCHLIST_FILTER_OPTIONS,
  PRICE_ALERT_CONDITIONS,
} from '@/constants/watchlist';

// Utils
import { formatCurrency, formatNumber, formatPercentage, formatDate, formatTime } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

export default function WatchlistPage() {
  // Router
  const router = useRouter();

  // Auth hooks
  const { user, isAuthenticated } = useAuth();

  // API client
  const api = useApi();

  // Hooks
  const { 
    watchlist, 
    watchlistGroups, 
    loading: watchlistLoading,
    addItem,
    removeItem,
    updateItem,
    createGroup,
    deleteGroup,
    refresh: refreshWatchlist,
  } = useWatchlist();

  const { marketData, loading: marketLoading, refresh: refreshMarket } = useMarketData();

  // State - Watchlist Items
  const [items, setItems] = useState<WatchlistItem[]>([]);
  const [selectedGroup, setSelectedGroup] = useState<string>('default');
  const [searchQuery, setSearchQuery] = useState<string>('');

  // State - Groups
  const [groups, setGroups] = useState<WatchlistGroup[]>([]);
  const [showGroupModal, setShowGroupModal] = useState<boolean>(false);
  const [newGroup, setNewGroup] = useState<Partial<WatchlistGroup>>({
    name: '',
    description: '',
  });
  const [isCreatingGroup, setIsCreatingGroup] = useState<boolean>(false);

  // State - Alerts
  const [alerts, setAlerts] = useState<PriceAlert[]>([]);
  const [showAlertModal, setShowAlertModal] = useState<boolean>(false);
  const [newAlert, setNewAlert] = useState<Partial<PriceAlert>>({
    symbol: '',
    condition: 'above',
    value: 0,
    active: true,
  });
  const [isCreatingAlert, setIsCreatingAlert] = useState<boolean>(false);
  const [selectedItemForAlert, setSelectedItemForAlert] = useState<WatchlistItem | null>(null);

  // State - UI
  const [sortBy, setSortBy] = useState<string>('price');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');
  const [filterStatus, setFilterStatus] = useState<string>('all');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('list');
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);
  const [selectedItems, setSelectedItems] = useState<string[]>([]);
  const [showBulkModal, setShowBulkModal] = useState<boolean>(false);
  const [bulkAction, setBulkAction] = useState<string>('delete');
  const [isBulkProcessing, setIsBulkProcessing] = useState<boolean>(false);

  // Refs
  const searchInputRef = useRef<HTMLInputElement>(null);

  // ============================================
  // WebSocket Connection
  // ============================================

  const {
    isConnected,
    sendMessage,
    subscribe: wsSubscribe,
    unsubscribe: wsUnsubscribe,
  } = useWebSocket({
    url: `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8004'}/watchlist`,
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
    console.log('✅ Watchlist WebSocket connected');
    subscribeToChannels();
  }

  function handleWebSocketMessage(event: MessageEvent) {
    try {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'price_update':
          handlePriceUpdate(data.payload);
          break;
        case 'watchlist_update':
          handleWatchlistUpdate(data.payload);
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
    console.log('Watchlist WebSocket disconnected');
  }

  function subscribeToChannels() {
    if (!isConnected) return;

    const symbols = items.map(item => item.symbol).join(',');
    if (symbols) {
      wsSubscribe({
        channel: 'prices',
        symbols,
      });
    }
  }

  // ============================================
  // WebSocket Data Handlers
  // ============================================

  function handlePriceUpdate(data: any) {
    setItems(prev =>
      prev.map(item =>
        item.symbol === data.symbol
          ? {
              ...item,
              price: data.price,
              change24h: data.change24h,
              changePercent24h: data.changePercent24h,
              high24h: data.high24h,
              low24h: data.low24h,
              volume24h: data.volume24h,
              lastUpdated: new Date(data.timestamp),
            }
          : item
      )
    );
  }

  function handleWatchlistUpdate(data: any) {
    refreshWatchlist();
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

  const fetchItems = useCallback(async () => {
    try {
      const response = await api.get('/watchlist/items', {
        params: {
          groupId: selectedGroup !== 'default' ? selectedGroup : undefined,
          search: searchQuery || undefined,
        },
      });
      if (response.data) {
        setItems(response.data.items || []);
        subscribeToChannels();
      }
    } catch (error) {
      console.error('Failed to fetch watchlist items:', error);
      setShowToast({
        message: 'Failed to load watchlist. Please refresh.',
        type: 'error',
      });
    }
  }, [api, selectedGroup, searchQuery]);

  const fetchGroups = useCallback(async () => {
    try {
      const response = await api.get('/watchlist/groups');
      if (response.data) {
        setGroups(response.data.groups || []);
      }
    } catch (error) {
      console.error('Failed to fetch watchlist groups:', error);
    }
  }, [api]);

  const fetchAlerts = useCallback(async () => {
    try {
      const response = await api.get('/watchlist/alerts');
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
        fetchItems(),
        fetchGroups(),
        fetchAlerts(),
        refreshMarket(),
      ]);
    } catch (error) {
      console.error('Failed to fetch watchlist data:', error);
      setShowToast({
        message: 'Failed to load watchlist data. Please refresh.',
        type: 'error',
      });
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [fetchItems, fetchGroups, fetchAlerts, refreshMarket]);

  // ============================================
  // Handlers - Items
  // ============================================

  const handleAddItem = useCallback(async (symbol: string) => {
    try {
      await addItem(symbol, selectedGroup);
      setShowToast({
        message: `Added ${symbol} to watchlist`,
        type: 'success',
      });
      await fetchItems();
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to add item.',
        type: 'error',
      });
    }
  }, [addItem, selectedGroup, fetchItems]);

  const handleRemoveItem = useCallback(async (symbol: string) => {
    if (!confirm(`Remove ${symbol} from watchlist?`)) return;

    try {
      await removeItem(symbol);
      setShowToast({
        message: `Removed ${symbol} from watchlist`,
        type: 'info',
      });
      setSelectedItems(prev => prev.filter(id => id !== symbol));
      await fetchItems();
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to remove item.',
        type: 'error',
      });
    }
  }, [removeItem, fetchItems]);

  const handleMoveItem = useCallback(async (symbol: string, groupId: string) => {
    try {
      await updateItem(symbol, { groupId });
      setShowToast({
        message: `Moved ${symbol} to ${groups.find(g => g.id === groupId)?.name || 'Default'}`,
        type: 'success',
      });
      await fetchItems();
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to move item.',
        type: 'error',
      });
    }
  }, [updateItem, groups, fetchItems]);

  // ============================================
  // Handlers - Groups
  // ============================================

  const handleCreateGroup = useCallback(async () => {
    if (!newGroup.name) {
      setShowToast({
        message: 'Please enter a group name.',
        type: 'warning',
      });
      return;
    }

    setIsCreatingGroup(true);
    try {
      const result = await createGroup(newGroup.name, newGroup.description);
      if (result.success) {
        setShowToast({
          message: 'Group created successfully!',
          type: 'success',
        });
        setShowGroupModal(false);
        setNewGroup({ name: '', description: '' });
        await fetchGroups();
      }
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to create group.',
        type: 'error',
      });
    } finally {
      setIsCreatingGroup(false);
    }
  }, [newGroup, createGroup, fetchGroups]);

  const handleDeleteGroup = useCallback(async (groupId: string) => {
    if (!confirm('Delete this group? Items will be moved to Default.')) return;

    try {
      await deleteGroup(groupId);
      setShowToast({
        message: 'Group deleted successfully.',
        type: 'info',
      });
      if (selectedGroup === groupId) {
        setSelectedGroup('default');
      }
      await fetchGroups();
      await fetchItems();
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to delete group.',
        type: 'error',
      });
    }
  }, [deleteGroup, fetchGroups, fetchItems, selectedGroup]);

  // ============================================
  // Handlers - Alerts
  // ============================================

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
      const response = await api.post('/watchlist/alerts', newAlert);
      if (response.data) {
        setAlerts(prev => [response.data, ...prev]);
        setShowAlertModal(false);
        setNewAlert({
          symbol: '',
          condition: 'above',
          value: 0,
          active: true,
        });
        setSelectedItemForAlert(null);
        setShowToast({
          message: `Alert created for ${newAlert.symbol}`,
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to create alert.',
        type: 'error',
      });
    } finally {
      setIsCreatingAlert(false);
    }
  }, [api, newAlert]);

  const handleDeleteAlert = useCallback(async (alertId: string) => {
    try {
      await api.delete(`/watchlist/alerts/${alertId}`);
      setAlerts(prev => prev.filter(a => a.id !== alertId));
      setShowToast({
        message: 'Alert deleted.',
        type: 'info',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to delete alert.',
        type: 'error',
      });
    }
  }, [api]);

  // ============================================
  // Handlers - Bulk Operations
  // ============================================

  const handleBulkAction = useCallback(async () => {
    if (selectedItems.length === 0) {
      setShowToast({
        message: 'Please select at least one item.',
        type: 'warning',
      });
      return;
    }

    setIsBulkProcessing(true);
    try {
      if (bulkAction === 'delete') {
        for (const symbol of selectedItems) {
          await removeItem(symbol);
        }
        setShowToast({
          message: `Removed ${selectedItems.length} items from watchlist.`,
          type: 'success',
        });
      } else if (bulkAction === 'move') {
        // Implement move to group
      }
      setSelectedItems([]);
      setShowBulkModal(false);
      await fetchItems();
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to perform bulk action.',
        type: 'error',
      });
    } finally {
      setIsBulkProcessing(false);
    }
  }, [selectedItems, bulkAction, removeItem, fetchItems]);

  // ============================================
  // Effects
  // ============================================

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/authentication/login?callbackUrl=/watchlist');
    } else {
      fetchAllData();
    }
  }, [isAuthenticated, router, fetchAllData]);

  useEffect(() => {
    if (isConnected && items.length > 0) {
      subscribeToChannels();
    }
  }, [isConnected, items]);

  useEffect(() => {
    const debounce = setTimeout(() => {
      fetchItems();
    }, 300);
    return () => clearTimeout(debounce);
  }, [selectedGroup, searchQuery, fetchItems]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      if (!isRefreshing) {
        fetchItems();
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [autoRefresh, fetchItems, isRefreshing]);

  // ============================================
  // Memoized Computations
  // ============================================

  const filteredItems = useMemo(() => {
    let result = [...items];

    // Filter by status
    if (filterStatus === 'positive') {
      result = result.filter(item => (item.change24h || 0) >= 0);
    } else if (filterStatus === 'negative') {
      result = result.filter(item => (item.change24h || 0) < 0);
    }

    // Sort
    result.sort((a, b) => {
      let aVal: number, bVal: number;
      switch (sortBy) {
        case 'price':
          aVal = a.price || 0;
          bVal = b.price || 0;
          break;
        case 'change':
          aVal = a.changePercent24h || 0;
          bVal = b.changePercent24h || 0;
          break;
        case 'volume':
          aVal = a.volume24h || 0;
          bVal = b.volume24h || 0;
          break;
        default:
          aVal = 0;
          bVal = 0;
      }
      return sortOrder === 'desc' ? bVal - aVal : aVal - bVal;
    });

    return result;
  }, [items, filterStatus, sortBy, sortOrder]);

  const stats = useMemo(() => {
    const total = items.length;
    const positive = items.filter(i => (i.change24h || 0) >= 0).length;
    const negative = items.filter(i => (i.change24h || 0) < 0).length;
    const totalValue = items.reduce((sum, i) => sum + (i.price || 0), 0);
    const totalChange = items.reduce((sum, i) => sum + (i.changePercent24h || 0), 0);
    const avgChange = total > 0 ? totalChange / total : 0;

    return { total, positive, negative, totalValue, avgChange };
  }, [items]);

  // ============================================
  // Render
  // ============================================

  if (isLoading && watchlistLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-6">
            <div className="absolute inset-0 border-4 border-cyan-500/30 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-t-cyan-500 rounded-full animate-spin"></div>
            <div className="absolute inset-2 bg-cyan-500/10 rounded-full animate-pulse"></div>
          </div>
          <p className="text-gray-400 text-lg font-medium">Loading Watchlist...</p>
          <p className="text-gray-500 text-sm mt-2">Fetching your assets</p>
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
            <div className="text-3xl">⭐</div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                Watchlist
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                Track your favorite assets in real-time
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

          {/* Auto-refresh toggle */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded-lg border border-gray-700">
            <Switch
              checked={autoRefresh}
              onCheckedChange={setAutoRefresh}
              className="data-[state=checked]:bg-cyan-500"
            />
            <span className="text-xs text-gray-400">Auto-refresh</span>
          </div>

          {/* Create Group Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowGroupModal(true)}
            className="border-gray-700 hover:border-cyan-500"
          >
            <Plus className="w-4 h-4 mr-2" />
            New Group
          </Button>

          {/* Add Item Button */}
          <Button
            onClick={() => {
              const symbol = prompt('Enter asset symbol (e.g., BTC-USD):');
              if (symbol) {
                handleAddItem(symbol.toUpperCase());
              }
            }}
            className="bg-gradient-to-r from-cyan-500 to-blue-500"
          >
            <Plus className="w-4 h-4 mr-2" />
            Add Asset
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
              <div className="text-xs text-gray-400">Total Assets</div>
              <div className="text-xl font-bold text-white">{stats.total}</div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center">
              <Star className="w-5 h-5 text-cyan-500" />
            </div>
          </div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-400">Positive</div>
              <div className="text-xl font-bold text-green-500">{stats.positive}</div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
              <TrendingUp className="w-5 h-5 text-green-500" />
            </div>
          </div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-400">Negative</div>
              <div className="text-xl font-bold text-red-500">{stats.negative}</div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-red-500/20 flex items-center justify-center">
              <TrendingDown className="w-5 h-5 text-red-500" />
            </div>
          </div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-400">Avg Change</div>
              <div className={cn(
                "text-xl font-bold",
                stats.avgChange >= 0 ? 'text-green-500' : 'text-red-500'
              )}>
                {formatPercentage(stats.avgChange)}
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
              <div className="text-xs text-gray-400">Total Value</div>
              <div className="text-xl font-bold text-white">{formatCurrency(stats.totalValue)}</div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-yellow-500/20 flex items-center justify-center">
              <Wallet className="w-5 h-5 text-yellow-500" />
            </div>
          </div>
        </Card>
      </div>

      {/* ============================================ */}
      {/* FILTERS & SEARCH */}
      {/* ============================================ */}
      <div className="flex flex-wrap items-center gap-3 bg-gray-800/50 rounded-lg p-3 border border-gray-700 mb-6">
        <div className="flex-1 min-w-[150px]">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
            <Input
              ref={searchInputRef}
              type="text"
              placeholder="Search assets..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 bg-gray-700 border-gray-600 text-white text-sm"
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Group:</span>
          <Select
            value={selectedGroup}
            onValueChange={setSelectedGroup}
            className="w-32 bg-gray-700 border-gray-600 text-sm"
          >
            <option value="default">Default</option>
            {groups.map((group) => (
              <option key={group.id} value={group.id}>{group.name}</option>
            ))}
          </Select>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Sort:</span>
          <Select
            value={sortBy}
            onValueChange={setSortBy}
            className="w-24 bg-gray-700 border-gray-600 text-sm"
          >
            <option value="price">Price</option>
            <option value="change">Change</option>
            <option value="volume">Volume</option>
          </Select>
        </div>

        <Button
          variant="ghost"
          size="sm"
          onClick={() => setSortOrder(prev => prev === 'desc' ? 'asc' : 'desc')}
          className="text-gray-400 hover:text-white"
        >
          {sortOrder === 'desc' ? '↓' : '↑'}
        </Button>

        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Status:</span>
          <Select
            value={filterStatus}
            onValueChange={setFilterStatus}
            className="w-24 bg-gray-700 border-gray-600 text-sm"
          >
            <option value="all">All</option>
            <option value="positive">Positive</option>
            <option value="negative">Negative</option>
          </Select>
        </div>

        {selectedItems.length > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowBulkModal(true)}
            className="border-yellow-500/50 hover:border-yellow-500 text-yellow-400"
          >
            <Filter className="w-4 h-4 mr-2" />
            Bulk Actions ({selectedItems.length})
          </Button>
        )}

        <Button
          variant="ghost"
          size="sm"
          onClick={fetchAllData}
          isLoading={isRefreshing}
          className="text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10"
        >
          <RefreshCw className="w-4 h-4 mr-2" />
          Refresh
        </Button>
      </div>

      {/* ============================================ */}
      {/* WATCHLIST TABLE */}
      {/* ============================================ */}
      {items.length > 0 ? (
        <Card className="bg-gray-800 border-gray-700 overflow-hidden">
          <Table>
            <thead>
              <tr className="border-b border-gray-700">
                <th className="text-left text-xs text-gray-400 p-3">
                  <input
                    type="checkbox"
                    checked={selectedItems.length === items.length && items.length > 0}
                    onChange={(e) => {
                      if (e.target.checked) {
                        setSelectedItems(items.map(i => i.symbol));
                      } else {
                        setSelectedItems([]);
                      }
                    }}
                    className="rounded border-gray-600 bg-gray-700 text-cyan-500"
                  />
                </th>
                <th className="text-left text-xs text-gray-400 p-3">Asset</th>
                <th className="text-right text-xs text-gray-400 p-3">Price</th>
                <th className="text-right text-xs text-gray-400 p-3">24h Change</th>
                <th className="text-right text-xs text-gray-400 p-3">24h High</th>
                <th className="text-right text-xs text-gray-400 p-3">24h Low</th>
                <th className="text-right text-xs text-gray-400 p-3">Volume</th>
                <th className="text-center text-xs text-gray-400 p-3">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredItems.map((item) => (
                <tr key={item.symbol} className="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
                  <td className="p-3">
                    <input
                      type="checkbox"
                      checked={selectedItems.includes(item.symbol)}
                      onChange={() => {
                        setSelectedItems(prev =>
                          prev.includes(item.symbol)
                            ? prev.filter(id => id !== item.symbol)
                            : [...prev, item.symbol]
                        );
                      }}
                      className="rounded border-gray-600 bg-gray-700 text-cyan-500"
                    />
                  </td>
                  <td className="p-3">
                    <div className="flex items-center gap-2">
                      <span className="font-mono text-white font-medium">{item.symbol}</span>
                      {item.name && (
                        <span className="text-sm text-gray-400">{item.name}</span>
                      )}
                      {groups.find(g => g.id === item.groupId) && (
                        <Badge className="bg-gray-600 text-xs">
                          {groups.find(g => g.id === item.groupId)?.name}
                        </Badge>
                      )}
                    </div>
                  </td>
                  <td className="p-3 text-right text-white font-mono">
                    {formatCurrency(item.price || 0)}
                  </td>
                  <td className={cn(
                    "p-3 text-right font-medium",
                    (item.change24h || 0) >= 0 ? 'text-green-500' : 'text-red-500'
                  )}>
                    {formatPercentage(item.changePercent24h || 0)}
                  </td>
                  <td className="p-3 text-right text-gray-400 font-mono">
                    {formatCurrency(item.high24h || 0)}
                  </td>
                  <td className="p-3 text-right text-gray-400 font-mono">
                    {formatCurrency(item.low24h || 0)}
                  </td>
                  <td className="p-3 text-right text-gray-300 font-mono">
                    {formatCurrency(item.volume24h || 0)}
                  </td>
                  <td className="p-3 text-center">
                    <div className="flex items-center justify-center gap-1">
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => {
                          setSelectedItemForAlert(item);
                          setNewAlert(prev => ({ ...prev, symbol: item.symbol }));
                          setShowAlertModal(true);
                        }}
                        className="text-gray-400 hover:text-yellow-500"
                      >
                        <Bell className="w-4 h-4" />
                      </Button>
                      <Select
                        value={item.groupId || 'default'}
                        onValueChange={(value) => handleMoveItem(item.symbol, value)}
                        className="w-24 bg-gray-700 border-gray-600 text-xs"
                      >
                        <option value="default">Default</option>
                        {groups.map((group) => (
                          <option key={group.id} value={group.id}>{group.name}</option>
                        ))}
                      </Select>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleRemoveItem(item.symbol)}
                        className="text-gray-400 hover:text-red-500"
                      >
                        <Trash className="w-4 h-4" />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </Table>
        </Card>
      ) : (
        <div className="text-center py-12 text-gray-500">
          <Star className="w-16 h-16 mx-auto mb-4 text-gray-600" />
          <p className="text-lg font-medium">Your watchlist is empty</p>
          <p className="text-sm">Add assets to track their performance</p>
          <Button
            onClick={() => {
              const symbol = prompt('Enter asset symbol (e.g., BTC-USD):');
              if (symbol) {
                handleAddItem(symbol.toUpperCase());
              }
            }}
            className="mt-4 bg-gradient-to-r from-cyan-500 to-blue-500"
          >
            <Plus className="w-4 h-4 mr-2" />
            Add First Asset
          </Button>
        </div>
      )}

      {/* ============================================ */}
      {/* CREATE GROUP MODAL */}
      {/* ============================================ */}
      <Modal
        open={showGroupModal}
        onOpenChange={setShowGroupModal}
        title="Create Watchlist Group"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Group Name *</label>
            <Input
              value={newGroup.name}
              onChange={(e) => setNewGroup({ ...newGroup, name: e.target.value })}
              placeholder="e.g., Crypto, Stocks, Forex"
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Description (optional)</label>
            <Textarea
              value={newGroup.description}
              onChange={(e) => setNewGroup({ ...newGroup, description: e.target.value })}
              placeholder="Brief description of this group"
              className="w-full bg-gray-700 border-gray-600 text-white resize-none"
              rows={2}
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => {
                setShowGroupModal(false);
                setNewGroup({ name: '', description: '' });
              }}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateGroup}
              isLoading={isCreatingGroup}
              className="bg-gradient-to-r from-cyan-500 to-blue-500"
            >
              Create Group
            </Button>
          </div>
        </div>
      </Modal>

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
            <label className="block text-sm text-gray-400 mb-1">Symbol</label>
            <Input
              value={newAlert.symbol}
              onChange={(e) => setNewAlert({ ...newAlert, symbol: e.target.value.toUpperCase() })}
              placeholder="BTC-USD"
              className="w-full bg-gray-700 border-gray-600 text-white font-mono"
              disabled={!!selectedItemForAlert}
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Condition</label>
              <Select
                value={newAlert.condition}
                onValueChange={(value) => setNewAlert({ ...newAlert, condition: value as any })}
                className="w-full bg-gray-700 border-gray-600"
              >
                {PRICE_ALERT_CONDITIONS.map((cond) => (
                  <option key={cond.value} value={cond.value}>
                    {cond.label}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Value *</label>
              <Input
                type="number"
                step="0.01"
                value={newAlert.value}
                onChange={(e) => setNewAlert({ ...newAlert, value: parseFloat(e.target.value) || 0 })}
                placeholder="0.00"
                className="w-full bg-gray-700 border-gray-600 text-white"
              />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Switch
              checked={newAlert.active}
              onCheckedChange={(checked) => setNewAlert({ ...newAlert, active: checked })}
              className="data-[state=checked]:bg-cyan-500"
            />
            <span className="text-sm text-gray-400">Active</span>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => {
                setShowAlertModal(false);
                setNewAlert({
                  symbol: '',
                  condition: 'above',
                  value: 0,
                  active: true,
                });
                setSelectedItemForAlert(null);
              }}
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
      {/* BULK ACTIONS MODAL */}
      {/* ============================================ */}
      <Modal
        open={showBulkModal}
        onOpenChange={setShowBulkModal}
        title="Bulk Actions"
        className="max-w-md"
      >
        <div className="space-y-4">
          <p className="text-sm text-gray-400">
            You have selected <span className="text-white font-medium">{selectedItems.length}</span> items.
          </p>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Action</label>
            <Select
              value={bulkAction}
              onValueChange={setBulkAction}
              className="w-full bg-gray-700 border-gray-600"
            >
              <option value="delete">Delete Selected</option>
              <option value="move">Move to Group</option>
            </Select>
          </div>
          {bulkAction === 'move' && (
            <div>
              <label className="block text-sm text-gray-400 mb-1">Target Group</label>
              <Select
                value={selectedGroup}
                onValueChange={setSelectedGroup}
                className="w-full bg-gray-700 border-gray-600"
              >
                <option value="default">Default</option>
                {groups.map((group) => (
                  <option key={group.id} value={group.id}>{group.name}</option>
                ))}
              </Select>
            </div>
          )}
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => {
                setShowBulkModal(false);
                setSelectedItems([]);
              }}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handleBulkAction}
              isLoading={isBulkProcessing}
              className="bg-gradient-to-r from-yellow-500 to-orange-500"
            >
              Apply to {selectedItems.length} Items
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

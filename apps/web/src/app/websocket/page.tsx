/**
 * NEXUS AI TRADING SYSTEM - WebSocket Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page provides comprehensive WebSocket management including:
 * - WebSocket connection status
 * - Real-time message streaming
 * - Channel subscription management
 * - Message history and logs
 * - Connection statistics
 * - Channel monitoring
 * - Message filtering and search
 * - Connection retry management
 * - Authentication status
 * - Latency monitoring
 * - Heartbeat tracking
 * - Message queuing
 * - Broadcast management
 * - Multi-channel support
 * - Responsive design for all devices
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
import { Switch } from '@/components/ui/Switch';
import { Table } from '@/components/ui/Table';
import { Avatar } from '@/components/ui/Avatar';
import { CopyButton } from '@/components/ui/CopyButton';

// Icons
import {
  Wifi,
  WifiOff,
  Signal,
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
  Link,
  ExternalLink as ExternalLinkIcon,
  Globe,
  MapPin as MapPinIcon,
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
  Edit,
  Save,
  Clock as ClockIcon,
  Calendar as CalendarIcon,
  User,
  Mail as MailIcon,
  Phone as PhoneIcon,
  Smartphone,
  Tablet,
  Laptop,
  Monitor as MonitorIcon,
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
  WebSocketConnection,
  WebSocketMessage,
  WebSocketChannel,
  WebSocketSubscription,
  WebSocketStats,
  WebSocketEvent,
  WebSocketLog,
} from '@/types/websocket';

// Constants
import {
  WS_CHANNELS,
  WS_MESSAGE_TYPES,
  WS_EVENTS,
  DEFAULT_CHANNELS,
} from '@/constants/websocket';

// Utils
import { formatDate, formatTime, formatBytes } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

export default function WebSocketPage() {
  // Router
  const router = useRouter();

  // Auth hooks
  const { user, isAuthenticated } = useAuth();

  // API client
  const api = useApi();

  // WebSocket hook
  const {
    isConnected,
    isConnecting,
    isAuthenticated: wsAuthenticated,
    lastMessage,
    messages: wsMessages,
    sendMessage,
    subscribe,
    unsubscribe,
    connect,
    disconnect,
    reconnect,
    stats,
    channels,
    subscriptions,
    connectionInfo,
    error,
    reconnectAttempts,
    maxReconnectAttempts,
    latency,
  } = useWebSocket({
    url: `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8004'}/websocket`,
    autoConnect: true,
    onOpen: handleWebSocketOpen,
    onMessage: handleWebSocketMessage,
    onError: handleWebSocketError,
    onClose: handleWebSocketClose,
    reconnectAttempts: 10,
    reconnectInterval: 3000,
    authToken: user?.accessToken || '',
  });

  // State - Messages
  const [messages, setMessages] = useState<WebSocketMessage[]>([]);
  const [filteredMessages, setFilteredMessages] = useState<WebSocketMessage[]>([]);
  const [messageFilter, setMessageFilter] = useState<string>('all');
  const [messageSearch, setMessageSearch] = useState<string>('');

  // State - Channels
  const [activeChannels, setActiveChannels] = useState<string[]>(DEFAULT_CHANNELS);
  const [showSubscribeModal, setShowSubscribeModal] = useState<boolean>(false);
  const [newChannel, setNewChannel] = useState<string>('');
  const [channelParams, setChannelParams] = useState<Record<string, any>>({});

  // State - Logs
  const [logs, setLogs] = useState<WebSocketLog[]>([]);
  const [logFilter, setLogFilter] = useState<string>('all');

  // State - UI
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [autoScroll, setAutoScroll] = useState<boolean>(true);
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [messageCount, setMessageCount] = useState<number>(0);
  const [messageRate, setMessageRate] = useState<number>(0);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const logContainerRef = useRef<HTMLDivElement>(null);
  const messageIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // ============================================
  // WebSocket Handlers
  // ============================================

  function handleWebSocketOpen() {
    console.log('✅ WebSocket connected');
    addLog('info', 'WebSocket connection established');
    setShowToast({
      message: 'WebSocket connected successfully!',
      type: 'success',
    });
  }

  function handleWebSocketMessage(event: MessageEvent) {
    try {
      const data = JSON.parse(event.data);
      const message: WebSocketMessage = {
        id: `msg-${Date.now()}`,
        type: data.type || 'unknown',
        channel: data.channel || 'unknown',
        data: data.payload || data,
        timestamp: new Date(),
        raw: event.data,
      };
      
      setMessages(prev => [...prev, message].slice(-500));
      setMessageCount(prev => prev + 1);
      
      // Add log for important messages
      if (data.type === 'error' || data.type === 'warning') {
        addLog('error', `Message error: ${data.message || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
      addLog('error', `Failed to parse message: ${error}`);
    }
  }

  function handleWebSocketError(error: Event) {
    console.error('WebSocket error:', error);
    addLog('error', `WebSocket error: ${error}`);
    setShowToast({
      message: 'WebSocket error occurred. Attempting to reconnect...',
      type: 'error',
    });
  }

  function handleWebSocketClose() {
    console.log('WebSocket disconnected');
    addLog('info', 'WebSocket connection closed');
    setShowToast({
      message: 'WebSocket disconnected. Reconnecting...',
      type: 'warning',
    });
  }

  // ============================================
  // Logging
  // ============================================

  const addLog = useCallback((level: 'info' | 'warning' | 'error', message: string) => {
    const log: WebSocketLog = {
      id: `log-${Date.now()}`,
      timestamp: new Date(),
      level,
      message,
    };
    setLogs(prev => [...prev, log].slice(-500));
  }, []);

  // ============================================
  // Channel Management
  // ============================================

  const handleSubscribe = useCallback(async () => {
    if (!newChannel.trim()) {
      setShowToast({
        message: 'Please enter a channel name.',
        type: 'warning',
      });
      return;
    }

    try {
      await subscribe(newChannel, channelParams);
      setActiveChannels(prev => [...prev, newChannel]);
      setShowSubscribeModal(false);
      setNewChannel('');
      setChannelParams({});
      setShowToast({
        message: `Subscribed to channel: ${newChannel}`,
        type: 'success',
      });
      addLog('info', `Subscribed to channel: ${newChannel}`);
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to subscribe.',
        type: 'error',
      });
      addLog('error', `Failed to subscribe to ${newChannel}: ${error}`);
    }
  }, [newChannel, channelParams, subscribe]);

  const handleUnsubscribe = useCallback(async (channel: string) => {
    try {
      await unsubscribe(channel);
      setActiveChannels(prev => prev.filter(c => c !== channel));
      setShowToast({
        message: `Unsubscribed from channel: ${channel}`,
        type: 'info',
      });
      addLog('info', `Unsubscribed from channel: ${channel}`);
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to unsubscribe.',
        type: 'error',
      });
      addLog('error', `Failed to unsubscribe from ${channel}: ${error}`);
    }
  }, [unsubscribe]);

  // ============================================
  // Message Management
  // ============================================

  const handleSendMessage = useCallback(async (type: string, data: any) => {
    try {
      await sendMessage({ type, data });
      addLog('info', `Sent message: ${type}`);
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to send message.',
        type: 'error',
      });
      addLog('error', `Failed to send message: ${error}`);
    }
  }, [sendMessage]);

  const clearMessages = useCallback(() => {
    setMessages([]);
    setMessageCount(0);
    addLog('info', 'Cleared message history');
  }, []);

  // ============================================
  // Effects
  // ============================================

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/authentication/login?callbackUrl=/websocket');
    } else {
      setIsLoading(false);
      addLog('info', 'WebSocket page loaded');
    }
  }, [isAuthenticated, router]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (autoScroll && messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, autoScroll]);

  // Filter messages
  useEffect(() => {
    let filtered = messages;
    
    if (messageFilter !== 'all') {
      filtered = filtered.filter(m => m.type === messageFilter);
    }
    
    if (messageSearch) {
      const search = messageSearch.toLowerCase();
      filtered = filtered.filter(m => 
        JSON.stringify(m.data).toLowerCase().includes(search) ||
        m.channel.toLowerCase().includes(search) ||
        m.type.toLowerCase().includes(search)
      );
    }
    
    setFilteredMessages(filtered);
  }, [messages, messageFilter, messageSearch]);

  // Calculate message rate
  useEffect(() => {
    if (messageIntervalRef.current) {
      clearInterval(messageIntervalRef.current);
    }
    
    let lastCount = messageCount;
    messageIntervalRef.current = setInterval(() => {
      const currentCount = messageCount;
      setMessageRate(currentCount - lastCount);
      lastCount = currentCount;
    }, 1000);
    
    return () => {
      if (messageIntervalRef.current) {
        clearInterval(messageIntervalRef.current);
      }
    };
  }, [messageCount]);

  // ============================================
  // Memoized Computations
  // ============================================

  const logLevelColors = useMemo(() => ({
    info: 'bg-blue-500/20 text-blue-500 border-blue-500/30',
    warning: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30',
    error: 'bg-red-500/20 text-red-500 border-red-500/30',
  }), []);

  const getMessageTypeBadge = (type: string) => {
    const badges: Record<string, { color: string; label: string }> = {
      connection: { color: 'bg-green-500/20 text-green-500', label: 'CONNECTION' },
      subscription: { color: 'bg-blue-500/20 text-blue-500', label: 'SUBSCRIPTION' },
      data: { color: 'bg-cyan-500/20 text-cyan-500', label: 'DATA' },
      error: { color: 'bg-red-500/20 text-red-500', label: 'ERROR' },
      ping: { color: 'bg-purple-500/20 text-purple-500', label: 'PING' },
      pong: { color: 'bg-purple-500/20 text-purple-500', label: 'PONG' },
    };
    return badges[type] || { color: 'bg-gray-500/20 text-gray-400', label: type.toUpperCase() };
  };

  // ============================================
  // Render
  // ============================================

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-6">
            <div className="absolute inset-0 border-4 border-cyan-500/30 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-t-cyan-500 rounded-full animate-spin"></div>
            <div className="absolute inset-2 bg-cyan-500/10 rounded-full animate-pulse"></div>
          </div>
          <p className="text-gray-400 text-lg font-medium">Loading WebSocket...</p>
          <p className="text-gray-500 text-sm mt-2">Connecting to WebSocket server</p>
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
            <div className="text-3xl">🔌</div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                WebSocket
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                Real-time communication management
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          {/* Connection Status */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded-lg border border-gray-700">
            <div className={cn(
              'w-2 h-2 rounded-full transition-all duration-500',
              isConnected ? 'bg-green-500 animate-pulse' : isConnecting ? 'bg-yellow-500 animate-pulse' : 'bg-red-500'
            )} />
            <span className="text-xs text-gray-400">
              {isConnected ? 'Connected' : isConnecting ? 'Connecting...' : 'Disconnected'}
            </span>
          </div>

          {/* Latency */}
          {isConnected && latency !== null && (
            <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded-lg border border-gray-700">
              <Activity className="w-4 h-4 text-cyan-500" />
              <span className="text-xs text-gray-400">
                Latency: {latency}ms
              </span>
            </div>
          )}

          {/* Message Rate */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded-lg border border-gray-700">
            <Zap className="w-4 h-4 text-yellow-500" />
            <span className="text-xs text-gray-400">
              {messageRate} msg/s
            </span>
          </div>

          {/* Reconnect Button */}
          {!isConnected && (
            <Button
              variant="outline"
              size="sm"
              onClick={reconnect}
              disabled={isConnecting}
              className="border-gray-700 hover:border-cyan-500"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Reconnect
            </Button>
          )}
        </div>
      </div>

      {/* ============================================ */}
      {/* CONNECTION DETAILS */}
      {/* ============================================ */}
      <Card className="p-4 bg-gray-800 border-gray-700 mb-6">
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          <div>
            <div className="text-xs text-gray-400">Status</div>
            <div className="flex items-center gap-2">
              <div className={cn(
                'w-2 h-2 rounded-full',
                isConnected ? 'bg-green-500' : isConnecting ? 'bg-yellow-500' : 'bg-red-500'
              )} />
              <span className="text-sm font-medium">
                {isConnected ? 'Connected' : isConnecting ? 'Connecting...' : 'Disconnected'}
              </span>
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-400">Authenticated</div>
            <div className="flex items-center gap-2">
              {wsAuthenticated ? (
                <Check className="w-4 h-4 text-green-500" />
              ) : (
                <X className="w-4 h-4 text-red-500" />
              )}
              <span className="text-sm font-medium">
                {wsAuthenticated ? 'Yes' : 'No'}
              </span>
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-400">Reconnect Attempts</div>
            <div className="text-sm font-medium">
              {reconnectAttempts}/{maxReconnectAttempts}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-400">Channels</div>
            <div className="text-sm font-medium">{activeChannels.length}</div>
          </div>
          <div>
            <div className="text-xs text-gray-400">Messages</div>
            <div className="text-sm font-medium">{messageCount}</div>
          </div>
          <div>
            <div className="text-xs text-gray-400">Uptime</div>
            <div className="text-sm font-medium">
              {connectionInfo?.connectedAt ? formatTime(connectionInfo.connectedAt) : 'N/A'}
            </div>
          </div>
        </div>
      </Card>

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
            value="messages"
            className="data-[state=active]:bg-blue-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            💬 Messages ({filteredMessages.length})
          </TabsTrigger>
          <TabsTrigger
            value="channels"
            className="data-[state=active]:bg-purple-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📡 Channels ({activeChannels.length})
          </TabsTrigger>
          <TabsTrigger
            value="logs"
            className="data-[state=active]:bg-yellow-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📋 Logs ({logs.length})
          </TabsTrigger>
        </TabsList>

        {/* ========================================== */}
        {/* OVERVIEW TAB */}
        {/* ========================================== */}
        <TabsContent value="overview" className="mt-4 space-y-6">
          <div className="grid grid-cols-12 gap-6">
            {/* Stats Cards */}
            <div className="col-span-12 grid grid-cols-2 md:grid-cols-4 gap-4">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs text-gray-400">Messages Received</div>
                    <div className="text-2xl font-bold text-white">{messageCount}</div>
                  </div>
                  <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                    <MessageSquare className="w-5 h-5 text-cyan-500" />
                  </div>
                </div>
              </Card>
              <Card className="p-4 bg-gray-800 border-gray-700">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs text-gray-400">Active Channels</div>
                    <div className="text-2xl font-bold text-white">{activeChannels.length}</div>
                  </div>
                  <div className="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
                    <Signal className="w-5 h-5 text-green-500" />
                  </div>
                </div>
              </Card>
              <Card className="p-4 bg-gray-800 border-gray-700">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs text-gray-400">Errors</div>
                    <div className="text-2xl font-bold text-red-500">
                      {logs.filter(l => l.level === 'error').length}
                    </div>
                  </div>
                  <div className="w-10 h-10 rounded-lg bg-red-500/20 flex items-center justify-center">
                    <AlertCircle className="w-5 h-5 text-red-500" />
                  </div>
                </div>
              </Card>
              <Card className="p-4 bg-gray-800 border-gray-700">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="text-xs text-gray-400">Avg Latency</div>
                    <div className="text-2xl font-bold text-cyan-400">
                      {latency !== null ? `${latency}ms` : 'N/A'}
                    </div>
                  </div>
                  <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
                    <Activity className="w-5 h-5 text-purple-500" />
                  </div>
                </div>
              </Card>
            </div>

            {/* Channel Status */}
            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Active Channels</h3>
                <div className="space-y-2">
                  {activeChannels.map((channel) => (
                    <div key={channel} className="flex items-center justify-between p-2 bg-gray-700/30 rounded-lg">
                      <div className="flex items-center gap-2">
                        <div className="w-2 h-2 rounded-full bg-green-500" />
                        <span className="text-white font-mono">{channel}</span>
                      </div>
                      <Badge className="bg-green-500/20 text-green-500 text-xs">Active</Badge>
                    </div>
                  ))}
                  {activeChannels.length === 0 && (
                    <div className="text-center py-4 text-gray-500">
                      <p>No active channels</p>
                      <p className="text-sm">Subscribe to a channel to start receiving data</p>
                    </div>
                  )}
                </div>
              </Card>
            </div>

            {/* Connection Info */}
            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Connection Details</h3>
                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-400">URL</span>
                    <span className="text-white font-mono truncate max-w-[200px]">
                      {connectionInfo?.url || 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Protocol</span>
                    <span className="text-white">{connectionInfo?.protocol || 'N/A'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Connected At</span>
                    <span className="text-white">{connectionInfo?.connectedAt ? formatTime(connectionInfo.connectedAt) : 'N/A'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Last Activity</span>
                    <span className="text-white">{connectionInfo?.lastActivity ? formatTime(connectionInfo.lastActivity) : 'N/A'}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Messages Sent</span>
                    <span className="text-white">{stats?.messagesSent || 0}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-400">Messages Received</span>
                    <span className="text-white">{stats?.messagesReceived || 0}</span>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* MESSAGES TAB */}
        {/* ========================================== */}
        <TabsContent value="messages" className="mt-4">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <div className="flex-1 min-w-[200px]">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500" />
                <Input
                  type="text"
                  placeholder="Search messages..."
                  value={messageSearch}
                  onChange={(e) => setMessageSearch(e.target.value)}
                  className="w-full pl-9 bg-gray-700 border-gray-600 text-white text-sm"
                />
              </div>
            </div>

            <Select
              value={messageFilter}
              onValueChange={setMessageFilter}
              className="w-32 bg-gray-700 border-gray-600 text-sm"
            >
              <option value="all">All Types</option>
              <option value="connection">Connection</option>
              <option value="subscription">Subscription</option>
              <option value="data">Data</option>
              <option value="error">Error</option>
              <option value="ping">Ping</option>
              <option value="pong">Pong</option>
            </Select>

            <div className="flex items-center gap-2">
              <Switch
                checked={autoScroll}
                onCheckedChange={setAutoScroll}
                className="data-[state=checked]:bg-cyan-500"
              />
              <span className="text-xs text-gray-400">Auto-scroll</span>
            </div>

            <Button
              variant="outline"
              size="sm"
              onClick={clearMessages}
              className="border-gray-600 hover:border-red-500 text-gray-400 hover:text-red-500"
            >
              <Trash className="w-4 h-4 mr-2" />
              Clear
            </Button>
          </div>

          <Card className="p-4 bg-gray-800 border-gray-700 h-[500px] overflow-y-auto">
            <div className="space-y-2">
              {filteredMessages.length > 0 ? (
                filteredMessages.map((message) => {
                  const badge = getMessageTypeBadge(message.type);
                  return (
                    <div key={message.id} className="p-2 bg-gray-700/30 rounded-lg hover:bg-gray-700/50 transition-colors">
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-2 flex-wrap">
                          <Badge className={cn("text-xs", badge.color)}>
                            {badge.label}
                          </Badge>
                          <span className="text-xs text-gray-500">{formatTime(message.timestamp)}</span>
                          <span className="text-xs text-cyan-400 font-mono">{message.channel}</span>
                        </div>
                        <CopyButton text={message.raw}>
                          <Button variant="ghost" size="sm" className="text-gray-400 hover:text-white p-1">
                            <Copy className="w-3 h-3" />
                          </Button>
                        </CopyButton>
                      </div>
                      <pre className="mt-1 text-xs text-gray-300 overflow-x-auto whitespace-pre-wrap">
                        {JSON.stringify(message.data, null, 2)}
                      </pre>
                    </div>
                  );
                })
              ) : (
                <div className="flex items-center justify-center h-full text-gray-500">
                  <div className="text-center">
                    <MessageSquare className="w-16 h-16 mx-auto mb-4 text-gray-600" />
                    <p className="text-lg font-medium">No messages</p>
                    <p className="text-sm">Messages will appear here in real-time</p>
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          </Card>
        </TabsContent>

        {/* ========================================== */}
        {/* CHANNELS TAB */}
        {/* ========================================== */}
        <TabsContent value="channels" className="mt-4">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-sm font-semibold text-gray-300">Active Channels</h3>
            <Button
              onClick={() => setShowSubscribeModal(true)}
              className="bg-gradient-to-r from-cyan-500 to-blue-500"
            >
              <Plus className="w-4 h-4 mr-2" />
              Subscribe
            </Button>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {activeChannels.map((channel) => (
              <Card key={channel} className="p-4 bg-gray-800 border-gray-700">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center">
                      <Signal className="w-5 h-5 text-cyan-500" />
                    </div>
                    <div>
                      <div className="font-mono text-white font-medium">{channel}</div>
                      <div className="text-xs text-gray-400">
                        {messages.filter(m => m.channel === channel).length} messages
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge className="bg-green-500/20 text-green-500 text-xs">Active</Badge>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleUnsubscribe(channel)}
                      className="text-gray-400 hover:text-red-500"
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
                <div className="mt-2 pt-2 border-t border-gray-700">
                  <div className="flex gap-2 text-xs text-gray-500">
                    <span>Subscribers: {subscriptions.filter(s => s.channel === channel).length}</span>
                    <span>•</span>
                    <span>Last message: {messages.filter(m => m.channel === channel).pop()?.timestamp ? formatTime(messages.filter(m => m.channel === channel).pop()!.timestamp) : 'N/A'}</span>
                  </div>
                </div>
              </Card>
            ))}
            {activeChannels.length === 0 && (
              <div className="col-span-2 text-center py-12 text-gray-500">
                <Signal className="w-16 h-16 mx-auto mb-4 text-gray-600" />
                <p className="text-lg font-medium">No active channels</p>
                <p className="text-sm">Subscribe to a channel to start receiving data</p>
              </div>
            )}
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* LOGS TAB */}
        {/* ========================================== */}
        <TabsContent value="logs" className="mt-4">
          <div className="flex flex-wrap items-center gap-3 mb-4">
            <Select
              value={logFilter}
              onValueChange={setLogFilter}
              className="w-32 bg-gray-700 border-gray-600 text-sm"
            >
              <option value="all">All Logs</option>
              <option value="info">Info</option>
              <option value="warning">Warning</option>
              <option value="error">Error</option>
            </Select>

            <Button
              variant="outline"
              size="sm"
              onClick={() => setLogs([])}
              className="border-gray-600 hover:border-red-500 text-gray-400 hover:text-red-500"
            >
              <Trash className="w-4 h-4 mr-2" />
              Clear Logs
            </Button>
          </div>

          <div ref={logContainerRef} className="space-y-2 max-h-[500px] overflow-y-auto">
            {logs
              .filter(log => logFilter === 'all' || log.level === logFilter)
              .map((log) => (
                <div
                  key={log.id}
                  className={cn(
                    "p-2 rounded-lg border transition-colors",
                    log.level === 'info' ? 'bg-blue-500/10 border-blue-500/20' :
                    log.level === 'warning' ? 'bg-yellow-500/10 border-yellow-500/20' :
                    'bg-red-500/10 border-red-500/20'
                  )}
                >
                  <div className="flex items-center gap-3">
                    <Badge className={cn("text-xs", logLevelColors[log.level])}>
                      {log.level.toUpperCase()}
                    </Badge>
                    <span className="text-xs text-gray-500">{formatTime(log.timestamp)}</span>
                    <span className="text-sm text-gray-300">{log.message}</span>
                  </div>
                </div>
              ))}
            {logs.length === 0 && (
              <div className="text-center py-12 text-gray-500">
                <FileText className="w-16 h-16 mx-auto mb-4 text-gray-600" />
                <p className="text-lg font-medium">No logs</p>
                <p className="text-sm">Logs will appear here as events occur</p>
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>

      {/* ============================================ */}
      {/* SUBSCRIBE MODAL */}
      {/* ============================================ */}
      <Modal
        open={showSubscribeModal}
        onOpenChange={setShowSubscribeModal}
        title="Subscribe to Channel"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Channel Name *</label>
            <Input
              value={newChannel}
              onChange={(e) => setNewChannel(e.target.value)}
              placeholder="e.g., market_data, ai_predictions"
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
            <div className="mt-1 flex flex-wrap gap-1">
              <span className="text-xs text-gray-500">Common channels:</span>
              {Object.values(WS_CHANNELS).slice(0, 4).map((ch) => (
                <button
                  key={ch}
                  onClick={() => setNewChannel(ch)}
                  className="text-xs text-cyan-400 hover:text-cyan-300 hover:underline"
                >
                  {ch}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Parameters (optional)</label>
            <Textarea
              value={JSON.stringify(channelParams, null, 2)}
              onChange={(e) => {
                try {
                  setChannelParams(JSON.parse(e.target.value));
                } catch {
                  // Invalid JSON, ignore
                }
              }}
              placeholder='{"symbol": "BTC-USD"}'
              className="w-full bg-gray-700 border-gray-600 text-white resize-none font-mono text-sm"
              rows={3}
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => {
                setShowSubscribeModal(false);
                setNewChannel('');
                setChannelParams({});
              }}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSubscribe}
              className="bg-gradient-to-r from-cyan-500 to-blue-500"
            >
              Subscribe
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

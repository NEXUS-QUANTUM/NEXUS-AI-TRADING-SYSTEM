/**
 * NEXUS AI TRADING SYSTEM - Support Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page provides comprehensive support management including:
 * - Ticket creation and management
 * - Ticket listing with filtering and search
 * - Ticket status tracking
 * - Knowledge base integration
 * - FAQ section
 * - Live chat support
 * - Support ticket analytics
 * - Priority management
 * - Assignment management
 * - Escalation handling
 * - Ticket resolution tracking
 * - User satisfaction surveys
 * - Support team management
 * - Response time tracking
 * - SLA monitoring
 * - Ticket templates
 * - Bulk operations
 * - Export functionality
 * - Real-time WebSocket updates
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
import { Textarea } from '@/components/ui/Textarea';
import { Avatar } from '@/components/ui/Avatar';
import { Table } from '@/components/ui/Table';
import { CopyButton } from '@/components/ui/CopyButton';

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
  User,
  Mail,
  Phone,
  MessageSquare,
  FileText,
  ArrowLeft,
  ArrowRight,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  MoreVertical,
  Settings,
  Users,
  Briefcase,
  Building,
  Landmark,
  PiggyBank,
  Receipt,
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
  Ticket,
  TicketCheck,
  TicketX,
  TicketMinus,
  TicketPlus,
  Headphones,
  LifeBuoy,
  MessageCircle as MessageCircleIcon,
  Send,
} from 'lucide-react';

// Types
import type {
  SupportTicket,
  TicketStatus,
  TicketPriority,
  TicketCategory,
  TicketFilter,
  TicketStats,
  TicketTemplate,
  SupportAgent,
  TicketSLA,
  TicketSurvey,
} from '@/types/support';

// Constants
import {
  TICKET_STATUSES,
  TICKET_PRIORITIES,
  TICKET_CATEGORIES,
  TICKET_ACTIVITY_TYPES,
  DEFAULT_PAGE_SIZE,
  MAX_PAGE_SIZE,
  TICKET_SORT_FIELDS,
  TICKET_TEMPLATES,
  SUPPORT_AGENTS,
} from '@/constants/support';

// Utils
import { formatDate, formatTime, formatDuration, formatNumber } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

export default function SupportPage() {
  // Router
  const router = useRouter();

  // Auth hooks
  const { user, isAuthenticated, accessToken } = useAuth();

  // API client
  const api = useApi();

  // State - Tickets
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [ticketsLoading, setTicketsLoading] = useState<boolean>(true);
  const [selectedTickets, setSelectedTickets] = useState<string[]>([]);
  const [totalTickets, setTotalTickets] = useState<number>(0);

  // State - Filters
  const [filter, setFilter] = useState<TicketFilter>({
    status: 'all',
    priority: 'all',
    category: 'all',
    assignedTo: 'all',
    search: '',
    page: 1,
    limit: DEFAULT_PAGE_SIZE,
    sortBy: 'createdAt',
    sortOrder: 'desc',
  });

  // State - Stats
  const [stats, setStats] = useState<TicketStats | null>(null);
  const [statsLoading, setStatsLoading] = useState<boolean>(true);

  // State - Create Ticket
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [newTicket, setNewTicket] = useState<Partial<SupportTicket>>({
    subject: '',
    description: '',
    priority: 'medium',
    category: 'general',
    attachments: [],
  });
  const [isCreating, setIsCreating] = useState<boolean>(false);

  // State - Templates
  const [templates, setTemplates] = useState<TicketTemplate[]>(TICKET_TEMPLATES);
  const [selectedTemplate, setSelectedTemplate] = useState<string>('');

  // State - Agents
  const [agents, setAgents] = useState<SupportAgent[]>(SUPPORT_AGENTS);
  const [agentsLoading, setAgentsLoading] = useState<boolean>(true);

  // State - SLA
  const [slaMetrics, setSlaMetrics] = useState<TicketSLA | null>(null);
  const [slaLoading, setSlaLoading] = useState<boolean>(true);

  // State - Surveys
  const [surveys, setSurveys] = useState<TicketSurvey[]>([]);
  const [surveysLoading, setSurveysLoading] = useState<boolean>(true);

  // State - Bulk Operations
  const [showBulkModal, setShowBulkModal] = useState<boolean>(false);
  const [bulkAction, setBulkAction] = useState<string>('status');
  const [bulkValue, setBulkValue] = useState<string>('');
  const [isBulkProcessing, setIsBulkProcessing] = useState<boolean>(false);

  // State - UI
  const [activeTab, setActiveTab] = useState<string>('tickets');
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);

  // Refs
  const searchInputRef = useRef<HTMLInputElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // ============================================
  // WebSocket Connection
  // ============================================

  const {
    isConnected,
    sendMessage,
    subscribe: wsSubscribe,
    unsubscribe: wsUnsubscribe,
  } = useWebSocket({
    url: `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8004'}/support`,
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
    console.log('✅ Support WebSocket connected');
    subscribeToChannels();
  }

  function handleWebSocketMessage(event: MessageEvent) {
    try {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'ticket_created':
          handleTicketCreated(data.payload);
          break;
        case 'ticket_updated':
          handleTicketUpdated(data.payload);
          break;
        case 'ticket_deleted':
          handleTicketDeleted(data.payload);
          break;
        case 'ticket_stats':
          handleStatsUpdate(data.payload);
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
    console.log('Support WebSocket disconnected');
  }

  function subscribeToChannels() {
    if (!isConnected) return;

    wsSubscribe({
      channel: 'tickets',
      userId: user?.id,
    });

    wsSubscribe({
      channel: 'ticket_stats',
      userId: user?.id,
    });
  }

  // ============================================
  // WebSocket Data Handlers
  // ============================================

  function handleTicketCreated(data: any) {
    const newTicketData: SupportTicket = {
      ...data,
      createdAt: new Date(data.createdAt),
      updatedAt: new Date(data.updatedAt),
      resolvedAt: data.resolvedAt ? new Date(data.resolvedAt) : undefined,
      closedAt: data.closedAt ? new Date(data.closedAt) : undefined,
    };
    setTickets(prev => [newTicketData, ...prev]);
    setTotalTickets(prev => prev + 1);
    setShowToast({
      message: `New ticket created: ${data.subject}`,
      type: 'info',
    });
  }

  function handleTicketUpdated(data: any) {
    setTickets(prev =>
      prev.map(t =>
        t.id === data.id
          ? {
              ...t,
              ...data,
              updatedAt: new Date(data.updatedAt),
              resolvedAt: data.resolvedAt ? new Date(data.resolvedAt) : undefined,
              closedAt: data.closedAt ? new Date(data.closedAt) : undefined,
            }
          : t
      )
    );
  }

  function handleTicketDeleted(data: any) {
    setTickets(prev => prev.filter(t => t.id !== data.id));
    setTotalTickets(prev => prev - 1);
    setSelectedTickets(prev => prev.filter(id => id !== data.id));
  }

  function handleStatsUpdate(data: any) {
    setStats(data);
  }

  // ============================================
  // API Calls
  // ============================================

  const fetchTickets = useCallback(async () => {
    try {
      setTicketsLoading(true);
      const response = await api.get('/support/tickets', {
        params: {
          status: filter.status !== 'all' ? filter.status : undefined,
          priority: filter.priority !== 'all' ? filter.priority : undefined,
          category: filter.category !== 'all' ? filter.category : undefined,
          assignedTo: filter.assignedTo !== 'all' ? filter.assignedTo : undefined,
          search: filter.search || undefined,
          page: filter.page,
          limit: filter.limit,
          sortBy: filter.sortBy,
          sortOrder: filter.sortOrder,
        },
      });
      if (response.data) {
        setTickets(response.data.tickets.map((t: any) => ({
          ...t,
          createdAt: new Date(t.createdAt),
          updatedAt: new Date(t.updatedAt),
          resolvedAt: t.resolvedAt ? new Date(t.resolvedAt) : undefined,
          closedAt: t.closedAt ? new Date(t.closedAt) : undefined,
        })));
        setTotalTickets(response.data.total || 0);
      }
    } catch (error) {
      console.error('Failed to fetch tickets:', error);
      setShowToast({
        message: 'Failed to load tickets. Please refresh the page.',
        type: 'error',
      });
    } finally {
      setTicketsLoading(false);
    }
  }, [api, filter]);

  const fetchStats = useCallback(async () => {
    try {
      setStatsLoading(true);
      const response = await api.get('/support/stats');
      if (response.data) {
        setStats(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    } finally {
      setStatsLoading(false);
    }
  }, [api]);

  const fetchAgents = useCallback(async () => {
    try {
      setAgentsLoading(true);
      const response = await api.get('/support/agents');
      if (response.data) {
        setAgents(response.data.agents || []);
      }
    } catch (error) {
      console.error('Failed to fetch agents:', error);
    } finally {
      setAgentsLoading(false);
    }
  }, [api]);

  const fetchSLAMetrics = useCallback(async () => {
    try {
      setSlaLoading(true);
      const response = await api.get('/support/sla');
      if (response.data) {
        setSlaMetrics(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch SLA metrics:', error);
    } finally {
      setSlaLoading(false);
    }
  }, [api]);

  const fetchSurveys = useCallback(async () => {
    try {
      setSurveysLoading(true);
      const response = await api.get('/support/surveys');
      if (response.data) {
        setSurveys(response.data.surveys || []);
      }
    } catch (error) {
      console.error('Failed to fetch surveys:', error);
    } finally {
      setSurveysLoading(false);
    }
  }, [api]);

  const fetchAllData = useCallback(async () => {
    setIsLoading(true);
    setIsRefreshing(true);
    try {
      await Promise.all([
        fetchTickets(),
        fetchStats(),
        fetchAgents(),
        fetchSLAMetrics(),
        fetchSurveys(),
      ]);
    } catch (error) {
      console.error('Failed to fetch support data:', error);
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [fetchTickets, fetchStats, fetchAgents, fetchSLAMetrics, fetchSurveys]);

  // ============================================
  // Handlers - Tickets
  // ============================================

  const handleCreateTicket = useCallback(async () => {
    if (!newTicket.subject || !newTicket.description) {
      setShowToast({
        message: 'Please fill in all required fields.',
        type: 'warning',
      });
      return;
    }

    setIsCreating(true);
    try {
      const response = await api.post('/support/tickets', newTicket);
      if (response.data) {
        const ticketData: SupportTicket = {
          ...response.data,
          createdAt: new Date(response.data.createdAt),
          updatedAt: new Date(response.data.updatedAt),
        };
        setTickets(prev => [ticketData, ...prev]);
        setTotalTickets(prev => prev + 1);
        setShowCreateModal(false);
        setNewTicket({
          subject: '',
          description: '',
          priority: 'medium',
          category: 'general',
          attachments: [],
        });
        setShowToast({
          message: 'Ticket created successfully!',
          type: 'success',
        });
        fetchStats();
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to create ticket.',
        type: 'error',
      });
    } finally {
      setIsCreating(false);
    }
  }, [api, newTicket, fetchStats]);

  const handleDeleteTicket = useCallback(async (ticketId: string) => {
    if (!confirm('Are you sure you want to delete this ticket?')) return;

    try {
      await api.delete(`/support/tickets/${ticketId}`);
      setTickets(prev => prev.filter(t => t.id !== ticketId));
      setTotalTickets(prev => prev - 1);
      setShowToast({
        message: 'Ticket deleted successfully.',
        type: 'info',
      });
      fetchStats();
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to delete ticket.',
        type: 'error',
      });
    }
  }, [api, fetchStats]);

  const handleTicketClick = useCallback((ticketId: string) => {
    router.push(`/support/${ticketId}`);
  }, [router]);

  // ============================================
  // Handlers - Bulk Operations
  // ============================================

  const handleBulkAction = useCallback(async () => {
    if (selectedTickets.length === 0) {
      setShowToast({
        message: 'Please select at least one ticket.',
        type: 'warning',
      });
      return;
    }

    if (!bulkValue) {
      setShowToast({
        message: 'Please select a value for the action.',
        type: 'warning',
      });
      return;
    }

    setIsBulkProcessing(true);
    try {
      const response = await api.post('/support/tickets/bulk', {
        ticketIds: selectedTickets,
        action: bulkAction,
        value: bulkValue,
      });
      if (response.data) {
        setShowToast({
          message: `Bulk ${bulkAction} completed for ${selectedTickets.length} tickets.`,
          type: 'success',
        });
        setSelectedTickets([]);
        setShowBulkModal(false);
        fetchTickets();
        fetchStats();
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to process bulk action.',
        type: 'error',
      });
    } finally {
      setIsBulkProcessing(false);
    }
  }, [api, selectedTickets, bulkAction, bulkValue, fetchTickets, fetchStats]);

  // ============================================
  // Handlers - Filters
  // ============================================

  const handleFilterChange = useCallback((key: keyof TicketFilter, value: any) => {
    setFilter(prev => ({ ...prev, [key]: value, page: 1 }));
  }, []);

  const handleSearch = useCallback((value: string) => {
    setFilter(prev => ({ ...prev, search: value, page: 1 }));
  }, []);

  const handlePageChange = useCallback((page: number) => {
    setFilter(prev => ({ ...prev, page }));
  }, []);

  const handleSortChange = useCallback((sortBy: string) => {
    setFilter(prev => ({
      ...prev,
      sortBy: sortBy as any,
      sortOrder: prev.sortBy === sortBy && prev.sortOrder === 'desc' ? 'asc' : 'desc',
    }));
  }, []);

  // ============================================
  // Handlers - Export
  // ============================================

  const handleExportTickets = useCallback(async (format: 'csv' | 'json' = 'csv') => {
    try {
      const response = await api.get('/support/tickets/export', {
        params: {
          format,
          status: filter.status !== 'all' ? filter.status : undefined,
          priority: filter.priority !== 'all' ? filter.priority : undefined,
          category: filter.category !== 'all' ? filter.category : undefined,
          fromDate: filter.fromDate,
          toDate: filter.toDate,
        },
        responseType: 'blob',
      });
      const blob = new Blob([response.data], {
        type: format === 'csv' ? 'text/csv' : 'application/json',
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `tickets-${Date.now()}.${format}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setShowToast({
        message: `Tickets exported successfully (${format.toUpperCase()})`,
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to export tickets.',
        type: 'error',
      });
    }
  }, [api, filter]);

  // ============================================
  // Handlers - Templates
  // ============================================

  const handleTemplateSelect = useCallback((templateId: string) => {
    const template = templates.find(t => t.id === templateId);
    if (template) {
      setNewTicket({
        ...newTicket,
        subject: template.subject,
        description: template.description,
        priority: template.priority,
        category: template.category,
      });
      setSelectedTemplate(templateId);
    }
  }, [templates, newTicket]);

  // ============================================
  // Effects
  // ============================================

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/authentication/login?callbackUrl=/support');
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
    const debounce = setTimeout(() => {
      fetchTickets();
    }, 300);
    return () => clearTimeout(debounce);
  }, [filter, fetchTickets]);

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      if (!isRefreshing) {
        fetchTickets();
        fetchStats();
      }
    }, 30000);

    return () => clearInterval(interval);
  }, [autoRefresh, fetchTickets, fetchStats, isRefreshing]);

  // ============================================
  // Memoized Computations
  // ============================================

  const statusColors = useMemo(() => ({
    open: 'bg-blue-500/20 text-blue-500 border-blue-500/30',
    in_progress: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30',
    resolved: 'bg-green-500/20 text-green-500 border-green-500/30',
    closed: 'bg-gray-500/20 text-gray-400 border-gray-500/30',
    pending: 'bg-orange-500/20 text-orange-500 border-orange-500/30',
    escalated: 'bg-red-500/20 text-red-500 border-red-500/30',
  }), []);

  const priorityColors = useMemo(() => ({
    low: 'bg-blue-500/20 text-blue-500 border-blue-500/30',
    medium: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30',
    high: 'bg-orange-500/20 text-orange-500 border-orange-500/30',
    critical: 'bg-red-500/20 text-red-500 border-red-500/30',
  }), []);

  const totalPages = useMemo(() => {
    return Math.ceil(totalTickets / filter.limit);
  }, [totalTickets, filter.limit]);

  // ============================================
  // Render
  // ============================================

  if (isLoading && ticketsLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-6">
            <div className="absolute inset-0 border-4 border-cyan-500/30 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-t-cyan-500 rounded-full animate-spin"></div>
            <div className="absolute inset-2 bg-cyan-500/10 rounded-full animate-pulse"></div>
          </div>
          <p className="text-gray-400 text-lg font-medium">Loading Support...</p>
          <p className="text-gray-500 text-sm mt-2">Fetching tickets and analytics</p>
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
            <div className="text-3xl">🎫</div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                Support Center
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                Manage your support tickets and get help
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

          {/* Export Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleExportTickets('csv')}
            className="border-gray-700 hover:border-cyan-500"
          >
            <Download className="w-4 h-4 mr-2" />
            Export
          </Button>

          {/* Create Ticket Button */}
          <Button
            onClick={() => setShowCreateModal(true)}
            className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600"
          >
            <Plus className="w-4 h-4 mr-2" />
            New Ticket
          </Button>
        </div>
      </div>

      {/* ============================================ */}
      {/* STATISTICS CARDS */}
      {/* ============================================ */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6">
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-400">Total Tickets</div>
              <div className="text-xl font-bold text-white">{stats?.total || 0}</div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-cyan-500/20 flex items-center justify-center">
              <Ticket className="w-5 h-5 text-cyan-500" />
            </div>
          </div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-400">Open</div>
              <div className="text-xl font-bold text-blue-500">{stats?.open || 0}</div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-blue-500/20 flex items-center justify-center">
              <TicketCheck className="w-5 h-5 text-blue-500" />
            </div>
          </div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-400">In Progress</div>
              <div className="text-xl font-bold text-yellow-500">{stats?.inProgress || 0}</div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-yellow-500/20 flex items-center justify-center">
              <Clock className="w-5 h-5 text-yellow-500" />
            </div>
          </div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-400">Resolved</div>
              <div className="text-xl font-bold text-green-500">{stats?.resolved || 0}</div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-green-500/20 flex items-center justify-center">
              <CheckCircle className="w-5 h-5 text-green-500" />
            </div>
          </div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-400">Escalated</div>
              <div className="text-xl font-bold text-red-500">{stats?.escalated || 0}</div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-red-500/20 flex items-center justify-center">
              <AlertCircle className="w-5 h-5 text-red-500" />
            </div>
          </div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-xs text-gray-400">Avg Response</div>
              <div className="text-xl font-bold text-purple-500">
                {stats?.avgResponseTime ? formatDuration(stats.avgResponseTime) : 'N/A'}
              </div>
            </div>
            <div className="w-10 h-10 rounded-lg bg-purple-500/20 flex items-center justify-center">
              <ClockIcon className="w-5 h-5 text-purple-500" />
            </div>
          </div>
        </Card>
      </div>

      {/* ============================================ */}
      {/* SLA METRICS */}
      {/* ============================================ */}
      {slaMetrics && (
        <div className="mb-6">
          <Card className="p-4 bg-gray-800 border-gray-700">
            <h3 className="text-sm font-semibold text-gray-300 mb-3">SLA Performance</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="text-xs text-gray-400">SLA Compliance</div>
                <div className="text-lg font-bold text-white">{formatPercentage(slaMetrics.complianceRate)}</div>
                <Progress value={slaMetrics.complianceRate * 100} className="h-1 mt-1" />
              </div>
              <div>
                <div className="text-xs text-gray-400">Avg First Response</div>
                <div className="text-lg font-bold text-white">{formatDuration(slaMetrics.avgFirstResponseTime)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-400">Avg Resolution</div>
                <div className="text-lg font-bold text-white">{formatDuration(slaMetrics.avgResolutionTime)}</div>
              </div>
              <div>
                <div className="text-xs text-gray-400">Breached SLA</div>
                <div className="text-lg font-bold text-red-500">{slaMetrics.breachedCount}</div>
              </div>
            </div>
          </Card>
        </div>
      )}

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
              placeholder="Search tickets..."
              value={filter.search}
              onChange={(e) => handleSearch(e.target.value)}
              className="w-full pl-9 bg-gray-700 border-gray-600 text-white text-sm"
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Status:</span>
          <Select
            value={filter.status}
            onValueChange={(value) => handleFilterChange('status', value)}
            className="w-28 bg-gray-700 border-gray-600 text-sm"
          >
            <option value="all">All</option>
            {Object.entries(TICKET_STATUSES).map(([key, value]) => (
              <option key={key} value={value}>{value.toUpperCase().replace('_', ' ')}</option>
            ))}
          </Select>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Priority:</span>
          <Select
            value={filter.priority}
            onValueChange={(value) => handleFilterChange('priority', value)}
            className="w-24 bg-gray-700 border-gray-600 text-sm"
          >
            <option value="all">All</option>
            {Object.entries(TICKET_PRIORITIES).map(([key, value]) => (
              <option key={key} value={value}>{value.toUpperCase()}</option>
            ))}
          </Select>
        </div>

        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-400">Category:</span>
          <Select
            value={filter.category}
            onValueChange={(value) => handleFilterChange('category', value)}
            className="w-28 bg-gray-700 border-gray-600 text-sm"
          >
            <option value="all">All</option>
            {Object.entries(TICKET_CATEGORIES).map(([key, value]) => (
              <option key={key} value={value}>{value.toUpperCase()}</option>
            ))}
          </Select>
        </div>

        {selectedTickets.length > 0 && (
          <Button
            variant="outline"
            size="sm"
            onClick={() => setShowBulkModal(true)}
            className="border-yellow-500/50 hover:border-yellow-500 text-yellow-400"
          >
            <Filter className="w-4 h-4 mr-2" />
            Bulk Actions ({selectedTickets.length})
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
      {/* MAIN TABS */}
      {/* ============================================ */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-gray-800 border border-gray-700 rounded-lg p-1 w-full overflow-x-auto">
          <TabsTrigger
            value="tickets"
            className="data-[state=active]:bg-cyan-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📋 Tickets ({totalTickets})
          </TabsTrigger>
          <TabsTrigger
            value="analytics"
            className="data-[state=active]:bg-purple-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📊 Analytics
          </TabsTrigger>
          <TabsTrigger
            value="knowledge"
            className="data-[state=active]:bg-green-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📚 Knowledge Base
          </TabsTrigger>
          <TabsTrigger
            value="surveys"
            className="data-[state=active]:bg-yellow-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📝 Surveys
          </TabsTrigger>
        </TabsList>

        {/* ========================================== */}
        {/* TICKETS TAB */}
        {/* ========================================== */}
        <TabsContent value="tickets" className="mt-4">
          {ticketsLoading ? (
            <div className="text-center py-8">
              <Spinner size="lg" className="mx-auto text-cyan-500" />
              <p className="text-gray-400 mt-4">Loading tickets...</p>
            </div>
          ) : tickets.length > 0 ? (
            <>
              <div className="space-y-3">
                {tickets.map((ticket) => (
                  <motion.div
                    key={ticket.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    whileHover={{ scale: 1.01 }}
                    transition={{ duration: 0.2 }}
                  >
                    <Card 
                      className={cn(
                        "p-4 bg-gray-800 border-gray-700 hover:border-cyan-500/50 transition-all cursor-pointer",
                        selectedTickets.includes(ticket.id) && "border-cyan-500 bg-cyan-500/5"
                      )}
                      onClick={() => handleTicketClick(ticket.id)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-3 flex-wrap">
                            <input
                              type="checkbox"
                              checked={selectedTickets.includes(ticket.id)}
                              onChange={(e) => {
                                e.stopPropagation();
                                setSelectedTickets(prev =>
                                  prev.includes(ticket.id)
                                    ? prev.filter(id => id !== ticket.id)
                                    : [...prev, ticket.id]
                                );
                              }}
                              className="rounded border-gray-600 bg-gray-700 text-cyan-500"
                            />
                            <Badge className={cn("text-xs", statusColors[ticket.status as keyof typeof statusColors])}>
                              {ticket.status?.toUpperCase().replace('_', ' ')}
                            </Badge>
                            <Badge className={cn("text-xs", priorityColors[ticket.priority as keyof typeof priorityColors])}>
                              {ticket.priority?.toUpperCase()}
                            </Badge>
                            <span className="text-sm font-medium text-white truncate">{ticket.subject}</span>
                          </div>
                          <div className="flex items-center gap-3 mt-1 text-sm text-gray-400">
                            <span>#{ticket.id.slice(0, 8)}</span>
                            <span>•</span>
                            <span>Category: {ticket.category?.toUpperCase()}</span>
                            <span>•</span>
                            <span>Created: {formatTime(ticket.createdAt)}</span>
                            {ticket.assignedToUser && (
                              <>
                                <span>•</span>
                                <span>Assigned to: {ticket.assignedToUser.name}</span>
                              </>
                            )}
                          </div>
                          <p className="text-sm text-gray-300 mt-2 line-clamp-2">{ticket.description}</p>
                        </div>
                        <div className="flex items-center gap-2 ml-4">
                          <div className="text-right">
                            <div className="text-xs text-gray-400">Replies</div>
                            <div className="text-sm font-medium text-white">{ticket.replyCount || 0}</div>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteTicket(ticket.id);
                            }}
                            className="text-gray-400 hover:text-red-500"
                          >
                            <Trash className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    </Card>
                  </motion.div>
                ))}
              </div>

              {/* Pagination */}
              {totalPages > 1 && (
                <div className="flex items-center justify-between mt-4">
                  <span className="text-sm text-gray-400">
                    Showing {((filter.page - 1) * filter.limit) + 1} to {Math.min(filter.page * filter.limit, totalTickets)} of {totalTickets} tickets
                  </span>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={filter.page <= 1}
                      onClick={() => handlePageChange(filter.page - 1)}
                      className="border-gray-600 hover:border-cyan-500"
                    >
                      <ChevronLeft className="w-4 h-4" />
                    </Button>
                    <span className="text-sm text-gray-400">
                      Page {filter.page} of {totalPages}
                    </span>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={filter.page >= totalPages}
                      onClick={() => handlePageChange(filter.page + 1)}
                      className="border-gray-600 hover:border-cyan-500"
                    >
                      <ChevronRight className="w-4 h-4" />
                    </Button>
                  </div>
                </div>
              )}
            </>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <Ticket className="w-16 h-16 mx-auto mb-4 text-gray-600" />
              <p className="text-lg font-medium">No tickets found</p>
              <p className="text-sm">Create your first support ticket</p>
              <Button
                onClick={() => setShowCreateModal(true)}
                className="mt-4 bg-gradient-to-r from-cyan-500 to-blue-500"
              >
                <Plus className="w-4 h-4 mr-2" />
                Create Ticket
              </Button>
            </div>
          )}
        </TabsContent>

        {/* ========================================== */}
        {/* ANALYTICS TAB */}
        {/* ========================================== */}
        <TabsContent value="analytics" className="mt-4">
          <div className="grid grid-cols-12 gap-6">
            {/* Ticket Distribution */}
            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Ticket Distribution by Status</h3>
                <div className="space-y-3">
                  {stats && Object.entries(stats).map(([key, value]) => {
                    if (key === 'total' || key === 'avgResponseTime' || typeof value !== 'number') return null;
                    const percentage = stats.total > 0 ? (value / stats.total) * 100 : 0;
                    const statusColorsMap: Record<string, string> = {
                      open: 'bg-blue-500',
                      inProgress: 'bg-yellow-500',
                      resolved: 'bg-green-500',
                      closed: 'bg-gray-500',
                      pending: 'bg-orange-500',
                      escalated: 'bg-red-500',
                    };
                    return (
                      <div key={key}>
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-400 capitalize">{key.replace(/([A-Z])/g, ' $1').trim()}</span>
                          <span className="text-white">{value} ({percentage.toFixed(1)}%)</span>
                        </div>
                        <Progress value={percentage} className={cn("h-2", statusColorsMap[key] || 'bg-cyan-500')} />
                      </div>
                    );
                  })}
                </div>
              </Card>
            </div>

            {/* Priority Distribution */}
            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Priority Distribution</h3>
                <div className="space-y-3">
                  {stats && Object.entries(stats).map(([key, value]) => {
                    if (key === 'total' || key === 'avgResponseTime' || typeof value !== 'number') return null;
                    const percentage = stats.total > 0 ? (value / stats.total) * 100 : 0;
                    return (
                      <div key={key}>
                        <div className="flex justify-between text-sm">
                          <span className="text-gray-400 capitalize">{key.replace(/([A-Z])/g, ' $1').trim()}</span>
                          <span className="text-white">{value} ({percentage.toFixed(1)}%)</span>
                        </div>
                        <Progress value={percentage} className="h-2" />
                      </div>
                    );
                  })}
                </div>
              </Card>
            </div>

            {/* Agent Performance */}
            <div className="col-span-12">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Agent Performance</h3>
                {agentsLoading ? (
                  <div className="text-center py-4">
                    <Spinner size="sm" className="mx-auto text-cyan-500" />
                  </div>
                ) : agents.length > 0 ? (
                  <Table>
                    <thead>
                      <tr className="border-b border-gray-700">
                        <th className="text-left text-xs text-gray-400 p-3">Agent</th>
                        <th className="text-right text-xs text-gray-400 p-3">Assigned</th>
                        <th className="text-right text-xs text-gray-400 p-3">Resolved</th>
                        <th className="text-right text-xs text-gray-400 p-3">Avg Response</th>
                        <th className="text-right text-xs text-gray-400 p-3">Satisfaction</th>
                      </tr>
                    </thead>
                    <tbody>
                      {agents.map((agent) => (
                        <tr key={agent.id} className="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
                          <td className="p-3">
                            <div className="flex items-center gap-2">
                              <Avatar size="sm" src={agent.image} alt={agent.name} />
                              <span className="text-white">{agent.name}</span>
                            </div>
                          </td>
                          <td className="p-3 text-right text-white">{agent.assignedTickets}</td>
                          <td className="p-3 text-right text-green-500">{agent.resolvedTickets}</td>
                          <td className="p-3 text-right text-white">{formatDuration(agent.avgResponseTime)}</td>
                          <td className="p-3 text-right">
                            <div className="flex items-center justify-end gap-1">
                              <span className="text-yellow-500">{formatPercentage(agent.satisfactionRating)}</span>
                              <Progress value={agent.satisfactionRating * 100} className="w-16 h-1" />
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </Table>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <p>No agent data available</p>
                  </div>
                )}
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* KNOWLEDGE BASE TAB */}
        {/* ========================================== */}
        <TabsContent value="knowledge" className="mt-4">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 lg:col-span-8">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <div className="flex items-center gap-3 mb-4">
                  <Search className="w-5 h-5 text-gray-400" />
                  <Input
                    type="text"
                    placeholder="Search knowledge base..."
                    className="flex-1 bg-gray-700 border-gray-600 text-white"
                  />
                  <Button variant="primary" className="bg-cyan-500 hover:bg-cyan-600">
                    Search
                  </Button>
                </div>
                <div className="space-y-3">
                  {templates.map((template) => (
                    <Card key={template.id} className="p-4 bg-gray-700/30 border-gray-600 hover:border-cyan-500/50 transition-colors cursor-pointer">
                      <div className="flex items-start gap-3">
                        <FileText className="w-5 h-5 text-cyan-500 mt-0.5" />
                        <div>
                          <h4 className="text-white font-medium">{template.subject}</h4>
                          <p className="text-sm text-gray-400 mt-1">{template.description}</p>
                          <div className="flex items-center gap-3 mt-2 text-xs text-gray-500">
                            <span>Category: {template.category.toUpperCase()}</span>
                            <span>Priority: {template.priority.toUpperCase()}</span>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => {
                                handleTemplateSelect(template.id);
                                setShowCreateModal(true);
                              }}
                              className="text-cyan-400 hover:text-cyan-300"
                            >
                              Use Template
                            </Button>
                          </div>
                        </div>
                      </div>
                    </Card>
                  ))}
                </div>
              </Card>
            </div>
            <div className="col-span-12 lg:col-span-4">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-3">Categories</h3>
                <div className="space-y-2">
                  {Object.entries(TICKET_CATEGORIES).map(([key, value]) => (
                    <button
                      key={key}
                      className="w-full text-left p-2 rounded-lg hover:bg-gray-700 transition-colors flex items-center justify-between"
                    >
                      <span className="text-sm text-gray-300">{value.toUpperCase()}</span>
                      <span className="text-xs text-gray-500">
                        {templates.filter(t => t.category === value).length} articles
                      </span>
                    </button>
                  ))}
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* SURVEYS TAB */}
        {/* ========================================== */}
        <TabsContent value="surveys" className="mt-4">
          {surveysLoading ? (
            <div className="text-center py-8">
              <Spinner size="lg" className="mx-auto text-cyan-500" />
              <p className="text-gray-400 mt-4">Loading surveys...</p>
            </div>
          ) : surveys.length > 0 ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {surveys.map((survey) => (
                <Card key={survey.id} className="p-4 bg-gray-800 border-gray-700">
                  <div className="flex items-start justify-between">
                    <div>
                      <h4 className="text-white font-medium">{survey.title}</h4>
                      <p className="text-sm text-gray-400 mt-1">{survey.description}</p>
                    </div>
                    <Badge className={cn(
                      "text-xs",
                      survey.status === 'active' ? 'bg-green-500/20 text-green-500' : 'bg-gray-500/20 text-gray-400'
                    )}>
                      {survey.status.toUpperCase()}
                    </Badge>
                  </div>
                  <div className="flex items-center gap-4 mt-3 text-sm text-gray-400">
                    <span>Responses: {survey.responseCount || 0}</span>
                    <span>Avg Rating: {survey.avgRating ? `${survey.avgRating.toFixed(1)}/5` : 'N/A'}</span>
                    <span>Created: {formatTime(survey.createdAt)}</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="mt-3 text-cyan-400 hover:text-cyan-300 border border-cyan-500/20 hover:bg-cyan-500/10 w-full"
                  >
                    View Responses
                  </Button>
                </Card>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <MessageSquare className="w-16 h-16 mx-auto mb-4 text-gray-600" />
              <p className="text-lg font-medium">No surveys available</p>
              <p className="text-sm">Customer satisfaction surveys will appear here</p>
            </div>
          )}
        </TabsContent>
      </Tabs>

      {/* ============================================ */}
      {/* CREATE TICKET MODAL */}
      {/* ============================================ */}
      <Modal
        open={showCreateModal}
        onOpenChange={setShowCreateModal}
        title="Create Support Ticket"
        className="max-w-2xl"
      >
        <div className="space-y-4 max-h-[70vh] overflow-y-auto">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Template (optional)</label>
            <Select
              value={selectedTemplate}
              onValueChange={handleTemplateSelect}
              className="w-full bg-gray-700 border-gray-600"
            >
              <option value="">Select a template...</option>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>{template.subject}</option>
              ))}
            </Select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Subject *</label>
            <Input
              value={newTicket.subject}
              onChange={(e) => setNewTicket({ ...newTicket, subject: e.target.value })}
              placeholder="Brief description of your issue"
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Category</label>
              <Select
                value={newTicket.category}
                onValueChange={(value) => setNewTicket({ ...newTicket, category: value as TicketCategory })}
                className="w-full bg-gray-700 border-gray-600"
              >
                {Object.entries(TICKET_CATEGORIES).map(([key, value]) => (
                  <option key={key} value={value}>{value.toUpperCase()}</option>
                ))}
              </Select>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Priority</label>
              <Select
                value={newTicket.priority}
                onValueChange={(value) => setNewTicket({ ...newTicket, priority: value as TicketPriority })}
                className="w-full bg-gray-700 border-gray-600"
              >
                {Object.entries(TICKET_PRIORITIES).map(([key, value]) => (
                  <option key={key} value={value}>{value.toUpperCase()}</option>
                ))}
              </Select>
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Description *</label>
            <Textarea
              value={newTicket.description}
              onChange={(e) => setNewTicket({ ...newTicket, description: e.target.value })}
              placeholder="Detailed description of your issue..."
              className="w-full bg-gray-700 border-gray-600 text-white resize-none"
              rows={5}
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Attachments (optional)</label>
            <div className="border-2 border-dashed border-gray-600 rounded-lg p-4 text-center hover:border-cyan-500 transition-colors cursor-pointer">
              <input
                ref={fileInputRef}
                type="file"
                multiple
                className="hidden"
                onChange={(e) => {
                  const files = e.target.files;
                  if (files) {
                    setNewTicket({ ...newTicket, attachments: Array.from(files) });
                  }
                }}
              />
              <Upload className="w-8 h-8 mx-auto text-gray-500" />
              <p className="text-sm text-gray-400 mt-2">Click to upload or drag and drop</p>
              <p className="text-xs text-gray-500">Max 10 files, 10MB each</p>
              {newTicket.attachments && newTicket.attachments.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-2">
                  {(newTicket.attachments as File[]).map((file, index) => (
                    <div key={index} className="flex items-center gap-1 bg-gray-700 px-2 py-1 rounded text-xs">
                      <span className="text-gray-300">{file.name}</span>
                      <button
                        onClick={() => {
                          const current = newTicket.attachments as File[];
                          setNewTicket({ ...newTicket, attachments: current.filter((_, i) => i !== index) });
                        }}
                        className="text-gray-500 hover:text-red-500"
                      >
                        <X className="w-3 h-3" />
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
            <Button
              variant="outline"
              onClick={() => {
                setShowCreateModal(false);
                setNewTicket({
                  subject: '',
                  description: '',
                  priority: 'medium',
                  category: 'general',
                  attachments: [],
                });
                setSelectedTemplate('');
              }}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateTicket}
              isLoading={isCreating}
              className="bg-gradient-to-r from-cyan-500 to-blue-500"
            >
              <Plus className="w-4 h-4 mr-2" />
              Create Ticket
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
            You have selected <span className="text-white font-medium">{selectedTickets.length}</span> tickets.
          </p>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Action *</label>
            <Select
              value={bulkAction}
              onValueChange={setBulkAction}
              className="w-full bg-gray-700 border-gray-600"
            >
              <option value="status">Change Status</option>
              <option value="priority">Change Priority</option>
              <option value="assign">Assign to Agent</option>
              <option value="delete">Delete Tickets</option>
            </Select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Value *</label>
            {bulkAction === 'status' && (
              <Select
                value={bulkValue}
                onValueChange={setBulkValue}
                className="w-full bg-gray-700 border-gray-600"
              >
                <option value="">Select status...</option>
                {Object.values(TICKET_STATUSES).map((value) => (
                  <option key={value} value={value}>{value.toUpperCase().replace('_', ' ')}</option>
                ))}
              </Select>
            )}
            {bulkAction === 'priority' && (
              <Select
                value={bulkValue}
                onValueChange={setBulkValue}
                className="w-full bg-gray-700 border-gray-600"
              >
                <option value="">Select priority...</option>
                {Object.values(TICKET_PRIORITIES).map((value) => (
                  <option key={value} value={value}>{value.toUpperCase()}</option>
                ))}
              </Select>
            )}
            {bulkAction === 'assign' && (
              <Select
                value={bulkValue}
                onValueChange={setBulkValue}
                className="w-full bg-gray-700 border-gray-600"
              >
                <option value="">Select agent...</option>
                {agents.map((agent) => (
                  <option key={agent.id} value={agent.id}>{agent.name}</option>
                ))}
              </Select>
            )}
            {bulkAction === 'delete' && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
                <p className="text-sm text-red-500 flex items-center gap-2">
                  <AlertCircle className="w-5 h-5" />
                  This action cannot be undone.
                </p>
              </div>
            )}
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => setShowBulkModal(false)}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handleBulkAction}
              isLoading={isBulkProcessing}
              className="bg-gradient-to-r from-yellow-500 to-orange-500"
            >
              Apply to {selectedTickets.length} Tickets
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

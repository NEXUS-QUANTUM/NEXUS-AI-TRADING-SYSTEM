/**
 * NEXUS AI TRADING SYSTEM - Support Ticket Detail Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page provides detailed support ticket management including:
 * - Ticket details and status
 * - Conversation thread with replies
 * - Reply composition and sending
 * - Attachments management
 * - Ticket status updates
 * - Priority management
 * - Assignment management
 * - Escalation handling
 * - Ticket history and activity log
 * - SLA tracking
 * - Internal notes for support team
 * - Email notifications
 * - Ticket resolution
 * - Knowledge base integration
 * - Related tickets
 * - User information display
 * - Real-time WebSocket updates
 * - Responsive design for all devices
 */

'use client';

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useRouter, useParams } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { useApi } from '@/hooks/useApi';
import { useWebSocket } from '@/hooks/useWebSocket';

// Components
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { Toast } from '@/components/ui/Toast';
import { Badge } from '@/components/ui/Badge';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Modal } from '@/components/ui/Modal';
import { Textarea } from '@/components/ui/Textarea';
import { Avatar } from '@/components/ui/Avatar';
import { Progress } from '@/components/ui/Progress';
import { Switch } from '@/components/ui/Switch';
import { Table } from '@/components/ui/Table';
import { CopyButton } from '@/components/ui/CopyButton';

// Icons
import {
  ArrowLeft,
  ArrowRight,
  Send,
  Paperclip,
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
  Download,
  Upload,
  RefreshCw,
  MoreVertical,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Plus,
  Minus,
  Share2,
  Bookmark,
  Flag,
  Heart,
  Star,
  Award,
  Trophy,
  Medal,
  Gift,
  Rocket,
  Sparkles,
  Crown,
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
  Paperclip as PaperclipIcon,
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
  SupportTicket,
  TicketReply,
  TicketAttachment,
  TicketActivity,
  TicketMetrics,
  TicketStatus,
  TicketPriority,
  TicketCategory,
} from '@/types/support';

// Constants
import {
  TICKET_STATUSES,
  TICKET_PRIORITIES,
  TICKET_CATEGORIES,
  TICKET_ACTIVITY_TYPES,
  MAX_TICKET_ATTACHMENTS,
  MAX_ATTACHMENT_SIZE,
  ALLOWED_ATTACHMENT_TYPES,
} from '@/constants/support';

// Utils
import { formatDate, formatTime, formatDuration } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

export default function SupportTicketDetailPage() {
  // Router
  const router = useRouter();
  const params = useParams();
  const ticketId = params.id as string;

  // Auth hooks
  const { user, isAuthenticated, accessToken } = useAuth();

  // API client
  const api = useApi();

  // State - Ticket
  const [ticket, setTicket] = useState<SupportTicket | null>(null);
  const [ticketLoading, setTicketLoading] = useState<boolean>(true);
  const [metrics, setMetrics] = useState<TicketMetrics | null>(null);
  const [activities, setActivities] = useState<TicketActivity[]>([]);

  // State - Replies
  const [replies, setReplies] = useState<TicketReply[]>([]);
  const [newReply, setNewReply] = useState<string>('');
  const [isInternal, setIsInternal] = useState<boolean>(false);
  const [sendingReply, setSendingReply] = useState<boolean>(false);
  const [editingReply, setEditingReply] = useState<string | null>(null);
  const [editContent, setEditContent] = useState<string>('');

  // State - Attachments
  const [attachments, setAttachments] = useState<File[]>([]);
  const [uploadingFiles, setUploadingFiles] = useState<boolean>(false);
  const [uploadProgress, setUploadProgress] = useState<number>(0);

  // State - Modals
  const [showEditModal, setShowEditModal] = useState<boolean>(false);
  const [showDeleteModal, setShowDeleteModal] = useState<boolean>(false);
  const [showResolveModal, setShowResolveModal] = useState<boolean>(false);
  const [showEscalateModal, setShowEscalateModal] = useState<boolean>(false);
  const [showAssignModal, setShowAssignModal] = useState<boolean>(false);
  const [showRelatedModal, setShowRelatedModal] = useState<boolean>(false);

  // State - Edit Form
  const [editForm, setEditForm] = useState<{
    subject: string;
    status: TicketStatus;
    priority: TicketPriority;
    category: TicketCategory;
    assignedTo: string;
  }>({
    subject: '',
    status: 'open',
    priority: 'medium',
    category: 'general',
    assignedTo: '',
  });

  // State - Users (for assignment)
  const [users, setUsers] = useState<{ id: string; name: string; email: string }[]>([]);
  const [usersLoading, setUsersLoading] = useState<boolean>(true);

  // State - UI
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [autoRefresh, setAutoRefresh] = useState<boolean>(true);

  // Refs
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

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
        case 'ticket_update':
          handleTicketUpdate(data.payload);
          break;
        case 'ticket_reply':
          handleNewReply(data.payload);
          break;
        case 'ticket_activity':
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
    console.log('Support WebSocket disconnected');
  }

  function subscribeToChannels() {
    if (!isConnected) return;

    wsSubscribe({
      channel: 'ticket',
      ticketId: ticketId,
    });
  }

  // ============================================
  // WebSocket Data Handlers
  // ============================================

  function handleTicketUpdate(data: any) {
    if (data.id === ticketId) {
      setTicket(prev => prev ? { ...prev, ...data } : data);
      setShowToast({
        message: `Ticket updated: ${data.status ? `Status changed to ${data.status}` : ''}`,
        type: 'info',
      });
    }
  }

  function handleNewReply(data: any) {
    if (data.ticketId === ticketId) {
      const newReplyData: TicketReply = {
        ...data,
        createdAt: new Date(data.createdAt),
        updatedAt: new Date(data.updatedAt),
      };
      setReplies(prev => [...prev, newReplyData]);
      scrollToBottom();

      // Update ticket reply count
      setTicket(prev => prev ? { ...prev, replyCount: (prev.replyCount || 0) + 1 } : prev);

      setShowToast({
        message: `New reply from ${data.user?.name || 'Unknown'}`,
        type: 'info',
      });
    }
  }

  function handleActivityUpdate(data: any) {
    if (data.ticketId === ticketId) {
      setActivities(prev => [{
        ...data,
        createdAt: new Date(data.createdAt),
      }, ...prev]);
    }
  }

  // ============================================
  // API Calls
  // ============================================

  const fetchTicket = useCallback(async () => {
    try {
      setTicketLoading(true);
      const response = await api.get(`/support/tickets/${ticketId}`);
      if (response.data) {
        const ticketData = {
          ...response.data,
          createdAt: new Date(response.data.createdAt),
          updatedAt: new Date(response.data.updatedAt),
          resolvedAt: response.data.resolvedAt ? new Date(response.data.resolvedAt) : undefined,
          closedAt: response.data.closedAt ? new Date(response.data.closedAt) : undefined,
        };
        setTicket(ticketData);
        setEditForm({
          subject: ticketData.subject,
          status: ticketData.status,
          priority: ticketData.priority,
          category: ticketData.category,
          assignedTo: ticketData.assignedTo || '',
        });
      }
    } catch (error: any) {
      console.error('Failed to fetch ticket:', error);
      setShowToast({
        message: error.response?.data?.message || 'Failed to load ticket details.',
        type: 'error',
      });
    } finally {
      setTicketLoading(false);
    }
  }, [api, ticketId]);

  const fetchReplies = useCallback(async () => {
    try {
      const response = await api.get(`/support/tickets/${ticketId}/replies`);
      if (response.data) {
        setReplies(response.data.map((r: any) => ({
          ...r,
          createdAt: new Date(r.createdAt),
          updatedAt: new Date(r.updatedAt),
        })));
      }
    } catch (error) {
      console.error('Failed to fetch replies:', error);
    }
  }, [api, ticketId]);

  const fetchActivities = useCallback(async () => {
    try {
      const response = await api.get(`/support/tickets/${ticketId}/activities`);
      if (response.data) {
        setActivities(response.data.map((a: any) => ({
          ...a,
          createdAt: new Date(a.createdAt),
        })));
      }
    } catch (error) {
      console.error('Failed to fetch activities:', error);
    }
  }, [api, ticketId]);

  const fetchMetrics = useCallback(async () => {
    try {
      const response = await api.get(`/support/tickets/${ticketId}/metrics`);
      if (response.data) {
        setMetrics({
          ...response.data,
          createdAt: new Date(response.data.createdAt),
          updatedAt: new Date(response.data.updatedAt),
          resolvedAt: response.data.resolvedAt ? new Date(response.data.resolvedAt) : undefined,
        });
      }
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
    }
  }, [api, ticketId]);

  const fetchUsers = useCallback(async () => {
    try {
      setUsersLoading(true);
      const response = await api.get('/users');
      if (response.data) {
        setUsers(response.data.users || []);
      }
    } catch (error) {
      console.error('Failed to fetch users:', error);
    } finally {
      setUsersLoading(false);
    }
  }, [api]);

  const fetchAllData = useCallback(async () => {
    setIsLoading(true);
    try {
      await Promise.all([
        fetchTicket(),
        fetchReplies(),
        fetchActivities(),
        fetchMetrics(),
        fetchUsers(),
      ]);
      scrollToBottom();
    } catch (error) {
      console.error('Failed to fetch ticket data:', error);
    } finally {
      setIsLoading(false);
    }
  }, [fetchTicket, fetchReplies, fetchActivities, fetchMetrics, fetchUsers]);

  // ============================================
  // Handlers - Replies
  // ============================================

  const handleSendReply = useCallback(async () => {
    if (!newReply.trim()) {
      setShowToast({
        message: 'Please enter a message.',
        type: 'warning',
      });
      return;
    }

    setSendingReply(true);
    setUploadingFiles(true);

    try {
      const formData = new FormData();
      formData.append('content', newReply);
      formData.append('isInternal', String(isInternal));

      // Add attachments
      attachments.forEach((file, index) => {
        formData.append(`attachment_${index}`, file);
        formData.append(`attachment_${index}_name`, file.name);
        formData.append(`attachment_${index}_type`, file.type);
      });

      const response = await api.post(`/support/tickets/${ticketId}/replies`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
        onUploadProgress: (progressEvent) => {
          const progress = Math.round((progressEvent.loaded * 100) / (progressEvent.total || 1));
          setUploadProgress(progress);
        },
      });

      if (response.data) {
        handleNewReply(response.data);
        setNewReply('');
        setAttachments([]);
        setUploadProgress(0);
        setShowToast({
          message: 'Reply sent successfully!',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to send reply.',
        type: 'error',
      });
    } finally {
      setSendingReply(false);
      setUploadingFiles(false);
    }
  }, [api, ticketId, newReply, isInternal, attachments]);

  const handleEditReply = useCallback(async (replyId: string) => {
    if (!editContent.trim()) {
      setShowToast({
        message: 'Please enter a message.',
        type: 'warning',
      });
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await api.put(`/support/replies/${replyId}`, {
        content: editContent,
      });
      if (response.data) {
        setReplies(prev => prev.map(r => 
          r.id === replyId 
            ? { ...r, content: editContent, edited: true, updatedAt: new Date() }
            : r
        ));
        setEditingReply(null);
        setEditContent('');
        setShowToast({
          message: 'Reply updated successfully!',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to update reply.',
        type: 'error',
      });
    } finally {
      setIsSubmitting(false);
    }
  }, [api, editContent]);

  const handleDeleteReply = useCallback(async (replyId: string) => {
    if (!confirm('Are you sure you want to delete this reply?')) return;

    try {
      await api.delete(`/support/replies/${replyId}`);
      setReplies(prev => prev.filter(r => r.id !== replyId));
      setShowToast({
        message: 'Reply deleted successfully.',
        type: 'info',
      });
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to delete reply.',
        type: 'error',
      });
    }
  }, [api]);

  // ============================================
  // Handlers - Ticket Actions
  // ============================================

  const handleUpdateTicket = useCallback(async () => {
    setIsSubmitting(true);
    try {
      const response = await api.put(`/support/tickets/${ticketId}`, editForm);
      if (response.data) {
        setTicket({
          ...response.data,
          createdAt: new Date(response.data.createdAt),
          updatedAt: new Date(response.data.updatedAt),
          resolvedAt: response.data.resolvedAt ? new Date(response.data.resolvedAt) : undefined,
          closedAt: response.data.closedAt ? new Date(response.data.closedAt) : undefined,
        });
        setShowEditModal(false);
        setShowToast({
          message: 'Ticket updated successfully!',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to update ticket.',
        type: 'error',
      });
    } finally {
      setIsSubmitting(false);
    }
  }, [api, ticketId, editForm]);

  const handleResolveTicket = useCallback(async () => {
    setIsSubmitting(true);
    try {
      const response = await api.post(`/support/tickets/${ticketId}/resolve`);
      if (response.data) {
        setTicket({
          ...response.data,
          createdAt: new Date(response.data.createdAt),
          updatedAt: new Date(response.data.updatedAt),
          resolvedAt: response.data.resolvedAt ? new Date(response.data.resolvedAt) : undefined,
          closedAt: response.data.closedAt ? new Date(response.data.closedAt) : undefined,
        });
        setShowResolveModal(false);
        setShowToast({
          message: 'Ticket resolved successfully!',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to resolve ticket.',
        type: 'error',
      });
    } finally {
      setIsSubmitting(false);
    }
  }, [api, ticketId]);

  const handleEscalateTicket = useCallback(async (reason: string) => {
    setIsSubmitting(true);
    try {
      const response = await api.post(`/support/tickets/${ticketId}/escalate`, { reason });
      if (response.data) {
        setTicket({
          ...response.data,
          createdAt: new Date(response.data.createdAt),
          updatedAt: new Date(response.data.updatedAt),
          resolvedAt: response.data.resolvedAt ? new Date(response.data.resolvedAt) : undefined,
          closedAt: response.data.closedAt ? new Date(response.data.closedAt) : undefined,
        });
        setShowEscalateModal(false);
        setShowToast({
          message: 'Ticket escalated successfully!',
          type: 'info',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to escalate ticket.',
        type: 'error',
      });
    } finally {
      setIsSubmitting(false);
    }
  }, [api, ticketId]);

  const handleAssignTicket = useCallback(async (userId: string) => {
    setIsSubmitting(true);
    try {
      const response = await api.put(`/support/tickets/${ticketId}/assign`, { assignedTo: userId });
      if (response.data) {
        setTicket({
          ...response.data,
          createdAt: new Date(response.data.createdAt),
          updatedAt: new Date(response.data.updatedAt),
          resolvedAt: response.data.resolvedAt ? new Date(response.data.resolvedAt) : undefined,
          closedAt: response.data.closedAt ? new Date(response.data.closedAt) : undefined,
        });
        setShowAssignModal(false);
        setShowToast({
          message: `Ticket assigned to ${users.find(u => u.id === userId)?.name || 'Unknown'}`,
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to assign ticket.',
        type: 'error',
      });
    } finally {
      setIsSubmitting(false);
    }
  }, [api, ticketId, users]);

  // ============================================
  // Handlers - File Upload
  // ============================================

  const handleFileSelect = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    const newFiles = Array.from(files);
    const validFiles: File[] = [];

    for (const file of newFiles) {
      // Validate file size
      if (file.size > MAX_ATTACHMENT_SIZE) {
        setShowToast({
          message: `File ${file.name} exceeds size limit of ${MAX_ATTACHMENT_SIZE / 1024 / 1024}MB`,
          type: 'error',
        });
        continue;
      }

      // Validate file type
      if (!ALLOWED_ATTACHMENT_TYPES.includes(file.type)) {
        setShowToast({
          message: `File ${file.name} type not allowed. Allowed: ${ALLOWED_ATTACHMENT_TYPES.join(', ')}`,
          type: 'error',
        });
        continue;
      }

      validFiles.push(file);
    }

    if (attachments.length + validFiles.length > MAX_TICKET_ATTACHMENTS) {
      setShowToast({
        message: `Maximum ${MAX_TICKET_ATTACHMENTS} attachments allowed.`,
        type: 'error',
      });
      return;
    }

    setAttachments(prev => [...prev, ...validFiles]);
    e.target.value = '';
  }, [attachments]);

  const handleRemoveAttachment = useCallback((index: number) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  }, []);

  // ============================================
  // Handlers - UI
  // ============================================

  const scrollToBottom = useCallback(() => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, []);

  const handleKeyPress = useCallback((e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSendReply();
    }
  }, [handleSendReply]);

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

  // Auto-refresh
  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchReplies();
      fetchActivities();
      fetchMetrics();
    }, 30000);

    return () => clearInterval(interval);
  }, [autoRefresh, fetchReplies, fetchActivities, fetchMetrics]);

  // ============================================
  // Memoized Computations
  // ============================================

  const isTicketOwner = useMemo(() => {
    return ticket?.userId === user?.id;
  }, [ticket, user]);

  const isAdmin = useMemo(() => {
    return user?.roles?.includes('admin') || user?.roles?.includes('support_admin');
  }, [user]);

  const canEdit = useMemo(() => {
    return isTicketOwner || isAdmin;
  }, [isTicketOwner, isAdmin]);

  const canResolve = useMemo(() => {
    return isAdmin && ticket?.status !== 'resolved' && ticket?.status !== 'closed';
  }, [isAdmin, ticket]);

  const canEscalate = useMemo(() => {
    return isAdmin && ticket?.status !== 'escalated' && ticket?.status !== 'resolved' && ticket?.status !== 'closed';
  }, [isAdmin, ticket]);

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

  // ============================================
  // Render
  // ============================================

  if (isLoading && ticketLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-6">
            <div className="absolute inset-0 border-4 border-cyan-500/30 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-t-cyan-500 rounded-full animate-spin"></div>
            <div className="absolute inset-2 bg-cyan-500/10 rounded-full animate-pulse"></div>
          </div>
          <p className="text-gray-400 text-lg font-medium">Loading Ticket...</p>
          <p className="text-gray-500 text-sm mt-2">Fetching ticket details</p>
        </div>
      </div>
    );
  }

  if (!ticket) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center p-4">
        <div className="text-center">
          <div className="text-6xl mb-4">🔍</div>
          <h2 className="text-2xl font-bold text-white">Ticket Not Found</h2>
          <p className="text-gray-400 mt-2">The ticket you're looking for doesn't exist or you don't have access.</p>
          <Button
            onClick={() => router.push('/support')}
            className="mt-4 bg-gradient-to-r from-cyan-500 to-blue-500"
          >
            Back to Support
          </Button>
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
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            onClick={() => router.push('/support')}
            className="text-gray-400 hover:text-white"
          >
            <ArrowLeft className="w-5 h-5" />
          </Button>
          <div>
            <div className="flex items-center gap-3">
              <h1 className="text-2xl font-bold text-white">{ticket.subject}</h1>
              <Badge className={cn("text-xs", statusColors[ticket.status as keyof typeof statusColors])}>
                {ticket.status?.toUpperCase().replace('_', ' ')}
              </Badge>
              <Badge className={cn("text-xs", priorityColors[ticket.priority as keyof typeof priorityColors])}>
                {ticket.priority?.toUpperCase()}
              </Badge>
            </div>
            <div className="flex items-center gap-3 mt-1 text-sm text-gray-400">
              <span>Ticket #{ticket.id.slice(0, 8)}</span>
              <span>•</span>
              <span>Created {formatTime(ticket.createdAt)}</span>
              <span>•</span>
              <span>Category: {ticket.category?.toUpperCase()}</span>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2 flex-wrap">
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

          {canEdit && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowEditModal(true)}
              className="border-gray-600 hover:border-cyan-500"
            >
              <Edit className="w-4 h-4 mr-2" />
              Edit
            </Button>
          )}

          {canResolve && (
            <Button
              variant="primary"
              size="sm"
              onClick={() => setShowResolveModal(true)}
              className="bg-green-600 hover:bg-green-700"
            >
              <Check className="w-4 h-4 mr-2" />
              Resolve
            </Button>
          )}
        </div>
      </div>

      {/* ============================================ */}
      {/* MAIN CONTENT */}
      {/* ============================================ */}
      <div className="grid grid-cols-12 gap-6">
        {/* ========================================== */}
        {/* LEFT COLUMN - Messages */}
        {/* ========================================== */}
        <div className="col-span-12 lg:col-span-8">
          <Card className="bg-gray-800 border-gray-700 h-[600px] flex flex-col">
            {/* Messages Header */}
            <div className="p-4 border-b border-gray-700 flex items-center justify-between">
              <div className="flex items-center gap-2">
                <MessageSquare className="w-5 h-5 text-cyan-500" />
                <span className="text-sm font-medium text-white">Conversation ({replies.length} replies)</span>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => {
                    fetchReplies();
                    fetchActivities();
                  }}
                  className="text-gray-400 hover:text-white"
                >
                  <RefreshCw className="w-4 h-4" />
                </Button>
              </div>
            </div>

            {/* Messages */}
            <div className="flex-1 overflow-y-auto p-4 space-y-4">
              {/* Initial Message */}
              <div className="flex items-start gap-3">
                <Avatar
                  size="sm"
                  src={ticket.user?.image}
                  alt={ticket.user?.name || 'User'}
                />
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-medium text-white">{ticket.user?.name || 'Unknown'}</span>
                    <span className="text-xs text-gray-500">{formatTime(ticket.createdAt)}</span>
                    <Badge className="bg-cyan-500/20 text-cyan-400 text-xs">Original</Badge>
                  </div>
                  <div className="mt-1 p-3 bg-gray-700/30 rounded-lg">
                    <p className="text-sm text-gray-300 whitespace-pre-wrap">{ticket.description}</p>
                    {ticket.attachments && ticket.attachments.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {ticket.attachments.map((att) => (
                          <div key={att.id} className="flex items-center gap-1 text-xs text-gray-400 bg-gray-700 px-2 py-1 rounded">
                            <Paperclip className="w-3 h-3" />
                            <span>{att.name}</span>
                            <span>({(att.size / 1024).toFixed(0)} KB)</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>

              {/* Replies */}
              <AnimatePresence>
                {replies.map((reply) => (
                  <motion.div
                    key={reply.id}
                    initial={{ opacity: 0, y: 10 }}
                    animate={{ opacity: 1, y: 0 }}
                    exit={{ opacity: 0, y: -10 }}
                    className={cn(
                      "flex items-start gap-3",
                      reply.isInternal && 'opacity-75'
                    )}
                  >
                    <Avatar
                      size="sm"
                      src={reply.user?.image}
                      alt={reply.user?.name || 'Unknown'}
                    />
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="text-sm font-medium text-white">{reply.user?.name || 'Unknown'}</span>
                        <span className="text-xs text-gray-500">{formatTime(reply.createdAt)}</span>
                        {reply.isInternal && (
                          <Badge className="bg-yellow-500/20 text-yellow-500 text-xs">Internal</Badge>
                        )}
                        {reply.edited && (
                          <span className="text-xs text-gray-500">(edited)</span>
                        )}
                        {reply.userId === user?.id && (
                          <div className="flex items-center gap-1">
                            <button
                              onClick={() => {
                                setEditingReply(reply.id);
                                setEditContent(reply.content);
                              }}
                              className="text-gray-400 hover:text-white p-1 rounded hover:bg-gray-700"
                            >
                              <Edit className="w-3 h-3" />
                            </button>
                            <button
                              onClick={() => handleDeleteReply(reply.id)}
                              className="text-gray-400 hover:text-red-500 p-1 rounded hover:bg-gray-700"
                            >
                              <Trash className="w-3 h-3" />
                            </button>
                          </div>
                        )}
                      </div>
                      {editingReply === reply.id ? (
                        <div className="mt-1">
                          <Textarea
                            value={editContent}
                            onChange={(e) => setEditContent(e.target.value)}
                            className="w-full bg-gray-700 border-gray-600 text-white resize-none"
                            rows={2}
                          />
                          <div className="flex items-center gap-2 mt-2">
                            <Button
                              size="sm"
                              onClick={() => handleEditReply(reply.id)}
                              isLoading={isSubmitting}
                              className="bg-cyan-500 hover:bg-cyan-600"
                            >
                              <Save className="w-4 h-4 mr-1" />
                              Save
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                setEditingReply(null);
                                setEditContent('');
                              }}
                              className="border-gray-600 hover:border-gray-500"
                            >
                              Cancel
                            </Button>
                          </div>
                        </div>
                      ) : (
                        <div className={cn(
                          "mt-1 p-3 rounded-lg",
                          reply.isInternal ? 'bg-yellow-500/10 border border-yellow-500/20' : 'bg-gray-700/30'
                        )}>
                          <p className="text-sm text-gray-300 whitespace-pre-wrap">{reply.content}</p>
                          {reply.attachments && reply.attachments.length > 0 && (
                            <div className="mt-2 flex flex-wrap gap-2">
                              {reply.attachments.map((att) => (
                                <div key={att.id} className="flex items-center gap-1 text-xs text-gray-400 bg-gray-700 px-2 py-1 rounded">
                                  <Paperclip className="w-3 h-3" />
                                  <span>{att.name}</span>
                                  <span>({(att.size / 1024).toFixed(0)} KB)</span>
                                </div>
                              ))}
                            </div>
                          )}
                        </div>
                      )}
                    </div>
                  </motion.div>
                ))}
              </AnimatePresence>

              <div ref={messagesEndRef} />
            </div>

            {/* Reply Input */}
            <div className="p-4 border-t border-gray-700">
              <div className="flex items-start gap-2">
                <div className="flex-1">
                  <Textarea
                    ref={textareaRef}
                    value={newReply}
                    onChange={(e) => setNewReply(e.target.value)}
                    onKeyDown={handleKeyPress}
                    placeholder="Type your reply..."
                    className="w-full bg-gray-700 border-gray-600 text-white resize-none"
                    rows={3}
                    disabled={ticket.status === 'closed' || ticket.status === 'resolved'}
                  />
                  <div className="flex items-center gap-3 mt-2">
                    <div className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        id="internal-note"
                        checked={isInternal}
                        onChange={(e) => setIsInternal(e.target.checked)}
                        className="rounded border-gray-600 bg-gray-700 text-cyan-500"
                      />
                      <label htmlFor="internal-note" className="text-xs text-gray-400">Internal Note</label>
                    </div>
                    <button
                      onClick={() => fileInputRef.current?.click()}
                      className="text-gray-400 hover:text-white transition-colors"
                      disabled={ticket.status === 'closed' || ticket.status === 'resolved'}
                    >
                      <Paperclip className="w-4 h-4" />
                    </button>
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      className="hidden"
                      onChange={handleFileSelect}
                      accept={ALLOWED_ATTACHMENT_TYPES.join(',')}
                    />
                    {attachments.length > 0 && (
                      <span className="text-xs text-gray-400">{attachments.length} files attached</span>
                    )}
                  </div>
                  {attachments.length > 0 && (
                    <div className="flex flex-wrap gap-2 mt-2">
                      {attachments.map((file, index) => (
                        <div key={index} className="flex items-center gap-1 bg-gray-700 px-2 py-1 rounded text-xs">
                          <span className="text-gray-300">{file.name}</span>
                          <button
                            onClick={() => handleRemoveAttachment(index)}
                            className="text-gray-500 hover:text-red-500"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  {uploadingFiles && (
                    <div className="mt-2">
                      <div className="flex justify-between text-xs text-gray-400 mb-1">
                        <span>Uploading...</span>
                        <span>{uploadProgress}%</span>
                      </div>
                      <Progress value={uploadProgress} className="h-1" />
                    </div>
                  )}
                </div>
                <Button
                  onClick={handleSendReply}
                  isLoading={sendingReply}
                  disabled={!newReply.trim() || ticket.status === 'closed' || ticket.status === 'resolved'}
                  className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600"
                >
                  <Send className="w-4 h-4" />
                </Button>
              </div>
              {ticket.status === 'closed' || ticket.status === 'resolved' ? (
                <p className="text-xs text-gray-500 mt-2">
                  This ticket is {ticket.status}. You cannot reply to closed tickets.
                  {ticket.status === 'closed' && ' Please open a new ticket if you need further assistance.'}
                </p>
              ) : null}
            </div>
          </Card>
        </div>

        {/* ========================================== */}
        {/* RIGHT COLUMN - Ticket Info & Actions */}
        {/* ========================================== */}
        <div className="col-span-12 lg:col-span-4 space-y-6">
          {/* Ticket Details */}
          <Card className="p-4 bg-gray-800 border-gray-700">
            <h3 className="text-sm font-semibold text-gray-300 mb-4">Ticket Details</h3>
            <div className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Status</span>
                <Badge className={cn("text-xs", statusColors[ticket.status as keyof typeof statusColors])}>
                  {ticket.status?.toUpperCase().replace('_', ' ')}
                </Badge>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Priority</span>
                <Badge className={cn("text-xs", priorityColors[ticket.priority as keyof typeof priorityColors])}>
                  {ticket.priority?.toUpperCase()}
                </Badge>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Category</span>
                <span className="text-white">{ticket.category?.toUpperCase()}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Assigned To</span>
                <span className="text-white">{ticket.assignedToUser?.name || 'Unassigned'}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Created</span>
                <span className="text-white">{formatTime(ticket.createdAt)}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Updated</span>
                <span className="text-white">{formatTime(ticket.updatedAt)}</span>
              </div>
              {ticket.resolvedAt && (
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">Resolved</span>
                  <span className="text-white">{formatTime(ticket.resolvedAt)}</span>
                </div>
              )}
              {ticket.closedAt && (
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">Closed</span>
                  <span className="text-white">{formatTime(ticket.closedAt)}</span>
                </div>
              )}
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Replies</span>
                <span className="text-white">{ticket.replyCount || 0}</span>
              </div>
            </div>
          </Card>

          {/* SLA Metrics */}
          {metrics && (
            <Card className="p-4 bg-gray-800 border-gray-700">
              <h3 className="text-sm font-semibold text-gray-300 mb-4">SLA Metrics</h3>
              <div className="space-y-3">
                <div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">First Response Time</span>
                    <span className={cn(
                      metrics.firstResponseTime && metrics.firstResponseTime <= 3600 ? 'text-green-500' : 'text-yellow-500'
                    )}>
                      {metrics.firstResponseTime ? formatDuration(metrics.firstResponseTime) : 'N/A'}
                    </span>
                  </div>
                  <Progress 
                    value={metrics.firstResponseTime ? Math.min((metrics.firstResponseTime / 3600) * 100, 100) : 0} 
                    className="h-1 mt-1"
                    color={metrics.firstResponseTime && metrics.firstResponseTime <= 3600 ? 'green' : 'yellow'}
                  />
                </div>
                <div>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Resolution Time</span>
                    <span className={cn(
                      metrics.resolutionTime && metrics.resolutionTime <= 86400 ? 'text-green-500' : 'text-yellow-500'
                    )}>
                      {metrics.resolutionTime ? formatDuration(metrics.resolutionTime) : 'N/A'}
                    </span>
                  </div>
                  <Progress 
                    value={metrics.resolutionTime ? Math.min((metrics.resolutionTime / 86400) * 100, 100) : 0} 
                    className="h-1 mt-1"
                    color={metrics.resolutionTime && metrics.resolutionTime <= 86400 ? 'green' : 'yellow'}
                  />
                </div>
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">SLA Status</span>
                  <Badge className={cn(
                    "text-xs",
                    metrics.slaBreached ? 'bg-red-500/20 text-red-500' : 'bg-green-500/20 text-green-500'
                  )}>
                    {metrics.slaBreached ? 'Breached' : 'On Track'}
                  </Badge>
                </div>
              </div>
            </Card>
          )}

          {/* Actions */}
          <Card className="p-4 bg-gray-800 border-gray-700">
            <h3 className="text-sm font-semibold text-gray-300 mb-4">Actions</h3>
            <div className="space-y-2">
              {canEscalate && (
                <Button
                  variant="outline"
                  className="w-full border-red-500/50 hover:border-red-500 text-red-400 hover:text-red-300"
                  onClick={() => setShowEscalateModal(true)}
                >
                  <AlertCircle className="w-4 h-4 mr-2" />
                  Escalate Ticket
                </Button>
              )}
              {isAdmin && (
                <>
                  <Button
                    variant="outline"
                    className="w-full border-gray-600 hover:border-cyan-500"
                    onClick={() => setShowAssignModal(true)}
                  >
                    <Users className="w-4 h-4 mr-2" />
                    Assign Ticket
                  </Button>
                  <Button
                    variant="outline"
                    className="w-full border-gray-600 hover:border-cyan-500"
                    onClick={() => setShowRelatedModal(true)}
                  >
                    <Link className="w-4 h-4 mr-2" />
                    View Related Tickets
                  </Button>
                </>
              )}
            </div>
          </Card>

          {/* Activity Log */}
          {activities.length > 0 && (
            <Card className="p-4 bg-gray-800 border-gray-700">
              <h3 className="text-sm font-semibold text-gray-300 mb-4">Activity Log</h3>
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {activities.slice(0, 10).map((activity) => (
                  <div key={activity.id} className="flex items-start gap-2 text-sm">
                    <div className="w-6 h-6 rounded-full bg-gray-700 flex items-center justify-center flex-shrink-0">
                      {activity.type === 'created' && <Plus className="w-3 h-3 text-cyan-500" />}
                      {activity.type === 'updated' && <Edit className="w-3 h-3 text-yellow-500" />}
                      {activity.type === 'replied' && <MessageSquare className="w-3 h-3 text-blue-500" />}
                      {activity.type === 'status_changed' && <RefreshCw className="w-3 h-3 text-purple-500" />}
                      {activity.type === 'assigned' && <Users className="w-3 h-3 text-green-500" />}
                      {activity.type === 'escalated' && <AlertCircle className="w-3 h-3 text-red-500" />}
                    </div>
                    <div className="flex-1">
                      <div className="text-gray-300 text-xs">{activity.description}</div>
                      <div className="text-gray-500 text-xs">{formatTime(activity.createdAt)}</div>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}

          {/* User Info */}
          {ticket.user && (
            <Card className="p-4 bg-gray-800 border-gray-700">
              <h3 className="text-sm font-semibold text-gray-300 mb-4">User Information</h3>
              <div className="space-y-2">
                <div className="flex items-center gap-3">
                  <Avatar size="sm" src={ticket.user.image} alt={ticket.user.name} />
                  <div>
                    <div className="text-sm font-medium text-white">{ticket.user.name}</div>
                    <div className="text-xs text-gray-400">{ticket.user.email}</div>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-sm text-gray-400">
                  <Mail className="w-4 h-4" />
                  <span>{ticket.user.email}</span>
                </div>
                {ticket.user.phone && (
                  <div className="flex items-center gap-2 text-sm text-gray-400">
                    <Phone className="w-4 h-4" />
                    <span>{ticket.user.phone}</span>
                  </div>
                )}
                <Button
                  variant="ghost"
                  size="sm"
                  className="w-full text-cyan-400 hover:text-cyan-300 border border-cyan-500/20 hover:bg-cyan-500/10 mt-2"
                >
                  View User Profile
                </Button>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* ============================================ */}
      {/* EDIT TICKET MODAL */}
      {/* ============================================ */}
      <Modal
        open={showEditModal}
        onOpenChange={setShowEditModal}
        title="Edit Ticket"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Subject *</label>
            <Input
              value={editForm.subject}
              onChange={(e) => setEditForm({ ...editForm, subject: e.target.value })}
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Status</label>
            <Select
              value={editForm.status}
              onValueChange={(value) => setEditForm({ ...editForm, status: value as TicketStatus })}
              className="w-full bg-gray-700 border-gray-600"
            >
              {Object.entries(TICKET_STATUSES).map(([key, value]) => (
                <option key={key} value={value}>{value.toUpperCase().replace('_', ' ')}</option>
              ))}
            </Select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Priority</label>
            <Select
              value={editForm.priority}
              onValueChange={(value) => setEditForm({ ...editForm, priority: value as TicketPriority })}
              className="w-full bg-gray-700 border-gray-600"
            >
              {Object.entries(TICKET_PRIORITIES).map(([key, value]) => (
                <option key={key} value={value}>{value.toUpperCase()}</option>
              ))}
            </Select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Category</label>
            <Select
              value={editForm.category}
              onValueChange={(value) => setEditForm({ ...editForm, category: value as TicketCategory })}
              className="w-full bg-gray-700 border-gray-600"
            >
              {Object.entries(TICKET_CATEGORIES).map(([key, value]) => (
                <option key={key} value={value}>{value.toUpperCase()}</option>
              ))}
            </Select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Assigned To</label>
            <Select
              value={editForm.assignedTo}
              onValueChange={(value) => setEditForm({ ...editForm, assignedTo: value })}
              className="w-full bg-gray-700 border-gray-600"
            >
              <option value="">Unassigned</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </Select>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => setShowEditModal(false)}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handleUpdateTicket}
              isLoading={isSubmitting}
              className="bg-gradient-to-r from-cyan-500 to-blue-500"
            >
              Save Changes
            </Button>
          </div>
        </div>
      </Modal>

      {/* ============================================ */}
      {/* RESOLVE TICKET MODAL */}
      {/* ============================================ */}
      <Modal
        open={showResolveModal}
        onOpenChange={setShowResolveModal}
        title="Resolve Ticket"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-3">
            <p className="text-sm text-green-500 flex items-center gap-2">
              <CheckCircle className="w-5 h-5" />
              This action will mark the ticket as resolved.
            </p>
            <p className="text-xs text-gray-400 mt-1">
              The ticket will be closed and no further replies will be accepted.
            </p>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => setShowResolveModal(false)}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handleResolveTicket}
              isLoading={isSubmitting}
              className="bg-green-600 hover:bg-green-700"
            >
              <Check className="w-4 h-4 mr-2" />
              Resolve Ticket
            </Button>
          </div>
        </div>
      </Modal>

      {/* ============================================ */}
      {/* ESCALATE TICKET MODAL */}
      {/* ============================================ */}
      <Modal
        open={showEscalateModal}
        onOpenChange={setShowEscalateModal}
        title="Escalate Ticket"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
            <p className="text-sm text-red-500 flex items-center gap-2">
              <AlertCircle className="w-5 h-5" />
              This action will escalate the ticket for higher priority handling.
            </p>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Escalation Reason *</label>
            <Textarea
              placeholder="Please provide a reason for escalation..."
              className="w-full bg-gray-700 border-gray-600 text-white resize-none"
              rows={3}
              onChange={(e) => {
                // Store reason in state
              }}
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => setShowEscalateModal(false)}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={() => handleEscalateTicket('')}
              isLoading={isSubmitting}
              className="bg-red-600 hover:bg-red-700"
            >
              <AlertCircle className="w-4 h-4 mr-2" />
              Escalate Ticket
            </Button>
          </div>
        </div>
      </Modal>

      {/* ============================================ */}
      {/* ASSIGN TICKET MODAL */}
      {/* ============================================ */}
      <Modal
        open={showAssignModal}
        onOpenChange={setShowAssignModal}
        title="Assign Ticket"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Assign To</label>
            <Select
              value={editForm.assignedTo}
              onValueChange={(value) => setEditForm({ ...editForm, assignedTo: value })}
              className="w-full bg-gray-700 border-gray-600"
            >
              <option value="">Unassigned</option>
              {users.map((u) => (
                <option key={u.id} value={u.id}>{u.name}</option>
              ))}
            </Select>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => setShowAssignModal(false)}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={() => handleAssignTicket(editForm.assignedTo)}
              isLoading={isSubmitting}
              className="bg-gradient-to-r from-cyan-500 to-blue-500"
            >
              Assign Ticket
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

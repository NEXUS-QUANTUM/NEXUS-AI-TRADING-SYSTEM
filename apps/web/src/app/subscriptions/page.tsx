/**
 * NEXUS AI TRADING SYSTEM - Subscriptions Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page provides comprehensive subscription management including:
 * - Subscription plan management
 * - Plan comparison and selection
 * - Subscription upgrade/downgrade
 * - Payment method management
 * - Billing history and invoices
 * - Usage tracking and limits
 * - Auto-renewal management
 * - Subscription cancellation
 * - Reactivation
 * - Trial management
 * - Feature access control
 * - Multi-tier pricing
 * - Annual/monthly billing cycles
 * - Coupon and discount management
 * - Referral program
 * - Tax management
 * - Invoice download
 * - Payment processing
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
import { useSubscription } from '@/hooks/useSubscription';

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
  Check,
  X,
  Crown,
  Star,
  Zap,
  Sparkles,
  Shield,
  Rocket,
  Award,
  Trophy,
  Medal,
  Gift,
  TrendingUp,
  TrendingDown,
  Wallet,
  CreditCard,
  Receipt,
  FileText,
  Download,
  Upload,
  RefreshCw,
  Plus,
  Minus,
  ArrowRight,
  ArrowLeft,
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
  Receipt as ReceiptIcon,
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
  AlertCircle,
  Info,
  HelpCircle,
  Clock,
  Calendar,
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
  SubscriptionPlan,
  Subscription,
  BillingCycle,
  PaymentMethod,
  Invoice,
  Usage,
  SubscriptionFeature,
  Coupon,
  Referral,
  TaxInfo,
} from '@/types/subscriptions';

// Constants
import {
  SUBSCRIPTION_PLANS,
  BILLING_CYCLES,
  PAYMENT_METHODS,
  SUBSCRIPTION_FEATURES,
  DEFAULT_PLAN,
  TRIAL_DAYS,
  REFERRAL_DISCOUNT,
} from '@/constants/subscriptions';

// Utils
import { formatCurrency, formatNumber, formatPercentage, formatDate, formatTime, formatBytes } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

export default function SubscriptionsPage() {
  // Router
  const router = useRouter();

  // Auth hooks
  const { user, isAuthenticated } = useAuth();

  // API client
  const api = useApi();

  // Subscription hook
  const {
    subscription,
    plans,
    isLoading: subscriptionLoading,
    refresh: refreshSubscription,
    upgrade: upgradeSubscription,
    downgrade: downgradeSubscription,
    cancel: cancelSubscription,
    reactivate: reactivateSubscription,
    updatePaymentMethod: updatePaymentMethod,
  } = useSubscription();

  // State - Plans
  const [selectedPlan, setSelectedPlan] = useState<string>('pro');
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'annual'>('monthly');

  // State - Payment Methods
  const [paymentMethods, setPaymentMethods] = useState<PaymentMethod[]>([]);
  const [paymentMethodsLoading, setPaymentMethodsLoading] = useState<boolean>(true);
  const [showAddPaymentMethod, setShowAddPaymentMethod] = useState<boolean>(false);
  const [newPaymentMethod, setNewPaymentMethod] = useState<Partial<PaymentMethod>>({
    type: 'card',
    cardNumber: '',
    cardName: '',
    expiryMonth: '',
    expiryYear: '',
    cvv: '',
    isDefault: false,
  });
  const [isAddingPaymentMethod, setIsAddingPaymentMethod] = useState<boolean>(false);

  // State - Invoices
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [invoicesLoading, setInvoicesLoading] = useState<boolean>(true);
  const [selectedInvoice, setSelectedInvoice] = useState<Invoice | null>(null);
  const [showInvoiceModal, setShowInvoiceModal] = useState<boolean>(false);
  const [isDownloadingInvoice, setIsDownloadingInvoice] = useState<boolean>(false);

  // State - Usage
  const [usage, setUsage] = useState<Usage | null>(null);
  const [usageLoading, setUsageLoading] = useState<boolean>(true);

  // State - Coupon
  const [couponCode, setCouponCode] = useState<string>('');
  const [coupon, setCoupon] = useState<Coupon | null>(null);
  const [couponLoading, setCouponLoading] = useState<boolean>(false);
  const [couponError, setCouponError] = useState<string>('');

  // State - Referral
  const [referral, setReferral] = useState<Referral | null>(null);
  const [referralLoading, setReferralLoading] = useState<boolean>(true);
  const [referralCode, setReferralCode] = useState<string>('');

  // State - Tax
  const [taxInfo, setTaxInfo] = useState<TaxInfo | null>(null);
  const [taxLoading, setTaxLoading] = useState<boolean>(true);

  // State - UI
  const [activeTab, setActiveTab] = useState<string>('plans');
  const [showCancelModal, setShowCancelModal] = useState<boolean>(false);
  const [cancelReason, setCancelReason] = useState<string>('');
  const [cancelFeedback, setCancelFeedback] = useState<string>('');
  const [isCancelling, setIsCancelling] = useState<boolean>(false);
  const [isUpgrading, setIsUpgrading] = useState<boolean>(false);
  const [isDowngrading, setIsDowngrading] = useState<boolean>(false);
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Refs
  const planSectionRef = useRef<HTMLDivElement>(null);

  // ============================================
  // WebSocket Connection
  // ============================================

  const {
    isConnected,
    sendMessage,
    subscribe: wsSubscribe,
    unsubscribe: wsUnsubscribe,
  } = useWebSocket({
    url: `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8004'}/subscriptions`,
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
    console.log('✅ Subscriptions WebSocket connected');
    subscribeToChannels();
  }

  function handleWebSocketMessage(event: MessageEvent) {
    try {
      const data = JSON.parse(event.data);

      switch (data.type) {
        case 'subscription_update':
          handleSubscriptionUpdate(data.payload);
          break;
        case 'invoice_update':
          handleInvoiceUpdate(data.payload);
          break;
        case 'usage_update':
          handleUsageUpdate(data.payload);
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
    console.log('Subscriptions WebSocket disconnected');
  }

  function subscribeToChannels() {
    if (!isConnected) return;

    wsSubscribe({
      channel: 'subscription',
      userId: user?.id,
    });

    wsSubscribe({
      channel: 'invoices',
      userId: user?.id,
    });

    wsSubscribe({
      channel: 'usage',
      userId: user?.id,
    });
  }

  // ============================================
  // WebSocket Data Handlers
  // ============================================

  function handleSubscriptionUpdate(data: any) {
    refreshSubscription();
  }

  function handleInvoiceUpdate(data: any) {
    setInvoices(prev => [data, ...prev]);
    setShowToast({
      message: `New invoice generated: ${data.number}`,
      type: 'info',
    });
  }

  function handleUsageUpdate(data: any) {
    setUsage(data);
  }

  // ============================================
  // API Calls
  // ============================================

  const fetchPaymentMethods = useCallback(async () => {
    try {
      setPaymentMethodsLoading(true);
      const response = await api.get('/subscriptions/payment-methods');
      if (response.data) {
        setPaymentMethods(response.data.methods || []);
      }
    } catch (error) {
      console.error('Failed to fetch payment methods:', error);
    } finally {
      setPaymentMethodsLoading(false);
    }
  }, [api]);

  const fetchInvoices = useCallback(async () => {
    try {
      setInvoicesLoading(true);
      const response = await api.get('/subscriptions/invoices');
      if (response.data) {
        setInvoices(response.data.invoices || []);
      }
    } catch (error) {
      console.error('Failed to fetch invoices:', error);
    } finally {
      setInvoicesLoading(false);
    }
  }, [api]);

  const fetchUsage = useCallback(async () => {
    try {
      setUsageLoading(true);
      const response = await api.get('/subscriptions/usage');
      if (response.data) {
        setUsage(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch usage:', error);
    } finally {
      setUsageLoading(false);
    }
  }, [api]);

  const fetchTaxInfo = useCallback(async () => {
    try {
      setTaxLoading(true);
      const response = await api.get('/subscriptions/tax');
      if (response.data) {
        setTaxInfo(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch tax info:', error);
    } finally {
      setTaxLoading(false);
    }
  }, [api]);

  const fetchReferral = useCallback(async () => {
    try {
      setReferralLoading(true);
      const response = await api.get('/subscriptions/referral');
      if (response.data) {
        setReferral(response.data);
        setReferralCode(response.data.code || '');
      }
    } catch (error) {
      console.error('Failed to fetch referral:', error);
    } finally {
      setReferralLoading(false);
    }
  }, [api]);

  const fetchAllData = useCallback(async () => {
    setIsLoading(true);
    setIsRefreshing(true);
    try {
      await Promise.all([
        refreshSubscription(),
        fetchPaymentMethods(),
        fetchInvoices(),
        fetchUsage(),
        fetchTaxInfo(),
        fetchReferral(),
      ]);
    } catch (error) {
      console.error('Failed to fetch subscription data:', error);
      setShowToast({
        message: 'Failed to load subscription data. Please refresh.',
        type: 'error',
      });
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [
    refreshSubscription,
    fetchPaymentMethods,
    fetchInvoices,
    fetchUsage,
    fetchTaxInfo,
    fetchReferral,
  ]);

  // ============================================
  // Handlers - Subscription Actions
  // ============================================

  const handleUpgrade = useCallback(async (planId: string) => {
    setIsUpgrading(true);
    try {
      const result = await upgradeSubscription(planId, billingCycle);
      if (result.success) {
        setShowToast({
          message: `Successfully upgraded to ${result.plan.name}!`,
          type: 'success',
        });
        await refreshSubscription();
      }
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to upgrade subscription.',
        type: 'error',
      });
    } finally {
      setIsUpgrading(false);
    }
  }, [billingCycle, upgradeSubscription, refreshSubscription]);

  const handleDowngrade = useCallback(async (planId: string) => {
    setIsDowngrading(true);
    try {
      const result = await downgradeSubscription(planId, billingCycle);
      if (result.success) {
        setShowToast({
          message: `Successfully downgraded to ${result.plan.name}. Changes will take effect next billing cycle.`,
          type: 'info',
        });
        await refreshSubscription();
      }
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to downgrade subscription.',
        type: 'error',
      });
    } finally {
      setIsDowngrading(false);
    }
  }, [billingCycle, downgradeSubscription, refreshSubscription]);

  const handleCancel = useCallback(async () => {
    if (!cancelReason) {
      setShowToast({
        message: 'Please provide a reason for cancelling.',
        type: 'warning',
      });
      return;
    }

    setIsCancelling(true);
    try {
      const result = await cancelSubscription(cancelReason, cancelFeedback);
      if (result.success) {
        setShowToast({
          message: 'Your subscription has been cancelled. You will continue to have access until the end of your billing period.',
          type: 'info',
        });
        setShowCancelModal(false);
        setCancelReason('');
        setCancelFeedback('');
        await refreshSubscription();
      }
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to cancel subscription.',
        type: 'error',
      });
    } finally {
      setIsCancelling(false);
    }
  }, [cancelReason, cancelFeedback, cancelSubscription, refreshSubscription]);

  const handleReactivate = useCallback(async () => {
    try {
      const result = await reactivateSubscription();
      if (result.success) {
        setShowToast({
          message: 'Your subscription has been reactivated!',
          type: 'success',
        });
        await refreshSubscription();
      }
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to reactivate subscription.',
        type: 'error',
      });
    }
  }, [reactivateSubscription, refreshSubscription]);

  const handleToggleAutoRenew = useCallback(async () => {
    try {
      const response = await api.put('/subscriptions/auto-renew', {
        enabled: !subscription?.autoRenew,
      });
      if (response.data) {
        await refreshSubscription();
        setShowToast({
          message: `Auto-renew ${subscription?.autoRenew ? 'disabled' : 'enabled'}`,
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to update auto-renew setting.',
        type: 'error',
      });
    }
  }, [api, subscription, refreshSubscription]);

  // ============================================
  // Handlers - Payment Methods
  // ============================================

  const handleAddPaymentMethod = useCallback(async () => {
    if (!newPaymentMethod.cardNumber || !newPaymentMethod.cardName ||
        !newPaymentMethod.expiryMonth || !newPaymentMethod.expiryYear ||
        !newPaymentMethod.cvv) {
      setShowToast({
        message: 'Please fill in all card details.',
        type: 'warning',
      });
      return;
    }

    setIsAddingPaymentMethod(true);
    try {
      const response = await api.post('/subscriptions/payment-methods', newPaymentMethod);
      if (response.data) {
        setPaymentMethods(prev => [...prev, response.data.method]);
        if (response.data.method.isDefault) {
          setPaymentMethods(prev => prev.map(m => ({ ...m, isDefault: m.id === response.data.method.id })));
        }
        setShowAddPaymentMethod(false);
        setNewPaymentMethod({
          type: 'card',
          cardNumber: '',
          cardName: '',
          expiryMonth: '',
          expiryYear: '',
          cvv: '',
          isDefault: false,
        });
        setShowToast({
          message: 'Payment method added successfully!',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to add payment method.',
        type: 'error',
      });
    } finally {
      setIsAddingPaymentMethod(false);
    }
  }, [api, newPaymentMethod]);

  const handleDeletePaymentMethod = useCallback(async (id: string) => {
    if (!confirm('Are you sure you want to remove this payment method?')) return;

    try {
      await api.delete(`/subscriptions/payment-methods/${id}`);
      setPaymentMethods(prev => prev.filter(m => m.id !== id));
      setShowToast({
        message: 'Payment method removed.',
        type: 'info',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to remove payment method.',
        type: 'error',
      });
    }
  }, [api]);

  const handleSetDefaultPaymentMethod = useCallback(async (id: string) => {
    try {
      const response = await api.put(`/subscriptions/payment-methods/${id}/default`);
      if (response.data) {
        setPaymentMethods(prev => prev.map(m => ({ ...m, isDefault: m.id === id })));
        setShowToast({
          message: 'Default payment method updated.',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to update default payment method.',
        type: 'error',
      });
    }
  }, [api]);

  // ============================================
  // Handlers - Invoices
  // ============================================

  const handleViewInvoice = useCallback((invoice: Invoice) => {
    setSelectedInvoice(invoice);
    setShowInvoiceModal(true);
  }, []);

  const handleDownloadInvoice = useCallback(async (id: string) => {
    setIsDownloadingInvoice(true);
    try {
      const response = await api.get(`/subscriptions/invoices/${id}/download`, {
        responseType: 'blob',
      });
      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `invoice-${id}.pdf`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      setShowToast({
        message: 'Invoice downloaded successfully.',
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to download invoice.',
        type: 'error',
      });
    } finally {
      setIsDownloadingInvoice(false);
    }
  }, [api]);

  // ============================================
  // Handlers - Coupon
  // ============================================

  const handleApplyCoupon = useCallback(async () => {
    if (!couponCode.trim()) {
      setCouponError('Please enter a coupon code.');
      return;
    }

    setCouponLoading(true);
    setCouponError('');
    try {
      const response = await api.post('/subscriptions/coupon/apply', { code: couponCode });
      if (response.data) {
        setCoupon(response.data);
        setShowToast({
          message: `Coupon applied! ${response.data.discount}% discount.`,
          type: 'success',
        });
      }
    } catch (error: any) {
      setCouponError(error.response?.data?.message || 'Invalid coupon code.');
      setCoupon(null);
    } finally {
      setCouponLoading(false);
    }
  }, [api, couponCode]);

  const handleRemoveCoupon = useCallback(async () => {
    try {
      await api.delete('/subscriptions/coupon/remove');
      setCoupon(null);
      setCouponCode('');
      setShowToast({
        message: 'Coupon removed.',
        type: 'info',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to remove coupon.',
        type: 'error',
      });
    }
  }, [api]);

  // ============================================
  // Effects
  // ============================================

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/authentication/login?callbackUrl=/subscriptions');
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
    const interval = setInterval(() => {
      if (!isRefreshing) {
        fetchUsage();
        fetchInvoices();
      }
    }, 60000);

    return () => clearInterval(interval);
  }, [fetchUsage, fetchInvoices, isRefreshing]);

  // ============================================
  // Memoized Computations
  // ============================================

  const currentPlan = useMemo(() => {
    if (!subscription) return null;
    return plans?.find(p => p.id === subscription.planId) || null;
  }, [subscription, plans]);

  const isCurrentPlan = useCallback((planId: string) => {
    return currentPlan?.id === planId;
  }, [currentPlan]);

  const isUpgrade = useCallback((planId: string) => {
    if (!currentPlan) return false;
    const currentIndex = plans?.findIndex(p => p.id === currentPlan.id) || 0;
    const targetIndex = plans?.findIndex(p => p.id === planId) || 0;
    return targetIndex > currentIndex;
  }, [currentPlan, plans]);

  const isDowngrade = useCallback((planId: string) => {
    if (!currentPlan) return false;
    const currentIndex = plans?.findIndex(p => p.id === currentPlan.id) || 0;
    const targetIndex = plans?.findIndex(p => p.id === planId) || 0;
    return targetIndex < currentIndex;
  }, [currentPlan, plans]);

  const totalUsage = useMemo(() => {
    if (!usage) return { apiCalls: 0, apiLimit: 1000, storageUsed: 0, storageLimit: 10 };
    return {
      apiCalls: usage.apiCalls || 0,
      apiLimit: usage.apiLimit || 1000,
      storageUsed: usage.storageUsed || 0,
      storageLimit: usage.storageLimit || 10,
    };
  }, [usage]);

  const features = useMemo(() => {
    const planFeatures: Record<string, SubscriptionFeature[]> = {
      free: [
        { name: 'Basic Market Data', included: true },
        { name: 'Paper Trading', included: true },
        { name: '1 AI Signal per Day', included: true },
        { name: 'Basic Support', included: true },
        { name: 'Advanced AI Predictions', included: false },
        { name: 'Real-time Trading', included: false },
        { name: 'Multiple Markets', included: false },
        { name: 'Priority Support', included: false },
      ],
      pro: [
        { name: 'Advanced Market Data', included: true },
        { name: 'Real-time Trading', included: true },
        { name: '10 AI Signals per Day', included: true },
        { name: 'Priority Support', included: true },
        { name: 'Multiple Markets', included: true },
        { name: 'Advanced Analytics', included: true },
        { name: 'API Access', included: false },
        { name: 'Custom Strategies', included: false },
      ],
      business: [
        { name: 'Enterprise Market Data', included: true },
        { name: 'Unlimited AI Signals', included: true },
        { name: 'API Access', included: true },
        { name: 'Custom Strategies', included: true },
        { name: 'Dedicated Support', included: true },
        { name: 'White-label Options', included: true },
        { name: 'Advanced Analytics', included: true },
        { name: 'Priority Trading Execution', included: true },
      ],
      enterprise: [
        { name: 'Full Market Data', included: true },
        { name: 'Unlimited AI Signals', included: true },
        { name: 'Full API Access', included: true },
        { name: 'Custom Development', included: true },
        { name: 'Dedicated Account Manager', included: true },
        { name: 'White-label Solutions', included: true },
        { name: 'Advanced Risk Management', included: true },
        { name: 'Custom Integrations', included: true },
      ],
    };
    const planId = currentPlan?.id || 'free';
    return planFeatures[planId as keyof typeof planFeatures] || planFeatures.free;
  }, [currentPlan]);

  // ============================================
  // Render
  // ============================================

  if (isLoading && subscriptionLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-6">
            <div className="absolute inset-0 border-4 border-cyan-500/30 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-t-cyan-500 rounded-full animate-spin"></div>
            <div className="absolute inset-2 bg-cyan-500/10 rounded-full animate-pulse"></div>
          </div>
          <p className="text-gray-400 text-lg font-medium">Loading Subscriptions...</p>
          <p className="text-gray-500 text-sm mt-2">Fetching your plan details</p>
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
            <div className="text-3xl">📋</div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                Subscriptions
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                Manage your plan and billing
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
        </div>
      </div>

      {/* ============================================ */}
      {/* CURRENT SUBSCRIPTION STATUS */}
      {/* ============================================ */}
      {subscription && (
        <Card className="p-6 bg-gray-800 border-gray-700 mb-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-4">
              <div className={cn(
                "w-16 h-16 rounded-full flex items-center justify-center",
                subscription.status === 'active' ? 'bg-green-500/20' :
                subscription.status === 'cancelled' ? 'bg-red-500/20' :
                subscription.status === 'past_due' ? 'bg-yellow-500/20' :
                'bg-gray-500/20'
              )}>
                {subscription.status === 'active' && <Check className="w-8 h-8 text-green-500" />}
                {subscription.status === 'cancelled' && <X className="w-8 h-8 text-red-500" />}
                {subscription.status === 'past_due' && <AlertCircle className="w-8 h-8 text-yellow-500" />}
                {subscription.status === 'trialing' && <Sparkles className="w-8 h-8 text-purple-500" />}
              </div>
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-xl font-bold text-white">{currentPlan?.name || 'Free Plan'}</h2>
                  <Badge className={cn(
                    "text-xs",
                    subscription.status === 'active' ? 'bg-green-500/20 text-green-500 border-green-500/30' :
                    subscription.status === 'cancelled' ? 'bg-red-500/20 text-red-500 border-red-500/30' :
                    subscription.status === 'past_due' ? 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30' :
                    'bg-gray-500/20 text-gray-400 border-gray-500/30'
                  )}>
                    {subscription.status?.toUpperCase() || 'ACTIVE'}
                  </Badge>
                  {subscription.autoRenew && subscription.status === 'active' && (
                    <Badge className="bg-blue-500/20 text-blue-400 border-blue-500/30 text-xs">
                      Auto-renew ON
                    </Badge>
                  )}
                </div>
                <p className="text-sm text-gray-400 mt-1">
                  {currentPlan?.description || 'Free tier with limited features'}
                </p>
              </div>
            </div>
            <div className="text-right">
              <div className="text-2xl font-bold text-white">
                {formatCurrency(subscription.price || 0, subscription.currency || 'USD')}
                <span className="text-sm font-normal text-gray-400 ml-1">
                  /{subscription.cycle || 'month'}
                </span>
              </div>
              {subscription.nextBillingDate && (
                <p className="text-xs text-gray-500 mt-1">
                  Next billing: {formatDate(subscription.nextBillingDate)}
                </p>
              )}
              {subscription.status === 'cancelled' && subscription.endsAt && (
                <p className="text-xs text-orange-400 mt-1">
                  Access until: {formatDate(subscription.endsAt)}
                </p>
              )}
            </div>
          </div>

          {/* Usage Progress */}
          {currentPlan?.id !== 'free' && (
            <div className="mt-4 pt-4 border-t border-gray-700">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <div className="flex justify-between text-xs text-gray-400 mb-1">
                    <span>API Calls</span>
                    <span>{formatNumber(totalUsage.apiCalls)} / {formatNumber(totalUsage.apiLimit)}</span>
                  </div>
                  <Progress 
                    value={(totalUsage.apiCalls / totalUsage.apiLimit) * 100} 
                    className="h-1.5"
                    color={(totalUsage.apiCalls / totalUsage.apiLimit) > 0.8 ? 'yellow' : 'cyan'}
                  />
                </div>
                <div>
                  <div className="flex justify-between text-xs text-gray-400 mb-1">
                    <span>Storage</span>
                    <span>{formatBytes(totalUsage.storageUsed)} / {formatBytes(totalUsage.storageLimit * 1024 * 1024 * 1024)}</span>
                  </div>
                  <Progress 
                    value={(totalUsage.storageUsed / (totalUsage.storageLimit * 1024 * 1024 * 1024)) * 100} 
                    className="h-1.5"
                    color={(totalUsage.storageUsed / (totalUsage.storageLimit * 1024 * 1024 * 1024)) > 0.8 ? 'yellow' : 'cyan'}
                  />
                </div>
              </div>
            </div>
          )}
        </Card>
      )}

      {/* ============================================ */}
      {/* MAIN TABS */}
      {/* ============================================ */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-gray-800 border border-gray-700 rounded-lg p-1 w-full overflow-x-auto">
          <TabsTrigger
            value="plans"
            className="data-[state=active]:bg-cyan-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📦 Plans
          </TabsTrigger>
          <TabsTrigger
            value="billing"
            className="data-[state=active]:bg-purple-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            💳 Billing
          </TabsTrigger>
          <TabsTrigger
            value="usage"
            className="data-[state=active]:bg-green-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📊 Usage
          </TabsTrigger>
          <TabsTrigger
            value="referral"
            className="data-[state=active]:bg-yellow-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            🎁 Referral
          </TabsTrigger>
        </TabsList>

        {/* ========================================== */}
        {/* PLANS TAB */}
        {/* ========================================== */}
        <TabsContent value="plans" className="mt-4">
          <div ref={planSectionRef} className="space-y-6">
            {/* Billing Cycle Toggle */}
            <div className="flex items-center justify-center gap-4">
              <span className={cn(
                "text-sm font-medium transition-colors",
                billingCycle === 'monthly' ? 'text-white' : 'text-gray-400'
              )}>
                Monthly
              </span>
              <button
                onClick={() => setBillingCycle(prev => prev === 'monthly' ? 'annual' : 'monthly')}
                className={cn(
                  "w-12 h-6 rounded-full bg-gray-700 relative transition-colors",
                  billingCycle === 'annual' ? 'bg-cyan-500' : 'bg-gray-600'
                )}
              >
                <div className={cn(
                  "absolute top-1 w-4 h-4 rounded-full bg-white transition-transform",
                  billingCycle === 'annual' ? 'translate-x-7' : 'translate-x-1'
                )} />
              </button>
              <span className={cn(
                "text-sm font-medium transition-colors",
                billingCycle === 'annual' ? 'text-white' : 'text-gray-400'
              )}>
                Annual
                <span className="ml-1 text-xs text-green-500">(Save 20%)</span>
              </span>
            </div>

            {/* Plan Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {SUBSCRIPTION_PLANS.map((plan) => {
                const isCurrent = isCurrentPlan(plan.id);
                const isUpgradePlan = isUpgrade(plan.id);
                const isDowngradePlan = isDowngrade(plan.id);
                const price = billingCycle === 'monthly' ? plan.monthlyPrice : plan.annualPrice;
                const priceLabel = billingCycle === 'monthly' ? '/month' : '/year';

                return (
                  <motion.div
                    key={plan.id}
                    initial={{ opacity: 0, y: 20 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.3 }}
                    className="relative"
                  >
                    {plan.popular && (
                      <div className="absolute -top-3 left-1/2 -translate-x-1/2 z-10">
                        <Badge className="bg-gradient-to-r from-yellow-500 to-orange-500 text-white text-xs px-4 py-1">
                          ⭐ Most Popular
                        </Badge>
                      </div>
                    )}
                    <Card className={cn(
                      "p-6 bg-gray-800 border-gray-700 h-full flex flex-col transition-all",
                      isCurrent && "border-cyan-500 ring-2 ring-cyan-500/20",
                      !isCurrent && "hover:border-cyan-500/50",
                      plan.popular && "border-yellow-500/30"
                    )}>
                      <div className="flex items-center justify-between mb-2">
                        <h3 className="text-lg font-bold text-white">{plan.name}</h3>
                        {isCurrent && (
                          <Badge className="bg-cyan-500/20 text-cyan-400 border-cyan-500/30">
                            Current
                          </Badge>
                        )}
                      </div>
                      <p className="text-sm text-gray-400 mb-4">{plan.description}</p>
                      <div className="mb-4">
                        <span className="text-3xl font-bold text-white">
                          {formatCurrency(price, 'USD')}
                        </span>
                        <span className="text-sm text-gray-400 ml-1">{priceLabel}</span>
                        {plan.annualPrice && billingCycle === 'annual' && (
                          <div className="text-sm text-green-500 mt-1">
                            Save {Math.round((1 - plan.annualPrice / (plan.monthlyPrice * 12)) * 100)}%
                          </div>
                        )}
                      </div>

                      {/* Features */}
                      <div className="flex-1 space-y-2 mb-6">
                        {plan.features.map((feature, idx) => (
                          <div key={idx} className="flex items-start gap-2 text-sm">
                            {feature.included ? (
                              <Check className="w-4 h-4 text-cyan-500 mt-0.5 flex-shrink-0" />
                            ) : (
                              <X className="w-4 h-4 text-gray-500 mt-0.5 flex-shrink-0" />
                            )}
                            <span className={feature.included ? 'text-gray-300' : 'text-gray-500'}>
                              {feature.name}
                            </span>
                          </div>
                        ))}
                      </div>

                      {/* Action Button */}
                      <Button
                        variant={isCurrent ? 'outline' : plan.popular ? 'primary' : 'outline'}
                        disabled={isCurrent || isUpgrading || isDowngrading}
                        onClick={() => {
                          if (isUpgradePlan) {
                            handleUpgrade(plan.id);
                          } else if (isDowngradePlan) {
                            handleDowngrade(plan.id);
                          }
                        }}
                        className={cn(
                          "w-full transition-all",
                          isCurrent ? "border-gray-600 text-gray-400 cursor-default" :
                          plan.popular ? "bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-600 hover:to-orange-600 text-white" :
                          "border-gray-600 hover:border-cyan-500 hover:text-cyan-400"
                        )}
                      >
                        {isCurrent ? 'Current Plan' :
                         isUpgradePlan ? 'Upgrade' :
                         isDowngradePlan ? 'Downgrade' :
                         'Select Plan'}
                        {!isCurrent && <ArrowRight className="w-4 h-4 ml-2" />}
                      </Button>
                    </Card>
                  </motion.div>
                );
              })}
            </div>

            {/* Coupon Section */}
            <Card className="p-4 bg-gray-800 border-gray-700">
              <h3 className="text-sm font-semibold text-gray-300 mb-3">Have a coupon?</h3>
              <div className="flex items-center gap-3">
                <Input
                  value={couponCode}
                  onChange={(e) => setCouponCode(e.target.value.toUpperCase())}
                  placeholder="Enter coupon code"
                  className="flex-1 bg-gray-700 border-gray-600 text-white"
                  disabled={!!coupon}
                />
                {coupon ? (
                  <Button
                    variant="outline"
                    onClick={handleRemoveCoupon}
                    className="border-red-500/50 hover:border-red-500 text-red-400"
                  >
                    <X className="w-4 h-4 mr-2" />
                    Remove
                  </Button>
                ) : (
                  <Button
                    onClick={handleApplyCoupon}
                    isLoading={couponLoading}
                    className="bg-gradient-to-r from-yellow-500 to-orange-500"
                  >
                    Apply
                  </Button>
                )}
              </div>
              {couponError && (
                <p className="mt-2 text-sm text-red-500">{couponError}</p>
              )}
              {coupon && (
                <div className="mt-2 p-2 bg-green-500/10 border border-green-500/30 rounded-lg">
                  <p className="text-sm text-green-500">
                    Coupon applied! {coupon.discount}% discount
                    {coupon.expiresAt && ` • Expires: ${formatDate(coupon.expiresAt)}`}
                  </p>
                </div>
              )}
            </Card>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* BILLING TAB */}
        {/* ========================================== */}
        <TabsContent value="billing" className="mt-4 space-y-6">
          {/* Payment Methods */}
          <div>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-gray-300">Payment Methods</h3>
              <Button
                onClick={() => setShowAddPaymentMethod(true)}
                className="bg-gradient-to-r from-purple-500 to-pink-500"
              >
                <Plus className="w-4 h-4 mr-2" />
                Add Payment Method
              </Button>
            </div>

            {paymentMethodsLoading ? (
              <div className="text-center py-8">
                <Spinner size="lg" className="mx-auto text-cyan-500" />
                <p className="text-gray-400 mt-4">Loading payment methods...</p>
              </div>
            ) : paymentMethods.length > 0 ? (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {paymentMethods.map((method) => (
                  <Card key={method.id} className={cn(
                    "p-4 bg-gray-800 border-gray-700 transition-all",
                    method.isDefault && "border-cyan-500/50 bg-cyan-500/5"
                  )}>
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-3">
                        <div className="w-12 h-12 bg-gray-700 rounded-lg flex items-center justify-center">
                          <CreditCard className="w-6 h-6 text-gray-400" />
                        </div>
                        <div>
                          <div className="font-medium text-white">
                            {method.cardBrand || 'Card'} •••• {method.last4}
                          </div>
                          <div className="text-sm text-gray-400">
                            Expires {method.expiryMonth}/{method.expiryYear}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {method.isDefault && (
                          <Badge className="bg-cyan-500/20 text-cyan-400 border-cyan-500/30 text-xs">
                            Default
                          </Badge>
                        )}
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeletePaymentMethod(method.id)}
                          className="text-gray-400 hover:text-red-500"
                        >
                          <Trash className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                    {!method.isDefault && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleSetDefaultPaymentMethod(method.id)}
                        className="mt-2 text-xs text-cyan-400 hover:text-cyan-300"
                      >
                        Set as default
                      </Button>
                    )}
                  </Card>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <CreditCard className="w-16 h-16 mx-auto mb-4 text-gray-600" />
                <p className="text-lg font-medium">No payment methods</p>
                <p className="text-sm">Add a payment method to subscribe to a plan</p>
              </div>
            )}
          </div>

          {/* Invoices */}
          <div>
            <h3 className="text-sm font-semibold text-gray-300 mb-4">Billing History</h3>
            {invoicesLoading ? (
              <div className="text-center py-8">
                <Spinner size="lg" className="mx-auto text-cyan-500" />
                <p className="text-gray-400 mt-4">Loading invoices...</p>
              </div>
            ) : invoices.length > 0 ? (
              <Card className="bg-gray-800 border-gray-700 overflow-hidden">
                <Table>
                  <thead>
                    <tr className="border-b border-gray-700">
                      <th className="text-left text-xs text-gray-400 p-4">Invoice</th>
                      <th className="text-left text-xs text-gray-400 p-4">Date</th>
                      <th className="text-left text-xs text-gray-400 p-4">Amount</th>
                      <th className="text-left text-xs text-gray-400 p-4">Status</th>
                      <th className="text-right text-xs text-gray-400 p-4">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {invoices.map((invoice) => (
                      <tr key={invoice.id} className="border-b border-gray-700/50 hover:bg-gray-700/30 transition-colors">
                        <td className="p-4">
                          <div className="flex items-center gap-2">
                            <FileText className="w-4 h-4 text-gray-400" />
                            <span className="text-white font-mono text-sm">#{invoice.number}</span>
                          </div>
                        </td>
                        <td className="p-4 text-sm text-gray-400">{formatDate(invoice.date)}</td>
                        <td className="p-4 text-sm text-white font-medium">
                          {formatCurrency(invoice.amount, invoice.currency)}
                        </td>
                        <td className="p-4">
                          <Badge className={cn(
                            "text-xs",
                            invoice.status === 'paid' ? 'bg-green-500/20 text-green-500 border-green-500/30' :
                            invoice.status === 'pending' ? 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30' :
                            'bg-red-500/20 text-red-500 border-red-500/30'
                          )}>
                            {invoice.status?.toUpperCase()}
                          </Badge>
                        </td>
                        <td className="p-4 text-right">
                          <div className="flex items-center justify-end gap-2">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleViewInvoice(invoice)}
                              className="text-gray-400 hover:text-white"
                            >
                              <Eye className="w-4 h-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleDownloadInvoice(invoice.id)}
                              isLoading={isDownloadingInvoice}
                              className="text-gray-400 hover:text-cyan-400"
                            >
                              <Download className="w-4 h-4" />
                            </Button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </Table>
              </Card>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <Receipt className="w-16 h-16 mx-auto mb-4 text-gray-600" />
                <p className="text-lg font-medium">No invoices found</p>
                <p className="text-sm">Your invoices will appear here</p>
              </div>
            )}
          </div>

          {/* Tax Information */}
          {taxInfo && (
            <Card className="p-4 bg-gray-800 border-gray-700">
              <h3 className="text-sm font-semibold text-gray-300 mb-3">Tax Information</h3>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-gray-400">Tax ID</span>
                  <div className="text-white">{taxInfo.taxId || 'N/A'}</div>
                </div>
                <div>
                  <span className="text-gray-400">Tax Rate</span>
                  <div className="text-white">{formatPercentage(taxInfo.rate)}</div>
                </div>
                <div>
                  <span className="text-gray-400">Tax Exempt</span>
                  <div className="text-white">{taxInfo.exempt ? 'Yes' : 'No'}</div>
                </div>
                <div>
                  <span className="text-gray-400">Tax Region</span>
                  <div className="text-white">{taxInfo.region || 'N/A'}</div>
                </div>
              </div>
            </Card>
          )}
        </TabsContent>

        {/* ========================================== */}
        {/* USAGE TAB */}
        {/* ========================================== */}
        <TabsContent value="usage" className="mt-4">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 md:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">API Usage</h3>
                {usageLoading ? (
                  <div className="text-center py-8">
                    <Spinner size="lg" className="mx-auto text-cyan-500" />
                    <p className="text-gray-400 mt-4">Loading usage data...</p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-400">API Calls</span>
                        <span className="text-white">{formatNumber(totalUsage.apiCalls)} / {formatNumber(totalUsage.apiLimit)}</span>
                      </div>
                      <Progress 
                        value={(totalUsage.apiCalls / totalUsage.apiLimit) * 100} 
                        className="h-2"
                        color={(totalUsage.apiCalls / totalUsage.apiLimit) > 0.8 ? 'yellow' : 'cyan'}
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        {totalUsage.apiLimit - totalUsage.apiCalls} remaining this month
                      </p>
                    </div>
                    <div>
                      <div className="flex justify-between text-sm mb-1">
                        <span className="text-gray-400">Storage</span>
                        <span className="text-white">{formatBytes(totalUsage.storageUsed)} / {formatBytes(totalUsage.storageLimit * 1024 * 1024 * 1024)}</span>
                      </div>
                      <Progress 
                        value={(totalUsage.storageUsed / (totalUsage.storageLimit * 1024 * 1024 * 1024)) * 100} 
                        className="h-2"
                        color={(totalUsage.storageUsed / (totalUsage.storageLimit * 1024 * 1024 * 1024)) > 0.8 ? 'yellow' : 'cyan'}
                      />
                      <p className="text-xs text-gray-500 mt-1">
                        {formatBytes(totalUsage.storageLimit * 1024 * 1024 * 1024 - totalUsage.storageUsed)} remaining
                      </p>
                    </div>
                  </div>
                )}
              </Card>
            </div>

            <div className="col-span-12 md:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Usage Breakdown</h3>
                {usageLoading ? (
                  <div className="text-center py-8">
                    <Spinner size="lg" className="mx-auto text-cyan-500" />
                    <p className="text-gray-400 mt-4">Loading usage data...</p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">AI Predictions</span>
                      <span className="text-white">{formatNumber(usage?.aiPredictions || 0)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Market Data Requests</span>
                      <span className="text-white">{formatNumber(usage?.marketDataRequests || 0)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Trades Executed</span>
                      <span className="text-white">{formatNumber(usage?.tradesExecuted || 0)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Alerts Triggered</span>
                      <span className="text-white">{formatNumber(usage?.alertsTriggered || 0)}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">API Keys</span>
                      <span className="text-white">{formatNumber(usage?.apiKeys || 0)}</span>
                    </div>
                  </div>
                )}
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* REFERRAL TAB */}
        {/* ========================================== */}
        <TabsContent value="referral" className="mt-4">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 md:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">Referral Program</h3>
                {referralLoading ? (
                  <div className="text-center py-8">
                    <Spinner size="lg" className="mx-auto text-cyan-500" />
                    <p className="text-gray-400 mt-4">Loading referral data...</p>
                  </div>
                ) : referral ? (
                  <div className="space-y-4">
                    <div className="p-4 bg-cyan-500/10 border border-cyan-500/30 rounded-lg text-center">
                      <p className="text-sm text-cyan-400 font-medium">Your Referral Code</p>
                      <div className="flex items-center justify-center gap-3 mt-2">
                        <code className="text-2xl font-mono font-bold text-white">{referralCode}</code>
                        <CopyButton text={referralCode}>
                          <Button variant="ghost" size="sm" className="text-cyan-400 hover:text-cyan-300">
                            <Copy className="w-4 h-4" />
                          </Button>
                        </CopyButton>
                      </div>
                    </div>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="p-3 bg-gray-700/30 rounded-lg text-center">
                        <div className="text-xs text-gray-400">Total Referrals</div>
                        <div className="text-xl font-bold text-white">{referral.totalReferrals || 0}</div>
                      </div>
                      <div className="p-3 bg-gray-700/30 rounded-lg text-center">
                        <div className="text-xs text-gray-400">Rewards Earned</div>
                        <div className="text-xl font-bold text-green-500">{formatCurrency(referral.rewardsEarned || 0)}</div>
                      </div>
                      <div className="p-3 bg-gray-700/30 rounded-lg text-center">
                        <div className="text-xs text-gray-400">Active Referrals</div>
                        <div className="text-xl font-bold text-cyan-400">{referral.activeReferrals || 0}</div>
                      </div>
                      <div className="p-3 bg-gray-700/30 rounded-lg text-center">
                        <div className="text-xs text-gray-400">Pending Rewards</div>
                        <div className="text-xl font-bold text-yellow-500">{formatCurrency(referral.pendingRewards || 0)}</div>
                      </div>
                    </div>
                    <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
                      <p className="text-xs text-yellow-400">
                        Share your referral code with friends and earn {formatPercentage(REFERRAL_DISCOUNT)} discount on their first subscription!
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <Gift className="w-16 h-16 mx-auto mb-4 text-gray-600" />
                    <p className="text-lg font-medium">No referral data</p>
                    <p className="text-sm">Start referring friends to earn rewards</p>
                  </div>
                )}
              </Card>
            </div>

            <div className="col-span-12 md:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4">How It Works</h3>
                <div className="space-y-4">
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-cyan-500/20 flex items-center justify-center flex-shrink-0">
                      <span className="text-cyan-400 font-bold">1</span>
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-white">Share Your Code</h4>
                      <p className="text-xs text-gray-400">Share your unique referral code with friends</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-cyan-500/20 flex items-center justify-center flex-shrink-0">
                      <span className="text-cyan-400 font-bold">2</span>
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-white">Friend Signs Up</h4>
                      <p className="text-xs text-gray-400">Your friend subscribes using your referral code</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-cyan-500/20 flex items-center justify-center flex-shrink-0">
                      <span className="text-cyan-400 font-bold">3</span>
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-white">Earn Rewards</h4>
                      <p className="text-xs text-gray-400">You earn {formatPercentage(REFERRAL_DISCOUNT)} of their first subscription</p>
                    </div>
                  </div>
                  <div className="flex items-start gap-3">
                    <div className="w-8 h-8 rounded-full bg-cyan-500/20 flex items-center justify-center flex-shrink-0">
                      <span className="text-cyan-400 font-bold">4</span>
                    </div>
                    <div>
                      <h4 className="text-sm font-medium text-white">Friend Gets Discount</h4>
                      <p className="text-xs text-gray-400">Your friend receives {formatPercentage(REFERRAL_DISCOUNT)} off their first month</p>
                    </div>
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>
      </Tabs>

      {/* ============================================ */}
      {/* ADD PAYMENT METHOD MODAL */}
      {/* ============================================ */}
      <Modal
        open={showAddPaymentMethod}
        onOpenChange={setShowAddPaymentMethod}
        title="Add Payment Method"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Card Number *</label>
            <Input
              value={newPaymentMethod.cardNumber}
              onChange={(e) => setNewPaymentMethod({ ...newPaymentMethod, cardNumber: e.target.value })}
              placeholder="4242 4242 4242 4242"
              className="w-full bg-gray-700 border-gray-600 text-white font-mono"
              maxLength={19}
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Cardholder Name *</label>
            <Input
              value={newPaymentMethod.cardName}
              onChange={(e) => setNewPaymentMethod({ ...newPaymentMethod, cardName: e.target.value })}
              placeholder="John Doe"
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-sm text-gray-400 mb-1">MM *</label>
              <Input
                value={newPaymentMethod.expiryMonth}
                onChange={(e) => setNewPaymentMethod({ ...newPaymentMethod, expiryMonth: e.target.value })}
                placeholder="12"
                className="w-full bg-gray-700 border-gray-600 text-white"
                maxLength={2}
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">YY *</label>
              <Input
                value={newPaymentMethod.expiryYear}
                onChange={(e) => setNewPaymentMethod({ ...newPaymentMethod, expiryYear: e.target.value })}
                placeholder="25"
                className="w-full bg-gray-700 border-gray-600 text-white"
                maxLength={2}
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">CVV *</label>
              <Input
                value={newPaymentMethod.cvv}
                onChange={(e) => setNewPaymentMethod({ ...newPaymentMethod, cvv: e.target.value })}
                placeholder="123"
                className="w-full bg-gray-700 border-gray-600 text-white font-mono"
                maxLength={4}
                type="password"
              />
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Switch
              checked={newPaymentMethod.isDefault}
              onCheckedChange={(checked) => setNewPaymentMethod({ ...newPaymentMethod, isDefault: checked })}
              className="data-[state=checked]:bg-cyan-500"
            />
            <span className="text-sm text-gray-400">Set as default payment method</span>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => setShowAddPaymentMethod(false)}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handleAddPaymentMethod}
              isLoading={isAddingPaymentMethod}
              className="bg-gradient-to-r from-purple-500 to-pink-500"
            >
              Add Payment Method
            </Button>
          </div>
        </div>
      </Modal>

      {/* ============================================ */}
      {/* INVOICE VIEW MODAL */}
      {/* ============================================ */}
      <Modal
        open={showInvoiceModal}
        onOpenChange={setShowInvoiceModal}
        title={`Invoice #${selectedInvoice?.number || ''}`}
        className="max-w-2xl"
      >
        {selectedInvoice && (
          <div className="space-y-4">
            <div className="flex justify-between items-start">
              <div>
                <p className="text-sm text-gray-400">Date</p>
                <p className="text-white">{formatDate(selectedInvoice.date)}</p>
              </div>
              <div className="text-right">
                <p className="text-sm text-gray-400">Amount</p>
                <p className="text-xl font-bold text-white">
                  {formatCurrency(selectedInvoice.amount, selectedInvoice.currency)}
                </p>
              </div>
            </div>
            <div className="border-t border-gray-700 pt-4">
              <p className="text-sm text-gray-400">Description</p>
              <p className="text-white">{selectedInvoice.description || 'Subscription payment'}</p>
            </div>
            <div className="border-t border-gray-700 pt-4 flex justify-between">
              <div>
                <p className="text-sm text-gray-400">Status</p>
                <Badge className={cn(
                  "text-xs",
                  selectedInvoice.status === 'paid' ? 'bg-green-500/20 text-green-500' :
                  selectedInvoice.status === 'pending' ? 'bg-yellow-500/20 text-yellow-500' :
                  'bg-red-500/20 text-red-500'
                )}>
                  {selectedInvoice.status?.toUpperCase()}
                </Badge>
              </div>
              <Button
                variant="outline"
                onClick={() => handleDownloadInvoice(selectedInvoice.id)}
                isLoading={isDownloadingInvoice}
                className="border-gray-600 hover:border-cyan-500"
              >
                <Download className="w-4 h-4 mr-2" />
                Download PDF
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* ============================================ */}
      {/* CANCEL SUBSCRIPTION MODAL */}
      {/* ============================================ */}
      <Modal
        open={showCancelModal}
        onOpenChange={setShowCancelModal}
        title="Cancel Subscription"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3">
            <p className="text-sm text-red-400 flex items-center gap-2">
              <AlertCircle className="w-5 h-5" />
              This action cannot be undone
            </p>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Reason for cancelling *</label>
            <Select
              value={cancelReason}
              onValueChange={setCancelReason}
              className="w-full bg-gray-700 border-gray-600"
            >
              <option value="">Select a reason...</option>
              <option value="too_expensive">Too expensive</option>
              <option value="not_using">Not using enough</option>
              <option value="found_alternative">Found alternative</option>
              <option value="technical_issues">Technical issues</option>
              <option value="other">Other</option>
            </Select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Feedback (optional)</label>
            <Textarea
              value={cancelFeedback}
              onChange={(e) => setCancelFeedback(e.target.value)}
              placeholder="Tell us how we can improve..."
              className="w-full bg-gray-700 border-gray-600 text-white resize-none"
              rows={3}
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => {
                setShowCancelModal(false);
                setCancelReason('');
                setCancelFeedback('');
              }}
              className="border-gray-600 hover:border-gray-500"
            >
              Keep Subscription
            </Button>
            <Button
              variant="destructive"
              onClick={handleCancel}
              isLoading={isCancelling}
              className="bg-red-600 hover:bg-red-700"
            >
              Cancel Subscription
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

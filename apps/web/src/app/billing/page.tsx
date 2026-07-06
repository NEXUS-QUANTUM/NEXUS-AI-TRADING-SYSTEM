/**
 * NEXUS AI TRADING SYSTEM - Billing Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page handles billing management including:
 * - Subscription plan management
 * - Payment method management
 * - Invoice history and viewing
 * - Usage analytics and limits
 * - Plan upgrade/downgrade
 * - Cancel subscription
 * - Billing information update
 * - Payment processing
 * - Tax management
 * - Receipt download
 * - Auto-renewal management
 * - Billing notifications
 * - Multi-currency support
 * - Usage tracking
 * - API rate limit management
 */

'use client';

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { useApi } from '@/hooks/useApi';
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
import { Table } from '@/components/ui/Table';
import { Switch } from '@/components/ui/Switch';
import { Textarea } from '@/components/ui/Textarea';

// Icons
import {
  CreditCard,
  Receipt,
  Download,
  RefreshCw,
  AlertCircle,
  CheckCircle,
  XCircle,
  Clock,
  Shield,
  Zap,
  TrendingUp,
  Users,
  Database,
  Layers,
  FileText,
  Trash2,
  Edit,
  Plus,
  ChevronRight,
  Sparkles,
  Crown,
  Star,
  DollarSign,
  Calendar,
  Settings,
  HelpCircle,
  Info,
  Package,
  Mail,
  Phone,
  Building,
  MapPin,
  Globe,
  Lock,
  Key,
  Upload,
  Eye,
  EyeOff,
  ArrowRight,
  Check,
  X,
} from 'lucide-react';

// Utils
import { formatCurrency, formatDate, formatNumber, formatBytes } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

// Constants
import {
  SUBSCRIPTION_PLANS,
  SUBSCRIPTION_FEATURES,
  PAYMENT_METHODS,
  CURRENCIES,
  BILLING_CYCLES,
  TAX_RATES,
} from '@/constants/billing';

export default function BillingPage() {
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

  // State - Subscription
  const [currentPlan, setCurrentPlan] = useState<any>(null);
  const [selectedPlan, setSelectedPlan] = useState<string>('pro');
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'annual'>('monthly');
  const [isUpgrading, setIsUpgrading] = useState<boolean>(false);
  const [isDowngrading, setIsDowngrading] = useState<boolean>(false);
  const [isCancelling, setIsCancelling] = useState<boolean>(false);

  // State - Payment Methods
  const [paymentMethods, setPaymentMethods] = useState<any[]>([]);
  const [defaultPaymentMethod, setDefaultPaymentMethod] = useState<string>('');
  const [paymentMethodsLoading, setPaymentMethodsLoading] = useState<boolean>(true);
  const [showAddPaymentMethod, setShowAddPaymentMethod] = useState<boolean>(false);
  const [newPaymentMethod, setNewPaymentMethod] = useState({
    cardNumber: '',
    cardName: '',
    expiryMonth: '',
    expiryYear: '',
    cvv: '',
    isDefault: false,
  });
  const [isAddingPaymentMethod, setIsAddingPaymentMethod] = useState<boolean>(false);
  const [isDeletingPaymentMethod, setIsDeletingPaymentMethod] = useState<boolean>(false);

  // State - Invoices
  const [invoices, setInvoices] = useState<any[]>([]);
  const [invoicesLoading, setInvoicesLoading] = useState<boolean>(true);
  const [selectedInvoice, setSelectedInvoice] = useState<any>(null);
  const [showInvoiceModal, setShowInvoiceModal] = useState<boolean>(false);
  const [isDownloadingInvoice, setIsDownloadingInvoice] = useState<boolean>(false);

  // State - Usage
  const [usage, setUsage] = useState<any>(null);
  const [usageLoading, setUsageLoading] = useState<boolean>(true);

  // State - Billing Info
  const [billingInfo, setBillingInfo] = useState<any>(null);
  const [billingInfoLoading, setBillingInfoLoading] = useState<boolean>(true);
  const [showBillingInfoModal, setShowBillingInfoModal] = useState<boolean>(false);
  const [isUpdatingBillingInfo, setIsUpdatingBillingInfo] = useState<boolean>(false);

  // State - UI
  const [activeTab, setActiveTab] = useState<string>('overview');
  const [showCancelModal, setShowCancelModal] = useState<boolean>(false);
  const [cancelReason, setCancelReason] = useState<string>('');
  const [cancelFeedback, setCancelFeedback] = useState<string>('');
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);

  // Refs
  const planSectionRef = useRef<HTMLDivElement>(null);

  // ============================================
  // Effects
  // ============================================

  // Redirect if not authenticated
  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/authentication/login?callbackUrl=/billing');
    }
  }, [isAuthenticated, router]);

  // Load data
  useEffect(() => {
    if (isAuthenticated) {
      fetchAllData();
    }
  }, [isAuthenticated]);

  // Set current plan from subscription
  useEffect(() => {
    if (subscription) {
      setCurrentPlan(subscription.plan);
      setBillingCycle(subscription.cycle || 'monthly');
    }
  }, [subscription]);

  // ============================================
  // API Calls
  // ============================================

  const fetchPaymentMethods = useCallback(async () => {
    try {
      setPaymentMethodsLoading(true);
      const response = await api.get('/billing/payment-methods');
      if (response.data) {
        setPaymentMethods(response.data.methods || []);
        const defaultMethod = response.data.methods?.find((m: any) => m.isDefault);
        if (defaultMethod) {
          setDefaultPaymentMethod(defaultMethod.id);
        }
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
      const response = await api.get('/billing/invoices');
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
      const response = await api.get('/billing/usage');
      if (response.data) {
        setUsage(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch usage:', error);
    } finally {
      setUsageLoading(false);
    }
  }, [api]);

  const fetchBillingInfo = useCallback(async () => {
    try {
      setBillingInfoLoading(true);
      const response = await api.get('/billing/info');
      if (response.data) {
        setBillingInfo(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch billing info:', error);
    } finally {
      setBillingInfoLoading(false);
    }
  }, [api]);

  const fetchAllData = useCallback(async () => {
    setIsLoading(true);
    try {
      await Promise.all([
        fetchPaymentMethods(),
        fetchInvoices(),
        fetchUsage(),
        fetchBillingInfo(),
        refreshSubscription(),
      ]);
    } catch (error) {
      console.error('Failed to fetch billing data:', error);
      setShowToast({
        message: 'Failed to load billing data. Please refresh the page.',
        type: 'error',
      });
    } finally {
      setIsLoading(false);
    }
  }, [fetchPaymentMethods, fetchInvoices, fetchUsage, fetchBillingInfo, refreshSubscription]);

  // ============================================
  // Handlers - Subscription
  // ============================================

  const handleUpgrade = useCallback(async (planId: string) => {
    if (!planId) return;

    setIsUpgrading(true);
    try {
      const result = await upgradeSubscription(planId, billingCycle);
      if (result.success) {
        setShowToast({
          message: `Successfully upgraded to ${result.plan.name}!`,
          type: 'success',
        });
        await refreshSubscription();
        if (planSectionRef.current) {
          planSectionRef.current.scrollIntoView({ behavior: 'smooth' });
        }
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
    if (!planId) return;

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
      const response = await api.put('/billing/subscription/auto-renew', {
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
      const response = await api.post('/billing/payment-methods', newPaymentMethod);
      if (response.data) {
        setPaymentMethods(prev => [...prev, response.data.method]);
        if (response.data.method.isDefault) {
          setDefaultPaymentMethod(response.data.method.id);
        }
        setShowAddPaymentMethod(false);
        setNewPaymentMethod({
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
  }, [newPaymentMethod, api]);

  const handleDeletePaymentMethod = useCallback(async (id: string) => {
    if (!confirm('Are you sure you want to remove this payment method?')) return;

    setIsDeletingPaymentMethod(true);
    try {
      await api.delete(`/billing/payment-methods/${id}`);
      setPaymentMethods(prev => prev.filter(m => m.id !== id));
      if (defaultPaymentMethod === id) {
        setDefaultPaymentMethod('');
      }
      setShowToast({
        message: 'Payment method removed.',
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to remove payment method.',
        type: 'error',
      });
    } finally {
      setIsDeletingPaymentMethod(false);
    }
  }, [api, defaultPaymentMethod]);

  const handleSetDefaultPaymentMethod = useCallback(async (id: string) => {
    try {
      const response = await api.put(`/billing/payment-methods/${id}/default`);
      if (response.data) {
        setDefaultPaymentMethod(id);
        setPaymentMethods(prev =>
          prev.map(m => ({
            ...m,
            isDefault: m.id === id,
          }))
        );
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

  const handleViewInvoice = useCallback((invoice: any) => {
    setSelectedInvoice(invoice);
    setShowInvoiceModal(true);
  }, []);

  const handleDownloadInvoice = useCallback(async (id: string) => {
    setIsDownloadingInvoice(true);
    try {
      const response = await api.get(`/billing/invoices/${id}/download`, {
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
  // Handlers - Billing Info
  // ============================================

  const handleUpdateBillingInfo = useCallback(async () => {
    setIsUpdatingBillingInfo(true);
    try {
      const response = await api.put('/billing/info', billingInfo);
      if (response.data) {
        setBillingInfo(response.data);
        setShowBillingInfoModal(false);
        setShowToast({
          message: 'Billing information updated successfully.',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to update billing information.',
        type: 'error',
      });
    } finally {
      setIsUpdatingBillingInfo(false);
    }
  }, [api, billingInfo]);

  // ============================================
  // Memoized Computations
  // ============================================

  const availablePlans = useMemo(() => {
    if (!plans) return SUBSCRIPTION_PLANS;
    return plans;
  }, [plans]);

  const currentPlanFeatures = useMemo(() => {
    if (!currentPlan) return [];
    return SUBSCRIPTION_FEATURES[currentPlan.id] || [];
  }, [currentPlan]);

  const totalUsage = useMemo(() => {
    if (!usage) return { apiCalls: 0, apiLimit: 1000, storageUsed: 0, storageLimit: 10 };
    return {
      apiCalls: usage.apiCalls || 0,
      apiLimit: usage.apiLimit || 1000,
      storageUsed: usage.storageUsed || 0,
      storageLimit: usage.storageLimit || 10,
    };
  }, [usage]);

  const activeInvoices = useMemo(() => {
    return invoices.filter(inv => inv.status === 'paid' || inv.status === 'pending');
  }, [invoices]);

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
          <p className="text-gray-400 text-lg font-medium">Loading Billing...</p>
          <p className="text-gray-500 text-sm mt-2">Fetching your subscription details</p>
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
            <div className="text-3xl">💳</div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                Billing & Subscription
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                Manage your subscription, payment methods, and billing history
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchAllData()}
            className="border-gray-700 hover:border-cyan-500 hover:text-cyan-400 transition-colors"
          >
            <RefreshCw className="w-4 h-4 mr-2" />
            Refresh
          </Button>
          {subscription?.status === 'active' && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowCancelModal(true)}
              className="border-red-500/50 hover:border-red-500 text-red-400 hover:text-red-300 hover:bg-red-500/10"
            >
              <XCircle className="w-4 h-4 mr-2" />
              Cancel Subscription
            </Button>
          )}
          {subscription?.status === 'cancelled' && (
            <Button
              variant="primary"
              size="sm"
              onClick={handleReactivate}
              className="bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600"
            >
              <RefreshCw className="w-4 h-4 mr-2" />
              Reactivate
            </Button>
          )}
        </div>
      </div>

      {/* ============================================ */}
      {/* SUBSCRIPTION STATUS */}
      {/* ============================================ */}
      {subscription && (
        <div className="mb-8">
          <Card className="p-6 bg-gray-800 border-gray-700">
            <div className="flex flex-wrap items-center justify-between gap-4">
              <div className="flex items-center gap-4">
                <div className={cn(
                  "w-12 h-12 rounded-full flex items-center justify-center",
                  subscription.status === 'active' ? 'bg-green-500/20' :
                  subscription.status === 'cancelled' ? 'bg-red-500/20' :
                  subscription.status === 'past_due' ? 'bg-yellow-500/20' :
                  'bg-gray-500/20'
                )}>
                  {subscription.status === 'active' && <CheckCircle className="w-6 h-6 text-green-500" />}
                  {subscription.status === 'cancelled' && <XCircle className="w-6 h-6 text-red-500" />}
                  {subscription.status === 'past_due' && <AlertCircle className="w-6 h-6 text-yellow-500" />}
                  {subscription.status === 'trialing' && <Sparkles className="w-6 h-6 text-purple-500" />}
                </div>
                <div>
                  <div className="flex items-center gap-3">
                    <h2 className="text-xl font-bold text-white">{subscription.plan?.name || 'Free Plan'}</h2>
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
                    {subscription.plan?.description || 'Free tier with limited features'}
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
            {subscription.plan?.id !== 'free' && (
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
        </div>
      )}

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
            value="plans"
            className="data-[state=active]:bg-blue-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📦 Plans
          </TabsTrigger>
          <TabsTrigger
            value="payment"
            className="data-[state=active]:bg-purple-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            💳 Payment Methods
          </TabsTrigger>
          <TabsTrigger
            value="invoices"
            className="data-[state=active]:bg-green-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📄 Invoices
          </TabsTrigger>
          <TabsTrigger
            value="usage"
            className="data-[state=active]:bg-orange-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📈 Usage
          </TabsTrigger>
          <TabsTrigger
            value="settings"
            className="data-[state=active]:bg-gray-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            ⚙️ Settings
          </TabsTrigger>
        </TabsList>

        {/* ========================================== */}
        {/* OVERVIEW TAB */}
        {/* ========================================== */}
        <TabsContent value="overview" className="mt-4 space-y-6">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
                  <span className="text-cyan-400">📋</span> Current Plan Details
                </h3>
                {subscription ? (
                  <div className="space-y-3">
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Plan</span>
                      <span className="text-white font-medium">{subscription.plan?.name}</span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Price</span>
                      <span className="text-white font-medium">
                        {formatCurrency(subscription.price || 0, subscription.currency || 'USD')}
                        <span className="text-gray-500 text-xs ml-1">/{subscription.cycle}</span>
                      </span>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Status</span>
                      <Badge className={cn(
                        "text-xs",
                        subscription.status === 'active' ? 'bg-green-500/20 text-green-500' :
                        subscription.status === 'cancelled' ? 'bg-red-500/20 text-red-500' :
                        'bg-yellow-500/20 text-yellow-500'
                      )}>
                        {subscription.status?.toUpperCase()}
                      </Badge>
                    </div>
                    <div className="flex justify-between text-sm">
                      <span className="text-gray-400">Auto-renew</span>
                      <div className="flex items-center gap-2">
                        <span className={subscription.autoRenew ? 'text-green-500' : 'text-red-500'}>
                          {subscription.autoRenew ? 'On' : 'Off'}
                        </span>
                        <Switch
                          checked={subscription.autoRenew}
                          onCheckedChange={handleToggleAutoRenew}
                          className="data-[state=checked]:bg-cyan-500"
                        />
                      </div>
                    </div>
                    {subscription.startedAt && (
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-400">Started</span>
                        <span className="text-white">{formatDate(subscription.startedAt)}</span>
                      </div>
                    )}
                    {subscription.nextBillingDate && (
                      <div className="flex justify-between text-sm">
                        <span className="text-gray-400">Next billing</span>
                        <span className="text-white">{formatDate(subscription.nextBillingDate)}</span>
                      </div>
                    )}
                  </div>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <p>No active subscription</p>
                    <p className="text-sm">Choose a plan to get started</p>
                  </div>
                )}
              </Card>
            </div>

            <div className="col-span-12 lg:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
                  <span className="text-blue-400">⚡</span> Quick Actions
                </h3>
                <div className="grid grid-cols-2 gap-3">
                  <Button
                    variant="outline"
                    className="border-gray-700 hover:border-cyan-500 hover:text-cyan-400 transition-colors justify-start"
                    onClick={() => setActiveTab('plans')}
                  >
                    <Package className="w-4 h-4 mr-2" />
                    Change Plan
                  </Button>
                  <Button
                    variant="outline"
                    className="border-gray-700 hover:border-cyan-500 hover:text-cyan-400 transition-colors justify-start"
                    onClick={() => setActiveTab('payment')}
                  >
                    <CreditCard className="w-4 h-4 mr-2" />
                    Manage Payment
                  </Button>
                  <Button
                    variant="outline"
                    className="border-gray-700 hover:border-cyan-500 hover:text-cyan-400 transition-colors justify-start"
                    onClick={() => setActiveTab('invoices')}
                  >
                    <Receipt className="w-4 h-4 mr-2" />
                    View Invoices
                  </Button>
                  <Button
                    variant="outline"
                    className="border-gray-700 hover:border-cyan-500 hover:text-cyan-400 transition-colors justify-start"
                    onClick={() => setShowBillingInfoModal(true)}
                  >
                    <Building className="w-4 h-4 mr-2" />
                    Billing Info
                  </Button>
                </div>
              </Card>

              <Card className="p-4 bg-gray-800 border-gray-700 mt-4">
                <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                  <span className="text-purple-400">📞</span> Billing Contact
                </h3>
                <div className="space-y-2 text-sm">
                  {billingInfo ? (
                    <>
                      <div className="flex items-center gap-2 text-gray-400">
                        <Mail className="w-4 h-4" />
                        {billingInfo.email || user?.email}
                      </div>
                      {billingInfo.phone && (
                        <div className="flex items-center gap-2 text-gray-400">
                          <Phone className="w-4 h-4" />
                          {billingInfo.phone}
                        </div>
                      )}
                      {billingInfo.company && (
                        <div className="flex items-center gap-2 text-gray-400">
                          <Building className="w-4 h-4" />
                          {billingInfo.company}
                        </div>
                      )}
                      {billingInfo.address && (
                        <div className="flex items-start gap-2 text-gray-400">
                          <MapPin className="w-4 h-4 mt-0.5" />
                          <span>{billingInfo.address}</span>
                        </div>
                      )}
                    </>
                  ) : (
                    <div className="text-gray-500">
                      <p>No billing contact information set.</p>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowBillingInfoModal(true)}
                        className="text-cyan-400 hover:text-cyan-300 mt-2"
                      >
                        Add billing information
                      </Button>
                    </div>
                  )}
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* PLANS TAB */}
        {/* ========================================== */}
        <TabsContent value="plans" className="mt-4">
          <div ref={planSectionRef} className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {availablePlans.map((plan) => {
              const isCurrentPlan = currentPlan?.id === plan.id;
              const isUpgrade = plan.priority > (currentPlan?.priority || 0);
              const isDowngrade = plan.priority < (currentPlan?.priority || 0);
              const planFeatures = SUBSCRIPTION_FEATURES[plan.id] || [];

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
                    isCurrentPlan && "border-cyan-500 ring-2 ring-cyan-500/20",
                    !isCurrentPlan && "hover:border-cyan-500/50",
                    plan.popular && "border-yellow-500/30"
                  )}>
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-lg font-bold text-white">{plan.name}</h3>
                      {isCurrentPlan && (
                        <Badge className="bg-cyan-500/20 text-cyan-400 border-cyan-500/30">
                          Current
                        </Badge>
                      )}
                    </div>
                    <p className="text-sm text-gray-400 mb-4">{plan.description}</p>
                    <div className="mb-4">
                      <span className="text-3xl font-bold text-white">
                        {formatCurrency(plan.monthlyPrice, 'USD')}
                      </span>
                      <span className="text-sm text-gray-400 ml-1">/month</span>
                      {plan.annualPrice && (
                        <div className="text-sm text-gray-500 mt-1">
                          or {formatCurrency(plan.annualPrice, 'USD')}/year 
                          <span className="text-green-500 ml-1">(Save {Math.round((1 - plan.annualPrice / (plan.monthlyPrice * 12)) * 100)}%)</span>
                        </div>
                      )}
                    </div>

                    {/* Features */}
                    <div className="flex-1 space-y-2 mb-6">
                      {planFeatures.map((feature, idx) => (
                        <div key={idx} className="flex items-start gap-2 text-sm">
                          <CheckCircle className="w-4 h-4 text-cyan-500 mt-0.5 flex-shrink-0" />
                          <span className="text-gray-300">{feature}</span>
                        </div>
                      ))}
                    </div>

                    {/* Action Button */}
                    <Button
                      variant={isCurrentPlan ? 'outline' : plan.popular ? 'primary' : 'outline'}
                      disabled={isCurrentPlan || isUpgrading || isDowngrading}
                      onClick={() => {
                        if (isUpgrade) {
                          handleUpgrade(plan.id);
                        } else if (isDowngrade) {
                          handleDowngrade(plan.id);
                        }
                      }}
                      className={cn(
                        "w-full transition-all",
                        isCurrentPlan ? "border-gray-600 text-gray-400 cursor-default" :
                        plan.popular ? "bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-600 hover:to-orange-600 text-white" :
                        "border-gray-600 hover:border-cyan-500 hover:text-cyan-400"
                      )}
                    >
                      {isCurrentPlan ? 'Current Plan' :
                       isUpgrade ? 'Upgrade' :
                       isDowngrade ? 'Downgrade' :
                       'Select Plan'}
                      {!isCurrentPlan && <ArrowRight className="w-4 h-4 ml-2" />}
                    </Button>
                  </Card>
                </motion.div>
              );
            })}
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* PAYMENT METHODS TAB */}
        {/* ========================================== */}
        <TabsContent value="payment" className="mt-4 space-y-6">
          <div className="flex justify-between items-center">
            <h3 className="text-sm font-semibold text-gray-300">Payment Methods</h3>
            <Button
              onClick={() => setShowAddPaymentMethod(true)}
              className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Payment Method
            </Button>
          </div>

          {paymentMethodsLoading ? (
            <div className="text-center py-8">
              <Spinner size="lg" className="mx-auto mb-4 text-cyan-500" />
              <p className="text-gray-400">Loading payment methods...</p>
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
                        <Trash2 className="w-4 h-4" />
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
            <div className="text-center py-12 text-gray-500">
              <CreditCard className="w-16 h-16 mx-auto mb-4 text-gray-600" />
              <p>No payment methods added</p>
              <p className="text-sm">Add a payment method to subscribe to a plan</p>
            </div>
          )}
        </TabsContent>

        {/* ========================================== */}
        {/* INVOICES TAB */}
        {/* ========================================== */}
        <TabsContent value="invoices" className="mt-4">
          {invoicesLoading ? (
            <div className="text-center py-8">
              <Spinner size="lg" className="mx-auto mb-4 text-cyan-500" />
              <p className="text-gray-400">Loading invoices...</p>
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
            <div className="text-center py-12 text-gray-500">
              <Receipt className="w-16 h-16 mx-auto mb-4 text-gray-600" />
              <p>No invoices found</p>
              <p className="text-sm">Your invoices will appear here once you start a subscription</p>
            </div>
          )}
        </TabsContent>

        {/* ========================================== */}
        {/* USAGE TAB */}
        {/* ========================================== */}
        <TabsContent value="usage" className="mt-4">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 md:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
                  <span className="text-orange-400">📊</span> API Usage
                </h3>
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
              </Card>
            </div>

            <div className="col-span-12 md:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
                  <span className="text-blue-400">📈</span> Usage Breakdown
                </h3>
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
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* SETTINGS TAB */}
        {/* ========================================== */}
        <TabsContent value="settings" className="mt-4">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 md:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
                  <span className="text-purple-400">⚙️</span> Billing Settings
                </h3>
                <div className="space-y-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Currency</label>
                    <Select 
                      className="w-full bg-gray-700 border-gray-600 text-white"
                      value={billingInfo?.currency || 'USD'}
                      onValueChange={(value) => setBillingInfo({ ...billingInfo, currency: value })}
                    >
                      {CURRENCIES.map(currency => (
                        <option key={currency} value={currency}>{currency}</option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Tax ID (optional)</label>
                    <Input
                      value={billingInfo?.taxId || ''}
                      onChange={(e) => setBillingInfo({ ...billingInfo, taxId: e.target.value })}
                      placeholder="Enter your tax ID"
                      className="w-full bg-gray-700 border-gray-600 text-white"
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-400">Email receipts</span>
                    <Switch
                      checked={billingInfo?.emailReceipts !== false}
                      onCheckedChange={(checked) => setBillingInfo({ ...billingInfo, emailReceipts: checked })}
                      className="data-[state=checked]:bg-cyan-500"
                    />
                  </div>
                  <Button
                    onClick={handleUpdateBillingInfo}
                    isLoading={isUpdatingBillingInfo}
                    className="w-full bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
                  >
                    Save Settings
                  </Button>
                </div>
              </Card>
            </div>

            <div className="col-span-12 md:col-span-6">
              <Card className="p-4 bg-gray-800 border-gray-700">
                <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
                  <span className="text-red-400">⚠️</span> Danger Zone
                </h3>
                <div className="space-y-4">
                  <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
                    <p className="text-sm text-red-400 font-medium">Delete Account</p>
                    <p className="text-xs text-gray-400 mt-1">
                      Permanently delete your account and all associated data. This action cannot be undone.
                    </p>
                    <Button
                      variant="destructive"
                      size="sm"
                      className="mt-3 bg-red-600 hover:bg-red-700"
                      onClick={() => {
                        if (confirm('Are you sure you want to delete your account? This action cannot be undone.')) {
                          // Handle account deletion
                        }
                      }}
                    >
                      Delete Account
                    </Button>
                  </div>
                  <div className="p-4 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                    <p className="text-sm text-yellow-400 font-medium">Export Data</p>
                    <p className="text-xs text-gray-400 mt-1">
                      Download all your data including transactions, trades, and history.
                    </p>
                    <Button
                      variant="outline"
                      size="sm"
                      className="mt-3 border-yellow-500/50 hover:border-yellow-500 text-yellow-400"
                      onClick={() => {
                        // Handle data export
                      }}
                    >
                      Export Data
                    </Button>
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
              className="bg-gradient-to-r from-purple-500 to-pink-500 hover:from-purple-600 hover:to-pink-600"
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
              className="w-full bg-gray-700 border-gray-600 text-white"
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
      {/* BILLING INFO MODAL */}
      {/* ============================================ */}
      <Modal
        open={showBillingInfoModal}
        onOpenChange={setShowBillingInfoModal}
        title="Billing Information"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Company (optional)</label>
            <Input
              value={billingInfo?.company || ''}
              onChange={(e) => setBillingInfo({ ...billingInfo, company: e.target.value })}
              placeholder="Your company name"
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Email *</label>
            <Input
              value={billingInfo?.email || user?.email || ''}
              onChange={(e) => setBillingInfo({ ...billingInfo, email: e.target.value })}
              placeholder="billing@example.com"
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Phone (optional)</label>
            <Input
              value={billingInfo?.phone || ''}
              onChange={(e) => setBillingInfo({ ...billingInfo, phone: e.target.value })}
              placeholder="+1 234 567 8900"
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Address (optional)</label>
            <Textarea
              value={billingInfo?.address || ''}
              onChange={(e) => setBillingInfo({ ...billingInfo, address: e.target.value })}
              placeholder="Street, City, Country, ZIP"
              className="w-full bg-gray-700 border-gray-600 text-white resize-none"
              rows={3}
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">VAT/Tax ID (optional)</label>
            <Input
              value={billingInfo?.taxId || ''}
              onChange={(e) => setBillingInfo({ ...billingInfo, taxId: e.target.value })}
              placeholder="Enter your tax ID"
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => setShowBillingInfoModal(false)}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handleUpdateBillingInfo}
              isLoading={isUpdatingBillingInfo}
              className="bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600"
            >
              Save Information
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

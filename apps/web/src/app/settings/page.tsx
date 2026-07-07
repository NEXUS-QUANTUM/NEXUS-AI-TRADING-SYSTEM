/**
 * NEXUS AI TRADING SYSTEM - Settings Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page provides comprehensive settings management including:
 * - Profile settings and customization
 * - Account security and authentication
 * - Notification preferences
 * - Trading preferences and defaults
 * - API key management
 * - Two-factor authentication (2FA)
 * - Session management
 * - Privacy settings
 * - Data export and management
 * - Language and localization
 * - Theme customization
 * - Trading alerts configuration
 * - Risk management defaults
 * - Integration settings
 * - Webhook configuration
 * - Audit logs
 * - Connected devices
 * - Billing and subscription settings
 * - Referral settings
 * - Support and help settings
 */

'use client';

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useRouter } from 'next/navigation';
import { useAuth } from '@/hooks/useAuth';
import { useApi } from '@/hooks/useApi';

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
import { Switch } from '@/components/ui/Switch';
import { Textarea } from '@/components/ui/Textarea';
import { Avatar } from '@/components/ui/Avatar';
import { Progress } from '@/components/ui/Progress';
import { Table } from '@/components/ui/Table';
import { CopyButton } from '@/components/ui/CopyButton';
import { Checkbox } from '@/components/ui/Checkbox';
import { Slider } from '@/components/ui/Slider';

// Icons
import {
  User,
  Mail,
  Phone,
  Shield,
  Key,
  Lock,
  Unlock,
  Eye,
  EyeOff,
  Bell,
  BellRing,
  BellOff,
  Settings as SettingsIcon,
  Palette,
  Globe,
  Language,
  Clock,
  Calendar,
  CreditCard,
  Wallet,
  Api,
  Link,
  Webhook,
  Database,
  Download,
  Upload,
  Trash2,
  Edit,
  Save,
  RefreshCw,
  Plus,
  Minus,
  X,
  Check,
  AlertCircle,
  Info,
  HelpCircle,
  Smartphone,
  Tablet,
  Laptop,
  Monitor,
  Server,
  Cloud,
  Network,
  Cpu,
  Memory,
  HardDrive,
  ShieldCheck,
  Fingerprint,
  Scan,
  QrCode,
  MailCheck,
  PhoneCheck,
  Globe2,
  MapPin,
  Building,
  Briefcase,
  DollarSign,
  CreditCard as CreditCardIcon,
  Wallet as WalletIcon,
  TrendingUp,
  BarChart3,
  PieChart,
  LineChart,
  Activity,
  Zap,
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
  BellRing as BellRingIcon,
  Mail as MailIcon,
  Phone as PhoneIcon,
  MapPin as MapPinIcon,
  Globe as GlobeIcon,
  Settings as GearIcon,
  User as UserIcon,
  Shield as ShieldIcon,
  Key as KeyIcon,
  Lock as LockIcon,
} from 'lucide-react';

// Types
import type {
  UserProfile,
  SecuritySettings,
  NotificationSettings,
  TradingSettings,
  APISettings,
  IntegrationSettings,
  PrivacySettings,
  SessionInfo,
  DeviceInfo,
  AuditLog,
  WebhookConfig,
  ReferralInfo,
  BillingInfo,
} from '@/types/settings';

// Constants
import {
  LANGUAGES,
  TIMEZONES,
  CURRENCIES,
  THEMES,
  CHART_TYPES,
  TIMEFRAMES,
  NOTIFICATION_TYPES,
  API_SCOPES,
  INTEGRATION_TYPES,
  WEBHOOK_EVENTS,
} from '@/constants/settings';

// Utils
import { formatDate, formatTime, formatCurrency } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

export default function SettingsPage() {
  // Router
  const router = useRouter();

  // Auth hooks
  const { user, isAuthenticated } = useAuth();

  // API client
  const api = useApi();

  // State - Profile
  const [profile, setProfile] = useState<UserProfile>({
    id: '',
    name: '',
    email: '',
    phone: '',
    avatar: '',
    bio: '',
    location: '',
    website: '',
    socialLinks: {},
    createdAt: new Date(),
    updatedAt: new Date(),
  });
  const [profileLoading, setProfileLoading] = useState<boolean>(true);
  const [isUpdatingProfile, setIsUpdatingProfile] = useState<boolean>(false);

  // State - Security
  const [security, setSecurity] = useState<SecuritySettings>({
    twoFactorEnabled: false,
    twoFactorSecret: '',
    backupCodes: [],
    emailVerified: false,
    phoneVerified: false,
    lastPasswordChange: new Date(),
    sessions: [],
    devices: [],
  });
  const [securityLoading, setSecurityLoading] = useState<boolean>(true);
  const [show2FAModal, setShow2FAModal] = useState<boolean>(false);
  const [showPasswordModal, setShowPasswordModal] = useState<boolean>(false);
  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });
  const [showCurrentPassword, setShowCurrentPassword] = useState<boolean>(false);
  const [showNewPassword, setShowNewPassword] = useState<boolean>(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState<boolean>(false);
  const [isUpdatingPassword, setIsUpdatingPassword] = useState<boolean>(false);
  const [isEnabling2FA, setIsEnabling2FA] = useState<boolean>(false);
  const [isDisabling2FA, setIsDisabling2FA] = useState<boolean>(false);

  // State - Notifications
  const [notifications, setNotifications] = useState<NotificationSettings>({
    email: {},
    push: {},
    inApp: {},
    slack: {},
    telegram: {},
    discord: {},
  });
  const [notificationsLoading, setNotificationsLoading] = useState<boolean>(true);
  const [isUpdatingNotifications, setIsUpdatingNotifications] = useState<boolean>(false);

  // State - Trading Preferences
  const [tradingPrefs, setTradingPrefs] = useState<TradingSettings>({
    defaultPair: 'BTC-USD',
    defaultTimeframe: '1h',
    chartType: 'candlestick',
    indicators: ['rsi', 'macd'],
    defaultOrderType: 'limit',
    defaultOrderSize: 0.001,
    maxPositionSize: 10000,
    riskPerTrade: 0.02,
    stopLossDefault: 0.05,
    takeProfitDefault: 0.10,
    slippageTolerance: 0.005,
    leverage: 1,
    marginCallLevel: 0.5,
    autoTradingEnabled: false,
    paperTradingEnabled: true,
  });
  const [tradingPrefsLoading, setTradingPrefsLoading] = useState<boolean>(true);
  const [isUpdatingTradingPrefs, setIsUpdatingTradingPrefs] = useState<boolean>(false);

  // State - API Keys
  const [apiKeys, setApiKeys] = useState<APISettings[]>([]);
  const [apiKeysLoading, setApiKeysLoading] = useState<boolean>(true);
  const [showApiKeyModal, setShowApiKeyModal] = useState<boolean>(false);
  const [newApiKey, setNewApiKey] = useState<Partial<APISettings>>({
    name: '',
    scopes: [],
    expiresAt: null,
  });
  const [isCreatingApiKey, setIsCreatingApiKey] = useState<boolean>(false);
  const [isDeletingApiKey, setIsDeletingApiKey] = useState<boolean>(false);
  const [generatedApiKey, setGeneratedApiKey] = useState<string | null>(null);
  const [showGeneratedKeyModal, setShowGeneratedKeyModal] = useState<boolean>(false);

  // State - Integrations
  const [integrations, setIntegrations] = useState<IntegrationSettings[]>([]);
  const [integrationsLoading, setIntegrationsLoading] = useState<boolean>(true);
  const [showIntegrationModal, setShowIntegrationModal] = useState<boolean>(false);
  const [newIntegration, setNewIntegration] = useState<Partial<IntegrationSettings>>({
    type: 'webhook',
    name: '',
    config: {},
    enabled: true,
  });
  const [isCreatingIntegration, setIsCreatingIntegration] = useState<boolean>(false);
  const [isDeletingIntegration, setIsDeletingIntegration] = useState<boolean>(false);

  // State - Privacy
  const [privacy, setPrivacy] = useState<PrivacySettings>({
    profileVisibility: 'public',
    showEmail: false,
    showPhone: false,
    showBalance: true,
    showTradingHistory: 'private',
    dataSharing: false,
    analyticsEnabled: true,
    marketingEmails: true,
  });
  const [privacyLoading, setPrivacyLoading] = useState<boolean>(true);
  const [isUpdatingPrivacy, setIsUpdatingPrivacy] = useState<boolean>(false);

  // State - Sessions & Devices
  const [sessions, setSessions] = useState<SessionInfo[]>([]);
  const [devices, setDevices] = useState<DeviceInfo[]>([]);
  const [sessionsLoading, setSessionsLoading] = useState<boolean>(true);
  const [isRevokingSession, setIsRevokingSession] = useState<boolean>(false);
  const [isRemovingDevice, setIsRemovingDevice] = useState<boolean>(false);

  // State - Audit Logs
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [auditLogsLoading, setAuditLogsLoading] = useState<boolean>(true);
  const [auditLogFilter, setAuditLogFilter] = useState<string>('all');

  // State - UI
  const [activeTab, setActiveTab] = useState<string>('profile');
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // ============================================
  // Effects
  // ============================================

  useEffect(() => {
    if (!isAuthenticated) {
      router.push('/authentication/login?callbackUrl=/settings');
    } else {
      fetchAllData();
    }
  }, [isAuthenticated, router]);

  // ============================================
  // API Calls
  // ============================================

  const fetchProfile = useCallback(async () => {
    try {
      setProfileLoading(true);
      const response = await api.get('/settings/profile');
      if (response.data) {
        setProfile(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch profile:', error);
    } finally {
      setProfileLoading(false);
    }
  }, [api]);

  const fetchSecurity = useCallback(async () => {
    try {
      setSecurityLoading(true);
      const response = await api.get('/settings/security');
      if (response.data) {
        setSecurity(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch security settings:', error);
    } finally {
      setSecurityLoading(false);
    }
  }, [api]);

  const fetchNotifications = useCallback(async () => {
    try {
      setNotificationsLoading(true);
      const response = await api.get('/settings/notifications');
      if (response.data) {
        setNotifications(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch notification settings:', error);
    } finally {
      setNotificationsLoading(false);
    }
  }, [api]);

  const fetchTradingPrefs = useCallback(async () => {
    try {
      setTradingPrefsLoading(true);
      const response = await api.get('/settings/trading');
      if (response.data) {
        setTradingPrefs(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch trading preferences:', error);
    } finally {
      setTradingPrefsLoading(false);
    }
  }, [api]);

  const fetchApiKeys = useCallback(async () => {
    try {
      setApiKeysLoading(true);
      const response = await api.get('/settings/api-keys');
      if (response.data) {
        setApiKeys(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch API keys:', error);
    } finally {
      setApiKeysLoading(false);
    }
  }, [api]);

  const fetchIntegrations = useCallback(async () => {
    try {
      setIntegrationsLoading(true);
      const response = await api.get('/settings/integrations');
      if (response.data) {
        setIntegrations(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch integrations:', error);
    } finally {
      setIntegrationsLoading(false);
    }
  }, [api]);

  const fetchPrivacy = useCallback(async () => {
    try {
      setPrivacyLoading(true);
      const response = await api.get('/settings/privacy');
      if (response.data) {
        setPrivacy(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch privacy settings:', error);
    } finally {
      setPrivacyLoading(false);
    }
  }, [api]);

  const fetchSessions = useCallback(async () => {
    try {
      setSessionsLoading(true);
      const response = await api.get('/settings/sessions');
      if (response.data) {
        setSessions(response.data.sessions || []);
        setDevices(response.data.devices || []);
      }
    } catch (error) {
      console.error('Failed to fetch sessions:', error);
    } finally {
      setSessionsLoading(false);
    }
  }, [api]);

  const fetchAuditLogs = useCallback(async () => {
    try {
      setAuditLogsLoading(true);
      const response = await api.get('/settings/audit-logs', {
        params: { limit: 100 },
      });
      if (response.data) {
        setAuditLogs(response.data.logs || []);
      }
    } catch (error) {
      console.error('Failed to fetch audit logs:', error);
    } finally {
      setAuditLogsLoading(false);
    }
  }, [api]);

  const fetchAllData = useCallback(async () => {
    setIsLoading(true);
    setIsRefreshing(true);
    try {
      await Promise.all([
        fetchProfile(),
        fetchSecurity(),
        fetchNotifications(),
        fetchTradingPrefs(),
        fetchApiKeys(),
        fetchIntegrations(),
        fetchPrivacy(),
        fetchSessions(),
        fetchAuditLogs(),
      ]);
    } catch (error) {
      console.error('Failed to fetch settings data:', error);
      setShowToast({
        message: 'Failed to load settings. Please refresh the page.',
        type: 'error',
      });
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [
    fetchProfile,
    fetchSecurity,
    fetchNotifications,
    fetchTradingPrefs,
    fetchApiKeys,
    fetchIntegrations,
    fetchPrivacy,
    fetchSessions,
    fetchAuditLogs,
  ]);

  // ============================================
  // Handlers - Profile
  // ============================================

  const handleProfileUpdate = useCallback(async () => {
    setIsUpdatingProfile(true);
    try {
      const response = await api.put('/settings/profile', profile);
      if (response.data) {
        setProfile(response.data);
        setShowToast({
          message: 'Profile updated successfully!',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to update profile.',
        type: 'error',
      });
    } finally {
      setIsUpdatingProfile(false);
    }
  }, [api, profile]);

  // ============================================
  // Handlers - Security
  // ============================================

  const handlePasswordUpdate = useCallback(async () => {
    if (passwordData.newPassword !== passwordData.confirmPassword) {
      setShowToast({
        message: 'Passwords do not match.',
        type: 'error',
      });
      return;
    }

    if (passwordData.newPassword.length < 8) {
      setShowToast({
        message: 'Password must be at least 8 characters.',
        type: 'error',
      });
      return;
    }

    setIsUpdatingPassword(true);
    try {
      const response = await api.put('/settings/security/password', {
        currentPassword: passwordData.currentPassword,
        newPassword: passwordData.newPassword,
      });
      if (response.data) {
        setShowPasswordModal(false);
        setPasswordData({
          currentPassword: '',
          newPassword: '',
          confirmPassword: '',
        });
        setShowToast({
          message: 'Password updated successfully!',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to update password.',
        type: 'error',
      });
    } finally {
      setIsUpdatingPassword(false);
    }
  }, [api, passwordData]);

  const handleEnable2FA = useCallback(async () => {
    setIsEnabling2FA(true);
    try {
      const response = await api.post('/settings/security/2fa/enable');
      if (response.data) {
        setSecurity(prev => ({
          ...prev,
          twoFactorEnabled: true,
          twoFactorSecret: response.data.secret,
          backupCodes: response.data.backupCodes,
        }));
        setShow2FAModal(true);
        setShowToast({
          message: '2FA enabled successfully! Save your backup codes.',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to enable 2FA.',
        type: 'error',
      });
    } finally {
      setIsEnabling2FA(false);
    }
  }, [api]);

  const handleDisable2FA = useCallback(async () => {
    setIsDisabling2FA(true);
    try {
      const response = await api.post('/settings/security/2fa/disable');
      if (response.data) {
        setSecurity(prev => ({
          ...prev,
          twoFactorEnabled: false,
          twoFactorSecret: '',
          backupCodes: [],
        }));
        setShow2FAModal(false);
        setShowToast({
          message: '2FA disabled successfully.',
          type: 'info',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to disable 2FA.',
        type: 'error',
      });
    } finally {
      setIsDisabling2FA(false);
    }
  }, [api]);

  // ============================================
  // Handlers - Notifications
  // ============================================

  const handleNotificationsUpdate = useCallback(async () => {
    setIsUpdatingNotifications(true);
    try {
      const response = await api.put('/settings/notifications', notifications);
      if (response.data) {
        setNotifications(response.data);
        setShowToast({
          message: 'Notification settings updated!',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to update notification settings.',
        type: 'error',
      });
    } finally {
      setIsUpdatingNotifications(false);
    }
  }, [api, notifications]);

  // ============================================
  // Handlers - Trading Preferences
  // ============================================

  const handleTradingPrefsUpdate = useCallback(async () => {
    setIsUpdatingTradingPrefs(true);
    try {
      const response = await api.put('/settings/trading', tradingPrefs);
      if (response.data) {
        setTradingPrefs(response.data);
        setShowToast({
          message: 'Trading preferences updated!',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to update trading preferences.',
        type: 'error',
      });
    } finally {
      setIsUpdatingTradingPrefs(false);
    }
  }, [api, tradingPrefs]);

  // ============================================
  // Handlers - API Keys
  // ============================================

  const handleCreateApiKey = useCallback(async () => {
    if (!newApiKey.name) {
      setShowToast({
        message: 'Please enter a name for the API key.',
        type: 'warning',
      });
      return;
    }

    if (!newApiKey.scopes || newApiKey.scopes.length === 0) {
      setShowToast({
        message: 'Please select at least one scope.',
        type: 'warning',
      });
      return;
    }

    setIsCreatingApiKey(true);
    try {
      const response = await api.post('/settings/api-keys', newApiKey);
      if (response.data) {
        setApiKeys(prev => [response.data.key, ...prev]);
        setGeneratedApiKey(response.data.rawKey);
        setShowApiKeyModal(false);
        setShowGeneratedKeyModal(true);
        setNewApiKey({
          name: '',
          scopes: [],
          expiresAt: null,
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to create API key.',
        type: 'error',
      });
    } finally {
      setIsCreatingApiKey(false);
    }
  }, [api, newApiKey]);

  const handleDeleteApiKey = useCallback(async (id: string) => {
    if (!confirm('Are you sure you want to delete this API key?')) return;

    setIsDeletingApiKey(true);
    try {
      await api.delete(`/settings/api-keys/${id}`);
      setApiKeys(prev => prev.filter(key => key.id !== id));
      setShowToast({
        message: 'API key deleted successfully.',
        type: 'info',
      });
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to delete API key.',
        type: 'error',
      });
    } finally {
      setIsDeletingApiKey(false);
    }
  }, [api]);

  // ============================================
  // Handlers - Sessions
  // ============================================

  const handleRevokeSession = useCallback(async (sessionId: string) => {
    if (!confirm('Are you sure you want to revoke this session?')) return;

    setIsRevokingSession(true);
    try {
      await api.delete(`/settings/sessions/${sessionId}`);
      setSessions(prev => prev.filter(s => s.id !== sessionId));
      setShowToast({
        message: 'Session revoked successfully.',
        type: 'info',
      });
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to revoke session.',
        type: 'error',
      });
    } finally {
      setIsRevokingSession(false);
    }
  }, [api]);

  const handleRevokeAllSessions = useCallback(async () => {
    if (!confirm('Are you sure you want to revoke all sessions except the current one?')) return;

    setIsRevokingSession(true);
    try {
      await api.delete('/settings/sessions/all');
      setSessions(prev => prev.filter(s => s.isCurrent));
      setShowToast({
        message: 'All other sessions revoked successfully.',
        type: 'info',
      });
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to revoke sessions.',
        type: 'error',
      });
    } finally {
      setIsRevokingSession(false);
    }
  }, [api]);

  // ============================================
  // Handlers - Integrations
  // ============================================

  const handleCreateIntegration = useCallback(async () => {
    if (!newIntegration.name || !newIntegration.type) {
      setShowToast({
        message: 'Please fill in all required fields.',
        type: 'warning',
      });
      return;
    }

    setIsCreatingIntegration(true);
    try {
      const response = await api.post('/settings/integrations', newIntegration);
      if (response.data) {
        setIntegrations(prev => [response.data, ...prev]);
        setShowIntegrationModal(false);
        setNewIntegration({
          type: 'webhook',
          name: '',
          config: {},
          enabled: true,
        });
        setShowToast({
          message: 'Integration created successfully!',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to create integration.',
        type: 'error',
      });
    } finally {
      setIsCreatingIntegration(false);
    }
  }, [api, newIntegration]);

  const handleDeleteIntegration = useCallback(async (id: string) => {
    if (!confirm('Are you sure you want to delete this integration?')) return;

    setIsDeletingIntegration(true);
    try {
      await api.delete(`/settings/integrations/${id}`);
      setIntegrations(prev => prev.filter(i => i.id !== id));
      setShowToast({
        message: 'Integration deleted successfully.',
        type: 'info',
      });
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to delete integration.',
        type: 'error',
      });
    } finally {
      setIsDeletingIntegration(false);
    }
  }, [api]);

  // ============================================
  // Handlers - Privacy
  // ============================================

  const handlePrivacyUpdate = useCallback(async () => {
    setIsUpdatingPrivacy(true);
    try {
      const response = await api.put('/settings/privacy', privacy);
      if (response.data) {
        setPrivacy(response.data);
        setShowToast({
          message: 'Privacy settings updated!',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.response?.data?.message || 'Failed to update privacy settings.',
        type: 'error',
      });
    } finally {
      setIsUpdatingPrivacy(false);
    }
  }, [api, privacy]);

  // ============================================
  // Memoized Computations
  // ============================================

  const filteredAuditLogs = useMemo(() => {
    if (auditLogFilter === 'all') return auditLogs;
    return auditLogs.filter(log => log.type === auditLogFilter);
  }, [auditLogs, auditLogFilter]);

  const uniqueAuditLogTypes = useMemo(() => {
    const types = new Set(auditLogs.map(log => log.type));
    return ['all', ...Array.from(types)];
  }, [auditLogs]);

  const activeSessions = useMemo(() => {
    return sessions.filter(s => s.isActive);
  }, [sessions]);

  // ============================================
  // Render
  // ============================================

  if (isLoading && profileLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-6">
            <div className="absolute inset-0 border-4 border-cyan-500/30 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-t-cyan-500 rounded-full animate-spin"></div>
            <div className="absolute inset-2 bg-cyan-500/10 rounded-full animate-pulse"></div>
          </div>
          <p className="text-gray-400 text-lg font-medium">Loading Settings...</p>
          <p className="text-gray-500 text-sm mt-2">Fetching your preferences</p>
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
            <div className="text-3xl">⚙️</div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-cyan-400 to-blue-400 bg-clip-text text-transparent">
                Settings
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                Manage your account, security, and preferences
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-3 flex-wrap">
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
      {/* MAIN TABS */}
      {/* ============================================ */}
      <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
        <TabsList className="bg-gray-800 border border-gray-700 rounded-lg p-1 w-full overflow-x-auto">
          <TabsTrigger
            value="profile"
            className="data-[state=active]:bg-cyan-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            👤 Profile
          </TabsTrigger>
          <TabsTrigger
            value="security"
            className="data-[state=active]:bg-red-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            🔒 Security
          </TabsTrigger>
          <TabsTrigger
            value="notifications"
            className="data-[state=active]:bg-yellow-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            🔔 Notifications
          </TabsTrigger>
          <TabsTrigger
            value="trading"
            className="data-[state=active]:bg-green-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📈 Trading
          </TabsTrigger>
          <TabsTrigger
            value="api"
            className="data-[state=active]:bg-purple-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            🔑 API Keys
          </TabsTrigger>
          <TabsTrigger
            value="integrations"
            className="data-[state=active]:bg-blue-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            🔗 Integrations
          </TabsTrigger>
          <TabsTrigger
            value="privacy"
            className="data-[state=active]:bg-pink-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            🛡️ Privacy
          </TabsTrigger>
          <TabsTrigger
            value="sessions"
            className="data-[state=active]:bg-orange-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📱 Sessions
          </TabsTrigger>
          <TabsTrigger
            value="audit"
            className="data-[state=active]:bg-gray-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
          >
            📋 Audit Log
          </TabsTrigger>
        </TabsList>

        {/* ========================================== */}
        {/* PROFILE TAB */}
        {/* ========================================== */}
        <TabsContent value="profile" className="mt-4 space-y-6">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 lg:col-span-4">
              <Card className="p-6 bg-gray-800 border-gray-700 text-center">
                <div className="relative inline-block">
                  <Avatar
                    size="xl"
                    src={profile.avatar}
                    alt={profile.name}
                    className="mx-auto mb-4"
                  />
                  <button
                    className="absolute bottom-2 right-2 p-1.5 bg-cyan-500 rounded-full hover:bg-cyan-600 transition-colors"
                    onClick={() => document.getElementById('avatar-upload')?.click()}
                  >
                    <Camera className="w-4 h-4 text-white" />
                  </button>
                  <input
                    id="avatar-upload"
                    type="file"
                    accept="image/*"
                    className="hidden"
                    onChange={async (e) => {
                      const file = e.target.files?.[0];
                      if (file) {
                        // Handle avatar upload
                      }
                    }}
                  />
                </div>
                <h2 className="text-xl font-bold text-white">{profile.name}</h2>
                <p className="text-sm text-gray-400">{profile.email}</p>
                <p className="text-sm text-gray-500 mt-1">Member since {formatDate(profile.createdAt)}</p>
              </Card>
            </div>

            <div className="col-span-12 lg:col-span-8">
              <Card className="p-6 bg-gray-800 border-gray-700">
                <h3 className="text-lg font-semibold text-white mb-4">Profile Information</h3>
                {profileLoading ? (
                  <div className="text-center py-4">
                    <Spinner size="sm" className="mx-auto text-cyan-500" />
                  </div>
                ) : (
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">Display Name</label>
                      <Input
                        value={profile.name}
                        onChange={(e) => setProfile({ ...profile, name: e.target.value })}
                        className="w-full bg-gray-700 border-gray-600 text-white"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">Email</label>
                      <div className="flex items-center gap-2">
                        <Mail className="w-4 h-4 text-gray-500" />
                        <span className="text-white">{profile.email}</span>
                        {security.emailVerified && (
                          <CheckCircle className="w-4 h-4 text-green-500" />
                        )}
                      </div>
                    </div>
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">Phone</label>
                      <Input
                        value={profile.phone || ''}
                        onChange={(e) => setProfile({ ...profile, phone: e.target.value })}
                        className="w-full bg-gray-700 border-gray-600 text-white"
                        placeholder="+1 234 567 8900"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">Bio</label>
                      <Textarea
                        value={profile.bio || ''}
                        onChange={(e) => setProfile({ ...profile, bio: e.target.value })}
                        className="w-full bg-gray-700 border-gray-600 text-white resize-none"
                        rows={3}
                        placeholder="Tell us about yourself..."
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">Location</label>
                      <Input
                        value={profile.location || ''}
                        onChange={(e) => setProfile({ ...profile, location: e.target.value })}
                        className="w-full bg-gray-700 border-gray-600 text-white"
                        placeholder="City, Country"
                      />
                    </div>
                    <div>
                      <label className="block text-sm text-gray-400 mb-1">Website</label>
                      <Input
                        value={profile.website || ''}
                        onChange={(e) => setProfile({ ...profile, website: e.target.value })}
                        className="w-full bg-gray-700 border-gray-600 text-white"
                        placeholder="https://your-website.com"
                      />
                    </div>
                    <Button
                      onClick={handleProfileUpdate}
                      isLoading={isUpdatingProfile}
                      className="w-full bg-gradient-to-r from-cyan-500 to-blue-500"
                    >
                      <Save className="w-4 h-4 mr-2" />
                      Save Changes
                    </Button>
                  </div>
                )}
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* SECURITY TAB */}
        {/* ========================================== */}
        <TabsContent value="security" className="mt-4 space-y-6">
          <div className="grid grid-cols-12 gap-6">
            <div className="col-span-12 lg:col-span-6">
              <Card className="p-6 bg-gray-800 border-gray-700">
                <h3 className="text-lg font-semibold text-white mb-4">Password</h3>
                <p className="text-sm text-gray-400 mb-4">
                  Last changed: {formatDate(security.lastPasswordChange)}
                </p>
                <Button
                  onClick={() => setShowPasswordModal(true)}
                  className="bg-gradient-to-r from-red-500 to-orange-500"
                >
                  <Key className="w-4 h-4 mr-2" />
                  Change Password
                </Button>
              </Card>
            </div>

            <div className="col-span-12 lg:col-span-6">
              <Card className="p-6 bg-gray-800 border-gray-700">
                <h3 className="text-lg font-semibold text-white mb-4">Two-Factor Authentication</h3>
                <div className="flex items-center justify-between mb-4">
                  <div>
                    <p className="text-sm text-white">
                      {security.twoFactorEnabled ? '🔒 2FA is enabled' : '🔓 2FA is disabled'}
                    </p>
                    <p className="text-xs text-gray-400">
                      {security.twoFactorEnabled
                        ? 'Your account is protected with 2FA'
                        : 'Add an extra layer of security to your account'}
                    </p>
                  </div>
                  <Switch
                    checked={security.twoFactorEnabled}
                    onCheckedChange={(checked) => {
                      if (checked) {
                        handleEnable2FA();
                      } else {
                        handleDisable2FA();
                      }
                    }}
                    className="data-[state=checked]:bg-cyan-500"
                    disabled={isEnabling2FA || isDisabling2FA}
                  />
                </div>
                {security.twoFactorEnabled && security.backupCodes.length > 0 && (
                  <div className="mt-4 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                    <p className="text-sm text-yellow-500 font-medium">Save Your Backup Codes</p>
                    <p className="text-xs text-gray-400 mt-1">
                      Keep these codes in a safe place. You'll need them if you lose access to your 2FA device.
                    </p>
                    <div className="mt-2 grid grid-cols-2 gap-1">
                      {security.backupCodes.map((code, index) => (
                        <code key={index} className="text-xs font-mono text-gray-300 bg-gray-700 p-1 rounded">
                          {code}
                        </code>
                      ))}
                    </div>
                  </div>
                )}
              </Card>
            </div>

            <div className="col-span-12">
              <Card className="p-6 bg-gray-800 border-gray-700">
                <h3 className="text-lg font-semibold text-white mb-4">Account Security</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
                    <div className="flex items-center gap-3">
                      <MailCheck className="w-5 h-5 text-green-500" />
                      <div>
                        <p className="text-sm text-white">Email Verification</p>
                        <p className="text-xs text-gray-400">
                          {security.emailVerified ? 'Verified' : 'Not verified'}
                        </p>
                      </div>
                    </div>
                    {!security.emailVerified && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="border-cyan-500/50 text-cyan-400 hover:bg-cyan-500/10"
                      >
                        Verify
                      </Button>
                    )}
                  </div>
                  <div className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
                    <div className="flex items-center gap-3">
                      <PhoneCheck className="w-5 h-5 text-blue-500" />
                      <div>
                        <p className="text-sm text-white">Phone Verification</p>
                        <p className="text-xs text-gray-400">
                          {security.phoneVerified ? 'Verified' : 'Not verified'}
                        </p>
                      </div>
                    </div>
                    {!security.phoneVerified && (
                      <Button
                        variant="outline"
                        size="sm"
                        className="border-cyan-500/50 text-cyan-400 hover:bg-cyan-500/10"
                      >
                        Verify
                      </Button>
                    )}
                  </div>
                </div>
              </Card>
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* NOTIFICATIONS TAB */}
        {/* ========================================== */}
        <TabsContent value="notifications" className="mt-4 space-y-6">
          <Card className="p-6 bg-gray-800 border-gray-700">
            <h3 className="text-lg font-semibold text-white mb-4">Notification Preferences</h3>
            {notificationsLoading ? (
              <div className="text-center py-4">
                <Spinner size="sm" className="mx-auto text-cyan-500" />
              </div>
            ) : (
              <div className="space-y-6">
                {/* Email Notifications */}
                <div>
                  <h4 className="text-sm font-medium text-gray-300 mb-3">Email Notifications</h4>
                  <div className="space-y-2">
                    {Object.entries(notifications.email || {}).map(([key, value]) => (
                      <div key={key} className="flex items-center justify-between p-2 bg-gray-700/30 rounded-lg">
                        <span className="text-sm text-gray-300 capitalize">{key.replace(/([A-Z])/g, ' $1').trim()}</span>
                        <Switch
                          checked={value}
                          onCheckedChange={(checked) => {
                            setNotifications(prev => ({
                              ...prev,
                              email: { ...prev.email, [key]: checked },
                            }));
                          }}
                          className="data-[state=checked]:bg-cyan-500"
                        />
                      </div>
                    ))}
                  </div>
                </div>

                {/* Push Notifications */}
                <div>
                  <h4 className="text-sm font-medium text-gray-300 mb-3">Push Notifications</h4>
                  <div className="space-y-2">
                    {Object.entries(notifications.push || {}).map(([key, value]) => (
                      <div key={key} className="flex items-center justify-between p-2 bg-gray-700/30 rounded-lg">
                        <span className="text-sm text-gray-300 capitalize">{key.replace(/([A-Z])/g, ' $1').trim()}</span>
                        <Switch
                          checked={value}
                          onCheckedChange={(checked) => {
                            setNotifications(prev => ({
                              ...prev,
                              push: { ...prev.push, [key]: checked },
                            }));
                          }}
                          className="data-[state=checked]:bg-cyan-500"
                        />
                      </div>
                    ))}
                  </div>
                </div>

                {/* In-App Notifications */}
                <div>
                  <h4 className="text-sm font-medium text-gray-300 mb-3">In-App Notifications</h4>
                  <div className="space-y-2">
                    {Object.entries(notifications.inApp || {}).map(([key, value]) => (
                      <div key={key} className="flex items-center justify-between p-2 bg-gray-700/30 rounded-lg">
                        <span className="text-sm text-gray-300 capitalize">{key.replace(/([A-Z])/g, ' $1').trim()}</span>
                        <Switch
                          checked={value}
                          onCheckedChange={(checked) => {
                            setNotifications(prev => ({
                              ...prev,
                              inApp: { ...prev.inApp, [key]: checked },
                            }));
                          }}
                          className="data-[state=checked]:bg-cyan-500"
                        />
                      </div>
                    ))}
                  </div>
                </div>

                <Button
                  onClick={handleNotificationsUpdate}
                  isLoading={isUpdatingNotifications}
                  className="w-full bg-gradient-to-r from-yellow-500 to-orange-500"
                >
                  <Save className="w-4 h-4 mr-2" />
                  Save Notification Settings
                </Button>
              </div>
            )}
          </Card>
        </TabsContent>

        {/* ========================================== */}
        {/* TRADING TAB */}
        {/* ========================================== */}
        <TabsContent value="trading" className="mt-4 space-y-6">
          <Card className="p-6 bg-gray-800 border-gray-700">
            <h3 className="text-lg font-semibold text-white mb-4">Trading Preferences</h3>
            {tradingPrefsLoading ? (
              <div className="text-center py-4">
                <Spinner size="sm" className="mx-auto text-cyan-500" />
              </div>
            ) : (
              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Default Pair</label>
                    <Select
                      value={tradingPrefs.defaultPair}
                      onValueChange={(value) => setTradingPrefs({ ...tradingPrefs, defaultPair: value })}
                      className="w-full bg-gray-700 border-gray-600"
                    >
                      <option value="BTC-USD">BTC-USD</option>
                      <option value="ETH-USD">ETH-USD</option>
                      <option value="SOL-USD">SOL-USD</option>
                      <option value="ADA-USD">ADA-USD</option>
                      <option value="EUR-USD">EUR-USD</option>
                    </Select>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Default Timeframe</label>
                    <Select
                      value={tradingPrefs.defaultTimeframe}
                      onValueChange={(value) => setTradingPrefs({ ...tradingPrefs, defaultTimeframe: value })}
                      className="w-full bg-gray-700 border-gray-600"
                    >
                      {TIMEFRAMES.map((tf) => (
                        <option key={tf} value={tf}>{tf}</option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Chart Type</label>
                    <Select
                      value={tradingPrefs.chartType}
                      onValueChange={(value) => setTradingPrefs({ ...tradingPrefs, chartType: value })}
                      className="w-full bg-gray-700 border-gray-600"
                    >
                      {CHART_TYPES.map((type) => (
                        <option key={type} value={type}>{type.charAt(0).toUpperCase() + type.slice(1)}</option>
                      ))}
                    </Select>
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Default Order Type</label>
                    <Select
                      value={tradingPrefs.defaultOrderType}
                      onValueChange={(value) => setTradingPrefs({ ...tradingPrefs, defaultOrderType: value })}
                      className="w-full bg-gray-700 border-gray-600"
                    >
                      <option value="market">Market</option>
                      <option value="limit">Limit</option>
                      <option value="stop">Stop</option>
                      <option value="stop_limit">Stop-Limit</option>
                    </Select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm text-gray-400 mb-1">Default Order Size</label>
                  <Input
                    type="number"
                    step="0.0001"
                    value={tradingPrefs.defaultOrderSize}
                    onChange={(e) => setTradingPrefs({ ...tradingPrefs, defaultOrderSize: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-gray-700 border-gray-600 text-white"
                  />
                </div>

                <div>
                  <label className="block text-sm text-gray-400 mb-1">Max Position Size</label>
                  <Input
                    type="number"
                    step="100"
                    value={tradingPrefs.maxPositionSize}
                    onChange={(e) => setTradingPrefs({ ...tradingPrefs, maxPositionSize: parseFloat(e.target.value) || 0 })}
                    className="w-full bg-gray-700 border-gray-600 text-white"
                  />
                </div>

                <div>
                  <label className="block text-sm text-gray-400 mb-1">Risk Per Trade (%)</label>
                  <div className="flex items-center gap-4">
                    <Slider
                      value={[tradingPrefs.riskPerTrade * 100]}
                      onValueChange={(value) => setTradingPrefs({ ...tradingPrefs, riskPerTrade: value[0] / 100 })}
                      max={10}
                      step={0.5}
                      className="flex-1"
                    />
                    <span className="text-sm text-cyan-400 w-16 text-right">
                      {(tradingPrefs.riskPerTrade * 100).toFixed(1)}%
                    </span>
                  </div>
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Stop Loss Default (%)</label>
                    <Input
                      type="number"
                      step="0.5"
                      value={tradingPrefs.stopLossDefault * 100}
                      onChange={(e) => setTradingPrefs({ ...tradingPrefs, stopLossDefault: parseFloat(e.target.value) / 100 || 0 })}
                      className="w-full bg-gray-700 border-gray-600 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Take Profit Default (%)</label>
                    <Input
                      type="number"
                      step="0.5"
                      value={tradingPrefs.takeProfitDefault * 100}
                      onChange={(e) => setTradingPrefs({ ...tradingPrefs, takeProfitDefault: parseFloat(e.target.value) / 100 || 0 })}
                      className="w-full bg-gray-700 border-gray-600 text-white"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm text-gray-400 mb-1">Slippage Tolerance (%)</label>
                  <Input
                    type="number"
                    step="0.1"
                    value={tradingPrefs.slippageTolerance * 100}
                    onChange={(e) => setTradingPrefs({ ...tradingPrefs, slippageTolerance: parseFloat(e.target.value) / 100 || 0 })}
                    className="w-full bg-gray-700 border-gray-600 text-white"
                  />
                </div>

                <div>
                  <label className="block text-sm text-gray-400 mb-1">Leverage</label>
                  <Select
                    value={String(tradingPrefs.leverage)}
                    onValueChange={(value) => setTradingPrefs({ ...tradingPrefs, leverage: parseInt(value) || 1 })}
                    className="w-full bg-gray-700 border-gray-600"
                  >
                    <option value="1">1x</option>
                    <option value="2">2x</option>
                    <option value="3">3x</option>
                    <option value="5">5x</option>
                    <option value="10">10x</option>
                    <option value="20">20x</option>
                    <option value="50">50x</option>
                    <option value="100">100x</option>
                  </Select>
                </div>

                <div className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
                  <div>
                    <p className="text-sm text-white">Auto Trading</p>
                    <p className="text-xs text-gray-400">Automatically execute trades based on AI signals</p>
                  </div>
                  <Switch
                    checked={tradingPrefs.autoTradingEnabled}
                    onCheckedChange={(checked) => setTradingPrefs({ ...tradingPrefs, autoTradingEnabled: checked })}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                </div>

                <div className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
                  <div>
                    <p className="text-sm text-white">Paper Trading</p>
                    <p className="text-xs text-gray-400">Practice trading with virtual funds</p>
                  </div>
                  <Switch
                    checked={tradingPrefs.paperTradingEnabled}
                    onCheckedChange={(checked) => setTradingPrefs({ ...tradingPrefs, paperTradingEnabled: checked })}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                </div>

                <Button
                  onClick={handleTradingPrefsUpdate}
                  isLoading={isUpdatingTradingPrefs}
                  className="w-full bg-gradient-to-r from-green-500 to-emerald-500"
                >
                  <Save className="w-4 h-4 mr-2" />
                  Save Trading Preferences
                </Button>
              </div>
            )}
          </Card>
        </TabsContent>

        {/* ========================================== */}
        {/* API KEYS TAB */}
        {/* ========================================== */}
        <TabsContent value="api" className="mt-4 space-y-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">API Keys</h3>
            <Button
              onClick={() => setShowApiKeyModal(true)}
              className="bg-gradient-to-r from-purple-500 to-pink-500"
            >
              <Plus className="w-4 h-4 mr-2" />
              Create API Key
            </Button>
          </div>

          {apiKeysLoading ? (
            <div className="text-center py-8">
              <Spinner size="lg" className="mx-auto text-cyan-500" />
              <p className="text-gray-400 mt-4">Loading API keys...</p>
            </div>
          ) : apiKeys.length > 0 ? (
            <div className="space-y-3">
              {apiKeys.map((key) => (
                <Card key={key.id} className="p-4 bg-gray-800 border-gray-700">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-white font-medium">{key.name}</span>
                        <Badge className={cn(
                          "text-xs",
                          key.isActive ? 'bg-green-500/20 text-green-500' : 'bg-red-500/20 text-red-500'
                        )}>
                          {key.isActive ? 'Active' : 'Inactive'}
                        </Badge>
                      </div>
                      <div className="text-sm text-gray-400 mt-1">
                        Created: {formatDate(key.createdAt)}
                        {key.lastUsed && ` • Last used: ${formatDate(key.lastUsed)}`}
                      </div>
                      <div className="flex flex-wrap gap-1 mt-2">
                        {key.scopes.map((scope) => (
                          <Badge key={scope} className="bg-gray-600 text-xs">
                            {scope}
                          </Badge>
                        ))}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {key.isActive && (
                        <Button
                          variant="ghost"
                          size="sm"
                          className="text-cyan-400 hover:text-cyan-300"
                        >
                          <RefreshCw className="w-4 h-4" />
                        </Button>
                      )}
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteApiKey(key.id)}
                        className="text-red-400 hover:text-red-300"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <Api className="w-16 h-16 mx-auto mb-4 text-gray-600" />
              <p className="text-lg font-medium">No API keys created</p>
              <p className="text-sm">Create an API key to access the NEXUS API programmatically</p>
            </div>
          )}
        </TabsContent>

        {/* ========================================== */}
        {/* INTEGRATIONS TAB */}
        {/* ========================================== */}
        <TabsContent value="integrations" className="mt-4 space-y-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-white">Integrations</h3>
            <Button
              onClick={() => setShowIntegrationModal(true)}
              className="bg-gradient-to-r from-blue-500 to-indigo-500"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Integration
            </Button>
          </div>

          {integrationsLoading ? (
            <div className="text-center py-8">
              <Spinner size="lg" className="mx-auto text-cyan-500" />
              <p className="text-gray-400 mt-4">Loading integrations...</p>
            </div>
          ) : integrations.length > 0 ? (
            <div className="space-y-3">
              {integrations.map((integration) => (
                <Card key={integration.id} className="p-4 bg-gray-800 border-gray-700">
                  <div className="flex items-center justify-between">
                    <div>
                      <div className="flex items-center gap-2">
                        {integration.type === 'webhook' && <Webhook className="w-5 h-5 text-cyan-500" />}
                        {integration.type === 'slack' && <MessageSquare className="w-5 h-5 text-purple-500" />}
                        {integration.type === 'telegram' && <Send className="w-5 h-5 text-blue-500" />}
                        {integration.type === 'discord' && <MessageSquare className="w-5 h-5 text-indigo-500" />}
                        <span className="text-white font-medium">{integration.name}</span>
                        <Badge className={cn(
                          "text-xs",
                          integration.enabled ? 'bg-green-500/20 text-green-500' : 'bg-gray-500/20 text-gray-400'
                        )}>
                          {integration.enabled ? 'Enabled' : 'Disabled'}
                        </Badge>
                      </div>
                      <div className="text-sm text-gray-400 mt-1">
                        Type: {integration.type.toUpperCase()} • Created: {formatDate(integration.createdAt)}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Switch
                        checked={integration.enabled}
                        onCheckedChange={(checked) => {
                          // Update integration status
                        }}
                        className="data-[state=checked]:bg-cyan-500"
                      />
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDeleteIntegration(integration.id)}
                        className="text-red-400 hover:text-red-300"
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          ) : (
            <div className="text-center py-12 text-gray-500">
              <Link className="w-16 h-16 mx-auto mb-4 text-gray-600" />
              <p className="text-lg font-medium">No integrations</p>
              <p className="text-sm">Connect external services to your NEXUS account</p>
            </div>
          )}
        </TabsContent>

        {/* ========================================== */}
        {/* PRIVACY TAB */}
        {/* ========================================== */}
        <TabsContent value="privacy" className="mt-4 space-y-6">
          <Card className="p-6 bg-gray-800 border-gray-700">
            <h3 className="text-lg font-semibold text-white mb-4">Privacy Settings</h3>
            {privacyLoading ? (
              <div className="text-center py-4">
                <Spinner size="sm" className="mx-auto text-cyan-500" />
              </div>
            ) : (
              <div className="space-y-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">Profile Visibility</label>
                  <Select
                    value={privacy.profileVisibility}
                    onValueChange={(value) => setPrivacy({ ...privacy, profileVisibility: value })}
                    className="w-full bg-gray-700 border-gray-600"
                  >
                    <option value="public">Public</option>
                    <option value="private">Private</option>
                    <option value="contacts">Contacts Only</option>
                  </Select>
                </div>

                <div>
                  <label className="block text-sm text-gray-400 mb-1">Trading History Visibility</label>
                  <Select
                    value={privacy.showTradingHistory}
                    onValueChange={(value) => setPrivacy({ ...privacy, showTradingHistory: value })}
                    className="w-full bg-gray-700 border-gray-600"
                  >
                    <option value="public">Public</option>
                    <option value="private">Private</option>
                    <option value="contacts">Contacts Only</option>
                  </Select>
                </div>

                <div className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
                  <div>
                    <p className="text-sm text-white">Show Email</p>
                    <p className="text-xs text-gray-400">Display your email on your profile</p>
                  </div>
                  <Switch
                    checked={privacy.showEmail}
                    onCheckedChange={(checked) => setPrivacy({ ...privacy, showEmail: checked })}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                </div>

                <div className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
                  <div>
                    <p className="text-sm text-white">Show Phone</p>
                    <p className="text-xs text-gray-400">Display your phone number on your profile</p>
                  </div>
                  <Switch
                    checked={privacy.showPhone}
                    onCheckedChange={(checked) => setPrivacy({ ...privacy, showPhone: checked })}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                </div>

                <div className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
                  <div>
                    <p className="text-sm text-white">Show Balance</p>
                    <p className="text-xs text-gray-400">Display your account balance</p>
                  </div>
                  <Switch
                    checked={privacy.showBalance}
                    onCheckedChange={(checked) => setPrivacy({ ...privacy, showBalance: checked })}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                </div>

                <div className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
                  <div>
                    <p className="text-sm text-white">Data Sharing</p>
                    <p className="text-xs text-gray-400">Allow anonymous data sharing for research</p>
                  </div>
                  <Switch
                    checked={privacy.dataSharing}
                    onCheckedChange={(checked) => setPrivacy({ ...privacy, dataSharing: checked })}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                </div>

                <div className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
                  <div>
                    <p className="text-sm text-white">Analytics</p>
                    <p className="text-xs text-gray-400">Enable usage analytics</p>
                  </div>
                  <Switch
                    checked={privacy.analyticsEnabled}
                    onCheckedChange={(checked) => setPrivacy({ ...privacy, analyticsEnabled: checked })}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                </div>

                <div className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
                  <div>
                    <p className="text-sm text-white">Marketing Emails</p>
                    <p className="text-xs text-gray-400">Receive marketing and promotional emails</p>
                  </div>
                  <Switch
                    checked={privacy.marketingEmails}
                    onCheckedChange={(checked) => setPrivacy({ ...privacy, marketingEmails: checked })}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                </div>

                <Button
                  onClick={handlePrivacyUpdate}
                  isLoading={isUpdatingPrivacy}
                  className="w-full bg-gradient-to-r from-pink-500 to-rose-500"
                >
                  <Save className="w-4 h-4 mr-2" />
                  Save Privacy Settings
                </Button>
              </div>
            )}
          </Card>
        </TabsContent>

        {/* ========================================== */}
        {/* SESSIONS TAB */}
        {/* ========================================== */}
        <TabsContent value="sessions" className="mt-4 space-y-6">
          <Card className="p-6 bg-gray-800 border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">Active Sessions</h3>
              {sessions.filter(s => !s.isCurrent).length > 0 && (
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleRevokeAllSessions}
                  isLoading={isRevokingSession}
                  className="bg-red-600 hover:bg-red-700"
                >
                  Revoke All
                </Button>
              )}
            </div>

            {sessionsLoading ? (
              <div className="text-center py-8">
                <Spinner size="lg" className="mx-auto text-cyan-500" />
                <p className="text-gray-400 mt-4">Loading sessions...</p>
              </div>
            ) : sessions.length > 0 ? (
              <div className="space-y-3">
                {sessions.map((session) => (
                  <div key={session.id} className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
                    <div className="flex items-center gap-3">
                      {session.deviceType === 'mobile' && <Smartphone className="w-5 h-5 text-cyan-500" />}
                      {session.deviceType === 'tablet' && <Tablet className="w-5 h-5 text-blue-500" />}
                      {session.deviceType === 'desktop' && <Monitor className="w-5 h-5 text-purple-500" />}
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-white font-medium">{session.deviceName || 'Unknown Device'}</span>
                          {session.isCurrent && (
                            <Badge className="bg-green-500/20 text-green-500 text-xs">Current</Badge>
                          )}
                          {session.isActive ? (
                            <Badge className="bg-green-500/20 text-green-500 text-xs">Active</Badge>
                          ) : (
                            <Badge className="bg-gray-500/20 text-gray-400 text-xs">Inactive</Badge>
                          )}
                        </div>
                        <div className="text-sm text-gray-400">
                          {session.browser} • {session.os} • Last active: {formatTime(session.lastActive)}
                        </div>
                        <div className="text-xs text-gray-500">
                          IP: {session.ip} • {session.location?.city}, {session.location?.country}
                        </div>
                      </div>
                    </div>
                    {!session.isCurrent && (
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleRevokeSession(session.id)}
                        className="text-red-400 hover:text-red-300"
                      >
                        <X className="w-4 h-4" />
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-gray-500">
                <Monitor className="w-16 h-16 mx-auto mb-4 text-gray-600" />
                <p className="text-lg font-medium">No active sessions</p>
                <p className="text-sm">Your sessions will appear here</p>
              </div>
            )}
          </Card>

          {/* Connected Devices */}
          <Card className="p-6 bg-gray-800 border-gray-700">
            <h3 className="text-lg font-semibold text-white mb-4">Connected Devices</h3>
            {devices.length > 0 ? (
              <div className="space-y-3">
                {devices.map((device) => (
                  <div key={device.id} className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
                    <div className="flex items-center gap-3">
                      {device.type === 'mobile' && <Smartphone className="w-5 h-5 text-cyan-500" />}
                      {device.type === 'tablet' && <Tablet className="w-5 h-5 text-blue-500" />}
                      {device.type === 'desktop' && <Monitor className="w-5 h-5 text-purple-500" />}
                      <div>
                        <div className="text-white font-medium">{device.name}</div>
                        <div className="text-sm text-gray-400">
                          {device.browser} • {device.os} • Added: {formatDate(device.addedAt)}
                        </div>
                        <div className="text-xs text-gray-500">
                          Last used: {formatTime(device.lastUsed)}
                        </div>
                      </div>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      className="text-red-400 hover:text-red-300"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <Smartphone className="w-16 h-16 mx-auto mb-4 text-gray-600" />
                <p className="text-lg font-medium">No connected devices</p>
                <p className="text-sm">Your devices will appear here</p>
              </div>
            )}
          </Card>
        </TabsContent>

        {/* ========================================== */}
        {/* AUDIT LOG TAB */}
        {/* ========================================== */}
        <TabsContent value="audit" className="mt-4 space-y-6">
          <Card className="p-6 bg-gray-800 border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold text-white">Audit Log</h3>
              <div className="flex items-center gap-2">
                <Select
                  value={auditLogFilter}
                  onValueChange={setAuditLogFilter}
                  className="w-32 bg-gray-700 border-gray-600 text-sm"
                >
                  {uniqueAuditLogTypes.map((type) => (
                    <option key={type} value={type}>
                      {type === 'all' ? 'All Types' : type}
                    </option>
                  ))}
                </Select>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => fetchAuditLogs()}
                  className="text-cyan-400 hover:text-cyan-300"
                >
                  <RefreshCw className="w-4 h-4" />
                </Button>
              </div>
            </div>

            {auditLogsLoading ? (
              <div className="text-center py-8">
                <Spinner size="lg" className="mx-auto text-cyan-500" />
                <p className="text-gray-400 mt-4">Loading audit logs...</p>
              </div>
            ) : filteredAuditLogs.length > 0 ? (
              <div className="space-y-2 max-h-96 overflow-y-auto">
                {filteredAuditLogs.map((log) => (
                  <div key={log.id} className="flex items-center justify-between p-2 bg-gray-700/20 rounded-lg hover:bg-gray-700/40 transition-colors">
                    <div className="flex items-center gap-3">
                      <div className={cn(
                        "w-2 h-2 rounded-full",
                        log.type === 'login' ? 'bg-green-500' :
                        log.type === 'logout' ? 'bg-blue-500' :
                        log.type === 'trade' ? 'bg-purple-500' :
                        log.type === 'security' ? 'bg-red-500' :
                        log.type === 'settings' ? 'bg-yellow-500' :
                        'bg-gray-500'
                      )} />
                      <div>
                        <div className="text-sm text-white">{log.message}</div>
                        <div className="text-xs text-gray-500">
                          {formatTime(log.timestamp)} • {log.ip} • {log.userAgent}
                        </div>
                      </div>
                    </div>
                    <Badge className="bg-gray-600 text-xs">{log.type}</Badge>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-12 text-gray-500">
                <Database className="w-16 h-16 mx-auto mb-4 text-gray-600" />
                <p className="text-lg font-medium">No audit logs</p>
                <p className="text-sm">Your activity will be logged here for security</p>
              </div>
            )}
          </Card>

          {/* Data Export */}
          <Card className="p-6 bg-gray-800 border-gray-700">
            <h3 className="text-lg font-semibold text-white mb-4">Data Export</h3>
            <p className="text-sm text-gray-400 mb-4">
              Download all your data including transactions, trades, and account information.
            </p>
            <div className="flex gap-3">
              <Button
                variant="outline"
                className="border-gray-600 hover:border-cyan-500"
              >
                <Download className="w-4 h-4 mr-2" />
                Export as CSV
              </Button>
              <Button
                variant="outline"
                className="border-gray-600 hover:border-cyan-500"
              >
                <Download className="w-4 h-4 mr-2" />
                Export as JSON
              </Button>
            </div>
          </Card>
        </TabsContent>
      </Tabs>

      {/* ============================================ */}
      {/* PASSWORD CHANGE MODAL */}
      {/* ============================================ */}
      <Modal
        open={showPasswordModal}
        onOpenChange={setShowPasswordModal}
        title="Change Password"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Current Password</label>
            <div className="relative">
              <Input
                type={showCurrentPassword ? 'text' : 'password'}
                value={passwordData.currentPassword}
                onChange={(e) => setPasswordData({ ...passwordData, currentPassword: e.target.value })}
                className="w-full bg-gray-700 border-gray-600 text-white pr-10"
                placeholder="Enter current password"
              />
              <button
                type="button"
                onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
              >
                {showCurrentPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">New Password</label>
            <div className="relative">
              <Input
                type={showNewPassword ? 'text' : 'password'}
                value={passwordData.newPassword}
                onChange={(e) => setPasswordData({ ...passwordData, newPassword: e.target.value })}
                className="w-full bg-gray-700 border-gray-600 text-white pr-10"
                placeholder="Enter new password"
              />
              <button
                type="button"
                onClick={() => setShowNewPassword(!showNewPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
              >
                {showNewPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            <p className="text-xs text-gray-500 mt-1">Must be at least 8 characters</p>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Confirm New Password</label>
            <div className="relative">
              <Input
                type={showConfirmPassword ? 'text' : 'password'}
                value={passwordData.confirmPassword}
                onChange={(e) => setPasswordData({ ...passwordData, confirmPassword: e.target.value })}
                className="w-full bg-gray-700 border-gray-600 text-white pr-10"
                placeholder="Confirm new password"
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-white"
              >
                {showConfirmPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => setShowPasswordModal(false)}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handlePasswordUpdate}
              isLoading={isUpdatingPassword}
              className="bg-gradient-to-r from-red-500 to-orange-500"
            >
              Update Password
            </Button>
          </div>
        </div>
      </Modal>

      {/* ============================================ */}
      {/* GENERATED API KEY MODAL */}
      {/* ============================================ */}
      <Modal
        open={showGeneratedKeyModal}
        onOpenChange={setShowGeneratedKeyModal}
        title="API Key Generated"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div className="bg-yellow-500/10 border border-yellow-500/30 rounded-lg p-3">
            <p className="text-sm text-yellow-500 font-medium flex items-center gap-2">
              <AlertCircle className="w-5 h-5" />
              Save this key now!
            </p>
            <p className="text-xs text-gray-400 mt-1">
              This is the only time the key will be displayed. Please copy and store it securely.
            </p>
          </div>
          <div className="bg-gray-700 rounded-lg p-4">
            <code className="text-sm text-cyan-400 font-mono break-all">
              {generatedApiKey}
            </code>
          </div>
          <div className="flex gap-3">
            <CopyButton text={generatedApiKey || ''} className="flex-1">
              <Button variant="primary" className="w-full bg-cyan-500 hover:bg-cyan-600">
                <Copy className="w-4 h-4 mr-2" />
                Copy Key
              </Button>
            </CopyButton>
            <Button
              variant="outline"
              onClick={() => {
                setShowGeneratedKeyModal(false);
                setGeneratedApiKey(null);
              }}
              className="flex-1 border-gray-600 hover:border-gray-500"
            >
              Close
            </Button>
          </div>
        </div>
      </Modal>

      {/* ============================================ */}
      {/* CREATE API KEY MODAL */}
      {/* ============================================ */}
      <Modal
        open={showApiKeyModal}
        onOpenChange={setShowApiKeyModal}
        title="Create API Key"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Name *</label>
            <Input
              value={newApiKey.name}
              onChange={(e) => setNewApiKey({ ...newApiKey, name: e.target.value })}
              placeholder="e.g., My Trading Bot"
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-2">Scopes *</label>
            <div className="space-y-2">
              {API_SCOPES.map((scope) => (
                <div key={scope} className="flex items-center gap-2">
                  <Checkbox
                    checked={newApiKey.scopes?.includes(scope)}
                    onCheckedChange={(checked) => {
                      const current = newApiKey.scopes || [];
                      const updated = checked ? [...current, scope] : current.filter(s => s !== scope);
                      setNewApiKey({ ...newApiKey, scopes: updated });
                    }}
                  />
                  <span className="text-sm text-gray-300">{scope}</span>
                </div>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Expires At (optional)</label>
            <Input
              type="datetime-local"
              value={newApiKey.expiresAt ? new Date(newApiKey.expiresAt).toISOString().slice(0, 16) : ''}
              onChange={(e) => setNewApiKey({ ...newApiKey, expiresAt: e.target.value ? new Date(e.target.value) : null })}
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => setShowApiKeyModal(false)}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateApiKey}
              isLoading={isCreatingApiKey}
              className="bg-gradient-to-r from-purple-500 to-pink-500"
            >
              Create API Key
            </Button>
          </div>
        </div>
      </Modal>

      {/* ============================================ */}
      {/* CREATE INTEGRATION MODAL */}
      {/* ============================================ */}
      <Modal
        open={showIntegrationModal}
        onOpenChange={setShowIntegrationModal}
        title="Add Integration"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Integration Type *</label>
            <Select
              value={newIntegration.type}
              onValueChange={(value) => setNewIntegration({ ...newIntegration, type: value })}
              className="w-full bg-gray-700 border-gray-600"
            >
              {INTEGRATION_TYPES.map((type) => (
                <option key={type} value={type}>{type.toUpperCase()}</option>
              ))}
            </Select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Name *</label>
            <Input
              value={newIntegration.name}
              onChange={(e) => setNewIntegration({ ...newIntegration, name: e.target.value })}
              placeholder="e.g., Trading Alerts"
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
          </div>
          {newIntegration.type === 'webhook' && (
            <div>
              <label className="block text-sm text-gray-400 mb-1">Webhook URL *</label>
              <Input
                value={newIntegration.config?.url || ''}
                onChange={(e) => setNewIntegration({
                  ...newIntegration,
                  config: { ...newIntegration.config, url: e.target.value }
                })}
                placeholder="https://example.com/webhook"
                className="w-full bg-gray-700 border-gray-600 text-white"
              />
            </div>
          )}
          {newIntegration.type === 'slack' && (
            <div>
              <label className="block text-sm text-gray-400 mb-1">Slack Webhook URL *</label>
              <Input
                value={newIntegration.config?.webhookUrl || ''}
                onChange={(e) => setNewIntegration({
                  ...newIntegration,
                  config: { ...newIntegration.config, webhookUrl: e.target.value }
                })}
                placeholder="https://hooks.slack.com/services/..."
                className="w-full bg-gray-700 border-gray-600 text-white"
              />
            </div>
          )}
          {newIntegration.type === 'telegram' && (
            <div>
              <label className="block text-sm text-gray-400 mb-1">Bot Token *</label>
              <Input
                value={newIntegration.config?.botToken || ''}
                onChange={(e) => setNewIntegration({
                  ...newIntegration,
                  config: { ...newIntegration.config, botToken: e.target.value }
                })}
                placeholder="1234567890:ABCdefGHIjklMNOpqrsTUVwxyz"
                className="w-full bg-gray-700 border-gray-600 text-white"
              />
            </div>
          )}
          <div>
            <label className="block text-sm text-gray-400 mb-1">Events</label>
            <div className="flex flex-wrap gap-2">
              {WEBHOOK_EVENTS.map((event) => (
                <button
                  key={event}
                  onClick={() => {
                    const current = newIntegration.config?.events || [];
                    const updated = current.includes(event) ? current.filter(e => e !== event) : [...current, event];
                    setNewIntegration({
                      ...newIntegration,
                      config: { ...newIntegration.config, events: updated }
                    });
                  }}
                  className={cn(
                    "px-2 py-1 rounded text-xs transition-colors",
                    (newIntegration.config?.events || []).includes(event)
                      ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                      : "bg-gray-700 text-gray-400 border border-gray-600 hover:border-gray-500"
                  )}
                >
                  {event}
                </button>
              ))}
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => setShowIntegrationModal(false)}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateIntegration}
              isLoading={isCreatingIntegration}
              className="bg-gradient-to-r from-blue-500 to-indigo-500"
            >
              Add Integration
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

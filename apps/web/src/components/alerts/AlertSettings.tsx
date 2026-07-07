/**
 * NEXUS AI TRADING SYSTEM - AlertSettings Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This component provides alert settings management including:
 * - Notification preferences
 * - Alert thresholds configuration
 * - Sound settings
 * - Email notifications
 * - Push notifications
 * - SMS notifications
 * - Alert frequency controls
 * - Priority settings
 * - Channel configuration
 * - Custom alert rules
 * - Cooldown periods
 * - Quiet hours
 * - Delivery methods
 * - Template management
 * - Webhook configuration
 * - Integration settings
 * - Accessibility options
 * - Responsive design
 */

'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Bell,
  BellOff,
  BellRing,
  Settings,
  Volume2,
  VolumeX,
  Mail,
  MailOpen,
  Smartphone,
  MessageSquare,
  Webhook,
  Sliders,
  Clock,
  Calendar,
  Moon,
  Sun,
  Check,
  X,
  AlertCircle,
  Info,
  HelpCircle,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Plus,
  Minus,
  Trash2,
  Edit,
  Save,
  RefreshCw,
  Download,
  Upload,
  Share2,
  Copy,
  ExternalLink,
  Globe,
  Zap,
  Shield,
  Lock,
  Unlock,
  Eye,
  EyeOff,
  Users,
  User,
  Mail as MailIcon,
  Phone,
  MapPin,
  Twitter,
  Linkedin,
  Github,
  Youtube,
  Instagram,
  Facebook,
  Telegram,
  Discord,
  Slack,
  MessageCircle,
  Send,
  MailOpen as MailOpenIcon,
  PhoneCall,
  Video,
  Camera,
  Image,
  File,
  Folder,
  Archive,
  Trash,
  Edit as EditIcon,
  Save as SaveIcon,
  Settings as SettingsIcon,
  Bell as BellIcon,
  BellRing as BellRingIcon,
  BellOff as BellOffIcon,
  Volume2 as Volume2Icon,
  VolumeX as VolumeXIcon,
  Smartphone as SmartphoneIcon,
  MessageSquare as MessageSquareIcon,
  Webhook as WebhookIcon,
  Sliders as SlidersIcon,
  Clock as ClockIcon,
  Calendar as CalendarIcon,
  Moon as MoonIcon,
  Sun as SunIcon,
} from 'lucide-react';

// Components
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Switch } from '@/components/ui/Switch';
import { Slider } from '@/components/ui/Slider';
import { Modal } from '@/components/ui/Modal';
import { Progress } from '@/components/ui/Progress';
import { Tooltip } from '@/components/ui/Tooltip';
import { Toast } from '@/components/ui/Toast';
import { Spinner } from '@/components/ui/Spinner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import { Textarea } from '@/components/ui/Textarea';
import { Checkbox } from '@/components/ui/Checkbox';
import { Avatar } from '@/components/ui/Avatar';

// Types
import type {
  AlertSettings as AlertSettingsType,
  AlertChannel,
  AlertPriority,
  AlertRule,
  NotificationPreference,
  QuietHours,
  AlertTemplate,
  WebhookConfig,
} from '@/types/alerts';

// Constants
import {
  ALERT_PRIORITIES,
  ALERT_CHANNELS,
  ALERT_TYPES,
  DEFAULT_ALERT_SETTINGS,
  DEFAULT_QUIET_HOURS,
  DEFAULT_TEMPLATES,
} from '@/constants/alerts';

// Utils
import { formatTime, formatDate, formatDuration } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

// ============================================
// Props Interface
// ============================================

interface AlertSettingsProps {
  settings: AlertSettingsType;
  onUpdateSettings: (settings: AlertSettingsType) => Promise<void>;
  onUpdatePreference: (channel: AlertChannel, preference: NotificationPreference) => Promise<void>;
  onUpdateRule: (rule: AlertRule) => Promise<void>;
  onDeleteRule: (ruleId: string) => Promise<void>;
  onUpdateTemplate: (template: AlertTemplate) => Promise<void>;
  onDeleteTemplate: (templateId: string) => Promise<void>;
  onUpdateWebhook: (webhook: WebhookConfig) => Promise<void>;
  onDeleteWebhook: (webhookId: string) => Promise<void>;
  isLoading?: boolean;
  className?: string;
  showAdvanced?: boolean;
  compact?: boolean;
}

// ============================================
// Main Component
// ============================================

export function AlertSettings({
  settings: initialSettings,
  onUpdateSettings,
  onUpdatePreference,
  onUpdateRule,
  onDeleteRule,
  onUpdateTemplate,
  onDeleteTemplate,
  onUpdateWebhook,
  onDeleteWebhook,
  isLoading = false,
  className,
  showAdvanced = false,
  compact = false,
}: AlertSettingsProps) {
  // State
  const [settings, setSettings] = useState<AlertSettingsType>(initialSettings);
  const [activeTab, setActiveTab] = useState<string>('general');
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [isSaving, setIsSaving] = useState<boolean>(false);
  const [isTesting, setIsTesting] = useState<boolean>(false);
  const [editTemplate, setEditTemplate] = useState<AlertTemplate | null>(null);
  const [showTemplateModal, setShowTemplateModal] = useState<boolean>(false);
  const [editWebhook, setEditWebhook] = useState<WebhookConfig | null>(null);
  const [showWebhookModal, setShowWebhookModal] = useState<boolean>(false);
  const [editRule, setEditRule] = useState<AlertRule | null>(null);
  const [showRuleModal, setShowRuleModal] = useState<boolean>(false);
  const [quietHours, setQuietHours] = useState<QuietHours>(DEFAULT_QUIET_HOURS);
  const [isTestingChannel, setIsTestingChannel] = useState<AlertChannel | null>(null);

  // Refs
  const formRef = useRef<HTMLFormElement>(null);
  const testTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // ============================================
  // Effects
  // ============================================

  useEffect(() => {
    setSettings(initialSettings);
  }, [initialSettings]);

  useEffect(() => {
    if (settings.quietHours) {
      setQuietHours(settings.quietHours);
    }
  }, [settings.quietHours]);

  // ============================================
  // Handlers - General Settings
  // ============================================

  const handleSettingsChange = useCallback(<K extends keyof AlertSettingsType>(
    key: K,
    value: AlertSettingsType[K]
  ) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSaveSettings = useCallback(async () => {
    setIsSaving(true);
    try {
      await onUpdateSettings(settings);
      setShowToast({
        message: 'Alert settings saved successfully!',
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to save alert settings.',
        type: 'error',
      });
    } finally {
      setIsSaving(false);
    }
  }, [settings, onUpdateSettings]);

  // ============================================
  // Handlers - Preferences
  // ============================================

  const handlePreferenceChange = useCallback(async (
    channel: AlertChannel,
    key: keyof NotificationPreference,
    value: any
  ) => {
    try {
      const preference = settings.preferences[channel] || {};
      const updatedPreference = { ...preference, [key]: value };
      await onUpdatePreference(channel, updatedPreference);
      setShowToast({
        message: `${channel} preference updated!`,
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || `Failed to update ${channel} preference.`,
        type: 'error',
      });
    }
  }, [settings.preferences, onUpdatePreference]);

  // ============================================
  // Handlers - Quiet Hours
  // ============================================

  const handleQuietHoursChange = useCallback((key: keyof QuietHours, value: any) => {
    setQuietHours((prev) => ({ ...prev, [key]: value }));
  }, []);

  const handleSaveQuietHours = useCallback(async () => {
    setIsSaving(true);
    try {
      await onUpdateSettings({ ...settings, quietHours });
      setShowToast({
        message: 'Quiet hours updated successfully!',
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to update quiet hours.',
        type: 'error',
      });
    } finally {
      setIsSaving(false);
    }
  }, [settings, quietHours, onUpdateSettings]);

  // ============================================
  // Handlers - Rules
  // ============================================

  const handleCreateRule = useCallback(async () => {
    const newRule: AlertRule = {
      id: `rule-${Date.now()}`,
      name: 'New Rule',
      type: 'price',
      condition: 'above',
      value: 0,
      priority: 'medium',
      enabled: true,
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    setEditRule(newRule);
    setShowRuleModal(true);
  }, []);

  const handleSaveRule = useCallback(async (rule: AlertRule) => {
    try {
      await onUpdateRule(rule);
      setShowRuleModal(false);
      setEditRule(null);
      setShowToast({
        message: 'Alert rule saved successfully!',
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to save alert rule.',
        type: 'error',
      });
    }
  }, [onUpdateRule]);

  const handleDeleteRule = useCallback(async (ruleId: string) => {
    if (!confirm('Are you sure you want to delete this rule?')) return;
    try {
      await onDeleteRule(ruleId);
      setShowToast({
        message: 'Alert rule deleted successfully.',
        type: 'info',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to delete alert rule.',
        type: 'error',
      });
    }
  }, [onDeleteRule]);

  // ============================================
  // Handlers - Templates
  // ============================================

  const handleCreateTemplate = useCallback(() => {
    const newTemplate: AlertTemplate = {
      id: `template-${Date.now()}`,
      name: 'New Template',
      subject: 'Alert: {{symbol}} {{condition}} {{value}}',
      body: 'Alert triggered for {{symbol}} at {{timestamp}}',
      channels: ['email', 'push'],
      priority: 'medium',
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    setEditTemplate(newTemplate);
    setShowTemplateModal(true);
  }, []);

  const handleSaveTemplate = useCallback(async (template: AlertTemplate) => {
    try {
      await onUpdateTemplate(template);
      setShowTemplateModal(false);
      setEditTemplate(null);
      setShowToast({
        message: 'Template saved successfully!',
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to save template.',
        type: 'error',
      });
    }
  }, [onUpdateTemplate]);

  const handleDeleteTemplate = useCallback(async (templateId: string) => {
    if (!confirm('Are you sure you want to delete this template?')) return;
    try {
      await onDeleteTemplate(templateId);
      setShowToast({
        message: 'Template deleted successfully.',
        type: 'info',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to delete template.',
        type: 'error',
      });
    }
  }, [onDeleteTemplate]);

  // ============================================
  // Handlers - Webhooks
  // ============================================

  const handleCreateWebhook = useCallback(() => {
    const newWebhook: WebhookConfig = {
      id: `webhook-${Date.now()}`,
      name: 'New Webhook',
      url: '',
      events: [],
      enabled: true,
      secret: '',
      retryCount: 3,
      timeout: 5000,
      createdAt: new Date(),
      updatedAt: new Date(),
    };
    setEditWebhook(newWebhook);
    setShowWebhookModal(true);
  }, []);

  const handleSaveWebhook = useCallback(async (webhook: WebhookConfig) => {
    try {
      await onUpdateWebhook(webhook);
      setShowWebhookModal(false);
      setEditWebhook(null);
      setShowToast({
        message: 'Webhook saved successfully!',
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to save webhook.',
        type: 'error',
      });
    }
  }, [onUpdateWebhook]);

  const handleDeleteWebhook = useCallback(async (webhookId: string) => {
    if (!confirm('Are you sure you want to delete this webhook?')) return;
    try {
      await onDeleteWebhook(webhookId);
      setShowToast({
        message: 'Webhook deleted successfully.',
        type: 'info',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to delete webhook.',
        type: 'error',
      });
    }
  }, [onDeleteWebhook]);

  // ============================================
  // Handlers - Testing
  // ============================================

  const handleTestChannel = useCallback(async (channel: AlertChannel) => {
    setIsTestingChannel(channel);
    setIsTesting(true);
    try {
      // In production, call API to send test notification
      await new Promise(resolve => setTimeout(resolve, 1000));
      setShowToast({
        message: `Test notification sent to ${channel}!`,
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || `Failed to send test to ${channel}.`,
        type: 'error',
      });
    } finally {
      setIsTesting(false);
      setIsTestingChannel(null);
    }
  }, []);

  // ============================================
  // Render Helpers
  // ============================================

  const renderPriorityBadge = (priority: AlertPriority) => {
    const config = {
      low: { color: 'bg-blue-500/20 text-blue-500 border-blue-500/30', label: 'Low' },
      medium: { color: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30', label: 'Medium' },
      high: { color: 'bg-orange-500/20 text-orange-500 border-orange-500/30', label: 'High' },
      critical: { color: 'bg-red-500/20 text-red-500 border-red-500/30', label: 'Critical' },
    };
    const { color, label } = config[priority] || config.medium;
    return <Badge className={cn("text-xs", color)}>{label}</Badge>;
  };

  const renderChannelIcon = (channel: AlertChannel) => {
    const icons: Record<AlertChannel, React.ReactNode> = {
      email: <MailIcon className="w-4 h-4" />,
      push: <SmartphoneIcon className="w-4 h-4" />,
      sms: <MessageSquareIcon className="w-4 h-4" />,
      slack: <Slack className="w-4 h-4" />,
      telegram: <Send className="w-4 h-4" />,
      discord: <MessageCircle className="w-4 h-4" />,
      webhook: <WebhookIcon className="w-4 h-4" />,
    };
    return icons[channel] || <BellIcon className="w-4 h-4" />;
  };

  // ============================================
  // Render
  // ============================================

  if (isLoading) {
    return (
      <Card className={cn("p-6 bg-gray-800 border-gray-700", className)}>
        <div className="flex items-center justify-center h-64">
          <Spinner size="lg" className="text-cyan-500" />
        </div>
      </Card>
    );
  }

  return (
    <Card className={cn("p-6 bg-gray-800 border-gray-700", className)}>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h3 className="text-lg font-semibold text-white">Alert Settings</h3>
          <p className="text-sm text-gray-400">Configure how you receive and manage alerts</p>
        </div>
        <Button
          onClick={handleSaveSettings}
          isLoading={isSaving}
          className="bg-gradient-to-r from-cyan-500 to-blue-500"
        >
          <Save className="w-4 h-4 mr-2" />
          Save Changes
        </Button>
      </div>

      {/* Tabs */}
      <Tabs value={activeTab} onValueChange={setActiveTab}>
        <TabsList className="bg-gray-700/30 rounded-lg p-1 mb-6">
          <TabsTrigger value="general" className="text-xs">General</TabsTrigger>
          <TabsTrigger value="preferences" className="text-xs">Preferences</TabsTrigger>
          <TabsTrigger value="quiet-hours" className="text-xs">Quiet Hours</TabsTrigger>
          <TabsTrigger value="rules" className="text-xs">Rules</TabsTrigger>
          <TabsTrigger value="templates" className="text-xs">Templates</TabsTrigger>
          {showAdvanced && (
            <TabsTrigger value="webhooks" className="text-xs">Webhooks</TabsTrigger>
          )}
        </TabsList>

        {/* ========================================== */}
        {/* GENERAL TAB */}
        {/* ========================================== */}
        <TabsContent value="general">
          <div className="space-y-4">
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Default Priority</label>
                <Select
                  value={settings.defaultPriority || 'medium'}
                  onValueChange={(value) => handleSettingsChange('defaultPriority', value as AlertPriority)}
                  className="w-full bg-gray-700 border-gray-600"
                >
                  {ALERT_PRIORITIES.map((priority) => (
                    <option key={priority.value} value={priority.value}>
                      {priority.label}
                    </option>
                  ))}
                </Select>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Cooldown (seconds)</label>
                <Input
                  type="number"
                  value={settings.cooldown || 300}
                  onChange={(e) => handleSettingsChange('cooldown', parseInt(e.target.value) || 300)}
                  className="w-full bg-gray-700 border-gray-600 text-white"
                  min={0}
                  max={3600}
                />
              </div>
            </div>

            <div className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
              <div>
                <p className="text-sm text-white">Sound Notifications</p>
                <p className="text-xs text-gray-400">Play sound when alerts are triggered</p>
              </div>
              <Switch
                checked={settings.soundEnabled || false}
                onCheckedChange={(checked) => handleSettingsChange('soundEnabled', checked)}
                className="data-[state=checked]:bg-cyan-500"
              />
            </div>

            <div className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
              <div>
                <p className="text-sm text-white">Desktop Notifications</p>
                <p className="text-xs text-gray-400">Show desktop notifications for alerts</p>
              </div>
              <Switch
                checked={settings.desktopEnabled || false}
                onCheckedChange={(checked) => handleSettingsChange('desktopEnabled', checked)}
                className="data-[state=checked]:bg-cyan-500"
              />
            </div>

            <div className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
              <div>
                <p className="text-sm text-white">Email Digest</p>
                <p className="text-xs text-gray-400">Send a daily digest of alerts via email</p>
              </div>
              <Switch
                checked={settings.emailDigest || false}
                onCheckedChange={(checked) => handleSettingsChange('emailDigest', checked)}
                className="data-[state=checked]:bg-cyan-500"
              />
            </div>
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* PREFERENCES TAB */}
        {/* ========================================== */}
        <TabsContent value="preferences">
          <div className="space-y-6">
            {ALERT_CHANNELS.map((channel) => {
              const preference = settings.preferences[channel.value] || {};
              return (
                <div key={channel.value} className="p-4 bg-gray-700/30 rounded-lg">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      {renderChannelIcon(channel.value)}
                      <span className="text-sm font-medium text-white">{channel.label}</span>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => handleTestChannel(channel.value)}
                        isLoading={isTestingChannel === channel.value}
                        className="text-xs text-cyan-400 hover:text-cyan-300"
                      >
                        Test
                      </Button>
                    </div>
                    <Switch
                      checked={preference.enabled !== false}
                      onCheckedChange={(checked) => handlePreferenceChange(channel.value, 'enabled', checked)}
                      className="data-[state=checked]:bg-cyan-500"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-sm">
                    <div>
                      <label className="block text-xs text-gray-400">Priority Level</label>
                      <Select
                        value={preference.minPriority || 'low'}
                        onValueChange={(value) => handlePreferenceChange(channel.value, 'minPriority', value)}
                        className="w-full bg-gray-700 border-gray-600 text-xs"
                        disabled={!preference.enabled}
                      >
                        {ALERT_PRIORITIES.map((p) => (
                          <option key={p.value} value={p.value}>{p.label}</option>
                        ))}
                      </Select>
                    </div>
                    <div>
                      <label className="block text-xs text-gray-400">Frequency</label>
                      <Select
                        value={preference.frequency || 'immediate'}
                        onValueChange={(value) => handlePreferenceChange(channel.value, 'frequency', value)}
                        className="w-full bg-gray-700 border-gray-600 text-xs"
                        disabled={!preference.enabled}
                      >
                        <option value="immediate">Immediate</option>
                        <option value="digest">Digest</option>
                        <option value="daily">Daily</option>
                        <option value="weekly">Weekly</option>
                      </Select>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* QUIET HOURS TAB */}
        {/* ========================================== */}
        <TabsContent value="quiet-hours">
          <div className="space-y-4">
            <div className="flex items-center justify-between p-3 bg-gray-700/30 rounded-lg">
              <div>
                <p className="text-sm text-white">Enable Quiet Hours</p>
                <p className="text-xs text-gray-400">Suppress alerts during specified hours</p>
              </div>
              <Switch
                checked={quietHours.enabled || false}
                onCheckedChange={(checked) => handleQuietHoursChange('enabled', checked)}
                className="data-[state=checked]:bg-cyan-500"
              />
            </div>

            {quietHours.enabled && (
              <>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">Start Time</label>
                    <Input
                      type="time"
                      value={quietHours.start || '22:00'}
                      onChange={(e) => handleQuietHoursChange('start', e.target.value)}
                      className="w-full bg-gray-700 border-gray-600 text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">End Time</label>
                    <Input
                      type="time"
                      value={quietHours.end || '07:00'}
                      onChange={(e) => handleQuietHoursChange('end', e.target.value)}
                      className="w-full bg-gray-700 border-gray-600 text-white"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm text-gray-400 mb-2">Days of Week</label>
                  <div className="flex flex-wrap gap-2">
                    {['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'].map((day, index) => (
                      <button
                        key={day}
                        onClick={() => {
                          const days = quietHours.days || [];
                          const dayIndex = index + 1;
                          const newDays = days.includes(dayIndex)
                            ? days.filter(d => d !== dayIndex)
                            : [...days, dayIndex];
                          handleQuietHoursChange('days', newDays);
                        }}
                        className={cn(
                          "px-3 py-1 rounded-lg text-xs transition-colors",
                          (quietHours.days || []).includes(index + 1)
                            ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                            : "bg-gray-700 text-gray-400 border border-gray-600 hover:border-gray-500"
                        )}
                      >
                        {day}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-2 p-3 bg-yellow-500/10 border border-yellow-500/30 rounded-lg">
                  <AlertCircle className="w-4 h-4 text-yellow-500" />
                  <p className="text-xs text-yellow-500">
                    Critical alerts will still be sent during quiet hours.
                  </p>
                </div>

                <Button
                  onClick={handleSaveQuietHours}
                  isLoading={isSaving}
                  className="w-full bg-gradient-to-r from-cyan-500 to-blue-500"
                >
                  Save Quiet Hours
                </Button>
              </>
            )}
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* RULES TAB */}
        {/* ========================================== */}
        <TabsContent value="rules">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">Custom alert rules</span>
              <Button
                onClick={handleCreateRule}
                className="bg-gradient-to-r from-cyan-500 to-blue-500"
              >
                <Plus className="w-4 h-4 mr-2" />
                Add Rule
              </Button>
            </div>

            {settings.rules && settings.rules.length > 0 ? (
              <div className="space-y-3">
                {settings.rules.map((rule) => (
                  <div key={rule.id} className="p-3 bg-gray-700/30 rounded-lg">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-white">{rule.name}</span>
                          {renderPriorityBadge(rule.priority)}
                          <Badge className={cn(
                            "text-xs",
                            rule.enabled ? 'bg-green-500/20 text-green-500' : 'bg-gray-500/20 text-gray-400'
                          )}>
                            {rule.enabled ? 'Active' : 'Inactive'}
                          </Badge>
                        </div>
                        <div className="text-sm text-gray-400 mt-1">
                          {rule.type}: {rule.condition} {rule.value}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          Created: {formatDate(rule.createdAt)}
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setEditRule(rule);
                            setShowRuleModal(true);
                          }}
                          className="text-gray-400 hover:text-white"
                        >
                          <Edit className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteRule(rule.id)}
                          className="text-gray-400 hover:text-red-500"
                        >
                          <Trash className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <Bell className="w-12 h-12 mx-auto mb-3 text-gray-600" />
                <p>No custom rules configured</p>
                <p className="text-sm">Create rules to customize alert conditions</p>
              </div>
            )}
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* TEMPLATES TAB */}
        {/* ========================================== */}
        <TabsContent value="templates">
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">Alert templates</span>
              <Button
                onClick={handleCreateTemplate}
                className="bg-gradient-to-r from-cyan-500 to-blue-500"
              >
                <Plus className="w-4 h-4 mr-2" />
                Add Template
              </Button>
            </div>

            {settings.templates && settings.templates.length > 0 ? (
              <div className="space-y-3">
                {settings.templates.map((template) => (
                  <div key={template.id} className="p-3 bg-gray-700/30 rounded-lg">
                    <div className="flex items-start justify-between">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="text-sm font-medium text-white">{template.name}</span>
                          <Badge className="text-xs bg-gray-600">{template.channels.join(', ')}</Badge>
                        </div>
                        <div className="text-sm text-gray-400 mt-1">Subject: {template.subject}</div>
                        <div className="text-xs text-gray-500 mt-1">
                          Updated: {formatDate(template.updatedAt)}
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => {
                            setEditTemplate(template);
                            setShowTemplateModal(true);
                          }}
                          className="text-gray-400 hover:text-white"
                        >
                          <Edit className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteTemplate(template.id)}
                          className="text-gray-400 hover:text-red-500"
                        >
                          <Trash className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-gray-500">
                <File className="w-12 h-12 mx-auto mb-3 text-gray-600" />
                <p>No templates configured</p>
                <p className="text-sm">Create templates for consistent alert formatting</p>
              </div>
            )}
          </div>
        </TabsContent>

        {/* ========================================== */}
        {/* WEBHOOKS TAB */}
        {/* ========================================== */}
        {showAdvanced && (
          <TabsContent value="webhooks">
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-400">Webhook integrations</span>
                <Button
                  onClick={handleCreateWebhook}
                  className="bg-gradient-to-r from-cyan-500 to-blue-500"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Add Webhook
                </Button>
              </div>

              {settings.webhooks && settings.webhooks.length > 0 ? (
                <div className="space-y-3">
                  {settings.webhooks.map((webhook) => (
                    <div key={webhook.id} className="p-3 bg-gray-700/30 rounded-lg">
                      <div className="flex items-start justify-between">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-medium text-white">{webhook.name}</span>
                            <Badge className={cn(
                              "text-xs",
                              webhook.enabled ? 'bg-green-500/20 text-green-500' : 'bg-gray-500/20 text-gray-400'
                            )}>
                              {webhook.enabled ? 'Active' : 'Inactive'}
                            </Badge>
                          </div>
                          <div className="text-sm text-gray-400 mt-1 truncate max-w-xs">{webhook.url}</div>
                          <div className="text-xs text-gray-500 mt-1">
                            Events: {webhook.events?.join(', ') || 'All'}
                          </div>
                        </div>
                        <div className="flex items-center gap-1">
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => {
                              setEditWebhook(webhook);
                              setShowWebhookModal(true);
                            }}
                            className="text-gray-400 hover:text-white"
                          >
                            <Edit className="w-4 h-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => handleDeleteWebhook(webhook.id)}
                            className="text-gray-400 hover:text-red-500"
                          >
                            <Trash className="w-4 h-4" />
                          </Button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="text-center py-8 text-gray-500">
                  <Webhook className="w-12 h-12 mx-auto mb-3 text-gray-600" />
                  <p>No webhooks configured</p>
                  <p className="text-sm">Add webhooks to send alerts to external services</p>
                </div>
              )}
            </div>
          </TabsContent>
        )}
      </Tabs>

      {/* ============================================ */}
      {/* RULE MODAL */}
      {/* ============================================ */}
      <Modal
        open={showRuleModal && !!editRule}
        onOpenChange={setShowRuleModal}
        title={editRule?.id?.startsWith('rule-') ? 'Edit Rule' : 'Create Rule'}
        className="max-w-md"
      >
        {editRule && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Rule Name *</label>
              <Input
                value={editRule.name}
                onChange={(e) => setEditRule({ ...editRule, name: e.target.value })}
                className="w-full bg-gray-700 border-gray-600 text-white"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Type</label>
              <Select                value={editRule.type}
                onValueChange={(value) => setEditRule({ ...editRule, type: value as any })}
                className="w-full bg-gray-700 border-gray-600"
              >
                {ALERT_TYPES.map((type) => (
                  <option key={type.value} value={type.value}>{type.label}</option>
                ))}
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Condition</label>
                <Select
                  value={editRule.condition}
                  onValueChange={(value) => setEditRule({ ...editRule, condition: value as any })}
                  className="w-full bg-gray-700 border-gray-600"
                >
                  <option value="above">Above</option>
                  <option value="below">Below</option>
                  <option value="crosses_above">Crosses Above</option>
                  <option value="crosses_below">Crosses Below</option>
                </Select>
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Value *</label>
                <Input
                  type="number"
                  step="0.01"
                  value={editRule.value}
                  onChange={(e) => setEditRule({ ...editRule, value: parseFloat(e.target.value) || 0 })}
                  className="w-full bg-gray-700 border-gray-600 text-white"
                />
              </div>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Priority</label>
              <Select
                value={editRule.priority}
                onValueChange={(value) => setEditRule({ ...editRule, priority: value as AlertPriority })}
                className="w-full bg-gray-700 border-gray-600"
              >
                {ALERT_PRIORITIES.map((priority) => (
                  <option key={priority.value} value={priority.value}>{priority.label}</option>
                ))}
              </Select>
            </div>
            <div className="flex items-center justify-between p-2 bg-gray-700/30 rounded-lg">
              <span className="text-sm text-gray-400">Enable Rule</span>
              <Switch
                checked={editRule.enabled !== false}
                onCheckedChange={(checked) => setEditRule({ ...editRule, enabled: checked })}
                className="data-[state=checked]:bg-cyan-500"
              />
            </div>
            <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
              <Button
                variant="outline"
                onClick={() => {
                  setShowRuleModal(false);
                  setEditRule(null);
                }}
                className="border-gray-600 hover:border-gray-500"
              >
                Cancel
              </Button>
              <Button
                onClick={() => handleSaveRule(editRule)}
                className="bg-gradient-to-r from-cyan-500 to-blue-500"
              >
                {editRule.id?.startsWith('rule-') ? 'Create' : 'Save'} Rule
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* ============================================ */}
      {/* TEMPLATE MODAL */}
      {/* ============================================ */}
      <Modal
        open={showTemplateModal && !!editTemplate}
        onOpenChange={setShowTemplateModal}
        title={editTemplate?.id?.startsWith('template-') ? 'Create Template' : 'Edit Template'}
        className="max-w-md"
      >
        {editTemplate && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Template Name *</label>
              <Input
                value={editTemplate.name}
                onChange={(e) => setEditTemplate({ ...editTemplate, name: e.target.value })}
                className="w-full bg-gray-700 border-gray-600 text-white"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Subject</label>
              <Input
                value={editTemplate.subject}
                onChange={(e) => setEditTemplate({ ...editTemplate, subject: e.target.value })}
                placeholder="Alert: {{symbol}} {{condition}} {{value}}"
                className="w-full bg-gray-700 border-gray-600 text-white"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Body</label>
              <Textarea
                value={editTemplate.body}
                onChange={(e) => setEditTemplate({ ...editTemplate, body: e.target.value })}
                placeholder="Alert triggered for {{symbol}} at {{timestamp}}"
                className="w-full bg-gray-700 border-gray-600 text-white resize-none"
                rows={3}
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Channels</label>
              <div className="flex flex-wrap gap-2">
                {ALERT_CHANNELS.map((channel) => (
                  <button
                    key={channel.value}
                    onClick={() => {
                      const channels = editTemplate.channels || [];
                      const newChannels = channels.includes(channel.value)
                        ? channels.filter(c => c !== channel.value)
                        : [...channels, channel.value];
                      setEditTemplate({ ...editTemplate, channels: newChannels });
                    }}
                    className={cn(
                      "px-3 py-1 rounded-lg text-xs transition-colors flex items-center gap-1",
                      (editTemplate.channels || []).includes(channel.value)
                        ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                        : "bg-gray-700 text-gray-400 border border-gray-600 hover:border-gray-500"
                    )}
                  >
                    {renderChannelIcon(channel.value)}
                    {channel.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Priority</label>
              <Select
                value={editTemplate.priority}
                onValueChange={(value) => setEditTemplate({ ...editTemplate, priority: value as AlertPriority })}
                className="w-full bg-gray-700 border-gray-600"
              >
                {ALERT_PRIORITIES.map((priority) => (
                  <option key={priority.value} value={priority.value}>{priority.label}</option>
                ))}
              </Select>
            </div>
            <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
              <Button
                variant="outline"
                onClick={() => {
                  setShowTemplateModal(false);
                  setEditTemplate(null);
                }}
                className="border-gray-600 hover:border-gray-500"
              >
                Cancel
              </Button>
              <Button
                onClick={() => handleSaveTemplate(editTemplate)}
                className="bg-gradient-to-r from-cyan-500 to-blue-500"
              >
                {editTemplate.id?.startsWith('template-') ? 'Create' : 'Save'} Template
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* ============================================ */}
      {/* WEBHOOK MODAL */}
      {/* ============================================ */}
      <Modal
        open={showWebhookModal && !!editWebhook}
        onOpenChange={setShowWebhookModal}
        title={editWebhook?.id?.startsWith('webhook-') ? 'Create Webhook' : 'Edit Webhook'}
        className="max-w-md"
      >
        {editWebhook && (
          <div className="space-y-4">
            <div>
              <label className="block text-sm text-gray-400 mb-1">Webhook Name *</label>
              <Input
                value={editWebhook.name}
                onChange={(e) => setEditWebhook({ ...editWebhook, name: e.target.value })}
                className="w-full bg-gray-700 border-gray-600 text-white"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">URL *</label>
              <Input
                value={editWebhook.url}
                onChange={(e) => setEditWebhook({ ...editWebhook, url: e.target.value })}
                placeholder="https://example.com/webhook"
                className="w-full bg-gray-700 border-gray-600 text-white"
              />
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Events</label>
              <div className="flex flex-wrap gap-2">
                {ALERT_TYPES.map((type) => (
                  <button
                    key={type.value}
                    onClick={() => {
                      const events = editWebhook.events || [];
                      const newEvents = events.includes(type.value)
                        ? events.filter(e => e !== type.value)
                        : [...events, type.value];
                      setEditWebhook({ ...editWebhook, events: newEvents });
                    }}
                    className={cn(
                      "px-3 py-1 rounded-lg text-xs transition-colors",
                      (editWebhook.events || []).includes(type.value)
                        ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                        : "bg-gray-700 text-gray-400 border border-gray-600 hover:border-gray-500"
                    )}
                  >
                    {type.label}
                  </button>
                ))}
              </div>
            </div>
            <div>
              <label className="block text-sm text-gray-400 mb-1">Secret (optional)</label>
              <Input
                type="password"
                value={editWebhook.secret || ''}
                onChange={(e) => setEditWebhook({ ...editWebhook, secret: e.target.value })}
                placeholder="Enter webhook secret"
                className="w-full bg-gray-700 border-gray-600 text-white"
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm text-gray-400 mb-1">Retry Count</label>
                <Input
                  type="number"
                  value={editWebhook.retryCount || 3}
                  onChange={(e) => setEditWebhook({ ...editWebhook, retryCount: parseInt(e.target.value) || 3 })}
                  className="w-full bg-gray-700 border-gray-600 text-white"
                  min={0}
                  max={10}
                />
              </div>
              <div>
                <label className="block text-sm text-gray-400 mb-1">Timeout (ms)</label>
                <Input
                  type="number"
                  value={editWebhook.timeout || 5000}
                  onChange={(e) => setEditWebhook({ ...editWebhook, timeout: parseInt(e.target.value) || 5000 })}
                  className="w-full bg-gray-700 border-gray-600 text-white"
                  min={1000}
                  max={30000}
                />
              </div>
            </div>
            <div className="flex items-center justify-between p-2 bg-gray-700/30 rounded-lg">
              <span className="text-sm text-gray-400">Enable Webhook</span>
              <Switch
                checked={editWebhook.enabled !== false}
                onCheckedChange={(checked) => setEditWebhook({ ...editWebhook, enabled: checked })}
                className="data-[state=checked]:bg-cyan-500"
              />
            </div>
            <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
              <Button
                variant="outline"
                onClick={() => {
                  setShowWebhookModal(false);
                  setEditWebhook(null);
                }}
                className="border-gray-600 hover:border-gray-500"
              >
                Cancel
              </Button>
              <Button
                onClick={() => handleSaveWebhook(editWebhook)}
                className="bg-gradient-to-r from-cyan-500 to-blue-500"
              >
                {editWebhook.id?.startsWith('webhook-') ? 'Create' : 'Save'} Webhook
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
    </Card>
  );
}

// ============================================
// Export
// ============================================

export default AlertSettings;

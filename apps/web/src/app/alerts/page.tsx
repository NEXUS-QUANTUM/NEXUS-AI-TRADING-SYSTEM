/**
 * NEXUS AI TRADING SYSTEM - Alerts Management Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page provides comprehensive alert management including:
 * - Real-time price alerts
 * - AI signal alerts
 * - Technical indicator alerts
 * - Custom alert creation
 * - Alert history and logs
 * - Notification preferences
 * - WebSocket real-time updates
 */

'use client';

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useWebSocket } from '@/hooks/useWebSocket';
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
import { Switch } from '@/components/ui/Switch';
import { Modal } from '@/components/ui/Modal';
import { Table } from '@/components/ui/Table';

// Types
import type {
  Alert,
  AlertType,
  AlertCondition,
  AlertTrigger,
  AlertNotification,
  AlertRule,
  AlertHistory,
  AlertSettings,
  AlertStats,
} from '@/types/alerts';

// Constants
import {
  ALERT_TYPES,
  ALERT_CONDITIONS,
  ALERT_PRIORITIES,
  ALERT_STATUSES,
  SUPPORTED_SYMBOLS,
  TIME_FRAMES,
} from '@/constants/alerts';

// Hooks
import { useAlerts } from '@/hooks/useAlerts';
import { useNotifications } from '@/hooks/useNotifications';

// Utils
import { formatCurrency, formatPercentage, formatTime, formatNumber } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

export default function AlertsPage() {
  // Authentication
  const { user, isAuthenticated, accessToken } = useAuth();
  
  // API client
  const api = useApi();
  
  // Refs
  const wsCleanupRef = useRef<(() => void) | null>(null);
  const alertPollIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  
  // State - Alerts
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [activeAlerts, setActiveAlerts] = useState<Alert[]>([]);
  const [triggeredAlerts, setTriggeredAlerts] = useState<Alert[]>([]);
  const [alertHistory, setAlertHistory] = useState<AlertHistory[]>([]);
  const [alertStats, setAlertStats] = useState<AlertStats | null>(null);
  const [alertsLoading, setAlertsLoading] = useState<boolean>(true);
  
  // State - Alert Creation
  const [showCreateModal, setShowCreateModal] = useState<boolean>(false);
  const [editingAlert, setEditingAlert] = useState<Alert | null>(null);
  const [newAlert, setNewAlert] = useState<Partial<Alert>>({
    name: '',
    type: 'price',
    symbol: 'BTC-USD',
    condition: 'above',
    value: 0,
    priority: 'medium',
    timeframe: '1h',
    enabled: true,
    notificationChannels: ['push', 'email'],
    cooldown: 300,
    triggerCount: 1,
    duration: 0,
  });
  const [isCreating, setIsCreating] = useState<boolean>(false);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  
  // State - Alert Settings
  const [settings, setSettings] = useState<AlertSettings>({
    emailNotifications: true,
    pushNotifications: true,
    soundNotifications: true,
    desktopNotifications: true,
    telegramNotifications: false,
    slackNotifications: false,
    discordNotifications: false,
    minPriority: 'low',
    maxDailyAlerts: 50,
    cooldownDefault: 300,
    soundFile: 'default',
  });
  const [settingsLoading, setSettingsLoading] = useState<boolean>(true);
  
  // State - UI
  const [activeTab, setActiveTab] = useState<string>('active');
  const [selectedAlert, setSelectedAlert] = useState<Alert | null>(null);
  const [showHistoryModal, setShowHistoryModal] = useState<boolean>(false);
  const [filterType, setFilterType] = useState<string>('all');
  const [filterPriority, setFilterPriority] = useState<string>('all');
  const [filterSymbol, setFilterSymbol] = useState<string>('all');
  const [showToast, setShowToast] = useState<{ message: string; type: 'success' | 'error' | 'info' | 'warning' } | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedAlerts, setSelectedAlerts] = useState<string[]>([]);
  const [isBulkDeleting, setIsBulkDeleting] = useState<boolean>(false);
  const [isBulkDisabling, setIsBulkDisabling] = useState<boolean>(false);

  // ============================================
  // WebSocket Connection
  // ============================================
  const { 
    isConnected, 
    sendMessage, 
    subscribe: wsSubscribe,
    unsubscribe: wsUnsubscribe,
    messages,
  } = useWebSocket({
    url: `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8004'}/alerts`,
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
    console.log('✅ Alerts WebSocket connected');
    subscribeToChannels();
  }

  function handleWebSocketMessage(event: MessageEvent) {
    try {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'alert_triggered':
          handleAlertTriggered(data.payload);
          break;
        case 'alert_created':
          handleAlertCreated(data.payload);
          break;
        case 'alert_updated':
          handleAlertUpdated(data.payload);
          break;
        case 'alert_deleted':
          handleAlertDeleted(data.payload);
          break;
        case 'alert_bulk_update':
          handleAlertBulkUpdate(data.payload);
          break;
        case 'alert_history':
          handleAlertHistoryUpdate(data.payload);
          break;
        case 'alert_stats':
          handleAlertStatsUpdate(data.payload);
          break;
        case 'error':
          handleAlertError(data.payload);
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
    console.log('Alerts WebSocket disconnected');
  }

  function subscribeToChannels() {
    if (!isConnected) return;

    wsSubscribe({
      channel: 'alerts',
      type: 'all',
    });

    wsSubscribe({
      channel: 'alerts_triggered',
      limit: 50,
    });

    wsSubscribe({
      channel: 'alerts_stats',
    });
  }

  // ============================================
  // WebSocket Data Handlers
  // ============================================
  function handleAlertTriggered(data: any) {
    const triggeredAlert: Alert = {
      id: data.id || `alert-${Date.now()}`,
      name: data.name || 'Unknown Alert',
      type: data.type || 'price',
      symbol: data.symbol || 'BTC-USD',
      condition: data.condition || 'above',
      value: data.value || 0,
      priority: data.priority || 'medium',
      timeframe: data.timeframe || '1h',
      enabled: true,
      notificationChannels: data.notificationChannels || ['push'],
      cooldown: data.cooldown || 300,
      triggerCount: data.triggerCount || 1,
      duration: data.duration || 0,
      createdAt: new Date(data.createdAt || Date.now()),
      updatedAt: new Date(data.updatedAt || Date.now()),
      lastTriggered: new Date(data.lastTriggered || Date.now()),
      triggeredValue: data.triggeredValue || 0,
      triggeredCondition: data.triggeredCondition || '',
      status: 'triggered',
      metadata: data.metadata || {},
    };

    setActiveAlerts(prev => [triggeredAlert, ...prev]);
    setAlerts(prev => 
      prev.map(a => 
        a.id === triggeredAlert.id 
          ? { ...a, status: 'triggered', lastTriggered: triggeredAlert.lastTriggered }
          : a
      )
    );

    // Add to history
    setAlertHistory(prev => [
      {
        id: `history-${Date.now()}`,
        alertId: triggeredAlert.id,
        alertName: triggeredAlert.name,
        symbol: triggeredAlert.symbol,
        type: triggeredAlert.type,
        condition: triggeredAlert.condition,
        value: triggeredAlert.value,
        triggeredValue: triggeredAlert.triggeredValue || 0,
        timestamp: new Date(),
        triggeredAt: new Date(),
        acknowledged: false,
        acknowledgedAt: undefined,
        acknowledgedBy: undefined,
        metadata: {},
      },
      ...prev,
    ]);

    // Play sound notification
    if (settings.soundNotifications) {
      playAlertSound(triggeredAlert.priority);
    }

    // Show desktop notification
    if (settings.desktopNotifications && 'Notification' in window) {
      showDesktopNotification(triggeredAlert);
    }

    setShowToast({
      message: `🔔 Alert Triggered: ${triggeredAlert.name} - ${triggeredAlert.symbol} ${triggeredAlert.condition} ${formatCurrency(triggeredAlert.value)}`,
      type: 'warning',
    });
  }

  function handleAlertCreated(data: any) {
    const newAlert: Alert = {
      id: data.id || `alert-${Date.now()}`,
      name: data.name || 'New Alert',
      type: data.type || 'price',
      symbol: data.symbol || 'BTC-USD',
      condition: data.condition || 'above',
      value: data.value || 0,
      priority: data.priority || 'medium',
      timeframe: data.timeframe || '1h',
      enabled: data.enabled !== undefined ? data.enabled : true,
      notificationChannels: data.notificationChannels || ['push'],
      cooldown: data.cooldown || 300,
      triggerCount: data.triggerCount || 1,
      duration: data.duration || 0,
      createdAt: new Date(data.createdAt || Date.now()),
      updatedAt: new Date(data.updatedAt || Date.now()),
      status: 'active',
      metadata: data.metadata || {},
    };

    setAlerts(prev => [newAlert, ...prev]);
    
    if (newAlert.enabled) {
      setActiveAlerts(prev => [newAlert, ...prev]);
    }

    setShowToast({
      message: `✅ Alert created: ${newAlert.name}`,
      type: 'success',
    });
  }

  function handleAlertUpdated(data: any) {
    const updatedAlert: Alert = {
      ...data,
      createdAt: new Date(data.createdAt || Date.now()),
      updatedAt: new Date(data.updatedAt || Date.now()),
      lastTriggered: data.lastTriggered ? new Date(data.lastTriggered) : undefined,
    };

    setAlerts(prev => 
      prev.map(a => a.id === updatedAlert.id ? updatedAlert : a)
    );

    setActiveAlerts(prev => 
      prev.map(a => a.id === updatedAlert.id ? updatedAlert : a)
    );

    setShowToast({
      message: `✏️ Alert updated: ${updatedAlert.name}`,
      type: 'info',
    });
  }

  function handleAlertDeleted(data: any) {
    setAlerts(prev => prev.filter(a => a.id !== data.id));
    setActiveAlerts(prev => prev.filter(a => a.id !== data.id));
    setTriggeredAlerts(prev => prev.filter(a => a.id !== data.id));

    setShowToast({
      message: `🗑️ Alert deleted: ${data.name || 'Unknown'}`,
      type: 'info',
    });
  }

  function handleAlertBulkUpdate(data: any) {
    if (data.ids && data.action) {
      if (data.action === 'disable') {
        setAlerts(prev => 
          prev.map(a => 
            data.ids.includes(a.id) ? { ...a, enabled: false } : a
          )
        );
        setActiveAlerts(prev => 
          prev.filter(a => !data.ids.includes(a.id))
        );
      } else if (data.action === 'enable') {
        setAlerts(prev => 
          prev.map(a => 
            data.ids.includes(a.id) ? { ...a, enabled: true } : a
          )
        );
        // Refresh alerts to get enabled ones
        fetchAlerts();
      } else if (data.action === 'delete') {
        setAlerts(prev => prev.filter(a => !data.ids.includes(a.id)));
        setActiveAlerts(prev => prev.filter(a => !data.ids.includes(a.id)));
        setTriggeredAlerts(prev => prev.filter(a => !data.ids.includes(a.id)));
      }
      
      setSelectedAlerts([]);
      setShowToast({
        message: `Bulk ${data.action} completed for ${data.ids.length} alerts`,
        type: 'info',
      });
    }
  }

  function handleAlertHistoryUpdate(data: any) {
    if (data.history) {
      setAlertHistory(prev => [
        ...data.history.map((h: any) => ({
          ...h,
          timestamp: new Date(h.timestamp || Date.now()),
          triggeredAt: new Date(h.triggeredAt || Date.now()),
          acknowledgedAt: h.acknowledgedAt ? new Date(h.acknowledgedAt) : undefined,
        })),
        ...prev,
      ].slice(0, 500));
    }
  }

  function handleAlertStatsUpdate(data: any) {
    setAlertStats({
      totalAlerts: data.totalAlerts || 0,
      activeAlerts: data.activeAlerts || 0,
      triggeredToday: data.triggeredToday || 0,
      triggeredThisWeek: data.triggeredThisWeek || 0,
      triggeredThisMonth: data.triggeredThisMonth || 0,
      byType: data.byType || {},
      byPriority: data.byPriority || {},
      bySymbol: data.bySymbol || {},
      successRate: data.successRate || 0,
      averageResponseTime: data.averageResponseTime || 0,
    });
  }

  function handleAlertError(data: any) {
    setShowToast({
      message: data.message || 'Alert service error occurred',
      type: 'error',
    });
  }

  // ============================================
  // Sound and Desktop Notifications
  // ============================================
  function playAlertSound(priority: string) {
    try {
      if (!audioRef.current) {
        audioRef.current = new Audio();
      }
      
      let soundFile = 'default.mp3';
      if (priority === 'high') {
        soundFile = 'high_priority.mp3';
      } else if (priority === 'critical') {
        soundFile = 'critical.mp3';
      }
      
      audioRef.current.src = `/sounds/${soundFile}`;
      audioRef.current.volume = 0.7;
      audioRef.current.play().catch(() => {
        // Auto-play blocked, ignore
      });
    } catch (error) {
      console.debug('Could not play sound:', error);
    }
  }

  function showDesktopNotification(alert: Alert) {
    if (!('Notification' in window)) return;
    if (Notification.permission === 'granted') {
      new Notification(`🔔 NEXUS Alert: ${alert.name}`, {
        body: `${alert.symbol} ${alert.condition} ${formatCurrency(alert.value)}\nPriority: ${alert.priority.toUpperCase()}`,
        icon: '/icons/logo-192x192.png',
        tag: alert.id,
        requireInteraction: alert.priority === 'critical',
        silent: true,
      });
    } else if (Notification.permission === 'default') {
      Notification.requestPermission();
    }
  }

  // ============================================
  // API Calls - Real Data
  // ============================================
  const fetchAlerts = useCallback(async () => {
    setAlertsLoading(true);
    
    try {
      const response = await api.get('/alerts', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          limit: 100,
          type: filterType !== 'all' ? filterType : undefined,
          priority: filterPriority !== 'all' ? filterPriority : undefined,
          symbol: filterSymbol !== 'all' ? filterSymbol : undefined,
          search: searchQuery || undefined,
          includeDisabled: true,
        },
      });
      
      if (response.data && response.data.alerts) {
        const parsedAlerts = response.data.alerts.map((a: any) => ({
          ...a,
          createdAt: new Date(a.createdAt || Date.now()),
          updatedAt: new Date(a.updatedAt || Date.now()),
          lastTriggered: a.lastTriggered ? new Date(a.lastTriggered) : undefined,
        }));
        setAlerts(parsedAlerts);
        setActiveAlerts(parsedAlerts.filter(a => a.enabled && a.status !== 'triggered'));
        setTriggeredAlerts(parsedAlerts.filter(a => a.status === 'triggered' || (a.lastTriggered && !a.acknowledged)));
      }
    } catch (error) {
      console.error('Failed to fetch alerts:', error);
      setShowToast({
        message: 'Failed to load alerts. Please refresh the page.',
        type: 'error',
      });
    } finally {
      setAlertsLoading(false);
    }
  }, [api, accessToken, filterType, filterPriority, filterSymbol, searchQuery]);

  const fetchAlertHistory = useCallback(async () => {
    try {
      const response = await api.get('/alerts/history', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          limit: 100,
          days: 7,
        },
      });
      
      if (response.data && response.data.history) {
        setAlertHistory(response.data.history.map((h: any) => ({
          ...h,
          timestamp: new Date(h.timestamp || Date.now()),
          triggeredAt: new Date(h.triggeredAt || Date.now()),
          acknowledgedAt: h.acknowledgedAt ? new Date(h.acknowledgedAt) : undefined,
        })));
      }
    } catch (error) {
      console.error('Failed to fetch alert history:', error);
    }
  }, [api, accessToken]);

  const fetchAlertStats = useCallback(async () => {
    try {
      const response = await api.get('/alerts/stats', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          days: 7,
        },
      });
      
      if (response.data) {
        setAlertStats(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch alert stats:', error);
    }
  }, [api, accessToken]);

  const fetchSettings = useCallback(async () => {
    setSettingsLoading(true);
    
    try {
      const response = await api.get('/alerts/settings', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      if (response.data) {
        setSettings(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch alert settings:', error);
    } finally {
      setSettingsLoading(false);
    }
  }, [api, accessToken]);

  const fetchAllData = useCallback(async () => {
    setIsLoading(true);
    try {
      await Promise.all([
        fetchAlerts(),
        fetchAlertHistory(),
        fetchAlertStats(),
        fetchSettings(),
      ]);
    } catch (error) {
      console.error('Failed to fetch all data:', error);
    } finally {
      setIsLoading(false);
    }
  }, [fetchAlerts, fetchAlertHistory, fetchAlertStats, fetchSettings]);

  // ============================================
  // API Actions
  // ============================================
  const handleCreateAlert = useCallback(async () => {
    if (!newAlert.name || !newAlert.symbol || !newAlert.value) {
      setShowToast({
        message: 'Please fill in all required fields',
        type: 'warning',
      });
      return;
    }

    setIsCreating(true);
    
    try {
      const response = await api.post('/alerts', newAlert, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      if (response.data) {
        handleAlertCreated(response.data);
        setShowCreateModal(false);
        setNewAlert({
          name: '',
          type: 'price',
          symbol: 'BTC-USD',
          condition: 'above',
          value: 0,
          priority: 'medium',
          timeframe: '1h',
          enabled: true,
          notificationChannels: ['push', 'email'],
          cooldown: 300,
          triggerCount: 1,
          duration: 0,
        });
        fetchAlerts();
      }
    } catch (error: any) {
      console.error('Failed to create alert:', error);
      setShowToast({
        message: error.response?.data?.message || 'Failed to create alert. Please try again.',
        type: 'error',
      });
    } finally {
      setIsCreating(false);
    }
  }, [api, accessToken, newAlert, fetchAlerts]);

  const handleUpdateAlert = useCallback(async (alertId: string, updates: Partial<Alert>) => {
    try {
      const response = await api.put(`/alerts/${alertId}`, updates, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      if (response.data) {
        handleAlertUpdated(response.data);
        fetchAlerts();
      }
    } catch (error: any) {
      console.error('Failed to update alert:', error);
      setShowToast({
        message: error.response?.data?.message || 'Failed to update alert. Please try again.',
        type: 'error',
      });
    }
  }, [api, accessToken, fetchAlerts]);

  const handleDeleteAlert = useCallback(async (alertId: string) => {
    if (!confirm('Are you sure you want to delete this alert?')) return;
    
    setIsDeleting(true);
    
    try {
      await api.delete(`/alerts/${alertId}`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      handleAlertDeleted({ id: alertId });
      fetchAlerts();
    } catch (error: any) {
      console.error('Failed to delete alert:', error);
      setShowToast({
        message: error.response?.data?.message || 'Failed to delete alert. Please try again.',
        type: 'error',
      });
    } finally {
      setIsDeleting(false);
    }
  }, [api, accessToken, fetchAlerts]);

  const handleBulkDelete = useCallback(async () => {
    if (selectedAlerts.length === 0) return;
    if (!confirm(`Delete ${selectedAlerts.length} alerts?`)) return;
    
    setIsBulkDeleting(true);
    
    try {
      await api.post('/alerts/bulk/delete', { ids: selectedAlerts }, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      handleAlertBulkUpdate({ ids: selectedAlerts, action: 'delete' });
      fetchAlerts();
    } catch (error: any) {
      console.error('Failed to bulk delete alerts:', error);
      setShowToast({
        message: error.response?.data?.message || 'Failed to delete alerts. Please try again.',
        type: 'error',
      });
    } finally {
      setIsBulkDeleting(false);
    }
  }, [api, accessToken, selectedAlerts, fetchAlerts]);

  const handleBulkDisable = useCallback(async () => {
    if (selectedAlerts.length === 0) return;
    
    setIsBulkDisabling(true);
    
    try {
      await api.post('/alerts/bulk/disable', { ids: selectedAlerts }, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      handleAlertBulkUpdate({ ids: selectedAlerts, action: 'disable' });
      fetchAlerts();
    } catch (error: any) {
      console.error('Failed to disable alerts:', error);
      setShowToast({
        message: error.response?.data?.message || 'Failed to disable alerts. Please try again.',
        type: 'error',
      });
    } finally {
      setIsBulkDisabling(false);
    }
  }, [api, accessToken, selectedAlerts, fetchAlerts]);

  const handleAcknowledgeAlert = useCallback(async (alertId: string) => {
    try {
      await api.post(`/alerts/${alertId}/acknowledge`, {}, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      setTriggeredAlerts(prev => prev.filter(a => a.id !== alertId));
      setAlerts(prev => 
        prev.map(a => 
          a.id === alertId ? { ...a, status: 'acknowledged', acknowledged: true } : a
        )
      );
      
      setShowToast({
        message: 'Alert acknowledged',
        type: 'success',
      });
    } catch (error: any) {
      console.error('Failed to acknowledge alert:', error);
      setShowToast({
        message: 'Failed to acknowledge alert. Please try again.',
        type: 'error',
      });
    }
  }, [api, accessToken]);

  const handleUpdateSettings = useCallback(async (updates: Partial<AlertSettings>) => {
    try {
      const response = await api.put('/alerts/settings', updates, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      if (response.data) {
        setSettings(response.data);
        setShowToast({
          message: 'Settings updated successfully',
          type: 'success',
        });
      }
    } catch (error: any) {
      console.error('Failed to update settings:', error);
      setShowToast({
        message: error.response?.data?.message || 'Failed to update settings.',
        type: 'error',
      });
    }
  }, [api, accessToken]);

  // ============================================
  // Effects
  // ============================================
  useEffect(() => {
    fetchAllData();
    
    // Request notification permission
    if ('Notification' in window && Notification.permission === 'default') {
      Notification.requestPermission();
    }
    
    return () => {
      if (wsCleanupRef.current) {
        wsCleanupRef.current();
      }
      if (alertPollIntervalRef.current) {
        clearInterval(alertPollIntervalRef.current);
      }
    };
  }, [fetchAllData]);

  useEffect(() => {
    if (isConnected) {
      subscribeToChannels();
    }
  }, [isConnected]);

  // Auto-refresh alerts
  useEffect(() => {
    if (alertPollIntervalRef.current) {
      clearInterval(alertPollIntervalRef.current);
    }
    
    alertPollIntervalRef.current = setInterval(() => {
      fetchAlerts();
      fetchAlertStats();
    }, 30000); // Refresh every 30 seconds
    
    return () => {
      if (alertPollIntervalRef.current) {
        clearInterval(alertPollIntervalRef.current);
      }
    };
  }, [fetchAlerts, fetchAlertStats]);

  // ============================================
  // Memoized Computations
  // ============================================
  const filteredAlerts = useMemo(() => {
    let result = alerts;
    
    if (filterType !== 'all') {
      result = result.filter(a => a.type === filterType);
    }
    
    if (filterPriority !== 'all') {
      result = result.filter(a => a.priority === filterPriority);
    }
    
    if (filterSymbol !== 'all') {
      result = result.filter(a => a.symbol === filterSymbol);
    }
    
    if (searchQuery) {
      const query = searchQuery.toLowerCase();
      result = result.filter(a => 
        a.name.toLowerCase().includes(query) ||
        a.symbol.toLowerCase().includes(query) ||
        a.condition.toLowerCase().includes(query)
      );
    }
    
    return result;
  }, [alerts, filterType, filterPriority, filterSymbol, searchQuery]);

  const filteredHistory = useMemo(() => {
    let result = alertHistory;
    
    if (filterType !== 'all') {
      result = result.filter(h => h.type === filterType);
    }
    
    if (filterSymbol !== 'all') {
      result = result.filter(h => h.symbol === filterSymbol);
    }
    
    return result.slice(0, 50);
  }, [alertHistory, filterType, filterSymbol]);

  const alertCounts = useMemo(() => {
    return {
      total: alerts.length,
      active: alerts.filter(a => a.enabled && a.status !== 'triggered').length,
      triggered: alerts.filter(a => a.status === 'triggered' || (a.lastTriggered && !a.acknowledged)).length,
      disabled: alerts.filter(a => !a.enabled).length,
      highPriority: alerts.filter(a => a.priority === 'high' || a.priority === 'critical').length,
    };
  }, [alerts]);

  // ============================================
  // Render
  // ============================================
  if (isLoading && alertsLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-6">
            <div className="absolute inset-0 border-4 border-cyan-500/30 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-t-cyan-500 rounded-full animate-spin"></div>
            <div className="absolute inset-2 bg-cyan-500/10 rounded-full animate-pulse"></div>
          </div>
          <p className="text-gray-400 text-lg font-medium">Loading Alerts...</p>
          <p className="text-gray-500 text-sm mt-2">Connecting to alert services</p>
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
            <div className="text-3xl">🔔</div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-yellow-400 to-orange-400 bg-clip-text text-transparent">
                Alert Management
              </h1>
              <p className="text-gray-400 text-sm mt-1">
                Real-time alerts and notifications for your trading strategy
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
          
          {/* Create Alert Button */}
          <Button
            onClick={() => setShowCreateModal(true)}
            className="bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-600 hover:to-orange-600 text-white transition-all"
          >
            <span className="mr-2">➕</span> Create Alert
          </Button>
        </div>
      </div>

      {/* ============================================ */}
      {/* STATISTICS CARDS */}
      {/* ============================================ */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4 mb-6">
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="text-2xl font-bold text-white">{alertCounts.total}</div>
          <div className="text-xs text-gray-400">Total Alerts</div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="text-2xl font-bold text-green-500">{alertCounts.active}</div>
          <div className="text-xs text-gray-400">Active</div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="text-2xl font-bold text-orange-500">{alertCounts.triggered}</div>
          <div className="text-xs text-gray-400">Triggered</div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="text-2xl font-bold text-gray-500">{alertCounts.disabled}</div>
          <div className="text-xs text-gray-400">Disabled</div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="text-2xl font-bold text-red-500">{alertCounts.highPriority}</div>
          <div className="text-xs text-gray-400">High Priority</div>
        </Card>
        <Card className="p-4 bg-gray-800 border-gray-700">
          <div className="text-2xl font-bold text-cyan-400">
            {alertStats?.triggeredToday || 0}
          </div>
          <div className="text-xs text-gray-400">Today</div>
        </Card>
      </div>

      {/* ============================================ */}
      {/* MAIN CONTENT */}
      {/* ============================================ */}
      <div className="grid grid-cols-12 gap-6">
        {/* ========================================== */}
        {/* LEFT COLUMN - Alert List */}
        {/* ========================================== */}
        <div className="col-span-12 lg:col-span-8 space-y-6">
          {/* Filters and Search */}
          <div className="flex flex-wrap items-center gap-3 bg-gray-800/50 rounded-lg p-3 border border-gray-700">
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400">Type:</span>
              <Select
                value={filterType}
                onValueChange={setFilterType}
                className="w-28 bg-gray-700 border-gray-600 text-sm"
              >
                <option value="all">All Types</option>
                {ALERT_TYPES.map(type => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400">Priority:</span>
              <Select
                value={filterPriority}
                onValueChange={setFilterPriority}
                className="w-28 bg-gray-700 border-gray-600 text-sm"
              >
                <option value="all">All</option>
                {ALERT_PRIORITIES.map(priority => (
                  <option key={priority.value} value={priority.value}>
                    {priority.label}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-400">Symbol:</span>
              <Select
                value={filterSymbol}
                onValueChange={setFilterSymbol}
                className="w-32 bg-gray-700 border-gray-600 text-sm"
              >
                <option value="all">All Symbols</option>
                {SUPPORTED_SYMBOLS.map(sym => (
                  <option key={sym.value} value={sym.value}>
                    {sym.label}
                  </option>
                ))}
              </Select>
            </div>
            <div className="flex-1 min-w-[150px]">
              <Input
                type="text"
                placeholder="Search alerts..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full bg-gray-700 border-gray-600 text-white text-sm"
              />
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={fetchAlerts}
              className="text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10"
            >
              🔄 Refresh
            </Button>
          </div>

          {/* Bulk Actions */}
          {selectedAlerts.length > 0 && (
            <div className="flex items-center gap-3 bg-gray-800 rounded-lg p-3 border border-yellow-500/30">
              <span className="text-sm text-yellow-400">
                {selectedAlerts.length} selected
              </span>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setSelectedAlerts([])}
                className="border-gray-600 hover:border-gray-500"
              >
                Clear
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleBulkDisable}
                isLoading={isBulkDisabling}
                className="border-yellow-500/50 hover:border-yellow-500 text-yellow-400"
              >
                ⏸️ Disable
              </Button>
              <Button
                variant="destructive"
                size="sm"
                onClick={handleBulkDelete}
                isLoading={isBulkDeleting}
                className="bg-red-600 hover:bg-red-700"
              >
                🗑️ Delete
              </Button>
            </div>
          )}

          {/* Alerts Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="bg-gray-800 border border-gray-700 rounded-lg p-1 w-full">
              <TabsTrigger
                value="active"
                className="flex-1 data-[state=active]:bg-green-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
              >
                <span className="mr-2">🟢</span> Active ({alertCounts.active})
              </TabsTrigger>
              <TabsTrigger
                value="triggered"
                className="flex-1 data-[state=active]:bg-orange-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
              >
                <span className="mr-2">🔴</span> Triggered ({alertCounts.triggered})
              </TabsTrigger>
              <TabsTrigger
                value="all"
                className="flex-1 data-[state=active]:bg-gray-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
              >
                <span className="mr-2">📋</span> All ({alertCounts.total})
              </TabsTrigger>
              <TabsTrigger
                value="disabled"
                className="flex-1 data-[state=active]:bg-gray-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
              >
                <span className="mr-2">⏸️</span> Disabled ({alertCounts.disabled})
              </TabsTrigger>
            </TabsList>

            <TabsContent value="active" className="mt-4 space-y-3">
              {alertsLoading ? (
                <div className="text-center py-8">
                  <Spinner size="lg" className="mx-auto mb-4 text-cyan-500" />
                  <p className="text-gray-400">Loading alerts...</p>
                </div>
              ) : filteredAlerts.filter(a => a.enabled && a.status !== 'triggered').length > 0 ? (
                <AnimatePresence>
                  {filteredAlerts
                    .filter(a => a.enabled && a.status !== 'triggered')
                    .map((alert) => (
                      <motion.div
                        key={alert.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                      >
                        <AlertCard
                          alert={alert}
                          selected={selectedAlerts.includes(alert.id)}
                          onSelect={(id) => {
                            setSelectedAlerts(prev =>
                              prev.includes(id)
                                ? prev.filter(a => a !== id)
                                : [...prev, id]
                            );
                          }}
                          onEdit={(alert) => {
                            setEditingAlert(alert);
                            setShowCreateModal(true);
                          }}
                          onDelete={handleDeleteAlert}
                          onToggle={(alertId, enabled) => {
                            handleUpdateAlert(alertId, { enabled });
                          }}
                          onAcknowledge={handleAcknowledgeAlert}
                        />
                      </motion.div>
                    ))}
                </AnimatePresence>
              ) : (
                <div className="text-center py-12 text-gray-500">
                  <div className="text-4xl mb-3">✅</div>
                  <p>No active alerts</p>
                  <p className="text-sm">Create a new alert to start monitoring</p>
                </div>
              )}
            </TabsContent>

            <TabsContent value="triggered" className="mt-4 space-y-3">
              {filteredAlerts.filter(a => a.status === 'triggered' || (a.lastTriggered && !a.acknowledged)).length > 0 ? (
                <AnimatePresence>
                  {filteredAlerts
                    .filter(a => a.status === 'triggered' || (a.lastTriggered && !a.acknowledged))
                    .sort((a, b) => (b.lastTriggered?.getTime() || 0) - (a.lastTriggered?.getTime() || 0))
                    .map((alert) => (
                      <motion.div
                        key={alert.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                      >
                        <AlertCard
                          alert={alert}
                          isTriggered
                          selected={selectedAlerts.includes(alert.id)}
                          onSelect={(id) => {
                            setSelectedAlerts(prev =>
                              prev.includes(id)
                                ? prev.filter(a => a !== id)
                                : [...prev, id]
                            );
                          }}
                          onEdit={(alert) => {
                            setEditingAlert(alert);
                            setShowCreateModal(true);
                          }}
                          onDelete={handleDeleteAlert}
                          onToggle={(alertId, enabled) => {
                            handleUpdateAlert(alertId, { enabled });
                          }}
                          onAcknowledge={handleAcknowledgeAlert}
                        />
                      </motion.div>
                    ))}
                </AnimatePresence>
              ) : (
                <div className="text-center py-12 text-gray-500">
                  <div className="text-4xl mb-3">🎉</div>
                  <p>No triggered alerts</p>
                  <p className="text-sm">All systems quiet</p>
                </div>
              )}
            </TabsContent>

            <TabsContent value="all" className="mt-4 space-y-3">
              {filteredAlerts.length > 0 ? (
                <AnimatePresence>
                  {filteredAlerts.map((alert) => (
                    <motion.div
                      key={alert.id}
                      initial={{ opacity: 0, y: 10 }}
                      animate={{ opacity: 1, y: 0 }}
                      exit={{ opacity: 0, y: -10 }}
                    >
                      <AlertCard
                        alert={alert}
                        selected={selectedAlerts.includes(alert.id)}
                        onSelect={(id) => {
                          setSelectedAlerts(prev =>
                            prev.includes(id)
                              ? prev.filter(a => a !== id)
                              : [...prev, id]
                          );
                        }}
                        onEdit={(alert) => {
                          setEditingAlert(alert);
                          setShowCreateModal(true);
                        }}
                        onDelete={handleDeleteAlert}
                        onToggle={(alertId, enabled) => {
                          handleUpdateAlert(alertId, { enabled });
                        }}
                        onAcknowledge={handleAcknowledgeAlert}
                      />
                    </motion.div>
                  ))}
                </AnimatePresence>
              ) : (
                <div className="text-center py-12 text-gray-500">
                  <div className="text-4xl mb-3">📭</div>
                  <p>No alerts found</p>
                  <p className="text-sm">Create your first alert to get started</p>
                </div>
              )}
            </TabsContent>

            <TabsContent value="disabled" className="mt-4 space-y-3">
              {filteredAlerts.filter(a => !a.enabled).length > 0 ? (
                <AnimatePresence>
                  {filteredAlerts
                    .filter(a => !a.enabled)
                    .map((alert) => (
                      <motion.div
                        key={alert.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -10 }}
                      >
                        <AlertCard
                          alert={alert}
                          isDisabled
                          selected={selectedAlerts.includes(alert.id)}
                          onSelect={(id) => {
                            setSelectedAlerts(prev =>
                              prev.includes(id)
                                ? prev.filter(a => a !== id)
                                : [...prev, id]
                            );
                          }}
                          onEdit={(alert) => {
                            setEditingAlert(alert);
                            setShowCreateModal(true);
                          }}
                          onDelete={handleDeleteAlert}
                          onToggle={(alertId, enabled) => {
                            handleUpdateAlert(alertId, { enabled });
                          }}
                          onAcknowledge={handleAcknowledgeAlert}
                        />
                      </motion.div>
                    ))}
                </AnimatePresence>
              ) : (
                <div className="text-center py-12 text-gray-500">
                  <div className="text-4xl mb-3">⏸️</div>
                  <p>No disabled alerts</p>
                  <p className="text-sm">All alerts are currently enabled</p>
                </div>
              )}
            </TabsContent>
          </Tabs>
        </div>

        {/* ========================================== */}
        {/* RIGHT COLUMN - History & Settings */}
        {/* ========================================== */}
        <div className="col-span-12 lg:col-span-4 space-y-6">
          {/* Recent History */}
          <Card className="p-4 bg-gray-800 border-gray-700">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-sm font-semibold text-gray-300 flex items-center gap-2">
                <span className="text-blue-400">📜</span> Recent History
              </h3>
              <Button
                variant="ghost"
                size="sm"
                onClick={fetchAlertHistory}
                className="text-xs text-gray-500 hover:text-white"
              >
                Refresh
              </Button>
            </div>
            <div className="space-y-2 max-h-[400px] overflow-y-auto">
              {filteredHistory.length > 0 ? (
                filteredHistory.map((history) => (
                  <div
                    key={history.id}
                    className="flex items-center justify-between p-2 bg-gray-700/30 rounded-lg text-sm hover:bg-gray-700/50 transition-colors"
                  >
                    <div>
                      <div className="text-white text-xs font-medium">{history.alertName}</div>
                      <div className="text-gray-400 text-xs">
                        {history.symbol} {history.condition} {formatCurrency(history.value)}
                      </div>
                    </div>
                    <div className="text-right">
                      <div className="text-xs text-gray-500">
                        {formatTime(history.triggeredAt)}
                      </div>
                      <div className={cn(
                        'text-xs',
                        history.triggeredValue >= history.value ? 'text-green-500' : 'text-red-500'
                      )}>
                        {formatCurrency(history.triggeredValue)}
                      </div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="text-center py-8 text-gray-500 text-sm">
                  <div className="text-3xl mb-2">📭</div>
                  <p>No alert history</p>
                </div>
              )}
            </div>
          </Card>

          {/* Alert Settings */}
          <Card className="p-4 bg-gray-800 border-gray-700">
            <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
              <span className="text-purple-400">⚙️</span> Notification Settings
            </h3>
            
            {settingsLoading ? (
              <div className="text-center py-4">
                <Spinner size="sm" className="mx-auto mb-2" />
                <p className="text-sm text-gray-500">Loading settings...</p>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400">Email Notifications</span>
                  <Switch
                    checked={settings.emailNotifications}
                    onCheckedChange={(checked) => handleUpdateSettings({ emailNotifications: checked })}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400">Push Notifications</span>
                  <Switch
                    checked={settings.pushNotifications}
                    onCheckedChange={(checked) => handleUpdateSettings({ pushNotifications: checked })}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400">Sound Notifications</span>
                  <Switch
                    checked={settings.soundNotifications}
                    onCheckedChange={(checked) => handleUpdateSettings({ soundNotifications: checked })}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400">Desktop Notifications</span>
                  <Switch
                    checked={settings.desktopNotifications}
                    onCheckedChange={(checked) => handleUpdateSettings({ desktopNotifications: checked })}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400">Telegram</span>
                  <Switch
                    checked={settings.telegramNotifications}
                    onCheckedChange={(checked) => handleUpdateSettings({ telegramNotifications: checked })}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400">Slack</span>
                  <Switch
                    checked={settings.slackNotifications}
                    onCheckedChange={(checked) => handleUpdateSettings({ slackNotifications: checked })}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm text-gray-400">Discord</span>
                  <Switch
                    checked={settings.discordNotifications}
                    onCheckedChange={(checked) => handleUpdateSettings({ discordNotifications: checked })}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                </div>
                <div className="pt-3 border-t border-gray-700">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-gray-400">Min Priority</span>
                    <Select
                      value={settings.minPriority}
                      onValueChange={(value) => handleUpdateSettings({ minPriority: value })}
                      className="w-28 bg-gray-700 border-gray-600 text-sm"
                    >
                      {ALERT_PRIORITIES.map(priority => (
                        <option key={priority.value} value={priority.value}>
                          {priority.label}
                        </option>
                      ))}
                    </Select>
                  </div>
                </div>
              </div>
            )}
          </Card>

          {/* Quick Stats */}
          {alertStats && (
            <Card className="p-4 bg-gray-800 border-gray-700">
              <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                <span className="text-green-400">📊</span> Alert Statistics
              </h3>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <div className="text-gray-400">This Week</div>
                  <div className="text-xl font-bold text-white">
                    {alertStats.triggeredThisWeek || 0}
                  </div>
                </div>
                <div>
                  <div className="text-gray-400">This Month</div>
                  <div className="text-xl font-bold text-white">
                    {alertStats.triggeredThisMonth || 0}
                  </div>
                </div>
                <div>
                  <div className="text-gray-400">Success Rate</div>
                  <div className="text-xl font-bold text-green-500">
                    {formatPercentage(alertStats.successRate || 0)}
                  </div>
                </div>
                <div>
                  <div className="text-gray-400">Avg Response</div>
                  <div className="text-xl font-bold text-cyan-400">
                    {alertStats.averageResponseTime || 0}s
                  </div>
                </div>
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* ============================================ */}
      {/* CREATE/EDIT ALERT MODAL */}
      {/* ============================================ */}
      <Modal
        open={showCreateModal}
        onOpenChange={setShowCreateModal}
        title={editingAlert ? 'Edit Alert' : 'Create New Alert'}
        className="max-w-2xl"
      >
        <div className="space-y-4">
          <div>
            <label className="text-sm text-gray-400 block mb-1">Alert Name *</label>
            <Input
              value={newAlert.name || ''}
              onChange={(e) => setNewAlert({ ...newAlert, name: e.target.value })}
              placeholder="e.g., BTC Price Alert"
              className="w-full bg-gray-700 border-gray-600 text-white"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-gray-400 block mb-1">Type *</label>
              <Select
                value={newAlert.type}
                onValueChange={(value) => setNewAlert({ ...newAlert, type: value as AlertType })}
                className="w-full bg-gray-700 border-gray-600"
              >
                {ALERT_TYPES.map(type => (
                  <option key={type.value} value={type.value}>
                    {type.label}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <label className="text-sm text-gray-400 block mb-1">Symbol *</label>
              <Select
                value={newAlert.symbol}
                onValueChange={(value) => setNewAlert({ ...newAlert, symbol: value })}
                className="w-full bg-gray-700 border-gray-600"
              >
                {SUPPORTED_SYMBOLS.map(sym => (
                  <option key={sym.value} value={sym.value}>
                    {sym.label}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="text-sm text-gray-400 block mb-1">Condition</label>
              <Select
                value={newAlert.condition}
                onValueChange={(value) => setNewAlert({ ...newAlert, condition: value as AlertCondition })}
                className="w-full bg-gray-700 border-gray-600"
              >
                {ALERT_CONDITIONS.map(cond => (
                  <option key={cond.value} value={cond.value}>
                    {cond.label}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <label className="text-sm text-gray-400 block mb-1">Value *</label>
              <Input
                type="number"
                value={newAlert.value || ''}
                onChange={(e) => setNewAlert({ ...newAlert, value: parseFloat(e.target.value) || 0 })}
                className="w-full bg-gray-700 border-gray-600 text-white"
                placeholder="0.00"
                step="0.01"
              />
            </div>
            <div>
              <label className="text-sm text-gray-400 block mb-1">Priority</label>
              <Select
                value={newAlert.priority}
                onValueChange={(value) => setNewAlert({ ...newAlert, priority: value })}
                className="w-full bg-gray-700 border-gray-600"
              >
                {ALERT_PRIORITIES.map(priority => (
                  <option key={priority.value} value={priority.value}>
                    {priority.label}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="text-sm text-gray-400 block mb-1">Timeframe</label>
              <Select
                value={newAlert.timeframe}
                onValueChange={(value) => setNewAlert({ ...newAlert, timeframe: value })}
                className="w-full bg-gray-700 border-gray-600"
              >
                {TIME_FRAMES.map(tf => (
                  <option key={tf.value} value={tf.value}>
                    {tf.label}
                  </option>
                ))}
              </Select>
            </div>
            <div>
              <label className="text-sm text-gray-400 block mb-1">Cooldown (seconds)</label>
              <Input
                type="number"
                value={newAlert.cooldown || ''}
                onChange={(e) => setNewAlert({ ...newAlert, cooldown: parseInt(e.target.value) || 300 })}
                className="w-full bg-gray-700 border-gray-600 text-white"
                min={0}
                max={3600}
              />
            </div>
          </div>

          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <Switch
                checked={newAlert.enabled}
                onCheckedChange={(checked) => setNewAlert({ ...newAlert, enabled: checked })}
                className="data-[state=checked]:bg-cyan-500"
              />
              <span className="text-sm text-gray-400">Enabled</span>
            </div>
            <div>
              <label className="text-sm text-gray-400 block mb-1">Trigger Count</label>
              <Input
                type="number"
                value={newAlert.triggerCount || ''}
                onChange={(e) => setNewAlert({ ...newAlert, triggerCount: parseInt(e.target.value) || 1 })}
                className="w-24 bg-gray-700 border-gray-600 text-white"
                min={1}
                max={10}
              />
            </div>
          </div>

          <div className="pt-4 border-t border-gray-700">
            <label className="text-sm text-gray-400 block mb-2">Notification Channels</label>
            <div className="flex flex-wrap gap-3">
              {['push', 'email', 'telegram', 'slack', 'discord'].map((channel) => (
                <div key={channel} className="flex items-center gap-1">
                  <input
                    type="checkbox"
                    checked={newAlert.notificationChannels?.includes(channel)}
                    onChange={(e) => {
                      const checked = e.target.checked;
                      setNewAlert({
                        ...newAlert,
                        notificationChannels: checked
                          ? [...(newAlert.notificationChannels || []), channel]
                          : (newAlert.notificationChannels || []).filter(c => c !== channel),
                      });
                    }}
                    className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-cyan-500 focus:ring-cyan-500"
                  />
                  <span className="text-sm text-gray-400 capitalize">{channel}</span>
                </div>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-3 pt-4">
            <Button
              variant="outline"
              onClick={() => {
                setShowCreateModal(false);
                setEditingAlert(null);
                setNewAlert({
                  name: '',
                  type: 'price',
                  symbol: 'BTC-USD',
                  condition: 'above',
                  value: 0,
                  priority: 'medium',
                  timeframe: '1h',
                  enabled: true,
                  notificationChannels: ['push', 'email'],
                  cooldown: 300,
                  triggerCount: 1,
                  duration: 0,
                });
              }}
              className="border-gray-600 hover:border-gray-500"
            >
              Cancel
            </Button>
            <Button
              onClick={handleCreateAlert}
              isLoading={isCreating}
              className="bg-gradient-to-r from-yellow-500 to-orange-500 hover:from-yellow-600 hover:to-orange-600"
            >
              {editingAlert ? 'Update Alert' : 'Create Alert'}
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

// ============================================
// ALERT CARD COMPONENT
// ============================================
interface AlertCardProps {
  alert: Alert;
  selected?: boolean;
  isTriggered?: boolean;
  isDisabled?: boolean;
  onSelect?: (id: string) => void;
  onEdit?: (alert: Alert) => void;
  onDelete?: (id: string) => void;
  onToggle?: (id: string, enabled: boolean) => void;
  onAcknowledge?: (id: string) => void;
}

function AlertCard({
  alert,
  selected,
  isTriggered,
  isDisabled,
  onSelect,
  onEdit,
  onDelete,
  onToggle,
  onAcknowledge,
}: AlertCardProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [isToggling, setIsToggling] = useState(false);

  const priorityColors = {
    low: 'bg-blue-500/20 text-blue-500 border-blue-500/30',
    medium: 'bg-yellow-500/20 text-yellow-500 border-yellow-500/30',
    high: 'bg-orange-500/20 text-orange-500 border-orange-500/30',
    critical: 'bg-red-500/20 text-red-500 border-red-500/30',
  };

  const typeIcons = {
    price: '💰',
    ai_signal: '🤖',
    technical: '📊',
    volatility: '📈',
    volume: '📊',
    custom: '⚙️',
  };

  const handleDelete = async () => {
    if (!confirm(`Delete alert "${alert.name}"?`)) return;
    setIsDeleting(true);
    try {
      await onDelete?.(alert.id);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleToggle = async () => {
    setIsToggling(true);
    try {
      await onToggle?.(alert.id, !alert.enabled);
    } finally {
      setIsToggling(false);
    }
  };

  return (
    <Card className={cn(
      'p-4 bg-gray-800 border-gray-700 hover:border-gray-600 transition-all',
      selected && 'border-cyan-500 bg-cyan-500/5',
      isTriggered && 'border-orange-500/50 bg-orange-500/5',
      isDisabled && 'opacity-60'
    )}>
      <div className="flex items-start gap-4">
        {/* Checkbox */}
        <div className="mt-1">
          <input
            type="checkbox"
            checked={selected}
            onChange={() => onSelect?.(alert.id)}
            className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-cyan-500 focus:ring-cyan-500"
          />
        </div>

        {/* Icon */}
        <div className="text-2xl">{typeIcons[alert.type] || '🔔'}</div>

        {/* Content */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-3 flex-wrap">
            <h4 className="text-white font-medium">{alert.name}</h4>
            <Badge className={cn('text-xs border', priorityColors[alert.priority])}>
              {alert.priority.toUpperCase()}
            </Badge>
            {isTriggered && (
              <Badge className="text-xs border-orange-500/50 bg-orange-500/20 text-orange-500 animate-pulse">
                🔴 TRIGGERED
              </Badge>
            )}
            {isDisabled && (
              <Badge className="text-xs border-gray-500/50 bg-gray-500/20 text-gray-500">
                ⏸️ DISABLED
              </Badge>
            )}
          </div>

          <div className="text-sm text-gray-400 mt-1">
            {alert.symbol} {alert.condition} {formatCurrency(alert.value)}
            {alert.timeframe && ` • ${TIME_FRAMES.find(t => t.value === alert.timeframe)?.label || alert.timeframe}`}
            {alert.duration > 0 && ` • Duration: ${alert.duration}s`}
          </div>

          <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
            <span>Created: {formatTime(alert.createdAt)}</span>
            {alert.lastTriggered && (
              <span className="text-orange-400">
                Last triggered: {formatTime(alert.lastTriggered)}
              </span>
            )}
            <span>Channels: {alert.notificationChannels?.join(', ') || 'None'}</span>
          </div>
        </div>

        {/* Actions */}
        <div className="flex items-center gap-2">
          {isTriggered && onAcknowledge && (
            <Button
              variant="primary"
              size="sm"
              onClick={() => onAcknowledge(alert.id)}
              className="bg-green-600 hover:bg-green-700 text-xs"
            >
              ✅ Acknowledge
            </Button>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={handleToggle}
            isLoading={isToggling}
            className="text-gray-400 hover:text-white"
          >
            {alert.enabled ? '⏸️' : '▶️'}
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => onEdit?.(alert)}
            className="text-gray-400 hover:text-white"
          >
            ✏️
          </Button>
          <Button
            variant="ghost"
            size="sm"
            onClick={handleDelete}
            isLoading={isDeleting}
            className="text-gray-400 hover:text-red-500"
          >
            🗑️
          </Button>
        </div>
      </div>
    </Card>
  );
}

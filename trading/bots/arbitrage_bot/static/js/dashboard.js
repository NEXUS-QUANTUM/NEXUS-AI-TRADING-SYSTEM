/**
 * NEXUS AI TRADING SYSTEM - Arbitrage Bot Dashboard Module
 * Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
 * @version 2.0.0
 * @author NEXUS QUANTUM TEAM
 */

// ============================================================
// CORE DASHBOARD CONTROLLER
// ============================================================

class ArbitrageDashboard {
    constructor() {
        // State management
        this.state = {
            isConnected: false,
            isRunning: false,
            lastUpdate: null,
            metrics: {},
            opportunities: [],
            executions: [],
            pnl: {},
            spreads: {},
            volumes: {},
            matrix: {},
            alerts: [],
            config: {},
            performance: {},
        };

        // DOM references
        this.elements = {};
        this.charts = null;
        this.websocket = null;
        this.updateInterval = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 3000;

        // Event listeners
        this.listeners = new Map();

        // Initialize
        this.initialize();
    }

    // ============================================================
    // INITIALIZATION
    // ============================================================

    initialize() {
        console.log('🚀 Initializing Arbitrage Dashboard...');
        this.cacheDOMReferences();
        this.setupEventListeners();
        this.loadConfig();
        this.connectWebSocket();
        this.startAutoRefresh();
        this.updateUI();
        console.log('✅ Arbitrage Dashboard initialized successfully');
    }

    cacheDOMReferences() {
        // Main containers
        this.elements.container = document.getElementById('dashboard-container');
        this.elements.mainContent = document.getElementById('main-content');
        this.elements.sidebar = document.getElementById('sidebar');

        // Status indicators
        this.elements.statusIndicator = document.getElementById('status-indicator');
        this.elements.connectionStatus = document.getElementById('connection-status');
        this.elements.botStatus = document.getElementById('bot-status');
        this.elements.lastUpdate = document.getElementById('last-update');

        // Metrics cards
        this.elements.metricsGrid = document.getElementById('metrics-grid');
        this.elements.totalPnL = document.getElementById('total-pnl');
        this.elements.totalTrades = document.getElementById('total-trades');
        this.elements.winRate = document.getElementById('win-rate');
        this.elements.avgProfit = document.getElementById('avg-profit');
        this.elements.bestTrade = document.getElementById('best-trade');
        this.elements.worstTrade = document.getElementById('worst-trade');
        this.elements.sharpeRatio = document.getElementById('sharpe-ratio');
        this.elements.maxDrawdown = document.getElementById('max-drawdown');

        // Chart containers
        this.elements.opportunityChart = document.getElementById('opportunity-chart');
        this.elements.executionChart = document.getElementById('execution-chart');
        this.elements.pnlChart = document.getElementById('pnl-chart');
        this.elements.spreadChart = document.getElementById('spread-chart');
        this.elements.volumeChart = document.getElementById('volume-chart');
        this.elements.matrixChart = document.getElementById('matrix-chart');

        // Tables
        this.elements.opportunitiesTable = document.getElementById('opportunities-table');
        this.elements.executionsTable = document.getElementById('executions-table');
        this.elements.alertsTable = document.getElementById('alerts-table');

        // Controls
        this.elements.startButton = document.getElementById('start-bot');
        this.elements.stopButton = document.getElementById('stop-bot');
        this.elements.pauseButton = document.getElementById('pause-bot');
        this.elements.resumeButton = document.getElementById('resume-bot');
        this.elements.settingsButton = document.getElementById('settings-button');
        this.elements.refreshButton = document.getElementById('refresh-button');
        this.elements.exportButton = document.getElementById('export-button');

        // Modals
        this.elements.settingsModal = document.getElementById('settings-modal');
        this.elements.alertModal = document.getElementById('alert-modal');
        this.elements.configModal = document.getElementById('config-modal');

        // Forms
        this.elements.settingsForm = document.getElementById('settings-form');
        this.elements.alertForm = document.getElementById('alert-form');
        this.elements.configForm = document.getElementById('config-form');

        // Notification
        this.elements.notificationContainer = document.getElementById('notification-container');
        this.elements.alertBell = document.getElementById('alert-bell');
        this.elements.alertCount = document.getElementById('alert-count');
        this.elements.alertDropdown = document.getElementById('alert-dropdown');

        // Loading states
        this.elements.loadingOverlay = document.getElementById('loading-overlay');
        this.elements.loadingSpinner = document.getElementById('loading-spinner');

        // Theme
        this.elements.themeToggle = document.getElementById('theme-toggle');
    }

    // ============================================================
    // EVENT LISTENERS
    // ============================================================

    setupEventListeners() {
        // Bot controls
        this.elements.startButton?.addEventListener('click', () => this.startBot());
        this.elements.stopButton?.addEventListener('click', () => this.stopBot());
        this.elements.pauseButton?.addEventListener('click', () => this.pauseBot());
        this.elements.resumeButton?.addEventListener('click', () => this.resumeBot());

        // UI controls
        this.elements.settingsButton?.addEventListener('click', () => this.openSettings());
        this.elements.refreshButton?.addEventListener('click', () => this.refreshData());
        this.elements.exportButton?.addEventListener('click', () => this.exportData());

        // Theme toggle
        this.elements.themeToggle?.addEventListener('click', () => this.toggleTheme());

        // Modal close buttons
        document.querySelectorAll('.modal-close').forEach(btn => {
            btn.addEventListener('click', () => this.closeModal(btn.closest('.modal')));
        });

        // Modal overlay clicks
        document.querySelectorAll('.modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) this.closeModal(overlay.closest('.modal'));
            });
        });

        // Form submissions
        this.elements.settingsForm?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveSettings();
        });

        this.elements.alertForm?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.createAlert();
        });

        this.elements.configForm?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.saveConfig();
        });

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl+Shift+R: Refresh
            if (e.ctrlKey && e.shiftKey && e.key === 'R') {
                e.preventDefault();
                this.refreshData();
            }
            // Escape: Close modals
            if (e.key === 'Escape') {
                this.closeAllModals();
            }
            // Ctrl+Shift+S: Start/Stop toggle
            if (e.ctrlKey && e.shiftKey && e.key === 'S') {
                e.preventDefault();
                this.state.isRunning ? this.stopBot() : this.startBot();
            }
        });

        // Window resize
        let resizeTimeout;
        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                this.handleResize();
            }, 250);
        });

        // Visibility change
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden) {
                this.refreshData();
            }
        });
    }

    // ============================================================
    // WEBSOCKET CONNECTION
    // ============================================================

    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws/dashboard`;

        try {
            this.websocket = new WebSocket(wsUrl);
            this.websocket.onopen = () => this.onWebSocketOpen();
            this.websocket.onmessage = (event) => this.onWebSocketMessage(event);
            this.websocket.onclose = () => this.onWebSocketClose();
            this.websocket.onerror = (error) => this.onWebSocketError(error);
        } catch (error) {
            console.error('WebSocket connection failed:', error);
            this.handleConnectionError();
        }
    }

    onWebSocketOpen() {
        console.log('🔗 WebSocket connected');
        this.state.isConnected = true;
        this.reconnectAttempts = 0;
        this.updateConnectionStatus(true);
        this.showNotification('Connected to server', 'success');
    }

    onWebSocketMessage(event) {
        try {
            const data = JSON.parse(event.data);
            this.handleRealtimeData(data);
        } catch (error) {
            console.error('WebSocket message parse error:', error);
        }
    }

    onWebSocketClose() {
        console.warn('⚠️ WebSocket disconnected');
        this.state.isConnected = false;
        this.updateConnectionStatus(false);
        this.handleReconnection();
    }

    onWebSocketError(error) {
        console.error('WebSocket error:', error);
        this.showNotification('Connection error', 'error');
    }

    handleReconnection() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * Math.pow(1.5, this.reconnectAttempts - 1);
            console.log(`🔄 Reconnecting in ${delay/1000}s (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            
            setTimeout(() => {
                this.connectWebSocket();
            }, delay);
        } else {
            console.error('❌ Max reconnection attempts reached');
            this.showNotification('Connection lost. Please refresh the page.', 'error');
        }
    }

    handleConnectionError() {
        this.updateConnectionStatus(false);
        this.fallbackToPolling();
    }

    fallbackToPolling() {
        if (!this.updateInterval) {
            this.updateInterval = setInterval(() => {
                this.fetchData();
            }, 5000);
        }
    }

    // ============================================================
    // DATA HANDLING
    // ============================================================

    handleRealtimeData(data) {
        const { type, payload, timestamp } = data;
        this.state.lastUpdate = timestamp || new Date().toISOString();

        switch (type) {
            case 'state':
                this.handleStateUpdate(payload);
                break;
            case 'metrics':
                this.handleMetricsUpdate(payload);
                break;
            case 'opportunity':
                this.handleOpportunityUpdate(payload);
                break;
            case 'execution':
                this.handleExecutionUpdate(payload);
                break;
            case 'pnl':
                this.handlePnLUpdate(payload);
                break;
            case 'spread':
                this.handleSpreadUpdate(payload);
                break;
            case 'volume':
                this.handleVolumeUpdate(payload);
                break;
            case 'matrix':
                this.handleMatrixUpdate(payload);
                break;
            case 'alert':
                this.handleAlert(payload);
                break;
            case 'config':
                this.handleConfigUpdate(payload);
                break;
            case 'performance':
                this.handlePerformanceUpdate(payload);
                break;
            default:
                console.debug('Unknown data type:', type);
        }

        this.updateLastUpdateTime();
        this.updateUI();
    }

    handleStateUpdate(payload) {
        this.state.isRunning = payload.isRunning || false;
        this.state.isPaused = payload.isPaused || false;
        this.state.mode = payload.mode || 'idle';
        this.updateBotStatus();
    }

    handleMetricsUpdate(payload) {
        this.state.metrics = payload;
        this.updateMetricsDisplay();
    }

    handleOpportunityUpdate(payload) {
        if (Array.isArray(payload)) {
            this.state.opportunities = payload.slice(0, 100);
        } else if (payload.opportunities) {
            this.state.opportunities = payload.opportunities.slice(0, 100);
        }
        this.updateOpportunitiesTable();
        if (this.charts) {
            this.charts.updateOpportunityChart(this.state.opportunities);
        }
    }

    handleExecutionUpdate(payload) {
        if (Array.isArray(payload)) {
            this.state.executions = payload.slice(0, 100);
        } else if (payload.executions) {
            this.state.executions = payload.executions.slice(0, 100);
        }
        this.updateExecutionsTable();
        if (this.charts) {
            this.charts.updateExecutionChart(this.state.executions);
        }
    }

    handlePnLUpdate(payload) {
        this.state.pnl = payload;
        if (this.charts) {
            this.charts.updatePnLChart(payload);
        }
        this.updateMetricsDisplay();
    }

    handleSpreadUpdate(payload) {
        this.state.spreads = payload;
        if (this.charts) {
            this.charts.updateSpreadChart(payload);
        }
    }

    handleVolumeUpdate(payload) {
        this.state.volumes = payload;
        if (this.charts) {
            this.charts.updateVolumeChart(payload);
        }
    }

    handleMatrixUpdate(payload) {
        this.state.matrix = payload;
        if (this.charts) {
            this.charts.updateArbitrageMatrix(payload);
        }
    }

    handleAlert(payload) {
        this.state.alerts.unshift({
            ...payload,
            timestamp: payload.timestamp || new Date().toISOString(),
            read: false,
        });
        if (this.state.alerts.length > 50) {
            this.state.alerts = this.state.alerts.slice(0, 50);
        }
        this.updateAlerts();
        this.showNotification(payload.message, payload.severity || 'info');
    }

    handleConfigUpdate(payload) {
        this.state.config = { ...this.state.config, ...payload };
    }

    handlePerformanceUpdate(payload) {
        this.state.performance = payload;
        this.updatePerformanceMetrics();
    }

    // ============================================================
    // DATA FETCHING (Polling Fallback)
    // ============================================================

    async fetchData() {
        try {
            const endpoints = [
                '/api/arbitrage/state',
                '/api/arbitrage/metrics',
                '/api/arbitrage/opportunities',
                '/api/arbitrage/executions',
                '/api/arbitrage/pnl',
                '/api/arbitrage/spreads',
                '/api/arbitrage/volume',
                '/api/arbitrage/matrix',
                '/api/arbitrage/alerts',
                '/api/arbitrage/performance',
            ];

            const responses = await Promise.all(
                endpoints.map(endpoint => fetch(endpoint).then(res => {
                    if (!res.ok) throw new Error(`HTTP ${res.status}`);
                    return res.json();
                }).catch(() => null))
            );

            const [
                state, metrics, opportunities, executions, pnl,
                spreads, volume, matrix, alerts, performance
            ] = responses;

            if (state) this.handleStateUpdate(state);
            if (metrics) this.handleMetricsUpdate(metrics);
            if (opportunities) this.handleOpportunityUpdate(opportunities);
            if (executions) this.handleExecutionUpdate(executions);
            if (pnl) this.handlePnLUpdate(pnl);
            if (spreads) this.handleSpreadUpdate(spreads);
            if (volume) this.handleVolumeUpdate(volume);
            if (matrix) this.handleMatrixUpdate(matrix);
            if (alerts) this.state.alerts = alerts;
            if (performance) this.state.performance = performance;

        } catch (error) {
            console.error('Data fetch error:', error);
        }
    }

    // ============================================================
    // UI UPDATES
    // ============================================================

    updateUI() {
        this.updateConnectionStatus(this.state.isConnected);
        this.updateBotStatus();
        this.updateLastUpdateTime();
        this.updateMetricsDisplay();
        this.updateOpportunitiesTable();
        this.updateExecutionsTable();
        this.updateAlerts();
        this.updatePerformanceMetrics();
    }

    updateConnectionStatus(isConnected) {
        const status = this.elements.connectionStatus;
        const indicator = this.elements.statusIndicator;
        
        if (status) {
            status.textContent = isConnected ? '🟢 Connected' : '🔴 Disconnected';
            status.className = isConnected ? 'connected' : 'disconnected';
        }

        if (indicator) {
            indicator.className = isConnected ? 'connected' : 'disconnected';
        }
    }

    updateBotStatus() {
        const status = this.elements.botStatus;
        if (!status) return;

        let text, className;
        if (this.state.isRunning) {
            if (this.state.isPaused) {
                text = '⏸️ Paused';
                className = 'paused';
            } else {
                text = '▶️ Running';
                className = 'running';
            }
        } else {
            text = '⏹️ Stopped';
            className = 'stopped';
        }

        status.textContent = text;
        status.className = className;

        // Update control buttons
        this.updateControlButtons();
    }

    updateControlButtons() {
        const { startButton, stopButton, pauseButton, resumeButton } = this.elements;

        if (this.state.isRunning) {
            if (this.state.isPaused) {
                startButton?.classList.add('hidden');
                stopButton?.classList.add('hidden');
                pauseButton?.classList.add('hidden');
                resumeButton?.classList.remove('hidden');
            } else {
                startButton?.classList.add('hidden');
                stopButton?.classList.remove('hidden');
                pauseButton?.classList.remove('hidden');
                resumeButton?.classList.add('hidden');
            }
        } else {
            startButton?.classList.remove('hidden');
            stopButton?.classList.add('hidden');
            pauseButton?.classList.add('hidden');
            resumeButton?.classList.add('hidden');
        }
    }

    updateLastUpdateTime() {
        const element = this.elements.lastUpdate;
        if (!element) return;

        if (this.state.lastUpdate) {
            const date = new Date(this.state.lastUpdate);
            element.textContent = `Last update: ${date.toLocaleTimeString()}`;
            element.title = date.toLocaleString();
        } else {
            element.textContent = 'Waiting for data...';
        }
    }

    updateMetricsDisplay() {
        const metrics = this.state.metrics;
        const pnl = this.state.pnl;

        // Update metric cards with animation
        this.animateMetricValue(this.elements.totalPnL, pnl.total || metrics.totalPnL || 0, '$');
        this.animateMetricValue(this.elements.totalTrades, metrics.totalTrades || 0, '');
        this.animateMetricValue(this.elements.winRate, metrics.winRate || 0, '%');
        this.animateMetricValue(this.elements.avgProfit, metrics.avgProfit || 0, '$');
        this.animateMetricValue(this.elements.bestTrade, metrics.bestTrade || 0, '$');
        this.animateMetricValue(this.elements.worstTrade, metrics.worstTrade || 0, '$');
        this.animateMetricValue(this.elements.sharpeRatio, metrics.sharpeRatio || 0, '');
        this.animateMetricValue(this.elements.maxDrawdown, metrics.maxDrawdown || 0, '%');
    }

    animateMetricValue(element, value, prefix = '') {
        if (!element) return;

        const formatted = this.formatMetricValue(value, prefix);
        const current = element.textContent;

        if (current !== formatted) {
            element.textContent = formatted;
            element.classList.add('flash');
            setTimeout(() => element.classList.remove('flash'), 300);
        }
    }

    formatMetricValue(value, prefix = '') {
        if (value === undefined || value === null) return '--';

        if (typeof value === 'number') {
            if (Math.abs(value) >= 1e6) {
                return prefix + (value / 1e6).toFixed(2) + 'M';
            }
            if (Math.abs(value) >= 1e3) {
                return prefix + (value / 1e3).toFixed(2) + 'K';
            }
            return prefix + value.toFixed(2);
        }
        return String(value);
    }

    updateOpportunitiesTable() {
        const table = this.elements.opportunitiesTable;
        if (!table) return;

        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        const opportunities = this.state.opportunities.slice(0, 20);
        
        if (opportunities.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" class="no-data">No opportunities detected</td></tr>';
            return;
        }

        tbody.innerHTML = opportunities.map(opp => `
            <tr class="opportunity-row ${opp.profit > 0 ? 'profitable' : 'unprofitable'}">
                <td class="pair">${this.escapeHtml(opp.pair || 'N/A')}</td>
                <td class="exchange-a">${this.escapeHtml(opp.exchangeA || 'N/A')}</td>
                <td class="exchange-b">${this.escapeHtml(opp.exchangeB || 'N/A')}</td>
                <td class="spread">$${opp.spread?.toFixed(2) || '0.00'}</td>
                <td class="profit ${opp.profit > 0 ? 'positive' : 'negative'}">$${opp.profit?.toFixed(2) || '0.00'}</td>
                <td class="timestamp">${this.formatTimestamp(opp.timestamp)}</td>
            </tr>
        `).join('');

        // Add click handlers
        tbody.querySelectorAll('.opportunity-row').forEach((row, index) => {
            row.addEventListener('click', () => {
                this.showOpportunityDetails(opportunities[index]);
            });
        });
    }

    updateExecutionsTable() {
        const table = this.elements.executionsTable;
        if (!table) return;

        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        const executions = this.state.executions.slice(0, 20);
        
        if (executions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="no-data">No executions recorded</td></tr>';
            return;
        }

        tbody.innerHTML = executions.map(exec => `
            <tr class="execution-row ${exec.pnl > 0 ? 'profitable' : 'unprofitable'}">
                <td class="id">#${exec.id || 'N/A'}</td>
                <td class="pair">${this.escapeHtml(exec.pair || 'N/A')}</td>
                <td class="side ${exec.side === 'buy' ? 'buy' : 'sell'}">${exec.side || 'N/A'}</td>
                <td class="size">${exec.size?.toFixed(4) || '0'}</td>
                <td class="price">$${exec.price?.toFixed(2) || '0.00'}</td>
                <td class="pnl ${exec.pnl > 0 ? 'positive' : 'negative'}">$${exec.pnl?.toFixed(2) || '0.00'}</td>
                <td class="timestamp">${this.formatTimestamp(exec.timestamp)}</td>
            </tr>
        `).join('');

        // Add click handlers
        tbody.querySelectorAll('.execution-row').forEach((row, index) => {
            row.addEventListener('click', () => {
                this.showExecutionDetails(executions[index]);
            });
        });
    }

    updateAlerts() {
        const table = this.elements.alertsTable;
        if (!table) return;

        const tbody = table.querySelector('tbody');
        if (!tbody) return;

        const alerts = this.state.alerts.slice(0, 20);
        const unreadCount = this.state.alerts.filter(a => !a.read).length;

        // Update alert bell
        if (this.elements.alertCount) {
            this.elements.alertCount.textContent = unreadCount;
            this.elements.alertCount.style.display = unreadCount > 0 ? 'inline' : 'none';
        }

        if (alerts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="4" class="no-data">No alerts</td></tr>';
            return;
        }

        tbody.innerHTML = alerts.map(alert => `
            <tr class="alert-row severity-${alert.severity || 'info'} ${alert.read ? 'read' : 'unread'}">
                <td class="severity">
                    <span class="severity-badge ${alert.severity || 'info'}">${alert.severity || 'info'}</span>
                </td>
                <td class="message">${this.escapeHtml(alert.message || '')}</td>
                <td class="source">${this.escapeHtml(alert.source || 'system')}</td>
                <td class="timestamp">${this.formatTimestamp(alert.timestamp)}</td>
            </tr>
        `).join('');

        // Mark all as read on click
        if (this.elements.alertBell) {
            this.elements.alertBell.addEventListener('click', () => {
                this.markAllAlertsRead();
            });
        }
    }

    updatePerformanceMetrics() {
        const perf = this.state.performance;
        if (!perf) return;

        // Update performance indicators
        document.querySelectorAll('[data-perf-key]').forEach(el => {
            const key = el.dataset.perfKey;
            const value = perf[key];
            if (value !== undefined) {
                el.textContent = this.formatMetricValue(value, el.dataset.prefix || '');
            }
        });
    }

    // ============================================================
    // BOT CONTROLS
    // ============================================================

    async startBot() {
        try {
            const response = await fetch('/api/arbitrage/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(this.state.config),
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const result = await response.json();
            if (result.success) {
                this.state.isRunning = true;
                this.state.isPaused = false;
                this.updateBotStatus();
                this.showNotification('Bot started successfully', 'success');
            } else {
                this.showNotification(result.message || 'Failed to start bot', 'error');
            }
        } catch (error) {
            console.error('Start bot error:', error);
            this.showNotification('Failed to start bot', 'error');
        }
    }

    async stopBot() {
        try {
            const response = await fetch('/api/arbitrage/stop', {
                method: 'POST',
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const result = await response.json();
            if (result.success) {
                this.state.isRunning = false;
                this.state.isPaused = false;
                this.updateBotStatus();
                this.showNotification('Bot stopped', 'info');
            } else {
                this.showNotification(result.message || 'Failed to stop bot', 'error');
            }
        } catch (error) {
            console.error('Stop bot error:', error);
            this.showNotification('Failed to stop bot', 'error');
        }
    }

    async pauseBot() {
        try {
            const response = await fetch('/api/arbitrage/pause', {
                method: 'POST',
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const result = await response.json();
            if (result.success) {
                this.state.isPaused = true;
                this.updateBotStatus();
                this.showNotification('Bot paused', 'info');
            } else {
                this.showNotification(result.message || 'Failed to pause bot', 'error');
            }
        } catch (error) {
            console.error('Pause bot error:', error);
            this.showNotification('Failed to pause bot', 'error');
        }
    }

    async resumeBot() {
        try {
            const response = await fetch('/api/arbitrage/resume', {
                method: 'POST',
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const result = await response.json();
            if (result.success) {
                this.state.isPaused = false;
                this.updateBotStatus();
                this.showNotification('Bot resumed', 'success');
            } else {
                this.showNotification(result.message || 'Failed to resume bot', 'error');
            }
        } catch (error) {
            console.error('Resume bot error:', error);
            this.showNotification('Failed to resume bot', 'error');
        }
    }

    // ============================================================
    // CONFIGURATION
    // ============================================================

    async loadConfig() {
        try {
            const response = await fetch('/api/arbitrage/config');
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const config = await response.json();
            this.state.config = config;
            this.populateSettingsForm(config);
        } catch (error) {
            console.error('Load config error:', error);
        }
    }

    populateSettingsForm(config) {
        const form = this.elements.settingsForm;
        if (!form) return;

        Object.entries(config).forEach(([key, value]) => {
            const input = form.querySelector(`[name="${key}"]`);
            if (input) {
                if (input.type === 'checkbox') {
                    input.checked = value;
                } else if (input.type === 'number') {
                    input.value = value !== undefined ? value : '';
                } else {
                    input.value = value !== undefined ? value : '';
                }
            }
        });
    }

    async saveSettings() {
        const form = this.elements.settingsForm;
        if (!form) return;

        const formData = new FormData(form);
        const config = {};

        formData.forEach((value, key) => {
            const input = form.querySelector(`[name="${key}"]`);
            if (input) {
                if (input.type === 'checkbox') {
                    config[key] = input.checked;
                } else if (input.type === 'number') {
                    config[key] = parseFloat(value) || 0;
                } else {
                    config[key] = value;
                }
            }
        });

        try {
            const response = await fetch('/api/arbitrage/config', {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(config),
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const result = await response.json();
            if (result.success) {
                this.state.config = { ...this.state.config, ...config };
                this.showNotification('Settings saved successfully', 'success');
                this.closeModal(this.elements.settingsModal);
            } else {
                this.showNotification(result.message || 'Failed to save settings', 'error');
            }
        } catch (error) {
            console.error('Save settings error:', error);
            this.showNotification('Failed to save settings', 'error');
        }
    }

    // ============================================================
    // ALERTS
    // ============================================================

    async createAlert() {
        const form = this.elements.alertForm;
        if (!form) return;

        const formData = new FormData(form);
        const alert = {};

        formData.forEach((value, key) => {
            alert[key] = value;
        });

        try {
            const response = await fetch('/api/arbitrage/alerts', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(alert),
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const result = await response.json();
            if (result.success) {
                this.showNotification('Alert created successfully', 'success');
                this.closeModal(this.elements.alertModal);
            } else {
                this.showNotification(result.message || 'Failed to create alert', 'error');
            }
        } catch (error) {
            console.error('Create alert error:', error);
            this.showNotification('Failed to create alert', 'error');
        }
    }

    markAllAlertsRead() {
        this.state.alerts.forEach(a => a.read = true);
        this.updateAlerts();
    }

    // ============================================================
    // MODALS
    // ============================================================

    openSettings() {
        this.openModal(this.elements.settingsModal);
    }

    openModal(modal) {
        if (!modal) return;
        modal.classList.add('open');
        document.body.classList.add('modal-open');
    }

    closeModal(modal) {
        if (!modal) return;
        modal.classList.remove('open');
        document.body.classList.remove('modal-open');
    }

    closeAllModals() {
        document.querySelectorAll('.modal.open').forEach(modal => {
            this.closeModal(modal);
        });
    }

    // ============================================================
    // DATA OPERATIONS
    // ============================================================

    async refreshData() {
        this.showLoading(true);
        try {
            await this.fetchData();
            this.showNotification('Data refreshed', 'info');
        } catch (error) {
            console.error('Refresh error:', error);
            this.showNotification('Failed to refresh data', 'error');
        } finally {
            this.showLoading(false);
        }
    }

    async exportData() {
        try {
            const response = await fetch('/api/arbitrage/export', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    format: 'csv',
                    include: ['opportunities', 'executions', 'pnl'],
                }),
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `arbitrage_data_${new Date().toISOString().slice(0,10)}.csv`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            URL.revokeObjectURL(url);

            this.showNotification('Data exported successfully', 'success');
        } catch (error) {
            console.error('Export error:', error);
            this.showNotification('Failed to export data', 'error');
        }
    }

    // ============================================================
    // SHOW DETAILS
    // ============================================================

    showOpportunityDetails(opportunity) {
        // Implement detail view
        console.log('Opportunity details:', opportunity);
        this.showNotification(`Opportunity: ${opportunity.pair} - $${opportunity.profit?.toFixed(2)}`, 'info');
    }

    showExecutionDetails(execution) {
        // Implement detail view
        console.log('Execution details:', execution);
        this.showNotification(`Execution #${execution.id}: $${execution.pnl?.toFixed(2)}`, 'info');
    }

    // ============================================================
    // THEME
    // ============================================================

    toggleTheme() {
        const current = document.documentElement.getAttribute('data-theme');
        const next = current === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', next);
        localStorage.setItem('nexus-theme', next);
        
        this.showNotification(`Theme switched to ${next}`, 'info');
    }

    // ============================================================
    // NOTIFICATIONS
    // ============================================================

    showNotification(message, type = 'info', duration = 4000) {
        const container = this.elements.notificationContainer;
        if (!container) return;

        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <span class="notification-icon">${this.getNotificationIcon(type)}</span>
            <span class="notification-message">${this.escapeHtml(message)}</span>
            <button class="notification-close">×</button>
        `;

        notification.querySelector('.notification-close')?.addEventListener('click', () => {
            notification.remove();
        });

        container.appendChild(notification);

        setTimeout(() => {
            notification.classList.add('fade-out');
            setTimeout(() => notification.remove(), 300);
        }, duration);
    }

    getNotificationIcon(type) {
        const icons = {
            success: '✅',
            error: '❌',
            warning: '⚠️',
            info: 'ℹ️',
        };
        return icons[type] || 'ℹ️';
    }

    // ============================================================
    // LOADING
    // ============================================================

    showLoading(show) {
        const overlay = this.elements.loadingOverlay;
        if (!overlay) return;
        
        if (show) {
            overlay.classList.remove('hidden');
        } else {
            overlay.classList.add('hidden');
        }
    }

    // ============================================================
    // RESIZE HANDLING
    // ============================================================

    handleResize() {
        // Resize charts if needed
        if (this.charts) {
            this.charts.resizeAllCharts();
        }
    }

    // ============================================================
    // AUTO REFRESH
    // ============================================================

    startAutoRefresh() {
        // Refresh data every 30 seconds (fallback)
        setInterval(() => {
            if (!this.state.isConnected) {
                this.fetchData();
            }
        }, 30000);
    }

    // ============================================================
    // UTILITY METHODS
    // ============================================================

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    formatTimestamp(timestamp) {
        if (!timestamp) return '--';
        try {
            const date = new Date(timestamp);
            if (isNaN(date.getTime())) return '--';
            return date.toLocaleString();
        } catch {
            return '--';
        }
    }

    // ============================================================
    // DESTROY
    // ============================================================

    destroy() {
        // Clean up WebSocket
        if (this.websocket) {
            this.websocket.close();
            this.websocket = null;
        }

        // Clear intervals
        if (this.updateInterval) {
            clearInterval(this.updateInterval);
            this.updateInterval = null;
        }

        // Destroy charts
        if (this.charts) {
            this.charts.destroyAll();
            this.charts = null;
        }

        // Clear event listeners
        this.listeners.clear();

        console.log('🔄 Dashboard destroyed');
    }
}

// ============================================================
// INITIALIZATION
// ============================================================

let dashboard = null;

function initializeDashboard() {
    if (dashboard) {
        dashboard.destroy();
    }
    dashboard = new ArbitrageDashboard();
    return dashboard;
}

// ============================================================
// EXPORTS
// ============================================================

export {
    ArbitrageDashboard,
    initializeDashboard,
    dashboard,
};

// ============================================================
// AUTO-INITIALIZATION
// ============================================================

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeDashboard);
} else {
    initializeDashboard();
}

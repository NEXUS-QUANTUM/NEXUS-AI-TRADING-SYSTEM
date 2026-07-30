/**
 * trading/bots/hedge_bot/static/js/dashboard.js
 * NEXUS AI TRADING SYSTEM - Hedge Bot Dashboard Controller
 * Version: 2.0.0
 * Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
 */

/**
 * NEXUS Dashboard Controller
 * 
 * Main dashboard controller for the NEXUS Hedge Bot.
 * Features include:
 * - Dashboard initialization
 * - Widget management
 * - Real-time data updates
 * - Event handling
 * - Theme management
 * - Responsive design
 * - Performance optimization
 * - Error handling
 */

import { NexusAPIClient } from './api_client.js';
import { NexusChart, ChartRegistry } from './charts.js';

class NexusDashboard {
    /**
     * Create a new dashboard instance
     * 
     * @param {Object} config - Dashboard configuration
     * @param {string} config.apiBaseUrl - API base URL
     * @param {string} config.wsUrl - WebSocket URL
     * @param {Object} config.theme - Theme configuration
     * @param {Object} config.widgets - Widget configuration
     * @param {boolean} config.debug - Enable debug mode
     */
    constructor(config = {}) {
        // Configuration
        this.config = {
            apiBaseUrl: config.apiBaseUrl || '/api/v1',
            wsUrl: config.wsUrl || null,
            theme: config.theme || 'dark',
            widgets: config.widgets || {},
            debug: config.debug || false,
            refreshInterval: config.refreshInterval || 5000,
            maxRetries: config.maxRetries || 3,
        };

        // State
        this.isInitialized = false;
        this.isRunning = false;
        this.widgets = {};
        this.data = {};
        this.timers = [];
        this.retryCounts = {};

        // Initialize API client
        this.api = new NexusAPIClient({
            baseURL: this.config.apiBaseUrl,
            debug: this.config.debug,
            onUnauthorized: this._handleUnauthorized.bind(this),
        });

        // DOM elements
        this.elements = {
            dashboard: document.getElementById('dashboard'),
            sidebar: document.getElementById('sidebar'),
            mainContent: document.getElementById('main-content'),
            statusBar: document.getElementById('status-bar'),
            notifications: document.getElementById('notifications'),
        };

        // Initialize
        this._init();

        this.log('Dashboard initialized');
    }

    // ============================================================
    // INITIALIZATION
    // ============================================================

    /**
     * Initialize dashboard
     */
    _init() {
        // Load theme
        this._loadTheme();

        // Setup sidebar
        this._setupSidebar();

        // Setup status bar
        this._setupStatusBar();

        // Setup notifications
        this._setupNotifications();

        // Load widgets
        this._loadWidgets();

        // Setup event listeners
        this._setupEventListeners();

        // Setup resize handler
        this._setupResizeHandler();

        // Setup keyboard shortcuts
        this._setupKeyboardShortcuts();

        // Mark as initialized
        this.isInitialized = true;
    }

    /**
     * Start dashboard
     */
    async start() {
        if (this.isRunning) {
            this.log('Dashboard already running');
            return;
        }

        this.log('Starting dashboard');

        try {
            // Authenticate
            await this._authenticate();

            // Initialize WebSocket
            await this._initWebSocket();

            // Load initial data
            await this._loadInitialData();

            // Start auto-refresh
            this._startAutoRefresh();

            // Start WebSocket heartbeats
            this._startWebSocketHeartbeats();

            this.isRunning = true;
            this._emit('started', { dashboard: this });

            this.log('Dashboard started successfully');

        } catch (error) {
            this.log('Failed to start dashboard:', error);
            this._showError('Failed to start dashboard. Please try again.');
            throw error;
        }
    }

    /**
     * Stop dashboard
     */
    stop() {
        if (!this.isRunning) {
            this.log('Dashboard already stopped');
            return;
        }

        this.log('Stopping dashboard');

        // Stop timers
        this._clearTimers();

        // Disconnect WebSocket
        this.api.disconnectWebSocket();

        // Clear data
        this.data = {};

        // Mark as stopped
        this.isRunning = false;
        this._emit('stopped', { dashboard: this });

        this.log('Dashboard stopped');
    }

    // ============================================================
    // AUTHENTICATION
    // ============================================================

    /**
     * Authenticate user
     */
    async _authenticate() {
        // Check if already authenticated
        const authStatus = this.api.getAuthStatus();
        if (authStatus.isAuthenticated) {
            this.log('Already authenticated');
            return;
        }

        // Check for saved credentials
        const credentials = this._getSavedCredentials();
        if (credentials) {
            try {
                await this.api.login(credentials.username, credentials.password);
                this.log('Authenticated with saved credentials');
                return;
            } catch (error) {
                this.log('Saved credentials failed:', error);
            }
        }

        // Show login modal
        await this._showLoginModal();
    }

    /**
     * Show login modal
     */
    async _showLoginModal() {
        return new Promise((resolve, reject) => {
            // Create modal
            const modal = this._createModal({
                title: 'Login to NEXUS Dashboard',
                content: `
                    <form id="login-form">
                        <div class="form-group">
                            <label class="form-label">Username</label>
                            <input type="text" id="login-username" class="form-control" placeholder="Enter username" required>
                        </div>
                        <div class="form-group">
                            <label class="form-label">Password</label>
                            <input type="password" id="login-password" class="form-control" placeholder="Enter password" required>
                        </div>
                        <div class="form-group">
                            <label class="form-label">2FA Code (optional)</label>
                            <input type="text" id="login-2fa" class="form-control" placeholder="Enter 2FA code">
                        </div>
                        <div class="form-group">
                            <button type="submit" class="btn btn-primary btn-block">Login</button>
                        </div>
                        <div id="login-error" class="alert alert-error" style="display:none;"></div>
                    </form>
                `,
                actions: [],
                onClose: () => reject(new Error('Login cancelled')),
            });

            // Handle form submission
            const form = modal.querySelector('#login-form');
            form.addEventListener('submit', async (e) => {
                e.preventDefault();

                const username = document.getElementById('login-username').value;
                const password = document.getElementById('login-password').value;
                const twoFactorCode = document.getElementById('login-2fa').value || null;

                try {
                    await this.api.login(username, password, twoFactorCode);
                    modal.remove();
                    resolve();
                } catch (error) {
                    const errorEl = document.getElementById('login-error');
                    errorEl.textContent = error.message || 'Login failed';
                    errorEl.style.display = 'block';
                }
            });
        });
    }

    /**
     * Get saved credentials
     */
    _getSavedCredentials() {
        try {
            const data = localStorage.getItem('nexus_credentials');
            if (data) {
                return JSON.parse(data);
            }
        } catch (error) {
            this.log('Failed to get saved credentials:', error);
        }
        return null;
    }

    /**
     * Save credentials
     */
    _saveCredentials(username, password) {
        try {
            localStorage.setItem('nexus_credentials', JSON.stringify({
                username,
                password,
                savedAt: Date.now(),
            }));
        } catch (error) {
            this.log('Failed to save credentials:', error);
        }
    }

    /**
     * Clear saved credentials
     */
    _clearCredentials() {
        try {
            localStorage.removeItem('nexus_credentials');
        } catch (error) {
            this.log('Failed to clear credentials:', error);
        }
    }

    // ============================================================
    // WEBSOCKET
    // ============================================================

    /**
     * Initialize WebSocket connection
     */
    async _initWebSocket() {
        try {
            await this.api.connectWebSocket(this.config.wsUrl);

            // Subscribe to channels
            this.api.subscribe('market_data', this._handleMarketData.bind(this));
            this.api.subscribe('positions', this._handlePositionUpdate.bind(this));
            this.api.subscribe('trades', this._handleTradeUpdate.bind(this));
            this.api.subscribe('strategy_updates', this._handleStrategyUpdate.bind(this));
            this.api.subscribe('risk_metrics', this._handleRiskUpdate.bind(this));
            this.api.subscribe('system_status', this._handleSystemStatus.bind(this));

            this.log('WebSocket initialized and subscribed');

        } catch (error) {
            this.log('WebSocket initialization failed:', error);
            // Continue without WebSocket (fallback to polling)
        }
    }

    /**
     * Start WebSocket heartbeats
     */
    _startWebSocketHeartbeats() {
        // Heartbeat is handled by the API client
    }

    // ============================================================
    // DATA LOADING
    // ============================================================

    /**
     * Load initial data
     */
    async _loadInitialData() {
        this.log('Loading initial data');

        const endpoints = [
            { key: 'portfolio', endpoint: '/portfolio/summary' },
            { key: 'positions', endpoint: '/trading/positions' },
            { key: 'orders', endpoint: '/trading/orders' },
            { key: 'strategy', endpoint: '/strategy/status' },
            { key: 'risk', endpoint: '/risk/metrics' },
            { key: 'performance', endpoint: '/strategy/performance' },
        ];

        const results = await Promise.allSettled(
            endpoints.map(async ({ key, endpoint }) => {
                try {
                    const data = await this.api.get(endpoint);
                    this.data[key] = data;
                    this._emit('data_loaded', { key, data });
                    this.log(`Loaded ${key} data`);
                } catch (error) {
                    this.log(`Failed to load ${key} data:`, error);
                    this.data[key] = null;
                }
            })
        );

        // Update UI with loaded data
        this._updateDashboard();

        this.log('Initial data loaded');
    }

    /**
     * Refresh all data
     */
    async refreshData() {
        this.log('Refreshing data');

        const endpoints = [
            { key: 'portfolio', endpoint: '/portfolio/summary' },
            { key: 'positions', endpoint: '/trading/positions' },
            { key: 'orders', endpoint: '/trading/orders' },
            { key: 'strategy', endpoint: '/strategy/status' },
            { key: 'risk', endpoint: '/risk/metrics' },
            { key: 'performance', endpoint: '/strategy/performance' },
        ];

        await Promise.all(
            endpoints.map(async ({ key, endpoint }) => {
                try {
                    const data = await this.api.get(endpoint);
                    this.data[key] = data;
                    this._emit('data_updated', { key, data });
                } catch (error) {
                    this.log(`Failed to refresh ${key} data:`, error);
                    this.data[key] = null;
                }
            })
        );

        this._updateDashboard();
        this._updateStatusBar();

        this.log('Data refreshed');
    }

    /**
     * Refresh a specific data endpoint
     */
    async refreshDataEndpoint(key, endpoint) {
        try {
            const data = await this.api.get(endpoint);
            this.data[key] = data;
            this._emit('data_updated', { key, data });
            this._updateDashboard();
            return data;
        } catch (error) {
            this.log(`Failed to refresh ${key} data:`, error);
            throw error;
        }
    }

    // ============================================================
    // UI UPDATES
    // ============================================================

    /**
     * Update dashboard UI
     */
    _updateDashboard() {
        // Update stats cards
        this._updateStats();

        // Update charts
        this._updateCharts();

        // Update tables
        this._updateTables();

        // Update strategy status
        this._updateStrategyStatus();

        // Update risk metrics
        this._updateRiskMetrics();

        // Update activity feed
        this._updateActivityFeed();
    }

    /**
     * Update statistics cards
     */
    _updateStats() {
        const portfolio = this.data.portfolio;
        if (!portfolio) return;

        const stats = {
            'total-value': {
                label: 'Total Value',
                value: this._formatCurrency(portfolio.total_value),
                change: portfolio.daily_pnl_percent,
            },
            'daily-pnl': {
                label: 'Daily P&L',
                value: this._formatCurrency(portfolio.daily_pnl),
                change: portfolio.daily_pnl_percent,
            },
            'total-pnl': {
                label: 'Total P&L',
                value: this._formatCurrency(portfolio.total_pnl),
                change: portfolio.total_pnl_percent,
            },
            'positions': {
                label: 'Open Positions',
                value: portfolio.positions?.length || 0,
                change: null,
            },
        };

        for (const [id, stat] of Object.entries(stats)) {
            const el = document.getElementById(`stat-${id}`);
            if (el) {
                const valueEl = el.querySelector('.stat-value');
                const changeEl = el.querySelector('.stat-change');
                if (valueEl) valueEl.textContent = stat.value;
                if (changeEl && stat.change !== null) {
                    changeEl.textContent = this._formatPercent(stat.change);
                    changeEl.className = `stat-change ${stat.change >= 0 ? 'positive' : 'negative'}`;
                }
            }
        }
    }

    /**
     * Update charts
     */
    _updateCharts() {
        // Update price chart
        this._updatePriceChart();

        // Update portfolio allocation chart
        this._updateAllocationChart();

        // Update performance chart
        this._updatePerformanceChart();

        // Update risk chart
        this._updateRiskChart();
    }

    /**
     * Update price chart
     */
    _updatePriceChart() {
        const chart = ChartRegistry.get('price-chart');
        if (!chart) return;

        // Get market data
        const marketData = this.data.market_data;
        if (!marketData) return;

        chart.update({
            labels: marketData.labels || [],
            datasets: [{
                label: 'Price',
                data: marketData.prices || [],
                color: '#00d4ff',
                fill: false,
            }],
        });
    }

    /**
     * Update allocation chart
     */
    _updateAllocationChart() {
        const chart = ChartRegistry.get('allocation-chart');
        if (!chart) return;

        const portfolio = this.data.portfolio;
        if (!portfolio || !portfolio.allocation) return;

        const labels = Object.keys(portfolio.allocation);
        const values = Object.values(portfolio.allocation);

        chart.update({
            labels: labels,
            datasets: [{
                data: values,
            }],
        });
    }

    /**
     * Update performance chart
     */
    _updatePerformanceChart() {
        const chart = ChartRegistry.get('performance-chart');
        if (!chart) return;

        const performance = this.data.performance;
        if (!performance) return;

        chart.update({
            labels: performance.dates || [],
            datasets: [
                {
                    label: 'Equity',
                    data: performance.equity || [],
                    color: '#10b981',
                    fill: true,
                },
                {
                    label: 'Benchmark',
                    data: performance.benchmark || [],
                    color: '#f59e0b',
                    fill: false,
                },
            ],
        });
    }

    /**
     * Update risk chart
     */
    _updateRiskChart() {
        const chart = ChartRegistry.get('risk-chart');
        if (!chart) return;

        const risk = this.data.risk;
        if (!risk) return;

        chart.update({
            labels: ['VaR 95%', 'VaR 99%', 'CVaR 95%', 'Max DD'],
            datasets: [{
                data: [
                    risk.var_95 || 0,
                    risk.var_99 || 0,
                    risk.cvar_95 || 0,
                    risk.max_drawdown || 0,
                ],
            }],
        });
    }

    /**
     * Update tables
     */
    _updateTables() {
        // Update positions table
        this._updatePositionsTable();

        // Update orders table
        this._updateOrdersTable();
    }

    /**
     * Update positions table
     */
    _updatePositionsTable() {
        const tbody = document.getElementById('positions-table-body');
        if (!tbody) return;

        const positions = this.data.positions?.positions || [];
        tbody.innerHTML = positions.map(pos => `
            <tr>
                <td class="position-symbol">${pos.symbol}</td>
                <td class="position-side ${pos.side}">${pos.side}</td>
                <td>${pos.quantity}</td>
                <td>${this._formatCurrency(pos.entry_price)}</td>
                <td>${this._formatCurrency(pos.current_price)}</td>
                <td class="position-pnl ${pos.unrealized_pnl >= 0 ? 'positive' : 'negative'}">
                    ${this._formatCurrency(pos.unrealized_pnl)}
                </td>
                <td><span class="position-status ${pos.status}">${pos.status}</span></td>
            </tr>
        `).join('');
    }

    /**
     * Update orders table
     */
    _updateOrdersTable() {
        const tbody = document.getElementById('orders-table-body');
        if (!tbody) return;

        const orders = this.data.orders?.orders || [];
        tbody.innerHTML = orders.map(order => `
            <tr>
                <td>${order.id}</td>
                <td>${order.symbol}</td>
                <td class="position-side ${order.side}">${order.side}</td>
                <td>${order.quantity}</td>
                <td>${this._formatCurrency(order.price)}</td>
                <td><span class="badge badge-${order.status}">${order.status}</span></td>
            </tr>
        `).join('');
    }

    /**
     * Update strategy status
     */
    _updateStrategyStatus() {
        const statusEl = document.getElementById('strategy-status');
        if (!statusEl) return;

        const strategy = this.data.strategy;
        if (!strategy) return;

        statusEl.innerHTML = `
            <div class="strategy-info">
                <div class="strategy-name">${strategy.name || 'N/A'}</div>
                <div class="strategy-status ${strategy.status}">${strategy.status || 'unknown'}</div>
            </div>
            <div class="strategy-metrics">
                <div class="metric">
                    <span class="metric-label">Hedge Ratio</span>
                    <span class="metric-value">${(strategy.metrics?.hedge_ratio || 0).toFixed(2)}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Positions</span>
                    <span class="metric-value">${strategy.positions?.total || 0}</span>
                </div>
                <div class="metric">
                    <span class="metric-label">Daily P&L</span>
                    <span class="metric-value ${(strategy.performance?.daily_pnl || 0) >= 0 ? 'positive' : 'negative'}">
                        ${this._formatCurrency(strategy.performance?.daily_pnl || 0)}
                    </span>
                </div>
            </div>
        `;
    }

    /**
     * Update risk metrics
     */
    _updateRiskMetrics() {
        const riskEl = document.getElementById('risk-metrics');
        if (!riskEl) return;

        const risk = this.data.risk;
        if (!risk) return;

        riskEl.innerHTML = `
            <div class="risk-grid">
                <div class="risk-item">
                    <span class="risk-label">VaR 95%</span>
                    <span class="risk-value">${this._formatCurrency(risk.var_95 || 0)}</span>
                </div>
                <div class="risk-item">
                    <span class="risk-label">VaR 99%</span>
                    <span class="risk-value">${this._formatCurrency(risk.var_99 || 0)}</span>
                </div>
                <div class="risk-item">
                    <span class="risk-label">CVaR 95%</span>
                    <span class="risk-value">${this._formatCurrency(risk.cvar_95 || 0)}</span>
                </div>
                <div class="risk-item">
                    <span class="risk-label">Max Drawdown</span>
                    <span class="risk-value">${this._formatPercent(risk.max_drawdown || 0)}</span>
                </div>
                <div class="risk-item">
                    <span class="risk-label">Margin Utilization</span>
                    <span class="risk-value">${this._formatPercent(risk.margin_utilization || 0)}</span>
                </div>
                <div class="risk-item">
                    <span class="risk-label">Risk Score</span>
                    <span class="risk-value">${(risk.risk_score || 0).toFixed(2)}</span>
                </div>
            </div>
        `;
    }

    /**
     * Update activity feed
     */
    _updateActivityFeed() {
        const feed = document.getElementById('activity-feed');
        if (!feed) return;

        // Get recent activities
        const activities = this._getRecentActivities();
        feed.innerHTML = activities.map(activity => `
            <div class="feed-item">
                <div class="feed-icon ${activity.type}">${activity.icon}</div>
                <div class="feed-content">
                    <div class="feed-text">${activity.text}</div>
                    <div class="feed-time">${this._formatTime(activity.timestamp)}</div>
                </div>
            </div>
        `).join('');
    }

    /**
     * Get recent activities
     */
    _getRecentActivities() {
        const activities = [];

        // Add trades
        const trades = this.data.orders?.orders || [];
        trades.slice(0, 5).forEach(order => {
            activities.push({
                type: order.side === 'buy' ? 'success' : 'error',
                icon: order.side === 'buy' ? '📈' : '📉',
                text: `${order.side.toUpperCase()} ${order.quantity} ${order.symbol} @ ${this._formatCurrency(order.price)}`,
                timestamp: order.created_at || Date.now(),
            });
        });

        // Add strategy updates
        const strategy = this.data.strategy;
        if (strategy) {
            activities.push({
                type: 'info',
                icon: '🤖',
                text: `Strategy ${strategy.status}: ${strategy.name}`,
                timestamp: Date.now(),
            });
        }

        // Add risk alerts
        const risk = this.data.risk;
        if (risk && risk.alerts) {
            risk.alerts.forEach(alert => {
                activities.push({
                    type: alert.level === 'critical' ? 'error' : 'warning',
                    icon: alert.level === 'critical' ? '⚠️' : '⚡',
                    text: alert.message,
                    timestamp: alert.timestamp || Date.now(),
                });
            });
        }

        // Sort by timestamp descending and limit
        return activities
            .sort((a, b) => b.timestamp - a.timestamp)
            .slice(0, 10);
    }

    /**
     * Update status bar
     */
    _updateStatusBar() {
        const statusBar = this.elements.statusBar;
        if (!statusBar) return;

        const status = this.api.isConnected ? 'online' : 'offline';
        const timestamp = new Date().toLocaleTimeString();

        statusBar.innerHTML = `
            <div class="status-item">
                <span class="status-indicator ${status}"></span>
                <span>${status}</span>
            </div>
            <div class="status-item">
                <span>Last Update: ${timestamp}</span>
            </div>
            <div class="status-item">
                <span>API: ${this.api.rateLimits.remaining || 'N/A'} / ${this.api.rateLimits.limit || 'N/A'}</span>
            </div>
        `;
    }

    // ============================================================
    // WIDGET MANAGEMENT
    // ============================================================

    /**
     * Load widgets
     */
    _loadWidgets() {
        const widgetConfigs = this.config.widgets;
        const container = document.getElementById('widget-container');
        if (!container) return;

        for (const [id, config] of Object.entries(widgetConfigs)) {
            this._createWidget(id, config, container);
        }
    }

    /**
     * Create a widget
     */
    _createWidget(id, config, container) {
        const widget = document.createElement('div');
        widget.id = `widget-${id}`;
        widget.className = `widget widget-${config.type || 'default'}`;

        widget.innerHTML = `
            <div class="widget-header">
                <span class="widget-title">${config.title || id}</span>
                <div class="widget-actions">
                    ${config.refreshable ? '<button class="btn-refresh" data-widget="' + id + '">⟳</button>' : ''}
                    <button class="btn-close" data-widget="' + id + '">×</button>
                </div>
            </div>
            <div class="widget-body">
                ${config.content || ''}
            </div>
        `;

        container.appendChild(widget);
        this.widgets[id] = widget;

        // Setup refresh button
        const refreshBtn = widget.querySelector('.btn-refresh');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => {
                this._refreshWidget(id);
            });
        }

        // Setup close button
        const closeBtn = widget.querySelector('.btn-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                this._removeWidget(id);
            });
        }
    }

    /**
     * Refresh a widget
     */
    async _refreshWidget(id) {
        const widget = this.widgets[id];
        if (!widget) return;

        const config = this.config.widgets[id];
        if (!config || !config.endpoint) return;

        try {
            widget.classList.add('loading');
            const data = await this.api.get(config.endpoint);
            this.data[id] = data;
            this._updateWidget(id, data);
            widget.classList.remove('loading');
        } catch (error) {
            this.log(`Failed to refresh widget ${id}:`, error);
            widget.classList.remove('loading');
            widget.querySelector('.widget-body').innerHTML = `
                <div class="widget-error">Failed to load data</div>
            `;
        }
    }

    /**
     * Update a widget
     */
    _updateWidget(id, data) {
        const widget = this.widgets[id];
        if (!widget) return;

        const config = this.config.widgets[id];
        if (config && config.render) {
            widget.querySelector('.widget-body').innerHTML = config.render(data);
        }
    }

    /**
     * Remove a widget
     */
    _removeWidget(id) {
        const widget = this.widgets[id];
        if (widget) {
            widget.remove();
            delete this.widgets[id];
        }
    }

    // ============================================================
    // THEME MANAGEMENT
    // ============================================================

    /**
     * Load theme
     */
    _loadTheme() {
        const theme = this.config.theme;
        const themeLink = document.getElementById('theme-link');

        if (themeLink) {
            themeLink.href = `/static/css/${theme}_theme.css`;
        }

        // Apply theme to body
        document.body.className = `theme-${theme}`;
        document.documentElement.setAttribute('data-theme', theme);

        // Save theme preference
        localStorage.setItem('nexus_theme', theme);
    }

    /**
     * Toggle theme
     */
    toggleTheme() {
        const currentTheme = this.config.theme;
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        this.config.theme = newTheme;
        this._loadTheme();
        this._emit('theme_changed', { theme: newTheme });
    }

    // ============================================================
    // SIDEBAR
    // ============================================================

    /**
     * Setup sidebar
     */
    _setupSidebar() {
        const sidebar = this.elements.sidebar;
        if (!sidebar) return;

        // Setup navigation links
        const navItems = sidebar.querySelectorAll('.nav-item');
        navItems.forEach(item => {
            item.addEventListener('click', () => {
                // Remove active class from all items
                navItems.forEach(i => i.classList.remove('active'));
                item.classList.add('active');

                // Handle navigation
                const target = item.dataset.target;
                if (target) {
                    this._navigateTo(target);
                }
            });
        });

        // Setup toggle button
        const toggleBtn = document.getElementById('sidebar-toggle');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => {
                sidebar.classList.toggle('open');
                document.getElementById('sidebar-overlay')?.classList.toggle('open');
            });
        }

        // Setup overlay for mobile
        const overlay = document.getElementById('sidebar-overlay');
        if (overlay) {
            overlay.addEventListener('click', () => {
                sidebar.classList.remove('open');
                overlay.classList.remove('open');
            });
        }
    }

    /**
     * Navigate to a page
     */
    _navigateTo(target) {
        this.log('Navigating to:', target);
        // Handle page navigation
        // This would load different views based on the target
        this._emit('navigate', { target });
    }

    // ============================================================
    // NOTIFICATIONS
    // ============================================================

    /**
     * Setup notifications
     */
    _setupNotifications() {
        const container = this.elements.notifications;
        if (!container) return;

        // Create notification container if not exists
        if (!document.getElementById('notification-container')) {
            const notifContainer = document.createElement('div');
            notifContainer.id = 'notification-container';
            document.body.appendChild(notifContainer);
        }

        // Setup notification handlers
        this.api.on('notification', this._handleNotification.bind(this));
        this.api.on('alert', this._handleAlert.bind(this));
    }

    /**
     * Handle notification
     */
    _handleNotification(notification) {
        this._showNotification(notification.message, notification.type || 'info');
    }

    /**
     * Handle alert
     */
    _handleAlert(alert) {
        this._showNotification(alert.message, alert.level || 'warning');
    }

    /**
     * Show notification
     */
    _showNotification(message, type = 'info') {
        const container = document.getElementById('notification-container');
        if (!container) return;

        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;

        const icons = {
            success: '✅',
            info: 'ℹ️',
            warning: '⚠️',
            error: '❌',
        };

        notification.innerHTML = `
            <span class="notification-icon">${icons[type] || 'ℹ️'}</span>
            <span class="notification-message">${message}</span>
            <button class="notification-close">×</button>
        `;

        container.appendChild(notification);

        // Setup close button
        notification.querySelector('.notification-close').addEventListener('click', () => {
            notification.remove();
        });

        // Auto-remove after 5 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.remove();
            }
        }, 5000);
    }

    /**
     * Show error
     */
    _showError(message) {
        this._showNotification(message, 'error');
    }

    // ============================================================
    // STATUS BAR
    // ============================================================

    /**
     * Setup status bar
     */
    _setupStatusBar() {
        const statusBar = this.elements.statusBar;
        if (!statusBar) return;

        // Update status bar periodically
        setInterval(() => {
            this._updateStatusBar();
        }, 5000);
    }

    // ============================================================
    // EVENT HANDLING
    // ============================================================

    /**
     * Setup event listeners
     */
    _setupEventListeners() {
        // Handle API events
        this.api.on('authenticated', this._handleAuthenticated.bind(this));
        this.api.on('unauthorized', this._handleUnauthorized.bind(this));
        this.api.on('ws_connected', this._handleWebSocketConnected.bind(this));
        this.api.on('ws_disconnected', this._handleWebSocketDisconnected.bind(this));
        this.api.on('ws_message', this._handleWebSocketMessage.bind(this));

        // Handle window events
        window.addEventListener('beforeunload', this._handleBeforeUnload.bind(this));
        window.addEventListener('online', this._handleOnline.bind(this));
        window.addEventListener('offline', this._handleOffline.bind(this));
    }

    /**
     * Handle authentication
     */
    _handleAuthenticated(data) {
        this.log('Authenticated:', data);
        this._showNotification('Authentication successful', 'success');
        this._emit('authenticated', data);
    }

    /**
     * Handle unauthorized
     */
    _handleUnauthorized(error) {
        this.log('Unauthorized:', error);
        this._showNotification('Session expired. Please login again.', 'error');
        this._emit('unauthorized', error);

        // Show login modal
        this._showLoginModal().catch(() => {});
    }

    /**
     * Handle WebSocket connected
     */
    _handleWebSocketConnected() {
        this.log('WebSocket connected');
        this._updateStatusBar();
    }

    /**
     * Handle WebSocket disconnected
     */
    _handleWebSocketDisconnected() {
        this.log('WebSocket disconnected');
        this._updateStatusBar();
    }

    /**
     * Handle WebSocket message
     */
    _handleWebSocketMessage(message) {
        // Handle different message types
        switch (message.type) {
            case 'market_data':
                this._handleMarketData(message);
                break;
            case 'position_update':
                this._handlePositionUpdate(message);
                break;
            case 'trade_update':
                this._handleTradeUpdate(message);
                break;
            case 'strategy_update':
                this._handleStrategyUpdate(message);
                break;
            case 'risk_metrics':
                this._handleRiskUpdate(message);
                break;
            case 'system_status':
                this._handleSystemStatus(message);
                break;
        }
    }

    /**
     * Handle market data
     */
    _handleMarketData(data) {
        this.data.market_data = data;
        this._updatePriceChart();
    }

    /**
     * Handle position update
     */
    _handlePositionUpdate(data) {
        this.data.positions = data;
        this._updatePositionsTable();
    }

    /**
     * Handle trade update
     */
    _handleTradeUpdate(data) {
        this.data.orders = data;
        this._updateOrdersTable();
        this._updateActivityFeed();
    }

    /**
     * Handle strategy update
     */
    _handleStrategyUpdate(data) {
        this.data.strategy = data;
        this._updateStrategyStatus();
    }

    /**
     * Handle risk update
     */
    _handleRiskUpdate(data) {
        this.data.risk = data;
        this._updateRiskMetrics();
        this._updateRiskChart();
    }

    /**
     * Handle system status
     */
    _handleSystemStatus(data) {
        this._updateStatusBar();
        this._emit('system_status', data);
    }

    /**
     * Handle before unload
     */
    _handleBeforeUnload() {
        this.stop();
    }

    /**
     * Handle online
     */
    _handleOnline() {
        this.log('Network online');
        this._showNotification('Network connection restored', 'success');
        this._startAutoRefresh();
    }

    /**
     * Handle offline
     */
    _handleOffline() {
        this.log('Network offline');
        this._showNotification('Network connection lost', 'warning');
        this._clearTimers();
    }

    // ============================================================
    // AUTO-REFRESH
    // ============================================================

    /**
     * Start auto-refresh
     */
    _startAutoRefresh() {
        this._clearTimers();

        const interval = setInterval(() => {
            if (!this.isRunning) return;
            this.refreshData().catch(() => {});
        }, this.config.refreshInterval);

        this.timers.push(interval);
    }

    /**
     * Clear timers
     */
    _clearTimers() {
        for (const timer of this.timers) {
            clearInterval(timer);
        }
        this.timers = [];
    }

    // ============================================================
    // RESIZE HANDLER
    // ============================================================

    /**
     * Setup resize handler
     */
    _setupResizeHandler() {
        let resizeTimeout;

        window.addEventListener('resize', () => {
            clearTimeout(resizeTimeout);
            resizeTimeout = setTimeout(() => {
                this._emit('resize', { width: window.innerWidth, height: window.innerHeight });
            }, 250);
        });
    }

    // ============================================================
    // KEYBOARD SHORTCUTS
    // ============================================================

    /**
     * Setup keyboard shortcuts
     */
    _setupKeyboardShortcuts() {
        document.addEventListener('keydown', (e) => {
            // Ctrl+Shift+R: Refresh data
            if (e.ctrlKey && e.shiftKey && e.key === 'R') {
                e.preventDefault();
                this.refreshData();
            }

            // Ctrl+Shift+T: Toggle theme
            if (e.ctrlKey && e.shiftKey && e.key === 'T') {
                e.preventDefault();
                this.toggleTheme();
            }

            // Ctrl+Shift+L: Toggle sidebar
            if (e.ctrlKey && e.shiftKey && e.key === 'L') {
                e.preventDefault();
                this.elements.sidebar?.classList.toggle('open');
                document.getElementById('sidebar-overlay')?.classList.toggle('open');
            }

            // Escape: Close sidebar
            if (e.key === 'Escape') {
                this.elements.sidebar?.classList.remove('open');
                document.getElementById('sidebar-overlay')?.classList.remove('open');
            }
        });
    }

    // ============================================================
    // MODAL HELPERS
    // ============================================================

    /**
     * Create a modal
     */
    _createModal(options) {
        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.innerHTML = `
            <div class="modal-overlay"></div>
            <div class="modal-container">
                <div class="modal-header">
                    <h2 class="modal-title">${options.title || 'Modal'}</h2>
                    <button class="modal-close">×</button>
                </div>
                <div class="modal-body">
                    ${options.content || ''}
                </div>
                <div class="modal-footer">
                    ${options.actions ? options.actions.map(action => `
                        <button class="btn btn-${action.type || 'secondary'} modal-action" data-action="${action.id}">
                            ${action.label}
                        </button>
                    `).join('') : ''}
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        // Setup close handler
        const closeBtn = modal.querySelector('.modal-close');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                modal.remove();
                if (options.onClose) options.onClose();
            });
        }

        // Setup overlay click
        const overlay = modal.querySelector('.modal-overlay');
        if (overlay) {
            overlay.addEventListener('click', () => {
                modal.remove();
                if (options.onClose) options.onClose();
            });
        }

        // Setup action buttons
        const actions = modal.querySelectorAll('.modal-action');
        actions.forEach(action => {
            action.addEventListener('click', () => {
                if (options.onAction) {
                    options.onAction(action.dataset.action);
                }
            });
        });

        return modal;
    }

    // ============================================================
    // FORMATTING HELPERS
    // ============================================================

    /**
     * Format currency
     */
    _formatCurrency(value) {
        if (value === undefined || value === null) return '—';
        const absValue = Math.abs(value);
        const sign = value < 0 ? '-' : '';

        if (absValue >= 1000000) {
            return `${sign}$${(absValue / 1000000).toFixed(2)}M`;
        }
        if (absValue >= 1000) {
            return `${sign}$${(absValue / 1000).toFixed(2)}K`;
        }
        return `${sign}$${absValue.toFixed(2)}`;
    }

    /**
     * Format percentage
     */
    _formatPercent(value) {
        if (value === undefined || value === null) return '—';
        return `${(value * 100).toFixed(2)}%`;
    }

    /**
     * Format time
     */
    _formatTime(timestamp) {
        const date = new Date(timestamp);
        const now = new Date();
        const diff = now - date;

        if (diff < 60000) {
            return 'Just now';
        }
        if (diff < 3600000) {
            return `${Math.floor(diff / 60000)}m ago`;
        }
        if (diff < 86400000) {
            return `${Math.floor(diff / 3600000)}h ago`;
        }
        return date.toLocaleDateString();
    }

    /**
     * Format number
     */
    _formatNumber(value) {
        if (value === undefined || value === null) return '—';
        return value.toLocaleString();
    }

    // ============================================================
    // LOGGING
    // ============================================================

    /**
     * Log message
     */
    log(...args) {
        if (this.config.debug) {
            console.log('[NexusDashboard]', ...args);
        }
    }

    // ============================================================
    // EVENT SYSTEM
    // ============================================================

    /**
     * Add event listener
     */
    on(event, listener) {
        if (!this._listeners) {
            this._listeners = {};
        }
        if (!this._listeners[event]) {
            this._listeners[event] = [];
        }
        this._listeners[event].push(listener);
    }

    /**
     * Remove event listener
     */
    off(event, listener) {
        if (this._listeners && this._listeners[event]) {
            const index = this._listeners[event].indexOf(listener);
            if (index !== -1) {
                this._listeners[event].splice(index, 1);
            }
        }
    }

    /**
     * Emit event
     */
    _emit(event, data) {
        if (this._listeners && this._listeners[event]) {
            this._listeners[event].forEach(listener => {
                try {
                    listener(data);
                } catch (error) {
                    this.log('Error in event listener:', error);
                }
            });
        }
    }

    // ============================================================
    // CLEANUP
    // ============================================================

    /**
     * Cleanup
     */
    destroy() {
        this.stop();
        this.api.destroy();
        this._listeners = {};
        this.widgets = {};
        this.data = {};
        this.log('Dashboard destroyed');
    }
}

// ============================================================
// EXPORTS
// ============================================================

// Export for Node.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NexusDashboard;
}

// Export for browser
if (typeof window !== 'undefined') {
    window.NexusDashboard = NexusDashboard;
}

export default NexusDashboard;

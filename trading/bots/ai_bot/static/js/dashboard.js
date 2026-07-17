// trading/bots/ai_bot/static/js/dashboard.js
// NEXUS AI TRADING SYSTEM - Dashboard Controller
// Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

/**
 * Dashboard Controller for NEXUS AI Trading Bot
 * Manages the main dashboard interface including:
 * - Portfolio overview
 * - Real-time market data
 * - Trade execution
 * - Performance metrics
 * - AI predictions
 * - Risk management
 * - Bot controls
 * - Notifications
 */

class DashboardController {
    constructor() {
        // DOM elements
        this.elements = {};
        this.cache = {};

        // State
        this.state = {
            isConnected: false,
            isBotRunning: false,
            isTrading: false,
            currentSymbol: 'BTC-USD',
            currentTimeframe: '1h',
            position: null,
            portfolio: null,
            marketData: null,
            predictions: null,
            alerts: [],
            riskMetrics: null,
            performance: null,
            orderBook: null,
            recentTrades: [],
        };

        // Chart instances
        this.charts = {};

        // WebSocket handlers
        this.wsHandlers = {};

        // Update intervals
        this.updateIntervals = {};

        // DOM references
        this.dom = {};

        // Initialize
        this.init();

        logger.info('DashboardController initialized');
    }

    // ========================================================================
    // Initialization
    // ========================================================================

    /**
     * Initialize dashboard
     */
    init() {
        // Cache DOM elements
        this.cacheElements();

        // Initialize components
        this.initCharts();
        this.initEventListeners();
        this.initWebSocket();
        this.initModals();
        this.initTooltips();

        // Load initial data
        this.loadInitialData();

        // Start periodic updates
        this.startUpdates();

        // Setup resize handlers
        this.setupResizeHandlers();

        logger.info('Dashboard initialization complete');
    }

    /**
     * Cache DOM elements
     */
    cacheElements() {
        this.dom = {
            // Main containers
            dashboard: document.getElementById('dashboard'),
            sidebar: document.getElementById('sidebar'),
            mainContent: document.getElementById('main-content'),

            // Header
            header: document.getElementById('header'),
            title: document.getElementById('title'),
            statusBadge: document.getElementById('status-badge'),
            connectionStatus: document.getElementById('connection-status'),
            botStatus: document.getElementById('bot-status'),

            // Portfolio
            portfolioValue: document.getElementById('portfolio-value'),
            portfolioChange: document.getElementById('portfolio-change'),
            portfolioChangePercent: document.getElementById('portfolio-change-percent'),
            portfolioAssets: document.getElementById('portfolio-assets'),
            portfolioChart: document.getElementById('portfolio-chart'),

            // Market
            marketSymbol: document.getElementById('market-symbol'),
            marketPrice: document.getElementById('market-price'),
            marketChange: document.getElementById('market-change'),
            marketChangePercent: document.getElementById('market-change-percent'),
            marketHigh: document.getElementById('market-high'),
            marketLow: document.getElementById('market-low'),
            marketVolume: document.getElementById('market-volume'),
            marketChart: document.getElementById('market-chart'),

            // Trading
            orderForm: document.getElementById('order-form'),
            orderSide: document.getElementById('order-side'),
            orderType: document.getElementById('order-type'),
            orderQuantity: document.getElementById('order-quantity'),
            orderPrice: document.getElementById('order-price'),
            orderTotal: document.getElementById('order-total'),
            orderSubmit: document.getElementById('order-submit'),
            orderBookBids: document.getElementById('order-book-bids'),
            orderBookAsks: document.getElementById('order-book-asks'),
            orderHistory: document.getElementById('order-history'),

            // AI
            aiPrediction: document.getElementById('ai-prediction'),
            aiConfidence: document.getElementById('ai-confidence'),
            aiSentiment: document.getElementById('ai-sentiment'),
            aiSignal: document.getElementById('ai-signal'),
            aiIndicators: document.getElementById('ai-indicators'),

            // Risk
            riskScore: document.getElementById('risk-score'),
            riskLevel: document.getElementById('risk-level'),
            riskMetrics: document.getElementById('risk-metrics'),
            riskChart: document.getElementById('risk-chart'),

            // Bot controls
            botStartBtn: document.getElementById('bot-start'),
            botStopBtn: document.getElementById('bot-stop'),
            botPauseBtn: document.getElementById('bot-pause'),
            botResumeBtn: document.getElementById('bot-resume'),
            botStatusText: document.getElementById('bot-status-text'),
            botStats: document.getElementById('bot-stats'),

            // Performance
            performanceChart: document.getElementById('performance-chart'),
            performanceMetrics: document.getElementById('performance-metrics'),
            winRate: document.getElementById('win-rate'),
            totalTrades: document.getElementById('total-trades'),
            profitFactor: document.getElementById('profit-factor'),
            avgWin: document.getElementById('avg-win'),
            avgLoss: document.getElementById('avg-loss'),

            // Notifications
            notificationContainer: document.getElementById('notifications'),
            alertList: document.getElementById('alert-list'),

            // Modals
            settingsModal: document.getElementById('settings-modal'),
            tradeModal: document.getElementById('trade-modal'),
            confirmModal: document.getElementById('confirm-modal'),
            alertModal: document.getElementById('alert-modal'),

            // Settings
            settingsForm: document.getElementById('settings-form'),
            themeSelect: document.getElementById('theme-select'),
            timeframeSelect: document.getElementById('timeframe-select'),
            symbolsSelect: document.getElementById('symbols-select'),

            // Loading
            loadingOverlay: document.getElementById('loading-overlay'),
            loadingText: document.getElementById('loading-text'),
        };

        // Validate required elements
        const required = ['dashboard', 'portfolioValue', 'marketPrice', 'orderSubmit', 'botStartBtn'];
        const missing = required.filter(id => !this.dom[id]);
        if (missing.length > 0) {
            logger.warn('Missing DOM elements:', missing);
        }
    }

    // ========================================================================
    // Chart Initialization
    // ========================================================================

    /**
     * Initialize charts
     */
    initCharts() {
        // Market chart
        if (this.dom.marketChart) {
            this.charts.market = new NexusCharts({
                container: 'market-chart',
                symbol: this.state.currentSymbol,
                timeframe: this.state.currentTimeframe,
                theme: this.getTheme(),
            });
        }

        // Portfolio chart
        if (this.dom.portfolioChart) {
            this.charts.portfolio = new NexusCharts({
                container: 'portfolio-chart',
                symbol: this.state.currentSymbol,
                chartType: 'line',
                theme: this.getTheme(),
            });
        }

        // Performance chart
        if (this.dom.performanceChart) {
            this.charts.performance = new NexusCharts({
                container: 'performance-chart',
                symbol: this.state.currentSymbol,
                chartType: 'line',
                theme: this.getTheme(),
            });
        }

        // Risk chart
        if (this.dom.riskChart) {
            this.charts.risk = new NexusCharts({
                container: 'risk-chart',
                chartType: 'line',
                theme: this.getTheme(),
            });
        }
    }

    // ========================================================================
    // Event Listeners
    // ========================================================================

    /**
     * Initialize event listeners
     */
    initEventListeners() {
        // Bot controls
        if (this.dom.botStartBtn) {
            this.dom.botStartBtn.addEventListener('click', () => this.startBot());
        }
        if (this.dom.botStopBtn) {
            this.dom.botStopBtn.addEventListener('click', () => this.stopBot());
        }
        if (this.dom.botPauseBtn) {
            this.dom.botPauseBtn.addEventListener('click', () => this.pauseBot());
        }
        if (this.dom.botResumeBtn) {
            this.dom.botResumeBtn.addEventListener('click', () => this.resumeBot());
        }

        // Order form
        if (this.dom.orderForm) {
            this.dom.orderForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.placeOrder();
            });
        }

        if (this.dom.orderSide) {
            this.dom.orderSide.addEventListener('change', () => this.updateOrderForm());
        }
        if (this.dom.orderType) {
            this.dom.orderType.addEventListener('change', () => this.updateOrderForm());
        }
        if (this.dom.orderQuantity) {
            this.dom.orderQuantity.addEventListener('input', () => this.updateOrderForm());
        }
        if (this.dom.orderPrice) {
            this.dom.orderPrice.addEventListener('input', () => this.updateOrderForm());
        }

        // Settings
        if (this.dom.settingsForm) {
            this.dom.settingsForm.addEventListener('submit', (e) => {
                e.preventDefault();
                this.saveSettings();
            });
        }

        if (this.dom.themeSelect) {
            this.dom.themeSelect.addEventListener('change', (e) => {
                this.setTheme(e.target.value);
            });
        }

        if (this.dom.timeframeSelect) {
            this.dom.timeframeSelect.addEventListener('change', (e) => {
                this.setTimeframe(e.target.value);
            });
        }

        if (this.dom.symbolsSelect) {
            this.dom.symbolsSelect.addEventListener('change', (e) => {
                this.setSymbol(e.target.value);
            });
        }

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {
            // Ctrl+1: Focus market chart
            if (e.ctrlKey && e.key === '1') {
                e.preventDefault();
                this.focusChart('market');
            }
            // Ctrl+2: Focus order form
            if (e.ctrlKey && e.key === '2') {
                e.preventDefault();
                this.focusOrderForm();
            }
            // Ctrl+B: Toggle bot
            if (e.ctrlKey && e.key === 'b') {
                e.preventDefault();
                this.toggleBot();
            }
            // Escape: Close modals
            if (e.key === 'Escape') {
                this.closeAllModals();
            }
        });

        // Window events
        window.addEventListener('resize', this.debounce(() => this.handleResize(), 250));
        window.addEventListener('beforeunload', () => this.cleanup());

        // Auth events
        NexusAPI.onAuthEvent((event) => {
            if (event.type === 'login') {
                this.handleLogin(event.data);
            } else if (event.type === 'logout') {
                this.handleLogout();
            } else if (event.type === 'unauthorized') {
                this.handleUnauthorized();
            }
        });

        logger.debug('Event listeners initialized');
    }

    // ========================================================================
    // WebSocket Management
    // ========================================================================

    /**
     * Initialize WebSocket connection
     */
    initWebSocket() {
        // Connect to WebSocket
        this.connectWebSocket();

        // Register handlers
        this.wsHandlers = {
            'market': (data) => this.handleMarketData(data),
            'trade': (data) => this.handleTrade(data),
            'order': (data) => this.handleOrder(data),
            'position': (data) => this.handlePosition(data),
            'portfolio': (data) => this.handlePortfolio(data),
            'prediction': (data) => this.handlePrediction(data),
            'alert': (data) => this.handleAlert(data),
            'status': (data) => this.handleStatus(data),
            'performance': (data) => this.handlePerformance(data),
        };

        // Subscribe to channels
        this.subscribeToChannels();
    }

    /**
     * Connect WebSocket
     */
    async connectWebSocket() {
        try {
            await NexusAPI.connectWebSocket([
                'market',
                'trade',
                'order',
                'position',
                'portfolio',
                'prediction',
                'alert',
                'status',
                'performance',
            ]);

            this.state.isConnected = true;
            this.updateConnectionStatus();

            logger.info('WebSocket connected');
        } catch (error) {
            logger.error('WebSocket connection error:', error);
            this.state.isConnected = false;
            this.updateConnectionStatus();

            // Retry after delay
            setTimeout(() => this.connectWebSocket(), 5000);
        }
    }

    /**
     * Subscribe to WebSocket channels
     */
    subscribeToChannels() {
        // Market data
        NexusAPI.onWebSocketMessage('market', (data) => {
            this.handleMarketData(data);
        });

        // Trade updates
        NexusAPI.onWebSocketMessage('trade', (data) => {
            this.handleTrade(data);
        });

        // Order updates
        NexusAPI.onWebSocketMessage('order', (data) => {
            this.handleOrder(data);
        });

        // Position updates
        NexusAPI.onWebSocketMessage('position', (data) => {
            this.handlePosition(data);
        });

        // Portfolio updates
        NexusAPI.onWebSocketMessage('portfolio', (data) => {
            this.handlePortfolio(data);
        });

        // AI predictions
        NexusAPI.onWebSocketMessage('prediction', (data) => {
            this.handlePrediction(data);
        });

        // Alerts
        NexusAPI.onWebSocketMessage('alert', (data) => {
            this.handleAlert(data);
        });

        // Status updates
        NexusAPI.onWebSocketMessage('status', (data) => {
            this.handleStatus(data);
        });

        // Performance updates
        NexusAPI.onWebSocketMessage('performance', (data) => {
            this.handlePerformance(data);
        });
    }

    /**
     * Update connection status
     */
    updateConnectionStatus() {
        if (this.dom.connectionStatus) {
            this.dom.connectionStatus.className = `status-indicator ${this.state.isConnected ? 'connected' : 'disconnected'}`;
            this.dom.connectionStatus.textContent = this.state.isConnected ? 'Connected' : 'Disconnected';
        }
    }

    // ========================================================================
    // Data Loading
    // ========================================================================

    /**
     * Load initial data
     */
    async loadInitialData() {
        this.showLoading('Loading dashboard data...');

        try {
            // Load portfolio
            await this.loadPortfolio();

            // Load market data
            await this.loadMarketData();

            // Load predictions
            await this.loadPredictions();

            // Load risk metrics
            await this.loadRiskMetrics();

            // Load bot status
            await this.loadBotStatus();

            // Load performance
            await this.loadPerformance();

            // Load settings
            await this.loadSettings();

            this.hideLoading();

            logger.info('Initial data loaded');
        } catch (error) {
            logger.error('Error loading initial data:', error);
            this.hideLoading();
            this.showNotification('Error loading dashboard data', 'error');
        }
    }

    /**
     * Load portfolio data
     */
    async loadPortfolio() {
        try {
            const portfolio = await NexusAPI.getPortfolioSummary();
            if (portfolio) {
                this.state.portfolio = portfolio;
                this.updatePortfolioUI(portfolio);
            }

            const assets = await NexusAPI.getPortfolioAssets();
            if (assets) {
                this.updateAssetsUI(assets);
            }

            const performance = await NexusAPI.getPortfolioPerformance();
            if (performance) {
                this.updatePortfolioPerformanceUI(performance);
            }
        } catch (error) {
            logger.error('Error loading portfolio:', error);
        }
    }

    /**
     * Load market data
     */
    async loadMarketData() {
        try {
            const symbol = this.state.currentSymbol;
            const data = await NexusAPI.getMarketData(symbol, this.state.currentTimeframe);
            if (data) {
                this.state.marketData = data;
                this.updateMarketUI(data);
                this.updateOrderBook(symbol);
            }

            const price = await NexusAPI.getCurrentPrice(symbol);
            if (price) {
                this.updatePriceUI(price);
            }

            const summary = await NexusAPI.getMarketSummary(symbol);
            if (summary) {
                this.updateSummaryUI(summary);
            }
        } catch (error) {
            logger.error('Error loading market data:', error);
        }
    }

    /**
     * Load predictions
     */
    async loadPredictions() {
        try {
            const symbol = this.state.currentSymbol;
            const prediction = await NexusAPI.getPrediction(symbol);
            if (prediction) {
                this.state.predictions = prediction;
                this.updatePredictionUI(prediction);
            }

            const sentiment = await NexusAPI.getSentiment(symbol);
            if (sentiment) {
                this.updateSentimentUI(sentiment);
            }
        } catch (error) {
            logger.error('Error loading predictions:', error);
        }
    }

    /**
     * Load risk metrics
     */
    async loadRiskMetrics() {
        try {
            const params = await NexusAPI.getRiskParameters();
            if (params) {
                this.state.riskMetrics = params;
                this.updateRiskUI(params);
            }

            const symbol = this.state.currentSymbol;
            const risk = await NexusAPI.getPositionRisk(symbol);
            if (risk) {
                this.updatePositionRiskUI(risk);
            }
        } catch (error) {
            logger.error('Error loading risk metrics:', error);
        }
    }

    /**
     * Load bot status
     */
    async loadBotStatus() {
        try {
            const status = await NexusAPI.getBotStatus();
            if (status) {
                this.state.isBotRunning = status.isRunning;
                this.state.isTrading = status.isTrading;
                this.updateBotStatusUI(status);
            }

            const config = await NexusAPI.getBotConfig();
            if (config) {
                this.updateBotConfigUI(config);
            }

            const performance = await NexusAPI.getBotPerformance();
            if (performance) {
                this.updateBotPerformanceUI(performance);
            }
        } catch (error) {
            logger.error('Error loading bot status:', error);
        }
    }

    /**
     * Load performance data
     */
    async loadPerformance() {
        try {
            const performance = await NexusAPI.getBotPerformance('30d');
            if (performance) {
                this.state.performance = performance;
                this.updatePerformanceUI(performance);
            }
        } catch (error) {
            logger.error('Error loading performance:', error);
        }
    }

    /**
     * Load settings
     */
    async loadSettings() {
        try {
            const config = await NexusAPI.getBotConfig();
            if (config) {
                // Populate settings form
                this.populateSettingsForm(config);

                // Set theme
                const theme = localStorage.getItem('nexus_theme') || 'dark';
                this.setTheme(theme);
                if (this.dom.themeSelect) {
                    this.dom.themeSelect.value = theme;
                }

                // Set timeframe
                if (this.dom.timeframeSelect) {
                    this.dom.timeframeSelect.value = this.state.currentTimeframe;
                }

                // Set symbol
                if (this.dom.symbolsSelect) {
                    this.dom.symbolsSelect.value = this.state.currentSymbol;
                }
            }
        } catch (error) {
            logger.error('Error loading settings:', error);
        }
    }

    // ========================================================================
    // UI Updates
    // ========================================================================

    /**
     * Update portfolio UI
     * @param {Object} portfolio - Portfolio data
     */
    updatePortfolioUI(portfolio) {
        if (!portfolio) return;

        if (this.dom.portfolioValue) {
            this.dom.portfolioValue.textContent = NexusAPI.formatCurrency(portfolio.total_value);
        }

        if (this.dom.portfolioChange) {
            const change = portfolio.day_change || 0;
            this.dom.portfolioChange.textContent = NexusAPI.formatCurrency(change);
            this.dom.portfolioChange.className = change >= 0 ? 'positive' : 'negative';
        }

        if (this.dom.portfolioChangePercent) {
            const changePercent = portfolio.day_change_percent || 0;
            this.dom.portfolioChangePercent.textContent = NexusAPI.formatPercentage(changePercent);
            this.dom.portfolioChangePercent.className = changePercent >= 0 ? 'positive' : 'negative';
        }

        // Update portfolio chart
        if (this.charts.portfolio && portfolio.history) {
            this.charts.portfolio.loadData(portfolio.history);
        }
    }

    /**
     * Update assets UI
     * @param {Array} assets - Asset list
     */
    updateAssetsUI(assets) {
        if (!assets || !this.dom.portfolioAssets) return;

        let html = '';
        assets.forEach(asset => {
            html += `
                <div class="asset-item">
                    <div class="asset-info">
                        <span class="asset-symbol">${asset.symbol}</span>
                        <span class="asset-name">${asset.name || ''}</span>
                    </div>
                    <div class="asset-balance">
                        <span class="asset-amount">${NexusAPI.formatNumber(asset.balance, 4)}</span>
                        <span class="asset-value">${NexusAPI.formatCurrency(asset.value)}</span>
                    </div>
                    <div class="asset-change ${asset.change >= 0 ? 'positive' : 'negative'}">
                        ${NexusAPI.formatPercentage(asset.change_percent)}
                    </div>
                </div>
            `;
        });

        this.dom.portfolioAssets.innerHTML = html;
    }

    /**
     * Update market UI
     * @param {Object} data - Market data
     */
    updateMarketUI(data) {
        if (!data) return;

        if (this.dom.marketSymbol) {
            this.dom.marketSymbol.textContent = this.state.currentSymbol;
        }

        // Update chart
        if (this.charts.market && data.candles) {
            this.charts.market.loadData(null, null, data.candles);
        }

        // Update order book
        if (data.orderBook) {
            this.updateOrderBookUI(data.orderBook);
        }

        // Update recent trades
        if (data.trades) {
            this.updateRecentTradesUI(data.trades);
        }
    }

    /**
     * Update price UI
     * @param {Object} price - Price data
     */
    updatePriceUI(price) {
        if (!price) return;

        if (this.dom.marketPrice) {
            this.dom.marketPrice.textContent = NexusAPI.formatCurrency(price.price);
            this.dom.marketPrice.className = price.change >= 0 ? 'positive' : 'negative';
        }

        if (this.dom.marketChange) {
            this.dom.marketChange.textContent = NexusAPI.formatCurrency(price.change);
            this.dom.marketChange.className = price.change >= 0 ? 'positive' : 'negative';
        }

        if (this.dom.marketChangePercent) {
            this.dom.marketChangePercent.textContent = NexusAPI.formatPercentage(price.change_percent);
            this.dom.marketChangePercent.className = price.change_percent >= 0 ? 'positive' : 'negative';
        }

        // Update order form price
        if (this.dom.orderPrice) {
            this.dom.orderPrice.value = price.price;
        }
    }

    /**
     * Update summary UI
     * @param {Object} summary - Market summary
     */
    updateSummaryUI(summary) {
        if (!summary) return;

        if (this.dom.marketHigh) {
            this.dom.marketHigh.textContent = NexusAPI.formatCurrency(summary.high);
        }

        if (this.dom.marketLow) {
            this.dom.marketLow.textContent = NexusAPI.formatCurrency(summary.low);
        }

        if (this.dom.marketVolume) {
            this.dom.marketVolume.textContent = NexusAPI.formatNumber(summary.volume);
        }
    }

    /**
     * Update order book UI
     * @param {Object} orderBook - Order book data
     */
    updateOrderBookUI(orderBook) {
        if (!orderBook) return;

        // Bids
        if (this.dom.orderBookBids && orderBook.bids) {
            let bidsHtml = '';
            orderBook.bids.slice(0, 10).forEach(bid => {
                bidsHtml += `
                    <div class="order-book-row bid">
                        <span class="price">${NexusAPI.formatCurrency(bid.price)}</span>
                        <span class="size">${NexusAPI.formatNumber(bid.size)}</span>
                        <span class="total">${NexusAPI.formatNumber(bid.total)}</span>
                    </div>
                `;
            });
            this.dom.orderBookBids.innerHTML = bidsHtml;
        }

        // Asks
        if (this.dom.orderBookAsks && orderBook.asks) {
            let asksHtml = '';
            orderBook.asks.slice(0, 10).forEach(ask => {
                asksHtml += `
                    <div class="order-book-row ask">
                        <span class="price">${NexusAPI.formatCurrency(ask.price)}</span>
                        <span class="size">${NexusAPI.formatNumber(ask.size)}</span>
                        <span class="total">${NexusAPI.formatNumber(ask.total)}</span>
                    </div>
                `;
            });
            this.dom.orderBookAsks.innerHTML = asksHtml;
        }
    }

    /**
     * Update recent trades UI
     * @param {Array} trades - Recent trades
     */
    updateRecentTradesUI(trades) {
        if (!trades || !this.dom.orderHistory) return;

        let html = '';
        trades.slice(0, 20).forEach(trade => {
            html += `
                <div class="trade-row ${trade.side}">
                    <span class="time">${NexusAPI.formatDate(trade.time, 'time')}</span>
                    <span class="price">${NexusAPI.formatCurrency(trade.price)}</span>
                    <span class="size">${NexusAPI.formatNumber(trade.size)}</span>
                    <span class="side">${trade.side.toUpperCase()}</span>
                </div>
            `;
        });

        this.dom.orderHistory.innerHTML = html;
    }

    /**
     * Update prediction UI
     * @param {Object} prediction - Prediction data
     */
    updatePredictionUI(prediction) {
        if (!prediction) return;

        if (this.dom.aiPrediction) {
            const direction = prediction.direction || 'neutral';
            this.dom.aiPrediction.textContent = direction.toUpperCase();
            this.dom.aiPrediction.className = `prediction-${direction}`;
        }

        if (this.dom.aiConfidence) {
            this.dom.aiConfidence.textContent = `${(prediction.confidence * 100).toFixed(1)}%`;
        }

        if (this.dom.aiSignal) {
            const signal = prediction.signal || 'NEUTRAL';
            this.dom.aiSignal.textContent = signal;
            this.dom.aiSignal.className = `signal-${signal.toLowerCase()}`;
        }

        // Update indicators
        if (this.dom.aiIndicators && prediction.indicators) {
            let html = '';
            for (const [key, value] of Object.entries(prediction.indicators)) {
                html += `
                    <div class="indicator-item">
                        <span class="indicator-name">${key.toUpperCase()}</span>
                        <span class="indicator-value">${value.toFixed(2)}</span>
                    </div>
                `;
            }
            this.dom.aiIndicators.innerHTML = html;
        }
    }

    /**
     * Update sentiment UI
     * @param {Object} sentiment - Sentiment data
     */
    updateSentimentUI(sentiment) {
        if (!sentiment) return;

        if (this.dom.aiSentiment) {
            this.dom.aiSentiment.textContent = sentiment.sentiment || 'NEUTRAL';
            this.dom.aiSentiment.className = `sentiment-${(sentiment.sentiment || 'neutral').toLowerCase()}`;
        }
    }

    /**
     * Update risk UI
     * @param {Object} risk - Risk data
     */
    updateRiskUI(risk) {
        if (!risk) return;

        if (this.dom.riskScore) {
            const score = risk.score || 0;
            this.dom.riskScore.textContent = `${(score * 100).toFixed(0)}%`;
            this.dom.riskScore.className = this.getRiskClass(score);
        }

        if (this.dom.riskLevel) {
            this.dom.riskLevel.textContent = risk.level || 'LOW';
            this.dom.riskLevel.className = `risk-${(risk.level || 'low').toLowerCase()}`;
        }

        // Update risk metrics
        if (this.dom.riskMetrics && risk.metrics) {
            let html = '';
            for (const [key, value] of Object.entries(risk.metrics)) {
                html += `
                    <div class="risk-metric">
                        <span class="metric-name">${key.replace(/_/g, ' ').toUpperCase()}</span>
                        <span class="metric-value">${typeof value === 'number' ? value.toFixed(2) : value}</span>
                    </div>
                `;
            }
            this.dom.riskMetrics.innerHTML = html;
        }

        // Update risk chart
        if (this.charts.risk && risk.history) {
            this.charts.risk.loadData(risk.history);
        }
    }

    /**
     * Update position risk UI
     * @param {Object} risk - Position risk data
     */
    updatePositionRiskUI(risk) {
        if (!risk) return;

        // Update position risk display
        // Implementation depends on UI layout
    }

    /**
     * Update bot status UI
     * @param {Object} status - Bot status
     */
    updateBotStatusUI(status) {
        if (!status) return;

        if (this.dom.botStatusText) {
            this.dom.botStatusText.textContent = status.status || 'STOPPED';
            this.dom.botStatusText.className = `bot-status-${(status.status || 'stopped').toLowerCase()}`;
        }

        if (this.dom.botStatus) {
            this.dom.botStatus.className = `status-indicator ${status.isRunning ? 'running' : 'stopped'}`;
        }

        // Update button states
        if (this.dom.botStartBtn) {
            this.dom.botStartBtn.disabled = status.isRunning;
        }
        if (this.dom.botStopBtn) {
            this.dom.botStopBtn.disabled = !status.isRunning;
        }
        if (this.dom.botPauseBtn) {
            this.dom.botPauseBtn.disabled = !status.isRunning || status.isPaused;
        }
        if (this.dom.botResumeBtn) {
            this.dom.botResumeBtn.disabled = !status.isPaused;
        }

        this.state.isBotRunning = status.isRunning;
        this.state.isTrading = status.isTrading;
    }

    /**
     * Update bot config UI
     * @param {Object} config - Bot configuration
     */
    updateBotConfigUI(config) {
        if (!config) return;

        // Update config display
        // Implementation depends on UI layout
    }

    /**
     * Update bot performance UI
     * @param {Object} performance - Performance data
     */
    updateBotPerformanceUI(performance) {
        if (!performance) return;

        if (this.dom.botStats) {
            let html = `
                <div class="stat-item">
                    <span class="stat-label">Total P&L</span>
                    <span class="stat-value ${performance.total_pnl >= 0 ? 'positive' : 'negative'}">
                        ${NexusAPI.formatCurrency(performance.total_pnl)}
                    </span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Win Rate</span>
                    <span class="stat-value">${(performance.win_rate * 100).toFixed(1)}%</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Total Trades</span>
                    <span class="stat-value">${performance.total_trades}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Profit Factor</span>
                    <span class="stat-value">${performance.profit_factor.toFixed(2)}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Sharpe Ratio</span>
                    <span class="stat-value">${performance.sharpe_ratio.toFixed(2)}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Max Drawdown</span>
                    <span class="stat-value">${(performance.max_drawdown * 100).toFixed(1)}%</span>
                </div>
            `;
            this.dom.botStats.innerHTML = html;
        }
    }

    /**
     * Update performance UI
     * @param {Object} performance - Performance data
     */
    updatePerformanceUI(performance) {
        if (!performance) return;

        if (this.dom.winRate) {
            this.dom.winRate.textContent = `${(performance.win_rate * 100).toFixed(1)}%`;
        }

        if (this.dom.totalTrades) {
            this.dom.totalTrades.textContent = performance.total_trades;
        }

        if (this.dom.profitFactor) {
            this.dom.profitFactor.textContent = performance.profit_factor.toFixed(2);
        }

        if (this.dom.avgWin) {
            this.dom.avgWin.textContent = NexusAPI.formatCurrency(performance.avg_win);
        }

        if (this.dom.avgLoss) {
            this.dom.avgLoss.textContent = NexusAPI.formatCurrency(performance.avg_loss);
        }

        // Update performance chart
        if (this.charts.performance && performance.history) {
            this.charts.performance.loadData(performance.history);
        }
    }

    /**
     * Update order form
     */
    updateOrderForm() {
        const side = this.dom.orderSide ? this.dom.orderSide.value : 'buy';
        const type = this.dom.orderType ? this.dom.orderType.value : 'market';
        const quantity = parseFloat(this.dom.orderQuantity ? this.dom.orderQuantity.value : 0);
        const price = parseFloat(this.dom.orderPrice ? this.dom.orderPrice.value : 0);

        // Update total
        if (this.dom.orderTotal) {
            const total = type === 'market' ? quantity * (this.state.marketData?.price || 0) : quantity * price;
            this.dom.orderTotal.textContent = NexusAPI.formatCurrency(total);
        }

        // Update submit button
        if (this.dom.orderSubmit) {
            const label = `${side.toUpperCase()} ${type.toUpperCase()}`;
            this.dom.orderSubmit.textContent = label;
            this.dom.orderSubmit.className = `btn btn-${side}`;
            this.dom.orderSubmit.disabled = quantity <= 0 || (type !== 'market' && price <= 0);
        }
    }

    /**
     * Get risk class
     * @param {number} score - Risk score (0-1)
     * @returns {string} CSS class
     */
    getRiskClass(score) {
        if (score >= 0.8) return 'risk-critical';
        if (score >= 0.6) return 'risk-high';
        if (score >= 0.4) return 'risk-medium';
        if (score >= 0.2) return 'risk-low';
        return 'risk-very-low';
    }

    // ========================================================================
    // Actions
    // ========================================================================

    /**
     * Place an order
     */
    async placeOrder() {
        const side = this.dom.orderSide ? this.dom.orderSide.value : 'buy';
        const type = this.dom.orderType ? this.dom.orderType.value : 'market';
        const quantity = parseFloat(this.dom.orderQuantity ? this.dom.orderQuantity.value : 0);
        const price = parseFloat(this.dom.orderPrice ? this.dom.orderPrice.value : 0);

        if (quantity <= 0) {
            this.showNotification('Invalid quantity', 'error');
            return;
        }

        if (type !== 'market' && price <= 0) {
            this.showNotification('Invalid price', 'error');
            return;
        }

        try {
            const order = {
                symbol: this.state.currentSymbol,
                side: side,
                type: type,
                quantity: quantity,
                price: type !== 'market' ? price : undefined,
            };

            const result = await NexusAPI.placeOrder(order);
            if (result && result.success) {
                this.showNotification(`Order placed: ${side.toUpperCase()} ${quantity} ${this.state.currentSymbol}`, 'success');
                this.resetOrderForm();
                this.loadPortfolio();
            } else {
                this.showNotification(result.message || 'Order failed', 'error');
            }
        } catch (error) {
            logger.error('Error placing order:', error);
            this.showNotification('Error placing order', 'error');
        }
    }

    /**
     * Reset order form
     */
    resetOrderForm() {
        if (this.dom.orderQuantity) this.dom.orderQuantity.value = '';
        if (this.dom.orderPrice) this.dom.orderPrice.value = '';
        if (this.dom.orderTotal) this.dom.orderTotal.textContent = '$0.00';
        this.updateOrderForm();
    }

    /**
     * Start the bot
     */
    async startBot() {
        try {
            this.showLoading('Starting bot...');
            const config = await NexusAPI.getBotConfig();
            const result = await NexusAPI.startBot(config);
            if (result && result.success) {
                this.showNotification('Bot started successfully', 'success');
                this.loadBotStatus();
                this.loadPerformance();
            } else {
                this.showNotification(result.message || 'Failed to start bot', 'error');
            }
        } catch (error) {
            logger.error('Error starting bot:', error);
            this.showNotification('Error starting bot', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Stop the bot
     */
    async stopBot() {
        try {
            const confirmed = await this.showConfirm('Stop Bot', 'Are you sure you want to stop the trading bot?');
            if (!confirmed) return;

            this.showLoading('Stopping bot...');
            const result = await NexusAPI.stopBot();
            if (result && result.success) {
                this.showNotification('Bot stopped', 'success');
                this.loadBotStatus();
            } else {
                this.showNotification(result.message || 'Failed to stop bot', 'error');
            }
        } catch (error) {
            logger.error('Error stopping bot:', error);
            this.showNotification('Error stopping bot', 'error');
        } finally {
            this.hideLoading();
        }
    }

    /**
     * Pause the bot
     */
    async pauseBot() {
        try {
            const result = await NexusAPI.pauseBot();
            if (result && result.success) {
                this.showNotification('Bot paused', 'success');
                this.loadBotStatus();
            } else {
                this.showNotification(result.message || 'Failed to pause bot', 'error');
            }
        } catch (error) {
            logger.error('Error pausing bot:', error);
            this.showNotification('Error pausing bot', 'error');
        }
    }

    /**
     * Resume the bot
     */
    async resumeBot() {
        try {
            const result = await NexusAPI.resumeBot();
            if (result && result.success) {
                this.showNotification('Bot resumed', 'success');
                this.loadBotStatus();
            } else {
                this.showNotification(result.message || 'Failed to resume bot', 'error');
            }
        } catch (error) {
            logger.error('Error resuming bot:', error);
            this.showNotification('Error resuming bot', 'error');
        }
    }

    /**
     * Toggle bot (start/stop)
     */
    async toggleBot() {
        if (this.state.isBotRunning) {
            await this.stopBot();
        } else {
            await this.startBot();
        }
    }

    // ========================================================================
    // Settings
    // ========================================================================

    /**
     * Save settings
     */
    async saveSettings() {
        try {
            const formData = new FormData(this.dom.settingsForm);
            const settings = Object.fromEntries(formData.entries());

            const result = await NexusAPI.updateBotConfig(settings);
            if (result && result.success) {
                this.showNotification('Settings saved', 'success');
                this.closeModal('settings');
                this.loadBotStatus();
            } else {
                this.showNotification(result.message || 'Failed to save settings', 'error');
            }
        } catch (error) {
            logger.error('Error saving settings:', error);
            this.showNotification('Error saving settings', 'error');
        }
    }

    /**
     * Populate settings form
     * @param {Object} config - Bot configuration
     */
    populateSettingsForm(config) {
        if (!config || !this.dom.settingsForm) return;

        for (const [key, value] of Object.entries(config)) {
            const input = this.dom.settingsForm.querySelector(`[name="${key}"]`);
            if (input) {
                if (input.type === 'checkbox') {
                    input.checked = value;
                } else {
                    input.value = value;
                }
            }
        }
    }

    /**
     * Set theme
     * @param {string} theme - Theme name
     */
    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        localStorage.setItem('nexus_theme', theme);

        // Update charts
        for (const chart of Object.values(this.charts)) {
            if (chart && chart.setTheme) {
                chart.setTheme(theme);
            }
        }
    }

    /**
     * Get current theme
     * @returns {string} Theme name
     */
    getTheme() {
        return localStorage.getItem('nexus_theme') || 'dark';
    }

    /**
     * Set timeframe
     * @param {string} timeframe - Timeframe
     */
    setTimeframe(timeframe) {
        this.state.currentTimeframe = timeframe;
        if (this.charts.market) {
            this.charts.market.setTimeframe(timeframe);
        }
    }

    /**
     * Set symbol
     * @param {string} symbol - Trading pair
     */
    setSymbol(symbol) {
        this.state.currentSymbol = symbol;
        if (this.charts.market) {
            this.charts.market.setSymbol(symbol);
        }
        this.loadMarketData();
        this.loadPredictions();
        this.loadRiskMetrics();
    }

    // ========================================================================
    // Modal Management
    // ========================================================================

    /**
     * Initialize modals
     */
    initModals() {
        // Close modals on overlay click
        document.querySelectorAll('.modal-overlay').forEach(overlay => {
            overlay.addEventListener('click', (e) => {
                if (e.target === overlay) {
                    this.closeModal(overlay.dataset.modal);
                }
            });
        });

        // Close modals on cancel/close buttons
        document.querySelectorAll('.modal-close, .modal-cancel').forEach(btn => {
            btn.addEventListener('click', () => {
                const modal = btn.closest('.modal-overlay');
                if (modal) {
                    this.closeModal(modal.dataset.modal);
                }
            });
        });
    }

    /**
     * Show modal
     * @param {string} id - Modal ID
     */
    showModal(id) {
        const modal = document.getElementById(id);
        if (modal) {
            modal.classList.add('active');
            document.body.style.overflow = 'hidden';
        }
    }

    /**
     * Close modal
     * @param {string} id - Modal ID
     */
    closeModal(id) {
        const modal = document.getElementById(id);
        if (modal) {
            modal.classList.remove('active');
            document.body.style.overflow = '';
        }
    }

    /**
     * Close all modals
     */
    closeAllModals() {
        document.querySelectorAll('.modal-overlay.active').forEach(modal => {
            modal.classList.remove('active');
        });
        document.body.style.overflow = '';
    }

    /**
     * Show confirm dialog
     * @param {string} title - Dialog title
     * @param {string} message - Dialog message
     * @returns {Promise<boolean>} User confirmed
     */
    showConfirm(title, message) {
        return new Promise((resolve) => {
            const modal = this.dom.confirmModal;
            if (!modal) {
                resolve(window.confirm(message));
                return;
            }

            modal.querySelector('.modal-title').textContent = title;
            modal.querySelector('.modal-body').textContent = message;

            const confirmBtn = modal.querySelector('.confirm-btn');
            const cancelBtn = modal.querySelector('.cancel-btn');

            const cleanup = () => {
                confirmBtn.removeEventListener('click', onConfirm);
                cancelBtn.removeEventListener('click', onCancel);
                this.closeModal('confirm-modal');
            };

            const onConfirm = () => {
                cleanup();
                resolve(true);
            };

            const onCancel = () => {
                cleanup();
                resolve(false);
            };

            confirmBtn.addEventListener('click', onConfirm);
            cancelBtn.addEventListener('click', onCancel);

            this.showModal('confirm-modal');
        });
    }

    // ========================================================================
    // Notifications
    // ========================================================================

    /**
     * Initialize tooltips
     */
    initTooltips() {
        document.querySelectorAll('[data-tooltip]').forEach(element => {
            element.addEventListener('mouseenter', (e) => {
                const tooltip = document.createElement('div');
                tooltip.className = 'tooltip';
                tooltip.textContent = element.dataset.tooltip;
                tooltip.style.position = 'absolute';
                tooltip.style.zIndex = '1000';
                tooltip.style.padding = '4px 8px';
                tooltip.style.borderRadius = '4px';
                tooltip.style.background = '#333';
                tooltip.style.color = '#fff';
                tooltip.style.fontSize = '12px';
                tooltip.style.pointerEvents = 'none';
                tooltip.style.whiteSpace = 'nowrap';

                const rect = element.getBoundingClientRect();
                tooltip.style.left = `${rect.left + rect.width / 2 - tooltip.offsetWidth / 2}px`;
                tooltip.style.top = `${rect.top - tooltip.offsetHeight - 5}px`;

                document.body.appendChild(tooltip);
                element._tooltip = tooltip;
            });

            element.addEventListener('mouseleave', (e) => {
                if (element._tooltip) {
                    element._tooltip.remove();
                    element._tooltip = null;
                }
            });
        });
    }

    /**
     * Show notification
     * @param {string} message - Notification message
     * @param {string} type - Notification type (success, error, warning, info)
     * @param {number} duration - Duration in ms
     */
    showNotification(message, type = 'info', duration = 5000) {
        const container = this.dom.notificationContainer;
        if (!container) {
            console.warn('Notification container not found');
            return;
        }

        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.innerHTML = `
            <span class="notification-icon">${this.getNotificationIcon(type)}</span>
            <span class="notification-message">${message}</span>
            <button class="notification-close">&times;</button>
        `;

        container.appendChild(notification);

        // Auto-remove after duration
        const timeout = setTimeout(() => {
            notification.remove();
        }, duration);

        // Close button
        notification.querySelector('.notification-close').addEventListener('click', () => {
            clearTimeout(timeout);
            notification.remove();
        });

        // Show with animation
        requestAnimationFrame(() => {
            notification.classList.add('show');
        });
    }

    /**
     * Get notification icon
     * @param {string} type - Notification type
     * @returns {string} Icon
     */
    getNotificationIcon(type) {
        const icons = {
            success: '✓',
            error: '✗',
            warning: '⚠',
            info: 'ℹ',
        };
        return icons[type] || icons.info;
    }

    // ========================================================================
    // Loading Management
    // ========================================================================

    /**
     * Show loading overlay
     * @param {string} text - Loading text
     */
    showLoading(text = 'Loading...') {
        if (this.dom.loadingOverlay) {
            if (this.dom.loadingText) {
                this.dom.loadingText.textContent = text;
            }
            this.dom.loadingOverlay.classList.add('active');
        }
    }

    /**
     * Hide loading overlay
     */
    hideLoading() {
        if (this.dom.loadingOverlay) {
            this.dom.loadingOverlay.classList.remove('active');
        }
    }

    // ========================================================================
    // WebSocket Handlers
    // ========================================================================

    /**
     * Handle market data
     * @param {Object} data - Market data
     */
    handleMarketData(data) {
        if (data.symbol === this.state.currentSymbol) {
            this.updatePriceUI(data);
            this.updateSummaryUI(data);
            if (this.charts.market && data.candle) {
                this.charts.market.updateLastCandle(data.candle);
            }
        }
    }

    /**
     * Handle trade data
     * @param {Object} data - Trade data
     */
    handleTrade(data) {
        // Update recent trades
        if (this.dom.orderHistory) {
            const row = document.createElement('div');
            row.className = `trade-row ${data.side}`;
            row.innerHTML = `
                <span class="time">${NexusAPI.formatDate(data.time, 'time')}</span>
                <span class="price">${NexusAPI.formatCurrency(data.price)}</span>
                <span class="size">${NexusAPI.formatNumber(data.size)}</span>
                <span class="side">${data.side.toUpperCase()}</span>
            `;
            this.dom.orderHistory.insertBefore(row, this.dom.orderHistory.firstChild);

            // Limit history
            while (this.dom.orderHistory.children.length > 100) {
                this.dom.orderHistory.removeChild(this.dom.orderHistory.lastChild);
            }
        }

        // Update portfolio
        this.loadPortfolio();
    }

    /**
     * Handle order data
     * @param {Object} data - Order data
     */
    handleOrder(data) {
        this.showNotification(
            `Order ${data.status}: ${data.side.toUpperCase()} ${data.quantity} ${data.symbol}`,
            data.status === 'filled' ? 'success' : 'info'
        );
    }

    /**
     * Handle position data
     * @param {Object} data - Position data
     */
    handlePosition(data) {
        this.state.position = data;
        this.updatePositionRiskUI(data);
    }

    /**
     * Handle portfolio data
     * @param {Object} data - Portfolio data
     */
    handlePortfolio(data) {
        this.state.portfolio = data;
        this.updatePortfolioUI(data);
        this.updateAssetsUI(data.assets);
        this.updatePortfolioPerformanceUI(data.performance);
    }

    /**
     * Handle prediction data
     * @param {Object} data - Prediction data
     */
    handlePrediction(data) {
        if (data.symbol === this.state.currentSymbol) {
            this.updatePredictionUI(data);
            this.updateSentimentUI(data.sentiment);
        }
    }

    /**
     * Handle alert data
     * @param {Object} data - Alert data
     */
    handleAlert(data) {
        this.state.alerts.push(data);
        this.showNotification(data.message, data.severity || 'info');
        this.updateAlertList();
    }

    /**
     * Handle status data
     * @param {Object} data - Status data
     */
    handleStatus(data) {
        this.updateBotStatusUI(data);
    }

    /**
     * Handle performance data
     * @param {Object} data - Performance data
     */
    handlePerformance(data) {
        this.state.performance = data;
        this.updatePerformanceUI(data);
        this.updateBotPerformanceUI(data);
    }

    /**
     * Update alert list
     */
    updateAlertList() {
        if (!this.dom.alertList) return;

        let html = '';
        this.state.alerts.slice(-20).reverse().forEach(alert => {
            html += `
                <div class="alert-item alert-${alert.severity || 'info'}">
                    <span class="alert-time">${NexusAPI.formatDate(alert.time, 'time')}</span>
                    <span class="alert-message">${alert.message}</span>
                    <button class="alert-dismiss" data-alert-id="${alert.id}">&times;</button>
                </div>
            `;
        });

        this.dom.alertList.innerHTML = html;

        // Add dismiss handlers
        this.dom.alertList.querySelectorAll('.alert-dismiss').forEach(btn => {
            btn.addEventListener('click', () => {
                const id = btn.dataset.alertId;
                this.dismissAlert(id);
            });
        });
    }

    /**
     * Dismiss alert
     * @param {string} id - Alert ID
     */
    dismissAlert(id) {
        this.state.alerts = this.state.alerts.filter(a => a.id !== id);
        this.updateAlertList();
    }

    // ========================================================================
    // Utility Methods
    // ========================================================================

    /**
     * Start periodic updates
     */
    startUpdates() {
        // Market data
        this.updateIntervals.market = setInterval(() => {
            if (this.state.isConnected) {
                this.loadMarketData();
            }
        }, 5000);

        // Portfolio
        this.updateIntervals.portfolio = setInterval(() => {
            this.loadPortfolio();
        }, 30000);

        // Predictions
        this.updateIntervals.predictions = setInterval(() => {
            this.loadPredictions();
        }, 60000);

        // Performance
        this.updateIntervals.performance = setInterval(() => {
            this.loadPerformance();
        }, 60000);

        // Bot status
        this.updateIntervals.botStatus = setInterval(() => {
            this.loadBotStatus();
        }, 15000);
    }

    /**
     * Stop periodic updates
     */
    stopUpdates() {
        for (const interval of Object.values(this.updateIntervals)) {
            clearInterval(interval);
        }
        this.updateIntervals = {};
    }

    /**
     * Setup resize handlers
     */
    setupResizeHandlers() {
        this.handleResize();
    }

    /**
     * Handle resize
     */
    handleResize() {
        // Resize charts
        for (const chart of Object.values(this.charts)) {
            if (chart && chart.resizeChart) {
                chart.resizeChart();
            }
        }

        // Update UI
        this.updateOrderForm();
    }

    /**
     * Focus chart
     * @param {string} name - Chart name
     */
    focusChart(name) {
        const chart = this.charts[name];
        if (chart && chart.mainChartElement) {
            chart.mainChartElement.scrollIntoView({ behavior: 'smooth' });
            chart.mainChartElement.focus();
        }
    }

    /**
     * Focus order form
     */
    focusOrderForm() {
        if (this.dom.orderForm) {
            this.dom.orderForm.scrollIntoView({ behavior: 'smooth' });
            if (this.dom.orderQuantity) {
                this.dom.orderQuantity.focus();
            }
        }
    }

    /**
     * Debounce function
     * @param {Function} fn - Function to debounce
     * @param {number} delay - Delay in ms
     * @returns {Function} Debounced function
     */
    debounce(fn, delay) {
        let timer;
        return (...args) => {
            clearTimeout(timer);
            timer = setTimeout(() => fn.apply(this, args), delay);
        };
    }

    /**
     * Handle login
     * @param {Object} data - Login data
     */
    handleLogin(data) {
        this.state.isConnected = true;
        this.updateConnectionStatus();
        this.loadInitialData();
        this.connectWebSocket();
    }

    /**
     * Handle logout
     */
    handleLogout() {
        this.state.isConnected = false;
        this.updateConnectionStatus();
        this.stopUpdates();
        this.disconnectWebSocket();
        this.clearUI();
        window.location.href = '/login';
    }

    /**
     * Handle unauthorized
     */
    handleUnauthorized() {
        this.showNotification('Session expired. Please login again.', 'error');
        setTimeout(() => {
            window.location.href = '/login';
        }, 3000);
    }

    /**
     * Clear UI
     */
    clearUI() {
        // Reset all UI elements
        this.state = {
            ...this.state,
            portfolio: null,
            marketData: null,
            predictions: null,
            performance: null,
        };

        // Clear displays
        if (this.dom.portfolioValue) this.dom.portfolioValue.textContent = '$0.00';
        if (this.dom.marketPrice) this.dom.marketPrice.textContent = '-';
        if (this.dom.botStatusText) this.dom.botStatusText.textContent = 'DISCONNECTED';
    }

    /**
     * Disconnect WebSocket
     */
    disconnectWebSocket() {
        NexusAPI.disconnectWebSocket();
        this.state.isConnected = false;
        this.updateConnectionStatus();
    }

    /**
     * Cleanup
     */
    cleanup() {
        this.stopUpdates();
        this.disconnectWebSocket();

        // Destroy charts
        for (const [key, chart] of Object.entries(this.charts)) {
            if (chart && chart.destroy) {
                chart.destroy();
                this.charts[key] = null;
            }
        }

        // Clear event listeners
        // (Would need to track listeners for proper cleanup)
    }
}

// Initialize dashboard on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new DashboardController();
});

// Simple logger
const logger = {
    debug: (...args) => console.debug('[DEBUG]', ...args),
    info: (...args) => console.info('[INFO]', ...args),
    warn: (...args) => console.warn('[WARN]', ...args),
    error: (...args) => console.error('[ERROR]', ...args),
};

export default DashboardController;

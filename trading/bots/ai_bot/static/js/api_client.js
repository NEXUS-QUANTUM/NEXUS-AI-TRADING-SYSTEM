// trading/bots/ai_bot/static/js/api_client.js
// NEXUS AI TRADING SYSTEM - AI Bot API Client
// Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

/**
 * API Client for NEXUS AI Trading Bot
 * Handles all communication with backend services including:
 * - Authentication
 * - Market data
 * - Trading operations
 * - AI predictions
 * - Portfolio management
 * - Risk management
 * - WebSocket connections
 */

class NexusAPIClient {
    constructor(config = {}) {
        this.baseUrl = config.baseUrl || window.location.origin;
        this.apiVersion = config.apiVersion || 'v1';
        this.timeout = config.timeout || 30000;
        this.retryAttempts = config.retryAttempts || 3;
        this.retryDelay = config.retryDelay || 1000;
        this.websocketReconnectDelay = config.websocketReconnectDelay || 3000;
        this.maxWebsocketReconnects = config.maxWebsocketReconnects || 10;

        // State
        this.accessToken = localStorage.getItem('nexus_access_token') || null;
        this.refreshToken = localStorage.getItem('nexus_refresh_token') || null;
        this.ws = null;
        this.wsReconnectAttempts = 0;
        this.wsHandlers = new Map();
        this.wsIsConnecting = false;
        this.requestQueue = [];
        this.isProcessingQueue = false;
        this.apiBaseUrl = `${this.baseUrl}/api/${this.apiVersion}`;
        this.wsBaseUrl = this.baseUrl.replace('http', 'ws');

        // Event listeners
        this.eventListeners = new Map();
        this.authListeners = [];

        // Request interceptors
        this.requestInterceptors = [];
        this.responseInterceptors = [];

        logger.info('NexusAPIClient initialized', { baseUrl: this.baseUrl, apiVersion: this.apiVersion });
    }

    // ========================================================================
    // Authentication Methods
    // ========================================================================

    /**
     * Authenticate user with email and password
     * @param {string} email - User email
     * @param {string} password - User password
     * @param {boolean} rememberMe - Remember me flag
     * @returns {Promise<Object>} Authentication response
     */
    async login(email, password, rememberMe = false) {
        try {
            const response = await this.request('/auth/login', {
                method: 'POST',
                body: JSON.stringify({ email, password, rememberMe }),
            });

            if (response.success) {
                this.setTokens(response.access_token, response.refresh_token);
                this.emitAuthEvent('login', response);
                return response;
            }
            throw new Error(response.message || 'Login failed');
        } catch (error) {
            logger.error('Login error:', error);
            throw error;
        }
    }

    /**
     * Authenticate user with social provider
     * @param {string} provider - Provider name (google, github, telegram)
     * @param {string} token - OAuth token
     * @returns {Promise<Object>} Authentication response
     */
    async socialLogin(provider, token) {
        try {
            const response = await this.request('/auth/social-login', {
                method: 'POST',
                body: JSON.stringify({ provider, token }),
            });

            if (response.success) {
                this.setTokens(response.access_token, response.refresh_token);
                this.emitAuthEvent('login', response);
                return response;
            }
            throw new Error(response.message || 'Social login failed');
        } catch (error) {
            logger.error('Social login error:', error);
            throw error;
        }
    }

    /**
     * Logout user
     * @returns {Promise<void>}
     */
    async logout() {
        try {
            await this.request('/auth/logout', {
                method: 'POST',
            });
        } catch (error) {
            logger.warn('Logout error (ignored):', error);
        } finally {
            this.clearTokens();
            this.disconnectWebSocket();
            this.emitAuthEvent('logout', null);
            // Clear all caches
            this.clearCache();
        }
    }

    /**
     * Refresh access token
     * @returns {Promise<Object>} Token refresh response
     */
    async refreshToken() {
        if (!this.refreshToken) {
            throw new Error('No refresh token available');
        }

        try {
            const response = await this.request('/auth/refresh', {
                method: 'POST',
                body: JSON.stringify({ refresh_token: this.refreshToken }),
                skipAuth: true,
            });

            if (response.success) {
                this.setTokens(response.access_token, response.refresh_token || this.refreshToken);
                return response;
            }
            throw new Error('Token refresh failed');
        } catch (error) {
            logger.error('Token refresh error:', error);
            this.clearTokens();
            throw error;
        }
    }

    /**
     * Register new user
     * @param {Object} userData - User registration data
     * @returns {Promise<Object>} Registration response
     */
    async register(userData) {
        try {
            const response = await this.request('/auth/register', {
                method: 'POST',
                body: JSON.stringify(userData),
                skipAuth: true,
            });

            if (response.success) {
                return response;
            }
            throw new Error(response.message || 'Registration failed');
        } catch (error) {
            logger.error('Registration error:', error);
            throw error;
        }
    }

    /**
     * Verify email
     * @param {string} token - Verification token
     * @returns {Promise<Object>} Verification response
     */
    async verifyEmail(token) {
        try {
            const response = await this.request('/auth/verify-email', {
                method: 'POST',
                body: JSON.stringify({ token }),
                skipAuth: true,
            });

            if (response.success) {
                return response;
            }
            throw new Error(response.message || 'Email verification failed');
        } catch (error) {
            logger.error('Email verification error:', error);
            throw error;
        }
    }

    /**
     * Request password reset
     * @param {string} email - User email
     * @returns {Promise<Object>} Reset request response
     */
    async requestPasswordReset(email) {
        try {
            const response = await this.request('/auth/request-reset', {
                method: 'POST',
                body: JSON.stringify({ email }),
                skipAuth: true,
            });

            return response;
        } catch (error) {
            logger.error('Password reset request error:', error);
            throw error;
        }
    }

    /**
     * Reset password
     * @param {string} token - Reset token
     * @param {string} newPassword - New password
     * @returns {Promise<Object>} Reset response
     */
    async resetPassword(token, newPassword) {
        try {
            const response = await this.request('/auth/reset-password', {
                method: 'POST',
                body: JSON.stringify({ token, newPassword }),
                skipAuth: true,
            });

            if (response.success) {
                return response;
            }
            throw new Error(response.message || 'Password reset failed');
        } catch (error) {
            logger.error('Password reset error:', error);
            throw error;
        }
    }

    /**
     * Enable 2FA
     * @param {string} code - 2FA code
     * @returns {Promise<Object>} 2FA enable response
     */
    async enable2FA(code) {
        try {
            const response = await this.request('/auth/enable-2fa', {
                method: 'POST',
                body: JSON.stringify({ code }),
            });

            if (response.success) {
                return response;
            }
            throw new Error(response.message || '2FA enable failed');
        } catch (error) {
            logger.error('2FA enable error:', error);
            throw error;
        }
    }

    /**
     * Verify 2FA
     * @param {string} code - 2FA code
     * @returns {Promise<Object>} 2FA verify response
     */
    async verify2FA(code) {
        try {
            const response = await this.request('/auth/verify-2fa', {
                method: 'POST',
                body: JSON.stringify({ code }),
            });

            if (response.success) {
                return response;
            }
            throw new Error(response.message || '2FA verification failed');
        } catch (error) {
            logger.error('2FA verification error:', error);
            throw error;
        }
    }

    /**
     * Get current user profile
     * @param {boolean} forceRefresh - Force refresh from server
     * @returns {Promise<Object>} User profile
     */
    async getProfile(forceRefresh = false) {
        const cacheKey = 'user_profile';
        
        if (!forceRefresh && this._cache && this._cache[cacheKey]) {
            return this._cache[cacheKey];
        }

        try {
            const response = await this.request('/auth/profile');
            if (response.success) {
                this._cache = this._cache || {};
                this._cache[cacheKey] = response.data;
                return response.data;
            }
            throw new Error(response.message || 'Failed to get profile');
        } catch (error) {
            logger.error('Get profile error:', error);
            throw error;
        }
    }

    /**
     * Update user profile
     * @param {Object} updates - Profile updates
     * @returns {Promise<Object>} Updated profile
     */
    async updateProfile(updates) {
        try {
            const response = await this.request('/auth/profile', {
                method: 'PUT',
                body: JSON.stringify(updates),
            });

            if (response.success) {
                this._cache = this._cache || {};
                this._cache['user_profile'] = response.data;
                return response.data;
            }
            throw new Error(response.message || 'Profile update failed');
        } catch (error) {
            logger.error('Profile update error:', error);
            throw error;
        }
    }

    // ========================================================================
    // Market Data Methods
    // ========================================================================

    /**
     * Get market data for a symbol
     * @param {string} symbol - Trading pair symbol
     * @param {string} timeframe - Timeframe (1m, 5m, 15m, 1h, 4h, 1d, 1w)
     * @param {number} limit - Number of candles
     * @returns {Promise<Object>} Market data
     */
    async getMarketData(symbol, timeframe = '1h', limit = 100) {
        try {
            const response = await this.request('/market/data', {
                params: { symbol, timeframe, limit },
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get market data');
        } catch (error) {
            logger.error('Get market data error:', error);
            throw error;
        }
    }

    /**
     * Get current price for a symbol
     * @param {string} symbol - Trading pair symbol
     * @returns {Promise<Object>} Current price data
     */
    async getCurrentPrice(symbol) {
        try {
            const response = await this.request('/market/price', {
                params: { symbol },
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get price');
        } catch (error) {
            logger.error('Get price error:', error);
            throw error;
        }
    }

    /**
     * Get order book for a symbol
     * @param {string} symbol - Trading pair symbol
     * @param {number} depth - Order book depth
     * @returns {Promise<Object>} Order book data
     */
    async getOrderBook(symbol, depth = 20) {
        try {
            const response = await this.request('/market/orderbook', {
                params: { symbol, depth },
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get order book');
        } catch (error) {
            logger.error('Get order book error:', error);
            throw error;
        }
    }

    /**
     * Get market summary for a symbol
     * @param {string} symbol - Trading pair symbol
     * @returns {Promise<Object>} Market summary
     */
    async getMarketSummary(symbol) {
        try {
            const response = await this.request('/market/summary', {
                params: { symbol },
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get market summary');
        } catch (error) {
            logger.error('Get market summary error:', error);
            throw error;
        }
    }

    /**
     * Get all available symbols
     * @returns {Promise<Array>} List of symbols
     */
    async getSymbols() {
        try {
            const response = await this.request('/market/symbols');

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get symbols');
        } catch (error) {
            logger.error('Get symbols error:', error);
            throw error;
        }
    }

    /**
     * Get market news
     * @param {string} symbol - Trading pair symbol (optional)
     * @param {number} limit - Number of news items
     * @returns {Promise<Array>} News items
     */
    async getMarketNews(symbol, limit = 10) {
        try {
            const response = await this.request('/market/news', {
                params: { symbol, limit },
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get news');
        } catch (error) {
            logger.error('Get news error:', error);
            throw error;
        }
    }

    // ========================================================================
    // Trading Methods
    // ========================================================================

    /**
     * Place a trade order
     * @param {Object} order - Order parameters
     * @param {string} order.symbol - Trading pair symbol
     * @param {string} order.side - buy or sell
     * @param {string} order.type - market, limit, stop, stop_limit
     * @param {number} order.quantity - Order quantity
     * @param {number} order.price - Price for limit orders
     * @param {number} order.stopPrice - Stop price for stop orders
     * @param {string} order.timeInForce - GTC, IOC, FOK
     * @param {string} order.clientOrderId - Client order ID
     * @returns {Promise<Object>} Order response
     */
    async placeOrder(order) {
        try {
            const response = await this.request('/trading/orders', {
                method: 'POST',
                body: JSON.stringify(order),
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to place order');
        } catch (error) {
            logger.error('Place order error:', error);
            throw error;
        }
    }

    /**
     * Cancel an order
     * @param {string} orderId - Order ID
     * @param {string} symbol - Trading pair symbol
     * @returns {Promise<Object>} Cancellation response
     */
    async cancelOrder(orderId, symbol) {
        try {
            const response = await this.request('/trading/orders', {
                method: 'DELETE',
                body: JSON.stringify({ orderId, symbol }),
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to cancel order');
        } catch (error) {
            logger.error('Cancel order error:', error);
            throw error;
        }
    }

    /**
     * Get all open orders
     * @param {string} symbol - Trading pair symbol (optional)
     * @returns {Promise<Array>} List of open orders
     */
    async getOpenOrders(symbol = null) {
        try {
            const response = await this.request('/trading/orders/open', {
                params: { symbol },
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get open orders');
        } catch (error) {
            logger.error('Get open orders error:', error);
            throw error;
        }
    }

    /**
     * Get order history
     * @param {string} symbol - Trading pair symbol (optional)
     * @param {number} limit - Number of orders
     * @param {number} offset - Pagination offset
     * @returns {Promise<Object>} Order history
     */
    async getOrderHistory(symbol = null, limit = 100, offset = 0) {
        try {
            const response = await this.request('/trading/orders/history', {
                params: { symbol, limit, offset },
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get order history');
        } catch (error) {
            logger.error('Get order history error:', error);
            throw error;
        }
    }

    /**
     * Get order details
     * @param {string} orderId - Order ID
     * @returns {Promise<Object>} Order details
     */
    async getOrderDetails(orderId) {
        try {
            const response = await this.request(`/trading/orders/${orderId}`);

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get order details');
        } catch (error) {
            logger.error('Get order details error:', error);
            throw error;
        }
    }

    /**
     * Get trade history
     * @param {string} symbol - Trading pair symbol (optional)
     * @param {number} limit - Number of trades
     * @param {number} offset - Pagination offset
     * @returns {Promise<Array>} Trade history
     */
    async getTradeHistory(symbol = null, limit = 100, offset = 0) {
        try {
            const response = await this.request('/trading/trades', {
                params: { symbol, limit, offset },
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get trade history');
        } catch (error) {
            logger.error('Get trade history error:', error);
            throw error;
        }
    }

    /**
     * Get position information
     * @param {string} symbol - Trading pair symbol (optional)
     * @returns {Promise<Array>} Position information
     */
    async getPositions(symbol = null) {
        try {
            const response = await this.request('/trading/positions', {
                params: { symbol },
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get positions');
        } catch (error) {
            logger.error('Get positions error:', error);
            throw error;
        }
    }

    // ========================================================================
    // AI Prediction Methods
    // ========================================================================

    /**
     * Get AI prediction for a symbol
     * @param {string} symbol - Trading pair symbol
     * @param {string} timeframe - Timeframe (1h, 4h, 1d, etc.)
     * @param {string} model - Model name (optional)
     * @returns {Promise<Object>} AI prediction
     */
    async getPrediction(symbol, timeframe = '1h', model = null) {
        try {
            const response = await this.request('/ai/predictions', {
                params: { symbol, timeframe, model },
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get prediction');
        } catch (error) {
            logger.error('Get prediction error:', error);
            throw error;
        }
    }

    /**
     * Get multiple AI predictions
     * @param {Array} requests - Array of prediction requests
     * @returns {Promise<Array>} List of predictions
     */
    async getBatchPredictions(requests) {
        try {
            const response = await this.request('/ai/predictions/batch', {
                method: 'POST',
                body: JSON.stringify({ requests }),
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get batch predictions');
        } catch (error) {
            logger.error('Get batch predictions error:', error);
            throw error;
        }
    }

    /**
     * Get AI sentiment analysis
     * @param {string} symbol - Trading pair symbol
     * @returns {Promise<Object>} Sentiment analysis
     */
    async getSentiment(symbol) {
        try {
            const response = await this.request('/ai/sentiment', {
                params: { symbol },
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get sentiment');
        } catch (error) {
            logger.error('Get sentiment error:', error);
            throw error;
        }
    }

    /**
     * Get AI model performance
     * @param {string} model - Model name
     * @param {string} symbol - Trading pair symbol (optional)
     * @returns {Promise<Object>} Model performance
     */
    async getModelPerformance(model, symbol = null) {
        try {
            const response = await this.request('/ai/models/performance', {
                params: { model, symbol },
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get model performance');
        } catch (error) {
            logger.error('Get model performance error:', error);
            throw error;
        }
    }

    /**
     * Get available AI models
     * @returns {Promise<Array>} List of available models
     */
    async getAvailableModels() {
        try {
            const response = await this.request('/ai/models');

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get models');
        } catch (error) {
            logger.error('Get models error:', error);
            throw error;
        }
    }

    // ========================================================================
    // Portfolio Management Methods
    // ========================================================================

    /**
     * Get portfolio summary
     * @returns {Promise<Object>} Portfolio summary
     */
    async getPortfolioSummary() {
        try {
            const response = await this.request('/portfolio/summary');

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get portfolio summary');
        } catch (error) {
            logger.error('Get portfolio summary error:', error);
            throw error;
        }
    }

    /**
     * Get portfolio assets
     * @returns {Promise<Array>} Portfolio assets
     */
    async getPortfolioAssets() {
        try {
            const response = await this.request('/portfolio/assets');

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get portfolio assets');
        } catch (error) {
            logger.error('Get portfolio assets error:', error);
            throw error;
        }
    }

    /**
     * Get portfolio performance
     * @param {string} timeframe - Timeframe (1d, 7d, 30d, 90d, 1y)
     * @returns {Promise<Object>} Portfolio performance
     */
    async getPortfolioPerformance(timeframe = '30d') {
        try {
            const response = await this.request('/portfolio/performance', {
                params: { timeframe },
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get portfolio performance');
        } catch (error) {
            logger.error('Get portfolio performance error:', error);
            throw error;
        }
    }

    /**
     * Get portfolio history
     * @param {string} timeframe - Timeframe (1d, 7d, 30d, 90d, 1y)
     * @param {number} limit - Number of data points
     * @returns {Promise<Array>} Portfolio history
     */
    async getPortfolioHistory(timeframe = '30d', limit = 100) {
        try {
            const response = await this.request('/portfolio/history', {
                params: { timeframe, limit },
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get portfolio history');
        } catch (error) {
            logger.error('Get portfolio history error:', error);
            throw error;
        }
    }

    // ========================================================================
    // Risk Management Methods
    // ========================================================================

    /**
     * Get risk parameters
     * @returns {Promise<Object>} Risk parameters
     */
    async getRiskParameters() {
        try {
            const response = await this.request('/risk/parameters');

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get risk parameters');
        } catch (error) {
            logger.error('Get risk parameters error:', error);
            throw error;
        }
    }

    /**
     * Update risk parameters
     * @param {Object} params - Risk parameters
     * @returns {Promise<Object>} Updated risk parameters
     */
    async updateRiskParameters(params) {
        try {
            const response = await this.request('/risk/parameters', {
                method: 'PUT',
                body: JSON.stringify(params),
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to update risk parameters');
        } catch (error) {
            logger.error('Update risk parameters error:', error);
            throw error;
        }
    }

    /**
     * Get risk metrics for a position
     * @param {string} symbol - Trading pair symbol
     * @returns {Promise<Object>} Risk metrics
     */
    async getPositionRisk(symbol) {
        try {
            const response = await this.request('/risk/position', {
                params: { symbol },
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get position risk');
        } catch (error) {
            logger.error('Get position risk error:', error);
            throw error;
        }
    }

    // ========================================================================
    // Bot Management Methods
    // ========================================================================

    /**
     * Get bot status
     * @returns {Promise<Object>} Bot status
     */
    async getBotStatus() {
        try {
            const response = await this.request('/bot/status');

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get bot status');
        } catch (error) {
            logger.error('Get bot status error:', error);
            throw error;
        }
    }

    /**
     * Start the trading bot
     * @param {Object} config - Bot configuration (optional)
     * @returns {Promise<Object>} Start response
     */
    async startBot(config = {}) {
        try {
            const response = await this.request('/bot/start', {
                method: 'POST',
                body: JSON.stringify(config),
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to start bot');
        } catch (error) {
            logger.error('Start bot error:', error);
            throw error;
        }
    }

    /**
     * Stop the trading bot
     * @returns {Promise<Object>} Stop response
     */
    async stopBot() {
        try {
            const response = await this.request('/bot/stop', {
                method: 'POST',
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to stop bot');
        } catch (error) {
            logger.error('Stop bot error:', error);
            throw error;
        }
    }

    /**
     * Pause the trading bot
     * @returns {Promise<Object>} Pause response
     */
    async pauseBot() {
        try {
            const response = await this.request('/bot/pause', {
                method: 'POST',
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to pause bot');
        } catch (error) {
            logger.error('Pause bot error:', error);
            throw error;
        }
    }

    /**
     * Resume the trading bot
     * @returns {Promise<Object>} Resume response
     */
    async resumeBot() {
        try {
            const response = await this.request('/bot/resume', {
                method: 'POST',
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to resume bot');
        } catch (error) {
            logger.error('Resume bot error:', error);
            throw error;
        }
    }

    /**
     * Get bot configuration
     * @returns {Promise<Object>} Bot configuration
     */
    async getBotConfig() {
        try {
            const response = await this.request('/bot/config');

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get bot config');
        } catch (error) {
            logger.error('Get bot config error:', error);
            throw error;
        }
    }

    /**
     * Update bot configuration
     * @param {Object} config - Bot configuration
     * @returns {Promise<Object>} Updated bot configuration
     */
    async updateBotConfig(config) {
        try {
            const response = await this.request('/bot/config', {
                method: 'PUT',
                body: JSON.stringify(config),
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to update bot config');
        } catch (error) {
            logger.error('Update bot config error:', error);
            throw error;
        }
    }

    /**
     * Get bot performance metrics
     * @param {string} timeframe - Timeframe (1h, 24h, 7d, 30d)
     * @returns {Promise<Object>} Bot performance
     */
    async getBotPerformance(timeframe = '24h') {
        try {
            const response = await this.request('/bot/performance', {
                params: { timeframe },
            });

            if (response.success) {
                return response.data;
            }
            throw new Error(response.message || 'Failed to get bot performance');
        } catch (error) {
            logger.error('Get bot performance error:', error);
            throw error;
        }
    }

    // ========================================================================
    // WebSocket Methods
    // ========================================================================

    /**
     * Connect to WebSocket
     * @param {Array} subscriptions - Initial subscriptions
     * @returns {Promise<void>}
     */
    async connectWebSocket(subscriptions = []) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            logger.info('WebSocket already connected');
            return;
        }

        if (this.wsIsConnecting) {
            logger.info('WebSocket already connecting');
            return new Promise((resolve) => {
                const checkConnection = setInterval(() => {
                    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                        clearInterval(checkConnection);
                        resolve();
                    }
                    if (this.ws && this.ws.readyState === WebSocket.CLOSED) {
                        clearInterval(checkConnection);
                        resolve();
                    }
                }, 100);
            });
        }

        this.wsIsConnecting = true;
        const token = this.accessToken;
        const wsUrl = `${this.wsBaseUrl}/ws?token=${token}`;

        return new Promise((resolve, reject) => {
            try {
                this.ws = new WebSocket(wsUrl);
                this.wsReconnectAttempts = 0;

                this.ws.onopen = () => {
                    logger.info('WebSocket connected');
                    this.wsIsConnecting = false;
                    this.wsReconnectAttempts = 0;

                    // Send initial subscriptions
                    if (subscriptions.length > 0) {
                        this.sendWebSocketMessage({
                            type: 'subscribe',
                            channels: subscriptions,
                        });
                    }

                    resolve();
                };

                this.ws.onmessage = (event) => {
                    try {
                        const data = JSON.parse(event.data);
                        this.handleWebSocketMessage(data);
                    } catch (error) {
                        logger.error('WebSocket message parse error:', error);
                    }
                };

                this.ws.onerror = (error) => {
                    logger.error('WebSocket error:', error);
                    this.wsIsConnecting = false;
                    reject(error);
                };

                this.ws.onclose = (event) => {
                    logger.warn('WebSocket closed', { code: event.code, reason: event.reason });
                    this.wsIsConnecting = false;
                    this.handleWebSocketClose(event);
                };

                // Set timeout for connection
                setTimeout(() => {
                    if (this.ws && this.ws.readyState !== WebSocket.OPEN) {
                        this.wsIsConnecting = false;
                        reject(new Error('WebSocket connection timeout'));
                    }
                }, 10000);
            } catch (error) {
                this.wsIsConnecting = false;
                reject(error);
            }
        });
    }

    /**
     * Disconnect WebSocket
     */
    disconnectWebSocket() {
        if (this.ws) {
            try {
                this.ws.close(1000, 'User disconnected');
            } catch (error) {
                logger.debug('WebSocket disconnect error (ignored):', error);
            }
            this.ws = null;
        }
        this.wsIsConnecting = false;
    }

    /**
     * Send WebSocket message
     * @param {Object} message - Message to send
     */
    sendWebSocketMessage(message) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            logger.warn('WebSocket not connected, message queued');
            // Queue message for later
            if (!this._wsMessageQueue) {
                this._wsMessageQueue = [];
            }
            this._wsMessageQueue.push(message);
            return;
        }

        try {
            this.ws.send(JSON.stringify(message));
        } catch (error) {
            logger.error('WebSocket send error:', error);
        }
    }

    /**
     * Handle incoming WebSocket message
     * @param {Object} data - Message data
     */
    handleWebSocketMessage(data) {
        const { type, channel, payload } = data;

        // Handle ping/pong
        if (type === 'ping') {
            this.sendWebSocketMessage({ type: 'pong' });
            return;
        }

        // Trigger handlers
        if (this.wsHandlers.has(type)) {
            const handlers = this.wsHandlers.get(type);
            handlers.forEach(handler => {
                try {
                    handler(payload);
                } catch (error) {
                    logger.error('WebSocket handler error:', error);
                }
            });
        }

        // Trigger channel-specific handlers
        if (channel && this.wsHandlers.has(`channel:${channel}`)) {
            const handlers = this.wsHandlers.get(`channel:${channel}`);
            handlers.forEach(handler => {
                try {
                    handler(payload);
                } catch (error) {
                    logger.error('WebSocket channel handler error:', error);
                }
            });
        }

        // Trigger global handlers
        if (this.wsHandlers.has('*')) {
            const handlers = this.wsHandlers.get('*');
            handlers.forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    logger.error('WebSocket global handler error:', error);
                }
            });
        }

        // Emit events
        this.emitEvent('websocket:message', data);
    }

    /**
     * Handle WebSocket close
     * @param {CloseEvent} event - Close event
     */
    handleWebSocketClose(event) {
        this.wsIsConnecting = false;

        // Check if reconnection should be attempted
        if (event.code !== 1000 && this.wsReconnectAttempts < this.maxWebsocketReconnects) {
            this.wsReconnectAttempts++;
            const delay = this.websocketReconnectDelay * this.wsReconnectAttempts;
            logger.info(`Attempting WebSocket reconnect ${this.wsReconnectAttempts}/${this.maxWebsocketReconnects} in ${delay}ms`);
            
            setTimeout(() => {
                this.connectWebSocket().catch(error => {
                    logger.error('WebSocket reconnect failed:', error);
                });
            }, delay);
        } else if (this.wsReconnectAttempts >= this.maxWebsocketReconnects) {
            logger.error('WebSocket max reconnection attempts reached');
            this.emitEvent('websocket:max_reconnects', { attempts: this.wsReconnectAttempts });
        }

        this.emitEvent('websocket:close', event);
    }

    /**
     * Subscribe to WebSocket channel
     * @param {string} channel - Channel name
     * @param {Function} handler - Message handler
     */
    subscribeToChannel(channel, handler) {
        if (!this.wsHandlers.has(`channel:${channel}`)) {
            this.wsHandlers.set(`channel:${channel}`, []);
        }
        this.wsHandlers.get(`channel:${channel}`).push(handler);

        // Send subscription message if connected
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.sendWebSocketMessage({
                type: 'subscribe',
                channel: channel,
            });
        }
    }

    /**
     * Unsubscribe from WebSocket channel
     * @param {string} channel - Channel name
     * @param {Function} handler - Message handler to remove (optional)
     */
    unsubscribeFromChannel(channel, handler = null) {
        if (this.wsHandlers.has(`channel:${channel}`)) {
            if (handler) {
                const handlers = this.wsHandlers.get(`channel:${channel}`);
                const index = handlers.indexOf(handler);
                if (index !== -1) {
                    handlers.splice(index, 1);
                }
                if (handlers.length === 0) {
                    this.wsHandlers.delete(`channel:${channel}`);
                }
            } else {
                this.wsHandlers.delete(`channel:${channel}`);
            }

            // Send unsubscription message if connected
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.sendWebSocketMessage({
                    type: 'unsubscribe',
                    channel: channel,
                });
            }
        }
    }

    /**
     * Register WebSocket message handler
     * @param {string} type - Message type
     * @param {Function} handler - Message handler
     */
    onWebSocketMessage(type, handler) {
        if (!this.wsHandlers.has(type)) {
            this.wsHandlers.set(type, []);
        }
        this.wsHandlers.get(type).push(handler);
    }

    /**
     * Remove WebSocket message handler
     * @param {string} type - Message type
     * @param {Function} handler - Message handler to remove (optional)
     */
    offWebSocketMessage(type, handler = null) {
        if (this.wsHandlers.has(type)) {
            if (handler) {
                const handlers = this.wsHandlers.get(type);
                const index = handlers.indexOf(handler);
                if (index !== -1) {
                    handlers.splice(index, 1);
                }
                if (handlers.length === 0) {
                    this.wsHandlers.delete(type);
                }
            } else {
                this.wsHandlers.delete(type);
            }
        }
    }

    // ========================================================================
    // HTTP Request Methods
    // ========================================================================

    /**
     * Make an HTTP request
     * @param {string} endpoint - API endpoint
     * @param {Object} options - Request options
     * @param {string} options.method - HTTP method
     * @param {Object} options.params - URL parameters
     * @param {Object} options.body - Request body
     * @param {boolean} options.skipAuth - Skip authentication
     * @param {number} options.retryAttempts - Retry attempts
     * @param {number} options.timeout - Request timeout
     * @returns {Promise<Object>} Response data
     */
    async request(endpoint, options = {}) {
        const {
            method = 'GET',
            params = null,
            body = null,
            skipAuth = false,
            retryAttempts = this.retryAttempts,
            timeout = this.timeout,
        } = options;

        // Build URL
        let url = `${this.apiBaseUrl}${endpoint}`;
        if (params) {
            const queryParams = new URLSearchParams();
            Object.keys(params).forEach(key => {
                if (params[key] !== null && params[key] !== undefined) {
                    queryParams.append(key, params[key]);
                }
            });
            if (queryParams.toString()) {
                url += `?${queryParams.toString()}`;
            }
        }

        // Apply request interceptors
        let requestOptions = {
            method,
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
            },
            timeout,
        };

        if (body) {
            requestOptions.body = body;
        }

        // Add authorization header
        if (!skipAuth && this.accessToken) {
            requestOptions.headers['Authorization'] = `Bearer ${this.accessToken}`;
        }

        // Apply interceptors
        for (const interceptor of this.requestInterceptors) {
            requestOptions = await interceptor(requestOptions);
        }

        // Execute request with retry
        let lastError = null;
        for (let attempt = 0; attempt <= retryAttempts; attempt++) {
            try {
                const response = await this._fetchWithTimeout(url, requestOptions, timeout);
                const data = await response.json();

                // Apply response interceptors
                let processedData = data;
                for (const interceptor of this.responseInterceptors) {
                    processedData = await interceptor(processedData, response);
                }

                // Check for token expiration
                if (processedData.code === 'token_expired' && this.refreshToken) {
                    await this.refreshToken();
                    // Retry with new token
                    requestOptions.headers['Authorization'] = `Bearer ${this.accessToken}`;
                    continue;
                }

                if (!processedData.success && processedData.code === 'unauthorized') {
                    this.clearTokens();
                    this.emitAuthEvent('unauthorized', processedData);
                }

                return processedData;
            } catch (error) {
                lastError = error;
                if (attempt < retryAttempts) {
                    const delay = this.retryDelay * Math.pow(2, attempt);
                    logger.debug(`Request retry ${attempt + 1}/${retryAttempts} after ${delay}ms`, { endpoint, error: error.message });
                    await this.sleep(delay);
                }
            }
        }

        throw lastError || new Error('Request failed');
    }

    /**
     * Fetch with timeout
     * @param {string} url - Request URL
     * @param {Object} options - Fetch options
     * @param {number} timeout - Timeout in milliseconds
     * @returns {Promise<Response>} Fetch response
     */
    _fetchWithTimeout(url, options, timeout) {
        return new Promise((resolve, reject) => {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => {
                controller.abort();
                reject(new Error('Request timeout'));
            }, timeout);

            fetch(url, {
                ...options,
                signal: controller.signal,
            })
                .then(response => {
                    clearTimeout(timeoutId);
                    resolve(response);
                })
                .catch(error => {
                    clearTimeout(timeoutId);
                    reject(error);
                });
        });
    }

    /**
     * Sleep for a duration
     * @param {number} ms - Milliseconds to sleep
     * @returns {Promise<void>}
     */
    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    // ========================================================================
    // Cache Management
    // ========================================================================

    /**
     * Clear all cached data
     */
    clearCache() {
        this._cache = {};
    }

    /**
     * Get cached data
     * @param {string} key - Cache key
     * @returns {*} Cached data
     */
    getCache(key) {
        if (this._cache && this._cache[key]) {
            return this._cache[key];
        }
        return null;
    }

    /**
     * Set cached data
     * @param {string} key - Cache key
     * @param {*} data - Data to cache
     * @param {number} ttl - Time to live in seconds (optional)
     */
    setCache(key, data, ttl = null) {
        if (!this._cache) {
            this._cache = {};
        }
        this._cache[key] = data;
        if (ttl) {
            setTimeout(() => {
                delete this._cache[key];
            }, ttl * 1000);
        }
    }

    // ========================================================================
    // Token Management
    // ========================================================================

    /**
     * Set authentication tokens
     * @param {string} accessToken - Access token
     * @param {string} refreshToken - Refresh token
     */
    setTokens(accessToken, refreshToken) {
        this.accessToken = accessToken;
        this.refreshToken = refreshToken;
        localStorage.setItem('nexus_access_token', accessToken);
        if (refreshToken) {
            localStorage.setItem('nexus_refresh_token', refreshToken);
        }
        this.emitAuthEvent('tokens_set', { accessToken, refreshToken });
    }

    /**
     * Clear authentication tokens
     */
    clearTokens() {
        this.accessToken = null;
        this.refreshToken = null;
        localStorage.removeItem('nexus_access_token');
        localStorage.removeItem('nexus_refresh_token');
    }

    /**
     * Check if authenticated
     * @returns {boolean} Authenticated status
     */
    isAuthenticated() {
        return !!this.accessToken;
    }

    // ========================================================================
    // Event System
    // ========================================================================

    /**
     * Add event listener
     * @param {string} event - Event name
     * @param {Function} listener - Event listener
     */
    on(event, listener) {
        if (!this.eventListeners.has(event)) {
            this.eventListeners.set(event, []);
        }
        this.eventListeners.get(event).push(listener);
    }

    /**
     * Remove event listener
     * @param {string} event - Event name
     * @param {Function} listener - Event listener (optional)
     */
    off(event, listener = null) {
        if (this.eventListeners.has(event)) {
            if (listener) {
                const listeners = this.eventListeners.get(event);
                const index = listeners.indexOf(listener);
                if (index !== -1) {
                    listeners.splice(index, 1);
                }
                if (listeners.length === 0) {
                    this.eventListeners.delete(event);
                }
            } else {
                this.eventListeners.delete(event);
            }
        }
    }

    /**
     * Emit event
     * @param {string} event - Event name
     * @param {*} data - Event data
     */
    emitEvent(event, data) {
        if (this.eventListeners.has(event)) {
            const listeners = this.eventListeners.get(event);
            listeners.forEach(listener => {
                try {
                    listener(data);
                } catch (error) {
                    logger.error(`Event listener error for ${event}:`, error);
                }
            });
        }
    }

    /**
     * Add authentication event listener
     * @param {Function} listener - Auth event listener
     */
    onAuthEvent(listener) {
        this.authListeners.push(listener);
    }

    /**
     * Remove authentication event listener
     * @param {Function} listener - Auth event listener (optional)
     */
    offAuthEvent(listener = null) {
        if (listener) {
            const index = this.authListeners.indexOf(listener);
            if (index !== -1) {
                this.authListeners.splice(index, 1);
            }
        } else {
            this.authListeners = [];
        }
    }

    /**
     * Emit authentication event
     * @param {string} type - Event type
     * @param {*} data - Event data
     */
    emitAuthEvent(type, data) {
        this.authListeners.forEach(listener => {
            try {
                listener({ type, data });
            } catch (error) {
                logger.error('Auth listener error:', error);
            }
        });
    }

    // ========================================================================
    // Interceptor Management
    // ========================================================================

    /**
     * Add request interceptor
     * @param {Function} interceptor - Request interceptor function
     */
    addRequestInterceptor(interceptor) {
        this.requestInterceptors.push(interceptor);
    }

    /**
     * Add response interceptor
     * @param {Function} interceptor - Response interceptor function
     */
    addResponseInterceptor(interceptor) {
        this.responseInterceptors.push(interceptor);
    }

    /**
     * Remove request interceptor
     * @param {Function} interceptor - Request interceptor to remove
     */
    removeRequestInterceptor(interceptor) {
        const index = this.requestInterceptors.indexOf(interceptor);
        if (index !== -1) {
            this.requestInterceptors.splice(index, 1);
        }
    }

    /**
     * Remove response interceptor
     * @param {Function} interceptor - Response interceptor to remove
     */
    removeResponseInterceptor(interceptor) {
        const index = this.responseInterceptors.indexOf(interceptor);
        if (index !== -1) {
            this.responseInterceptors.splice(index, 1);
        }
    }

    // ========================================================================
    // Utility Methods
    // ========================================================================

    /**
     * Get API base URL
     * @returns {string} API base URL
     */
    getApiBaseUrl() {
        return this.apiBaseUrl;
    }

    /**
     * Get WebSocket base URL
     * @returns {string} WebSocket base URL
     */
    getWsBaseUrl() {
        return this.wsBaseUrl;
    }

    /**
     * Set API base URL
     * @param {string} baseUrl - New base URL
     */
    setApiBaseUrl(baseUrl) {
        this.baseUrl = baseUrl;
        this.apiBaseUrl = `${baseUrl}/api/${this.apiVersion}`;
        this.wsBaseUrl = baseUrl.replace('http', 'ws');
    }

    /**
     * Set API version
     * @param {string} version - API version
     */
    setApiVersion(version) {
        this.apiVersion = version;
        this.apiBaseUrl = `${this.baseUrl}/api/${this.version}`;
    }

    /**
     * Get request headers
     * @returns {Object} Request headers
     */
    getHeaders() {
        const headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        };
        if (this.accessToken) {
            headers['Authorization'] = `Bearer ${this.accessToken}`;
        }
        return headers;
    }

    /**
     * Format currency amount
     * @param {number} amount - Amount
     * @param {string} currency - Currency symbol
     * @returns {string} Formatted amount
     */
    static formatCurrency(amount, currency = '$') {
        if (amount === null || amount === undefined) {
            return `${currency}0.00`;
        }
        const absAmount = Math.abs(amount);
        let formatted = '';
        if (absAmount >= 1e9) {
            formatted = `${(amount / 1e9).toFixed(2)}B`;
        } else if (absAmount >= 1e6) {
            formatted = `${(amount / 1e6).toFixed(2)}M`;
        } else if (absAmount >= 1e3) {
            formatted = `${(amount / 1e3).toFixed(2)}K`;
        } else {
            formatted = amount.toFixed(2);
        }
        return `${currency}${formatted}`;
    }

    /**
     * Format percentage
     * @param {number} value - Percentage value
     * @param {number} decimals - Number of decimals
     * @returns {string} Formatted percentage
     */
    static formatPercentage(value, decimals = 2) {
        if (value === null || value === undefined) {
            return '0.00%';
        }
        const sign = value > 0 ? '+' : '';
        return `${sign}${value.toFixed(decimals)}%`;
    }

    /**
     * Format number with commas
     * @param {number} value - Number to format
     * @param {number} decimals - Number of decimals
     * @returns {string} Formatted number
     */
    static formatNumber(value, decimals = 2) {
        if (value === null || value === undefined) {
            return '0';
        }
        return Number(value).toLocaleString('en-US', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
        });
    }

    /**
     * Format timestamp to readable date
     * @param {string|number} timestamp - ISO timestamp or Unix timestamp
     * @param {string} format - Date format (iso, date, time, datetime)
     * @returns {string} Formatted date
     */
    static formatDate(timestamp, format = 'datetime') {
        const date = new Date(timestamp);
        if (isNaN(date.getTime())) {
            return '-';
        }

        const options = {
            iso: date.toISOString(),
            date: date.toLocaleDateString('en-US', { year: 'numeric', month: 'short', day: 'numeric' }),
            time: date.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', second: '2-digit' }),
            datetime: date.toLocaleString('en-US', { 
                year: 'numeric', 
                month: 'short', 
                day: 'numeric',
                hour: '2-digit', 
                minute: '2-digit',
                second: '2-digit'
            }),
        };

        return options[format] || options.datetime;
    }
}

// Create global instance
window.NexusAPI = new NexusAPIClient();

// Simple logger
const logger = {
    debug: (...args) => console.debug('[DEBUG]', ...args),
    info: (...args) => console.info('[INFO]', ...args),
    warn: (...args) => console.warn('[WARN]', ...args),
    error: (...args) => console.error('[ERROR]', ...args),
};

export default NexusAPIClient;

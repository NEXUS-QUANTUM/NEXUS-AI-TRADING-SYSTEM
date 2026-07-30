/**
 * trading/bots/hedge_bot/static/js/api_client.js
 * NEXUS AI TRADING SYSTEM - Hedge Bot API Client
 * Version: 2.0.0
 * Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
 */

/**
 * NEXUS API Client
 * 
 * A comprehensive JavaScript client for interacting with the NEXUS Hedge Bot API.
 * Features include:
 * - Authentication (JWT)
 * - Automatic token refresh
 * - Request/response interceptors
 * - Error handling
 * - Retry logic
 * - Rate limiting
 * - WebSocket support
 * - Comprehensive logging
 * - TypeScript definitions
 */

class NexusAPIClient {
    /**
     * Create a new API client instance
     * 
     * @param {Object} config - Client configuration
     * @param {string} config.baseURL - Base URL for API requests
     * @param {number} config.timeout - Request timeout in milliseconds
     * @param {number} config.retryAttempts - Number of retry attempts
     * @param {number} config.retryDelay - Delay between retries in milliseconds
     * @param {Object} config.headers - Default headers
     * @param {boolean} config.debug - Enable debug logging
     * @param {Function} config.onAuthRequired - Callback when authentication is required
     * @param {Function} config.onUnauthorized - Callback when unauthorized
     */
    constructor(config = {}) {
        // Configuration
        this.config = {
            baseURL: config.baseURL || '/api/v1',
            timeout: config.timeout || 30000,
            retryAttempts: config.retryAttempts || 3,
            retryDelay: config.retryDelay || 1000,
            headers: config.headers || {},
            debug: config.debug || false,
            onAuthRequired: config.onAuthRequired || (() => {}),
            onUnauthorized: config.onUnauthorized || (() => {}),
            tokenRefreshBuffer: config.tokenRefreshBuffer || 60, // seconds
        };

        // State
        this.token = null;
        this.refreshToken = null;
        this.tokenExpiry = null;
        this.refreshPromise = null;
        this.isRefreshing = false;
        this.requestQueue = [];
        this.pendingRequests = new Map();
        this.rateLimits = {
            remaining: 60,
            reset: null,
            limit: 60,
        };
        this.isConnected = false;
        this.healthCheckInterval = null;
        this.retryCounts = new Map();

        // WebSocket state
        this.ws = null;
        this.wsReconnectAttempts = 0;
        this.wsMaxReconnectAttempts = 10;
        this.wsReconnectDelay = 1000;
        this.wsSubscriptions = new Map();
        this.wsHandlers = new Map();
        this.wsMessageQueue = [];
        this.wsIsConnecting = false;
        this.wsHeartbeatInterval = null;

        // Event listeners
        this.eventListeners = new Map();

        // Initialize
        this._loadToken();
        this._setupHealthCheck();
        this._setupInterceptors();

        this.log('Initialized API Client');
    }

    // ============================================================
    // AUTHENTICATION
    // ============================================================

    /**
     * Authenticate with the API
     * 
     * @param {string} username - User username
     * @param {string} password - User password
     * @param {string} twoFactorCode - Optional 2FA code
     * @returns {Promise<Object>} Authentication response
     */
    async login(username, password, twoFactorCode = null) {
        this.log('Authenticating user:', username);

        try {
            const response = await this._request('POST', '/auth/login', {
                username,
                password,
                two_factor_code: twoFactorCode,
            });

            if (response.access_token) {
                this._setToken(response.access_token, response.refresh_token, response.expires_in);
                this._saveToken();
                this._emit('authenticated', response);
                return response;
            }

            throw new Error('Invalid authentication response');
        } catch (error) {
            this.log('Authentication failed:', error);
            throw error;
        }
    }

    /**
     * Refresh the access token
     * 
     * @returns {Promise<Object>} Refresh response
     */
    async refreshAccessToken() {
        // Prevent multiple simultaneous refresh attempts
        if (this.isRefreshing) {
            return new Promise((resolve, reject) => {
                this.requestQueue.push({ resolve, reject });
            });
        }

        this.isRefreshing = true;
        this.refreshPromise = null;

        try {
            if (!this.refreshToken) {
                throw new Error('No refresh token available');
            }

            this.log('Refreshing access token');

            const response = await this._request('POST', '/auth/refresh', {
                refresh_token: this.refreshToken,
            });

            if (response.access_token) {
                this._setToken(response.access_token, null, response.expires_in);
                this._saveToken();
                this._emit('token_refreshed', response);
                
                // Resolve queued requests
                this._resolveQueue();
                return response;
            }

            throw new Error('Invalid refresh response');
        } catch (error) {
            this.log('Token refresh failed:', error);
            this._rejectQueue(error);
            this._clearToken();
            this._emit('unauthorized', error);
            this.config.onUnauthorized(error);
            throw error;
        } finally {
            this.isRefreshing = false;
            this.refreshPromise = null;
        }
    }

    /**
     * Logout and clear authentication state
     * 
     * @returns {Promise<void>}
     */
    async logout() {
        this.log('Logging out');

        try {
            await this._request('POST', '/auth/logout');
        } catch (error) {
            this.log('Logout error:', error);
        } finally {
            this._clearToken();
            this._removeToken();
            this._emit('logout');
        }
    }

    /**
     * Get current authentication status
     * 
     * @returns {Object} Auth status
     */
    getAuthStatus() {
        return {
            isAuthenticated: !!this.token,
            hasRefreshToken: !!this.refreshToken,
            tokenExpiry: this.tokenExpiry,
            isRefreshing: this.isRefreshing,
        };
    }

    // ============================================================
    // API REQUESTS
    // ============================================================

    /**
     * Make a GET request
     * 
     * @param {string} endpoint - API endpoint
     * @param {Object} params - Query parameters
     * @param {Object} options - Request options
     * @returns {Promise<any>} Response data
     */
    async get(endpoint, params = {}, options = {}) {
        const url = this._buildURL(endpoint, params);
        return this._request('GET', url, null, options);
    }

    /**
     * Make a POST request
     * 
     * @param {string} endpoint - API endpoint
     * @param {Object} data - Request body
     * @param {Object} options - Request options
     * @returns {Promise<any>} Response data
     */
    async post(endpoint, data = {}, options = {}) {
        return this._request('POST', endpoint, data, options);
    }

    /**
     * Make a PUT request
     * 
     * @param {string} endpoint - API endpoint
     * @param {Object} data - Request body
     * @param {Object} options - Request options
     * @returns {Promise<any>} Response data
     */
    async put(endpoint, data = {}, options = {}) {
        return this._request('PUT', endpoint, data, options);
    }

    /**
     * Make a PATCH request
     * 
     * @param {string} endpoint - API endpoint
     * @param {Object} data - Request body
     * @param {Object} options - Request options
     * @returns {Promise<any>} Response data
     */
    async patch(endpoint, data = {}, options = {}) {
        return this._request('PATCH', endpoint, data, options);
    }

    /**
     * Make a DELETE request
     * 
     * @param {string} endpoint - API endpoint
     * @param {Object} options - Request options
     * @returns {Promise<any>} Response data
     */
    async delete(endpoint, options = {}) {
        return this._request('DELETE', endpoint, null, options);
    }

    /**
     * Upload a file
     * 
     * @param {string} endpoint - API endpoint
     * @param {File|Blob} file - File to upload
     * @param {Object} data - Additional form data
     * @param {Object} options - Request options
     * @returns {Promise<any>} Response data
     */
    async upload(endpoint, file, data = {}, options = {}) {
        const formData = new FormData();
        formData.append('file', file);
        
        for (const [key, value] of Object.entries(data)) {
            formData.append(key, value);
        }

        return this._request('POST', endpoint, formData, {
            ...options,
            headers: {
                ...options.headers,
                'Content-Type': 'multipart/form-data',
            },
        });
    }

    /**
     * Download a file
     * 
     * @param {string} endpoint - API endpoint
     * @param {Object} params - Query parameters
     * @param {Object} options - Request options
     * @returns {Promise<Blob>} File blob
     */
    async download(endpoint, params = {}, options = {}) {
        const url = this._buildURL(endpoint, params);
        const response = await this._request('GET', url, null, {
            ...options,
            responseType: 'blob',
        });
        return response;
    }

    // ============================================================
    // WEBSOCKET CONNECTION
    // ============================================================

    /**
     * Connect to WebSocket
     * 
     * @param {string} url - WebSocket URL
     * @param {Object} options - Connection options
     * @returns {Promise<void>}
     */
    async connectWebSocket(url = null, options = {}) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.log('WebSocket already connected');
            return;
        }

        if (this.wsIsConnecting) {
            this.log('WebSocket connection in progress');
            return;
        }

        this.wsIsConnecting = true;

        try {
            const wsUrl = url || this._getWebSocketURL();
            this.log('Connecting to WebSocket:', wsUrl);

            this.ws = new WebSocket(wsUrl);
            this.ws.binaryType = options.binaryType || 'arraybuffer';
            this.ws.timeout = options.timeout || 30000;

            // Setup event handlers
            this.ws.onopen = this._handleWebSocketOpen.bind(this);
            this.ws.onclose = this._handleWebSocketClose.bind(this);
            this.ws.onerror = this._handleWebSocketError.bind(this);
            this.ws.onmessage = this._handleWebSocketMessage.bind(this);

            // Wait for connection
            await new Promise((resolve, reject) => {
                const timeout = setTimeout(() => {
                    reject(new Error('WebSocket connection timeout'));
                }, options.timeout || 30000);

                this.ws._resolveOpen = resolve;
                this.ws._rejectOpen = reject;
                this.ws._openTimeout = timeout;
            });

            this.wsReconnectAttempts = 0;
            this._startWebSocketHeartbeat();
            this._emit('ws_connected');

        } catch (error) {
            this.log('WebSocket connection failed:', error);
            this._emit('ws_error', error);
            throw error;
        } finally {
            this.wsIsConnecting = false;
        }
    }

    /**
     * Disconnect WebSocket
     * 
     * @param {number} code - Close code
     * @param {string} reason - Close reason
     * @returns {void}
     */
    disconnectWebSocket(code = 1000, reason = 'Normal closure') {
        if (!this.ws) {
            return;
        }

        this.log('Disconnecting WebSocket:', code, reason);
        this.ws.close(code, reason);
        this.ws = null;
        this._stopWebSocketHeartbeat();
        this._emit('ws_disconnected');
    }

    /**
     * Subscribe to a WebSocket channel
     * 
     * @param {string} channel - Channel name
     * @param {Function} handler - Message handler
     * @param {Object} options - Subscription options
     * @returns {Promise<void>}
     */
    async subscribe(channel, handler, options = {}) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            await this.connectWebSocket();
        }

        if (this.wsSubscriptions.has(channel)) {
            this.log('Already subscribed to channel:', channel);
            return;
        }

        this.log('Subscribing to channel:', channel);

        const subscription = {
            channel,
            handler,
            options,
            active: true,
        };

        this.wsSubscriptions.set(channel, subscription);

        // Send subscription message
        this._sendWebSocketMessage({
            type: 'subscribe',
            channel: channel,
            ...options,
        });

        this._emit('ws_subscribed', { channel, options });
    }

    /**
     * Unsubscribe from a WebSocket channel
     * 
     * @param {string} channel - Channel name
     * @returns {void}
     */
    unsubscribe(channel) {
        if (!this.wsSubscriptions.has(channel)) {
            this.log('Not subscribed to channel:', channel);
            return;
        }

        this.log('Unsubscribing from channel:', channel);
        this.wsSubscriptions.delete(channel);

        this._sendWebSocketMessage({
            type: 'unsubscribe',
            channel: channel,
        });

        this._emit('ws_unsubscribed', { channel });
    }

    /**
     * Send a WebSocket message
     * 
     * @param {Object} data - Message data
     * @param {boolean} queue - Queue message if not connected
     * @returns {void}
     */
    sendWebSocketMessage(data, queue = true) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this._sendWebSocketMessage(data);
        } else if (queue) {
            this.wsMessageQueue.push(data);
        } else {
            throw new Error('WebSocket not connected');
        }
    }

    // ============================================================
    // HEALTH CHECKS
    // ============================================================

    /**
     * Check API health
     * 
     * @returns {Promise<Object>} Health status
     */
    async healthCheck() {
        try {
            const response = await this._request('GET', '/health', null, {
                timeout: 5000,
                skipAuth: true,
            });
            this.isConnected = true;
            this._emit('healthy', response);
            return response;
        } catch (error) {
            this.isConnected = false;
            this._emit('unhealthy', error);
            throw error;
        }
    }

    /**
     * Check service readiness
     * 
     * @returns {Promise<Object>} Readiness status
     */
    async readinessCheck() {
        try {
            const response = await this._request('GET', '/ready', null, {
                timeout: 5000,
                skipAuth: true,
            });
            return response;
        } catch (error) {
            throw error;
        }
    }

    /**
     * Check service liveness
     * 
     * @returns {Promise<Object>} Liveness status
     */
    async livenessCheck() {
        try {
            const response = await this._request('GET', '/live', null, {
                timeout: 3000,
                skipAuth: true,
            });
            return response;
        } catch (error) {
            throw error;
        }
    }

    // ============================================================
    // TRADING API METHODS
    // ============================================================

    /**
     * Get all positions
     * 
     * @param {Object} filters - Filter options
     * @returns {Promise<Object>} Positions data
     */
    async getPositions(filters = {}) {
        return this.get('/trading/positions', filters);
    }

    /**
     * Get position details
     * 
     * @param {string} positionId - Position ID
     * @returns {Promise<Object>} Position data
     */
    async getPosition(positionId) {
        return this.get(`/trading/positions/${positionId}`);
    }

    /**
     * Get all orders
     * 
     * @param {Object} filters - Filter options
     * @returns {Promise<Object>} Orders data
     */
    async getOrders(filters = {}) {
        return this.get('/trading/orders', filters);
    }

    /**
     * Place an order
     * 
     * @param {Object} order - Order data
     * @returns {Promise<Object>} Order response
     */
    async placeOrder(order) {
        return this.post('/trading/orders', order);
    }

    /**
     * Cancel an order
     * 
     * @param {string} orderId - Order ID
     * @returns {Promise<Object>} Cancellation response
     */
    async cancelOrder(orderId) {
        return this.delete(`/trading/orders/${orderId}`);
    }

    /**
     * Get trade history
     * 
     * @param {Object} filters - Filter options
     * @returns {Promise<Object>} Trade history
     */
    async getTradeHistory(filters = {}) {
        return this.get('/trading/history', filters);
    }

    // ============================================================
    // STRATEGY API METHODS
    // ============================================================

    /**
     * Get strategy status
     * 
     * @returns {Promise<Object>} Strategy status
     */
    async getStrategyStatus() {
        return this.get('/strategy/status');
    }

    /**
     * Start a strategy
     * 
     * @param {string} strategyName - Strategy name
     * @param {Object} parameters - Strategy parameters
     * @returns {Promise<Object>} Start response
     */
    async startStrategy(strategyName, parameters = {}) {
        return this.post('/strategy/start', {
            strategy_name: strategyName,
            parameters,
        });
    }

    /**
     * Stop a strategy
     * 
     * @param {string} strategyName - Strategy name
     * @param {boolean} emergency - Emergency stop
     * @returns {Promise<Object>} Stop response
     */
    async stopStrategy(strategyName, emergency = false) {
        return this.post('/strategy/stop', {
            strategy_name: strategyName,
            emergency,
        });
    }

    /**
     * Get strategy parameters
     * 
     * @returns {Promise<Object>} Strategy parameters
     */
    async getStrategyParameters() {
        return this.get('/strategy/parameters');
    }

    /**
     * Update strategy parameters
     * 
     * @param {Object} parameters - New parameters
     * @returns {Promise<Object>} Update response
     */
    async updateStrategyParameters(parameters) {
        return this.patch('/strategy/parameters', parameters);
    }

    /**
     * Get strategy performance
     * 
     * @param {Object} filters - Filter options
     * @returns {Promise<Object>} Performance data
     */
    async getStrategyPerformance(filters = {}) {
        return this.get('/strategy/performance', filters);
    }

    // ============================================================
    // RISK API METHODS
    // ============================================================

    /**
     * Get risk metrics
     * 
     * @returns {Promise<Object>} Risk metrics
     */
    async getRiskMetrics() {
        return this.get('/risk/metrics');
    }

    /**
     * Get risk limits
     * 
     * @returns {Promise<Object>} Risk limits
     */
    async getRiskLimits() {
        return this.get('/risk/limits');
    }

    /**
     * Update risk limits
     * 
     * @param {Object} limits - New limits
     * @returns {Promise<Object>} Update response
     */
    async updateRiskLimits(limits) {
        return this.patch('/risk/limits', limits);
    }

    /**
     * Run a stress test
     * 
     * @param {Object} scenario - Stress scenario
     * @returns {Promise<Object>} Stress test results
     */
    async runStressTest(scenario) {
        return this.post('/risk/stress-test', scenario);
    }

    // ============================================================
    // PORTFOLIO API METHODS
    // ============================================================

    /**
     * Get portfolio summary
     * 
     * @returns {Promise<Object>} Portfolio summary
     */
    async getPortfolioSummary() {
        return this.get('/portfolio/summary');
    }

    /**
     * Get portfolio allocation
     * 
     * @returns {Promise<Object>} Portfolio allocation
     */
    async getPortfolioAllocation() {
        return this.get('/portfolio/allocation');
    }

    /**
     * Rebalance portfolio
     * 
     * @param {Object} targetAllocation - Target allocation
     * @param {boolean} execute - Execute trades
     * @returns {Promise<Object>} Rebalance response
     */
    async rebalancePortfolio(targetAllocation, execute = true) {
        return this.post('/portfolio/rebalance', {
            target_allocation: targetAllocation,
            execute,
        });
    }

    // ============================================================
    // CONFIGURATION API METHODS
    // ============================================================

    /**
     * Get configuration
     * 
     * @param {string} section - Configuration section
     * @returns {Promise<Object>} Configuration data
     */
    async getConfig(section = null) {
        const endpoint = section ? `/config/${section}` : '/config';
        return this.get(endpoint);
    }

    /**
     * Update configuration
     * 
     * @param {Object} config - New configuration
     * @returns {Promise<Object>} Update response
     */
    async updateConfig(config) {
        return this.patch('/config', config);
    }

    /**
     * Reload configuration
     * 
     * @returns {Promise<Object>} Reload response
     */
    async reloadConfig() {
        return this.post('/config/reload');
    }

    // ============================================================
    // PRIVATE METHODS
    // ============================================================

    /**
     * Make an HTTP request
     * 
     * @param {string} method - HTTP method
     * @param {string} endpoint - API endpoint
     * @param {Object} data - Request data
     * @param {Object} options - Request options
     * @param {number} retryCount - Current retry count
     * @returns {Promise<any>} Response data
     */
    async _request(method, endpoint, data = null, options = {}, retryCount = 0) {
        const url = this._buildURL(endpoint);
        const requestId = this._generateRequestId();

        // Prepare request options
        const requestOptions = {
            method,
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                ...this.config.headers,
                ...(options.headers || {}),
            },
            credentials: 'include',
            signal: this._createAbortSignal(options.timeout || this.config.timeout),
        };

        // Add token if available and not skipped
        if (!options.skipAuth && this.token) {
            requestOptions.headers['Authorization'] = `Bearer ${this.token}`;
        }

        // Add body data
        if (data) {
            if (data instanceof FormData) {
                requestOptions.body = data;
                delete requestOptions.headers['Content-Type'];
            } else {
                requestOptions.body = JSON.stringify(data);
            }
        }

        // Add response type
        if (options.responseType === 'blob') {
            requestOptions.responseType = 'blob';
        }

        try {
            this._emit('request_start', { requestId, method, url, options });

            const response = await fetch(`${this.config.baseURL}${url}`, requestOptions);
            const responseData = await this._parseResponse(response, options.responseType);

            this._emit('request_end', { requestId, method, url, status: response.status });

            // Check for rate limit headers
            this._updateRateLimits(response);

            // Handle response status
            if (response.ok) {
                return responseData;
            }

            // Handle specific status codes
            if (response.status === 401) {
                if (this.token && !options.skipAuth) {
                    // Token expired, try refresh
                    await this.refreshAccessToken();
                    // Retry request with new token
                    return this._request(method, endpoint, data, {
                        ...options,
                        skipAuth: true,
                    }, retryCount);
                }
                this._emit('unauthorized', responseData);
                this.config.onUnauthorized(responseData);
                throw new Error('Unauthorized');
            }

            if (response.status === 429) {
                const retryAfter = response.headers.get('Retry-After') || 60;
                if (retryCount < this.config.retryAttempts) {
                    this.log(`Rate limited, retrying after ${retryAfter}s`);
                    await this._delay(retryAfter * 1000);
                    return this._request(method, endpoint, data, options, retryCount + 1);
                }
                throw new Error('Rate limit exceeded');
            }

            if (response.status === 503) {
                if (retryCount < this.config.retryAttempts) {
                    const delay = this._calculateBackoff(retryCount);
                    this.log(`Service unavailable, retrying after ${delay}ms`);
                    await this._delay(delay);
                    return this._request(method, endpoint, data, options, retryCount + 1);
                }
            }

            throw new Error(responseData?.error?.message || `Request failed with status ${response.status}`);

        } catch (error) {
            // Handle network errors
            if (error.name === 'AbortError') {
                throw new Error('Request timeout');
            }

            if (error.name === 'TypeError' && error.message.includes('fetch')) {
                if (retryCount < this.config.retryAttempts) {
                    const delay = this._calculateBackoff(retryCount);
                    this.log(`Network error, retrying after ${delay}ms`);
                    await this._delay(delay);
                    return this._request(method, endpoint, data, options, retryCount + 1);
                }
            }

            this._emit('request_error', { requestId, error });
            throw error;
        }
    }

    /**
     * Parse HTTP response
     * 
     * @param {Response} response - Fetch response
     * @param {string} responseType - Response type
     * @returns {Promise<any>} Parsed response
     */
    async _parseResponse(response, responseType) {
        if (responseType === 'blob') {
            return response.blob();
        }

        const contentLength = response.headers.get('content-length');
        if (contentLength && parseInt(contentLength) === 0) {
            return null;
        }

        const contentType = response.headers.get('content-type') || '';
        if (contentType.includes('application/json')) {
            return response.json();
        }

        if (contentType.includes('text/')) {
            return response.text();
        }

        return response.blob();
    }

    /**
     * Build URL with query parameters
     * 
     * @param {string} endpoint - API endpoint
     * @param {Object} params - Query parameters
     * @returns {string} Full URL
     */
    _buildURL(endpoint, params = {}) {
        const url = endpoint.startsWith('http') ? endpoint : endpoint;
        const searchParams = new URLSearchParams();

        for (const [key, value] of Object.entries(params)) {
            if (value !== undefined && value !== null) {
                searchParams.append(key, String(value));
            }
        }

        const queryString = searchParams.toString();
        return queryString ? `${url}?${queryString}` : url;
    }

    /**
     * Create abort signal for timeout
     * 
     * @param {number} timeout - Timeout in milliseconds
     * @returns {AbortSignal} Abort signal
     */
    _createAbortSignal(timeout) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);
        controller.signal.addEventListener('abort', () => clearTimeout(timeoutId));
        return controller.signal;
    }

    /**
     * Calculate backoff delay
     * 
     * @param {number} retryCount - Current retry count
     * @returns {number} Delay in milliseconds
     */
    _calculateBackoff(retryCount) {
        const baseDelay = this.config.retryDelay;
        const maxDelay = 30000;
        const delay = Math.min(baseDelay * Math.pow(2, retryCount), maxDelay);
        return delay + (Math.random() * 100);
    }

    /**
     * Delay execution
     * 
     * @param {number} ms - Milliseconds to delay
     * @returns {Promise<void>}
     */
    _delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    /**
     * Generate unique request ID
     * 
     * @returns {string} Request ID
     */
    _generateRequestId() {
        return `req_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    // ============================================================
    // TOKEN MANAGEMENT
    // ============================================================

    /**
     * Set authentication token
     * 
     * @param {string} token - Access token
     * @param {string} refreshToken - Refresh token
     * @param {number} expiresIn - Expiration in seconds
     */
    _setToken(token, refreshToken, expiresIn) {
        this.token = token;
        if (refreshToken) {
            this.refreshToken = refreshToken;
        }
        if (expiresIn) {
            this.tokenExpiry = Date.now() + (expiresIn - this.config.tokenRefreshBuffer) * 1000;
        }
    }

    /**
     * Clear authentication token
     */
    _clearToken() {
        this.token = null;
        this.refreshToken = null;
        this.tokenExpiry = null;
        this.requestQueue = [];
    }

    /**
     * Save token to storage
     */
    _saveToken() {
        try {
            const data = {
                token: this.token,
                refreshToken: this.refreshToken,
                tokenExpiry: this.tokenExpiry,
            };
            localStorage.setItem('nexus_auth', JSON.stringify(data));
        } catch (error) {
            this.log('Failed to save token:', error);
        }
    }

    /**
     * Load token from storage
     */
    _loadToken() {
        try {
            const data = localStorage.getItem('nexus_auth');
            if (data) {
                const parsed = JSON.parse(data);
                this.token = parsed.token;
                this.refreshToken = parsed.refreshToken;
                this.tokenExpiry = parsed.tokenExpiry;
                
                if (this.tokenExpiry && this.tokenExpiry < Date.now()) {
                    this._clearToken();
                    this._removeToken();
                }
            }
        } catch (error) {
            this.log('Failed to load token:', error);
        }
    }

    /**
     * Remove token from storage
     */
    _removeToken() {
        try {
            localStorage.removeItem('nexus_auth');
        } catch (error) {
            this.log('Failed to remove token:', error);
        }
    }

    /**
     * Resolve queued requests
     */
    _resolveQueue() {
        while (this.requestQueue.length) {
            const { resolve } = this.requestQueue.shift();
            resolve({ success: true });
        }
    }

    /**
     * Reject queued requests
     * 
     * @param {Error} error - Error to reject with
     */
    _rejectQueue(error) {
        while (this.requestQueue.length) {
            const { reject } = this.requestQueue.shift();
            reject(error);
        }
    }

    // ============================================================
    // WEBSOCKET PRIVATE METHODS
    // ============================================================

    /**
     * Get WebSocket URL
     * 
     * @returns {string} WebSocket URL
     */
    _getWebSocketURL() {
        const baseURL = this.config.baseURL.replace(/^http/, 'ws');
        return `${baseURL}/ws`;
    }

    /**
     * Handle WebSocket open event
     */
    _handleWebSocketOpen(event) {
        this.log('WebSocket connected');

        // Clear open timeout
        if (this.ws._openTimeout) {
            clearTimeout(this.ws._openTimeout);
        }

        // Resolve connection promise
        if (this.ws._resolveOpen) {
            this.ws._resolveOpen();
            this.ws._resolveOpen = null;
        }

        // Process queued messages
        this._processWebSocketQueue();

        // Re-subscribe to channels
        this._resubscribeWebSocketChannels();

        this._emit('ws_open', event);
    }

    /**
     * Handle WebSocket close event
     */
    _handleWebSocketClose(event) {
        this.log('WebSocket closed:', event.code, event.reason);

        // Clear open timeout
        if (this.ws._openTimeout) {
            clearTimeout(this.ws._openTimeout);
        }

        // Reject connection promise
        if (this.ws._rejectOpen) {
            this.ws._rejectOpen(new Error('WebSocket closed'));
            this.ws._rejectOpen = null;
        }

        this.ws = null;
        this._stopWebSocketHeartbeat();
        this._emit('ws_close', event);

        // Attempt reconnect
        if (this.wsReconnectAttempts < this.wsMaxReconnectAttempts) {
            const delay = Math.min(
                1000 * Math.pow(2, this.wsReconnectAttempts),
                30000
            );
            this.log(`Reconnecting in ${delay}ms (attempt ${this.wsReconnectAttempts + 1})`);
            
            setTimeout(() => {
                this.wsReconnectAttempts++;
                this.connectWebSocket().catch(() => {});
            }, delay);
        }
    }

    /**
     * Handle WebSocket error event
     */
    _handleWebSocketError(error) {
        this.log('WebSocket error:', error);
        this._emit('ws_error', error);
    }

    /**
     * Handle WebSocket message event
     */
    _handleWebSocketMessage(event) {
        try {
            let data;
            if (event.data instanceof ArrayBuffer) {
                data = new Uint8Array(event.data);
            } else {
                data = JSON.parse(event.data);
            }

            // Handle heartbeat
            if (data.type === 'pong') {
                this._emit('ws_pong', data);
                return;
            }

            // Route message to handlers
            if (data.channel && this.wsSubscriptions.has(data.channel)) {
                const subscription = this.wsSubscriptions.get(data.channel);
                if (subscription.handler) {
                    subscription.handler(data);
                }
            }

            // Global message handler
            this._emit('ws_message', data);

        } catch (error) {
            this.log('Failed to parse WebSocket message:', error);
        }
    }

    /**
     * Send WebSocket message
     * 
     * @param {Object} data - Message data
     */
    _sendWebSocketMessage(data) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            this.log('WebSocket not connected, queuing message');
            this.wsMessageQueue.push(data);
            return;
        }

        try {
            const message = typeof data === 'string' ? data : JSON.stringify(data);
            this.ws.send(message);
        } catch (error) {
            this.log('Failed to send WebSocket message:', error);
        }
    }

    /**
     * Process queued WebSocket messages
     */
    _processWebSocketQueue() {
        while (this.wsMessageQueue.length) {
            const message = this.wsMessageQueue.shift();
            this._sendWebSocketMessage(message);
        }
    }

    /**
     * Resubscribe to WebSocket channels
     */
    _resubscribeWebSocketChannels() {
        for (const [channel, subscription] of this.wsSubscriptions) {
            this._sendWebSocketMessage({
                type: 'subscribe',
                channel,
                ...subscription.options,
            });
        }
    }

    /**
     * Start WebSocket heartbeat
     */
    _startWebSocketHeartbeat() {
        this._stopWebSocketHeartbeat();
        this.wsHeartbeatInterval = setInterval(() => {
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this._sendWebSocketMessage({ type: 'ping' });
            }
        }, 30000);
    }

    /**
     * Stop WebSocket heartbeat
     */
    _stopWebSocketHeartbeat() {
        if (this.wsHeartbeatInterval) {
            clearInterval(this.wsHeartbeatInterval);
            this.wsHeartbeatInterval = null;
        }
    }

    // ============================================================
    // RATE LIMIT MANAGEMENT
    // ============================================================

    /**
     * Update rate limits from response headers
     * 
     * @param {Response} response - HTTP response
     */
    _updateRateLimits(response) {
        const limit = response.headers.get('X-RateLimit-Limit');
        const remaining = response.headers.get('X-RateLimit-Remaining');
        const reset = response.headers.get('X-RateLimit-Reset');

        if (limit) this.rateLimits.limit = parseInt(limit);
        if (remaining) this.rateLimits.remaining = parseInt(remaining);
        if (reset) this.rateLimits.reset = new Date(parseInt(reset) * 1000);
    }

    /**
     * Check if rate limit is exceeded
     * 
     * @returns {boolean} Whether rate limit is exceeded
     */
    isRateLimited() {
        if (this.rateLimits.remaining <= 0 && this.rateLimits.reset) {
            return this.rateLimits.reset > new Date();
        }
        return false;
    }

    /**
     * Get rate limit status
     * 
     * @returns {Object} Rate limit status
     */
    getRateLimitStatus() {
        return {
            ...this.rateLimits,
            isLimited: this.isRateLimited(),
        };
    }

    // ============================================================
    // HEALTH CHECK
    // ============================================================

    /**
     * Setup health check interval
     */
    _setupHealthCheck() {
        this.healthCheckInterval = setInterval(() => {
            this.healthCheck().catch(() => {});
        }, 30000);
    }

    /**
     * Cleanup health check interval
     */
    _cleanupHealthCheck() {
        if (this.healthCheckInterval) {
            clearInterval(this.healthCheckInterval);
            this.healthCheckInterval = null;
        }
    }

    // ============================================================
    // INTERCEPTORS
    // ============================================================

    /**
     * Setup request/response interceptors
     */
    _setupInterceptors() {
        // Interceptor can be extended by user
        this.interceptors = {
            request: [],
            response: [],
            error: [],
        };
    }

    /**
     * Add request interceptor
     * 
     * @param {Function} interceptor - Interceptor function
     */
    addRequestInterceptor(interceptor) {
        this.interceptors.request.push(interceptor);
    }

    /**
     * Add response interceptor
     * 
     * @param {Function} interceptor - Interceptor function
     */
    addResponseInterceptor(interceptor) {
        this.interceptors.response.push(interceptor);
    }

    /**
     * Add error interceptor
     * 
     * @param {Function} interceptor - Interceptor function
     */
    addErrorInterceptor(interceptor) {
        this.interceptors.error.push(interceptor);
    }

    // ============================================================
    // EVENT SYSTEM
    // ============================================================

    /**
     * Add event listener
     * 
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
     * 
     * @param {string} event - Event name
     * @param {Function} listener - Event listener
     */
    off(event, listener) {
        if (this.eventListeners.has(event)) {
            const listeners = this.eventListeners.get(event);
            const index = listeners.indexOf(listener);
            if (index !== -1) {
                listeners.splice(index, 1);
            }
        }
    }

    /**
     * Emit event
     * 
     * @param {string} event - Event name
     * @param {*} data - Event data
     */
    _emit(event, data) {
        if (this.eventListeners.has(event)) {
            for (const listener of this.eventListeners.get(event)) {
                try {
                    listener(data);
                } catch (error) {
                    this.log('Error in event listener:', error);
                }
            }
        }
    }

    // ============================================================
    // LOGGING
    // ============================================================

    /**
     * Log message
     * 
     * @param {...*} args - Log arguments
     */
    log(...args) {
        if (this.config.debug) {
            console.log('[NexusAPI]', ...args);
        }
    }

    // ============================================================
    // CLEANUP
    // ============================================================

    /**
     * Cleanup resources
     */
    destroy() {
        this._cleanupHealthCheck();
        this._stopWebSocketHeartbeat();
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
        this.eventListeners.clear();
        this.log('API Client destroyed');
    }
}

// ============================================================
// EXPORTS
// ============================================================

// Export for Node.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NexusAPIClient;
}

// Export for browser
if (typeof window !== 'undefined') {
    window.NexusAPIClient = NexusAPIClient;
}

export default NexusAPIClient;

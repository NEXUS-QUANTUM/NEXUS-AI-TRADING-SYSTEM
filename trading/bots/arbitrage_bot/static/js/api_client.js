// trading/bots/arbitrage_bot/static/js/api_client.js
// NEXUS AI TRADING SYSTEM
// Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
// Version: 4.2.0 - Complete API Client with Real API Integration

/**
 * NEXUS API Client - Complete REST API Client
 * 
 * This module provides a comprehensive API client for the NEXUS AI Trading System
 * with support for:
 * - Authentication (JWT)
 * - Request/Response interceptors
 * - Error handling
 * - Retry logic
 * - Rate limiting
 * - WebSocket connections
 * - File uploads
 * - Real-time data streaming
 * 
 * @author NEXUS QUANTUM LTD
 * @version 4.2.0
 */

// ================================================================
// CONFIGURATION
// ================================================================

const API_CONFIG = {
    baseURL: '/api',
    version: 'v1',
    timeout: 30000,
    retryAttempts: 3,
    retryDelay: 1000,
    maxConcurrentRequests: 10,
    defaultHeaders: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    },
    endpoints: {
        // Auth
        auth: {
            login: '/auth/login',
            logout: '/auth/logout',
            refresh: '/auth/refresh',
            register: '/auth/register',
            verify: '/auth/verify',
            forgotPassword: '/auth/forgot-password',
            resetPassword: '/auth/reset-password',
            me: '/auth/me',
        },
        // Dashboard
        dashboard: {
            overview: '/dashboard/overview',
            metrics: '/dashboard/metrics',
            activity: '/dashboard/activity',
            status: '/dashboard/status',
        },
        // Exchanges
        exchanges: {
            list: '/exchanges',
            get: '/exchanges/:id',
            create: '/exchanges',
            update: '/exchanges/:id',
            delete: '/exchanges/:id',
            connect: '/exchanges/:id/connect',
            disconnect: '/exchanges/:id/disconnect',
            status: '/exchanges/status',
            metrics: '/exchanges/:id/metrics',
        },
        // Opportunities
        opportunities: {
            list: '/opportunities',
            get: '/opportunities/:id',
            execute: '/opportunities/:id/execute',
            dismiss: '/opportunities/:id/dismiss',
            clear: '/opportunities/clear',
            stats: '/opportunities/stats',
            autoExecute: '/opportunities/auto-execute',
        },
        // Strategies
        strategies: {
            list: '/strategies',
            get: '/strategies/:id',
            create: '/strategies',
            update: '/strategies/:id',
            delete: '/strategies/:id',
            start: '/strategies/:id/start',
            pause: '/strategies/:id/pause',
            stop: '/strategies/:id/stop',
            stats: '/strategies/stats',
        },
        // Performance
        performance: {
            overview: '/performance',
            metrics: '/performance/metrics',
            equity: '/performance/equity',
            monthly: '/performance/monthly',
            drawdown: '/performance/drawdown',
            strategies: '/performance/strategies',
            distribution: '/performance/strategy-distribution',
            export: '/performance/export',
        },
        // Reports
        reports: {
            list: '/reports',
            get: '/reports/:id',
            generate: '/reports/generate',
            download: '/reports/:id/download',
            delete: '/reports/:id',
            stats: '/reports/stats',
        },
        // Portfolio
        portfolio: {
            overview: '/portfolio',
            positions: '/portfolio/positions',
            history: '/portfolio/history',
            performance: '/portfolio/performance',
            allocation: '/portfolio/allocation',
        },
        // Settings
        settings: {
            general: '/settings/general',
            trading: '/settings/trading',
            exchanges: '/settings/exchanges',
            strategies: '/settings/strategies',
            security: '/settings/security',
            notifications: '/settings/notifications',
            advanced: '/settings/advanced',
            export: '/settings/export',
            import: '/settings/import',
        },
        // System
        system: {
            status: '/system/status',
            health: '/system/health',
            metrics: '/system/metrics',
            restart: '/system/restart',
            cache: '/system/cache',
            migrations: '/system/migrations',
            logs: '/system/logs',
        },
        // WebSocket
        ws: {
            dashboard: '/ws/dashboard',
            opportunities: '/ws/opportunities',
            strategies: '/ws/strategies',
            performance: '/ws/performance',
            reports: '/ws/reports',
            exchanges: '/ws/exchanges',
            logs: '/ws/logs',
            alerts: '/ws/alerts',
            status: '/ws/status',
            portfolio: '/ws/portfolio',
            trades: '/ws/trades',
            chart: '/ws/charts',
        },
    },
};

// ================================================================
// API CLIENT CLASS
// ================================================================

class APIClient {
    constructor(config = {}) {
        this.config = {
            ...API_CONFIG,
            ...config,
        };
        
        this.baseURL = this.config.baseURL;
        this.version = this.config.version;
        this.timeout = this.config.timeout;
        this.retryAttempts = this.config.retryAttempts;
        this.retryDelay = this.config.retryDelay;
        
        this.token = null;
        this.refreshToken = null;
        this.user = null;
        
        this.pendingRequests = new Map();
        this.requestQueue = [];
        this.activeRequests = 0;
        this.maxConcurrent = this.config.maxConcurrentRequests;
        
        this.eventListeners = new Map();
        this.wsConnections = new Map();
        
        // Interceptors
        this.requestInterceptors = [];
        this.responseInterceptors = [];
        this.errorInterceptors = [];
        
        // Initialize
        this._loadToken();
        this._setupDefaultInterceptors();
    }
    
    // ============================================================
    // AUTHENTICATION
    // ============================================================
    
    _loadToken() {
        try {
            const token = localStorage.getItem('nexus_access_token');
            const refresh = localStorage.getItem('nexus_refresh_token');
            const user = localStorage.getItem('nexus_user');
            
            if (token) this.token = token;
            if (refresh) this.refreshToken = refresh;
            if (user) this.user = JSON.parse(user);
        } catch (error) {
            console.error('Failed to load tokens:', error);
        }
    }
    
    _saveToken(token, refresh, user) {
        this.token = token;
        this.refreshToken = refresh;
        this.user = user;
        
        try {
            if (token) localStorage.setItem('nexus_access_token', token);
            if (refresh) localStorage.setItem('nexus_refresh_token', refresh);
            if (user) localStorage.setItem('nexus_user', JSON.stringify(user));
        } catch (error) {
            console.error('Failed to save tokens:', error);
        }
    }
    
    _clearToken() {
        this.token = null;
        this.refreshToken = null;
        this.user = null;
        
        try {
            localStorage.removeItem('nexus_access_token');
            localStorage.removeItem('nexus_refresh_token');
            localStorage.removeItem('nexus_user');
        } catch (error) {
            console.error('Failed to clear tokens:', error);
        }
    }
    
    async login(email, password) {
        try {
            const response = await this._request('POST', this.config.endpoints.auth.login, {
                email,
                password,
            });
            
            if (response && response.access_token) {
                this._saveToken(
                    response.access_token,
                    response.refresh_token,
                    response.user
                );
                this._emit('login', response);
                return response;
            }
            
            throw new Error('Invalid login response');
        } catch (error) {
            this._emit('login_error', error);
            throw error;
        }
    }
    
    async logout() {
        try {
            if (this.token) {
                await this._request('POST', this.config.endpoints.auth.logout);
            }
        } catch (error) {
            console.error('Logout error:', error);
        } finally {
            this._clearToken();
            this._emit('logout');
            // Close all WebSocket connections
            this._closeAllWebSockets();
        }
    }
    
    async refreshAccessToken() {
        if (!this.refreshToken) {
            throw new Error('No refresh token available');
        }
        
        try {
            const response = await this._request('POST', this.config.endpoints.auth.refresh, {
                refresh_token: this.refreshToken,
            });
            
            if (response && response.access_token) {
                this._saveToken(
                    response.access_token,
                    response.refresh_token || this.refreshToken,
                    this.user
                );
                return response;
            }
            
            throw new Error('Invalid refresh response');
        } catch (error) {
            this._clearToken();
            throw error;
        }
    }
    
    async register(userData) {
        try {
            const response = await this._request('POST', this.config.endpoints.auth.register, userData);
            this._emit('register', response);
            return response;
        } catch (error) {
            this._emit('register_error', error);
            throw error;
        }
    }
    
    async verifyEmail(token) {
        return this._request('POST', this.config.endpoints.auth.verify, { token });
    }
    
    async forgotPassword(email) {
        return this._request('POST', this.config.endpoints.auth.forgotPassword, { email });
    }
    
    async resetPassword(token, password) {
        return this._request('POST', this.config.endpoints.auth.resetPassword, { token, password });
    }
    
    async getCurrentUser() {
        if (this.user) return this.user;
        
        try {
            const response = await this._request('GET', this.config.endpoints.auth.me);
            if (response) {
                this.user = response;
                return response;
            }
        } catch (error) {
            throw error;
        }
    }
    
    isAuthenticated() {
        return !!this.token;
    }
    
    getToken() {
        return this.token;
    }
    
    // ============================================================
    // REQUEST METHODS
    // ============================================================
    
    async get(url, params = {}, options = {}) {
        return this._request('GET', url, params, options);
    }
    
    async post(url, data = {}, options = {}) {
        return this._request('POST', url, data, options);
    }
    
    async put(url, data = {}, options = {}) {
        return this._request('PUT', url, data, options);
    }
    
    async patch(url, data = {}, options = {}) {
        return this._request('PATCH', url, data, options);
    }
    
    async delete(url, params = {}, options = {}) {
        return this._request('DELETE', url, params, options);
    }
    
    async upload(url, file, data = {}, options = {}) {
        const formData = new FormData();
        formData.append('file', file);
        
        for (const [key, value] of Object.entries(data)) {
            formData.append(key, value);
        }
        
        return this._request('POST', url, formData, {
            ...options,
            headers: {
                'Content-Type': 'multipart/form-data',
            },
        });
    }
    
    // ============================================================
    // CORE REQUEST METHOD
    // ============================================================
    
    async _request(method, endpoint, data = null, options = {}) {
        // Build URL
        let url = this._buildURL(endpoint);
        
        // Prepare request
        const requestId = this._generateRequestId();
        const headers = {
            ...this.config.defaultHeaders,
            ...options.headers,
        };
        
        // Add auth token
        if (this.token && !options.public) {
            headers['Authorization'] = `Bearer ${this.token}`;
        }
        
        // Add version header
        headers['API-Version'] = this.version;
        
        // Prepare request options
        const requestOptions = {
            method,
            headers,
            credentials: 'include',
            signal: options.signal || null,
        };
        
        // Add body
        if (data) {
            if (data instanceof FormData) {
                requestOptions.body = data;
                delete headers['Content-Type'];
            } else {
                requestOptions.body = JSON.stringify(data);
            }
        }
        
        // Add query params for GET/DELETE
        if (method === 'GET' || method === 'DELETE') {
            const queryString = this._buildQueryString(data);
            if (queryString) {
                url += (url.includes('?') ? '&' : '?') + queryString;
            }
        }
        
        // Apply request interceptors
        let interceptedOptions = { ...requestOptions };
        for (const interceptor of this.requestInterceptors) {
            interceptedOptions = interceptor(url, interceptedOptions) || interceptedOptions;
        }
        
        // Queue request if needed
        if (this.activeRequests >= this.maxConcurrent) {
            await this._queueRequest();
        }
        
        this.activeRequests++;
        
        try {
            // Execute with retry
            const response = await this._executeWithRetry(url, interceptedOptions, this.retryAttempts);
            
            // Apply response interceptors
            let processedResponse = response;
            for (const interceptor of this.responseInterceptors) {
                processedResponse = interceptor(processedResponse) || processedResponse;
            }
            
            this.activeRequests--;
            this._processQueue();
            
            return processedResponse;
            
        } catch (error) {
            this.activeRequests--;
            this._processQueue();
            
            // Apply error interceptors
            let processedError = error;
            for (const interceptor of this.errorInterceptors) {
                processedError = interceptor(processedError) || processedError;
            }
            
            // Handle token refresh
            if (error.status === 401 && this.token && !options._retry) {
                try {
                    await this.refreshAccessToken();
                    options._retry = true;
                    return this._request(method, endpoint, data, options);
                } catch (refreshError) {
                    // Refresh failed, clear token
                    this._clearToken();
                    this._emit('unauthorized', refreshError);
                    throw refreshError;
                }
            }
            
            throw processedError;
        }
    }
    
    async _executeWithRetry(url, options, retries) {
        let attempt = 0;
        let lastError = null;
        
        while (attempt <= retries) {
            try {
                const response = await fetch(url, options);
                
                if (!response.ok) {
                    const error = await this._parseError(response);
                    throw error;
                }
                
                return await this._parseResponse(response);
                
            } catch (error) {
                lastError = error;
                attempt++;
                
                if (attempt > retries) {
                    throw lastError;
                }
                
                // Check if we should retry
                if (!this._shouldRetry(error)) {
                    throw error;
                }
                
                // Wait before retry
                await this._delay(this.retryDelay * attempt);
            }
        }
        
        throw lastError;
    }
    
    async _parseResponse(response) {
        const contentType = response.headers.get('content-type');
        
        if (contentType && contentType.includes('application/json')) {
            return response.json();
        }
        
        if (contentType && contentType.includes('text/')) {
            return response.text();
        }
        
        return response.blob();
    }
    
    async _parseError(response) {
        let errorData;
        
        try {
            errorData = await response.json();
        } catch {
            errorData = { message: response.statusText };
        }
        
        const error = new Error(errorData.message || 'Request failed');
        error.status = response.status;
        error.statusText = response.statusText;
        error.data = errorData;
        error.response = response;
        
        return error;
    }
    
    _shouldRetry(error) {
        // Retry on network errors, timeouts, and 5xx errors
        if (error.status >= 500 && error.status < 600) return true;
        if (error.status === 429) return true;
        if (error.code === 'ECONNABORTED' || error.code === 'ETIMEDOUT') return true;
        if (error.message.includes('network')) return true;
        
        return false;
    }
    
    _buildURL(endpoint) {
        let url = endpoint;
        
        // Add base URL
        if (!url.startsWith('http')) {
            url = this.baseURL + url;
        }
        
        // Replace path parameters
        for (const [key, value] of Object.entries(this.config.endpoints)) {
            if (typeof value === 'object') {
                for (const [subKey, subValue] of Object.entries(value)) {
                    if (typeof subValue === 'string' && subValue.includes(':id')) {
                        // Handle dynamic paths
                    }
                }
            }
        }
        
        return url;
    }
    
    _buildQueryString(params) {
        if (!params || typeof params !== 'object') return '';
        
        const query = [];
        for (const [key, value] of Object.entries(params)) {
            if (value === undefined || value === null) continue;
            if (Array.isArray(value)) {
                for (const item of value) {
                    query.push(`${encodeURIComponent(key)}[]=${encodeURIComponent(item)}`);
                }
            } else {
                query.push(`${encodeURIComponent(key)}=${encodeURIComponent(value)}`);
            }
        }
        
        return query.join('&');
    }
    
    _generateRequestId() {
        return 'req_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
    }
    
    _delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }
    
    // ============================================================
    // REQUEST QUEUE
    // ============================================================
    
    _queueRequest() {
        return new Promise((resolve) => {
            this.requestQueue.push(resolve);
        });
    }
    
    _processQueue() {
        while (this.activeRequests < this.maxConcurrent && this.requestQueue.length > 0) {
            const resolve = this.requestQueue.shift();
            this.activeRequests++;
            resolve();
        }
    }
    
    // ============================================================
    // INTERCEPTORS
    // ============================================================
    
    addRequestInterceptor(interceptor) {
        this.requestInterceptors.push(interceptor);
    }
    
    addResponseInterceptor(interceptor) {
        this.responseInterceptors.push(interceptor);
    }
    
    addErrorInterceptor(interceptor) {
        this.errorInterceptors.push(interceptor);
    }
    
    _setupDefaultInterceptors() {
        // Logging interceptor
        this.addRequestInterceptor((url, options) => {
            if (process.env.NODE_ENV === 'development') {
                console.log('API Request:', {
                    url,
                    method: options.method,
                    headers: options.headers,
                });
            }
            return options;
        });
        
        // Response interceptor
        this.addResponseInterceptor((response) => {
            if (process.env.NODE_ENV === 'development') {
                console.log('API Response:', response);
            }
            return response;
        });
        
        // Error interceptor
        this.addErrorInterceptor((error) => {
            if (error.status === 401) {
                this._emit('unauthorized', error);
            }
            if (error.status >= 500) {
                this._emit('server_error', error);
            }
            return error;
        });
    }
    
    // ============================================================
    // WEBSOCKET CONNECTIONS
    // ============================================================
    
    connectWebSocket(channel, options = {}) {
        const endpoint = this.config.endpoints.ws[channel];
        if (!endpoint) {
            throw new Error(`Unknown WebSocket channel: ${channel}`);
        }
        
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const token = this.token ? `?token=${encodeURIComponent(this.token)}` : '';
        const url = `${protocol}//${host}${endpoint}${token}`;
        
        // Check if already connected
        if (this.wsConnections.has(channel)) {
            const existing = this.wsConnections.get(channel);
            if (existing.readyState === WebSocket.OPEN) {
                return existing;
            }
            this._closeWebSocket(channel);
        }
        
        const ws = new WebSocket(url);
        ws.onopen = () => {
            this._emit(`ws:${channel}:open`, { channel, ws });
            if (options.onOpen) options.onOpen();
        };
        
        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this._emit(`ws:${channel}:message`, data);
                if (options.onMessage) options.onMessage(data);
            } catch (error) {
                console.error('WebSocket message error:', error);
            }
        };
        
        ws.onclose = (event) => {
            this.wsConnections.delete(channel);
            this._emit(`ws:${channel}:close`, event);
            if (options.onClose) options.onClose(event);
            
            // Auto-reconnect
            if (options.reconnect !== false && event.code !== 1000) {
                setTimeout(() => {
                    this.connectWebSocket(channel, options);
                }, 5000);
            }
        };
        
        ws.onerror = (error) => {
            this._emit(`ws:${channel}:error`, error);
            if (options.onError) options.onError(error);
        };
        
        this.wsConnections.set(channel, ws);
        return ws;
    }
    
    disconnectWebSocket(channel) {
        this._closeWebSocket(channel);
    }
    
    _closeWebSocket(channel) {
        const ws = this.wsConnections.get(channel);
        if (ws) {
            try {
                ws.close(1000, 'Client disconnection');
            } catch (error) {
                console.error('WebSocket close error:', error);
            }
            this.wsConnections.delete(channel);
        }
    }
    
    _closeAllWebSockets() {
        for (const [channel, ws] of this.wsConnections) {
            try {
                ws.close(1000, 'Client disconnection');
            } catch (error) {
                console.error('WebSocket close error:', error);
            }
        }
        this.wsConnections.clear();
    }
    
    sendWebSocketMessage(channel, data) {
        const ws = this.wsConnections.get(channel);
        if (!ws || ws.readyState !== WebSocket.OPEN) {
            throw new Error(`WebSocket not connected: ${channel}`);
        }
        
        ws.send(JSON.stringify(data));
    }
    
    // ============================================================
    // EVENT SYSTEM
    // ============================================================
    
    on(event, callback) {
        if (!this.eventListeners.has(event)) {
            this.eventListeners.set(event, []);
        }
        this.eventListeners.get(event).push(callback);
    }
    
    off(event, callback) {
        if (!this.eventListeners.has(event)) return;
        const listeners = this.eventListeners.get(event);
        const index = listeners.indexOf(callback);
        if (index !== -1) {
            listeners.splice(index, 1);
        }
    }
    
    _emit(event, data) {
        if (!this.eventListeners.has(event)) return;
        for (const listener of this.eventListeners.get(event)) {
            try {
                listener(data);
            } catch (error) {
                console.error(`Event listener error (${event}):`, error);
            }
        }
    }
    
    // ============================================================
    // CONVENIENCE METHODS
    // ============================================================
    
    // Dashboard
    async getDashboardOverview(params = {}) {
        return this.get(this.config.endpoints.dashboard.overview, params);
    }
    
    async getDashboardMetrics(params = {}) {
        return this.get(this.config.endpoints.dashboard.metrics, params);
    }
    
    async getDashboardActivity(params = {}) {
        return this.get(this.config.endpoints.dashboard.activity, params);
    }
    
    // Exchanges
    async getExchanges(params = {}) {
        return this.get(this.config.endpoints.exchanges.list, params);
    }
    
    async getExchange(id) {
        return this.get(this.config.endpoints.exchanges.get.replace(':id', id));
    }
    
    async createExchange(data) {
        return this.post(this.config.endpoints.exchanges.create, data);
    }
    
    async updateExchange(id, data) {
        return this.put(this.config.endpoints.exchanges.update.replace(':id', id), data);
    }
    
    async deleteExchange(id) {
        return this.delete(this.config.endpoints.exchanges.delete.replace(':id', id));
    }
    
    async connectExchange(id) {
        return this.post(this.config.endpoints.exchanges.connect.replace(':id', id));
    }
    
    async disconnectExchange(id) {
        return this.post(this.config.endpoints.exchanges.disconnect.replace(':id', id));
    }
    
    // Opportunities
    async getOpportunities(params = {}) {
        return this.get(this.config.endpoints.opportunities.list, params);
    }
    
    async getOpportunity(id) {
        return this.get(this.config.endpoints.opportunities.get.replace(':id', id));
    }
    
    async executeOpportunity(id) {
        return this.post(this.config.endpoints.opportunities.execute.replace(':id', id));
    }
    
    async dismissOpportunity(id) {
        return this.delete(this.config.endpoints.opportunities.dismiss.replace(':id', id));
    }
    
    async clearOpportunities() {
        return this.delete(this.config.endpoints.opportunities.clear);
    }
    
    async getOpportunityStats() {
        return this.get(this.config.endpoints.opportunities.stats);
    }
    
    async toggleAutoExecute(enabled) {
        return this.post(this.config.endpoints.opportunities.autoExecute, { enabled });
    }
    
    // Strategies
    async getStrategies(params = {}) {
        return this.get(this.config.endpoints.strategies.list, params);
    }
    
    async getStrategy(id) {
        return this.get(this.config.endpoints.strategies.get.replace(':id', id));
    }
    
    async createStrategy(data) {
        return this.post(this.config.endpoints.strategies.create, data);
    }
    
    async updateStrategy(id, data) {
        return this.put(this.config.endpoints.strategies.update.replace(':id', id), data);
    }
    
    async deleteStrategy(id) {
        return this.delete(this.config.endpoints.strategies.delete.replace(':id', id));
    }
    
    async startStrategy(id) {
        return this.post(this.config.endpoints.strategies.start.replace(':id', id));
    }
    
    async pauseStrategy(id) {
        return this.post(this.config.endpoints.strategies.pause.replace(':id', id));
    }
    
    async stopStrategy(id) {
        return this.post(this.config.endpoints.strategies.stop.replace(':id', id));
    }
    
    async getStrategyStats() {
        return this.get(this.config.endpoints.strategies.stats);
    }
    
    // Performance
    async getPerformance(params = {}) {
        return this.get(this.config.endpoints.performance.overview, params);
    }
    
    async getPerformanceMetrics(params = {}) {
        return this.get(this.config.endpoints.performance.metrics, params);
    }
    
    async getEquityData(params = {}) {
        return this.get(this.config.endpoints.performance.equity, params);
    }
    
    async getMonthlyReturns(params = {}) {
        return this.get(this.config.endpoints.performance.monthly, params);
    }
    
    async getDrawdownData(params = {}) {
        return this.get(this.config.endpoints.performance.drawdown, params);
    }
    
    async getStrategyPerformance(params = {}) {
        return this.get(this.config.endpoints.performance.strategies, params);
    }
    
    async getStrategyDistribution(params = {}) {
        return this.get(this.config.endpoints.performance.distribution, params);
    }
    
    async exportPerformance(params = {}) {
        return this.get(this.config.endpoints.performance.export, params);
    }
    
    // Reports
    async getReports(params = {}) {
        return this.get(this.config.endpoints.reports.list, params);
    }
    
    async getReport(id) {
        return this.get(this.config.endpoints.reports.get.replace(':id', id));
    }
    
    async generateReport(data) {
        return this.post(this.config.endpoints.reports.generate, data);
    }
    
    async downloadReport(id) {
        return this.get(this.config.endpoints.reports.download.replace(':id', id));
    }
    
    async deleteReport(id) {
        return this.delete(this.config.endpoints.reports.delete.replace(':id', id));
    }
    
    async getReportStats() {
        return this.get(this.config.endpoints.reports.stats);
    }
    
    // Portfolio
    async getPortfolioOverview(params = {}) {
        return this.get(this.config.endpoints.portfolio.overview, params);
    }
    
    async getPositions(params = {}) {
        return this.get(this.config.endpoints.portfolio.positions, params);
    }
    
    async getPortfolioHistory(params = {}) {
        return this.get(this.config.endpoints.portfolio.history, params);
    }
    
    async getPortfolioPerformance(params = {}) {
        return this.get(this.config.endpoints.portfolio.performance, params);
    }
    
    async getPortfolioAllocation(params = {}) {
        return this.get(this.config.endpoints.portfolio.allocation, params);
    }
    
    // Settings
    async getSettings(section) {
        const endpoint = this.config.endpoints.settings[section];
        if (!endpoint) throw new Error(`Unknown settings section: ${section}`);
        return this.get(endpoint);
    }
    
    async updateSettings(section, data) {
        const endpoint = this.config.endpoints.settings[section];
        if (!endpoint) throw new Error(`Unknown settings section: ${section}`);
        return this.post(endpoint, data);
    }
    
    async exportSettings() {
        return this.get(this.config.endpoints.settings.export);
    }
    
    async importSettings(data) {
        return this.post(this.config.endpoints.settings.import, data);
    }
    
    // System
    async getSystemStatus() {
        return this.get(this.config.endpoints.system.status);
    }
    
    async getSystemHealth() {
        return this.get(this.config.endpoints.system.health);
    }
    
    async getSystemMetrics() {
        return this.get(this.config.endpoints.system.metrics);
    }
    
    async restartSystem() {
        return this.post(this.config.endpoints.system.restart);
    }
    
    async clearCache() {
        return this.delete(this.config.endpoints.system.cache);
    }
    
    async runMigrations() {
        return this.post(this.config.endpoints.system.migrations);
    }
    
    async getSystemLogs(params = {}) {
        return this.get(this.config.endpoints.system.logs, params);
    }
}

// ================================================================
// EXPORT
// ================================================================

// Create singleton instance
const apiClient = new APIClient();

// Export for module usage
if (typeof module !== 'undefined' && module.exports) {
    module.exports = {
        APIClient,
        apiClient,
        API_CONFIG,
    };
}

// Export for browser usage
if (typeof window !== 'undefined') {
    window.apiClient = apiClient;
    window.APIClient = APIClient;
}

// ================================================================
// USAGE EXAMPLES
// ================================================================

/*
// Authentication
await apiClient.login('user@example.com', 'password');
await apiClient.logout();

// Get dashboard data
const dashboard = await apiClient.getDashboardOverview();
const metrics = await apiClient.getDashboardMetrics();

// Manage exchanges
const exchanges = await apiClient.getExchanges();
await apiClient.connectExchange('exchange-id');

// Manage opportunities
const opportunities = await apiClient.getOpportunities({ status: 'pending' });
await apiClient.executeOpportunity('opportunity-id');

// Manage strategies
const strategies = await apiClient.getStrategies({ status: 'running' });
await apiClient.startStrategy('strategy-id');

// Get performance data
const performance = await apiClient.getPerformance({ period: '30d' });
const equity = await apiClient.getEquityData({ period: '7d' });

// Generate report
const report = await apiClient.generateReport({
    type: 'daily',
    format: 'pdf',
    start_date: '2026-01-01',
    end_date: '2026-01-07',
});

// WebSocket real-time data
apiClient.connectWebSocket('dashboard', {
    onMessage: (data) => {
        console.log('Dashboard update:', data);
    },
});

// Events
apiClient.on('login', (data) => {
    console.log('User logged in:', data.user);
});

apiClient.on('unauthorized', (error) => {
    console.log('Unauthorized access:', error);
});
*/

/**
 * NEXUS AI TRADING SYSTEM - Arbitrage Bot WebSocket Module
 * Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
 * @version 2.1.0
 * @author NEXUS QUANTUM TEAM
 */

// ============================================================
// CORE WEBSOCKET MANAGER
// ============================================================

class WebSocketManager {
    constructor(options = {}) {
        // Configuration
        this.config = {
            url: options.url || this.getDefaultUrl(),
            protocols: options.protocols || [],
            reconnect: options.reconnect !== undefined ? options.reconnect : true,
            reconnectDelay: options.reconnectDelay || 3000,
            maxReconnectAttempts: options.maxReconnectAttempts || 10,
            heartbeatInterval: options.heartbeatInterval || 30000,
            heartbeatTimeout: options.heartbeatTimeout || 10000,
            pingMessage: options.pingMessage || 'ping',
            pongMessage: options.pongMessage || 'pong',
            autoConnect: options.autoConnect !== undefined ? options.autoConnect : true,
            debug: options.debug || false,
            binaryType: options.binaryType || 'blob',
            maxMessageSize: options.maxMessageSize || 1024 * 1024, // 1MB
            compression: options.compression !== undefined ? options.compression : true,
            authToken: options.authToken || null,
            sessionId: options.sessionId || this.generateSessionId(),
        };

        // State
        this.ws = null;
        this.isConnected = false;
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.heartbeatTimer = null;
        this.heartbeatTimeoutTimer = null;
        this.lastHeartbeat = null;
        this.messageQueue = [];
        this.subscriptions = new Map();
        this.eventListeners = new Map();
        this.messageHandlers = new Map();
        this.requestPromises = new Map();
        this.messageIdCounter = 0;
        this.connectionStartTime = null;
        this.totalReconnects = 0;
        this.bytesReceived = 0;
        this.bytesSent = 0;
        this.messagesReceived = 0;
        this.messagesSent = 0;
        this.lastError = null;
        this.reconnectTimer = null;

        // Promise resolvers for connection
        this.connectionPromise = null;
        this.connectionResolve = null;
        this.connectionReject = null;

        // Initialize
        if (this.config.autoConnect) {
            this.connect();
        }

        this.setupVisibilityHandler();
        this.setupOnlineHandler();
        this.setupBeforeUnloadHandler();

        if (this.config.debug) {
            console.log('🔧 WebSocketManager initialized with config:', this.config);
            console.log(`📋 Session ID: ${this.config.sessionId}`);
        }
    }

    // ============================================================
    // CONNECTION METHODS
    // ============================================================

    getDefaultUrl() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const host = window.location.host;
        const path = '/ws/arbitrage';
        return `${protocol}//${host}${path}`;
    }

    generateSessionId() {
        return `nexus_ws_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    }

    connect() {
        if (this.isConnected || this.isConnecting) {
            if (this.config.debug) {
                console.log('ℹ️ Already connected or connecting');
            }
            return this.connectionPromise;
        }

        if (this.config.debug) {
            console.log('🔌 Connecting to WebSocket:', this.config.url);
        }

        this.isConnecting = true;
        this.connectionStartTime = Date.now();
        this.lastError = null;
        
        this.connectionPromise = new Promise((resolve, reject) => {
            this.connectionResolve = resolve;
            this.connectionReject = reject;
        });

        try {
            // Build URL with query parameters
            let url = this.config.url;
            const params = new URLSearchParams();
            if (this.config.authToken) {
                params.append('token', this.config.authToken);
            }
            if (this.config.sessionId) {
                params.append('sessionId', this.config.sessionId);
            }
            if (params.toString()) {
                url += (url.includes('?') ? '&' : '?') + params.toString();
            }

            this.ws = new WebSocket(url, this.config.protocols);
            this.ws.binaryType = this.config.binaryType;
            this.setupWebSocketEvents();
        } catch (error) {
            this.isConnecting = false;
            this.handleError(error);
            if (this.connectionReject) {
                this.connectionReject(error);
            }
            this.connectionPromise = null;
        }

        return this.connectionPromise;
    }

    setupWebSocketEvents() {
        if (!this.ws) return;

        this.ws.onopen = (event) => this.handleOpen(event);
        this.ws.onmessage = (event) => this.handleMessage(event);
        this.ws.onclose = (event) => this.handleClose(event);
        this.ws.onerror = (event) => this.handleError(event);
    }

    handleOpen(event) {
        this.isConnected = true;
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.lastHeartbeat = Date.now();
        this.connectionStartTime = Date.now();

        if (this.config.debug) {
            console.log('✅ WebSocket connected');
            console.log(`⏱️ Connection time: ${new Date().toISOString()}`);
        }

        // Start heartbeat
        this.startHeartbeat();

        // Process queued messages
        this.flushMessageQueue();

        // Resolve connection promise
        if (this.connectionResolve) {
            this.connectionResolve(this);
            this.connectionPromise = null;
            this.connectionResolve = null;
            this.connectionReject = null;
        }

        // Emit connection event
        this.emit('connect', { 
            event, 
            sessionId: this.config.sessionId,
            timestamp: new Date().toISOString(),
            connectionTime: Date.now() - this.connectionStartTime,
        });

        // Re-subscribe
        this.resubscribe();

        // Send session info
        this.sendJSON('session_info', {
            sessionId: this.config.sessionId,
            userAgent: navigator.userAgent,
            platform: navigator.platform,
            language: navigator.language,
            timestamp: new Date().toISOString(),
        });
    }

    handleMessage(event) {
        this.messagesReceived++;
        this.bytesReceived += event.data?.length || 0;

        if (this.config.debug) {
            const size = event.data?.length || 0;
            console.log(`📨 WebSocket message received (${size} bytes)`);
        }

        try {
            // Check for binary data
            if (event.data instanceof ArrayBuffer || event.data instanceof Blob) {
                this.handleBinaryMessage(event.data);
                return;
            }

            // Check for heartbeat response
            if (event.data === this.config.pongMessage) {
                this.handlePong();
                return;
            }

            // Parse JSON
            let data;
            try {
                data = JSON.parse(event.data);
            } catch (parseError) {
                // If not JSON, handle as raw message
                this.handleRawMessage(event.data);
                return;
            }

            // Handle message by type
            this.handleTypedMessage(data);

            // Emit message event
            this.emit('message', { 
                data, 
                timestamp: new Date().toISOString(),
                size: event.data?.length || 0,
            });

        } catch (error) {
            console.error('WebSocket message error:', error);
            this.emit('error', { error, message: event.data });
        }
    }

    handleTypedMessage(data) {
        const { type, payload, id, timestamp, error, result } = data;

        // Handle request responses (with id)
        if (id && this.requestPromises.has(id)) {
            const { resolve, reject } = this.requestPromises.get(id);
            this.requestPromises.delete(id);
            
            if (error) {
                reject(new Error(error));
            } else {
                resolve(result || payload);
            }
            return;
        }

        // Handle subscription responses
        if (type === 'subscribed' || type === 'unsubscribed') {
            this.handleSubscriptionResponse(type, payload);
            return;
        }

        // Handle acknowledgement
        if (type === 'ack' || type === 'nack') {
            this.handleAcknowledgement(type, payload, id);
            return;
        }

        // Handle error response
        if (type === 'error') {
            this.handleErrorMessage(payload, id);
            return;
        }

        // Handle data messages
        if (payload && typeof payload === 'object') {
            // Route to specific handlers
            this.routeMessage(type, payload);
        }

        // Notify subscribers
        this.notifySubscribers(type, data);

        // Call registered handlers
        if (this.messageHandlers.has(type)) {
            const handlers = this.messageHandlers.get(type);
            handlers.forEach(handler => {
                try {
                    handler(data, this);
                } catch (error) {
                    console.error(`Handler error for type ${type}:`, error);
                }
            });
        }
    }

    handleBinaryMessage(data) {
        // Handle binary data (e.g., protobuf, custom binary protocol)
        this.emit('binary', { 
            data, 
            timestamp: new Date().toISOString(),
            size: data.byteLength || data.size || 0,
            type: data instanceof ArrayBuffer ? 'ArrayBuffer' : 'Blob',
        });

        // Attempt to parse as protobuf if available
        if (this.config.protobufDecoder) {
            try {
                const decoded = this.config.protobufDecoder(data);
                this.emit('protobuf', decoded);
                this.handleTypedMessage(decoded);
            } catch (error) {
                console.error('Protobuf decode error:', error);
            }
        }
    }

    handleRawMessage(message) {
        // Handle raw messages (non-JSON)
        this.emit('raw', { 
            message, 
            timestamp: new Date().toISOString(),
        });
        
        // Check for heartbeat
        if (message === this.config.pongMessage) {
            this.handlePong();
        }
    }

    handleErrorMessage(payload, id) {
        const { code, message, details } = payload || {};
        console.error(`❌ WebSocket error [${code}]: ${message}`, details);
        this.lastError = { code, message, details };
        this.emit('error_message', { code, message, details, id });
    }

    handleClose(event) {
        this.isConnected = false;
        this.isConnecting = false;
        this.stopHeartbeat();
        this.connectionStartTime = null;

        if (this.config.debug) {
            console.log(`⚠️ WebSocket disconnected: ${event.code} - ${event.reason || 'No reason'}`);
            console.log(`🔢 Was clean: ${event.wasClean}`);
        }

        // Emit close event
        this.emit('close', { 
            event, 
            timestamp: new Date().toISOString(),
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean,
        });

        // Attempt reconnect
        if (this.config.reconnect && event.code !== 1000 && event.code !== 1001) {
            this.handleReconnection();
        } else {
            // Clear reconnect timer if any
            if (this.reconnectTimer) {
                clearTimeout(this.reconnectTimer);
                this.reconnectTimer = null;
            }
            this.emit('closed_permanent', { event });
        }
    }

    handleError(error) {
        console.error('❌ WebSocket error:', error);
        this.lastError = error;
        this.emit('error', { error, timestamp: new Date().toISOString() });
        
        // If we're connecting, reject the promise
        if (this.isConnecting && this.connectionReject) {
            this.connectionReject(error);
            this.connectionPromise = null;
            this.connectionResolve = null;
            this.connectionReject = null;
        }
    }

    // ============================================================
    // RECONNECTION
    // ============================================================

    handleReconnection() {
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        if (this.reconnectAttempts < this.config.maxReconnectAttempts) {
            this.reconnectAttempts++;
            this.totalReconnects++;
            
            // Exponential backoff with jitter
            const baseDelay = this.config.reconnectDelay;
            const maxDelay = 60000; // 1 minute
            const delay = Math.min(
                baseDelay * Math.pow(1.5, this.reconnectAttempts - 1) + Math.random() * 1000,
                maxDelay
            );
            
            if (this.config.debug) {
                console.log(`🔄 Reconnecting in ${(delay/1000).toFixed(1)}s (attempt ${this.reconnectAttempts}/${this.config.maxReconnectAttempts})`);
                console.log(`📊 Total reconnects: ${this.totalReconnects}`);
            }

            this.emit('reconnecting', {
                attempt: this.reconnectAttempts,
                maxAttempts: this.config.maxReconnectAttempts,
                delay: delay,
                totalReconnects: this.totalReconnects,
                timestamp: new Date().toISOString(),
            });

            this.reconnectTimer = setTimeout(() => {
                this.reconnectTimer = null;
                this.connect();
            }, delay);
        } else {
            console.error('❌ Max reconnection attempts reached');
            this.emit('reconnect_failed', {
                attempts: this.reconnectAttempts,
                maxAttempts: this.config.maxReconnectAttempts,
                totalReconnects: this.totalReconnects,
                timestamp: new Date().toISOString(),
            });
        }
    }

    // ============================================================
    // HEARTBEAT
    // ============================================================

    startHeartbeat() {
        this.stopHeartbeat();
        
        this.heartbeatTimer = setInterval(() => {
            this.sendPing();
        }, this.config.heartbeatInterval);

        if (this.config.debug) {
            console.log('💓 Heartbeat started');
        }
    }

    stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
        if (this.heartbeatTimeoutTimer) {
            clearTimeout(this.heartbeatTimeoutTimer);
            this.heartbeatTimeoutTimer = null;
        }
        if (this.config.debug) {
            console.log('💓 Heartbeat stopped');
        }
    }

    sendPing() {
        if (!this.isConnected) return;

        try {
            this.send(this.config.pingMessage);
            this.lastHeartbeat = Date.now();

            // Set timeout for pong response
            if (this.heartbeatTimeoutTimer) {
                clearTimeout(this.heartbeatTimeoutTimer);
            }
            this.heartbeatTimeoutTimer = setTimeout(() => {
                this.handleHeartbeatTimeout();
            }, this.config.heartbeatTimeout);

            this.messagesSent++;

        } catch (error) {
            console.error('Send ping error:', error);
        }
    }

    handlePong() {
        if (this.heartbeatTimeoutTimer) {
            clearTimeout(this.heartbeatTimeoutTimer);
            this.heartbeatTimeoutTimer = null;
        }
        this.lastHeartbeat = Date.now();
        if (this.config.debug) {
            console.log('💓 Heartbeat received');
        }
        this.emit('heartbeat', { 
            timestamp: new Date().toISOString(),
            latency: Date.now() - this.lastHeartbeat,
        });
    }

    handleHeartbeatTimeout() {
        console.warn('⚠️ Heartbeat timeout - no pong received');
        this.emit('heartbeat_timeout', { 
            timestamp: new Date().toISOString(),
            lastHeartbeat: this.lastHeartbeat,
        });
        
        // Close and reconnect
        if (this.ws) {
            try {
                this.ws.close(4000, 'Heartbeat timeout');
            } catch (error) {
                // Ignore
            }
            this.ws = null;
        }
        this.isConnected = false;
        this.handleReconnection();
    }

    // ============================================================
    // SEND METHODS
    // ============================================================

    send(data) {
        if (this.isConnected && this.ws && this.ws.readyState === WebSocket.OPEN) {
            try {
                if (typeof data === 'object') {
                    const json = JSON.stringify(data);
                    this.ws.send(json);
                    this.bytesSent += json.length;
                } else {
                    this.ws.send(data);
                    this.bytesSent += data.length || data.byteLength || 0;
                }
                this.messagesSent++;
                
                if (this.config.debug) {
                    console.log('📤 WebSocket sent:', typeof data === 'object' ? JSON.stringify(data).substring(0, 200) + '...' : data);
                }
                return true;
            } catch (error) {
                console.error('Send error:', error);
                this.emit('send_error', { error, data });
                return false;
            }
        } else {
            // Queue message for later
            this.queueMessage(data);
            if (this.config.debug) {
                console.log('📦 Message queued (not connected)');
            }
            return false;
        }
    }

    sendJSON(type, payload = {}, options = {}) {
        const message = {
            type: type,
            payload: payload,
            id: options.id || this.generateMessageId(),
            timestamp: new Date().toISOString(),
            ...options,
        };
        return this.send(message);
    }

    sendRequest(type, payload = {}, timeout = 30000) {
        return new Promise((resolve, reject) => {
            const id = this.generateMessageId();
            const message = {
                type: type,
                payload: payload,
                id: id,
                timestamp: new Date().toISOString(),
                request: true,
            };

            // Store promise resolvers
            this.requestPromises.set(id, { resolve, reject });

            // Set timeout
            const timeoutId = setTimeout(() => {
                if (this.requestPromises.has(id)) {
                    this.requestPromises.delete(id);
                    reject(new Error(`Request timeout after ${timeout}ms`));
                }
            }, timeout);

            // Override reject to clear timeout
            const originalReject = reject;
            const wrappedReject = (error) => {
                clearTimeout(timeoutId);
                originalReject(error);
            };
            this.requestPromises.set(id, { resolve, reject: wrappedReject });

            // Send message
            this.send(message);
        });
    }

    queueMessage(data) {
        this.messageQueue.push({
            data: data,
            timestamp: Date.now(),
        });

        // Limit queue size
        if (this.messageQueue.length > 1000) {
            this.messageQueue.shift();
        }
    }

    flushMessageQueue() {
        if (this.messageQueue.length === 0) return;

        const queue = [...this.messageQueue];
        this.messageQueue = [];

        if (this.config.debug) {
            console.log(`📤 Flushing ${queue.length} queued messages`);
        }

        queue.forEach(item => {
            this.send(item.data);
        });
    }

    generateMessageId() {
        return `msg_${Date.now()}_${(++this.messageIdCounter)}_${Math.random().toString(36).substr(2, 9)}`;
    }

    // ============================================================
    // SUBSCRIPTION SYSTEM
    // ============================================================

    subscribe(channel, callback) {
        if (!this.subscriptions.has(channel)) {
            this.subscriptions.set(channel, new Set());
        }
        this.subscriptions.get(channel).add(callback);

        // Send subscribe message if connected
        if (this.isConnected) {
            this.sendJSON('subscribe', { channel });
        }

        if (this.config.debug) {
            console.log(`📡 Subscribed to: ${channel}`);
        }

        // Return unsubscribe function
        return () => this.unsubscribe(channel, callback);
    }

    subscribeOnce(channel) {
        return new Promise((resolve) => {
            const unsubscribe = this.subscribe(channel, (data) => {
                unsubscribe();
                resolve(data);
            });
        });
    }

    unsubscribe(channel, callback) {
        if (this.subscriptions.has(channel)) {
            const callbacks = this.subscriptions.get(channel);
            if (callback) {
                callbacks.delete(callback);
            } else {
                callbacks.clear();
            }
            if (callbacks.size === 0) {
                this.subscriptions.delete(channel);
                // Send unsubscribe message
                if (this.isConnected) {
                    this.sendJSON('unsubscribe', { channel });
                }
            }
        }
        if (this.config.debug) {
            console.log(`📡 Unsubscribed from: ${channel}`);
        }
    }

    unsubscribeAll() {
        const channels = Array.from(this.subscriptions.keys());
        channels.forEach(channel => {
            if (channel !== '*') {
                this.unsubscribe(channel);
            }
        });
        this.subscriptions.clear();
        if (this.config.debug) {
            console.log('📡 Unsubscribed from all channels');
        }
    }

    notifySubscribers(channel, data) {
        if (this.subscriptions.has(channel)) {
            const callbacks = this.subscriptions.get(channel);
            callbacks.forEach(callback => {
                try {
                    callback(data, this);
                } catch (error) {
                    console.error(`Subscriber error for channel ${channel}:`, error);
                }
            });
        }

        // Also notify wildcard subscribers
        if (this.subscriptions.has('*')) {
            const callbacks = this.subscriptions.get('*');
            callbacks.forEach(callback => {
                try {
                    callback({ channel, data }, this);
                } catch (error) {
                    console.error('Wildcard subscriber error:', error);
                }
            });
        }
    }

    resubscribe() {
        if (!this.isConnected) return;

        const channels = Array.from(this.subscriptions.keys());
        channels.forEach(channel => {
            if (channel !== '*') {
                this.sendJSON('subscribe', { channel });
            }
        });

        if (this.config.debug) {
            console.log(`📡 Resubscribed to ${channels.length} channels`);
        }
    }

    handleSubscriptionResponse(type, payload) {
        const { channel, success, error, subscriptionId } = payload || {};
        if (type === 'subscribed') {
            this.emit('subscribed', { channel, success, error, subscriptionId });
            if (this.config.debug && success) {
                console.log(`✅ Subscribed to channel: ${channel} (${subscriptionId})`);
            }
        } else if (type === 'unsubscribed') {
            this.emit('unsubscribed', { channel, success, error });
            if (this.config.debug && success) {
                console.log(`✅ Unsubscribed from channel: ${channel}`);
            }
        }
    }

    // ============================================================
    // ACKNOWLEDGEMENT SYSTEM
    // ============================================================

    handleAcknowledgement(type, payload, id) {
        const { success, error, result, timestamp } = payload || {};
        this.emit('ack', { 
            id, 
            success, 
            error, 
            result, 
            type,
            timestamp: timestamp || new Date().toISOString(),
        });
        
        if (this.config.debug) {
            console.log(`✅ Acknowledgement: ${id} - ${success ? 'OK' : 'FAIL'}${error ? ' (' + error + ')' : ''}`);
        }
    }

    // ============================================================
    // MESSAGE ROUTING
    // ============================================================

    routeMessage(type, payload) {
        // Route to specific handler based on type
        const routes = {
            'opportunity': this.handleOpportunity.bind(this),
            'execution': this.handleExecution.bind(this),
            'pnl': this.handlePnL.bind(this),
            'spread': this.handleSpread.bind(this),
            'volume': this.handleVolume.bind(this),
            'matrix': this.handleMatrix.bind(this),
            'metrics': this.handleMetrics.bind(this),
            'alert': this.handleAlert.bind(this),
            'config': this.handleConfig.bind(this),
            'state': this.handleState.bind(this),
            'performance': this.handlePerformance.bind(this),
            'settings': this.handleSettings.bind(this),
            'notification': this.handleNotification.bind(this),
            'heartbeat': this.handleHeartbeat.bind(this),
            'system': this.handleSystem.bind(this),
            'error': this.handleErrorMessage.bind(this),
            'log': this.handleLog.bind(this),
            'trade': this.handleTrade.bind(this),
            'order': this.handleOrder.bind(this),
            'position': this.handlePosition.bind(this),
            'portfolio': this.handlePortfolio.bind(this),
            'risk': this.handleRisk.bind(this),
            'backtest': this.handleBacktest.bind(this),
            'signal': this.handleSignal.bind(this),
            'strategy': this.handleStrategy.bind(this),
            'broker': this.handleBroker.bind(this),
            'exchange': this.handleExchange.bind(this),
            'market': this.handleMarket.bind(this),
            'price': this.handlePrice.bind(this),
            'candle': this.handleCandle.bind(this),
            'ticker': this.handleTicker.bind(this),
            'orderbook': this.handleOrderBook.bind(this),
        };

        if (routes[type]) {
            try {
                routes[type](payload);
            } catch (error) {
                console.error(`Route error for ${type}:`, error);
            }
        }
    }

    registerHandler(type, handler) {
        if (!this.messageHandlers.has(type)) {
            this.messageHandlers.set(type, []);
        }
        this.messageHandlers.get(type).push(handler);
        return () => this.unregisterHandler(type, handler);
    }

    unregisterHandler(type, handler) {
        if (this.messageHandlers.has(type)) {
            const handlers = this.messageHandlers.get(type);
            const index = handlers.indexOf(handler);
            if (index !== -1) {
                handlers.splice(index, 1);
            }
            if (handlers.length === 0) {
                this.messageHandlers.delete(type);
            }
        }
    }

    // ============================================================
    // EVENT SYSTEM
    // ============================================================

    on(event, callback) {
        if (!this.eventListeners.has(event)) {
            this.eventListeners.set(event, []);
        }
        this.eventListeners.get(event).push(callback);
        return () => this.off(event, callback);
    }

    once(event, callback) {
        const wrapper = (data) => {
            this.off(event, wrapper);
            callback(data);
        };
        return this.on(event, wrapper);
    }

    off(event, callback) {
        if (this.eventListeners.has(event)) {
            const callbacks = this.eventListeners.get(event);
            if (callback) {
                const index = callbacks.indexOf(callback);
                if (index !== -1) {
                    callbacks.splice(index, 1);
                }
            } else {
                callbacks.clear();
            }
            if (callbacks.size === 0) {
                this.eventListeners.delete(event);
            }
        }
    }

    emit(event, data) {
        if (this.eventListeners.has(event)) {
            const callbacks = this.eventListeners.get(event);
            callbacks.forEach(callback => {
                try {
                    callback(data, this);
                } catch (error) {
                    console.error(`Event handler error for ${event}:`, error);
                }
            });
        }
    }

    // ============================================================
    // ROUTE HANDLERS
    // ============================================================

    handleOpportunity(payload) {
        this.emit('opportunity', payload);
    }

    handleExecution(payload) {
        this.emit('execution', payload);
    }

    handlePnL(payload) {
        this.emit('pnl', payload);
    }

    handleSpread(payload) {
        this.emit('spread', payload);
    }

    handleVolume(payload) {
        this.emit('volume', payload);
    }

    handleMatrix(payload) {
        this.emit('matrix', payload);
    }

    handleMetrics(payload) {
        this.emit('metrics', payload);
    }

    handleAlert(payload) {
        this.emit('alert', payload);
    }

    handleConfig(payload) {
        this.emit('config', payload);
    }

    handleState(payload) {
        this.emit('state', payload);
    }

    handlePerformance(payload) {
        this.emit('performance', payload);
    }

    handleSettings(payload) {
        this.emit('settings', payload);
    }

    handleNotification(payload) {
        this.emit('notification', payload);
    }

    handleHeartbeat(payload) {
        this.emit('heartbeat_data', payload);
    }

    handleSystem(payload) {
        this.emit('system', payload);
    }

    handleLog(payload) {
        this.emit('log', payload);
    }

    handleTrade(payload) {
        this.emit('trade', payload);
    }

    handleOrder(payload) {
        this.emit('order', payload);
    }

    handlePosition(payload) {
        this.emit('position', payload);
    }

    handlePortfolio(payload) {
        this.emit('portfolio', payload);
    }

    handleRisk(payload) {
        this.emit('risk', payload);
    }

    handleBacktest(payload) {
        this.emit('backtest', payload);
    }

    handleSignal(payload) {
        this.emit('signal', payload);
    }

    handleStrategy(payload) {
        this.emit('strategy', payload);
    }

    handleBroker(payload) {
        this.emit('broker', payload);
    }

    handleExchange(payload) {
        this.emit('exchange', payload);
    }

    handleMarket(payload) {
        this.emit('market', payload);
    }

    handlePrice(payload) {
        this.emit('price', payload);
    }

    handleCandle(payload) {
        this.emit('candle', payload);
    }

    handleTicker(payload) {
        this.emit('ticker', payload);
    }

    handleOrderBook(payload) {
        this.emit('orderbook', payload);
    }

    // ============================================================
    // UTILITY METHODS
    // ============================================================

    isReady() {
        return this.isConnected && this.ws && this.ws.readyState === WebSocket.OPEN;
    }

    getState() {
        return {
            isConnected: this.isConnected,
            isConnecting: this.isConnecting,
            reconnectAttempts: this.reconnectAttempts,
            totalReconnects: this.totalReconnects,
            lastHeartbeat: this.lastHeartbeat,
            connectionStartTime: this.connectionStartTime,
            subscriptions: Array.from(this.subscriptions.keys()),
            messageQueueSize: this.messageQueue.length,
            messagesReceived: this.messagesReceived,
            messagesSent: this.messagesSent,
            bytesReceived: this.bytesReceived,
            bytesSent: this.bytesSent,
            lastError: this.lastError,
            sessionId: this.config.sessionId,
        };
    }

    getStats() {
        const uptime = this.connectionStartTime ? Date.now() - this.connectionStartTime : 0;
        return {
            uptime: uptime,
            uptimeFormatted: this.formatUptime(uptime),
            messagesReceived: this.messagesReceived,
            messagesSent: this.messagesSent,
            bytesReceived: this.bytesReceived,
            bytesSent: this.bytesSent,
            reconnects: this.totalReconnects,
            subscriptions: this.subscriptions.size,
            queueSize: this.messageQueue.length,
        };
    }

    formatUptime(ms) {
        const seconds = Math.floor(ms / 1000);
        const minutes = Math.floor(seconds / 60);
        const hours = Math.floor(minutes / 60);
        const days = Math.floor(hours / 24);
        
        if (days > 0) return `${days}d ${hours % 24}h ${minutes % 60}m`;
        if (hours > 0) return `${hours}h ${minutes % 60}m`;
        if (minutes > 0) return `${minutes}m ${seconds % 60}s`;
        return `${seconds}s`;
    }

    setupVisibilityHandler() {
        document.addEventListener('visibilitychange', () => {
            if (!document.hidden && this.config.reconnect) {
                // Page became visible again - check connection
                if (!this.isConnected && !this.isConnecting) {
                    if (this.config.debug) {
                        console.log('👁️ Page visible, reconnecting...');
                    }
                    this.connect();
                }
                // If connected, send visibility event
                if (this.isConnected) {
                    this.sendJSON('visibility_change', {
                        visible: true,
                        timestamp: new Date().toISOString(),
                    });
                }
            } else if (document.hidden && this.isConnected) {
                // Page hidden - notify server
                this.sendJSON('visibility_change', {
                    visible: false,
                    timestamp: new Date().toISOString(),
                });
            }
        });
    }

    setupOnlineHandler() {
        window.addEventListener('online', () => {
            if (!this.isConnected && this.config.reconnect) {
                if (this.config.debug) {
                    console.log('🌐 Online, reconnecting...');
                }
                this.connect();
            }
        });

        window.addEventListener('offline', () => {
            if (this.config.debug) {
                console.log('🌐 Offline');
            }
            this.emit('offline', { timestamp: new Date().toISOString() });
        });
    }

    setupBeforeUnloadHandler() {
        window.addEventListener('beforeunload', () => {
            if (this.isConnected) {
                try {
                    this.sendJSON('session_end', {
                        sessionId: this.config.sessionId,
                        timestamp: new Date().toISOString(),
                    });
                } catch (e) {
                    // Ignore
                }
            }
        });
    }

    // ============================================================
    // CLOSE / DESTROY
    // ============================================================

    close(code = 1000, reason = 'Normal closure') {
        if (this.config.debug) {
            console.log(`🔌 Closing WebSocket: ${code} - ${reason}`);
        }

        this.stopHeartbeat();
        this.isConnected = false;
        this.isConnecting = false;

        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        if (this.ws) {
            try {
                this.ws.close(code, reason);
            } catch (error) {
                // Ignore
            }
            this.ws = null;
        }

        // Clear message queue
        this.messageQueue = [];

        // Clear request promises
        this.requestPromises.forEach(({ reject }) => {
            reject(new Error('Connection closed'));
        });
        this.requestPromises.clear();

        // Emit close event
        this.emit('close', { 
            code, 
            reason, 
            timestamp: new Date().toISOString(),
            manual: true,
        });
    }

    destroy() {
        this.close(1000, 'Manager destroyed');
        
        // Clear all subscriptions
        this.subscriptions.clear();
        this.eventListeners.clear();
        this.messageHandlers.clear();

        if (this.config.debug) {
            console.log('🧹 WebSocketManager destroyed');
            console.log(`📊 Final stats:`, this.getStats());
        }
    }

    // ============================================================
    // BATCH OPERATIONS
    // ============================================================

    sendBatch(messages) {
        if (!Array.isArray(messages)) {
            throw new Error('Messages must be an array');
        }

        if (messages.length === 0) return true;

        // If connected, send as batch
        if (this.isConnected) {
            const batch = {
                type: 'batch',
                payload: messages.map(msg => ({
                    ...msg,
                    id: msg.id || this.generateMessageId(),
                    timestamp: msg.timestamp || new Date().toISOString(),
                })),
                id: this.generateMessageId(),
                timestamp: new Date().toISOString(),
            };
            return this.send(batch);
        } else {
            // Queue each message individually
            messages.forEach(msg => this.queueMessage(msg));
            return false;
        }
    }

    // ============================================================
    // COMPRESSION
    // ============================================================

    compress(data) {
        if (!this.config.compression) return data;

        // Simple compression for JSON data
        if (typeof data === 'object') {
            return JSON.stringify(data);
        }
        return data;
    }

    decompress(data) {
        if (!this.config.compression) return data;

        // Decompression is handled automatically by JSON.parse
        return data;
    }

    // ============================================================
    // STATIC METHODS
    // ============================================================

    static getInstance(options = {}) {
        if (!WebSocketManager._instance) {
            WebSocketManager._instance = new WebSocketManager(options);
        }
        return WebSocketManager._instance;
    }

    static destroyInstance() {
        if (WebSocketManager._instance) {
            WebSocketManager._instance.destroy();
            WebSocketManager._instance = null;
        }
    }

    static create(url, options = {}) {
        return new WebSocketManager({ url, ...options });
    }
}

// ============================================================
// REACT HOOKS
// ============================================================

class WebSocketHook {
    constructor(options = {}) {
        this.manager = new WebSocketManager(options);
        this.listeners = [];
        this.state = {
            isConnected: false,
            isConnecting: false,
            lastMessage: null,
            lastError: null,
            stats: null,
        };

        // Bind manager events to state
        this.manager.on('connect', (data) => {
            this.state.isConnected = true;
            this.state.isConnecting = false;
            this.state.stats = this.manager.getStats();
            this.notify();
        });

        this.manager.on('close', (data) => {
            this.state.isConnected = false;
            this.state.stats = this.manager.getStats();
            this.notify();
        });

        this.manager.on('message', (data) => {
            this.state.lastMessage = data;
            this.notify();
        });

        this.manager.on('error', (error) => {
            this.state.lastError = error;
            this.notify();
        });

        this.manager.on('reconnecting', (data) => {
            this.state.isConnecting = true;
            this.notify();
        });

        this.manager.on('heartbeat', (data) => {
            this.notify();
        });
    }

    getState() {
        return {
            ...this.state,
            send: this.manager.send.bind(this.manager),
            sendJSON: this.manager.sendJSON.bind(this.manager),
            sendRequest: this.manager.sendRequest.bind(this.manager),
            subscribe: this.manager.subscribe.bind(this.manager),
            subscribeOnce: this.manager.subscribeOnce.bind(this.manager),
            on: this.manager.on.bind(this.manager),
            once: this.manager.once.bind(this.manager),
            off: this.manager.off.bind(this.manager),
            isReady: this.manager.isReady.bind(this.manager),
            connect: this.manager.connect.bind(this.manager),
            close: this.manager.close.bind(this.manager),
            getStats: this.manager.getStats.bind(this.manager),
            getState: this.manager.getState.bind(this.manager),
        };
    }

    notify() {
        const state = this.getState();
        this.listeners.forEach(listener => listener(state));
    }

    subscribe(callback) {
        this.listeners.push(callback);
        callback(this.getState());
        return () => {
            const index = this.listeners.indexOf(callback);
            if (index !== -1) {
                this.listeners.splice(index, 1);
            }
        };
    }

    destroy() {
        this.manager.destroy();
        this.listeners = [];
    }
}

// ============================================================
// VUE COMPOSABLE
// ============================================================

class WebSocketComposable {
    constructor(options = {}) {
        this.manager = new WebSocketManager(options);
        this.state = reactive({
            isConnected: false,
            isConnecting: false,
            lastMessage: null,
            lastError: null,
            stats: null,
        });

        // Bind manager events to state
        this.manager.on('connect', (data) => {
            this.state.isConnected = true;
            this.state.isConnecting = false;
            this.state.stats = this.manager.getStats();
        });

        this.manager.on('close', (data) => {
            this.state.isConnected = false;
            this.state.stats = this.manager.getStats();
        });

        this.manager.on('message', (data) => {
            this.state.lastMessage = data;
        });

        this.manager.on('error', (error) => {
            this.state.lastError = error;
        });

        this.manager.on('reconnecting', (data) => {
            this.state.isConnecting = true;
        });
    }

    getState() {
        return {
            ...this.state,
            send: this.manager.send.bind(this.manager),
            sendJSON: this.manager.sendJSON.bind(this.manager),
            sendRequest: this.manager.sendRequest.bind(this.manager),
            subscribe: this.manager.subscribe.bind(this.manager),
            subscribeOnce: this.manager.subscribeOnce.bind(this.manager),
            on: this.manager.on.bind(this.manager),
            once: this.manager.once.bind(this.manager),
            off: this.manager.off.bind(this.manager),
            isReady: this.manager.isReady.bind(this.manager),
            connect: this.manager.connect.bind(this.manager),
            close: this.manager.close.bind(this.manager),
            getStats: this.manager.getStats.bind(this.manager),
            getState: this.manager.getState.bind(this.manager),
        };
    }

    destroy() {
        this.manager.destroy();
    }
}

// ============================================================
// EXPORTS
// ============================================================

export {
    WebSocketManager,
    WebSocketHook,
    WebSocketComposable,
};

// ============================================================
// AUTO-INITIALIZATION
// ============================================================

// Create singleton instance
const defaultManager = WebSocketManager.getInstance();

// Expose globally for debugging
if (typeof window !== 'undefined') {
    window.NexusWebSocket = {
        manager: defaultManager,
        WebSocketManager: WebSocketManager,
        WebSocketHook: WebSocketHook,
        WebSocketComposable: WebSocketComposable,
        version: '2.1.0',
    };
}

console.log('🔌 WebSocket module v2.1.0 loaded successfully');
console.log(`📋 Default session: ${defaultManager.config.sessionId}`);

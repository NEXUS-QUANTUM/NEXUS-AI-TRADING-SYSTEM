// trading/bots/ai_bot/static/js/websocket.js
// NEXUS AI TRADING SYSTEM - WebSocket Manager
// Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved

/**
 * WebSocket Manager for NEXUS AI Trading Bot
 * Manages real-time WebSocket connections with:
 * - Automatic reconnection with exponential backoff
 * - Message queuing and delivery
 * - Channel subscription management
 * - Heartbeat/ping-pong
 * - Message batching
 * - Compression support
 * - Error handling
 * - Connection status monitoring
 */

class WebSocketManager {
    constructor(config = {}) {
        // Configuration
        this.config = {
            url: config.url || `${window.location.protocol === 'https:' ? 'wss:' : 'ws:'}//${window.location.host}/ws`,
            reconnectAttempts: config.reconnectAttempts || 10,
            reconnectDelay: config.reconnectDelay || 1000,
            maxReconnectDelay: config.maxReconnectDelay || 30000,
            heartbeatInterval: config.heartbeatInterval || 30000,
            heartbeatTimeout: config.heartbeatTimeout || 10000,
            messageQueueSize: config.messageQueueSize || 1000,
            batchSize: config.batchSize || 50,
            batchInterval: config.batchInterval || 100,
            compression: config.compression || false,
            debug: config.debug || false,
        };

        // State
        this.ws = null;
        this.isConnected = false;
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.reconnectTimer = null;
        this.heartbeatTimer = null;
        this.heartbeatTimeoutTimer = null;
        this.lastPingTime = null;
        this.lastPongTime = null;
        this.messageQueue = [];
        this.pendingMessages = new Map();
        this.subscriptions = new Map();
        this.handlers = new Map();
        this.channelHandlers = new Map();
        this.batchTimer = null;
        this.pendingBatch = [];
        this.messageIdCounter = 0;

        // Status
        this.status = 'disconnected';
        this.statusHistory = [];
        this.connectionStartTime = null;
        this.totalReconnects = 0;
        this.messagesSent = 0;
        this.messagesReceived = 0;
        this.messagesQueued = 0;

        // Event listeners
        this.eventListeners = new Map();

        // Authentication token
        this.token = localStorage.getItem('nexus_access_token') || null;

        // Initialize
        this.init();

        logger.info('WebSocketManager initialized', { url: this.config.url });
    }

    // ========================================================================
    // Initialization
    // ========================================================================

    /**
     * Initialize WebSocket manager
     */
    init() {
        // Connect if token exists
        if (this.token) {
            this.connect();
        }

        // Listen for auth events
        this.setupAuthListener();

        // Handle page visibility
        this.setupVisibilityListener();

        // Handle network changes
        this.setupNetworkListener();
    }

    /**
     * Setup auth listener
     */
    setupAuthListener() {
        // Listen for token changes
        window.addEventListener('storage', (e) => {
            if (e.key === 'nexus_access_token') {
                const newToken = e.newValue;
                if (newToken && newToken !== this.token) {
                    this.token = newToken;
                    this.reconnect();
                } else if (!newToken) {
                    this.token = null;
                    this.disconnect();
                }
            }
        });

        // Listen for auth events from API client
        if (window.NexusAPI) {
            window.NexusAPI.onAuthEvent((event) => {
                if (event.type === 'login' || event.type === 'tokens_set') {
                    this.token = localStorage.getItem('nexus_access_token');
                    this.reconnect();
                } else if (event.type === 'logout' || event.type === 'unauthorized') {
                    this.token = null;
                    this.disconnect();
                }
            });
        }
    }

    /**
     * Setup visibility listener
     */
    setupVisibilityListener() {
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                // Page hidden - reduce heartbeat frequency
                this.setHeartbeatInterval(60000);
            } else {
                // Page visible - restore heartbeat
                this.setHeartbeatInterval(this.config.heartbeatInterval);
                // Check connection
                if (!this.isConnected && !this.isConnecting) {
                    this.reconnect();
                }
            }
        });
    }

    /**
     * Setup network listener
     */
    setupNetworkListener() {
        window.addEventListener('online', () => {
            logger.info('Network online, reconnecting...');
            this.reconnect();
        });

        window.addEventListener('offline', () => {
            logger.info('Network offline');
            this.disconnect();
            this.updateStatus('offline');
        });
    }

    // ========================================================================
    // Connection Management
    // ========================================================================

    /**
     * Connect to WebSocket
     * @param {string} token - Authentication token (optional)
     * @returns {Promise<void>}
     */
    connect(token = null) {
        if (token) {
            this.token = token;
        }

        if (this.isConnected || this.isConnecting) {
            logger.debug('Already connected or connecting');
            return Promise.resolve();
        }

        if (!this.token) {
            logger.warn('No authentication token available');
            this.updateStatus('unauthenticated');
            return Promise.reject(new Error('No authentication token'));
        }

        this.isConnecting = true;
        this.updateStatus('connecting');

        return new Promise((resolve, reject) => {
            try {
                const wsUrl = `${this.config.url}?token=${this.token}`;
                this.ws = new WebSocket(wsUrl);

                // Set binary type
                if (this.config.compression) {
                    this.ws.binaryType = 'arraybuffer';
                }

                this.ws.onopen = (event) => {
                    this.handleOpen(event);
                    resolve();
                };

                this.ws.onmessage = (event) => {
                    this.handleMessage(event);
                };

                this.ws.onerror = (event) => {
                    this.handleError(event);
                    reject(event);
                };

                this.ws.onclose = (event) => {
                    this.handleClose(event);
                };

                // Connection timeout
                const timeout = setTimeout(() => {
                    if (this.isConnecting) {
                        this.ws.close();
                        reject(new Error('Connection timeout'));
                    }
                }, 10000);

                // Clear timeout on open
                const clearTimeoutOnOpen = () => {
                    clearTimeout(timeout);
                    this.ws.removeEventListener('open', clearTimeoutOnOpen);
                };
                this.ws.addEventListener('open', clearTimeoutOnOpen);

            } catch (error) {
                this.isConnecting = false;
                this.updateStatus('error');
                reject(error);
            }
        });
    }

    /**
     * Disconnect from WebSocket
     * @param {number} code - Close code
     * @param {string} reason - Close reason
     */
    disconnect(code = 1000, reason = 'User disconnected') {
        this.reconnectAttempts = this.config.reconnectAttempts; // Prevent reconnection
        this.stopHeartbeat();

        if (this.ws) {
            try {
                this.ws.close(code, reason);
            } catch (error) {
                logger.debug('WebSocket close error (ignored):', error);
            }
            this.ws = null;
        }

        this.isConnected = false;
        this.isConnecting = false;
        this.updateStatus('disconnected');

        logger.info('WebSocket disconnected', { code, reason });
    }

    /**
     * Reconnect to WebSocket
     */
    reconnect() {
        if (this.isConnected) {
            logger.debug('Already connected');
            return;
        }

        if (this.isConnecting) {
            logger.debug('Already connecting');
            return;
        }

        if (this.reconnectAttempts >= this.config.reconnectAttempts) {
            logger.warn('Max reconnect attempts reached');
            this.updateStatus('failed');
            return;
        }

        // Clear existing reconnect timer
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        // Calculate delay with exponential backoff
        const delay = Math.min(
            this.config.reconnectDelay * Math.pow(2, this.reconnectAttempts),
            this.config.maxReconnectDelay
        );

        this.reconnectAttempts++;
        this.totalReconnects++;

        logger.info(
            `Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.config.reconnectAttempts})`
        );

        this.updateStatus('reconnecting', {
            attempt: this.reconnectAttempts,
            maxAttempts: this.config.reconnectAttempts,
            delay: delay,
        });

        this.reconnectTimer = setTimeout(() => {
            this.reconnectTimer = null;
            this.connect().catch((error) => {
                logger.error('Reconnection failed:', error);
                this.reconnect(); // Retry
            });
        }, delay);
    }

    // ========================================================================
    // Connection Handlers
    // ========================================================================

    /**
     * Handle WebSocket open
     * @param {Event} event - Open event
     */
    handleOpen(event) {
        this.isConnected = true;
        this.isConnecting = false;
        this.reconnectAttempts = 0;
        this.connectionStartTime = Date.now();

        this.updateStatus('connected');

        logger.info('WebSocket connected');

        // Start heartbeat
        this.startHeartbeat();

        // Resubscribe to channels
        this.resubscribeAll();

        // Send queued messages
        this.flushQueue();

        // Emit event
        this.emitEvent('connected', event);
    }

    /**
     * Handle WebSocket message
     * @param {MessageEvent} event - Message event
     */
    handleMessage(event) {
        try {
            let data;

            // Handle binary data
            if (event.data instanceof ArrayBuffer) {
                const text = new TextDecoder().decode(event.data);
                data = JSON.parse(text);
            } else {
                data = JSON.parse(event.data);
            }

            this.messagesReceived++;

            // Debug logging
            if (this.config.debug) {
                logger.debug('WebSocket message received', data);
            }

            // Handle heartbeat
            if (data.type === 'pong') {
                this.handlePong(data);
                return;
            }

            if (data.type === 'ping') {
                this.sendPong();
                return;
            }

            // Handle acknowledgment
            if (data.type === 'ack') {
                this.handleAck(data);
                return;
            }

            // Handle error
            if (data.type === 'error') {
                this.handleErrorResponse(data);
                return;
            }

            // Handle channel message
            if (data.channel) {
                this.dispatchChannelMessage(data.channel, data.payload);
            }

            // Handle direct message
            if (data.type && this.handlers.has(data.type)) {
                const handlers = this.handlers.get(data.type);
                handlers.forEach(handler => {
                    try {
                        handler(data.payload, data);
                    } catch (error) {
                        logger.error('Handler error:', error);
                    }
                });
            }

            // Emit event
            this.emitEvent('message', data);

        } catch (error) {
            logger.error('Error processing WebSocket message:', error);
        }
    }

    /**
     * Handle WebSocket error
     * @param {Event} event - Error event
     */
    handleError(event) {
        logger.error('WebSocket error:', event);
        this.updateStatus('error');
        this.emitEvent('error', event);
    }

    /**
     * Handle WebSocket close
     * @param {CloseEvent} event - Close event
     */
    handleClose(event) {
        this.isConnected = false;
        this.isConnecting = false;
        this.stopHeartbeat();

        logger.info('WebSocket closed', {
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean,
        });

        this.updateStatus('disconnected', {
            code: event.code,
            reason: event.reason,
            wasClean: event.wasClean,
        });

        this.emitEvent('disconnected', event);

        // Attempt reconnect if not intentional
        if (event.code !== 1000) {
            this.reconnect();
        }
    }

    // ========================================================================
    // Message Sending
    // ========================================================================

    /**
     * Send message
     * @param {Object} message - Message to send
     * @param {boolean} queue - Queue if not connected
     * @returns {Promise<Object>} Response
     */
    send(message, queue = true) {
        return new Promise((resolve, reject) => {
            // Generate message ID
            const id = ++this.messageIdCounter;
            const msg = {
                ...message,
                id: id,
                timestamp: Date.now(),
            };

            // Store pending promise
            this.pendingMessages.set(id, { resolve, reject, timestamp: Date.now() });

            // Send or queue
            if (this.isConnected && this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.sendMessage(msg);
            } else if (queue) {
                this.queueMessage(msg);
            } else {
                this.pendingMessages.delete(id);
                reject(new Error('WebSocket not connected'));
            }
        });
    }

    /**
     * Send message immediately
     * @param {Object} message - Message to send
     */
    sendMessage(message) {
        try {
            const data = JSON.stringify(message);
            this.ws.send(data);
            this.messagesSent++;
            this.pendingMessages.set(message.id, {
                ...this.pendingMessages.get(message.id),
                sent: true,
                sentAt: Date.now(),
            });

            if (this.config.debug) {
                logger.debug('WebSocket message sent', message);
            }
        } catch (error) {
            logger.error('Error sending WebSocket message:', error);
            const pending = this.pendingMessages.get(message.id);
            if (pending) {
                pending.reject(error);
                this.pendingMessages.delete(message.id);
            }
            throw error;
        }
    }

    /**
     * Queue message
     * @param {Object} message - Message to queue
     */
    queueMessage(message) {
        if (this.messageQueue.length >= this.config.messageQueueSize) {
            this.messageQueue.shift();
            logger.warn('Message queue overflow, dropping oldest message');
        }

        this.messageQueue.push(message);
        this.messagesQueued++;

        if (this.config.debug) {
            logger.debug('Message queued', { id: message.id, queueSize: this.messageQueue.length });
        }

        // Try to flush queue
        this.scheduleFlush();
    }

    /**
     * Flush message queue
     */
    flushQueue() {
        if (!this.isConnected || this.messageQueue.length === 0) {
            return;
        }

        const batchSize = Math.min(this.config.batchSize, this.messageQueue.length);
        const batch = this.messageQueue.splice(0, batchSize);

        if (this.config.debug) {
            logger.debug('Flushing message queue', { batchSize: batch.length, remaining: this.messageQueue.length });
        }

        for (const message of batch) {
            try {
                this.sendMessage(message);
            } catch (error) {
                // Re-queue on error
                this.messageQueue.unshift(message);
                logger.error('Error sending queued message:', error);
                break;
            }
        }

        // If messages remain, schedule another flush
        if (this.messageQueue.length > 0) {
            this.scheduleFlush();
        }
    }

    /**
     * Schedule queue flush
     */
    scheduleFlush() {
        if (this.batchTimer) {
            return;
        }

        this.batchTimer = setTimeout(() => {
            this.batchTimer = null;
            this.flushQueue();
        }, this.config.batchInterval);
    }

    // ========================================================================
    // Subscription Management
    // ========================================================================

    /**
     * Subscribe to a channel
     * @param {string} channel - Channel name
     * @param {Function} handler - Message handler
     * @param {Object} options - Subscription options
     * @returns {Promise<void>}
     */
    subscribe(channel, handler, options = {}) {
        // Store handler
        if (!this.channelHandlers.has(channel)) {
            this.channelHandlers.set(channel, []);
        }
        this.channelHandlers.get(channel).push(handler);

        // Track subscription
        if (!this.subscriptions.has(channel)) {
            this.subscriptions.set(channel, { handlerCount: 1, options });
        } else {
            const sub = this.subscriptions.get(channel);
            sub.handlerCount++;
        }

        // Send subscription message
        return this.send({
            type: 'subscribe',
            channel: channel,
            options: options,
        });
    }

    /**
     * Unsubscribe from a channel
     * @param {string} channel - Channel name
     * @param {Function} handler - Handler to remove (optional)
     * @returns {Promise<void>}
     */
    unsubscribe(channel, handler = null) {
        // Remove handler
        if (this.channelHandlers.has(channel)) {
            if (handler) {
                const handlers = this.channelHandlers.get(channel);
                const index = handlers.indexOf(handler);
                if (index !== -1) {
                    handlers.splice(index, 1);
                }
                if (handlers.length === 0) {
                    this.channelHandlers.delete(channel);
                }
            } else {
                this.channelHandlers.delete(channel);
            }
        }

        // Update subscription count
        if (this.subscriptions.has(channel)) {
            const sub = this.subscriptions.get(channel);
            sub.handlerCount--;
            if (sub.handlerCount <= 0 || handler === null) {
                this.subscriptions.delete(channel);

                // Send unsubscribe message
                return this.send({
                    type: 'unsubscribe',
                    channel: channel,
                });
            }
        }

        return Promise.resolve();
    }

    /**
     * Resubscribe to all channels
     */
    resubscribeAll() {
        for (const [channel, subscription] of this.subscriptions) {
            this.send({
                type: 'subscribe',
                channel: channel,
                options: subscription.options,
            }).catch((error) => {
                logger.error(`Error resubscribing to ${channel}:`, error);
            });
        }
    }

    // ========================================================================
    // Channel Dispatch
    // ========================================================================

    /**
     * Dispatch message to channel handlers
     * @param {string} channel - Channel name
     * @param {*} data - Message data
     */
    dispatchChannelMessage(channel, data) {
        if (this.channelHandlers.has(channel)) {
            const handlers = this.channelHandlers.get(channel);
            handlers.forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    logger.error(`Error in channel handler for ${channel}:`, error);
                }
            });
        }

        // Dispatch to wildcard handlers
        if (this.channelHandlers.has('*')) {
            const handlers = this.channelHandlers.get('*');
            handlers.forEach(handler => {
                try {
                    handler(channel, data);
                } catch (error) {
                    logger.error('Error in wildcard handler:', error);
                }
            });
        }

        // Emit event
        this.emitEvent(`channel:${channel}`, data);
    }

    // ========================================================================
    // Heartbeat
    // ========================================================================

    /**
     * Start heartbeat
     */
    startHeartbeat() {
        this.stopHeartbeat();

        this.heartbeatTimer = setInterval(() => {
            this.sendPing();
        }, this.config.heartbeatInterval);

        // Also set heartbeat timeout
        this.heartbeatTimeoutTimer = setTimeout(() => {
            this.handleHeartbeatTimeout();
        }, this.config.heartbeatTimeout);

        this.lastPingTime = Date.now();
    }

    /**
     * Stop heartbeat
     */
    stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }

        if (this.heartbeatTimeoutTimer) {
            clearTimeout(this.heartbeatTimeoutTimer);
            this.heartbeatTimeoutTimer = null;
        }
    }

    /**
     * Set heartbeat interval
     * @param {number} interval - Interval in ms
     */
    setHeartbeatInterval(interval) {
        this.config.heartbeatInterval = interval;
        if (this.isConnected) {
            this.startHeartbeat();
        }
    }

    /**
     * Send ping
     */
    sendPing() {
        if (!this.isConnected || !this.ws) {
            return;
        }

        try {
            this.ws.send(JSON.stringify({
                type: 'ping',
                timestamp: Date.now(),
            }));

            this.lastPingTime = Date.now();

            // Reset heartbeat timeout
            if (this.heartbeatTimeoutTimer) {
                clearTimeout(this.heartbeatTimeoutTimer);
            }
            this.heartbeatTimeoutTimer = setTimeout(() => {
                this.handleHeartbeatTimeout();
            }, this.config.heartbeatTimeout);

        } catch (error) {
            logger.error('Error sending ping:', error);
        }
    }

    /**
     * Send pong
     */
    sendPong() {
        if (!this.isConnected || !this.ws) {
            return;
        }

        try {
            this.ws.send(JSON.stringify({
                type: 'pong',
                timestamp: Date.now(),
            }));

            this.lastPongTime = Date.now();

        } catch (error) {
            logger.error('Error sending pong:', error);
        }
    }

    /**
     * Handle pong response
     * @param {Object} data - Pong data
     */
    handlePong(data) {
        this.lastPongTime = Date.now();

        // Reset heartbeat timeout
        if (this.heartbeatTimeoutTimer) {
            clearTimeout(this.heartbeatTimeoutTimer);
        }
        this.heartbeatTimeoutTimer = setTimeout(() => {
            this.handleHeartbeatTimeout();
        }, this.config.heartbeatTimeout);

        // Update status
        this.updateStatus('connected', {
            ping: Date.now() - (data.timestamp || this.lastPingTime),
        });

        if (this.config.debug) {
            logger.debug('Pong received', { latency: Date.now() - data.timestamp });
        }
    }

    /**
     * Handle heartbeat timeout
     */
    handleHeartbeatTimeout() {
        logger.warn('Heartbeat timeout');
        this.emitEvent('heartbeat_timeout');

        // Attempt reconnect
        this.disconnect(1006, 'Heartbeat timeout');
        this.reconnect();
    }

    // ========================================================================
    // Message Acknowledgment
    // ========================================================================

    /**
     * Handle acknowledgment
     * @param {Object} data - Acknowledgment data
     */
    handleAck(data) {
        const id = data.id;
        if (this.pendingMessages.has(id)) {
            const pending = this.pendingMessages.get(id);
            if (data.success) {
                pending.resolve(data.result);
            } else {
                pending.reject(new Error(data.error || 'Message failed'));
            }
            this.pendingMessages.delete(id);
        }
    }

    /**
     * Handle error response
     * @param {Object} data - Error data
     */
    handleErrorResponse(data) {
        const id = data.id;
        if (id && this.pendingMessages.has(id)) {
            const pending = this.pendingMessages.get(id);
            pending.reject(new Error(data.message || 'WebSocket error'));
            this.pendingMessages.delete(id);
        }

        this.emitEvent('error_response', data);
    }

    // ========================================================================
    // Event System
    // ========================================================================

    /**
     * Register event listener
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
                    logger.error(`Error in event listener for ${event}:`, error);
                }
            });
        }
    }

    // ========================================================================
    // Status Management
    // ========================================================================

    /**
     * Update connection status
     * @param {string} status - Status value
     * @param {Object} metadata - Additional metadata
     */
    updateStatus(status, metadata = {}) {
        this.status = status;
        this.statusHistory.push({
            status,
            timestamp: Date.now(),
            metadata,
        });

        // Keep history limited
        if (this.statusHistory.length > 100) {
            this.statusHistory.shift();
        }

        // Emit event
        this.emitEvent('status', { status, metadata });
    }

    /**
     * Get connection status
     * @returns {Object} Status information
     */
    getStatus() {
        return {
            status: this.status,
            isConnected: this.isConnected,
            isConnecting: this.isConnecting,
            reconnectAttempts: this.reconnectAttempts,
            totalReconnects: this.totalReconnects,
            connectionStartTime: this.connectionStartTime,
            uptime: this.connectionStartTime ? Date.now() - this.connectionStartTime : 0,
            messagesSent: this.messagesSent,
            messagesReceived: this.messagesReceived,
            messagesQueued: this.messagesQueued,
            queueSize: this.messageQueue.length,
            pendingMessages: this.pendingMessages.size,
            subscriptions: this.subscriptions.size,
            channelHandlers: this.channelHandlers.size,
            handlers: this.handlers.size,
            lastPing: this.lastPingTime,
            lastPong: this.lastPongTime,
        };
    }

    // ========================================================================
    // Utility Methods
    // ========================================================================

    /**
     * Register message handler
     * @param {string} type - Message type
     * @param {Function} handler - Message handler
     */
    onMessage(type, handler) {
        if (!this.handlers.has(type)) {
            this.handlers.set(type, []);
        }
        this.handlers.get(type).push(handler);
    }

    /**
     * Remove message handler
     * @param {string} type - Message type
     * @param {Function} handler - Handler to remove (optional)
     */
    offMessage(type, handler = null) {
        if (this.handlers.has(type)) {
            if (handler) {
                const handlers = this.handlers.get(type);
                const index = handlers.indexOf(handler);
                if (index !== -1) {
                    handlers.splice(index, 1);
                }
                if (handlers.length === 0) {
                    this.handlers.delete(type);
                }
            } else {
                this.handlers.delete(type);
            }
        }
    }

    /**
     * Get connection statistics
     * @returns {Object} Statistics
     */
    getStats() {
        return {
            messagesSent: this.messagesSent,
            messagesReceived: this.messagesReceived,
            messagesQueued: this.messagesQueued,
            pendingMessages: this.pendingMessages.size,
            queueSize: this.messageQueue.length,
            subscriptions: this.subscriptions.size,
            totalReconnects: this.totalReconnects,
            uptime: this.connectionStartTime ? Date.now() - this.connectionStartTime : 0,
        };
    }

    /**
     * Reset statistics
     */
    resetStats() {
        this.messagesSent = 0;
        this.messagesReceived = 0;
        this.messagesQueued = 0;
        this.pendingMessages.clear();
        this.messageQueue = [];
        this.totalReconnects = 0;
    }

    /**
     * Clear all subscriptions
     */
    clearSubscriptions() {
        this.subscriptions.clear();
        this.channelHandlers.clear();
    }

    /**
     * Check if connected
     * @returns {boolean} Connected status
     */
    isConnected() {
        return this.isConnected && this.ws && this.ws.readyState === WebSocket.OPEN;
    }

    /**
     * Get WebSocket ready state
     * @returns {number} Ready state
     */
    getReadyState() {
        return this.ws ? this.ws.readyState : WebSocket.CLOSED;
    }

    /**
     * Get WebSocket URL
     * @returns {string} WebSocket URL
     */
    getUrl() {
        return this.config.url;
    }

    /**
     * Set WebSocket URL
     * @param {string} url - New URL
     */
    setUrl(url) {
        this.config.url = url;
        if (this.isConnected) {
            this.reconnect();
        }
    }

    /**
     * Set authentication token
     * @param {string} token - New token
     */
    setToken(token) {
        this.token = token;
        if (this.isConnected) {
            this.reconnect();
        } else {
            this.connect();
        }
    }

    /**
     * Clear authentication token
     */
    clearToken() {
        this.token = null;
        this.disconnect();
    }
}

// Create global instance
window.WebSocketManager = new WebSocketManager();

// Simple logger
const logger = {
    debug: (...args) => console.debug('[DEBUG]', ...args),
    info: (...args) => console.info('[INFO]', ...args),
    warn: (...args) => console.warn('[WARN]', ...args),
    error: (...args) => console.error('[ERROR]', ...args),
};

export default WebSocketManager;

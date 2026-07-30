/**
 * trading/bots/hedge_bot/static/js/websocket.js
 * NEXUS AI TRADING SYSTEM - Hedge Bot WebSocket Client
 * Version: 2.0.0
 * Copyright © 2026 NEXUS QUANTUM LTD - All Rights Reserved
 */

/**
 * NEXUS WebSocket Client
 * 
 * A comprehensive WebSocket client for the NEXUS Hedge Bot.
 * Features include:
 * - Automatic reconnection
 * - Message queuing
 * - Channel subscription management
 * - Heartbeat monitoring
 * - Message batching
 * - Compression support
 * - Authentication
 * - Event handling
 * - Performance optimization
 * - Error recovery
 */

class NexusWebSocket {
    /**
     * Create a new WebSocket client instance
     * 
     * @param {Object} config - WebSocket configuration
     * @param {string} config.url - WebSocket URL
     * @param {Object} config.options - Connection options
     * @param {number} config.reconnectAttempts - Max reconnect attempts
     * @param {number} config.reconnectDelay - Reconnect delay in milliseconds
     * @param {number} config.heartbeatInterval - Heartbeat interval in milliseconds
     * @param {number} config.timeout - Connection timeout in milliseconds
     * @param {boolean} config.debug - Enable debug logging
     * @param {Function} config.onMessage - Message handler
     * @param {Function} config.onConnect - Connection handler
     * @param {Function} config.onDisconnect - Disconnection handler
     * @param {Function} config.onError - Error handler
     */
    constructor(config = {}) {
        // Configuration
        this.config = {
            url: config.url || 'ws://localhost:8080/ws',
            reconnectAttempts: config.reconnectAttempts || 10,
            reconnectDelay: config.reconnectDelay || 1000,
            maxReconnectDelay: config.maxReconnectDelay || 30000,
            heartbeatInterval: config.heartbeatInterval || 30000,
            timeout: config.timeout || 30000,
            debug: config.debug || false,
            autoReconnect: config.autoReconnect !== undefined ? config.autoReconnect : true,
            messageQueueSize: config.messageQueueSize || 1000,
            batchSize: config.batchSize || 50,
            batchInterval: config.batchInterval || 100,
            compression: config.compression || false,
            authToken: config.authToken || null,
        };

        // State
        this.ws = null;
        this.isConnected = false;
        this.isConnecting = false;
        this.reconnectCount = 0;
        this.heartbeatTimer = null;
        this.reconnectTimer = null;
        this.messageQueue = [];
        this.batchTimer = null;
        this.subscriptions = new Map();
        this.messageHandlers = new Map();
        this.pendingMessages = new Map();
        this.messageId = 0;
        this.lastPing = null;
        this.lastPong = null;
        this.latency = 0;
        this.connectionStart = null;

        // Event listeners
        this.listeners = {
            connect: [],
            disconnect: [],
            message: [],
            error: [],
            reconnect: [],
            reconnect_failed: [],
            heartbeat: [],
            subscribe: [],
            unsubscribe: [],
        };

        // Initialize
        this.log('WebSocket client initialized');

        // Start connection
        if (config.autoConnect !== false) {
            this.connect();
        }
    }

    // ============================================================
    // CONNECTION MANAGEMENT
    // ============================================================

    /**
     * Connect to WebSocket server
     * 
     * @returns {Promise<void>}
     */
    connect() {
        if (this.isConnected || this.isConnecting) {
            this.log('Already connected or connecting');
            return Promise.resolve();
        }

        this.log('Connecting to WebSocket:', this.config.url);
        this.isConnecting = true;
        this.connectionStart = Date.now();

        return new Promise((resolve, reject) => {
            try {
                // Build URL with authentication
                let url = this.config.url;
                if (this.config.authToken) {
                    const separator = url.includes('?') ? '&' : '?';
                    url += `${separator}token=${encodeURIComponent(this.config.authToken)}`;
                }

                this.ws = new WebSocket(url);

                // Set timeout
                const timeoutId = setTimeout(() => {
                    if (this.ws && this.ws.readyState === WebSocket.CONNECTING) {
                        this.ws.close();
                        reject(new Error('WebSocket connection timeout'));
                    }
                }, this.config.timeout);

                // Setup event handlers
                this.ws.onopen = (event) => {
                    clearTimeout(timeoutId);
                    this._handleOpen(event);
                    resolve();
                };

                this.ws.onclose = (event) => {
                    clearTimeout(timeoutId);
                    this._handleClose(event);
                };

                this.ws.onerror = (event) => {
                    clearTimeout(timeoutId);
                    this._handleError(event);
                    reject(new Error('WebSocket connection error'));
                };

                this.ws.onmessage = (event) => {
                    this._handleMessage(event);
                };

            } catch (error) {
                this.isConnecting = false;
                this._emit('error', error);
                reject(error);
            }
        });
    }

    /**
     * Disconnect from WebSocket server
     * 
     * @param {number} code - Close code
     * @param {string} reason - Close reason
     */
    disconnect(code = 1000, reason = 'Normal closure') {
        this.log('Disconnecting WebSocket:', code, reason);

        // Clear reconnect timer
        if (this.reconnectTimer) {
            clearTimeout(this.reconnectTimer);
            this.reconnectTimer = null;
        }

        // Stop heartbeat
        this._stopHeartbeat();

        // Close WebSocket
        if (this.ws) {
            this.ws.close(code, reason);
            this.ws = null;
        }

        this.isConnected = false;
        this.isConnecting = false;
        this._emit('disconnect', { code, reason });
    }

    /**
     * Reconnect WebSocket
     */
    _reconnect() {
        if (!this.config.autoReconnect) {
            this.log('Auto-reconnect disabled');
            this._emit('reconnect_failed', { attempts: this.reconnectCount });
            return;
        }

        if (this.reconnectCount >= this.config.reconnectAttempts) {
            this.log('Max reconnect attempts reached');
            this._emit('reconnect_failed', { attempts: this.reconnectCount });
            return;
        }

        this.reconnectCount++;

        // Calculate delay with exponential backoff
        const delay = Math.min(
            this.config.reconnectDelay * Math.pow(1.5, this.reconnectCount - 1),
            this.config.maxReconnectDelay
        );

        this.log(`Reconnecting in ${delay}ms (attempt ${this.reconnectCount})`);

        this.reconnectTimer = setTimeout(() => {
            this._emit('reconnect', { attempt: this.reconnectCount, delay });
            this.connect().catch(() => {});
        }, delay);
    }

    // ============================================================
    // MESSAGE HANDLING
    // ============================================================

    /**
     * Send a message
     * 
     * @param {Object} data - Message data
     * @param {boolean} queue - Queue message if not connected
     * @returns {Promise<any>} Response promise
     */
    send(data, queue = true) {
        return new Promise((resolve, reject) => {
            const message = {
                id: ++this.messageId,
                data: data,
                timestamp: Date.now(),
                resolve: resolve,
                reject: reject,
            };

            if (this.isConnected && this.ws && this.ws.readyState === WebSocket.OPEN) {
                this._sendMessage(message);
            } else if (queue) {
                this.log('Not connected, queuing message:', data);
                if (this.messageQueue.length < this.config.messageQueueSize) {
                    this.messageQueue.push(message);
                } else {
                    reject(new Error('Message queue full'));
                }
            } else {
                reject(new Error('WebSocket not connected'));
            }
        });
    }

    /**
     * Send a message directly
     * 
     * @param {Object} message - Message object
     */
    _sendMessage(message) {
        try {
            const data = message.data;
            const serialized = typeof data === 'string' ? data : JSON.stringify(data);
            this.ws.send(serialized);

            // Store pending message for response tracking
            if (message.id) {
                this.pendingMessages.set(message.id, message);
                setTimeout(() => {
                    if (this.pendingMessages.has(message.id)) {
                        this.pendingMessages.delete(message.id);
                        message.reject(new Error('Message timeout'));
                    }
                }, 30000);
            }

            this.log('Message sent:', data);

        } catch (error) {
            this.log('Failed to send message:', error);
            message.reject(error);
        }
    }

    /**
     * Send a batch of messages
     */
    _sendBatch() {
        if (this.messageQueue.length === 0) return;

        const batch = this.messageQueue.splice(0, this.config.batchSize);
        this.log(`Sending batch of ${batch.length} messages`);

        batch.forEach(message => {
            this._sendMessage(message);
        });
    }

    /**
     * Queue a message for sending
     */
    _queueMessage(message) {
        if (this.messageQueue.length < this.config.messageQueueSize) {
            this.messageQueue.push(message);

            // Start batch timer if not already started
            if (!this.batchTimer) {
                this.batchTimer = setTimeout(() => {
                    this._sendBatch();
                    this.batchTimer = null;
                }, this.config.batchInterval);
            }
        } else {
            this.log('Message queue full, dropping message');
        }
    }

    /**
     * Handle incoming message
     */
    _handleMessage(event) {
        try {
            let data;
            if (event.data instanceof ArrayBuffer) {
                // Binary message (compressed)
                if (this.config.compression) {
                    const decompressed = this._decompressData(event.data);
                    data = JSON.parse(decompressed);
                } else {
                    data = new Uint8Array(event.data);
                }
            } else {
                data = JSON.parse(event.data);
            }

            // Handle heartbeat
            if (data.type === 'pong') {
                this._handlePong(data);
                return;
            }

            if (data.type === 'ping') {
                this._handlePing(data);
                return;
            }

            // Handle response to pending message
            if (data.id && this.pendingMessages.has(data.id)) {
                const message = this.pendingMessages.get(data.id);
                this.pendingMessages.delete(data.id);
                message.resolve(data);
                return;
            }

            // Route to message handlers
            this._routeMessage(data);

            // Emit message event
            this._emit('message', data);

            this.log('Message received:', data);

        } catch (error) {
            this.log('Failed to parse message:', error);
            this._emit('error', error);
        }
    }

    /**
     * Route message to appropriate handlers
     */
    _routeMessage(data) {
        // Check for channel subscription
        if (data.channel && this.subscriptions.has(data.channel)) {
            const handlers = this.subscriptions.get(data.channel);
            handlers.forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    this.log('Error in message handler:', error);
                }
            });
        }

        // Check for message type handlers
        if (data.type && this.messageHandlers.has(data.type)) {
            const handlers = this.messageHandlers.get(data.type);
            handlers.forEach(handler => {
                try {
                    handler(data);
                } catch (error) {
                    this.log('Error in type handler:', error);
                }
            });
        }
    }

    // ============================================================
    // SUBSCRIPTION MANAGEMENT
    // ============================================================

    /**
     * Subscribe to a channel
     * 
     * @param {string} channel - Channel name
     * @param {Function} handler - Message handler
     * @param {Object} options - Subscription options
     */
    subscribe(channel, handler, options = {}) {
        if (!this.subscriptions.has(channel)) {
            this.subscriptions.set(channel, []);
        }

        this.subscriptions.get(channel).push(handler);

        // Send subscription message
        this.send({
            type: 'subscribe',
            channel: channel,
            ...options,
        }).then(() => {
            this._emit('subscribe', { channel, options });
            this.log('Subscribed to channel:', channel);
        }).catch((error) => {
            this.log('Failed to subscribe to channel:', error);
        });
    }

    /**
     * Unsubscribe from a channel
     * 
     * @param {string} channel - Channel name
     * @param {Function} handler - Specific handler to remove
     */
    unsubscribe(channel, handler = null) {
        if (!this.subscriptions.has(channel)) return;

        if (handler) {
            const handlers = this.subscriptions.get(channel);
            const index = handlers.indexOf(handler);
            if (index !== -1) {
                handlers.splice(index, 1);
            }
            if (handlers.length === 0) {
                this.subscriptions.delete(channel);
            }
        } else {
            this.subscriptions.delete(channel);
        }

        // Send unsubscribe message
        this.send({
            type: 'unsubscribe',
            channel: channel,
        }).then(() => {
            this._emit('unsubscribe', { channel });
            this.log('Unsubscribed from channel:', channel);
        }).catch((error) => {
            this.log('Failed to unsubscribe from channel:', error);
        });
    }

    /**
     * Register a message type handler
     * 
     * @param {string} type - Message type
     * @param {Function} handler - Message handler
     */
    onMessageType(type, handler) {
        if (!this.messageHandlers.has(type)) {
            this.messageHandlers.set(type, []);
        }
        this.messageHandlers.get(type).push(handler);
    }

    /**
     * Remove a message type handler
     * 
     * @param {string} type - Message type
     * @param {Function} handler - Handler to remove
     */
    offMessageType(type, handler) {
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
    // HEARTBEAT MANAGEMENT
    // ============================================================

    /**
     * Start heartbeat
     */
    _startHeartbeat() {
        this._stopHeartbeat();

        this.heartbeatTimer = setInterval(() => {
            this._sendPing();
        }, this.config.heartbeatInterval);

        this.log('Heartbeat started');
    }

    /**
     * Stop heartbeat
     */
    _stopHeartbeat() {
        if (this.heartbeatTimer) {
            clearInterval(this.heartbeatTimer);
            this.heartbeatTimer = null;
        }
    }

    /**
     * Send ping
     */
    _sendPing() {
        if (!this.isConnected || !this.ws) return;

        this.lastPing = Date.now();

        this.send({
            type: 'ping',
            timestamp: this.lastPing,
        }).catch(() => {});
    }

    /**
     * Handle ping
     */
    _handlePing(data) {
        this.send({
            type: 'pong',
            timestamp: data.timestamp,
            echo: data,
        }).catch(() => {});
    }

    /**
     * Handle pong
     */
    _handlePong(data) {
        this.lastPong = Date.now();
        if (data.timestamp) {
            this.latency = this.lastPong - data.timestamp;
        }

        this._emit('heartbeat', { latency: this.latency, data });
    }

    // ============================================================
    // COMPRESSION
    // ============================================================

    /**
     * Compress data
     * 
     * @param {string} data - Data to compress
     * @returns {Uint8Array} Compressed data
     */
    _compressData(data) {
        // Implementation would use compression libraries
        // For now, return as-is
        return new TextEncoder().encode(data);
    }

    /**
     * Decompress data
     * 
     * @param {ArrayBuffer} data - Data to decompress
     * @returns {string} Decompressed data
     */
    _decompressData(data) {
        // Implementation would use decompression libraries
        // For now, return as-is
        return new TextDecoder().decode(data);
    }

    // ============================================================
    // EVENT HANDLING
    // ============================================================

    /**
     * Handle open event
     */
    _handleOpen(event) {
        this.isConnected = true;
        this.isConnecting = false;
        this.reconnectCount = 0;

        // Send queued messages
        this._sendBatch();

        // Start heartbeat
        this._startHeartbeat();

        this._emit('connect', event);
        this.log('WebSocket connected');
    }

    /**
     * Handle close event
     */
    _handleClose(event) {
        this.isConnected = false;
        this.isConnecting = false;

        // Stop heartbeat
        this._stopHeartbeat();

        // Clear pending messages
        this.pendingMessages.forEach((message) => {
            message.reject(new Error('WebSocket closed'));
        });
        this.pendingMessages.clear();

        this._emit('close', event);

        // Attempt reconnect
        if (event.code !== 1000 && this.config.autoReconnect) {
            this._reconnect();
        }

        this.log('WebSocket closed:', event.code, event.reason);
    }

    /**
     * Handle error event
     */
    _handleError(event) {
        this._emit('error', event);
        this.log('WebSocket error:', event);
    }

    // ============================================================
    // EVENT SYSTEM
    // ============================================================

    /**
     * Add event listener
     */
    on(event, listener) {
        if (this.listeners[event]) {
            this.listeners[event].push(listener);
        }
    }

    /**
     * Remove event listener
     */
    off(event, listener) {
        if (this.listeners[event]) {
            const index = this.listeners[event].indexOf(listener);
            if (index !== -1) {
                this.listeners[event].splice(index, 1);
            }
        }
    }

    /**
     * Emit event
     */
    _emit(event, data) {
        if (this.listeners[event]) {
            this.listeners[event].forEach(listener => {
                try {
                    listener(data);
                } catch (error) {
                    this.log('Error in event listener:', error);
                }
            });
        }
    }

    // ============================================================
    // STATUS INFORMATION
    // ============================================================

    /**
     * Get connection status
     * 
     * @returns {Object} Status information
     */
    getStatus() {
        return {
            isConnected: this.isConnected,
            isConnecting: this.isConnecting,
            reconnectCount: this.reconnectCount,
            messageQueueSize: this.messageQueue.length,
            pendingMessages: this.pendingMessages.size,
            latency: this.latency,
            connectionDuration: this.connectionStart ? Date.now() - this.connectionStart : 0,
            url: this.config.url,
            subscriptions: Array.from(this.subscriptions.keys()),
        };
    }

    /**
     * Check if connected
     * 
     * @returns {boolean} Connected status
     */
    isActive() {
        return this.isConnected && this.ws && this.ws.readyState === WebSocket.OPEN;
    }

    // ============================================================
    // UTILITY METHODS
    // ============================================================

    /**
     * Log message
     */
    log(...args) {
        if (this.config.debug) {
            console.log('[NexusWS]', ...args);
        }
    }

    /**
     * Reset connection
     */
    reset() {
        this.disconnect(1000, 'Reset');
        this.reconnectCount = 0;
        this.messageQueue = [];
        this.pendingMessages.clear();
        this.subscriptions.clear();
        this.messageHandlers.clear();
        this.connect();
    }

    // ============================================================
    // CLEANUP
    // ============================================================

    /**
     * Cleanup resources
     */
    destroy() {
        this.disconnect(1000, 'Destroy');
        this.listeners = {};
        this.subscriptions.clear();
        this.messageHandlers.clear();
        this.pendingMessages.clear();
        this.messageQueue = [];
        this.log('WebSocket client destroyed');
    }
}

// ============================================================
// EXPORTS
// ============================================================

// Export for Node.js
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NexusWebSocket;
}

// Export for browser
if (typeof window !== 'undefined') {
    window.NexusWebSocket = NexusWebSocket;
}

export default NexusWebSocket;

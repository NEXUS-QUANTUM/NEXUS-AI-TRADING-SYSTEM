/**
 * NEXUS AI TRADING SYSTEM - WebSocket Route
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This route handles WebSocket connections including:
 * - Real-time bi-directional communication
 * - Authentication and authorization
 * - Channel subscription management
 * - Message broadcasting
 * - Connection lifecycle management
 * - Heartbeat and keep-alive
 * - Rate limiting per connection
 * - Message queuing and delivery guarantees
 * - Reconnection handling
 * - Presence management
 * - Event streaming
 * - Error handling and recovery
 * - Metrics and monitoring
 * - Logging and audit trails
 */

import { NextRequest } from 'next/server';
import { WebSocketServer, WebSocket } from 'ws';
import { headers } from 'next/headers';

// Types
import type {
  WebSocketMessage,
  WebSocketChannel,
  WebSocketSubscription,
  WebSocketEvent,
  WebSocketConnection,
  WebSocketPresence,
  WebSocketMetrics,
  WebSocketAuth,
  WebSocketMessageType,
  WebSocketChannelType,
  WebSocketEventType,
} from '@/types/websocket';

// Utils
import {
  authenticateWebSocket,
  validateWebSocketMessage,
  processWebSocketMessage,
  broadcastToChannel,
  sendToClient,
  handleWebSocketError,
  logWebSocketEvent,
  createAuditLog,
  generateConnectionId,
  validateChannelAccess,
  getChannelSubscribers,
  updatePresence,
} from '@/lib/websocket';

// Constants
import {
  WS_MESSAGE_TYPES,
  WS_CHANNELS,
  WS_EVENTS,
  WS_MESSAGE_SIZE_LIMIT,
  WS_CONNECTION_TIMEOUT,
  WS_HEARTBEAT_INTERVAL,
  WS_MAX_CONNECTIONS_PER_USER,
  WS_RATE_LIMIT,
  WS_RECONNECT_GRACE_PERIOD,
} from '@/constants/websocket';

// Database
import { prisma } from '@/lib/prisma';
import { redis } from '@/lib/redis';

// ============================================
// Configuration
// ============================================

const wss = new WebSocketServer({
  noServer: true,
  path: '/api/websocket',
  maxPayload: WS_MESSAGE_SIZE_LIMIT,
});

// Connection store
const connections = new Map<string, WebSocketConnection>();
const channelSubscribers = new Map<string, Set<string>>();
const userConnections = new Map<string, Set<string>>();

// Metrics
const metrics: WebSocketMetrics = {
  totalConnections: 0,
  activeConnections: 0,
  totalMessages: 0,
  messagesPerSecond: 0,
  errors: 0,
  bytesTransferred: 0,
};

let metricsInterval: NodeJS.Timeout | null = null;

// ============================================
// WebSocket Server Handler
// ============================================

export async function GET(req: NextRequest) {
  try {
    // Handle WebSocket upgrade
    const upgradeHeader = req.headers.get('upgrade');
    if (upgradeHeader !== 'websocket') {
      return new Response('WebSocket upgrade required', { status: 400 });
    }

    // Get authorization token
    const authHeader = req.headers.get('authorization');
    const token = authHeader?.replace('Bearer ', '');
    const userId = req.headers.get('x-user-id');

    if (!token || !userId) {
      return new Response('Authentication required', { status: 401 });
    }

    // Authenticate user
    const authResult = await authenticateWebSocket(token, userId);
    if (!authResult.success) {
      return new Response('Authentication failed', { status: 401 });
    }

    const user = authResult.user;

    // Rate limiting per user
    const userConnectionCount = userConnections.get(user.id)?.size || 0;
    if (userConnectionCount >= WS_MAX_CONNECTIONS_PER_USER) {
      return new Response('Too many connections', { status: 429 });
    }

    // Check if user has active subscription
    const hasActiveSubscription = await checkUserSubscription(user.id);
    if (!hasActiveSubscription) {
      return new Response('Active subscription required', { status: 403 });
    }

    // Upgrade connection
    const socket = await upgradeWebSocket(req);

    // Create connection object
    const connectionId = generateConnectionId();
    const connection: WebSocketConnection = {
      id: connectionId,
      userId: user.id,
      socket,
      subscribedChannels: new Set(),
      connectedAt: new Date(),
      lastActivity: new Date(),
      heartbeat: {
        lastPing: new Date(),
        lastPong: new Date(),
        missedPongs: 0,
      },
      metrics: {
        messagesReceived: 0,
        messagesSent: 0,
        bytesReceived: 0,
        bytesSent: 0,
      },
      isAlive: true,
      metadata: {
        ip: req.headers.get('x-forwarded-for') || 'unknown',
        userAgent: req.headers.get('user-agent') || 'unknown',
        authMethod: authResult.method || 'jwt',
      },
    };

    // Store connection
    connections.set(connectionId, connection);
    if (!userConnections.has(user.id)) {
      userConnections.set(user.id, new Set());
    }
    userConnections.get(user.id)?.add(connectionId);

    // Update metrics
    metrics.totalConnections++;
    metrics.activeConnections = connections.size;

    // Log connection
    await logWebSocketEvent({
      type: 'connection',
      connectionId,
      userId: user.id,
      metadata: connection.metadata,
      timestamp: new Date(),
    });

    // Setup connection handlers
    setupConnectionHandlers(connection);

    // Send initial connection acknowledgment
    sendToClient(connectionId, {
      type: WS_MESSAGE_TYPES.CONNECTION,
      event: WS_EVENTS.CONNECTION_ESTABLISHED,
      data: {
        connectionId,
        userId: user.id,
        timestamp: new Date().toISOString(),
        serverTime: new Date().toISOString(),
        subscription: {
          plan: user.subscriptionPlan?.name || 'free',
          tier: user.subscriptionPlan?.tier || 'free',
        },
      },
      timestamp: new Date().toISOString(),
    });

    return new Response('WebSocket connection established', { status: 101 });

  } catch (error: any) {
    console.error('WebSocket connection error:', error);
    return new Response('WebSocket connection failed', { status: 500 });
  }
}

// ============================================
// Connection Handler Setup
// ============================================

function setupConnectionHandlers(connection: WebSocketConnection) {
  const { id: connectionId, userId, socket } = connection;

  // Message handler
  socket.on('message', async (data: Buffer) => {
    try {
      await handleMessage(connectionId, data);
    } catch (error) {
      console.error('Message handling error:', error);
      handleError(connectionId, error);
    }
  });

  // Close handler
  socket.on('close', async (code: number, reason: string) => {
    await handleClose(connectionId, code, reason);
  });

  // Error handler
  socket.on('error', async (error: Error) => {
    await handleError(connectionId, error);
  });

  // Pong handler (for heartbeat)
  socket.on('pong', () => {
    handlePong(connectionId);
  });

  // Start heartbeat
  startHeartbeat(connectionId);
}

// ============================================
// Message Handler
// ============================================

async function handleMessage(connectionId: string, data: Buffer) {
  const connection = connections.get(connectionId);
  if (!connection || !connection.isAlive) {
    return;
  }

  // Update metrics
  connection.metrics.messagesReceived++;
  connection.metrics.bytesReceived += data.length;
  connection.lastActivity = new Date();

  // Parse message
  let message: WebSocketMessage;
  try {
    const rawMessage = data.toString();
    message = JSON.parse(rawMessage);
  } catch (error) {
    handleError(connectionId, new Error('Invalid JSON message'));
    return;
  }

  // Validate message
  const validation = await validateWebSocketMessage(message);
  if (!validation.isValid) {
    sendToClient(connectionId, {
      type: WS_MESSAGE_TYPES.ERROR,
      event: WS_EVENTS.ERROR,
      data: {
        error: validation.error || 'Invalid message',
        code: 'INVALID_MESSAGE',
      },
      timestamp: new Date().toISOString(),
    });
    return;
  }

  // Process message based on type
  try {
    switch (message.type) {
      case WS_MESSAGE_TYPES.SUBSCRIBE:
        await handleSubscribe(connectionId, message);
        break;

      case WS_MESSAGE_TYPES.UNSUBSCRIBE:
        await handleUnsubscribe(connectionId, message);
        break;

      case WS_MESSAGE_TYPES.PUBLISH:
        await handlePublish(connectionId, message);
        break;

      case WS_MESSAGE_TYPES.PING:
        await handlePing(connectionId, message);
        break;

      case WS_MESSAGE_TYPES.PONG:
        await handlePong(connectionId);
        break;

      case WS_MESSAGE_TYPES.PRESENCE:
        await handlePresence(connectionId, message);
        break;

      case WS_MESSAGE_TYPES.AUTH:
        await handleAuth(connectionId, message);
        break;

      case WS_MESSAGE_TYPES.LEAVE:
        await handleLeave(connectionId, message);
        break;

      case WS_MESSAGE_TYPES.JOIN:
        await handleJoin(connectionId, message);
        break;

      case WS_MESSAGE_TYPES.CHAT:
        await handleChat(connectionId, message);
        break;

      case WS_MESSAGE_TYPES.METRICS:
        await handleMetrics(connectionId, message);
        break;

      default:
        // Route to custom handler based on channel
        await routeToChannelHandler(connectionId, message);
    }

    // Update metrics
    metrics.totalMessages++;
  } catch (error: any) {
    console.error('Message processing error:', error);
    sendToClient(connectionId, {
      type: WS_MESSAGE_TYPES.ERROR,
      event: WS_EVENTS.ERROR,
      data: {
        error: error.message || 'Failed to process message',
        code: error.code || 'PROCESSING_ERROR',
      },
      timestamp: new Date().toISOString(),
    });
  }
}

// ============================================
// Subscription Handlers
// ============================================

async function handleSubscribe(connectionId: string, message: WebSocketMessage) {
  const connection = connections.get(connectionId);
  if (!connection) return;

  const { channel, params } = message.data;

  // Validate channel access
  const hasAccess = await validateChannelAccess(connection.userId, channel);
  if (!hasAccess) {
    sendToClient(connectionId, {
      type: WS_MESSAGE_TYPES.ERROR,
      event: WS_EVENTS.SUBSCRIPTION_FAILED,
      data: {
        channel,
        error: 'Access denied to channel',
        code: 'ACCESS_DENIED',
      },
      timestamp: new Date().toISOString(),
    });
    return;
  }

  // Check rate limit for subscriptions
  const isRateLimited = await checkSubscriptionRateLimit(connectionId, channel);
  if (isRateLimited) {
    sendToClient(connectionId, {
      type: WS_MESSAGE_TYPES.ERROR,
      event: WS_EVENTS.SUBSCRIPTION_FAILED,
      data: {
        channel,
        error: 'Rate limit exceeded for subscriptions',
        code: 'RATE_LIMITED',
      },
      timestamp: new Date().toISOString(),
    });
    return;
  }

  // Add to subscribed channels
  connection.subscribedChannels.add(channel);

  // Add to channel subscribers
  if (!channelSubscribers.has(channel)) {
    channelSubscribers.set(channel, new Set());
  }
  channelSubscribers.get(channel)?.add(connectionId);

  // Send confirmation
  sendToClient(connectionId, {
    type: WS_MESSAGE_TYPES.SUBSCRIBE,
    event: WS_EVENTS.SUBSCRIPTION_SUCCESS,
    data: {
      channel,
      subscribed: true,
      subscriberCount: channelSubscribers.get(channel)?.size || 0,
      timestamp: new Date().toISOString(),
    },
    timestamp: new Date().toISOString(),
  });

  // Log subscription
  await logWebSocketEvent({
    type: 'subscription',
    connectionId,
    userId: connection.userId,
    channel,
    metadata: { params },
    timestamp: new Date(),
  });

  // Send initial data if available
  await sendInitialChannelData(connectionId, channel, params);
}

async function handleUnsubscribe(connectionId: string, message: WebSocketMessage) {
  const connection = connections.get(connectionId);
  if (!connection) return;

  const { channel } = message.data;

  // Remove from subscribed channels
  connection.subscribedChannels.delete(channel);

  // Remove from channel subscribers
  if (channelSubscribers.has(channel)) {
    channelSubscribers.get(channel)?.delete(connectionId);
    if (channelSubscribers.get(channel)?.size === 0) {
      channelSubscribers.delete(channel);
    }
  }

  // Send confirmation
  sendToClient(connectionId, {
    type: WS_MESSAGE_TYPES.UNSUBSCRIBE,
    event: WS_EVENTS.UNSUBSCRIBED,
    data: {
      channel,
      unsubscribed: true,
      timestamp: new Date().toISOString(),
    },
    timestamp: new Date().toISOString(),
  });
}

// ============================================
// Message Publishing
// ============================================

async function handlePublish(connectionId: string, message: WebSocketMessage) {
  const connection = connections.get(connectionId);
  if (!connection) return;

  const { channel, data } = message.data;

  // Validate channel access
  const hasAccess = await validateChannelAccess(connection.userId, channel);
  if (!hasAccess) {
    sendToClient(connectionId, {
      type: WS_MESSAGE_TYPES.ERROR,
      event: WS_EVENTS.PUBLISH_FAILED,
      data: {
        channel,
        error: 'Access denied to publish to channel',
        code: 'ACCESS_DENIED',
      },
      timestamp: new Date().toISOString(),
    });
    return;
  }

  // Check if connection is subscribed to channel
  if (!connection.subscribedChannels.has(channel)) {
    sendToClient(connectionId, {
      type: WS_MESSAGE_TYPES.ERROR,
      event: WS_EVENTS.PUBLISH_FAILED,
      data: {
        channel,
        error: 'Not subscribed to channel',
        code: 'NOT_SUBSCRIBED',
      },
      timestamp: new Date().toISOString(),
    });
    return;
  }

  // Rate limit publishing
  const isRateLimited = await checkPublishRateLimit(connectionId, channel);
  if (isRateLimited) {
    sendToClient(connectionId, {
      type: WS_MESSAGE_TYPES.ERROR,
      event: WS_EVENTS.PUBLISH_FAILED,
      data: {
        channel,
        error: 'Rate limit exceeded for publishing',
        code: 'RATE_LIMITED',
      },
      timestamp: new Date().toISOString(),
    });
    return;
  }

  // Broadcast to channel
  await broadcastToChannel(channel, {
    type: WS_MESSAGE_TYPES.PUBLISH,
    event: WS_EVENTS.MESSAGE,
    data: {
      channel,
      sender: connection.userId,
      message: data,
      timestamp: new Date().toISOString(),
    },
    timestamp: new Date().toISOString(),
  }, [connectionId]); // Exclude sender

  // Send acknowledgment
  sendToClient(connectionId, {
    type: WS_MESSAGE_TYPES.PUBLISH,
    event: WS_EVENTS.PUBLISH_SUCCESS,
    data: {
      channel,
      delivered: true,
      timestamp: new Date().toISOString(),
    },
    timestamp: new Date().toISOString(),
  });

  // Update metrics
  connection.metrics.messagesSent++;
}

// ============================================
// Presence and Chat Handlers
// ============================================

async function handlePresence(connectionId: string, message: WebSocketMessage) {
  const connection = connections.get(connectionId);
  if (!connection) return;

  const { channel, status, metadata } = message.data;

  // Update presence
  await updatePresence(connection.userId, channel, status, metadata);

  // Broadcast presence update
  await broadcastToChannel(channel, {
    type: WS_MESSAGE_TYPES.PRESENCE,
    event: WS_EVENTS.PRESENCE_UPDATE,
    data: {
      userId: connection.userId,
      status,
      metadata,
      timestamp: new Date().toISOString(),
    },
    timestamp: new Date().toISOString(),
  });
}

async function handleChat(connectionId: string, message: WebSocketMessage) {
  const connection = connections.get(connectionId);
  if (!connection) return;

  const { channel, content, metadata } = message.data;

  // Save chat message to database
  const chatMessage = await prisma.chatMessage.create({
    data: {
      userId: connection.userId,
      channel: channel,
      content: content,
      metadata: metadata || {},
      createdAt: new Date(),
    },
  });

  // Broadcast to channel
  await broadcastToChannel(channel, {
    type: WS_MESSAGE_TYPES.CHAT,
    event: WS_EVENTS.CHAT_MESSAGE,
    data: {
      id: chatMessage.id,
      userId: connection.userId,
      content,
      metadata,
      timestamp: new Date().toISOString(),
    },
    timestamp: new Date().toISOString(),
  });
}

// ============================================
// Heartbeat and Keep-alive
// ============================================

function startHeartbeat(connectionId: string) {
  const connection = connections.get(connectionId);
  if (!connection) return;

  const heartbeatInterval = setInterval(() => {
    const conn = connections.get(connectionId);
    if (!conn) {
      clearInterval(heartbeatInterval);
      return;
    }

    if (!conn.isAlive) {
      clearInterval(heartbeatInterval);
      handleClose(connectionId, 1006, 'Heartbeat timeout');
      return;
    }

    // Check for missed pongs
    const now = Date.now();
    const lastPongTime = conn.heartbeat.lastPong.getTime();
    if (now - lastPongTime > WS_HEARTBEAT_INTERVAL * 2) {
      conn.heartbeat.missedPongs++;
      if (conn.heartbeat.missedPongs > 3) {
        conn.isAlive = false;
        clearInterval(heartbeatInterval);
        handleClose(connectionId, 1006, 'Missed heartbeats');
        return;
      }
    }

    // Send ping
    if (conn.socket.readyState === WebSocket.OPEN) {
      conn.socket.ping();
      conn.heartbeat.lastPing = new Date();
    }
  }, WS_HEARTBEAT_INTERVAL);

  // Store interval for cleanup
  (connection as any).heartbeatInterval = heartbeatInterval;
}

async function handlePing(connectionId: string, message: WebSocketMessage) {
  const connection = connections.get(connectionId);
  if (!connection) return;

  // Update last ping
  connection.heartbeat.lastPing = new Date();

  // Send pong response
  sendToClient(connectionId, {
    type: WS_MESSAGE_TYPES.PONG,
    event: WS_EVENTS.PONG,
    data: {
      timestamp: new Date().toISOString(),
      echo: message.data?.timestamp || null,
    },
    timestamp: new Date().toISOString(),
  });
}

async function handlePong(connectionId: string) {
  const connection = connections.get(connectionId);
  if (!connection) return;

  // Update last pong
  connection.heartbeat.lastPong = new Date();
  connection.heartbeat.missedPongs = 0;
  connection.isAlive = true;
}

// ============================================
// Connection Lifecycle Handlers
// ============================================

async function handleClose(connectionId: string, code: number, reason: string) {
  const connection = connections.get(connectionId);
  if (!connection) return;

  // Mark as inactive
  connection.isAlive = false;

  // Clean up heartbeat interval
  if ((connection as any).heartbeatInterval) {
    clearInterval((connection as any).heartbeatInterval);
  }

  // Remove from all subscribed channels
  for (const channel of connection.subscribedChannels) {
    if (channelSubscribers.has(channel)) {
      channelSubscribers.get(channel)?.delete(connectionId);
      if (channelSubscribers.get(channel)?.size === 0) {
        channelSubscribers.delete(channel);
      }
    }
  }

  // Remove from user connections
  if (userConnections.has(connection.userId)) {
    userConnections.get(connection.userId)?.delete(connectionId);
    if (userConnections.get(connection.userId)?.size === 0) {
      userConnections.delete(connection.userId);
    }
  }

  // Remove from connections store
  connections.delete(connectionId);

  // Update metrics
  metrics.activeConnections = connections.size;

  // Log disconnection
  await logWebSocketEvent({
    type: 'disconnection',
    connectionId,
    userId: connection.userId,
    metadata: {
      code,
      reason,
      duration: Date.now() - connection.connectedAt.getTime(),
    },
    timestamp: new Date(),
  });

  // Broadcast presence offline
  await broadcastPresenceOffline(connection.userId);
}

async function handleError(connectionId: string, error: any) {
  const connection = connections.get(connectionId);
  if (!connection) return;

  metrics.errors++;

  // Log error
  await logWebSocketEvent({
    type: 'error',
    connectionId,
    userId: connection.userId,
    metadata: {
      error: error.message || String(error),
      stack: error.stack,
    },
    timestamp: new Date(),
  });

  // Send error to client if connection is still open
  if (connection.socket.readyState === WebSocket.OPEN) {
    sendToClient(connectionId, {
      type: WS_MESSAGE_TYPES.ERROR,
      event: WS_EVENTS.ERROR,
      data: {
        error: error.message || 'An error occurred',
        code: error.code || 'INTERNAL_ERROR',
      },
      timestamp: new Date().toISOString(),
    });
  }

  // Close connection on fatal errors
  if (error.fatal) {
    connection.socket.close(1011, error.message || 'Internal error');
  }
}

// ============================================
// Helper Functions
// ============================================

async function upgradeWebSocket(req: NextRequest): Promise<WebSocket> {
  return new Promise((resolve, reject) => {
    const { socket, head } = (req as any).upgradeWebSocket();
    const ws = new WebSocket(socket, head, {
      maxPayload: WS_MESSAGE_SIZE_LIMIT,
    });
    
    ws.on('open', () => resolve(ws));
    ws.on('error', reject);
  });
}

async function checkUserSubscription(userId: string): Promise<boolean> {
  const subscription = await prisma.subscription.findFirst({
    where: {
      userId,
      status: 'active',
      currentPeriodEnd: {
        gt: new Date(),
      },
    },
  });
  
  return !!subscription;
}

async function checkSubscriptionRateLimit(
  connectionId: string,
  channel: string
): Promise<boolean> {
  const key = `ws:subscriptions:${connectionId}`;
  const count = parseInt(await redis.get(key) || '0');
  const max = 50; // Max 50 subscriptions per minute
  
  if (count >= max) {
    return true;
  }
  
  if (count === 0) {
    await redis.set(key, '1', 'EX', 60);
  } else {
    await redis.incr(key);
  }
  
  return false;
}

async function checkPublishRateLimit(
  connectionId: string,
  channel: string
): Promise<boolean> {
  const key = `ws:publish:${connectionId}:${channel}`;
  const count = parseInt(await redis.get(key) || '0');
  const max = 30; // Max 30 messages per minute per channel
  
  if (count >= max) {
    return true;
  }
  
  if (count === 0) {
    await redis.set(key, '1', 'EX', 60);
  } else {
    await redis.incr(key);
  }
  
  return false;
}

async function sendInitialChannelData(
  connectionId: string,
  channel: string,
  params: any
) {
  // Get channel-specific initial data
  let data = null;
  
  switch (channel) {
    case WS_CHANNELS.AI_PREDICTIONS:
      data = await getInitialPredictions(params);
      break;
    case WS_CHANNELS.MARKET_DATA:
      data = await getInitialMarketData(params);
      break;
    case WS_CHANNELS.PORTFOLIO:
      data = await getInitialPortfolio(params);
      break;
    case WS_CHANNELS.ALERTS:
      data = await getInitialAlerts(params);
      break;
    case WS_CHANNELS.CHAT:
      data = await getInitialChatMessages(params);
      break;
    default:
      break;
  }
  
  if (data) {
    sendToClient(connectionId, {
      type: WS_MESSAGE_TYPES.DATA,
      event: WS_EVENTS.INITIAL_DATA,
      data: {
        channel,
        data,
        timestamp: new Date().toISOString(),
      },
      timestamp: new Date().toISOString(),
    });
  }
}

async function routeToChannelHandler(
  connectionId: string,
  message: WebSocketMessage
) {
  // Custom channel-specific message handling
  const { channel } = message.data || {};
  if (!channel) return;

  // Route to appropriate channel handler
  switch (channel) {
    case WS_CHANNELS.AI_PREDICTIONS:
      await handleAIPredictionMessage(connectionId, message);
      break;
    case WS_CHANNELS.MARKET_DATA:
      await handleMarketDataMessage(connectionId, message);
      break;
    case WS_CHANNELS.PORTFOLIO:
      await handlePortfolioMessage(connectionId, message);
      break;
    case WS_CHANNELS.ALERTS:
      await handleAlertMessage(connectionId, message);
      break;
    case WS_CHANNELS.CHAT:
      await handleChatMessage(connectionId, message);
      break;
    default:
      throw new Error(`Unknown channel: ${channel}`);
  }
}

async function broadcastPresenceOffline(userId: string) {
  // Broadcast offline presence to all channels user was in
  const userChannels = await getChannelsForUser(userId);
  
  for (const channel of userChannels) {
    await broadcastToChannel(channel, {
      type: WS_MESSAGE_TYPES.PRESENCE,
      event: WS_EVENTS.PRESENCE_UPDATE,
      data: {
        userId,
        status: 'offline',
        timestamp: new Date().toISOString(),
      },
      timestamp: new Date().toISOString(),
    });
  }
}

async function getChannelsForUser(userId: string): Promise<string[]> {
  const channels: string[] = [];
  for (const [channel, subscribers] of channelSubscribers) {
    const userConnections = Array.from(subscribers).filter(connId => {
      const conn = connections.get(connId);
      return conn?.userId === userId;
    });
    if (userConnections.length > 0) {
      channels.push(channel);
    }
  }
  return channels;
}

// ============================================
// Channel-Specific Data Handlers
// ============================================

async function getInitialPredictions(params: any) {
  // Implementation for initial predictions data
  return { predictions: [] };
}

async function getInitialMarketData(params: any) {
  // Implementation for initial market data
  return { marketData: {} };
}

async function getInitialPortfolio(params: any) {
  // Implementation for initial portfolio data
  return { portfolio: {} };
}

async function getInitialAlerts(params: any) {
  // Implementation for initial alerts data
  return { alerts: [] };
}

async function getInitialChatMessages(params: any) {
  // Implementation for initial chat messages
  return { messages: [] };
}

async function handleAIPredictionMessage(connectionId: string, message: WebSocketMessage) {
  // AI prediction channel message handler
}

async function handleMarketDataMessage(connectionId: string, message: WebSocketMessage) {
  // Market data channel message handler
}

async function handlePortfolioMessage(connectionId: string, message: WebSocketMessage) {
  // Portfolio channel message handler
}

async function handleAlertMessage(connectionId: string, message: WebSocketMessage) {
  // Alert channel message handler
}

async function handleChatMessage(connectionId: string, message: WebSocketMessage) {
  // Chat channel message handler
}

// ============================================
// Metrics Collection
// ============================================

function startMetricsCollection() {
  if (metricsInterval) {
    clearInterval(metricsInterval);
  }
  
  metricsInterval = setInterval(() => {
    // Update metrics
    const now = Date.now();
    const connectionsList = Array.from(connections.values());
    const totalMessages = connectionsList.reduce((sum, conn) => 
      sum + conn.metrics.messagesReceived + conn.metrics.messagesSent, 0
    );
    const totalBytes = connectionsList.reduce((sum, conn) => 
      sum + conn.metrics.bytesReceived + conn.metrics.bytesSent, 0
    );
    
    metrics.totalMessages = totalMessages;
    metrics.bytesTransferred = totalBytes;
    metrics.messagesPerSecond = totalMessages / 60; // Average per second over last minute
    
    // Store metrics in Redis
    redis.set('ws:metrics', JSON.stringify({
      ...metrics,
      timestamp: new Date().toISOString(),
    }), 'EX', 60);
    
    // Log metrics
    if (connections.size > 0) {
      console.debug(`WebSocket Metrics: ${connections.size} connections, ${totalMessages} messages`);
    }
  }, 60000); // Update every minute
}

// ============================================
// Initialization
// ============================================

// Start metrics collection
startMetricsCollection();

// Handle process cleanup
process.on('SIGTERM', () => {
  if (metricsInterval) {
    clearInterval(metricsInterval);
  }
  
  // Close all connections
  for (const [connectionId, connection] of connections) {
    connection.socket.close(1001, 'Server shutting down');
  }
});

// ============================================
// Type Definitions
// ============================================

declare module '@/types/websocket' {
  export interface WebSocketMessage {
    id?: string;
    type: WebSocketMessageType;
    event?: WebSocketEventType;
    data: any;
    channel?: WebSocketChannelType;
    timestamp: string;
    userId?: string;
    metadata?: Record<string, any>;
  }

  export interface WebSocketChannel {
    id: string;
    name: string;
    type: string;
    subscribers: number;
    metadata: Record<string, any>;
    createdAt: Date;
  }

  export interface WebSocketSubscription {
    channel: string;
    userId: string;
    connectionId: string;
    subscribedAt: Date;
    params: Record<string, any>;
  }

  export interface WebSocketEvent {
    id: string;
    type: string;
    channel: string;
    data: any;
    timestamp: Date;
    userId: string;
  }

  export interface WebSocketConnection {
    id: string;
    userId: string;
    socket: WebSocket;
    subscribedChannels: Set<string>;
    connectedAt: Date;
    lastActivity: Date;
    heartbeat: {
      lastPing: Date;
      lastPong: Date;
      missedPongs: number;
    };
    metrics: {
      messagesReceived: number;
      messagesSent: number;
      bytesReceived: number;
      bytesSent: number;
    };
    isAlive: boolean;
    metadata: {
      ip: string;
      userAgent: string;
      authMethod: string;
    };
  }

  export interface WebSocketPresence {
    userId: string;
    status: 'online' | 'away' | 'offline' | 'busy';
    lastSeen: Date;
    metadata: Record<string, any>;
  }

  export interface WebSocketMetrics {
    totalConnections: number;
    activeConnections: number;
    totalMessages: number;
    messagesPerSecond: number;
    errors: number;
    bytesTransferred: number;
  }

  export interface WebSocketAuth {
    userId: string;
    token: string;
    method: 'jwt' | 'api_key' | 'session';
    expiresAt?: Date;
  }
}

// ============================================
// Constants
// ============================================

export const WS_MESSAGE_TYPES = {
  CONNECTION: 'connection',
  SUBSCRIBE: 'subscribe',
  UNSUBSCRIBE: 'unsubscribe',
  PUBLISH: 'publish',
  PING: 'ping',
  PONG: 'pong',
  PRESENCE: 'presence',
  AUTH: 'auth',
  LEAVE: 'leave',
  JOIN: 'join',
  CHAT: 'chat',
  METRICS: 'metrics',
  DATA: 'data',
  ERROR: 'error',
} as const;

export const WS_CHANNELS = {
  AI_PREDICTIONS: 'ai_predictions',
  MARKET_DATA: 'market_data',
  PORTFOLIO: 'portfolio',
  ALERTS: 'alerts',
  CHAT: 'chat',
  SYSTEM: 'system',
  TRADING: 'trading',
  RISK: 'risk',
  PERFORMANCE: 'performance',
} as const;

export const WS_EVENTS = {
  CONNECTION_ESTABLISHED: 'connection_established',
  CONNECTION_CLOSED: 'connection_closed',
  SUBSCRIPTION_SUCCESS: 'subscription_success',
  SUBSCRIPTION_FAILED: 'subscription_failed',
  UNSUBSCRIBED: 'unsubscribed',
  PUBLISH_SUCCESS: 'publish_success',
  PUBLISH_FAILED: 'publish_failed',
  MESSAGE: 'message',
  PRESENCE_UPDATE: 'presence_update',
  CHAT_MESSAGE: 'chat_message',
  INITIAL_DATA: 'initial_data',
  ERROR: 'error',
  PONG: 'pong',
} as const;

export const WS_MESSAGE_SIZE_LIMIT = 1024 * 1024; // 1MB
export const WS_CONNECTION_TIMEOUT = 30000; // 30 seconds
export const WS_HEARTBEAT_INTERVAL = 15000; // 15 seconds
export const WS_MAX_CONNECTIONS_PER_USER = 5;
export const WS_RATE_LIMIT = 60; // 60 messages per minute
export const WS_RECONNECT_GRACE_PERIOD = 5000; // 5 seconds

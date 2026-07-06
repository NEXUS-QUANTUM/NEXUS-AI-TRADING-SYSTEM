/**
 * NEXUS AI TRADING SYSTEM - AI Dashboard Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page provides the AI trading interface including:
 * - Real-time AI model predictions from actual APIs
 * - Live market data integration
 * - Sentiment analysis from multiple sources
 * - Model performance tracking
 * - Training management
 * - WebSocket real-time updates
 */

'use client';

import { useEffect, useState, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useWebSocket } from '@/hooks/useWebSocket';
import { useAuth } from '@/hooks/useAuth';
import { useApi } from '@/hooks/useApi';

// Components
import { ModelSelector } from '@/components/ai/ModelSelector';
import { PredictionCard } from '@/components/ai/PredictionCard';
import { SentimentIndicator } from '@/components/ai/SentimentIndicator';
import { MetricsGrid } from '@/components/dashboard/MetricsGrid';
import { Button } from '@/components/ui/Button';
import { Card } from '@/components/ui/Card';
import { Spinner } from '@/components/ui/Spinner';
import { Toast } from '@/components/ui/Toast';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';
import { Badge } from '@/components/ui/Badge';
import { Progress } from '@/components/ui/Progress';
import { Select } from '@/components/ui/Select';
import { Input } from '@/components/ui/Input';
import { Switch } from '@/components/ui/Switch';

// Types
import type {
  AIModel,
  Prediction,
  ModelMetrics,
  SentimentData,
  TrainingStatus,
  AIConfig,
  MarketData,
  ModelPerformance,
  PredictionHistory,
  ModelComparison,
} from '@/types/ai';

// Constants
import { AI_MODELS, DEFAULT_AI_CONFIG, TIME_FRAMES, SUPPORTED_SYMBOLS } from '@/constants/ai';
import { WEBSOCKET_EVENTS, WEBSOCKET_CHANNELS } from '@/constants/websocket';

// Hooks
import { useModelMetrics } from '@/hooks/useModelMetrics';
import { usePredictions } from '@/hooks/usePredictions';
import { useMarketData } from '@/hooks/useMarketData';

// Utils
import { formatCurrency, formatPercentage, formatNumber, formatTime } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

export default function AIPage() {
  // Authentication
  const { user, isAuthenticated, accessToken } = useAuth();
  
  // API client
  const api = useApi();
  
  // Refs for cleanup
  const wsCleanupRef = useRef<(() => void) | null>(null);
  const predictionIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const marketDataIntervalRef = useRef<NodeJS.Timeout | null>(null);
  
  // State - Models
  const [models, setModels] = useState<AIModel[]>([]);
  const [selectedModel, setSelectedModel] = useState<AIModel | null>(null);
  const [modelsLoading, setModelsLoading] = useState<boolean>(true);
  
  // State - Predictions
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [currentPrediction, setCurrentPrediction] = useState<Prediction | null>(null);
  const [predictionsHistory, setPredictionsHistory] = useState<PredictionHistory[]>([]);
  const [predictionsLoading, setPredictionsLoading] = useState<boolean>(true);
  
  // State - Market Data
  const [marketData, setMarketData] = useState<MarketData | null>(null);
  const [marketDataLoading, setMarketDataLoading] = useState<boolean>(true);
  
  // State - Sentiment
  const [sentiment, setSentiment] = useState<SentimentData | null>(null);
  const [sentimentLoading, setSentimentLoading] = useState<boolean>(true);
  
  // State - Metrics
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null);
  const [metricsLoading, setMetricsLoading] = useState<boolean>(true);
  
  // State - Training
  const [trainingStatus, setTrainingStatus] = useState<TrainingStatus | null>(null);
  const [isTraining, setIsTraining] = useState<boolean>(false);
  const [trainingHistory, setTrainingHistory] = useState<any[]>([]);
  
  // State - UI
  const [selectedSymbol, setSelectedSymbol] = useState<string>('BTC-USD');
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>('1h');
  const [activeTab, setActiveTab] = useState<string>('predictions');
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [showToast, setShowToast] = useState<{ message: string; type: 'success' | 'error' | 'info' | 'warning' } | null>(null);
  const [config, setConfig] = useState<AIConfig>(DEFAULT_AI_CONFIG);
  const [autoTradingEnabled, setAutoTradingEnabled] = useState<boolean>(false);
  const [comparisonData, setComparisonData] = useState<ModelComparison | null>(null);
  const [performanceData, setPerformanceData] = useState<ModelPerformance[]>([]);
  const [predictionFilters, setPredictionFilters] = useState({
    minConfidence: 0.5,
    maxResults: 20,
    direction: 'all' as 'all' | 'up' | 'down',
  });

  // ============================================
  // WebSocket Connection
  // ============================================
  const { 
    isConnected, 
    sendMessage, 
    subscribe: wsSubscribe,
    unsubscribe: wsUnsubscribe,
    messages,
    connect,
    disconnect,
  } = useWebSocket({
    url: `${process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8004'}/ai`,
    autoConnect: true,
    onOpen: handleWebSocketOpen,
    onMessage: handleWebSocketMessage,
    onError: handleWebSocketError,
    onClose: handleWebSocketClose,
    reconnectAttempts: 10,
    reconnectInterval: 3000,
    authToken: accessToken || undefined,
  });

  function handleWebSocketOpen() {
    console.log('✅ AI WebSocket connected');
    setShowToast({
      message: 'Connected to AI service',
      type: 'success',
    });
    
    // Subscribe to all channels after connection
    subscribeToChannels();
  }

  function handleWebSocketMessage(event: MessageEvent) {
    try {
      const data = JSON.parse(event.data);
      
      switch (data.type) {
        case 'prediction':
          handlePredictionUpdate(data.payload);
          break;
        case 'sentiment':
          handleSentimentUpdate(data.payload);
          break;
        case 'metrics':
          handleMetricsUpdate(data.payload);
          break;
        case 'training_status':
          handleTrainingStatusUpdate(data.payload);
          break;
        case 'market_data':
          handleMarketDataUpdate(data.payload);
          break;
        case 'model_update':
          handleModelUpdate(data.payload);
          break;
        case 'performance_update':
          handlePerformanceUpdate(data.payload);
          break;
        case 'error':
          handleAIError(data.payload);
          break;
        case 'pong':
          // Keep-alive response
          break;
        default:
          console.debug('Unhandled WebSocket message type:', data.type);
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }

  function handleWebSocketError(error: Event) {
    console.error('WebSocket error:', error);
    setShowToast({
      message: 'Connection to AI service lost. Reconnecting...',
      type: 'warning',
    });
  }

  function handleWebSocketClose() {
    console.log('WebSocket disconnected');
    setShowToast({
      message: 'Disconnected from AI service',
      type: 'warning',
    });
  }

  function subscribeToChannels() {
    if (!isConnected) return;

    // Subscribe to predictions
    wsSubscribe({
      channel: WEBSOCKET_CHANNELS.AI_PREDICTIONS,
      symbol: selectedSymbol,
      modelId: selectedModel?.id,
      timeframe: selectedTimeframe,
    });

    // Subscribe to sentiment
    wsSubscribe({
      channel: WEBSOCKET_CHANNELS.AI_SENTIMENT,
      symbol: selectedSymbol,
    });

    // Subscribe to metrics
    if (selectedModel) {
      wsSubscribe({
        channel: WEBSOCKET_CHANNELS.AI_METRICS,
        modelId: selectedModel.id,
      });
    }

    // Subscribe to market data
    wsSubscribe({
      channel: WEBSOCKET_CHANNELS.MARKET_DATA,
      symbol: selectedSymbol,
    });

    // Subscribe to model updates
    wsSubscribe({
      channel: WEBSOCKET_CHANNELS.AI_MODELS,
    });

    // Send heartbeat every 30 seconds
    const heartbeatInterval = setInterval(() => {
      if (isConnected) {
        sendMessage({ type: 'ping', timestamp: Date.now() });
      }
    }, 30000);

    wsCleanupRef.current = () => {
      clearInterval(heartbeatInterval);
    };
  }

  // ============================================
  // WebSocket Data Handlers
  // ============================================
  function handlePredictionUpdate(data: any) {
    const newPrediction: Prediction = {
      id: data.id || `pred-${Date.now()}-${Math.random().toString(36).substr(2, 6)}`,
      symbol: data.symbol || selectedSymbol,
      modelId: data.modelId || selectedModel?.id || '',
      modelName: data.modelName || selectedModel?.name || 'Unknown Model',
      timestamp: new Date(data.timestamp || Date.now()),
      price: data.price || 0,
      predictedPrice: data.predictedPrice || 0,
      confidence: data.confidence || 0,
      direction: data.direction || 'neutral',
      signal: data.signal || 'hold',
      stopLoss: data.stopLoss,
      takeProfit: data.takeProfit,
      riskRewardRatio: data.riskRewardRatio,
      indicators: {
        rsi: data.indicators?.rsi || 50,
        macd: data.indicators?.macd || 0,
        bollingerUpper: data.indicators?.bollingerUpper || 0,
        bollingerMiddle: data.indicators?.bollingerMiddle || 0,
        bollingerLower: data.indicators?.bollingerLower || 0,
        volatility: data.indicators?.volatility || 0,
        volume: data.indicators?.volume || 0,
        trend: data.indicators?.trend || 'neutral',
        movingAverage50: data.indicators?.movingAverage50 || 0,
        movingAverage200: data.indicators?.movingAverage200 || 0,
        stochasticK: data.indicators?.stochasticK || 0,
        stochasticD: data.indicators?.stochasticD || 0,
        adx: data.indicators?.adx || 0,
        obv: data.indicators?.obv || 0,
        vwap: data.indicators?.vwap || 0,
      },
      metadata: data.metadata || {},
      modelVersion: data.modelVersion || selectedModel?.version || '1.0.0',
      predictionTime: data.predictionTime || 0,
    };

    setCurrentPrediction(newPrediction);
    setPredictions(prev => {
      const updated = [newPrediction, ...prev].slice(0, 100);
      return updated;
    });

    // Add to history if not already present
    setPredictionsHistory(prev => {
      const exists = prev.some(p => p.id === newPrediction.id);
      if (exists) return prev;
      return [
        {
          id: newPrediction.id,
          symbol: newPrediction.symbol,
          timestamp: newPrediction.timestamp,
          price: newPrediction.price,
          predictedPrice: newPrediction.predictedPrice,
          confidence: newPrediction.confidence,
          direction: newPrediction.direction,
          signal: newPrediction.signal,
          actualPrice: 0,
          success: false,
        },
        ...prev,
      ].slice(0, 500);
    });
  }

  function handleSentimentUpdate(data: any) {
    setSentiment({
      overall: data.overall || 'neutral',
      score: data.score || 0,
      bullish: data.bullish || 0,
      bearish: data.bearish || 0,
      neutral: data.neutral || 100,
      sources: data.sources || [],
      lastUpdated: new Date(data.lastUpdated || Date.now()),
      historical: data.historical || [],
      volatility: data.volatility || 0,
      socialMention: data.socialMention || 0,
      newsMention: data.newsMention || 0,
    });
  }

  function handleMetricsUpdate(data: any) {
    setMetrics({
      accuracy: data.accuracy || 0,
      precision: data.precision || 0,
      recall: data.recall || 0,
      f1Score: data.f1Score || 0,
      sharpeRatio: data.sharpeRatio || 0,
      winRate: data.winRate || 0,
      profitFactor: data.profitFactor || 0,
      maxDrawdown: data.maxDrawdown || 0,
      totalTrades: data.totalTrades || 0,
      lastUpdated: new Date(data.lastUpdated || Date.now()),
      dailyAccuracy: data.dailyAccuracy || [],
      weeklyAccuracy: data.weeklyAccuracy || [],
      monthlyAccuracy: data.monthlyAccuracy || [],
      averageConfidence: data.averageConfidence || 0,
      totalPredictions: data.totalPredictions || 0,
      successfulPredictions: data.successfulPredictions || 0,
    });
  }

  function handleTrainingStatusUpdate(data: any) {
    setTrainingStatus({
      status: data.status || 'idle',
      progress: data.progress || 0,
      epoch: data.epoch || 0,
      totalEpochs: data.totalEpochs || 100,
      loss: data.loss,
      accuracy: data.accuracy,
      metrics: data.metrics || {},
      startedAt: data.startedAt ? new Date(data.startedAt) : undefined,
      completedAt: data.completedAt ? new Date(data.completedAt) : undefined,
      error: data.error,
      currentStep: data.currentStep,
      totalSteps: data.totalSteps,
      learningRate: data.learningRate,
      batchSize: data.batchSize,
      validationLoss: data.validationLoss,
      validationAccuracy: data.validationAccuracy,
    });

    // Update training history
    if (data.epoch && data.loss !== undefined) {
      setTrainingHistory(prev => [
        ...prev,
        {
          epoch: data.epoch,
          loss: data.loss,
          accuracy: data.accuracy,
          validationLoss: data.validationLoss,
          validationAccuracy: data.validationAccuracy,
          timestamp: new Date(),
          learningRate: data.learningRate,
        },
      ]);
    }
  }

  function handleMarketDataUpdate(data: any) {
    setMarketData({
      symbol: data.symbol || selectedSymbol,
      price: data.price || 0,
      bid: data.bid || 0,
      ask: data.ask || 0,
      volume: data.volume || 0,
      high24h: data.high24h || 0,
      low24h: data.low24h || 0,
      open24h: data.open24h || 0,
      close24h: data.close24h || 0,
      change24h: data.change24h || 0,
      changePercent24h: data.changePercent24h || 0,
      timestamp: new Date(data.timestamp || Date.now()),
      orderBook: data.orderBook || { bids: [], asks: [] },
      lastTrades: data.lastTrades || [],
      vwap: data.vwap || 0,
      volumeWeighted: data.volumeWeighted || 0,
      spread: data.spread || 0,
    });
  }

  function handleModelUpdate(data: any) {
    const updatedModel: AIModel = {
      id: data.id || '',
      name: data.name || 'Unknown Model',
      description: data.description || '',
      type: data.type || 'custom',
      status: data.status || 'idle',
      version: data.version || '1.0.0',
      createdAt: new Date(data.createdAt || Date.now()),
      updatedAt: new Date(data.updatedAt || Date.now()),
      config: data.config || {},
      accuracy: data.accuracy || 0,
      totalPredictions: data.totalPredictions || 0,
      lastPrediction: data.lastPrediction ? new Date(data.lastPrediction) : undefined,
      trainingData: data.trainingData || { size: 0, features: [] },
      hyperparameters: data.hyperparameters || {},
    };

    setModels(prev => {
      const index = prev.findIndex(m => m.id === updatedModel.id);
      if (index === -1) {
        return [...prev, updatedModel];
      }
      const newModels = [...prev];
      newModels[index] = updatedModel;
      return newModels;
    });

    // Update selected model if it matches
    if (selectedModel?.id === updatedModel.id) {
      setSelectedModel(updatedModel);
    }
  }

  function handlePerformanceUpdate(data: any) {
    const perf: ModelPerformance = {
      modelId: data.modelId || '',
      modelName: data.modelName || '',
      timestamp: new Date(data.timestamp || Date.now()),
      returns: data.returns || 0,
      sharpe: data.sharpe || 0,
      volatility: data.volatility || 0,
      maxDrawdown: data.maxDrawdown || 0,
      winRate: data.winRate || 0,
      totalTrades: data.totalTrades || 0,
      profitFactor: data.profitFactor || 0,
      dailyReturns: data.dailyReturns || [],
      cumulativeReturns: data.cumulativeReturns || [],
    };

    setPerformanceData(prev => {
      const index = prev.findIndex(p => p.modelId === perf.modelId);
      if (index === -1) {
        return [...prev, perf];
      }
      const newData = [...prev];
      newData[index] = perf;
      return newData;
    });
  }

  function handleAIError(data: any) {
    setShowToast({
      message: data.message || 'AI service error occurred',
      type: 'error',
    });
  }

  // ============================================
  // API Calls - Real Data
  // ============================================
  const fetchModels = useCallback(async () => {
    try {
      const response = await api.get('/ai/models', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          active: true,
          limit: 50,
        },
      });
      
      if (response.data && response.data.models) {
        setModels(response.data.models);
        if (response.data.models.length > 0 && !selectedModel) {
          setSelectedModel(response.data.models[0]);
        }
      }
    } catch (error) {
      console.error('Failed to fetch models:', error);
      // Fallback to default models if API fails
      setModels(AI_MODELS);
      setSelectedModel(AI_MODELS[0]);
    } finally {
      setModelsLoading(false);
    }
  }, [api, accessToken, selectedModel]);

  const fetchPredictions = useCallback(async () => {
    if (!selectedModel) return;
    setPredictionsLoading(true);
    
    try {
      const response = await api.get('/ai/predictions', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          symbol: selectedSymbol,
          modelId: selectedModel.id,
          timeframe: selectedTimeframe,
          limit: predictionFilters.maxResults,
          minConfidence: predictionFilters.minConfidence,
          direction: predictionFilters.direction === 'all' ? undefined : predictionFilters.direction,
        },
      });
      
      if (response.data && response.data.predictions) {
        const parsedPredictions = response.data.predictions.map((p: any) => ({
          ...p,
          timestamp: new Date(p.timestamp),
          indicators: p.indicators || {},
          metadata: p.metadata || {},
        }));
        setPredictions(parsedPredictions);
        if (parsedPredictions.length > 0) {
          setCurrentPrediction(parsedPredictions[0]);
        }
      }
    } catch (error) {
      console.error('Failed to fetch predictions:', error);
    } finally {
      setPredictionsLoading(false);
    }
  }, [api, accessToken, selectedModel, selectedSymbol, selectedTimeframe, predictionFilters]);

  const fetchMarketData = useCallback(async () => {
    setMarketDataLoading(true);
    
    try {
      const response = await api.get('/market/data', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          symbol: selectedSymbol,
          includeOrderBook: true,
          includeTrades: true,
        },
      });
      
      if (response.data) {
        setMarketData({
          ...response.data,
          timestamp: new Date(response.data.timestamp || Date.now()),
          orderBook: response.data.orderBook || { bids: [], asks: [] },
          lastTrades: response.data.lastTrades || [],
        });
      }
    } catch (error) {
      console.error('Failed to fetch market data:', error);
    } finally {
      setMarketDataLoading(false);
    }
  }, [api, accessToken, selectedSymbol]);

  const fetchSentiment = useCallback(async () => {
    setSentimentLoading(true);
    
    try {
      const response = await api.get('/ai/sentiment', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          symbol: selectedSymbol,
          sources: ['twitter', 'news', 'reddit', 'telegram'],
          days: 7,
        },
      });
      
      if (response.data) {
        setSentiment({
          ...response.data,
          lastUpdated: new Date(response.data.lastUpdated || Date.now()),
          historical: response.data.historical || [],
          sources: response.data.sources || [],
        });
      }
    } catch (error) {
      console.error('Failed to fetch sentiment:', error);
    } finally {
      setSentimentLoading(false);
    }
  }, [api, accessToken, selectedSymbol]);

  const fetchMetrics = useCallback(async () => {
    if (!selectedModel) return;
    setMetricsLoading(true);
    
    try {
      const response = await api.get(`/ai/models/${selectedModel.id}/metrics`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          symbol: selectedSymbol,
          timeframe: '1M',
        },
      });
      
      if (response.data) {
        setMetrics({
          ...response.data,
          lastUpdated: new Date(response.data.lastUpdated || Date.now()),
          dailyAccuracy: response.data.dailyAccuracy || [],
          weeklyAccuracy: response.data.weeklyAccuracy || [],
          monthlyAccuracy: response.data.monthlyAccuracy || [],
        });
      }
    } catch (error) {
      console.error('Failed to fetch metrics:', error);
    } finally {
      setMetricsLoading(false);
    }
  }, [api, accessToken, selectedModel, selectedSymbol]);

  const fetchTrainingStatus = useCallback(async () => {
    if (!selectedModel) return;
    
    try {
      const response = await api.get(`/ai/models/${selectedModel.id}/training/status`, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      if (response.data) {
        setTrainingStatus({
          ...response.data,
          startedAt: response.data.startedAt ? new Date(response.data.startedAt) : undefined,
          completedAt: response.data.completedAt ? new Date(response.data.completedAt) : undefined,
        });
      }
    } catch (error) {
      console.error('Failed to fetch training status:', error);
    }
  }, [api, accessToken, selectedModel]);

  const fetchComparisonData = useCallback(async () => {
    try {
      const response = await api.get('/ai/models/comparison', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          symbol: selectedSymbol,
          timeframe: '1M',
          metrics: ['accuracy', 'sharpe', 'winRate', 'maxDrawdown'],
        },
      });
      
      if (response.data) {
        setComparisonData(response.data);
      }
    } catch (error) {
      console.error('Failed to fetch comparison data:', error);
    }
  }, [api, accessToken, selectedSymbol]);

  const fetchConfig = useCallback(async () => {
    try {
      const response = await api.get('/ai/config', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      if (response.data) {
        setConfig(response.data);
        setAutoTradingEnabled(response.data.trading?.allowAutoTrading || false);
      }
    } catch (error) {
      console.error('Failed to fetch config:', error);
    }
  }, [api, accessToken]);

  const fetchAllData = useCallback(async () => {
    setIsLoading(true);
    try {
      await Promise.all([
        fetchModels(),
        fetchPredictions(),
        fetchMarketData(),
        fetchSentiment(),
        fetchMetrics(),
        fetchTrainingStatus(),
        fetchComparisonData(),
        fetchConfig(),
      ]);
    } catch (error) {
      console.error('Failed to fetch all data:', error);
      setShowToast({
        message: 'Failed to load AI data. Please refresh the page.',
        type: 'error',
      });
    } finally {
      setIsLoading(false);
    }
  }, [
    fetchModels,
    fetchPredictions,
    fetchMarketData,
    fetchSentiment,
    fetchMetrics,
    fetchTrainingStatus,
    fetchComparisonData,
    fetchConfig,
  ]);

  // ============================================
  // API Actions
  // ============================================
  const handleStartTraining = useCallback(async () => {
    if (!selectedModel) {
      setShowToast({
        message: 'Please select a model to train.',
        type: 'warning',
      });
      return;
    }

    setIsTraining(true);
    try {
      const response = await api.post(`/ai/models/${selectedModel.id}/train`, {
        epochs: config.training.epochs,
        batchSize: config.training.batchSize,
        learningRate: config.training.learningRate,
        validationSplit: config.training.validationSplit,
        earlyStopping: config.training.earlyStopping,
        useGPU: config.training.useGPU,
        symbol: selectedSymbol,
        timeframe: selectedTimeframe,
        saveCheckpoints: true,
        loggingFrequency: 10,
        lossFunction: 'mse',
        optimizer: 'adam',
        scheduler: 'reduce_on_plateau',
        schedulerFactor: 0.1,
        schedulerPatience: 5,
        minEpochs: 10,
        maxEpochs: config.training.epochs,
        gradientClipping: 1.0,
        weightDecay: 0.0001,
        dropout: 0.2,
        dataAugmentation: true,
      }, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      if (response.data) {
        setTrainingStatus({
          ...response.data,
          startedAt: new Date(response.data.startedAt || Date.now()),
        });
        setShowToast({
          message: `Training started for model: ${selectedModel.name}`,
          type: 'success',
        });
        
        // Start polling for training status
        const pollInterval = setInterval(() => {
          fetchTrainingStatus();
        }, 5000);
        
        // Store interval for cleanup
        (window as any).__trainingPollInterval = pollInterval;
      }
    } catch (error: any) {
      console.error('Failed to start training:', error);
      setShowToast({
        message: error.response?.data?.message || 'Failed to start training. Please try again.',
        type: 'error',
      });
    } finally {
      setIsTraining(false);
    }
  }, [api, accessToken, selectedModel, config, selectedSymbol, selectedTimeframe, fetchTrainingStatus]);

  const handleStopTraining = useCallback(async () => {
    if (!selectedModel) return;

    try {
      await api.post(`/ai/models/${selectedModel.id}/train/stop`, {}, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      setShowToast({
        message: `Training stopped for model: ${selectedModel.name}`,
        type: 'info',
      });
      
      // Clear polling interval
      if ((window as any).__trainingPollInterval) {
        clearInterval((window as any).__trainingPollInterval);
        delete (window as any).__trainingPollInterval;
      }
      
      await fetchTrainingStatus();
    } catch (error) {
      console.error('Failed to stop training:', error);
      setShowToast({
        message: 'Failed to stop training. Please try again.',
        type: 'error',
      });
    }
  }, [api, accessToken, selectedModel, fetchTrainingStatus]);

  const handleConfirmPrediction = useCallback(async (prediction: Prediction) => {
    if (!isAuthenticated) {
      setShowToast({
        message: 'Please login to execute trades.',
        type: 'warning',
      });
      return;
    }

    try {
      const response = await api.post('/trading/orders', {
        symbol: prediction.symbol,
        type: 'market',
        side: prediction.direction === 'up' ? 'buy' : 'sell',
        amount: config.trading.maxPositionSize * config.trading.riskPerTrade,
        stopLoss: prediction.stopLoss,
        takeProfit: prediction.takeProfit,
        confidence: prediction.confidence,
        modelId: prediction.modelId,
        predictionId: prediction.id,
        metadata: {
          strategy: 'ai_prediction',
          modelName: prediction.modelName,
          confidence: prediction.confidence,
          indicators: prediction.indicators,
        },
      }, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });

      if (response.data) {
        setShowToast({
          message: `✅ Trade executed! ${prediction.direction === 'up' ? '📈 Buy' : '📉 Sell'} ${prediction.symbol}`,
          type: 'success',
        });
        
        // Update prediction status
        setPredictions(prev => 
          prev.map(p => 
            p.id === prediction.id 
              ? { ...p, status: 'executed', executedAt: new Date() }
              : p
          )
        );
      }
    } catch (error: any) {
      console.error('Failed to execute trade:', error);
      setShowToast({
        message: error.response?.data?.message || 'Failed to execute trade. Please check your account.',
        type: 'error',
      });
    }
  }, [api, accessToken, config, isAuthenticated]);

  const handleUpdateConfig = useCallback(async (newConfig: Partial<AIConfig>) => {
    try {
      const response = await api.put('/ai/config', newConfig, {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
      });
      
      if (response.data) {
        setConfig(response.data);
        setShowToast({
          message: 'Configuration updated successfully',
          type: 'success',
        });
      }
    } catch (error) {
      console.error('Failed to update config:', error);
      setShowToast({
        message: 'Failed to update configuration',
        type: 'error',
      });
    }
  }, [api, accessToken]);

  const handleExportData = useCallback(async (format: 'csv' | 'json' = 'csv') => {
    try {
      const response = await api.get('/ai/export', {
        headers: {
          Authorization: `Bearer ${accessToken}`,
        },
        params: {
          modelId: selectedModel?.id,
          symbol: selectedSymbol,
          timeframe: selectedTimeframe,
          format: format,
          includePredictions: true,
          includeMetrics: true,
          includeTraining: true,
          startDate: new Date(Date.now() - 30 * 24 * 60 * 60 * 1000).toISOString(),
          endDate: new Date().toISOString(),
        },
        responseType: 'blob',
      });

      // Create download link
      const blob = new Blob([response.data], {
        type: format === 'csv' ? 'text/csv' : 'application/json',
      });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `ai-data-${selectedSymbol}-${Date.now()}.${format === 'csv' ? 'csv' : 'json'}`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      setShowToast({
        message: `Data exported successfully (${format.toUpperCase()})`,
        type: 'success',
      });
    } catch (error) {
      console.error('Failed to export data:', error);
      setShowToast({
        message: 'Failed to export data. Please try again.',
        type: 'error',
      });
    }
  }, [api, accessToken, selectedModel, selectedSymbol, selectedTimeframe]);

  // ============================================
  // Effects
  // ============================================
  useEffect(() => {
    fetchAllData();
  }, [fetchAllData]);

  useEffect(() => {
    if (isConnected) {
      subscribeToChannels();
    }
    
    return () => {
      if (wsCleanupRef.current) {
        wsCleanupRef.current();
      }
      if ((window as any).__trainingPollInterval) {
        clearInterval((window as any).__trainingPollInterval);
        delete (window as any).__trainingPollInterval;
      }
    };
  }, [isConnected, selectedSymbol, selectedModel, selectedTimeframe]);

  // Refresh data on symbol/model change
  useEffect(() => {
    if (selectedModel) {
      fetchPredictions();
      fetchMetrics();
      fetchTrainingStatus();
    }
  }, [selectedModel, selectedSymbol, selectedTimeframe, fetchPredictions, fetchMetrics, fetchTrainingStatus]);

  // Auto-refresh market data
  useEffect(() => {
    if (marketDataIntervalRef.current) {
      clearInterval(marketDataIntervalRef.current);
    }
    
    marketDataIntervalRef.current = setInterval(() => {
      fetchMarketData();
    }, 5000); // Refresh every 5 seconds
    
    return () => {
      if (marketDataIntervalRef.current) {
        clearInterval(marketDataIntervalRef.current);
      }
    };
  }, [fetchMarketData]);

  // ============================================
  // Memoized Computations
  // ============================================
  const filteredPredictions = useMemo(() => {
    return predictions.filter(p => {
      if (predictionFilters.minConfidence > 0 && p.confidence < predictionFilters.minConfidence) {
        return false;
      }
      if (predictionFilters.direction !== 'all' && p.direction !== predictionFilters.direction) {
        return false;
      }
      return true;
    });
  }, [predictions, predictionFilters]);

  const performanceMetrics = useMemo(() => {
    if (!metrics) return [];
    return [
      { 
        label: 'Accuracy', 
        value: formatPercentage(metrics.accuracy), 
        color: metrics.accuracy > 0.6 ? 'text-green-500' : metrics.accuracy > 0.4 ? 'text-yellow-500' : 'text-red-500',
        tooltip: 'Percentage of correct predictions',
      },
      { 
        label: 'Win Rate', 
        value: formatPercentage(metrics.winRate), 
        color: metrics.winRate > 0.55 ? 'text-green-500' : metrics.winRate > 0.45 ? 'text-yellow-500' : 'text-red-500',
        tooltip: 'Percentage of profitable trades',
      },
      { 
        label: 'Sharpe Ratio', 
        value: metrics.sharpeRatio.toFixed(2), 
        color: metrics.sharpeRatio > 1 ? 'text-green-500' : metrics.sharpeRatio > 0.5 ? 'text-yellow-500' : 'text-red-500',
        tooltip: 'Risk-adjusted return measure',
      },
      { 
        label: 'Profit Factor', 
        value: metrics.profitFactor.toFixed(2), 
        color: metrics.profitFactor > 1.5 ? 'text-green-500' : metrics.profitFactor > 1 ? 'text-yellow-500' : 'text-red-500',
        tooltip: 'Gross profit / Gross loss',
      },
      { 
        label: 'Max Drawdown', 
        value: formatPercentage(metrics.maxDrawdown), 
        color: metrics.maxDrawdown < 0.2 ? 'text-green-500' : metrics.maxDrawdown < 0.4 ? 'text-yellow-500' : 'text-red-500',
        tooltip: 'Maximum peak-to-trough decline',
      },
      { 
        label: 'Total Trades', 
        value: formatNumber(metrics.totalTrades), 
        color: 'text-gray-400',
        tooltip: 'Total number of trades executed',
      },
      { 
        label: 'Avg Confidence', 
        value: formatPercentage(metrics.averageConfidence || 0), 
        color: (metrics.averageConfidence || 0) > 0.7 ? 'text-green-500' : 'text-yellow-500',
        tooltip: 'Average prediction confidence',
      },
      { 
        label: 'Success Rate', 
        value: metrics.totalPredictions > 0 
          ? formatPercentage((metrics.successfulPredictions || 0) / metrics.totalPredictions) 
          : '0%', 
        color: 'text-blue-500',
        tooltip: 'Successful predictions / Total predictions',
      },
    ];
  }, [metrics]);

  const topPredictions = useMemo(() => {
    return filteredPredictions.slice(0, 5);
  }, [filteredPredictions]);

  const predictionStats = useMemo(() => {
    const total = filteredPredictions.length;
    const up = filteredPredictions.filter(p => p.direction === 'up').length;
    const down = filteredPredictions.filter(p => p.direction === 'down').length;
    const neutral = filteredPredictions.filter(p => p.direction === 'neutral').length;
    const avgConfidence = total > 0 
      ? filteredPredictions.reduce((sum, p) => sum + p.confidence, 0) / total 
      : 0;
    
    return { total, up, down, neutral, avgConfidence };
  }, [filteredPredictions]);

  // ============================================
  // Render
  // ============================================
  if (isLoading && modelsLoading && predictionsLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <div className="relative w-16 h-16 mx-auto mb-6">
            <div className="absolute inset-0 border-4 border-cyan-500/30 rounded-full"></div>
            <div className="absolute inset-0 border-4 border-t-cyan-500 rounded-full animate-spin"></div>
            <div className="absolute inset-2 bg-cyan-500/10 rounded-full animate-pulse"></div>
          </div>
          <p className="text-gray-400 text-lg font-medium">Loading AI Dashboard...</p>
          <p className="text-gray-500 text-sm mt-2">Connecting to AI services and fetching real-time data</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white p-4 md:p-6 lg:p-8">
      {/* ============================================ */}
      {/* HEADER */}
      {/* ============================================ */}
      <div className="flex flex-wrap items-center justify-between mb-8 gap-4">
        <div>
          <div className="flex items-center gap-3">
            <div className="text-3xl">🤖</div>
            <div>
              <h1 className="text-2xl md:text-3xl font-bold bg-gradient-to-r from-cyan-400 via-blue-400 to-purple-400 bg-clip-text text-transparent">
                NEXUS AI Trading Engine
              </h1>
              <p className="text-gray-400 text-sm mt-1 flex items-center gap-2">
                <span>Real-time AI predictions and trading signals</span>
                <Badge variant="outline" className="text-xs border-cyan-500 text-cyan-400">
                  v3.0.0
                </Badge>
              </p>
            </div>
          </div>
        </div>
        
        <div className="flex items-center gap-3 flex-wrap">
          {/* Connection Status */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded-lg border border-gray-700">
            <div className={cn(
              'w-2 h-2 rounded-full transition-all duration-500',
              isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
            )} />
            <span className="text-xs text-gray-400">
              {isConnected ? 'Live' : 'Disconnected'}
            </span>
          </div>
          
          {/* Auto Trading Switch */}
          <div className="flex items-center gap-2 px-3 py-1.5 bg-gray-800 rounded-lg border border-gray-700">
            <span className="text-xs text-gray-400">Auto Trade</span>
            <Switch
              checked={autoTradingEnabled}
              onCheckedChange={setAutoTradingEnabled}
              className="data-[state=checked]:bg-cyan-500"
            />
          </div>
          
          {/* Export Button */}
          <Button
            variant="outline"
            size="sm"
            onClick={() => handleExportData('csv')}
            className="border-gray-700 hover:border-cyan-500 hover:text-cyan-400 transition-colors"
          >
            <span className="mr-2">📊</span> Export Data
          </Button>
        </div>
      </div>

      {/* ============================================ */}
      {/* MAIN GRID */}
      {/* ============================================ */}
      <div className="grid grid-cols-12 gap-6">
        {/* ========================================== */}
        {/* LEFT COLUMN - Model Selection & Controls */}
        {/* ========================================== */}
        <div className="col-span-12 lg:col-span-3 space-y-6">
          {/* Model Selector */}
          <ModelSelector
            selectedModel={selectedModel}
            onModelChange={setSelectedModel}
            models={models}
            isLoading={modelsLoading}
            className="w-full"
          />

          {/* Training Controls */}
          <Card className="p-4 bg-gray-800 border-gray-700">
            <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
              <span className="text-cyan-400">⚡</span> Training Controls
            </h3>
            
            {trainingStatus && trainingStatus.status === 'running' ? (
              <div className="space-y-4">
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">Progress</span>
                  <span className="text-cyan-400 font-mono">{trainingStatus.progress.toFixed(1)}%</span>
                </div>
                <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
                  <motion.div
                    className="h-full bg-gradient-to-r from-cyan-500 via-blue-500 to-purple-500"
                    initial={{ width: '0%' }}
                    animate={{ width: `${trainingStatus.progress}%` }}
                    transition={{ duration: 0.5 }}
                  />
                </div>
                <div className="grid grid-cols-2 gap-2 text-xs text-gray-500">
                  <div>
                    <span>Epoch</span>
                    <div className="text-white font-mono">
                      {trainingStatus.epoch}/{trainingStatus.totalEpochs}
                    </div>
                  </div>
                  <div>
                    <span>Loss</span>
                    <div className="text-white font-mono">
                      {trainingStatus.loss?.toFixed(4) || 'N/A'}
                    </div>
                  </div>
                  <div>
                    <span>Accuracy</span>
                    <div className="text-white font-mono">
                      {trainingStatus.accuracy ? formatPercentage(trainingStatus.accuracy) : 'N/A'}
                    </div>
                  </div>
                  <div>
                    <span>Val. Loss</span>
                    <div className="text-white font-mono">
                      {trainingStatus.validationLoss?.toFixed(4) || 'N/A'}
                    </div>
                  </div>
                </div>
                <Button
                  variant="destructive"
                  size="sm"
                  onClick={handleStopTraining}
                  className="w-full bg-red-600 hover:bg-red-700 transition-colors"
                  disabled={isTraining}
                >
                  ⏹ Stop Training
                </Button>
              </div>
            ) : trainingStatus && trainingStatus.status === 'completed' ? (
              <div className="text-center py-4">
                <div className="text-3xl mb-2">✅</div>
                <p className="text-green-500 font-medium">Training Complete</p>
                <p className="text-sm text-gray-400 mt-1">
                  Final Accuracy: {trainingStatus.accuracy ? formatPercentage(trainingStatus.accuracy) : 'N/A'}
                </p>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleStartTraining}
                  className="w-full mt-4"
                >
                  🔄 Retrain Model
                </Button>
              </div>
            ) : (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Epochs</label>
                    <Input
                      type="number"
                      value={config.training.epochs}
                      onChange={(e) => setConfig({
                        ...config,
                        training: { ...config.training, epochs: parseInt(e.target.value) || 100 },
                      })}
                      className="w-full bg-gray-700 border-gray-600 text-white text-sm"
                      min={1}
                      max={10000}
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-400 block mb-1">Batch Size</label>
                    <Input
                      type="number"
                      value={config.training.batchSize}
                      onChange={(e) => setConfig({
                        ...config,
                        training: { ...config.training, batchSize: parseInt(e.target.value) || 64 },
                      })}
                      className="w-full bg-gray-700 border-gray-600 text-white text-sm"
                      min={1}
                      max={4096}
                    />
                  </div>
                </div>
                <div>
                  <label className="text-xs text-gray-400 block mb-1">Learning Rate</label>
                  <Input
                    type="number"
                    step="0.0001"
                    value={config.training.learningRate}
                    onChange={(e) => setConfig({
                      ...config,
                      training: { ...config.training, learningRate: parseFloat(e.target.value) || 0.001 },
                    })}
                    className="w-full bg-gray-700 border-gray-600 text-white text-sm"
                    min={0.00001}
                    max={0.1}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-gray-400">Use GPU</span>
                  <Switch
                    checked={config.training.useGPU}
                    onCheckedChange={(checked) => setConfig({
                      ...config,
                      training: { ...config.training, useGPU: checked },
                    })}
                    className="data-[state=checked]:bg-cyan-500"
                  />
                </div>
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleStartTraining}
                  isLoading={isTraining}
                  className="w-full bg-gradient-to-r from-cyan-500 to-blue-500 hover:from-cyan-600 hover:to-blue-600 transition-all"
                >
                  {isTraining ? 'Starting...' : '🚀 Start Training'}
                </Button>
              </div>
            )}
          </Card>

          {/* Model Performance */}
          {metrics && !metricsLoading && (
            <Card className="p-4 bg-gray-800 border-gray-700">
              <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
                <span className="text-purple-400">📈</span> Model Performance
              </h3>
              <div className="space-y-2">
                {performanceMetrics.map((metric, index) => (
                  <motion.div
                    key={index}
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: index * 0.05 }}
                    className="flex justify-between items-center text-sm group"
                  >
                    <span className="text-gray-400 group-hover:text-gray-300 transition-colors">
                      {metric.label}
                    </span>
                    <span className={cn('font-mono font-medium', metric.color)}>
                      {metric.value}
                    </span>
                  </motion.div>
                ))}
              </div>
            </Card>
          )}

          {/* Prediction Stats */}
          {filteredPredictions.length > 0 && (
            <Card className="p-4 bg-gray-800 border-gray-700">
              <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                <span className="text-yellow-400">📊</span> Prediction Stats
              </h3>
              <div className="grid grid-cols-3 gap-2 text-center">
                <div className="bg-green-500/10 rounded-lg p-2 border border-green-500/20">
                  <div className="text-green-500 text-lg font-bold">{predictionStats.up}</div>
                  <div className="text-xs text-gray-400">Buy</div>
                </div>
                <div className="bg-red-500/10 rounded-lg p-2 border border-red-500/20">
                  <div className="text-red-500 text-lg font-bold">{predictionStats.down}</div>
                  <div className="text-xs text-gray-400">Sell</div>
                </div>
                <div className="bg-gray-500/10 rounded-lg p-2 border border-gray-500/20">
                  <div className="text-gray-400 text-lg font-bold">{predictionStats.neutral}</div>
                  <div className="text-xs text-gray-400">Hold</div>
                </div>
                <div className="col-span-3 mt-2 flex justify-between text-xs text-gray-500">
                  <span>Total: {predictionStats.total}</span>
                  <span>Avg Confidence: {formatPercentage(predictionStats.avgConfidence)}</span>
                </div>
              </div>
            </Card>
          )}
        </div>

        {/* ========================================== */}
        {/* CENTER COLUMN - Predictions */}
        {/* ========================================== */}
        <div className="col-span-12 lg:col-span-6 space-y-6">
          {/* Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="bg-gray-800 border border-gray-700 rounded-lg p-1 w-full">
              <TabsTrigger
                value="predictions"
                className="flex-1 data-[state=active]:bg-cyan-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
              >
                <span className="mr-2">📈</span> Predictions
              </TabsTrigger>
              <TabsTrigger
                value="signals"
                className="flex-1 data-[state=active]:bg-purple-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
              >
                <span className="mr-2">🔔</span> Signals
              </TabsTrigger>
              <TabsTrigger
                value="history"
                className="flex-1 data-[state=active]:bg-gray-600 data-[state=active]:text-white data-[state=active]:shadow-lg transition-all"
              >
                <span className="mr-2">📊</span> History
              </TabsTrigger>
            </TabsList>

            <TabsContent value="predictions" className="mt-4 space-y-4">
              {/* Filters */}
              <div className="flex flex-wrap items-center gap-3 bg-gray-800/50 rounded-lg p-3 border border-gray-700">
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400">Symbol:</span>
                  <Select
                    value={selectedSymbol}
                    onValueChange={setSelectedSymbol}
                    className="w-32 bg-gray-700 border-gray-600"
                  >
                    {SUPPORTED_SYMBOLS.map(sym => (
                      <option key={sym.value} value={sym.value}>
                        {sym.label}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400">Timeframe:</span>
                  <Select
                    value={selectedTimeframe}
                    onValueChange={setSelectedTimeframe}
                    className="w-24 bg-gray-700 border-gray-600"
                  >
                    {TIME_FRAMES.map(tf => (
                      <option key={tf.value} value={tf.value}>
                        {tf.label}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-xs text-gray-400">Min Conf:</span>
                  <Input
                    type="number"
                    step="0.05"
                    min={0}
                    max={1}
                    value={predictionFilters.minConfidence}
                    onChange={(e) => setPredictionFilters({
                      ...predictionFilters,
                      minConfidence: parseFloat(e.target.value) || 0,
                    })}
                    className="w-16 bg-gray-700 border-gray-600 text-white text-sm"
                  />
                </div>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={fetchPredictions}
                  className="text-cyan-400 hover:text-cyan-300 hover:bg-cyan-500/10"
                >
                  🔄 Refresh
                </Button>
                <span className="text-xs text-gray-500 ml-auto">
                  {filteredPredictions.length} predictions
                </span>
              </div>

              {/* Current Prediction - Highlighted */}
              {currentPrediction && (
                <motion.div
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3 }}
                >
                  <PredictionCard
                    prediction={currentPrediction}
                    onConfirm={handleConfirmPrediction}
                    highlighted
                    className="border-2 border-cyan-500/30 bg-gradient-to-br from-cyan-500/5 to-purple-500/5"
                  />
                </motion.div>
              )}

              {/* Recent Predictions List */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold text-gray-400">Recent Predictions</h3>
                  {predictionsLoading && (
                    <Spinner size="sm" className="text-cyan-500" />
                  )}
                </div>
                {topPredictions.length > 0 ? (
                  <AnimatePresence>
                    {topPredictions.map((prediction, index) => (
                      <motion.div
                        key={prediction.id}
                        initial={{ opacity: 0, y: 10 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: index * 0.05 }}
                      >
                        <PredictionCard
                          prediction={prediction}
                          onConfirm={handleConfirmPrediction}
                          compact
                          className="hover:border-cyan-500/50 transition-colors"
                        />
                      </motion.div>
                    ))}
                  </AnimatePresence>
                ) : (
                  <div className="text-center py-8 text-gray-500">
                    <div className="text-4xl mb-3">📭</div>
                    <p>No predictions available</p>
                    <p className="text-sm">Waiting for AI model to generate predictions...</p>
                  </div>
                )}
              </div>
            </TabsContent>

            <TabsContent value="signals" className="mt-4">
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 text-center">
                <div className="text-5xl mb-4">📡</div>
                <h3 className="text-lg font-semibold text-white mb-2">Live Signal Feed</h3>
                <p className="text-gray-400">
                  Real-time trading signals from the AI model will appear here
                </p>
                <p className="text-sm text-gray-500 mt-2">
                  Connected to {isConnected ? '🟢' : '🔴'} AI WebSocket
                </p>
                {isConnected && (
                  <Badge variant="outline" className="mt-4 border-cyan-500 text-cyan-400">
                    Live Streaming Active
                  </Badge>
                )}
              </div>
            </TabsContent>

            <TabsContent value="history" className="mt-4">
              <div className="bg-gray-800 rounded-lg border border-gray-700 p-6 text-center">
                <div className="text-5xl mb-4">📊</div>
                <h3 className="text-lg font-semibold text-white mb-2">Prediction History</h3>
                <p className="text-gray-400">
                  Historical performance and prediction accuracy
                </p>
                <div className="grid grid-cols-3 gap-4 mt-6 max-w-2xl mx-auto">
                  <div className="bg-gray-700/50 rounded-lg p-4">
                    <div className="text-2xl text-cyan-400 font-bold">
                      {predictionsHistory.length}
                    </div>
                    <div className="text-xs text-gray-500">Total Predictions</div>
                  </div>
                  <div className="bg-gray-700/50 rounded-lg p-4">
                    <div className="text-2xl text-green-400 font-bold">
                      {metrics?.successfulPredictions || 0}
                    </div>
                    <div className="text-xs text-gray-500">Successful</div>
                  </div>
                  <div className="bg-gray-700/50 rounded-lg p-4">
                    <div className="text-2xl text-purple-400 font-bold">
                      {metrics?.accuracy ? formatPercentage(metrics.accuracy) : 'N/A'}
                    </div>
                    <div className="text-xs text-gray-500">Accuracy</div>
                  </div>
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </div>

        {/* ========================================== */}
        {/* RIGHT COLUMN - Sentiment & Market Context */}
        {/* ========================================== */}
        <div className="col-span-12 lg:col-span-3 space-y-6">
          {/* Sentiment Analysis */}
          {sentiment ? (
            <SentimentIndicator
              data={sentiment}
              isLoading={sentimentLoading}
              className="bg-gray-800 border-gray-700"
            />
          ) : (
            <Card className="p-4 bg-gray-800 border-gray-700">
              <div className="text-center py-8 text-gray-500">
                <div className="text-4xl mb-3">🔍</div>
                <p>No sentiment data available</p>
                <p className="text-sm">Waiting for sentiment analysis...</p>
              </div>
            </Card>
          )}

          {/* Market Data */}
          <Card className="p-4 bg-gray-800 border-gray-700">
            <h3 className="text-sm font-semibold text-gray-300 mb-4 flex items-center gap-2">
              <span className="text-blue-400">📊</span> Market Data
            </h3>
            {marketData ? (
              <div className="space-y-3">
                <div className="flex justify-between items-center">
                  <span className="text-gray-400 text-sm">{marketData.symbol}</span>
                  <div className="text-right">
                    <div className="text-lg font-mono font-semibold text-white">
                      {formatCurrency(marketData.price)}
                    </div>
                    <div className={cn(
                      'text-xs font-medium',
                      marketData.changePercent24h >= 0 ? 'text-green-500' : 'text-red-500'
                    )}>
                      {marketData.changePercent24h >= 0 ? '▲' : '▼'} {formatPercentage(Math.abs(marketData.changePercent24h))}
                    </div>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <div className="text-xs text-gray-500">24h High</div>
                    <div className="font-mono text-white">{formatCurrency(marketData.high24h)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">24h Low</div>
                    <div className="font-mono text-white">{formatCurrency(marketData.low24h)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">Volume</div>
                    <div className="font-mono text-white">{formatNumber(marketData.volume)}</div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-500">Spread</div>
                    <div className="font-mono text-white">{formatCurrency(marketData.spread)}</div>
                  </div>
                </div>
                <div className="flex justify-between text-xs text-gray-500 pt-2 border-t border-gray-700">
                  <span>Bid: {formatCurrency(marketData.bid)}</span>
                  <span>Ask: {formatCurrency(marketData.ask)}</span>
                </div>
              </div>
            ) : (
              <div className="text-center py-4 text-gray-500">
                <Spinner size="sm" className="mx-auto mb-2" />
                <p className="text-sm">Loading market data...</p>
              </div>
            )}
          </Card>

          {/* Quick Actions */}
          <Card className="p-4 bg-gray-800 border-gray-700">
            <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
              <span className="text-yellow-400">⚡</span> Quick Actions
            </h3>
            <div className="grid grid-cols-2 gap-2">
              {SUPPORTED_SYMBOLS.slice(0, 4).map((sym) => (
                <Button
                  key={sym.value}
                  variant="outline"
                  size="sm"
                  onClick={() => setSelectedSymbol(sym.value)}
                  className={cn(
                    'border-gray-700 hover:border-cyan-500 justify-start text-sm transition-all',
                    selectedSymbol === sym.value && 'border-cyan-500 bg-cyan-500/10'
                  )}
                >
                  {sym.icon} {sym.label}
                </Button>
              ))}
            </div>
            <div className="mt-3 pt-3 border-t border-gray-700 grid grid-cols-2 gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={fetchAllData}
                className="text-gray-400 hover:text-white hover:bg-gray-700"
              >
                🔄 Refresh All
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => handleExportData('json')}
                className="text-gray-400 hover:text-white hover:bg-gray-700"
              >
                📥 Export JSON
              </Button>
            </div>
          </Card>

          {/* Model Comparison */}
          {comparisonData && (
            <Card className="p-4 bg-gray-800 border-gray-700">
              <h3 className="text-sm font-semibold text-gray-300 mb-3 flex items-center gap-2">
                <span className="text-purple-400">🏆</span> Model Comparison
              </h3>
              <div className="space-y-2">
                {comparisonData.models?.slice(0, 3).map((model: any, index: number) => (
                  <div key={index} className="flex items-center justify-between text-sm">
                    <span className="text-gray-400">{model.name}</span>
                    <div className="flex items-center gap-3">
                      <span className="text-cyan-400">{formatPercentage(model.accuracy)}</span>
                      <span className="text-yellow-400">{model.sharpe?.toFixed(2)}</span>
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>
      </div>

      {/* ============================================ */}
      {/* TOAST NOTIFICATIONS */}
      {/* ============================================ */}
      <AnimatePresence>
        {showToast && (
          <Toast
            message={showToast.message}
            type={showToast.type}
            onClose={() => setShowToast(null)}
            className="fixed bottom-4 right-4 z-50 max-w-md"
            duration={5000}
          />
        )}
      </AnimatePresence>
    </div>
  );
}

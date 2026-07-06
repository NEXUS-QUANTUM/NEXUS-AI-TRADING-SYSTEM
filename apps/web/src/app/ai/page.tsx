/**
 * NEXUS AI TRADING SYSTEM - AI Dashboard Page
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This page provides the AI trading interface including:
 * - AI model selection and configuration
 * - Real-time predictions and signals
 * - Model performance metrics
 * - Sentiment analysis
 * - Training controls
 */

'use client';

import { useEffect, useState, useCallback, useMemo } from 'react';
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

// Types
import type {
  AIModel,
  Prediction,
  ModelMetrics,
  SentimentData,
  TrainingStatus,
  AIConfig,
} from '@/types/ai';

// Constants
import { AI_MODELS, DEFAULT_AI_CONFIG, TIME_FRAMES } from '@/constants/ai';
import { WEBSOCKET_EVENTS } from '@/constants/websocket';

// Hooks
import { useModelMetrics } from '@/hooks/useModelMetrics';
import { usePredictions } from '@/hooks/usePredictions';

// Utils
import { formatCurrency, formatPercentage } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

export default function AIPage() {
  // Authentication
  const { user, isAuthenticated } = useAuth();
  
  // API client
  const api = useApi();
  
  // State
  const [selectedModel, setSelectedModel] = useState<AIModel>(AI_MODELS[0]);
  const [selectedSymbol, setSelectedSymbol] = useState<string>('BTC-USD');
  const [selectedTimeframe, setSelectedTimeframe] = useState<string>('1h');
  const [predictions, setPredictions] = useState<Prediction[]>([]);
  const [currentPrediction, setCurrentPrediction] = useState<Prediction | null>(null);
  const [sentiment, setSentiment] = useState<SentimentData | null>(null);
  const [metrics, setMetrics] = useState<ModelMetrics | null>(null);
  const [trainingStatus, setTrainingStatus] = useState<TrainingStatus | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isTraining, setIsTraining] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<string>('predictions');
  const [showToast, setShowToast] = useState<{ message: string; type: 'success' | 'error' | 'info' } | null>(null);
  const [config, setConfig] = useState<AIConfig>(DEFAULT_AI_CONFIG);

  // Custom hooks
  const { metrics: modelMetrics, loading: metricsLoading, refresh: refreshMetrics } = useModelMetrics(selectedModel.id);
  const { predictions: livePredictions, loading: predictionsLoading, subscribe } = usePredictions(selectedSymbol, selectedModel.id);

  // WebSocket connection for real-time data
  const { 
    isConnected, 
    sendMessage, 
    subscribe: wsSubscribe,
    unsubscribe: wsUnsubscribe,
    messages 
  } = useWebSocket({
    url: `${process.env.NEXT_PUBLIC_WS_URL}/ai`,
    autoConnect: true,
    onMessage: handleWebSocketMessage,
    onError: handleWebSocketError,
  });

  // ============================================
  // WebSocket Handlers
  // ============================================
  function handleWebSocketMessage(event: MessageEvent) {
    try {
      const data = JSON.parse(event.data);
      
      switch (data.event) {
        case WEBSOCKET_EVENTS.AI_PREDICTION:
          handlePredictionUpdate(data.data);
          break;
        case WEBSOCKET_EVENTS.AI_SENTIMENT:
          handleSentimentUpdate(data.data);
          break;
        case WEBSOCKET_EVENTS.AI_METRICS:
          handleMetricsUpdate(data.data);
          break;
        case WEBSOCKET_EVENTS.AI_TRAINING_STATUS:
          handleTrainingStatusUpdate(data.data);
          break;
        case WEBSOCKET_EVENTS.AI_ERROR:
          handleAIError(data.data);
          break;
        default:
          break;
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  }

  function handleWebSocketError(error: Event) {
    console.error('WebSocket error:', error);
    setShowToast({
      message: 'Connection to AI service lost. Attempting to reconnect...',
      type: 'error',
    });
  }

  function handlePredictionUpdate(data: any) {
    const newPrediction: Prediction = {
      id: data.id || `pred-${Date.now()}`,
      symbol: data.symbol,
      modelId: data.modelId,
      timestamp: new Date(data.timestamp || Date.now()),
      price: data.price,
      predictedPrice: data.predictedPrice,
      confidence: data.confidence,
      direction: data.direction,
      signal: data.signal,
      stopLoss: data.stopLoss,
      takeProfit: data.takeProfit,
      riskRewardRatio: data.riskRewardRatio,
      indicators: data.indicators,
      metadata: data.metadata,
    };

    setCurrentPrediction(newPrediction);
    setPredictions(prev => [newPrediction, ...prev].slice(0, 100));
  }

  function handleSentimentUpdate(data: any) {
    setSentiment({
      overall: data.overall,
      score: data.score,
      bullish: data.bullish,
      bearish: data.bearish,
      neutral: data.neutral,
      sources: data.sources,
      lastUpdated: new Date(data.lastUpdated || Date.now()),
    });
  }

  function handleMetricsUpdate(data: any) {
    setMetrics({
      accuracy: data.accuracy,
      precision: data.precision,
      recall: data.recall,
      f1Score: data.f1Score,
      sharpeRatio: data.sharpeRatio,
      winRate: data.winRate,
      profitFactor: data.profitFactor,
      maxDrawdown: data.maxDrawdown,
      totalTrades: data.totalTrades,
      lastUpdated: new Date(data.lastUpdated || Date.now()),
    });
  }

  function handleTrainingStatusUpdate(data: any) {
    setTrainingStatus({
      status: data.status,
      progress: data.progress,
      epoch: data.epoch,
      totalEpochs: data.totalEpochs,
      loss: data.loss,
      accuracy: data.accuracy,
      metrics: data.metrics,
      startedAt: data.startedAt ? new Date(data.startedAt) : undefined,
      completedAt: data.completedAt ? new Date(data.completedAt) : undefined,
      error: data.error,
    });
  }

  function handleAIError(data: any) {
    setShowToast({
      message: data.message || 'AI service error occurred',
      type: 'error',
    });
  }

  // ============================================
  // API Calls
  // ============================================
  const fetchInitialData = useCallback(async () => {
    setIsLoading(true);
    try {
      // Fetch current predictions
      const predictionsResponse = await api.get('/ai/predictions', {
        params: {
          symbol: selectedSymbol,
          modelId: selectedModel.id,
          limit: 20,
        },
      });
      if (predictionsResponse.data) {
        setPredictions(predictionsResponse.data);
        if (predictionsResponse.data.length > 0) {
          setCurrentPrediction(predictionsResponse.data[0]);
        }
      }

      // Fetch sentiment data
      const sentimentResponse = await api.get('/ai/sentiment', {
        params: { symbol: selectedSymbol },
      });
      if (sentimentResponse.data) {
        setSentiment(sentimentResponse.data);
      }

      // Fetch model metrics
      const metricsResponse = await api.get(`/ai/models/${selectedModel.id}/metrics`);
      if (metricsResponse.data) {
        setMetrics(metricsResponse.data);
      }

      // Fetch training status
      const trainingResponse = await api.get(`/ai/models/${selectedModel.id}/training/status`);
      if (trainingResponse.data) {
        setTrainingStatus(trainingResponse.data);
      }

      // Fetch AI config
      const configResponse = await api.get('/ai/config');
      if (configResponse.data) {
        setConfig(configResponse.data);
      }
    } catch (error) {
      console.error('Failed to fetch AI data:', error);
      setShowToast({
        message: 'Failed to load AI data. Please refresh the page.',
        type: 'error',
      });
    } finally {
      setIsLoading(false);
    }
  }, [api, selectedSymbol, selectedModel.id]);

  // ============================================
  // WebSocket Subscriptions
  // ============================================
  useEffect(() => {
    if (isConnected) {
      // Subscribe to real-time predictions
      wsSubscribe({
        event: WEBSOCKET_EVENTS.SUBSCRIBE,
        channel: 'ai_predictions',
        params: {
          symbol: selectedSymbol,
          modelId: selectedModel.id,
          timeframe: selectedTimeframe,
        },
      });

      // Subscribe to sentiment updates
      wsSubscribe({
        event: WEBSOCKET_EVENTS.SUBSCRIBE,
        channel: 'ai_sentiment',
        params: { symbol: selectedSymbol },
      });

      // Subscribe to model metrics
      wsSubscribe({
        event: WEBSOCKET_EVENTS.SUBSCRIBE,
        channel: 'ai_metrics',
        params: { modelId: selectedModel.id },
      });
    }

    return () => {
      if (isConnected) {
        wsUnsubscribe({
          event: WEBSOCKET_EVENTS.UNSUBSCRIBE,
          channel: 'ai_predictions',
        });
        wsUnsubscribe({
          event: WEBSOCKET_EVENTS.UNSUBSCRIBE,
          channel: 'ai_sentiment',
        });
        wsUnsubscribe({
          event: WEBSOCKET_EVENTS.UNSUBSCRIBE,
          channel: 'ai_metrics',
        });
      }
    };
  }, [isConnected, selectedSymbol, selectedModel.id, selectedTimeframe, wsSubscribe, wsUnsubscribe]);

  // ============================================
  // Effects
  // ============================================
  useEffect(() => {
    fetchInitialData();
    refreshMetrics();
  }, [fetchInitialData, refreshMetrics]);

  // ============================================
  // Handlers
  // ============================================
  const handleModelChange = useCallback((model: AIModel) => {
    setSelectedModel(model);
    setShowToast({
      message: `Switched to model: ${model.name}`,
      type: 'info',
    });
  }, []);

  const handleSymbolChange = useCallback((symbol: string) => {
    setSelectedSymbol(symbol);
  }, []);

  const handleTimeframeChange = useCallback((timeframe: string) => {
    setSelectedTimeframe(timeframe);
  }, []);

  const handleStartTraining = useCallback(async () => {
    setIsTraining(true);
    try {
      const response = await api.post(`/ai/models/${selectedModel.id}/train`, {
        epochs: config.training.epochs,
        batchSize: config.training.batchSize,
        learningRate: config.training.learningRate,
        validationSplit: config.training.validationSplit,
        earlyStopping: config.training.earlyStopping,
        useGPU: config.training.useGPU,
      });

      if (response.data) {
        setShowToast({
          message: `Training started for model: ${selectedModel.name}`,
          type: 'success',
        });
        setTrainingStatus(response.data);
      }
    } catch (error) {
      console.error('Failed to start training:', error);
      setShowToast({
        message: 'Failed to start training. Please try again.',
        type: 'error',
      });
    } finally {
      setIsTraining(false);
    }
  }, [api, selectedModel, config]);

  const handleStopTraining = useCallback(async () => {
    try {
      await api.post(`/ai/models/${selectedModel.id}/train/stop`);
      setShowToast({
        message: `Training stopped for model: ${selectedModel.name}`,
        type: 'info',
      });
    } catch (error) {
      console.error('Failed to stop training:', error);
      setShowToast({
        message: 'Failed to stop training. Please try again.',
        type: 'error',
      });
    }
  }, [api, selectedModel]);

  const handlePredictionConfirm = useCallback(async (prediction: Prediction) => {
    if (!user) {
      setShowToast({
        message: 'Please login to confirm predictions.',
        type: 'error',
      });
      return;
    }

    try {
      await api.post('/trading/orders', {
        symbol: prediction.symbol,
        type: 'market',
        side: prediction.direction === 'up' ? 'buy' : 'sell',
        amount: config.trading.maxPositionSize * 0.01, // 1% of max position
        stopLoss: prediction.stopLoss,
        takeProfit: prediction.takeProfit,
        metadata: {
          predictionId: prediction.id,
          modelId: prediction.modelId,
          confidence: prediction.confidence,
        },
      });

      setShowToast({
        message: `Prediction confirmed! ${prediction.direction === 'up' ? '📈 Buy' : '📉 Sell'} signal executed.`,
        type: 'success',
      });
    } catch (error) {
      console.error('Failed to execute trade:', error);
      setShowToast({
        message: 'Failed to execute trade. Please check your account.',
        type: 'error',
      });
    }
  }, [api, user, config]);

  const handleExportData = useCallback(async () => {
    try {
      const response = await api.get('/ai/export', {
        params: {
          modelId: selectedModel.id,
          symbol: selectedSymbol,
          format: 'csv',
        },
        responseType: 'blob',
      });

      // Create download link
      const url = window.URL.createObjectURL(new Blob([response.data]));
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', `ai-data-${selectedSymbol}-${Date.now()}.csv`);
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);

      setShowToast({
        message: 'Data exported successfully!',
        type: 'success',
      });
    } catch (error) {
      console.error('Failed to export data:', error);
      setShowToast({
        message: 'Failed to export data. Please try again.',
        type: 'error',
      });
    }
  }, [api, selectedModel, selectedSymbol]);

  // ============================================
  // Memoized Computations
  // ============================================
  const performanceMetrics = useMemo(() => {
    if (!metrics) return [];
    return [
      { label: 'Accuracy', value: formatPercentage(metrics.accuracy), color: 'text-green-500' },
      { label: 'Win Rate', value: formatPercentage(metrics.winRate), color: 'text-blue-500' },
      { label: 'Sharpe Ratio', value: metrics.sharpeRatio.toFixed(2), color: 'text-purple-500' },
      { label: 'Profit Factor', value: metrics.profitFactor.toFixed(2), color: 'text-yellow-500' },
      { label: 'Max Drawdown', value: formatPercentage(metrics.maxDrawdown), color: 'text-red-500' },
      { label: 'Total Trades', value: metrics.totalTrades.toString(), color: 'text-gray-400' },
    ];
  }, [metrics]);

  const topPredictions = useMemo(() => {
    return predictions.slice(0, 5);
  }, [predictions]);

  // ============================================
  // Render
  // ============================================
  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen bg-gray-900">
        <div className="text-center">
          <Spinner size="lg" className="mx-auto mb-4" />
          <p className="text-gray-400">Loading AI Dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-900 text-white p-6">
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between mb-8">
        <div>
          <h1 className="text-3xl font-bold bg-gradient-to-r from-cyan-400 to-purple-400 bg-clip-text text-transparent">
            🤖 AI Trading Engine
          </h1>
          <p className="text-gray-400 mt-1">
            Real-time AI predictions and trading signals
          </p>
        </div>
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className={cn(
              'w-2 h-2 rounded-full',
              isConnected ? 'bg-green-500 animate-pulse' : 'bg-red-500'
            )} />
            <span className="text-sm text-gray-400">
              {isConnected ? 'Live' : 'Disconnected'}
            </span>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={handleExportData}
            className="border-gray-700 hover:border-cyan-500"
          >
            📊 Export Data
          </Button>
        </div>
      </div>

      {/* Main Grid */}
      <div className="grid grid-cols-12 gap-6">
        {/* Left Column - Model Selection and Controls */}
        <div className="col-span-12 lg:col-span-3 space-y-6">
          {/* Model Selector */}
          <ModelSelector
            selectedModel={selectedModel}
            onModelChange={handleModelChange}
            models={AI_MODELS}
            className="w-full"
          />

          {/* Training Controls */}
          <Card className="p-4 bg-gray-800 border-gray-700">
            <h3 className="text-sm font-semibold text-gray-300 mb-3">Training Controls</h3>
            <div className="space-y-3">
              {trainingStatus && trainingStatus.status === 'running' ? (
                <>
                  <div className="flex justify-between text-sm">
                    <span className="text-gray-400">Progress</span>
                    <span className="text-cyan-400">{trainingStatus.progress}%</span>
                  </div>
                  <div className="w-full h-2 bg-gray-700 rounded-full overflow-hidden">
                    <motion.div
                      className="h-full bg-gradient-to-r from-cyan-500 to-purple-500"
                      initial={{ width: '0%' }}
                      animate={{ width: `${trainingStatus.progress}%` }}
                      transition={{ duration: 0.5 }}
                    />
                  </div>
                  <div className="flex justify-between text-xs text-gray-500">
                    <span>Epoch {trainingStatus.epoch}/{trainingStatus.totalEpochs}</span>
                    <span>Loss: {trainingStatus.loss?.toFixed(4)}</span>
                  </div>
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleStopTraining}
                    className="w-full bg-red-600 hover:bg-red-700"
                  >
                    ⏹ Stop Training
                  </Button>
                </>
              ) : (
                <Button
                  variant="primary"
                  size="sm"
                  onClick={handleStartTraining}
                  isLoading={isTraining}
                  className="w-full"
                >
                  {isTraining ? 'Starting...' : '🚀 Start Training'}
                </Button>
              )}
            </div>
          </Card>

          {/* Model Performance */}
          {metrics && (
            <Card className="p-4 bg-gray-800 border-gray-700">
              <h3 className="text-sm font-semibold text-gray-300 mb-3">Model Performance</h3>
              <div className="space-y-2">
                {performanceMetrics.map((metric, index) => (
                  <div key={index} className="flex justify-between text-sm">
                    <span className="text-gray-400">{metric.label}</span>
                    <span className={metric.color}>{metric.value}</span>
                  </div>
                ))}
              </div>
            </Card>
          )}
        </div>

        {/* Center Column - Predictions */}
        <div className="col-span-12 lg:col-span-6 space-y-6">
          {/* Tabs */}
          <Tabs value={activeTab} onValueChange={setActiveTab}>
            <TabsList className="bg-gray-800 border border-gray-700 rounded-lg p-1">
              <TabsTrigger
                value="predictions"
                className="data-[state=active]:bg-cyan-600 data-[state=active]:text-white"
              >
                📈 Predictions
              </TabsTrigger>
              <TabsTrigger
                value="signals"
                className="data-[state=active]:bg-purple-600 data-[state=active]:text-white"
              >
                🔔 Signals
              </TabsTrigger>
              <TabsTrigger
                value="history"
                className="data-[state=active]:bg-gray-600 data-[state=active]:text-white"
              >
                📊 History
              </TabsTrigger>
            </TabsList>

            <TabsContent value="predictions" className="mt-4 space-y-4">
              {/* Current Prediction */}
              {currentPrediction && (
                <PredictionCard
                  prediction={currentPrediction}
                  onConfirm={handlePredictionConfirm}
                  className="bg-gray-800 border border-gray-700"
                />
              )}

              {/* Recent Predictions */}
              <div className="space-y-3">
                <h3 className="text-sm font-semibold text-gray-400">Recent Predictions</h3>
                {topPredictions.map((prediction) => (
                  <PredictionCard
                    key={prediction.id}
                    prediction={prediction}
                    compact
                    onConfirm={handlePredictionConfirm}
                    className="bg-gray-800/50 border border-gray-700"
                  />
                ))}
              </div>
            </TabsContent>

            <TabsContent value="signals" className="mt-4">
              <div className="text-center py-12 text-gray-500">
                <div className="text-4xl mb-4">📡</div>
                <p>Live signal feed coming soon...</p>
                <p className="text-sm">AI signals will appear here in real-time</p>
              </div>
            </TabsContent>

            <TabsContent value="history" className="mt-4">
              <div className="text-center py-12 text-gray-500">
                <div className="text-4xl mb-4">📊</div>
                <p>Prediction history available in dashboard</p>
                <p className="text-sm">View detailed performance analytics</p>
              </div>
            </TabsContent>
          </Tabs>
        </div>

        {/* Right Column - Sentiment & Market Context */}
        <div className="col-span-12 lg:col-span-3 space-y-6">
          {/* Sentiment Analysis */}
          {sentiment && (
            <SentimentIndicator
              data={sentiment}
              className="bg-gray-800 border border-gray-700"
            />
          )}

          {/* Market Context */}
          <Card className="p-4 bg-gray-800 border-gray-700">
            <h3 className="text-sm font-semibold text-gray-300 mb-3">Market Context</h3>
            <div className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Symbol</span>
                <span className="font-mono text-cyan-400">{selectedSymbol}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Timeframe</span>
                <span className="text-white">{selectedTimeframe}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Model</span>
                <span className="text-purple-400">{selectedModel.name}</span>
              </div>
              <div className="flex justify-between text-sm">
                <span className="text-gray-400">Confidence</span>
                <span className="text-green-400">
                  {currentPrediction ? formatPercentage(currentPrediction.confidence) : 'N/A'}
                </span>
              </div>
              {currentPrediction && (
                <div className="flex justify-between text-sm">
                  <span className="text-gray-400">Signal</span>
                  <span className={cn(
                    'font-semibold',
                    currentPrediction.direction === 'up' ? 'text-green-500' : 'text-red-500'
                  )}>
                    {currentPrediction.direction === 'up' ? '🟢 BUY' : '🔴 SELL'}
                  </span>
                </div>
              )}
            </div>
          </Card>

          {/* Quick Actions */}
          <Card className="p-4 bg-gray-800 border-gray-700">
            <h3 className="text-sm font-semibold text-gray-300 mb-3">Quick Actions</h3>
            <div className="space-y-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleSymbolChange('BTC-USD')}
                className="w-full border-gray-700 hover:border-cyan-500 justify-start"
              >
                ₿ Bitcoin
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleSymbolChange('ETH-USD')}
                className="w-full border-gray-700 hover:border-cyan-500 justify-start"
              >
                ⟠ Ethereum
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleSymbolChange('SOL-USD')}
                className="w-full border-gray-700 hover:border-cyan-500 justify-start"
              >
                ◎ Solana
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={() => handleSymbolChange('EUR-USD')}
                className="w-full border-gray-700 hover:border-cyan-500 justify-start"
              >
                💱 EUR/USD
              </Button>
            </div>
          </Card>
        </div>
      </div>

      {/* Toast Notifications */}
      <AnimatePresence>
        {showToast && (
          <Toast
            message={showToast.message}
            type={showToast.type}
            onClose={() => setShowToast(null)}
            className="fixed bottom-4 right-4 z-50"
          />
        )}
      </AnimatePresence>
    </div>
  );
}

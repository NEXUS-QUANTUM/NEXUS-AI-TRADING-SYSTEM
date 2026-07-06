/**
 * NEXUS AI Trading System - AI Types
 * Copyright © 2026 NEXUS QUANTUM LTD
 */

export interface AIModel {
  id: string;
  name: string;
  description: string;
  type: 'ensemble' | 'lstm' | 'transformer' | 'xgboost' | 'lightgbm' | 'custom';
  status: 'active' | 'training' | 'idle' | 'error' | 'stopped' | 'completed';
  version: string;
  createdAt: Date;
  updatedAt: Date;
  config: Record<string, any>;
  accuracy?: number;
  totalPredictions?: number;
  lastPrediction?: Date;
  trainingData?: {
    size: number;
    features: string[];
    lastUpdated?: Date;
  };
  hyperparameters?: Record<string, any>;
}

export interface Prediction {
  id: string;
  symbol: string;
  modelId: string;
  modelName: string;
  modelVersion: string;
  timestamp: Date;
  price: number;
  predictedPrice: number;
  confidence: number;
  direction: 'up' | 'down' | 'neutral';
  signal: 'buy' | 'sell' | 'hold';
  stopLoss?: number;
  takeProfit?: number;
  riskRewardRatio?: number;
  predictionTime?: number;
  status?: 'pending' | 'executed' | 'expired' | 'cancelled';
  executedAt?: Date;
  indicators: {
    rsi: number;
    macd: number;
    bollingerUpper: number;
    bollingerMiddle: number;
    bollingerLower: number;
    volatility: number;
    volume: number;
    trend: 'bullish' | 'bearish' | 'neutral';
    movingAverage50: number;
    movingAverage200: number;
    stochasticK: number;
    stochasticD: number;
    adx: number;
    obv: number;
    vwap: number;
  };
  metadata: Record<string, any>;
}

export interface ModelMetrics {
  accuracy: number;
  precision: number;
  recall: number;
  f1Score: number;
  sharpeRatio: number;
  winRate: number;
  profitFactor: number;
  maxDrawdown: number;
  totalTrades: number;
  lastUpdated: Date;
  dailyAccuracy: number[];
  weeklyAccuracy: number[];
  monthlyAccuracy: number[];
  averageConfidence: number;
  totalPredictions: number;
  successfulPredictions: number;
}

export interface SentimentData {
  overall: 'bullish' | 'bearish' | 'neutral';
  score: number;
  bullish: number;
  bearish: number;
  neutral: number;
  sources: SentimentSource[];
  lastUpdated: Date;
  historical: SentimentHistoryPoint[];
  volatility: number;
  socialMention: number;
  newsMention: number;
}

export interface SentimentSource {
  name: string;
  score: number;
  weight: number;
  data: Record<string, any>;
  mentionCount?: number;
  sentimentScore?: number;
}

export interface SentimentHistoryPoint {
  timestamp: Date;
  score: number;
  bullish: number;
  bearish: number;
  neutral: number;
}

export interface TrainingStatus {
  status: 'idle' | 'running' | 'completed' | 'failed' | 'stopped';
  progress: number;
  epoch: number;
  totalEpochs: number;
  loss?: number;
  accuracy?: number;
  metrics: Record<string, number>;
  startedAt?: Date;
  completedAt?: Date;
  error?: string;
  currentStep?: number;
  totalSteps?: number;
  learningRate?: number;
  batchSize?: number;
  validationLoss?: number;
  validationAccuracy?: number;
}

export interface AIConfig {
  training: {
    epochs: number;
    batchSize: number;
    learningRate: number;
    validationSplit: number;
    earlyStopping: boolean;
    useGPU: boolean;
  };
  inference: {
    confidenceThreshold: number;
    maxPredictions: number;
    cacheTTL: number;
  };
  trading: {
    maxPositionSize: number;
    riskPerTrade: number;
    allowAutoTrading: boolean;
  };
}

export interface MarketData {
  symbol: string;
  price: number;
  bid: number;
  ask: number;
  volume: number;
  high24h: number;
  low24h: number;
  open24h: number;
  close24h: number;
  change24h: number;
  changePercent24h: number;
  timestamp: Date;
  orderBook: {
    bids: [number, number][];
    asks: [number, number][];
  };
  lastTrades: {
    price: number;
    volume: number;
    timestamp: Date;
    side: 'buy' | 'sell';
  }[];
  vwap: number;
  volumeWeighted: number;
  spread: number;
}

export interface ModelPerformance {
  modelId: string;
  modelName: string;
  timestamp: Date;
  returns: number;
  sharpe: number;
  volatility: number;
  maxDrawdown: number;
  winRate: number;
  totalTrades: number;
  profitFactor: number;
  dailyReturns: number[];
  cumulativeReturns: number[];
}

export interface PredictionHistory {
  id: string;
  symbol: string;
  timestamp: Date;
  price: number;
  predictedPrice: number;
  confidence: number;
  direction: 'up' | 'down' | 'neutral';
  signal: 'buy' | 'sell' | 'hold';
  actualPrice: number;
  success: boolean;
  executed?: boolean;
  profitLoss?: number;
}

export interface ModelComparison {
  models: {
    id: string;
    name: string;
    accuracy: number;
    sharpe: number;
    winRate: number;
    maxDrawdown: number;
  }[];
  bestModel: string;
  timestamp: Date;
}

export interface TrainingHistoryPoint {
  epoch: number;
  loss: number;
  accuracy: number;
  validationLoss: number;
  validationAccuracy: number;
  timestamp: Date;
  learningRate: number;
}

/**
 * NEXUS AI TRADING SYSTEM - PredictionCard Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This component provides AI prediction display functionality including:
 * - Prediction visualization with direction indicators
 * - Confidence scoring with progress bars
 * - Price targets and levels
 * - Technical indicators display
 * - Signal strength visualization
 * - Risk/Reward ratio display
 * - Prediction history and performance
 * - Real-time updates
 * - Interactive actions (confirm, dismiss, share)
 * - Responsive design for all devices
 */

'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  TrendingUp, 
  TrendingDown, 
  Minus,
  Check,
  X,
  AlertCircle,
  Info,
  Brain,
  Target,
  Zap,
  Clock,
  BarChart3,
  PieChart,
  LineChart,
  Activity,
  RefreshCw,
  Share2,
  Bookmark,
  Flag,
  Heart,
  MessageSquare,
  Download,
  Copy,
  ExternalLink,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  ArrowUp,
  ArrowDown,
  DollarSign,
  Percent,
  Award,
  Shield,
  Sparkles,
  Crown,
  Star,
  Rocket,
  TrendingUp as TrendingUpIcon,
  TrendingDown as TrendingDownIcon,
} from 'lucide-react';

// Components
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Progress } from '@/components/ui/Progress';
import { Tooltip } from '@/components/ui/Tooltip';
import { Avatar } from '@/components/ui/Avatar';
import { Modal } from '@/components/ui/Modal';
import { Toast } from '@/components/ui/Toast';
import { Spinner } from '@/components/ui/Spinner';

// Types
import type { Prediction, PredictionIndicators } from '@/types/ai';

// Utils
import { formatCurrency, formatPercentage, formatNumber, formatTime, formatDate } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

// ============================================
// Props Interface
// ============================================

interface PredictionCardProps {
  prediction: Prediction;
  onConfirm?: (prediction: Prediction) => void;
  onDismiss?: (prediction: Prediction) => void;
  onShare?: (prediction: Prediction) => void;
  onSave?: (prediction: Prediction) => void;
  onViewDetails?: (prediction: Prediction) => void;
  compact?: boolean;
  highlighted?: boolean;
  showActions?: boolean;
  showIndicators?: boolean;
  showHistory?: boolean;
  className?: string;
  isLoading?: boolean;
  isExecuting?: boolean;
  isSaved?: boolean;
}

// ============================================
// Main Component
// ============================================

export function PredictionCard({
  prediction,
  onConfirm,
  onDismiss,
  onShare,
  onSave,
  onViewDetails,
  compact = false,
  highlighted = false,
  showActions = true,
  showIndicators = true,
  showHistory = false,
  className,
  isLoading = false,
  isExecuting = false,
  isSaved = false,
}: PredictionCardProps) {
  // State
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [isConfirming, setIsConfirming] = useState<boolean>(false);
  const [isDismissing, setIsDismissing] = useState<boolean>(false);
  const [isSharing, setIsSharing] = useState<boolean>(false);
  const [showShareModal, setShowShareModal] = useState<boolean>(false);
  const [showDetailsModal, setShowDetailsModal] = useState<boolean>(false);
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [copied, setCopied] = useState<boolean>(false);

  // Refs
  const cardRef = useRef<HTMLDivElement>(null);

  // ============================================
  // Memoized Computations
  // ============================================

  const priceChange = useMemo(() => {
    return prediction.predictedPrice - prediction.price;
  }, [prediction]);

  const percentChange = useMemo(() => {
    return (priceChange / prediction.price) * 100;
  }, [priceChange, prediction.price]);

  const isBullish = useMemo(() => {
    return prediction.direction === 'up' || prediction.signal === 'buy';
  }, [prediction]);

  const isBearish = useMemo(() => {
    return prediction.direction === 'down' || prediction.signal === 'sell';
  }, [prediction]);

  const isNeutral = useMemo(() => {
    return prediction.direction === 'neutral' || prediction.signal === 'hold';
  }, [prediction]);

  const signalColor = useMemo(() => {
    if (isBullish) return 'text-green-500 bg-green-500/20 border-green-500/30';
    if (isBearish) return 'text-red-500 bg-red-500/20 border-red-500/30';
    return 'text-yellow-500 bg-yellow-500/20 border-yellow-500/30';
  }, [isBullish, isBearish]);

  const signalIcon = useMemo(() => {
    if (isBullish) return <TrendingUp className="w-4 h-4" />;
    if (isBearish) return <TrendingDown className="w-4 h-4" />;
    return <Minus className="w-4 h-4" />;
  }, [isBullish, isBearish]);

  const signalLabel = useMemo(() => {
    if (isBullish) return 'BUY';
    if (isBearish) return 'SELL';
    return 'HOLD';
  }, [isBullish, isBearish]);

  const confidenceLevel = useMemo(() => {
    const conf = prediction.confidence;
    if (conf >= 0.8) return { label: 'High', color: 'text-green-500' };
    if (conf >= 0.6) return { label: 'Medium', color: 'text-yellow-500' };
    return { label: 'Low', color: 'text-red-500' };
  }, [prediction.confidence]);

  const indicators = useMemo(() => {
    return prediction.indicators || {
      rsi: 50,
      macd: 0,
      bollingerUpper: 0,
      bollingerMiddle: 0,
      bollingerLower: 0,
      volatility: 0,
      volume: 0,
      trend: 'neutral',
      movingAverage50: 0,
      movingAverage200: 0,
      stochasticK: 0,
      stochasticD: 0,
      adx: 0,
      obv: 0,
      vwap: 0,
    };
  }, [prediction.indicators]);

  // ============================================
  // Handlers
  // ============================================

  const handleConfirm = useCallback(async () => {
    if (!onConfirm) return;
    setIsConfirming(true);
    try {
      await onConfirm(prediction);
      setShowToast({
        message: `✅ Prediction confirmed! ${signalLabel} signal executed.`,
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to confirm prediction.',
        type: 'error',
      });
    } finally {
      setIsConfirming(false);
    }
  }, [onConfirm, prediction, signalLabel]);

  const handleDismiss = useCallback(async () => {
    if (!onDismiss) return;
    setIsDismissing(true);
    try {
      await onDismiss(prediction);
      setShowToast({
        message: 'Prediction dismissed.',
        type: 'info',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to dismiss prediction.',
        type: 'error',
      });
    } finally {
      setIsDismissing(false);
    }
  }, [onDismiss, prediction]);

  const handleShare = useCallback(async () => {
    if (!onShare) {
      // Default share behavior
      setIsSharing(true);
      try {
        const shareData = {
          title: `NEXUS AI Prediction - ${prediction.symbol}`,
          text: `${prediction.symbol}: ${signalLabel} signal with ${formatPercentage(prediction.confidence)} confidence. Predicted price: ${formatCurrency(prediction.predictedPrice)}`,
          url: window.location.href,
        };
        if (navigator.share) {
          await navigator.share(shareData);
        } else {
          await navigator.clipboard.writeText(shareData.text);
          setCopied(true);
          setTimeout(() => setCopied(false), 3000);
          setShowToast({
            message: 'Prediction copied to clipboard!',
            type: 'success',
          });
        }
      } catch (error: any) {
        if (error.name !== 'AbortError') {
          setShowToast({
            message: error.message || 'Failed to share prediction.',
            type: 'error',
          });
        }
      } finally {
        setIsSharing(false);
      }
      return;
    }
    await onShare(prediction);
  }, [onShare, prediction, signalLabel]);

  const handleSave = useCallback(() => {
    onSave?.(prediction);
    setShowToast({
      message: isSaved ? 'Removed from saved predictions' : 'Saved prediction!',
      type: isSaved ? 'info' : 'success',
    });
  }, [onSave, prediction, isSaved]);

  const handleViewDetails = useCallback(() => {
    if (onViewDetails) {
      onViewDetails(prediction);
    } else {
      setShowDetailsModal(true);
    }
  }, [onViewDetails, prediction]);

  const handleCopyPrediction = useCallback(() => {
    const text = `${prediction.symbol}: ${signalLabel} signal with ${formatPercentage(prediction.confidence)} confidence. Predicted price: ${formatCurrency(prediction.predictedPrice)}. Current price: ${formatCurrency(prediction.price)}.`;
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 3000);
    setShowToast({
      message: 'Prediction copied to clipboard!',
      type: 'success',
    });
  }, [prediction, signalLabel]);

  // ============================================
  // Render
  // ============================================

  if (isLoading) {
    return (
      <Card className={cn(
        "p-4 bg-gray-800 border-gray-700 animate-pulse",
        className
      )}>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-gray-700" />
            <div>
              <div className="h-4 w-24 bg-gray-700 rounded" />
              <div className="h-3 w-16 bg-gray-700 rounded mt-1" />
            </div>
          </div>
          <div className="h-8 w-20 bg-gray-700 rounded" />
        </div>
      </Card>
    );
  }

  // Compact Mode
  if (compact) {
    return (
      <Card
        ref={cardRef}
        className={cn(
          "p-3 hover:border-cyan-500/50 transition-colors cursor-pointer",
          highlighted && "border-cyan-500/30 bg-cyan-500/5",
          className
        )}
        onClick={handleViewDetails}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3 min-w-0">
            <div className={cn(
              "px-2 py-1 rounded text-xs font-semibold flex items-center gap-1",
              signalColor
            )}>
              {signalIcon}
              {signalLabel}
            </div>
            <div>
              <span className="text-sm font-mono text-white">{prediction.symbol}</span>
              <span className="text-xs text-gray-400 ml-2">
                {formatTime(prediction.timestamp)}
              </span>
            </div>
          </div>
          <div className="flex items-center gap-4">
            <div className="text-right">
              <div className="text-sm font-mono text-white">
                {formatCurrency(prediction.predictedPrice)}
              </div>
              <div className={cn(
                "text-xs",
                percentChange >= 0 ? 'text-green-500' : 'text-red-500'
              )}>
                {formatPercentage(percentChange)}
              </div>
            </div>
            <Badge className={cn(
              "text-xs",
              prediction.confidence >= 0.7 ? 'bg-green-500/20 text-green-500' :
              prediction.confidence >= 0.5 ? 'bg-yellow-500/20 text-yellow-500' :
              'bg-red-500/20 text-red-500'
            )}>
              {formatPercentage(prediction.confidence)} confidence
            </Badge>
            {showActions && (
              <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                {onConfirm && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleConfirm}
                    isLoading={isConfirming}
                    className="text-green-500 hover:text-green-400 hover:bg-green-500/10"
                  >
                    <Check className="w-4 h-4" />
                  </Button>
                )}
                {onDismiss && (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleDismiss}
                    isLoading={isDismissing}
                    className="text-gray-400 hover:text-red-500"
                  >
                    <X className="w-4 h-4" />
                  </Button>
                )}
              </div>
            )}
          </div>
        </div>
      </Card>
    );
  }

  // Full Mode
  return (
    <>
      <Card
        ref={cardRef}
        className={cn(
          "p-4 hover:border-cyan-500/50 transition-colors",
          highlighted && "border-cyan-500/30 bg-cyan-500/5",
          className
        )}
      >
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={cn(
              "px-3 py-1.5 rounded-lg text-sm font-semibold flex items-center gap-2",
              signalColor
            )}>
              {signalIcon}
              {signalLabel}
            </div>
            <span className="text-sm font-mono text-white">{prediction.symbol}</span>
            <Badge className={cn(
              "text-xs",
              confidenceLevel.color,
              "bg-opacity-10 border-opacity-20"
            )}>
              {confidenceLevel.label} Confidence
            </Badge>
            {isSaved && (
              <Badge className="bg-yellow-500/20 text-yellow-400 text-xs">
                Saved
              </Badge>
            )}
          </div>
          <div className="text-right">
            <div className="text-xs text-gray-400">Predicted Price</div>
            <div className="text-lg font-mono font-semibold text-white">
              {formatCurrency(prediction.predictedPrice)}
            </div>
          </div>
        </div>

        {/* Prediction Details */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">
          <div>
            <div className="text-xs text-gray-400">Current Price</div>
            <div className="text-sm font-mono text-white">
              {formatCurrency(prediction.price)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-400">Change</div>
            <div className={cn(
              "text-sm font-mono",
              percentChange >= 0 ? 'text-green-500' : 'text-red-500'
            )}>
              {formatPercentage(percentChange)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-400">Confidence</div>
            <div className="flex items-center gap-2">
              <div className="text-sm font-mono text-white">
                {formatPercentage(prediction.confidence)}
              </div>
              <div className="flex-1 max-w-16">
                <Progress 
                  value={prediction.confidence * 100} 
                  className="h-1.5"
                  color={prediction.confidence >= 0.7 ? 'green' : prediction.confidence >= 0.5 ? 'yellow' : 'red'}
                />
              </div>
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-400">Risk/Reward</div>
            <div className="text-sm font-mono text-white">
              {prediction.riskRewardRatio?.toFixed(2) || 'N/A'}
            </div>
          </div>
        </div>

        {/* Stop Loss & Take Profit */}
        {(prediction.stopLoss || prediction.takeProfit) && (
          <div className="grid grid-cols-2 gap-4 mb-4 p-3 bg-gray-700/30 rounded-lg">
            {prediction.stopLoss && (
              <div>
                <div className="text-xs text-gray-400">Stop Loss</div>
                <div className="text-sm font-mono text-red-500">
                  {formatCurrency(prediction.stopLoss)}
                </div>
              </div>
            )}
            {prediction.takeProfit && (
              <div>
                <div className="text-xs text-gray-400">Take Profit</div>
                <div className="text-sm font-mono text-green-500">
                  {formatCurrency(prediction.takeProfit)}
                </div>
              </div>
            )}
          </div>
        )}

        {/* Expandable Details */}
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors flex items-center gap-1 mb-2"
        >
          {isExpanded ? 'Show less' : 'Show more details'}
          {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
        </button>

        <AnimatePresence>
          {isExpanded && showIndicators && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              exit={{ opacity: 0, height: 0 }}
              transition={{ duration: 0.3 }}
              className="overflow-hidden"
            >
              <div className="mt-4 pt-4 border-t border-gray-700">
                <h4 className="text-sm font-medium text-gray-300 mb-3">Technical Indicators</h4>
                <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                  <div>
                    <div className="text-xs text-gray-400">RSI</div>
                    <div className={cn(
                      "text-sm font-mono",
                      indicators.rsi > 70 ? 'text-red-500' :
                      indicators.rsi < 30 ? 'text-green-500' :
                      'text-white'
                    )}>
                      {indicators.rsi.toFixed(2)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">MACD</div>
                    <div className={cn(
                      "text-sm font-mono",
                      indicators.macd > 0 ? 'text-green-500' : 'text-red-500'
                    )}>
                      {indicators.macd.toFixed(4)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">Volatility</div>
                    <div className="text-sm font-mono text-white">
                      {formatPercentage(indicators.volatility)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">Trend</div>
                    <div className={cn(
                      "text-sm font-semibold",
                      indicators.trend === 'bullish' ? 'text-green-500' :
                      indicators.trend === 'bearish' ? 'text-red-500' :
                      'text-yellow-500'
                    )}>
                      {indicators.trend.toUpperCase()}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">Volume</div>
                    <div className="text-sm font-mono text-white">
                      {formatNumber(indicators.volume)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">ADX</div>
                    <div className="text-sm font-mono text-white">
                      {indicators.adx.toFixed(2)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">VWAP</div>
                    <div className="text-sm font-mono text-white">
                      {formatCurrency(indicators.vwap)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">OBV</div>
                    <div className="text-sm font-mono text-white">
                      {formatNumber(indicators.obv)}
                    </div>
                  </div>
                </div>
              </div>

              {/* Bollinger Bands */}
              <div className="mt-4 pt-4 border-t border-gray-700">
                <h4 className="text-sm font-medium text-gray-300 mb-3">Bollinger Bands</h4>
                <div className="grid grid-cols-3 gap-3">
                  <div>
                    <div className="text-xs text-gray-400">Upper</div>
                    <div className="text-sm font-mono text-green-500">
                      {formatCurrency(indicators.bollingerUpper)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">Middle</div>
                    <div className="text-sm font-mono text-white">
                      {formatCurrency(indicators.bollingerMiddle)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">Lower</div>
                    <div className="text-sm font-mono text-red-500">
                      {formatCurrency(indicators.bollingerLower)}
                    </div>
                  </div>
                </div>
              </div>

              {/* Moving Averages */}
              <div className="mt-4 pt-4 border-t border-gray-700">
                <h4 className="text-sm font-medium text-gray-300 mb-3">Moving Averages</h4>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-xs text-gray-400">MA 50</div>
                    <div className="text-sm font-mono text-white">
                      {formatCurrency(indicators.movingAverage50)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">MA 200</div>
                    <div className="text-sm font-mono text-white">
                      {formatCurrency(indicators.movingAverage200)}
                    </div>
                  </div>
                </div>
              </div>

              {/* Stochastic */}
              <div className="mt-4 pt-4 border-t border-gray-700">
                <h4 className="text-sm font-medium text-gray-300 mb-3">Stochastic</h4>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <div className="text-xs text-gray-400">%K</div>
                    <div className="text-sm font-mono text-white">
                      {indicators.stochasticK.toFixed(2)}
                    </div>
                  </div>
                  <div>
                    <div className="text-xs text-gray-400">%D</div>
                    <div className="text-sm font-mono text-white">
                      {indicators.stochasticD.toFixed(2)}
                    </div>
                  </div>
                </div>
              </div>

              {/* Model Info */}
              <div className="mt-4 pt-4 border-t border-gray-700">
                <div className="flex items-center gap-4 text-xs text-gray-500">
                  <span>Model: {prediction.modelName || 'Unknown'}</span>
                  <span>Version: {prediction.modelVersion || 'N/A'}</span>
                  <span>Time: {formatTime(prediction.timestamp)}</span>
                  <span>ID: #{prediction.id.slice(0, 8)}</span>
                </div>
              </div>

              {/* History (if showHistory is true) */}
              {showHistory && (
                <div className="mt-4 pt-4 border-t border-gray-700">
                  <h4 className="text-sm font-medium text-gray-300 mb-3">Prediction History</h4>
                  <div className="space-y-2 text-sm text-gray-400">
                    <div className="flex justify-between">
                      <span>Previous Predictions</span>
                      <span className="text-white">12</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Accuracy Rate</span>
                      <span className="text-green-500">68.5%</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Average Confidence</span>
                      <span className="text-white">{formatPercentage(0.72)}</span>
                    </div>
                  </div>
                </div>
              )}
            </motion.div>
          )}
        </AnimatePresence>

        {/* Actions */}
        {showActions && (
          <div className="mt-4 pt-4 border-t border-gray-700 flex flex-wrap items-center gap-2">
            {onConfirm && (
              <Button
                variant="primary"
                size="sm"
                onClick={handleConfirm}
                isLoading={isConfirming}
                className={cn(
                  "flex-1",
                  isBullish 
                    ? "bg-gradient-to-r from-green-500 to-emerald-500 hover:from-green-600 hover:to-emerald-600"
                    : "bg-gradient-to-r from-red-500 to-rose-500 hover:from-red-600 hover:to-rose-600"
                )}
              >
                {isBullish ? 'Confirm Buy' : 'Confirm Sell'}
              </Button>
            )}
            {onDismiss && (
              <Button
                variant="outline"
                size="sm"
                onClick={handleDismiss}
                isLoading={isDismissing}
                className="border-gray-600 hover:border-gray-500"
              >
                Dismiss
              </Button>
            )}
            <div className="flex items-center gap-1 ml-auto">
              {onSave && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleSave}
                  className={isSaved ? 'text-yellow-500' : 'text-gray-400 hover:text-white'}
                >
                  <Bookmark className="w-4 h-4" />
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                onClick={handleShare}
                isLoading={isSharing}
                className="text-gray-400 hover:text-white"
              >
                <Share2 className="w-4 h-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleCopyPrediction}
                className="text-gray-400 hover:text-white"
              >
                <Copy className="w-4 h-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleViewDetails}
                className="text-gray-400 hover:text-white"
              >
                <ExternalLink className="w-4 h-4" />
              </Button>
            </div>
          </div>
        )}

        {/* Timestamp */}
        <div className="mt-3 text-xs text-gray-500">
          {formatTime(prediction.timestamp)} • {formatDate(prediction.timestamp)}
          {prediction.executedAt && (
            <span className="ml-2 text-green-500">
              • Executed: {formatTime(prediction.executedAt)}
            </span>
          )}
        </div>
      </Card>

      {/* Share Modal */}
      <Modal
        open={showShareModal}
        onOpenChange={setShowShareModal}
        title="Share Prediction"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div className="p-3 bg-gray-700/30 rounded-lg">
            <div className="text-sm text-gray-300">
              {prediction.symbol}: {signalLabel} signal with {formatPercentage(prediction.confidence)} confidence
            </div>
            <div className="text-sm text-gray-400 mt-1">
              Predicted price: {formatCurrency(prediction.predictedPrice)}
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={() => {
                navigator.clipboard.writeText(
                  `${prediction.symbol}: ${signalLabel} signal with ${formatPercentage(prediction.confidence)} confidence. Predicted price: ${formatCurrency(prediction.predictedPrice)}`
                );
                setCopied(true);
                setTimeout(() => setCopied(false), 3000);
              }}
              className="flex-1 border-gray-600 hover:border-cyan-500"
            >
              <Copy className="w-4 h-4 mr-2" />
              Copy to Clipboard
            </Button>
            {navigator.share && (
              <Button
                variant="primary"
                onClick={() => {
                  navigator.share({
                    title: `NEXUS AI Prediction - ${prediction.symbol}`,
                    text: `${prediction.symbol}: ${signalLabel} signal with ${formatPercentage(prediction.confidence)} confidence`,
                  });
                }}
                className="flex-1 bg-gradient-to-r from-cyan-500 to-blue-500"
              >
                <Share2 className="w-4 h-4 mr-2" />
                Share
              </Button>
            )}
          </div>
        </div>
      </Modal>

      {/* Details Modal */}
      <Modal
        open={showDetailsModal}
        onOpenChange={setShowDetailsModal}
        title="Prediction Details"
        className="max-w-2xl"
      >
        <div className="space-y-4 max-h-[70vh] overflow-y-auto">
          <div className="flex items-center gap-3">
            <div className={cn(
              "px-3 py-1.5 rounded-lg text-sm font-semibold flex items-center gap-2",
              signalColor
            )}>
              {signalIcon}
              {signalLabel}
            </div>
            <span className="text-lg font-mono text-white">{prediction.symbol}</span>
            <Badge className={cn(
              "text-xs",
              confidenceLevel.color,
              "bg-opacity-10 border-opacity-20"
            )}>
              {confidenceLevel.label} Confidence
            </Badge>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <span className="text-xs text-gray-400">Current Price</span>
              <div className="text-lg font-mono text-white">{formatCurrency(prediction.price)}</div>
            </div>
            <div>
              <span className="text-xs text-gray-400">Predicted Price</span>
              <div className="text-lg font-mono text-white">{formatCurrency(prediction.predictedPrice)}</div>
            </div>
            <div>
              <span className="text-xs text-gray-400">Change</span>
              <div className={cn(
                "text-lg font-mono",
                percentChange >= 0 ? 'text-green-500' : 'text-red-500'
              )}>
                {formatPercentage(percentChange)}
              </div>
            </div>
            <div>
              <span className="text-xs text-gray-400">Confidence</span>
              <div className="flex items-center gap-2">
                <div className="text-lg font-mono text-white">
                  {formatPercentage(prediction.confidence)}
                </div>
                <Progress 
                  value={prediction.confidence * 100} 
                  className="h-2 flex-1"
                  color={prediction.confidence >= 0.7 ? 'green' : prediction.confidence >= 0.5 ? 'yellow' : 'red'}
                />
              </div>
            </div>
          </div>

          {(prediction.stopLoss || prediction.takeProfit) && (
            <div className="grid grid-cols-2 gap-4 p-3 bg-gray-700/30 rounded-lg">
              {prediction.stopLoss && (
                <div>
                  <span className="text-xs text-gray-400">Stop Loss</span>
                  <div className="text-lg font-mono text-red-500">{formatCurrency(prediction.stopLoss)}</div>
                </div>
              )}
              {prediction.takeProfit && (
                <div>
                  <span className="text-xs text-gray-400">Take Profit</span>
                  <div className="text-lg font-mono text-green-500">{formatCurrency(prediction.takeProfit)}</div>
                </div>
              )}
            </div>
          )}

          <div className="p-3 bg-gray-700/30 rounded-lg">
            <h4 className="text-sm font-medium text-gray-300 mb-2">Technical Indicators</h4>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
              <div>
                <span className="text-xs text-gray-400">RSI</span>
                <div className={cn(
                  "text-sm font-mono",
                  indicators.rsi > 70 ? 'text-red-500' :
                  indicators.rsi < 30 ? 'text-green-500' :
                  'text-white'
                )}>
                  {indicators.rsi.toFixed(2)}
                </div>
              </div>
              <div>
                <span className="text-xs text-gray-400">MACD</span>
                <div className={cn(
                  "text-sm font-mono",
                  indicators.macd > 0 ? 'text-green-500' : 'text-red-500'
                )}>
                  {indicators.macd.toFixed(4)}
                </div>
              </div>
              <div>
                <span className="text-xs text-gray-400">Volatility</span>
                <div className="text-sm font-mono text-white">{formatPercentage(indicators.volatility)}</div>
              </div>
              <div>
                <span className="text-xs text-gray-400">Trend</span>
                <div className={cn(
                  "text-sm font-semibold",
                  indicators.trend === 'bullish' ? 'text-green-500' :
                  indicators.trend === 'bearish' ? 'text-red-500' :
                  'text-yellow-500'
                )}>
                  {indicators.trend.toUpperCase()}
                </div>
              </div>
              <div>
                <span className="text-xs text-gray-400">Volume</span>
                <div className="text-sm font-mono text-white">{formatNumber(indicators.volume)}</div>
              </div>
              <div>
                <span className="text-xs text-gray-400">ADX</span>
                <div className="text-sm font-mono text-white">{indicators.adx.toFixed(2)}</div>
              </div>
            </div>
          </div>

          <div className="text-xs text-gray-500">
            Model: {prediction.modelName || 'Unknown'} • Version: {prediction.modelVersion || 'N/A'} • ID: #{prediction.id.slice(0, 8)}
          </div>

          <div className="flex gap-2 pt-4 border-t border-gray-700">
            {onConfirm && (
              <Button
                variant="primary"
                onClick={handleConfirm}
                isLoading={isConfirming}
                className={cn(
                  "flex-1",
                  isBullish 
                    ? "bg-gradient-to-r from-green-500 to-emerald-500"
                    : "bg-gradient-to-r from-red-500 to-rose-500"
                )}
              >
                {isBullish ? 'Confirm Buy' : 'Confirm Sell'}
              </Button>
            )}
            <Button
              variant="outline"
              onClick={() => setShowDetailsModal(false)}
              className="border-gray-600 hover:border-gray-500"
            >
              Close
            </Button>
          </div>
        </div>
      </Modal>

      {/* Toast Notifications */}
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
    </>
  );
}

// ============================================
// Export
// ============================================

export default PredictionCard;

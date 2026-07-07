/**
 * NEXUS AI TRADING SYSTEM - SentimentIndicator Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This component provides AI sentiment analysis display including:
 * - Overall sentiment with visual indicators
 * - Sentiment score with gauge/progress
 * - Bullish/Bearish/Neutral breakdown
 * - Source sentiment analysis
 * - Historical sentiment trends
 * - Social media and news sentiment
 * - Volatility indicators
 * - Real-time sentiment updates
 * - Interactive sentiment details
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
  Twitter,
  Globe,
  Newspaper,
  Users,
  MessageCircle,
  ThumbsUp,
  ThumbsDown,
  Smile,
  Frown,
  Meh,
  Send,
  Mail,
  Phone,
  MapPin,
  Globe2,
  Sun,
  Moon,
  Monitor,
  Layout,
  Columns,
  Rows,
  PanelTop,
  PanelBottom,
  PanelLeft,
  PanelRight,
  Square,
  Circle,
  Triangle,
  Hexagon,
  Octagon,
  Pentagon,
  Sparkles as SparklesIcon,
  Crown as CrownIcon,
  Star as StarIcon,
  Award as AwardIcon,
  Trophy,
  Medal,
  Gift,
  Rocket as RocketIcon,
  Zap as ZapIcon,
  Shield as ShieldIcon,
  Brain as BrainIcon,
  TrendingUp as TrendingUpIcon2,
  TrendingDown as TrendingDownIcon2,
  Minus as MinusIcon,
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';

// Types
import type { SentimentData, SentimentSource, SentimentHistoryPoint } from '@/types/ai';

// Utils
import { formatPercentage, formatNumber, formatTime, formatDate } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

// ============================================
// Props Interface
// ============================================

interface SentimentIndicatorProps {
  data: SentimentData;
  isLoading?: boolean;
  className?: string;
  showSources?: boolean;
  showHistory?: boolean;
  showVolatility?: boolean;
  compact?: boolean;
  onRefresh?: () => void;
  onShare?: () => void;
  onExport?: () => void;
  interactive?: boolean;
}

// ============================================
// Main Component
// ============================================

export function SentimentIndicator({
  data,
  isLoading = false,
  className,
  showSources = true,
  showHistory = true,
  showVolatility = true,
  compact = false,
  onRefresh,
  onShare,
  onExport,
  interactive = true,
}: SentimentIndicatorProps) {
  // State
  const [isExpanded, setIsExpanded] = useState<boolean>(false);
  const [showDetailsModal, setShowDetailsModal] = useState<boolean>(false);
  const [selectedSource, setSelectedSource] = useState<SentimentSource | null>(null);
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);
  const [isCopied, setIsCopied] = useState<boolean>(false);

  // Refs
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<HTMLDivElement>(null);

  // ============================================
  // Memoized Computations
  // ============================================

  const sentimentColor = useMemo(() => {
    switch (data.overall) {
      case 'bullish':
        return 'text-green-500 bg-green-500/20 border-green-500/30';
      case 'bearish':
        return 'text-red-500 bg-red-500/20 border-red-500/30';
      default:
        return 'text-yellow-500 bg-yellow-500/20 border-yellow-500/30';
    }
  }, [data.overall]);

  const sentimentIcon = useMemo(() => {
    switch (data.overall) {
      case 'bullish':
        return <TrendingUp className="w-5 h-5" />;
      case 'bearish':
        return <TrendingDown className="w-5 h-5" />;
      default:
        return <Minus className="w-5 h-5" />;
    }
  }, [data.overall]);

  const sentimentEmoji = useMemo(() => {
    switch (data.overall) {
      case 'bullish':
        return '🐂';
      case 'bearish':
        return '🐻';
      default:
        return '🤔';
    }
  }, [data.overall]);

  const sentimentLabel = useMemo(() => {
    switch (data.overall) {
      case 'bullish':
        return 'Bullish';
      case 'bearish':
        return 'Bearish';
      default:
        return 'Neutral';
    }
  }, [data.overall]);

  const sentimentScore = useMemo(() => {
    return data.score || 0;
  }, [data.score]);

  const normalizedScore = useMemo(() => {
    return Math.max(0, Math.min(1, (sentimentScore + 1) / 2));
  }, [sentimentScore]);

  const totalMentions = useMemo(() => {
    return (data.socialMention || 0) + (data.newsMention || 0);
  }, [data.socialMention, data.newsMention]);

  const sortedSources = useMemo(() => {
    return [...(data.sources || [])].sort((a, b) => b.score - a.score);
  }, [data.sources]);

  const historyData = useMemo(() => {
    return data.historical || [];
  }, [data.historical]);

  const recentTrend = useMemo(() => {
    if (historyData.length < 2) return 'stable';
    const last = historyData[historyData.length - 1].score;
    const prev = historyData[historyData.length - 2].score;
    if (last > prev + 0.05) return 'improving';
    if (last < prev - 0.05) return 'declining';
    return 'stable';
  }, [historyData]);

  const trendColor = useMemo(() => {
    switch (recentTrend) {
      case 'improving':
        return 'text-green-500';
      case 'declining':
        return 'text-red-500';
      default:
        return 'text-yellow-500';
    }
  }, [recentTrend]);

  const trendIcon = useMemo(() => {
    switch (recentTrend) {
      case 'improving':
        return <ArrowUp className="w-4 h-4" />;
      case 'declining':
        return <ArrowDown className="w-4 h-4" />;
      default:
        return <Minus className="w-4 h-4" />;
    }
  }, [recentTrend]);

  // ============================================
  // Handlers
  // ============================================

  const handleRefresh = useCallback(async () => {
    if (!onRefresh) return;
    setIsRefreshing(true);
    try {
      await onRefresh();
      setShowToast({
        message: 'Sentiment data refreshed!',
        type: 'success',
      });
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to refresh sentiment data.',
        type: 'error',
      });
    } finally {
      setIsRefreshing(false);
    }
  }, [onRefresh]);

  const handleShare = useCallback(() => {
    if (onShare) {
      onShare();
      return;
    }
    const shareText = `📊 ${data.overall.toUpperCase()} sentiment for market: ${sentimentLabel} (${formatPercentage(sentimentScore)}). Sources: ${totalMentions} mentions.`;
    if (navigator.share) {
      navigator.share({
        title: 'NEXUS AI Sentiment Analysis',
        text: shareText,
      }).catch(() => {});
    } else {
      navigator.clipboard.writeText(shareText);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 3000);
      setShowToast({
        message: 'Sentiment data copied to clipboard!',
        type: 'success',
      });
    }
  }, [onShare, data, sentimentLabel, sentimentScore, totalMentions]);

  const handleExport = useCallback(() => {
    if (onExport) {
      onExport();
      return;
    }
    const exportData = {
      timestamp: new Date().toISOString(),
      sentiment: data,
      exportedBy: 'NEXUS AI Trading System',
    };
    const blob = new Blob([JSON.stringify(exportData, null, 2)], {
      type: 'application/json',
    });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', `sentiment-data-${Date.now()}.json`);
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setShowToast({
      message: 'Sentiment data exported!',
      type: 'success',
    });
  }, [onExport, data]);

  const handleViewSource = useCallback((source: SentimentSource) => {
    setSelectedSource(source);
  }, []);

  const handleCloseSource = useCallback(() => {
    setSelectedSource(null);
  }, []);

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
            <div className="w-10 h-10 rounded-full bg-gray-700" />
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
        ref={containerRef}
        className={cn(
          "p-3 hover:border-cyan-500/50 transition-colors cursor-pointer",
          className
        )}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className={cn(
              "w-8 h-8 rounded-full flex items-center justify-center",
              sentimentColor
            )}>
              {sentimentIcon}
            </div>
            <div>
              <div className="text-sm font-medium text-white">{sentimentLabel}</div>
              <div className="text-xs text-gray-400">{formatPercentage(sentimentScore)}</div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <Badge className={cn("text-xs", sentimentColor)}>
              {data.overall.toUpperCase()}
            </Badge>
            <div className="text-xs text-gray-500">{totalMentions} mentions</div>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <>
      <Card
        ref={containerRef}
        className={cn(
          "p-4 bg-gray-800 border-gray-700",
          interactive && "hover:border-cyan-500/50 transition-colors",
          className
        )}
      >
        {/* ============================================ */}
        {/* Header */}
        {/* ============================================ */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <div className={cn(
              "w-10 h-10 rounded-full flex items-center justify-center",
              sentimentColor
            )}>
              {sentimentIcon}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-semibold text-white">{sentimentLabel}</span>
                <Badge className={cn("text-xs", sentimentColor)}>
                  {data.overall.toUpperCase()}
                </Badge>
                {recentTrend !== 'stable' && (
                  <Badge className={cn(
                    "text-xs",
                    recentTrend === 'improving' ? 'bg-green-500/20 text-green-500' : 'bg-red-500/20 text-red-500'
                  )}>
                    {trendIcon}
                    {recentTrend}
                  </Badge>
                )}
              </div>
              <div className="text-xs text-gray-400">
                Updated {formatTime(data.lastUpdated)}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {onRefresh && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRefresh}
                isLoading={isRefreshing}
                className="text-gray-400 hover:text-white"
              >
                <RefreshCw className="w-4 h-4" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={handleShare}
              className="text-gray-400 hover:text-white"
            >
              <Share2 className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleExport}
              className="text-gray-400 hover:text-white"
            >
              <Download className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowDetailsModal(true)}
              className="text-gray-400 hover:text-white"
            >
              <ExternalLink className="w-4 h-4" />
            </Button>
          </div>
        </div>

        {/* ============================================ */}
        {/* Sentiment Score Gauge */}
        {/* ============================================ */}
        <div className="mb-4">
          <div className="flex items-center justify-between mb-1">
            <span className="text-sm text-gray-400">Sentiment Score</span>
            <span className="text-sm font-mono text-white">{formatPercentage(sentimentScore)}</span>
          </div>
          <div className="relative h-3 bg-gray-700 rounded-full overflow-hidden">
            <motion.div
              className="absolute inset-0 bg-gradient-to-r from-red-500 via-yellow-500 to-green-500"
              initial={{ scaleX: 0 }}
              animate={{ scaleX: 1 }}
              transition={{ duration: 0.8 }}
            />
            <motion.div
              className="absolute top-0 bottom-0 w-0.5 bg-white shadow-lg"
              style={{
                left: `${normalizedScore * 100}%`,
              }}
              initial={{ left: '50%' }}
              animate={{ left: `${normalizedScore * 100}%` }}
              transition={{ duration: 0.8 }}
            />
          </div>
          <div className="flex justify-between mt-1 text-xs text-gray-500">
            <span>Bearish</span>
            <span>Neutral</span>
            <span>Bullish</span>
          </div>
        </div>

        {/* ============================================ */}
        {/* Sentiment Breakdown */}
        {/* ============================================ */}
        <div className="grid grid-cols-3 gap-3 mb-4">
          <div className="p-2 bg-green-500/10 rounded-lg text-center border border-green-500/20">
            <div className="text-2xl font-bold text-green-500">
              {formatPercentage(data.bullish / 100)}
            </div>
            <div className="text-xs text-gray-400">Bullish</div>
          </div>
          <div className="p-2 bg-yellow-500/10 rounded-lg text-center border border-yellow-500/20">
            <div className="text-2xl font-bold text-yellow-500">
              {formatPercentage(data.neutral / 100)}
            </div>
            <div className="text-xs text-gray-400">Neutral</div>
          </div>
          <div className="p-2 bg-red-500/10 rounded-lg text-center border border-red-500/20">
            <div className="text-2xl font-bold text-red-500">
              {formatPercentage(data.bearish / 100)}
            </div>
            <div className="text-xs text-gray-400">Bearish</div>
          </div>
        </div>

        {/* ============================================ */}
        {/* Volatility */}
        {/* ============================================ */}
        {showVolatility && data.volatility !== undefined && (
          <div className="mb-4 p-2 bg-gray-700/30 rounded-lg">
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-400">Volatility</span>
              <span className={cn(
                "font-mono",
                data.volatility > 0.5 ? 'text-red-500' :
                data.volatility > 0.3 ? 'text-yellow-500' :
                'text-green-500'
              )}>
                {formatPercentage(data.volatility)}
              </span>
            </div>
            <Progress 
              value={data.volatility * 100} 
              className="h-1 mt-1"
              color={data.volatility > 0.5 ? 'red' : data.volatility > 0.3 ? 'yellow' : 'green'}
            />
          </div>
        )}

        {/* ============================================ */}
        {/* Mention Counts */}
        {/* ============================================ */}
        <div className="flex items-center gap-4 text-sm text-gray-400 mb-4">
          <div className="flex items-center gap-1">
            <MessageSquare className="w-4 h-4" />
            <span>{totalMentions} mentions</span>
          </div>
          <div className="flex items-center gap-1">
            <Twitter className="w-4 h-4" />
            <span>{data.socialMention || 0} social</span>
          </div>
          <div className="flex items-center gap-1">
            <Newspaper className="w-4 h-4" />
            <span>{data.newsMention || 0} news</span>
          </div>
        </div>

        {/* ============================================ */}
        {/* Sources */}
        {/* ============================================ */}
        {showSources && sortedSources.length > 0 && (
          <div className="mb-4">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm text-gray-400">Sources</span>
              <span className="text-xs text-gray-500">{sortedSources.length} active</span>
            </div>
            <div className="flex flex-wrap gap-2">
              {sortedSources.slice(0, 4).map((source, index) => (
                <button
                  key={index}
                  onClick={() => handleViewSource(source)}
                  className={cn(
                    "px-2 py-1 rounded-lg text-xs transition-colors flex items-center gap-1",
                    source.score > 0.3 ? 'bg-green-500/20 text-green-500' :
                    source.score < -0.3 ? 'bg-red-500/20 text-red-500' :
                    'bg-yellow-500/20 text-yellow-500'
                  )}
                >
                  {source.name}
                  <span className="text-[10px] opacity-70">
                    ({formatPercentage(source.score)})
                  </span>
                </button>
              ))}
              {sortedSources.length > 4 && (
                <Badge className="bg-gray-700 text-gray-400 text-xs">
                  +{sortedSources.length - 4} more
                </Badge>
              )}
            </div>
          </div>
        )}

        {/* ============================================ */}
        {/* History */}
        {/* ============================================ */}
        {showHistory && historyData.length > 0 && (
          <div className="pt-4 border-t border-gray-700">
            <button
              onClick={() => setIsExpanded(!isExpanded)}
              className="flex items-center gap-1 text-xs text-gray-400 hover:text-white transition-colors"
            >
              {isExpanded ? 'Hide history' : 'Show history'}
              {isExpanded ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
            </button>
            <AnimatePresence>
              {isExpanded && (
                <motion.div
                  initial={{ opacity: 0, height: 0 }}
                  animate={{ opacity: 1, height: 'auto' }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.3 }}
                  className="overflow-hidden"
                >
                  <div className="mt-3 space-y-1">
                    {historyData.slice(-10).map((point, index) => (
                      <div key={index} className="flex items-center justify-between text-xs">
                        <span className="text-gray-500">{formatTime(point.timestamp)}</span>
                        <div className="flex items-center gap-2 flex-1 mx-2">
                          <div className="flex-1 h-1 bg-gray-700 rounded-full overflow-hidden">
                            <div 
                              className={cn(
                                "h-full transition-all",
                                point.score > 0.3 ? 'bg-green-500' :
                                point.score < -0.3 ? 'bg-red-500' :
                                'bg-yellow-500'
                              )}
                              style={{ width: `${(point.score + 1) / 2 * 100}%` }}
                            />
                          </div>
                        </div>
                        <span className={cn(
                          "font-mono",
                          point.score > 0.3 ? 'text-green-500' :
                          point.score < -0.3 ? 'text-red-500' :
                          'text-yellow-500'
                        )}>
                          {formatPercentage(point.score)}
                        </span>
                      </div>
                    ))}
                  </div>
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        )}

        {/* ============================================ */}
        {/* Last Updated */}
        {/* ============================================ */}
        <div className="mt-3 text-xs text-gray-500">
          Last updated: {formatTime(data.lastUpdated)}
          {data.lastUpdated && (
            <span className="ml-2">
              ({formatDate(data.lastUpdated)})
            </span>
          )}
        </div>
      </Card>

      {/* ============================================ */}
      {/* Details Modal */}
      {/* ============================================ */}
      <Modal
        open={showDetailsModal}
        onOpenChange={setShowDetailsModal}
        title="Sentiment Analysis Details"
        className="max-w-2xl"
      >
        <div className="space-y-4 max-h-[70vh] overflow-y-auto">
          {/* Header */}
          <div className="flex items-center gap-3">
            <div className={cn(
              "w-12 h-12 rounded-full flex items-center justify-center",
              sentimentColor
            )}>
              {sentimentIcon}
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl font-bold text-white">{sentimentLabel}</span>
                <Badge className={cn("text-sm", sentimentColor)}>
                  {data.overall.toUpperCase()}
                </Badge>
              </div>
              <div className="text-sm text-gray-400">
                Score: {formatPercentage(sentimentScore)}
              </div>
            </div>
          </div>

          {/* Tabs */}
          <Tabs defaultValue="overview">
            <TabsList className="bg-gray-700/30 rounded-lg p-1">
              <TabsTrigger value="overview" className="text-xs">Overview</TabsTrigger>
              <TabsTrigger value="sources" className="text-xs">Sources</TabsTrigger>
              <TabsTrigger value="history" className="text-xs">History</TabsTrigger>
            </TabsList>

            <TabsContent value="overview" className="mt-4 space-y-4">
              {/* Breakdown */}
              <div className="grid grid-cols-3 gap-4">
                <div className="p-3 bg-green-500/10 rounded-lg text-center border border-green-500/20">
                  <div className="text-3xl font-bold text-green-500">
                    {formatPercentage(data.bullish / 100)}
                  </div>
                  <div className="text-sm text-gray-400">Bullish</div>
                </div>
                <div className="p-3 bg-yellow-500/10 rounded-lg text-center border border-yellow-500/20">
                  <div className="text-3xl font-bold text-yellow-500">
                    {formatPercentage(data.neutral / 100)}
                  </div>
                  <div className="text-sm text-gray-400">Neutral</div>
                </div>
                <div className="p-3 bg-red-500/10 rounded-lg text-center border border-red-500/20">
                  <div className="text-3xl font-bold text-red-500">
                    {formatPercentage(data.bearish / 100)}
                  </div>
                  <div className="text-sm text-gray-400">Bearish</div>
                </div>
              </div>

              {/* Metrics */}
              <div className="p-3 bg-gray-700/30 rounded-lg">
                <h4 className="text-sm font-medium text-gray-300 mb-2">Key Metrics</h4>
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div>
                    <span className="text-gray-400">Social Mentions</span>
                    <div className="text-white">{formatNumber(data.socialMention || 0)}</div>
                  </div>
                  <div>
                    <span className="text-gray-400">News Mentions</span>
                    <div className="text-white">{formatNumber(data.newsMention || 0)}</div>
                  </div>
                  <div>
                    <span className="text-gray-400">Total Mentions</span>
                    <div className="text-white">{formatNumber(totalMentions)}</div>
                  </div>
                  <div>
                    <span className="text-gray-400">Volatility</span>
                    <div className={cn(
                      "font-medium",
                      data.volatility > 0.5 ? 'text-red-500' :
                      data.volatility > 0.3 ? 'text-yellow-500' :
                      'text-green-500'
                    )}>
                      {formatPercentage(data.volatility)}
                    </div>
                  </div>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="sources" className="mt-4">
              <div className="space-y-3">
                {sortedSources.map((source, index) => (
                  <div key={index} className="p-3 bg-gray-700/30 rounded-lg">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-white">{source.name}</span>
                        <span className="text-xs text-gray-400">(Weight: {formatPercentage(source.weight)})</span>
                      </div>
                      <Badge className={cn(
                        "text-xs",
                        source.score > 0.3 ? 'bg-green-500/20 text-green-500' :
                        source.score < -0.3 ? 'bg-red-500/20 text-red-500' :
                        'bg-yellow-500/20 text-yellow-500'
                      )}>
                        {formatPercentage(source.score)}
                      </Badge>
                    </div>
                    {source.data && Object.keys(source.data).length > 0 && (
                      <div className="mt-2 text-xs text-gray-400">
                        {Object.entries(source.data).slice(0, 3).map(([key, value]) => (
                          <span key={key} className="mr-3">
                            {key}: {String(value)}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </TabsContent>

            <TabsContent value="history" className="mt-4">
              <div className="space-y-2">
                {historyData.map((point, index) => (
                  <div key={index} className="flex items-center justify-between p-2 bg-gray-700/30 rounded-lg text-sm">
                    <span className="text-gray-400">{formatTime(point.timestamp)}</span>
                    <div className="flex items-center gap-4">
                      <div className="w-32 h-1.5 bg-gray-700 rounded-full overflow-hidden">
                        <div 
                          className={cn(
                            "h-full transition-all",
                            point.score > 0.3 ? 'bg-green-500' :
                            point.score < -0.3 ? 'bg-red-500' :
                            'bg-yellow-500'
                          )}
                          style={{ width: `${(point.score + 1) / 2 * 100}%` }}
                        />
                      </div>
                      <span className={cn(
                        "font-mono w-16 text-right",
                        point.score > 0.3 ? 'text-green-500' :
                        point.score < -0.3 ? 'text-red-500' :
                        'text-yellow-500'
                      )}>
                        {formatPercentage(point.score)}
                      </span>
                    </div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs text-gray-500">
                        B:{formatPercentage(point.bullish / 100)}
                      </span>
                      <span className="text-xs text-gray-500">
                        N:{formatPercentage(point.neutral / 100)}
                      </span>
                      <span className="text-xs text-gray-500">
                        B:{formatPercentage(point.bearish / 100)}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </TabsContent>
          </Tabs>

          <div className="flex justify-end gap-2 pt-4 border-t border-gray-700">
            <Button
              variant="outline"
              onClick={handleShare}
              className="border-gray-600 hover:border-cyan-500"
            >
              <Share2 className="w-4 h-4 mr-2" />
              Share
            </Button>
            <Button
              variant="outline"
              onClick={handleExport}
              className="border-gray-600 hover:border-cyan-500"
            >
              <Download className="w-4 h-4 mr-2" />
              Export
            </Button>
            <Button
              variant="primary"
              onClick={() => setShowDetailsModal(false)}
              className="bg-gradient-to-r from-cyan-500 to-blue-500"
            >
              Close
            </Button>
          </div>
        </div>
      </Modal>

      {/* ============================================ */}
      {/* Source Detail Modal */}
      {/* ============================================ */}
      <Modal
        open={!!selectedSource}
        onOpenChange={() => setSelectedSource(null)}
        title={selectedSource?.name || 'Source Details'}
        className="max-w-md"
      >
        {selectedSource && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <span className="text-sm text-gray-400">Sentiment Score</span>
              <Badge className={cn(
                "text-sm",
                selectedSource.score > 0.3 ? 'bg-green-500/20 text-green-500' :
                selectedSource.score < -0.3 ? 'bg-red-500/20 text-red-500' :
                'bg-yellow-500/20 text-yellow-500'
              )}>
                {formatPercentage(selectedSource.score)}
              </Badge>
            </div>
            <div className="flex items-center justify-between text-sm">
              <span className="text-gray-400">Weight</span>
              <span className="text-white">{formatPercentage(selectedSource.weight)}</span>
            </div>
            {selectedSource.data && Object.keys(selectedSource.data).length > 0 && (
              <div className="p-3 bg-gray-700/30 rounded-lg">
                <h4 className="text-sm font-medium text-gray-300 mb-2">Additional Data</h4>
                <div className="space-y-1 text-sm">
                  {Object.entries(selectedSource.data).map(([key, value]) => (
                    <div key={key} className="flex justify-between">
                      <span className="text-gray-400">{key}</span>
                      <span className="text-white">{String(value)}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div className="flex justify-end">
              <Button
                variant="outline"
                onClick={handleCloseSource}
                className="border-gray-600 hover:border-gray-500"
              >
                Close
              </Button>
            </div>
          </div>
        )}
      </Modal>

      {/* ============================================ */}
      {/* Toast Notifications */}
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
    </>
  );
}

// ============================================
// Export
// ============================================

export default SentimentIndicator;

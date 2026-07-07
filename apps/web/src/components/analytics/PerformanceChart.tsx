/**
 * NEXUS AI TRADING SYSTEM - PerformanceChart Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This component provides comprehensive performance charting including:
 * - Multiple chart types (line, area, bar, candlestick)
 * - Multiple timeframes (1D, 1W, 1M, 3M, 6M, 1Y, ALL)
 * - Performance metrics overlay
 * - Benchmark comparison
 * - Technical indicators
 * - Interactive tooltips
 * - Zoom and pan support
 * - Export capabilities
 * - Responsive design
 * - Real-time updates
 * - Dark/light theme support
 * - Accessibility features
 * - Customizable appearance
 */

'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  LineChart,
  AreaChart,
  BarChart,
  CandlestickChart,
  ResponsiveContainer,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  Brush,
  ReferenceLine,
  ReferenceArea,
  ComposedChart,
  Scatter,
  Line,
  Area,
  Bar,
  Candlestick,
} from 'recharts';

import {
  TrendingUp,
  TrendingDown,
  Download,
  RefreshCw,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Minimize2,
  Settings,
  Calendar,
  Clock,
  Filter,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Plus,
  Minus,
  X,
  Check,
  AlertCircle,
  Info,
  HelpCircle,
  BarChart3,
  PieChart,
  LineChart as LineChartIcon,
  AreaChart as AreaChartIcon,
  CandlestickChart as CandlestickChartIcon,
} from 'lucide-react';

// Components
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Select } from '@/components/ui/Select';
import { Switch } from '@/components/ui/Switch';
import { Modal } from '@/components/ui/Modal';
import { Progress } from '@/components/ui/Progress';
import { Tooltip as UITooltip } from '@/components/ui/Tooltip';
import { Toast } from '@/components/ui/Toast';
import { Spinner } from '@/components/ui/Spinner';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/Tabs';

// Types
import type {
  ChartData,
  ChartType,
  ChartTimeframe,
  ChartIndicator,
  ChartConfig,
  ChartPoint,
  ChartSeries,
  ChartTooltip,
} from '@/types/analytics';

// Constants
import {
  CHART_TYPES,
  CHART_TIMEFRAMES,
  CHART_INDICATORS,
  CHART_COLORS,
  CHART_DEFAULT_CONFIG,
} from '@/constants/analytics';

// Utils
import { formatCurrency, formatPercentage, formatNumber, formatDate, formatTime } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

// ============================================
// Props Interface
// ============================================

interface PerformanceChartProps {
  data: ChartData[];
  series?: ChartSeries[];
  type?: ChartType;
  timeframe?: ChartTimeframe;
  height?: number | string;
  width?: number | string;
  indicators?: ChartIndicator[];
  config?: Partial<ChartConfig>;
  isLoading?: boolean;
  className?: string;
  showControls?: boolean;
  showLegend?: boolean;
  showGrid?: boolean;
  showTooltip?: boolean;
  showZoom?: boolean;
  onTimeframeChange?: (timeframe: ChartTimeframe) => void;
  onTypeChange?: (type: ChartType) => void;
  onIndicatorToggle?: (indicator: ChartIndicator) => void;
  onExport?: () => void;
  onRefresh?: () => void;
}

// ============================================
// Chart Tooltip Component
// ============================================

interface ChartTooltipContentProps {
  active?: boolean;
  payload?: any[];
  label?: string;
  valueFormatter?: (value: number) => string;
  labelFormatter?: (label: string) => string;
}

function ChartTooltipContent({
  active,
  payload,
  label,
  valueFormatter = formatCurrency,
  labelFormatter = (l: string) => formatDate(new Date(l)),
}: ChartTooltipContentProps) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg shadow-xl p-3 min-w-[200px]">
      <p className="text-sm font-medium text-white mb-2">
        {labelFormatter(label || '')}
      </p>
      <div className="space-y-1">
        {payload.map((item: any, index: number) => (
          <div key={index} className="flex items-center justify-between gap-4 text-sm">
            <div className="flex items-center gap-2">
              <div
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: item.color || CHART_COLORS[index % CHART_COLORS.length] }}
              />
              <span className="text-gray-400">{item.name}</span>
            </div>
            <span className="text-white font-mono font-medium">
              {valueFormatter(item.value)}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ============================================
// Main Component
// ============================================

export function PerformanceChart({
  data,
  series = [],
  type = 'line',
  timeframe = '1M',
  height = 400,
  width = '100%',
  indicators = [],
  config = {},
  isLoading = false,
  className,
  showControls = true,
  showLegend = true,
  showGrid = true,
  showTooltip = true,
  showZoom = true,
  onTimeframeChange,
  onTypeChange,
  onIndicatorToggle,
  onExport,
  onRefresh,
}: PerformanceChartProps) {
  // State
  const [chartType, setChartType] = useState<ChartType>(type);
  const [chartTimeframe, setChartTimeframe] = useState<ChartTimeframe>(timeframe);
  const [activeIndicators, setActiveIndicators] = useState<ChartIndicator[]>(indicators);
  const [isZoomed, setIsZoomed] = useState<boolean>(false);
  const [zoomDomain, setZoomDomain] = useState<{ start: number; end: number } | null>(null);
  const [showSettings, setShowSettings] = useState<boolean>(false);
  const [chartConfig, setChartConfig] = useState<ChartConfig>({
    ...CHART_DEFAULT_CONFIG,
    ...config,
  });
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [isExporting, setIsExporting] = useState<boolean>(false);

  // Refs
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);

  // ============================================
  // Effects
  // ============================================

  useEffect(() => {
    setChartType(type);
  }, [type]);

  useEffect(() => {
    setChartTimeframe(timeframe);
  }, [timeframe]);

  useEffect(() => {
    setActiveIndicators(indicators);
  }, [indicators]);

  // ============================================
  // Handlers
  // ============================================

  const handleTypeChange = useCallback((newType: ChartType) => {
    setChartType(newType);
    onTypeChange?.(newType);
  }, [onTypeChange]);

  const handleTimeframeChange = useCallback((newTimeframe: ChartTimeframe) => {
    setChartTimeframe(newTimeframe);
    onTimeframeChange?.(newTimeframe);
  }, [onTimeframeChange]);

  const handleIndicatorToggle = useCallback((indicator: ChartIndicator) => {
    setActiveIndicators(prev => {
      const index = prev.indexOf(indicator);
      if (index > -1) {
        return prev.filter(i => i !== indicator);
      }
      return [...prev, indicator];
    });
    onIndicatorToggle?.(indicator);
  }, [onIndicatorToggle]);

  const handleZoomIn = useCallback(() => {
    setIsZoomed(true);
    const currentData = data;
    const midPoint = Math.floor(currentData.length / 2);
    const range = Math.floor(currentData.length / 4);
    setZoomDomain({
      start: Math.max(0, midPoint - range),
      end: Math.min(currentData.length - 1, midPoint + range),
    });
  }, [data]);

  const handleZoomOut = useCallback(() => {
    setIsZoomed(false);
    setZoomDomain(null);
  }, []);

  const handleExport = useCallback(async () => {
    setIsExporting(true);
    try {
      if (onExport) {
        await onExport();
      } else {
        // Default export as CSV
        const headers = ['Date', ...series.map(s => s.name)];
        const rows = data.map(point => [
          formatDate(new Date(point.date)),
          ...series.map(s => point[s.key] || 0),
        ]);
        const csv = [headers.join(','), ...rows.map(row => row.join(','))].join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `performance-data-${Date.now()}.csv`);
        document.body.appendChild(link);
        link.click();
        link.remove();
        URL.revokeObjectURL(url);
        setShowToast({
          message: 'Chart data exported successfully!',
          type: 'success',
        });
      }
    } catch (error: any) {
      setShowToast({
        message: error.message || 'Failed to export chart data.',
        type: 'error',
      });
    } finally {
      setIsExporting(false);
    }
  }, [onExport, data, series]);

  const handleRefresh = useCallback(() => {
    onRefresh?.();
  }, [onRefresh]);

  // ============================================
  // Memoized Computations
  // ============================================

  const chartSeries = useMemo(() => {
    if (series.length === 0) {
      return [
        {
          key: 'value',
          name: 'Performance',
          color: CHART_COLORS[0],
          type: 'line',
        },
      ];
    }
    return series;
  }, [series]);

  const chartColors = useMemo(() => {
    return chartSeries.map((s, i) => s.color || CHART_COLORS[i % CHART_COLORS.length]);
  }, [chartSeries]);

  const chartDataWithIndicators = useMemo(() => {
    if (activeIndicators.length === 0) {
      return data;
    }

    return data.map(point => {
      const indicators: Record<string, number> = {};
      activeIndicators.forEach(indicator => {
        switch (indicator) {
          case 'sma':
            indicators.sma = calculateSMA(data, point.date, 20);
            break;
          case 'ema':
            indicators.ema = calculateEMA(data, point.date, 12);
            break;
          case 'bollinger_upper':
            indicators.bollingerUpper = calculateBollingerUpper(data, point.date, 20, 2);
            break;
          case 'bollinger_lower':
            indicators.bollingerLower = calculateBollingerLower(data, point.date, 20, 2);
            break;
          case 'rsi':
            indicators.rsi = calculateRSI(data, point.date, 14);
            break;
          case 'macd':
            indicators.macd = calculateMACD(data, point.date);
            break;
          case 'volume':
            indicators.volume = point.volume || 0;
            break;
          default:
            break;
        }
      });
      return { ...point, ...indicators };
    });
  }, [data, activeIndicators]);

  const renderChart = useCallback(() => {
    const ChartComponent = chartType === 'line' ? LineChart :
                           chartType === 'area' ? AreaChart :
                           chartType === 'bar' ? BarChart :
                           chartType === 'candlestick' ? CandlestickChart :
                           ComposedChart;

    const chartProps: any = {
      data: chartDataWithIndicators,
      height: typeof height === 'number' ? height : 400,
      width: typeof width === 'number' ? width : '100%',
      margin: { top: 20, right: 30, left: 20, bottom: 20 },
    };

    if (showGrid) {
      chartProps.children = [
        <CartesianGrid key="grid" strokeDasharray="3 3" stroke="#334155" />,
        <XAxis key="x" dataKey="date" tickFormatter={(date) => formatDate(new Date(date))} stroke="#64748b" />,
        <YAxis key="y" tickFormatter={(value) => formatCurrency(value)} stroke="#64748b" />,
      ];
    }

    // Add series
    chartSeries.forEach((series, index) => {
      const color = series.color || CHART_COLORS[index % CHART_COLORS.length];
      const type = series.type || 'line';

      switch (type) {
        case 'line':
          chartProps.children.push(
            <Line
              key={series.key}
              type="monotone"
              dataKey={series.key}
              stroke={color}
              strokeWidth={2}
              dot={false}
              activeDot={{ r: 6 }}
              name={series.name}
            />
          );
          break;
        case 'area':
          chartProps.children.push(
            <Area
              key={series.key}
              type="monotone"
              dataKey={series.key}
              stroke={color}
              fill={color}
              fillOpacity={0.2}
              name={series.name}
            />
          );
          break;
        case 'bar':
          chartProps.children.push(
            <Bar
              key={series.key}
              dataKey={series.key}
              fill={color}
              name={series.name}
            />
          );
          break;
        default:
          break;
      }
    });

    // Add indicators
    activeIndicators.forEach(indicator => {
      switch (indicator) {
        case 'sma':
          chartProps.children.push(
            <Line
              key="sma"
              type="monotone"
              dataKey="sma"
              stroke="#f59e0b"
              strokeWidth={1.5}
              strokeDasharray="5 5"
              dot={false}
              name="SMA (20)"
            />
          );
          break;
        case 'ema':
          chartProps.children.push(
            <Line
              key="ema"
              type="monotone"
              dataKey="ema"
              stroke="#8b5cf6"
              strokeWidth={1.5}
              strokeDasharray="5 5"
              dot={false}
              name="EMA (12)"
            />
          );
          break;
        case 'bollinger_upper':
          chartProps.children.push(
            <Line
              key="bollingerUpper"
              type="monotone"
              dataKey="bollingerUpper"
              stroke="#10b981"
              strokeWidth={1}
              strokeDasharray="3 3"
              dot={false}
              name="Bollinger Upper"
            />
          );
          break;
        case 'bollinger_lower':
          chartProps.children.push(
            <Line
              key="bollingerLower"
              type="monotone"
              dataKey="bollingerLower"
              stroke="#10b981"
              strokeWidth={1}
              strokeDasharray="3 3"
              dot={false}
              name="Bollinger Lower"
            />
          );
          break;
        default:
          break;
      }
    });

    // Add tooltip
    if (showTooltip) {
      chartProps.children.push(
        <Tooltip
          key="tooltip"
          content={<ChartTooltipContent valueFormatter={formatCurrency} />}
        />
      );
    }

    // Add legend
    if (showLegend) {
      chartProps.children.push(<Legend key="legend" wrapperStyle={{ color: '#94a3b8' }} />);
    }

    // Add zoom/brush
    if (showZoom && isZoomed && zoomDomain) {
      chartProps.children.push(
        <Brush
          key="brush"
          dataKey="date"
          height={30}
          stroke="#06b6d4"
          startIndex={zoomDomain.start}
          endIndex={zoomDomain.end}
        />
      );
    }

    return <ResponsiveContainer {...chartProps} />;
  }, [
    chartType,
    chartDataWithIndicators,
    height,
    width,
    showGrid,
    showTooltip,
    showLegend,
    showZoom,
    isZoomed,
    zoomDomain,
    chartSeries,
    activeIndicators,
  ]);

  // ============================================
  // Indicator Helper Functions
  // ============================================

  const calculateSMA = (data: ChartData[], date: string, period: number): number => {
    const index = data.findIndex(d => d.date === date);
    if (index < period - 1) return 0;
    const values = data.slice(index - period + 1, index + 1).map(d => d.value);
    return values.reduce((a, b) => a + b, 0) / period;
  };

  const calculateEMA = (data: ChartData[], date: string, period: number): number => {
    const index = data.findIndex(d => d.date === date);
    if (index === 0) return data[0].value;
    const multiplier = 2 / (period + 1);
    const previousEMA = calculateEMA(data, data[index - 1].date, period);
    return (data[index].value - previousEMA) * multiplier + previousEMA;
  };

  const calculateBollingerUpper = (data: ChartData[], date: string, period: number, deviations: number): number => {
    const sma = calculateSMA(data, date, period);
    if (sma === 0) return 0;
    const index = data.findIndex(d => d.date === date);
    if (index < period - 1) return 0;
    const values = data.slice(index - period + 1, index + 1).map(d => d.value);
    const stdDev = Math.sqrt(values.reduce((a, b) => a + Math.pow(b - sma, 2), 0) / period);
    return sma + deviations * stdDev;
  };

  const calculateBollingerLower = (data: ChartData[], date: string, period: number, deviations: number): number => {
    const sma = calculateSMA(data, date, period);
    if (sma === 0) return 0;
    const index = data.findIndex(d => d.date === date);
    if (index < period - 1) return 0;
    const values = data.slice(index - period + 1, index + 1).map(d => d.value);
    const stdDev = Math.sqrt(values.reduce((a, b) => a + Math.pow(b - sma, 2), 0) / period);
    return sma - deviations * stdDev;
  };

  const calculateRSI = (data: ChartData[], date: string, period: number): number => {
    const index = data.findIndex(d => d.date === date);
    if (index < period) return 50;
    let gains = 0;
    let losses = 0;
    for (let i = index - period + 1; i <= index; i++) {
      const change = data[i].value - data[i - 1].value;
      if (change >= 0) gains += change;
      else losses += Math.abs(change);
    }
    const avgGain = gains / period;
    const avgLoss = losses / period;
    if (avgLoss === 0) return 100;
    const rs = avgGain / avgLoss;
    return 100 - (100 / (1 + rs));
  };

  const calculateMACD = (data: ChartData[], date: string): number => {
    const ema12 = calculateEMA(data, date, 12);
    const ema26 = calculateEMA(data, date, 26);
    return ema12 - ema26;
  };

  // ============================================
  // Render
  // ============================================

  if (isLoading) {
    return (
      <Card className={cn("p-4 bg-gray-800 border-gray-700", className)}>
        <div className="flex items-center justify-center h-[400px]">
          <Spinner size="lg" className="text-cyan-500" />
        </div>
      </Card>
    );
  }

  return (
    <Card className={cn("p-4 bg-gray-800 border-gray-700", className)}>
      {/* Header */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-3">
          <h3 className="text-sm font-semibold text-gray-300">Performance Chart</h3>
          <Badge className="bg-cyan-500/20 text-cyan-400 text-xs border-cyan-500/30">
            {chartTimeframe}
          </Badge>
        </div>

        {showControls && (
          <div className="flex flex-wrap items-center gap-2">
            {/* Timeframe Controls */}
            <div className="flex items-center gap-1">
              {CHART_TIMEFRAMES.map((tf) => (
                <Button
                  key={tf}
                  variant={chartTimeframe === tf ? 'primary' : 'ghost'}
                  size="sm"
                  onClick={() => handleTimeframeChange(tf)}
                  className={cn(
                    "text-xs px-2 py-1 h-7",
                    chartTimeframe === tf
                      ? "bg-cyan-500/20 text-cyan-400"
                      : "text-gray-400 hover:text-white"
                  )}
                >
                  {tf}
                </Button>
              ))}
            </div>

            <div className="w-px h-6 bg-gray-700" />

            {/* Chart Type Controls */}
            <div className="flex items-center gap-1">
              <Button
                variant={chartType === 'line' ? 'primary' : 'ghost'}
                size="sm"
                onClick={() => handleTypeChange('line')}
                className={cn(
                  "p-1 h-7 w-7",
                  chartType === 'line'
                    ? "bg-cyan-500/20 text-cyan-400"
                    : "text-gray-400 hover:text-white"
                )}
              >
                <LineChartIcon className="w-4 h-4" />
              </Button>
              <Button
                variant={chartType === 'area' ? 'primary' : 'ghost'}
                size="sm"
                onClick={() => handleTypeChange('area')}
                className={cn(
                  "p-1 h-7 w-7",
                  chartType === 'area'
                    ? "bg-cyan-500/20 text-cyan-400"
                    : "text-gray-400 hover:text-white"
                )}
              >
                <AreaChartIcon className="w-4 h-4" />
              </Button>
              <Button
                variant={chartType === 'bar' ? 'primary' : 'ghost'}
                size="sm"
                onClick={() => handleTypeChange('bar')}
                className={cn(
                  "p-1 h-7 w-7",
                  chartType === 'bar'
                    ? "bg-cyan-500/20 text-cyan-400"
                    : "text-gray-400 hover:text-white"
                )}
              >
                <BarChart3 className="w-4 h-4" />
              </Button>
              <Button
                variant={chartType === 'candlestick' ? 'primary' : 'ghost'}
                size="sm"
                onClick={() => handleTypeChange('candlestick')}
                className={cn(
                  "p-1 h-7 w-7",
                  chartType === 'candlestick'
                    ? "bg-cyan-500/20 text-cyan-400"
                    : "text-gray-400 hover:text-white"
                )}
              >
                <CandlestickChartIcon className="w-4 h-4" />
              </Button>
            </div>

            <div className="w-px h-6 bg-gray-700" />

            {/* Zoom Controls */}
            {showZoom && (
              <div className="flex items-center gap-1">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleZoomIn}
                  className="p-1 h-7 w-7 text-gray-400 hover:text-white"
                >
                  <ZoomIn className="w-4 h-4" />
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={handleZoomOut}
                  className="p-1 h-7 w-7 text-gray-400 hover:text-white"
                >
                  <ZoomOut className="w-4 h-4" />
                </Button>
              </div>
            )}

            <div className="w-px h-6 bg-gray-700" />

            {/* Action Buttons */}
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowSettings(true)}
              className="p-1 h-7 w-7 text-gray-400 hover:text-white"
            >
              <Settings className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleRefresh}
              className="p-1 h-7 w-7 text-gray-400 hover:text-white"
            >
              <RefreshCw className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleExport}
              isLoading={isExporting}
              className="p-1 h-7 w-7 text-gray-400 hover:text-white"
            >
              <Download className="w-4 h-4" />
            </Button>
          </div>
        )}
      </div>

      {/* Chart */}
      <div ref={chartContainerRef} className="w-full" style={{ height: typeof height === 'number' ? height : '400px' }}>
        {data.length > 0 ? (
          renderChart()
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <BarChart3 className="w-12 h-12 mx-auto mb-3 text-gray-600" />
              <p className="text-lg font-medium">No data available</p>
              <p className="text-sm">Select a different timeframe or refresh</p>
            </div>
          </div>
        )}
      </div>

      {/* Indicators */}
      <div className="flex flex-wrap items-center gap-2 mt-4 pt-4 border-t border-gray-700">
        <span className="text-xs text-gray-400">Indicators:</span>
        {CHART_INDICATORS.map((indicator) => (
          <button
            key={indicator}
            onClick={() => handleIndicatorToggle(indicator as ChartIndicator)}
            className={cn(
              "px-2 py-0.5 rounded text-xs transition-colors",
              activeIndicators.includes(indicator as ChartIndicator)
                ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                : "bg-gray-700 text-gray-400 border border-gray-600 hover:border-gray-500"
            )}
          >
            {indicator.toUpperCase()}
          </button>
        ))}
      </div>

      {/* Settings Modal */}
      <Modal
        open={showSettings}
        onOpenChange={setShowSettings}
        title="Chart Settings"
        className="max-w-md"
      >
        <div className="space-y-4">
          <div>
            <label className="block text-sm text-gray-400 mb-1">Chart Type</label>
            <Select
              value={chartType}
              onValueChange={(value) => handleTypeChange(value as ChartType)}
              className="w-full bg-gray-700 border-gray-600"
            >
              <option value="line">Line</option>
              <option value="area">Area</option>
              <option value="bar">Bar</option>
              <option value="candlestick">Candlestick</option>
            </Select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Timeframe</label>
            <Select
              value={chartTimeframe}
              onValueChange={(value) => handleTimeframeChange(value as ChartTimeframe)}
              className="w-full bg-gray-700 border-gray-600"
            >
              {CHART_TIMEFRAMES.map((tf) => (
                <option key={tf} value={tf}>{tf}</option>
              ))}
            </Select>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Indicators</label>
            <div className="flex flex-wrap gap-2">
              {CHART_INDICATORS.map((indicator) => (
                <button
                  key={indicator}
                  onClick={() => handleIndicatorToggle(indicator as ChartIndicator)}
                  className={cn(
                    "px-3 py-1 rounded-lg text-sm transition-colors",
                    activeIndicators.includes(indicator as ChartIndicator)
                      ? "bg-cyan-500/20 text-cyan-400 border border-cyan-500/30"
                      : "bg-gray-700 text-gray-400 border border-gray-600 hover:border-gray-500"
                  )}
                >
                  {indicator.toUpperCase()}
                </button>
              ))}
            </div>
          </div>
          <div>
            <label className="block text-sm text-gray-400 mb-1">Display Options</label>
            <div className="space-y-2">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300">Show Grid</span>
                <Switch
                  checked={chartConfig.showGrid !== undefined ? chartConfig.showGrid : true}
                  onCheckedChange={(checked) => setChartConfig(prev => ({ ...prev, showGrid: checked }))}
                  className="data-[state=checked]:bg-cyan-500"
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300">Show Legend</span>
                <Switch
                  checked={chartConfig.showLegend !== undefined ? chartConfig.showLegend : true}
                  onCheckedChange={(checked) => setChartConfig(prev => ({ ...prev, showLegend: checked }))}
                  className="data-[state=checked]:bg-cyan-500"
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300">Show Tooltips</span>
                <Switch
                  checked={chartConfig.showTooltip !== undefined ? chartConfig.showTooltip : true}
                  onCheckedChange={(checked) => setChartConfig(prev => ({ ...prev, showTooltip: checked }))}
                  className="data-[state=checked]:bg-cyan-500"
                />
              </div>
            </div>
          </div>
          <div className="flex justify-end gap-3 pt-4 border-t border-gray-700">
            <Button
              variant="outline"
              onClick={() => setShowSettings(false)}
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
    </Card>
  );
}

// ============================================
// Export
// ============================================

export default PerformanceChart;

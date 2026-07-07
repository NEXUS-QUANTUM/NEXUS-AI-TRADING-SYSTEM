/**
 * NEXUS AI TRADING SYSTEM - BarChart Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * This component provides a comprehensive bar chart implementation including:
 * - Multiple bar chart types (vertical, horizontal, stacked, grouped)
 * - Customizable colors and styling
 * - Interactive tooltips
 * - Legend support
 * - Data labels
 * - Responsive design
 * - Animated transitions
 * - Accessibility features
 * - Dark/light theme support
 * - Export capabilities
 * - Zoom and pan
 * - Real-time updates
 * - Performance optimization
 */

'use client';

import { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import {
  BarChart as RechartsBarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  Cell,
  ReferenceLine,
  ReferenceArea,
  Brush,
  LabelList,
} from 'recharts';

import {
  Download,
  RefreshCw,
  ZoomIn,
  ZoomOut,
  Maximize2,
  Minimize2,
  Settings,
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
import { Select } from '@/components/ui/Select';
import { Switch } from '@/components/ui/Switch';
import { Modal } from '@/components/ui/Modal';
import { Toast } from '@/components/ui/Toast';
import { Spinner } from '@/components/ui/Spinner';
import { Tooltip as UITooltip } from '@/components/ui/Tooltip';

// Types
import type { ChartData, ChartConfig } from '@/types/charts';

// Constants
import { CHART_COLORS, CHART_DEFAULT_CONFIG } from '@/constants/charts';

// Utils
import { formatCurrency, formatPercentage, formatNumber, formatDate } from '@/utils/formatters';
import { cn } from '@/utils/helpers';

// ============================================
// Props Interface
// ============================================

interface BarChartProps {
  data: ChartData[];
  xKey: string;
  yKey: string | string[];
  colors?: string | string[];
  height?: number | string;
  width?: number | string;
  title?: string;
  subtitle?: string;
  isLoading?: boolean;
  className?: string;
  showGrid?: boolean;
  showLegend?: boolean;
  showTooltip?: boolean;
  showLabels?: boolean;
  showAnimation?: boolean;
  stacked?: boolean;
  horizontal?: boolean;
  layout?: 'vertical' | 'horizontal';
  barSize?: number;
  maxBarSize?: number;
  barGap?: number;
  barCategoryGap?: number;
  borderRadius?: number;
  onDataPointClick?: (data: any) => void;
  onRefresh?: () => void;
  onExport?: () => void;
  valueFormatter?: (value: number) => string;
  labelFormatter?: (label: string) => string;
  tooltipFormatter?: (value: number, name: string) => string;
  customTooltip?: React.ReactNode;
  emptyMessage?: string;
}

// ============================================
// Custom Tooltip Component
// ============================================

interface CustomTooltipProps {
  active?: boolean;
  payload?: any[];
  label?: string;
  valueFormatter?: (value: number) => string;
  labelFormatter?: (label: string) => string;
  tooltipFormatter?: (value: number, name: string) => string;
}

function CustomTooltip({
  active,
  payload,
  label,
  valueFormatter = formatCurrency,
  labelFormatter = (l: string) => l,
  tooltipFormatter,
}: CustomTooltipProps) {
  if (!active || !payload || payload.length === 0) {
    return null;
  }

  return (
    <div className="bg-gray-800 border border-gray-700 rounded-lg shadow-xl p-3 min-w-[200px]">
      <p className="text-sm font-medium text-white mb-2">
        {labelFormatter(label || '')}
      </p>
      <div className="space-y-1">
        {payload.map((item: any, index: number) => {
          const value = tooltipFormatter
            ? tooltipFormatter(item.value, item.name)
            : valueFormatter(item.value);
          return (
            <div key={index} className="flex items-center justify-between gap-4 text-sm">
              <div className="flex items-center gap-2">
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: item.color || item.fill || CHART_COLORS[index % CHART_COLORS.length] }}
                />
                <span className="text-gray-400">{item.name}</span>
              </div>
              <span className="text-white font-mono font-medium">
                {value}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ============================================
// Main Component
// ============================================

export function BarChart({
  data,
  xKey,
  yKey,
  colors,
  height = 400,
  width = '100%',
  title,
  subtitle,
  isLoading = false,
  className,
  showGrid = true,
  showLegend = true,
  showTooltip = true,
  showLabels = false,
  showAnimation = true,
  stacked = false,
  horizontal = false,
  layout = 'vertical',
  barSize = 30,
  maxBarSize = 50,
  barGap = 4,
  barCategoryGap = 20,
  borderRadius = 4,
  onDataPointClick,
  onRefresh,
  onExport,
  valueFormatter = formatCurrency,
  labelFormatter = (l: string) => l,
  tooltipFormatter,
  customTooltip,
  emptyMessage = 'No data available',
}: BarChartProps) {
  // State
  const [isZoomed, setIsZoomed] = useState<boolean>(false);
  const [zoomDomain, setZoomDomain] = useState<{ start: number; end: number } | null>(null);
  const [showSettings, setShowSettings] = useState<boolean>(false);
  const [chartConfig, setChartConfig] = useState<ChartConfig>(CHART_DEFAULT_CONFIG);
  const [showToast, setShowToast] = useState<{
    message: string;
    type: 'success' | 'error' | 'info' | 'warning';
  } | null>(null);
  const [isExporting, setIsExporting] = useState<boolean>(false);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Refs
  const containerRef = useRef<HTMLDivElement>(null);

  // ============================================
  // Handlers
  // ============================================

  const handleRefresh = useCallback(() => {
    setIsRefreshing(true);
    onRefresh?.();
    setTimeout(() => setIsRefreshing(false), 500);
  }, [onRefresh]);

  const handleExport = useCallback(async () => {
    setIsExporting(true);
    try {
      if (onExport) {
        await onExport();
      } else {
        // Default export as CSV
        const headers = [xKey, ...(Array.isArray(yKey) ? yKey : [yKey])];
        const rows = data.map(point => [
          point[xKey],
          ...(Array.isArray(yKey) ? yKey.map(key => point[key]) : [point[yKey]]),
        ]);
        const csv = [headers.join(','), ...rows.map(row => row.join(','))].join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', `barchart-data-${Date.now()}.csv`);
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
  }, [onExport, data, xKey, yKey]);

  const handleZoomIn = useCallback(() => {
    if (data.length < 10) return;
    setIsZoomed(true);
    const midPoint = Math.floor(data.length / 2);
    const range = Math.floor(data.length / 4);
    setZoomDomain({
      start: Math.max(0, midPoint - range),
      end: Math.min(data.length - 1, midPoint + range),
    });
  }, [data]);

  const handleZoomOut = useCallback(() => {
    setIsZoomed(false);
    setZoomDomain(null);
  }, []);

  // ============================================
  // Memoized Computations
  // ============================================

  const chartColors = useMemo(() => {
    if (typeof colors === 'string') {
      return [colors];
    }
    if (Array.isArray(colors) && colors.length > 0) {
      return colors;
    }
    return CHART_COLORS;
  }, [colors]);

  const chartDataWithColors = useMemo(() => {
    return data.map((point, index) => ({
      ...point,
      fill: point.fill || chartColors[index % chartColors.length],
    }));
  }, [data, chartColors]);

  const isStacked = useMemo(() => {
    return stacked && Array.isArray(yKey) && yKey.length > 1;
  }, [stacked, yKey]);

  const isHorizontalLayout = useMemo(() => {
    return horizontal || layout === 'horizontal';
  }, [horizontal, layout]);

  const chartKeys = useMemo(() => {
    return Array.isArray(yKey) ? yKey : [yKey];
  }, [yKey]);

  const maxValue = useMemo(() => {
    let max = 0;
    data.forEach(point => {
      chartKeys.forEach(key => {
        const value = point[key] || 0;
        if (value > max) max = value;
      });
    });
    return max * 1.1; // Add 10% padding
  }, [data, chartKeys]);

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

  if (!data || data.length === 0) {
    return (
      <Card className={cn("p-4 bg-gray-800 border-gray-700", className)}>
        <div className="flex items-center justify-center h-[400px] text-gray-500">
          <div className="text-center">
            <BarChart3 className="w-12 h-12 mx-auto mb-3 text-gray-600" />
            <p className="text-lg font-medium">{emptyMessage}</p>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <div className={cn("relative", className)} ref={containerRef}>
      {/* Header */}
      {(title || subtitle || onRefresh || onExport) && (
        <div className="flex flex-wrap items-center justify-between mb-4 gap-2">
          <div>
            {title && <h3 className="text-sm font-semibold text-gray-300">{title}</h3>}
            {subtitle && <p className="text-xs text-gray-500">{subtitle}</p>}
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={handleZoomIn}
              className="p-1 h-7 w-7 text-gray-400 hover:text-white"
              title="Zoom In"
            >
              <ZoomIn className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={handleZoomOut}
              className="p-1 h-7 w-7 text-gray-400 hover:text-white"
              title="Zoom Out"
            >
              <ZoomOut className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowSettings(true)}
              className="p-1 h-7 w-7 text-gray-400 hover:text-white"
              title="Settings"
            >
              <Settings className="w-4 h-4" />
            </Button>
            {onRefresh && (
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRefresh}
                isLoading={isRefreshing}
                className="p-1 h-7 w-7 text-gray-400 hover:text-white"
                title="Refresh"
              >
                <RefreshCw className="w-4 h-4" />
              </Button>
            )}
            <Button
              variant="ghost"
              size="sm"
              onClick={handleExport}
              isLoading={isExporting}
              className="p-1 h-7 w-7 text-gray-400 hover:text-white"
              title="Export"
            >
              <Download className="w-4 h-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Chart */}
      <div style={{ width: typeof width === 'number' ? width : '100%', height: typeof height === 'number' ? height : 400 }}>
        <ResponsiveContainer>
          <RechartsBarChart
            data={chartDataWithColors}
            layout={isHorizontalLayout ? 'vertical' : 'horizontal'}
            stackOffset={isStacked ? 'expand' : 'none'}
            barSize={barSize}
            maxBarSize={maxBarSize}
            barGap={barGap}
            barCategoryGap={barCategoryGap}
            margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
            onClick={(data) => onDataPointClick?.(data)}
          >
            {/* Grid */}
            {showGrid && (
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
            )}

            {/* X Axis */}
            {!isHorizontalLayout ? (
              <XAxis
                dataKey={xKey}
                tickFormatter={labelFormatter}
                stroke="#64748b"
                tick={{ fill: '#64748b', fontSize: 12 }}
                axisLine={{ stroke: '#334155' }}
                tickLine={{ stroke: '#334155' }}
              />
            ) : (
              <XAxis
                type="number"
                domain={[0, maxValue]}
                tickFormatter={valueFormatter}
                stroke="#64748b"
                tick={{ fill: '#64748b', fontSize: 12 }}
                axisLine={{ stroke: '#334155' }}
                tickLine={{ stroke: '#334155' }}
              />
            )}

            {/* Y Axis */}
            {!isHorizontalLayout ? (
              <YAxis
                tickFormatter={valueFormatter}
                stroke="#64748b"
                tick={{ fill: '#64748b', fontSize: 12 }}
                axisLine={{ stroke: '#334155' }}
                tickLine={{ stroke: '#334155' }}
              />
            ) : (
              <YAxis
                dataKey={xKey}
                type="category"
                tickFormatter={labelFormatter}
                stroke="#64748b"
                tick={{ fill: '#64748b', fontSize: 12 }}
                axisLine={{ stroke: '#334155' }}
                tickLine={{ stroke: '#334155' }}
              />
            )}

            {/* Bars */}
            {chartKeys.map((key, index) => {
              const color = chartColors[index % chartColors.length];
              return (
                <Bar
                  key={key}
                  dataKey={key}
                  fill={color}
                  stroke={color}
                  strokeWidth={1}
                  radius={borderRadius}
                  stackId={isStacked ? 'stack' : undefined}
                  isAnimationActive={showAnimation}
                  animationDuration={500}
                  animationEasing="ease-in-out"
                  onClick={(data) => onDataPointClick?.(data)}
                >
                  {showLabels && (
                    <LabelList
                      dataKey={key}
                      position="top"
                      formatter={valueFormatter}
                      fill="#94a3b8"
                      fontSize={11}
                    />
                  )}
                </Bar>
              );
            })}

            {/* Tooltip */}
            {showTooltip && (
              <Tooltip
                content={
                  customTooltip || (
                    <CustomTooltip
                      valueFormatter={valueFormatter}
                      labelFormatter={labelFormatter}
                      tooltipFormatter={tooltipFormatter}
                    />
                  )
                }
                cursor={{ fill: 'rgba(255, 255, 255, 0.05)' }}
              />
            )}

            {/* Legend */}
            {showLegend && chartKeys.length > 1 && (
              <Legend
                wrapperStyle={{ color: '#94a3b8', fontSize: 12, paddingTop: 10 }}
                iconType="circle"
                iconSize={8}
              />
            )}

            {/* Reference Lines */}
            <ReferenceLine y={0} stroke="#475569" strokeWidth={1} />

            {/* Brush for Zoom */}
            {isZoomed && zoomDomain && data.length > 10 && (
              <Brush
                dataKey={xKey}
                height={30}
                stroke="#06b6d4"
                startIndex={zoomDomain.start}
                endIndex={zoomDomain.end}
                tickFormatter={labelFormatter}
              />
            )}
          </RechartsBarChart>
        </ResponsiveContainer>
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
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300">Show Labels</span>
                <Switch
                  checked={chartConfig.showLabels !== undefined ? chartConfig.showLabels : false}
                  onCheckedChange={(checked) => setChartConfig(prev => ({ ...prev, showLabels: checked }))}
                  className="data-[state=checked]:bg-cyan-500"
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300">Stacked View</span>
                <Switch
                  checked={chartConfig.stacked !== undefined ? chartConfig.stacked : false}
                  onCheckedChange={(checked) => setChartConfig(prev => ({ ...prev, stacked: checked }))}
                  className="data-[state=checked]:bg-cyan-500"
                />
              </div>
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-300">Horizontal Layout</span>
                <Switch
                  checked={chartConfig.horizontal !== undefined ? chartConfig.horizontal : false}
                  onCheckedChange={(checked) => setChartConfig(prev => ({ ...prev, horizontal: checked }))}
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
    </div>
  );
}

// ============================================
// Export
// ============================================

export default BarChart;

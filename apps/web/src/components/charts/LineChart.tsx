/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from '@/components/common/Card';
import { Button } from '@/components/common/Button';
import { Spinner } from '@/components/common/Spinner';
import { cn, formatPrice, formatDate, formatCompactNumber } from '@/utils/helpers';

// ============================================
// TYPES
// ============================================

interface LineDataPoint {
  time: number;
  value: number;
  label?: string;
  color?: string;
}

interface LineChartData {
  id: string;
  name: string;
  data: LineDataPoint[];
  color?: string;
  type?: 'line' | 'area' | 'step';
  fillOpacity?: number;
  strokeWidth?: number;
}

interface LineChartProps {
  data?: LineChartData[];
  title?: string;
  description?: string;
  height?: number;
  width?: number;
  showLegend?: boolean;
  showTooltip?: boolean;
  showGrid?: boolean;
  showAnimation?: boolean;
  isCurrency?: boolean;
  isPercentage?: boolean;
  className?: string;
  onDataPointClick?: (data: LineDataPoint, seriesId: string) => void;
  onHover?: (data: LineDataPoint | null) => void;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  xAxisLabel?: string;
  yAxisLabel?: string;
  timeFormat?: string;
  valueFormat?: (value: number) => string;
}

// ============================================
// COMPOSANT PRINCIPAL
// ============================================

export function LineChart({
  data: initialData = [],
  title = 'Graphique en ligne',
  description = 'Visualisation des données en temps réel',
  height = 400,
  width = 0,
  showLegend = true,
  showTooltip = true,
  showGrid = true,
  showAnimation = true,
  isCurrency = false,
  isPercentage = false,
  className = '',
  onDataPointClick,
  onHover,
  loading = false,
  error = null,
  onRetry,
  xAxisLabel,
  yAxisLabel,
  timeFormat = 'HH:mm',
  valueFormat,
}: LineChartProps) {
  // ============================================
  // RÉFÉRENCES
  // ============================================
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const svgRef = useRef<SVGSVGElement>(null);
  const tooltipRef = useRef<HTMLDivElement>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  // ============================================
  // ÉTATS
  // ============================================
  const [data, setData] = useState<LineChartData[]>(initialData);
  const [chartWidth, setChartWidth] = useState(width || 0);
  const [hoveredPoint, setHoveredPoint] = useState<{
    seriesId: string;
    index: number;
    data: LineDataPoint;
  } | null>(null);
  const [selectedPoint, setSelectedPoint] = useState<{
    seriesId: string;
    index: number;
    data: LineDataPoint;
  } | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // ============================================
  // COULEURS PAR DÉFAUT
  // ============================================
  const defaultColors = [
    '#4ECDC4', '#FF6B6B', '#45B7D1', '#96CEB4', '#FFEAA7',
    '#DDA0DD', '#FF8A80', '#80DEEA', '#C5E1A5', '#FFD54F',
    '#CE93D8', '#EF5350', '#26A69A', '#42A5F5', '#FFA726',
  ];

  // ============================================
  // FONCTIONS DE FORMATAGE
  // ============================================

  const formatValue = (value: number): string => {
    if (valueFormat) return valueFormat(value);
    if (isCurrency) return formatPrice(value);
    if (isPercentage) return `${value.toFixed(2)}%`;
    if (Math.abs(value) >= 1e9) return formatCompactNumber(value);
    if (Math.abs(value) >= 1e6) return formatCompactNumber(value);
    if (Math.abs(value) >= 1e3) return formatCompactNumber(value);
    return value.toFixed(2);
  };

  const formatTimestamp = (timestamp: number): string => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('fr-FR', {
      hour: '2-digit',
      minute: '2-digit',
      ...(timeFormat.includes('second') ? { second: '2-digit' } : {}),
    });
  };

  // ============================================
  // CALCULS DE RENDU
  // ============================================

  const getMinMax = useCallback(() => {
    let min = Infinity;
    let max = -Infinity;

    data.forEach((series) => {
      series.data.forEach((point) => {
        if (point.value < min) min = point.value;
        if (point.value > max) max = point.value;
      });
    });

    const padding = (max - min) * 0.1 || 1;
    return {
      min: min - padding,
      max: max + padding,
    };
  }, [data]);

  const getXScale = useCallback(
    (width: number) => {
      const allPoints = data.flatMap((d) => d.data);
      if (allPoints.length === 0) return { min: 0, max: 1 };
      const minTime = Math.min(...allPoints.map((p) => p.time));
      const maxTime = Math.max(...allPoints.map((p) => p.time));
      return { min: minTime, max: maxTime };
    },
    [data]
  );

  const getYScale = useCallback(
    (height: number, min: number, max: number) => {
      return {
        min,
        max,
        getY: (value: number) => height - ((value - min) / (max - min)) * height,
      };
    },
    []
  );

  const getX = useCallback(
    (width: number, time: number, xScale: { min: number; max: number }) => {
      return ((time - xScale.min) / (xScale.max - xScale.min)) * width;
    },
    []
  );

  // ============================================
  // RENDU DU GRAPHIQUE
  // ============================================

  const renderGrid = useCallback(
    (width: number, height: number, yScale: { min: number; max: number }) => {
      if (!showGrid) return null;

      const lines = 5;
      const gridLines = [];

      for (let i = 0; i <= lines; i++) {
        const ratio = i / lines;
        const y = height - ratio * height;
        const value = yScale.min + ratio * (yScale.max - yScale.min);

        gridLines.push(
          <g key={`grid-${i}`}>
            <line
              x1={0}
              y1={y}
              x2={width}
              y2={y}
              stroke="rgba(197, 203, 206, 0.3)"
              strokeWidth={1}
              strokeDasharray={i % 2 === 0 ? '0' : '4,4'}
            />
            <text
              x={5}
              y={y - 5}
              fill="#888"
              fontSize="11"
              dominantBaseline="auto"
            >
              {formatValue(value)}
            </text>
          </g>
        );
      }

      return gridLines;
    },
    [showGrid, formatValue]
  );

  const renderXAxis = useCallback(
    (width: number, xScale: { min: number; max: number }) => {
      const labels = 5;
      const xLabels = [];

      for (let i = 0; i <= labels; i++) {
        const ratio = i / labels;
        const x = ratio * width;
        const time = xScale.min + ratio * (xScale.max - xScale.min);

        xLabels.push(
          <g key={`x-label-${i}`}>
            <line
              x1={x}
              y1={0}
              x2={x}
              y2={5}
              stroke="rgba(197, 203, 206, 0.3)"
              strokeWidth={1}
            />
            <text
              x={x}
              y={20}
              fill="#888"
              fontSize="11"
              textAnchor="middle"
            >
              {formatTimestamp(time)}
            </text>
          </g>
        );
      }

      return xLabels;
    },
    [formatTimestamp]
  );

  const renderLines = useCallback(
    (width: number, height: number, xScale: { min: number; max: number }) => {
      if (!data.length) return null;

      const { min, max } = getMinMax();
      const yScale = getYScale(height, min, max);

      return data.map((series, seriesIndex) => {
        const color = series.color || defaultColors[seriesIndex % defaultColors.length];
        const points = series.data
          .filter((p) => p.value !== null && p.value !== undefined)
          .map((point) => ({
            x: getX(width, point.time, xScale),
            y: yScale.getY(point.value),
            original: point,
          }));

        if (points.length === 0) return null;

        const lineType = series.type || 'line';
        let path = '';

        for (let i = 0; i < points.length; i++) {
          const { x, y } = points[i];
          if (i === 0) {
            path += `M ${x} ${y}`;
          } else {
            if (lineType === 'step') {
              path += `L ${x} ${points[i - 1].y} L ${x} ${y}`;
            } else {
              path += `L ${x} ${y}`;
            }
          }
        }

        // Path pour l'area
        const areaPath =
          series.type === 'area'
            ? `${path} L ${points[points.length - 1].x} ${height} L ${points[0].x} ${height} Z`
            : '';

        return (
          <g key={series.id || seriesIndex}>
            {/* Area */}
            {series.type === 'area' && (
              <path
                d={areaPath}
                fill={color}
                fillOpacity={series.fillOpacity || 0.1}
                stroke="none"
              />
            )}

            {/* Ligne */}
            <path
              d={path}
              fill="none"
              stroke={color}
              strokeWidth={series.strokeWidth || 2}
              strokeLinecap="round"
              strokeLinejoin="round"
              className={showAnimation ? 'line-chart-animate' : ''}
            />

            {/* Points */}
            {points.map((point, index) => (
              <circle
                key={`${series.id}-${index}`}
                cx={point.x}
                cy={point.y}
                r={4}
                fill="white"
                stroke={color}
                strokeWidth={2}
                className="cursor-pointer transition-all duration-200 hover:r-6"
                onMouseEnter={() => {
                  setHoveredPoint({
                    seriesId: series.id || seriesIndex.toString(),
                    index,
                    data: point.original,
                  });
                  onHover?.(point.original);
                }}
                onMouseLeave={() => {
                  setHoveredPoint(null);
                  onHover?.(null);
                }}
                onClick={() => {
                  setSelectedPoint({
                    seriesId: series.id || seriesIndex.toString(),
                    index,
                    data: point.original,
                  });
                  onDataPointClick?.(point.original, series.id || seriesIndex.toString());
                }}
              />
            ))}

            {/* Dernier point - plus grand */}
            {points.length > 0 && (
              <circle
                cx={points[points.length - 1].x}
                cy={points[points.length - 1].y}
                r={6}
                fill={color}
                stroke="white"
                strokeWidth={2}
                className="cursor-pointer"
              />
            )}
          </g>
        );
      });
    },
    [data, getMinMax, getYScale, getX, showAnimation, onHover, onDataPointClick]
  );

  const renderLegend = useCallback(() => {
    if (!showLegend || !data.length) return null;

    return (
      <div className="flex flex-wrap gap-4 mb-4 justify-center">
        {data.map((series, index) => {
          const color = series.color || defaultColors[index % defaultColors.length];
          const lastValue = series.data.length > 0 ? series.data[series.data.length - 1].value : 0;

          return (
            <div
              key={series.id || index}
              className="flex items-center gap-2 text-sm"
            >
              <span
                className="w-3 h-3 rounded-full"
                style={{ backgroundColor: color }}
              />
              <span className="font-medium text-gray-700 dark:text-gray-300">
                {series.name}
              </span>
              <span className="text-gray-500 dark:text-gray-400">
                {formatValue(lastValue)}
              </span>
            </div>
          );
        })}
      </div>
    );
  }, [data, showLegend, formatValue]);

  const renderTooltip = useCallback(() => {
    if (!showTooltip || !hoveredPoint) return null;

    const { seriesId, data: point } = hoveredPoint;
    const series = data.find((s) => s.id === seriesId);
    const color = series?.color || defaultColors[0];

    return (
      <div
        ref={tooltipRef}
        className="absolute pointer-events-none bg-white dark:bg-gray-800 shadow-lg rounded-lg p-3 border border-gray-200 dark:border-gray-700 z-10"
        style={{
          left: '50%',
          top: '10px',
          transform: 'translateX(-50%)',
          minWidth: '150px',
        }}
      >
        <div className="text-xs text-gray-500 dark:text-gray-400">
          {formatDate(point.time)}
        </div>
        <div className="flex items-center gap-2 mt-1">
          <span
            className="w-2 h-2 rounded-full"
            style={{ backgroundColor: color }}
          />
          <span className="font-medium">{series?.name || 'Valeur'}</span>
          <span className="font-bold">{formatValue(point.value)}</span>
        </div>
        {point.label && (
          <div className="text-xs text-gray-500 dark:text-gray-400 mt-1">
            {point.label}
          </div>
        )}
      </div>
    );
  }, [showTooltip, hoveredPoint, data, formatValue, formatDate]);

  // ============================================
  // GESTION DU REDIMENSIONNEMENT
  // ============================================

  useEffect(() => {
    if (!chartContainerRef.current) return;

    const container = chartContainerRef.current;
    const resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const { width } = entry.contentRect;
        setChartWidth(width || 0);
      }
    });

    resizeObserver.observe(container);
    resizeObserverRef.current = resizeObserver;

    // Initialiser la largeur
    setChartWidth(container.clientWidth || 0);

    return () => {
      if (resizeObserverRef.current) {
        resizeObserverRef.current.disconnect();
      }
    };
  }, []);

  // ============================================
  // GESTIONNAIRES D'ÉVÉNEMENTS
  // ============================================

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  // ============================================
  // RENDU PRINCIPAL
  // ============================================

  const chartHeight = isFullscreen ? 'calc(100vh - 250px)' : height;
  const chartWidthPx = chartWidth || 600;

  return (
    <Card
      className={cn(
        'relative overflow-hidden transition-all duration-300',
        isFullscreen && 'fixed inset-4 z-50',
        className
      )}
    >
      <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
        <div>
          <CardTitle>{title}</CardTitle>
          <CardDescription>{description}</CardDescription>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleFullscreen}
            className="hidden md:flex"
          >
            {isFullscreen ? 'Réduire' : 'Plein écran'}
          </Button>
          {onRetry && error && (
            <Button variant="outline" size="sm" onClick={onRetry}>
              Réessayer
            </Button>
          )}
        </div>
      </CardHeader>

      <CardContent>
        {renderLegend()}

        <div
          ref={chartContainerRef}
          className={cn(
            'relative w-full transition-all',
            isFullscreen ? 'h-[calc(100vh-250px)]' : `h-[${height}px]`
          )}
          style={{ height: isFullscreen ? 'calc(100vh - 250px)' : height }}
        >
          {loading && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/50 dark:bg-gray-900/50 z-10">
              <Spinner className="h-8 w-8" />
              <span className="ml-2 text-gray-600 dark:text-gray-400">
                Chargement...
              </span>
            </div>
          )}

          {error && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/50 dark:bg-gray-900/50 z-10">
              <div className="text-center text-red-600">
                <p className="text-lg font-semibold">⚠️ {error}</p>
              </div>
            </div>
          )}

          {!loading && !error && data.length === 0 && (
            <div className="absolute inset-0 flex items-center justify-center">
              <div className="text-center text-gray-500">
                <p className="text-lg">Aucune donnée disponible</p>
              </div>
            </div>
          )}

          {!loading && !error && data.length > 0 && chartWidthPx > 0 && (
            <svg
              ref={svgRef}
              width="100%"
              height="100%"
              viewBox={`0 0 ${chartWidthPx} ${chartHeight}`}
              preserveAspectRatio="none"
              className="overflow-visible"
            >
              {/* X Axis */}
              {renderXAxis(chartWidthPx, getXScale(chartWidthPx))}

              {/* Grid */}
              {renderGrid(chartWidthPx, chartHeight, getYScale(chartHeight, getMinMax().min, getMinMax().max))}

              {/* Lines */}
              {renderLines(chartWidthPx, chartHeight, getXScale(chartWidthPx))}
            </svg>
          )}

          {/* Tooltip */}
          {renderTooltip()}
        </div>

        {/* Bas du graphique */}
        <div className="flex justify-between items-center mt-4 text-sm text-gray-500 dark:text-gray-400">
          <div>
            {data.length > 0 && (
              <>
                {data[0].data.length} points de données
                {xAxisLabel && ` • ${xAxisLabel}`}
              </>
            )}
          </div>
          {yAxisLabel && (
            <div>
              {yAxisLabel}
            </div>
          )}
        </div>
      </CardContent>

      {/* Style d'animation */}
      <style jsx>{`
        .line-chart-animate {
          stroke-dasharray: 1000;
          stroke-dashoffset: 1000;
          animation: dash 1.5s ease-in-out forwards;
        }

        @keyframes dash {
          to {
            stroke-dashoffset: 0;
          }
        }
      `}</style>
    </Card>
  );
}

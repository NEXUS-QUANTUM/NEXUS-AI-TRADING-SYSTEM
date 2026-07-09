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
import { cn, formatPrice, formatCompactNumber } from '@/utils/helpers';

// ============================================
// TYPES
// ============================================

interface PieDataItem {
  id: string;
  label: string;
  value: number;
  color?: string;
  percentage?: number;
}

interface PieChartProps {
  data?: PieDataItem[];
  title?: string;
  description?: string;
  height?: number;
  width?: number;
  showLegend?: boolean;
  showLabels?: boolean;
  showPercentage?: boolean;
  showTooltip?: boolean;
  showAnimation?: boolean;
  isCurrency?: boolean;
  isPercentage?: boolean;
  className?: string;
  onSliceClick?: (item: PieDataItem) => void;
  onHover?: (item: PieDataItem | null) => void;
  loading?: boolean;
  error?: string | null;
  onRetry?: () => void;
  innerRadius?: number;
  outerRadius?: number;
  paddingAngle?: number;
  cornerRadius?: number;
}

// ============================================
// COMPOSANT PRINCIPAL
// ============================================

export function PieChart({
  data: initialData = [],
  title = 'Répartition',
  description = 'Visualisation des données en camembert',
  height = 400,
  width = 0,
  showLegend = true,
  showLabels = true,
  showPercentage = true,
  showTooltip = true,
  showAnimation = true,
  isCurrency = false,
  isPercentage = false,
  className = '',
  onSliceClick,
  onHover,
  loading = false,
  error = null,
  onRetry,
  innerRadius = 0,
  outerRadius = 0,
  paddingAngle = 0.02,
  cornerRadius = 0,
}: PieChartProps) {
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
  const [data, setData] = useState<PieDataItem[]>(initialData);
  const [chartWidth, setChartWidth] = useState(width || 0);
  const [hoveredSlice, setHoveredSlice] = useState<PieDataItem | null>(null);
  const [selectedSlice, setSelectedSlice] = useState<PieDataItem | null>(null);
  const [animationProgress, setAnimationProgress] = useState(0);
  const [isFullscreen, setIsFullscreen] = useState(false);

  // ============================================
  // COULEURS PAR DÉFAUT
  // ============================================
  const defaultColors = [
    '#4ECDC4', '#FF6B6B', '#45B7D1', '#96CEB4', '#FFEAA7',
    '#DDA0DD', '#FF8A80', '#80DEEA', '#C5E1A5', '#FFD54F',
    '#CE93D8', '#EF5350', '#26A69A', '#42A5F5', '#FFA726',
    '#8D6E63', '#78909C', '#4DD0E1', '#4DB6AC', '#7986CB',
  ];

  // ============================================
  // FONCTIONS DE FORMATAGE
  // ============================================

  const formatValue = (value: number): string => {
    if (isCurrency) return formatPrice(value);
    if (isPercentage) return `${value.toFixed(1)}%`;
    if (Math.abs(value) >= 1e9) return formatCompactNumber(value);
    if (Math.abs(value) >= 1e6) return formatCompactNumber(value);
    if (Math.abs(value) >= 1e3) return formatCompactNumber(value);
    return value.toFixed(2);
  };

  // ============================================
  // CALCULS DES DONNÉES
  // ============================================

  const getPieData = useCallback(() => {
    const total = data.reduce((sum, item) => sum + item.value, 0);
    let currentAngle = 0;

    return data.map((item, index) => {
      const percentage = total > 0 ? (item.value / total) * 100 : 0;
      const angle = (item.value / total) * 2 * Math.PI;
      const startAngle = currentAngle;
      const endAngle = currentAngle + angle;
      currentAngle = endAngle;

      const color = item.color || defaultColors[index % defaultColors.length];

      return {
        ...item,
        percentage,
        startAngle,
        endAngle,
        color,
        total,
      };
    });
  }, [data]);

  // ============================================
  // RENDU DES SLICES
  // ============================================

  const renderSlices = useCallback(
    (width: number, height: number) => {
      const pieData = getPieData();
      const radius = Math.min(width, height) / 2 * 0.8;
      const innerR = innerRadius || radius * 0.3;
      const outerR = outerRadius || radius;
      const centerX = width / 2;
      const centerY = height / 2;
      const actualPadding = paddingAngle || 0;

      if (!pieData.length) return null;

      return pieData.map((item, index) => {
        const startA = item.startAngle + actualPadding / 2;
        const endA = item.endAngle - actualPadding / 2;
        const isHovered = hoveredSlice?.id === item.id;
        const isSelected = selectedSlice?.id === item.id;

        // Calcul des points pour l'arc
        const startX = centerX + innerR * Math.cos(startA);
        const startY = centerY + innerR * Math.sin(startA);
        const endX = centerX + innerR * Math.cos(endA);
        const endY = centerY + innerR * Math.sin(endA);

        const outerStartX = centerX + outerR * Math.cos(startA);
        const outerStartY = centerY + outerR * Math.sin(startA);
        const outerEndX = centerX + outerR * Math.cos(endA);
        const outerEndY = centerY + outerR * Math.sin(endA);

        const largeArc = endA - startA > Math.PI ? 1 : 0;

        // Chemin pour l'arc
        let path = '';
        if (innerR === 0) {
          // Camembert simple
          path = `
            M ${centerX} ${centerY}
            L ${outerStartX} ${outerStartY}
            A ${outerR} ${outerR} 0 ${largeArc} 1 ${outerEndX} ${outerEndY}
            Z
          `;
        } else {
          // Donut
          path = `
            M ${startX} ${startY}
            L ${outerStartX} ${outerStartY}
            A ${outerR} ${outerR} 0 ${largeArc} 1 ${outerEndX} ${outerEndY}
            L ${endX} ${endY}
            A ${innerR} ${innerR} 0 ${largeArc} 0 ${startX} ${startY}
            Z
          `;
        }

        // Calcul du centre de la slice pour l'étiquette
        const midAngle = (startA + endA) / 2;
        const labelRadius = innerR === 0 ? outerR * 0.6 : (innerR + outerR) / 2;
        const labelX = centerX + labelRadius * Math.cos(midAngle);
        const labelY = centerY + labelRadius * Math.sin(midAngle);

        // Calcul du pourcentage
        const percentage = item.percentage || 0;

        // Rayon pour l'effet de zoom
        const zoomFactor = isHovered || isSelected ? 1.05 : 1;
        const zoomedR = outerR * zoomFactor;

        return (
          <g key={item.id || index}>
            {/* Slice */}
            <path
              d={path}
              fill={item.color}
              stroke="white"
              strokeWidth={2}
              className={cn(
                'cursor-pointer transition-all duration-300',
                showAnimation && 'pie-chart-animate'
              )}
              style={{
                transform: isHovered || isSelected
                  ? `translate(${(centerX - centerX) * (zoomFactor - 1)}, ${(centerY - centerY) * (zoomFactor - 1)})`
                  : 'none',
                transformOrigin: `${centerX}px ${centerY}px`,
              }}
              onMouseEnter={() => {
                setHoveredSlice(item);
                onHover?.(item);
              }}
              onMouseLeave={() => {
                setHoveredSlice(null);
                onHover?.(null);
              }}
              onClick={() => {
                setSelectedSlice(item);
                onSliceClick?.(item);
              }}
            />

            {/* Labels */}
            {showLabels && percentage > 3 && (
              <>
                <text
                  x={labelX}
                  y={labelY}
                  textAnchor="middle"
                  dominantBaseline="middle"
                  className="text-xs font-medium text-white drop-shadow-md"
                  style={{
                    pointerEvents: 'none',
                  }}
                >
                  {showPercentage && percentage > 5
                    ? `${percentage.toFixed(1)}%`
                    : ''}
                </text>
                {percentage <= 5 && percentage > 3 && (
                  <text
                    x={labelX + 20}
                    y={labelY - 10}
                    textAnchor="start"
                    dominantBaseline="middle"
                    className="text-xs text-gray-600 dark:text-gray-400"
                    style={{
                      pointerEvents: 'none',
                    }}
                  >
                    {`${percentage.toFixed(1)}%`}
                  </text>
                )}
              </>
            )}

            {/* Arc extérieur pour l'effet de hover */}
            {isHovered && (
              <path
                d={`
                  M ${outerStartX} ${outerStartY}
                  A ${outerR + 5} ${outerR + 5} 0 ${largeArc} 1 ${outerEndX} ${outerEndY}
                `}
                fill="none"
                stroke={item.color}
                strokeWidth={3}
                opacity={0.5}
              />
            )}
          </g>
        );
      });
    },
    [
      getPieData,
      hoveredSlice,
      selectedSlice,
      showLabels,
      showPercentage,
      showAnimation,
      innerRadius,
      outerRadius,
      paddingAngle,
      onHover,
      onSliceClick,
    ]
  );

  // ============================================
  // RENDU DE LA LÉGENDE
  // ============================================

  const renderLegend = useCallback(() => {
    if (!showLegend || !data.length) return null;

    const pieData = getPieData();

    return (
      <div className="flex flex-wrap gap-3 mt-4 justify-center">
        {pieData.map((item, index) => (
          <div
            key={item.id || index}
            className="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity"
            onMouseEnter={() => {
              setHoveredSlice(item);
              onHover?.(item);
            }}
            onMouseLeave={() => {
              setHoveredSlice(null);
              onHover?.(null);
            }}
            onClick={() => {
              setSelectedSlice(item);
              onSliceClick?.(item);
            }}
          >
            <span
              className="w-3 h-3 rounded-full flex-shrink-0"
              style={{ backgroundColor: item.color }}
            />
            <span className="text-sm text-gray-700 dark:text-gray-300">
              {item.label}
            </span>
            <span className="text-sm text-gray-500 dark:text-gray-400">
              {formatValue(item.value)}
              {showPercentage && (
                <span className="ml-1 text-xs">
                  ({item.percentage?.toFixed(1)}%)
                </span>
              )}
            </span>
          </div>
        ))}
      </div>
    );
  }, [data, showLegend, showPercentage, getPieData, formatValue, onHover, onSliceClick]);

  // ============================================
  // RENDU DU TOOLTIP
  // ============================================

  const renderTooltip = useCallback(() => {
    if (!showTooltip || !hoveredSlice) return null;

    const total = hoveredSlice.total || 0;
    const percentage = total > 0 ? (hoveredSlice.value / total) * 100 : 0;

    return (
      <div
        ref={tooltipRef}
        className="absolute pointer-events-none bg-white dark:bg-gray-800 shadow-lg rounded-lg p-4 border border-gray-200 dark:border-gray-700 z-10"
        style={{
          left: '50%',
          top: '10px',
          transform: 'translateX(-50%)',
          minWidth: '200px',
        }}
      >
        <div className="flex items-center gap-2">
          <span
            className="w-3 h-3 rounded-full flex-shrink-0"
            style={{ backgroundColor: hoveredSlice.color }}
          />
          <span className="font-semibold text-gray-900 dark:text-white">
            {hoveredSlice.label}
          </span>
        </div>
        <div className="mt-2 space-y-1">
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Valeur</span>
            <span className="font-medium text-gray-900 dark:text-white">
              {formatValue(hoveredSlice.value)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Pourcentage</span>
            <span className="font-medium text-gray-900 dark:text-white">
              {percentage.toFixed(2)}%
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-gray-500 dark:text-gray-400">Total</span>
            <span className="font-medium text-gray-900 dark:text-white">
              {formatValue(total)}
            </span>
          </div>
        </div>
      </div>
    );
  }, [showTooltip, hoveredSlice, formatValue]);

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

    setChartWidth(container.clientWidth || 0);

    return () => {
      if (resizeObserverRef.current) {
        resizeObserverRef.current.disconnect();
      }
    };
  }, []);

  // ============================================
  // ANIMATION
  // ============================================

  useEffect(() => {
    if (showAnimation && data.length > 0) {
      let startTime: number;
      const duration = 800;

      const animate = (timestamp: number) => {
        if (!startTime) startTime = timestamp;
        const progress = Math.min((timestamp - startTime) / duration, 1);
        setAnimationProgress(progress);

        if (progress < 1) {
          requestAnimationFrame(animate);
        }
      };

      requestAnimationFrame(animate);
    }
  }, [data, showAnimation]);

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
          {data.length > 0 && (
            <span className="text-sm text-gray-500 dark:text-gray-400">
              Total: {formatValue(data.reduce((sum, item) => sum + item.value, 0))}
            </span>
          )}
          <Button
            variant="ghost"
            size="sm"
            onClick={toggleFullscreen}
            className="hidden md:flex"
          >
            {isFullscreen ? 'Réduire' : 'Plein écran'}
          </Button>
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
                {onRetry && (
                  <Button
                    variant="default"
                    size="sm"
                    onClick={onRetry}
                    className="mt-2"
                  >
                    Réessayer
                  </Button>
                )}
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
              preserveAspectRatio="xMidYMid meet"
              className="overflow-visible"
            >
              {renderSlices(chartWidthPx, chartHeight)}
            </svg>
          )}

          {/* Tooltip */}
          {renderTooltip()}
        </div>

        {/* Informations supplémentaires */}
        {data.length > 0 && (
          <div className="flex flex-wrap justify-between items-center mt-4 text-sm text-gray-500 dark:text-gray-400">
            <div>
              {data.length} éléments • Total: {formatValue(data.reduce((sum, item) => sum + item.value, 0))}
            </div>
            <div>
              {selectedSlice && (
                <span className="flex items-center gap-2">
                  <span
                    className="w-2 h-2 rounded-full"
                    style={{ backgroundColor: selectedSlice.color }}
                  />
                  {selectedSlice.label}: {formatValue(selectedSlice.value)}
                </span>
              )}
            </div>
          </div>
        )}
      </CardContent>

      {/* Style d'animation */}
      <style jsx>{`
        .pie-chart-animate {
          animation: pieGrow 0.8s ease-out forwards;
          transform-origin: center;
        }

        @keyframes pieGrow {
          from {
            transform: scale(0) rotate(-180deg);
          }
          to {
            transform: scale(1) rotate(0deg);
          }
        }

        .pie-chart-animate:hover {
          filter: brightness(1.1);
          transition: filter 0.3s ease;
        }
      `}</style>
    </Card>
  );
}

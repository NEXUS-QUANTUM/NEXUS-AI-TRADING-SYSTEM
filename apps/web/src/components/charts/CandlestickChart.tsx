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
import { useApi } from '@/hooks/useApi';
import { useWebSocket } from '@/hooks/useWebSocket';
import { cn, formatPrice, formatDate } from '@/utils/helpers';

// ============================================
// TYPES
// ============================================

interface CandlestickData {
  time: number;
  open: number;
  high: number;
  low: number;
  close: number;
  volume?: number;
}

interface Indicator {
  name: string;
  data: number[];
  color: string;
}

interface ChartConfig {
  symbol: string;
  timeframe: string;
  indicators: string[];
  height: number;
  width: number;
}

type Timeframe = '1m' | '5m' | '15m' | '30m' | '1h' | '4h' | '1d' | '1w' | '1M';

// ============================================
// COMPOSANT PRINCIPAL
// ============================================

interface CandlestickChartProps {
  symbol?: string;
  timeframe?: Timeframe;
  height?: number;
  width?: number;
  showIndicators?: boolean;
  showVolume?: boolean;
  className?: string;
  onTimeframeChange?: (timeframe: Timeframe) => void;
  onSymbolChange?: (symbol: string) => void;
}

export function CandlestickChart({
  symbol: initialSymbol = 'BTCUSDT',
  timeframe: initialTimeframe = '1h',
  height = 500,
  width = 0,
  showIndicators = true,
  showVolume = true,
  className = '',
  onTimeframeChange,
  onSymbolChange,
}: CandlestickChartProps) {
  // ============================================
  // RÉFÉRENCES
  // ============================================
  const chartContainerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<any>(null);
  const resizeObserverRef = useRef<ResizeObserver | null>(null);

  // ============================================
  // ÉTATS
  // ============================================
  const [symbol, setSymbol] = useState(initialSymbol);
  const [timeframe, setTimeframe] = useState<Timeframe>(initialTimeframe);
  const [data, setData] = useState<CandlestickData[]>([]);
  const [indicators, setIndicators] = useState<Indicator[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [selectedIndicators, setSelectedIndicators] = useState<string[]>(['sma20', 'ema50']);
  const [chartWidth, setChartWidth] = useState(width || 0);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastPrice, setLastPrice] = useState<number | null>(null);
  const [priceChange, setPriceChange] = useState<number | null>(null);
  const [priceChangePercent, setPriceChangePercent] = useState<number | null>(null);

  // ============================================
  // HOOKS
  // ============================================
  const { get } = useApi();
  const { sendMessage, lastMessage, isConnected } = useWebSocket(
    `${process.env.NEXT_PUBLIC_WEBSOCKET_URL}/market`
  );

  // ============================================
  // TIME FRAMES
  // ============================================
  const timeframes: { label: string; value: Timeframe }[] = [
    { label: '1m', value: '1m' },
    { label: '5m', value: '5m' },
    { label: '15m', value: '15m' },
    { label: '30m', value: '30m' },
    { label: '1h', value: '1h' },
    { label: '4h', value: '4h' },
    { label: '1d', value: '1d' },
    { label: '1w', value: '1w' },
    { label: '1M', value: '1M' },
  ];

  // ============================================
  // INDICATEURS DISPONIBLES
  // ============================================
  const availableIndicators = [
    { id: 'sma20', name: 'SMA 20', color: '#FF6B6B' },
    { id: 'sma50', name: 'SMA 50', color: '#4ECDC4' },
    { id: 'sma200', name: 'SMA 200', color: '#45B7D1' },
    { id: 'ema20', name: 'EMA 20', color: '#96CEB4' },
    { id: 'ema50', name: 'EMA 50', color: '#FFEAA7' },
    { id: 'bollinger', name: 'Bollinger Bands', color: '#DDA0DD' },
    { id: 'rsi', name: 'RSI', color: '#FF6B6B' },
    { id: 'macd', name: 'MACD', color: '#4ECDC4' },
    { id: 'volume', name: 'Volume', color: '#45B7D1' },
  ];

  // ============================================
  // FONCTIONS
  // ============================================

  // Charger les données
  const loadData = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await get(`/market/klines/${symbol}`, {
        params: { interval: timeframe, limit: 500 },
      });
      const formattedData: CandlestickData[] = response.data.map((item: any) => ({
        time: item[0] / 1000,
        open: parseFloat(item[1]),
        high: parseFloat(item[2]),
        low: parseFloat(item[3]),
        close: parseFloat(item[4]),
        volume: parseFloat(item[5]),
      }));
      setData(formattedData);
      
      // Calculer les changements de prix
      if (formattedData.length > 0) {
        const last = formattedData[formattedData.length - 1];
        const first = formattedData[0];
        setLastPrice(last.close);
        setPriceChange(last.close - first.open);
        setPriceChangePercent(((last.close - first.open) / first.open) * 100);
      }
    } catch (err) {
      console.error('Erreur lors du chargement des données:', err);
      setError('Impossible de charger les données de marché');
    } finally {
      setIsLoading(false);
    }
  }, [get, symbol, timeframe]);

  // Charger les indicateurs
  const loadIndicators = useCallback(async () => {
    if (!selectedIndicators.length) return;
    try {
      const response = await get(`/market/indicators/${symbol}`, {
        params: {
          indicators: selectedIndicators.join(','),
          interval: timeframe,
        },
      });
      const formattedIndicators: Indicator[] = Object.entries(response.data).map(
        ([name, data]) => ({
          name,
          data: data as number[],
          color: availableIndicators.find((i) => i.id === name)?.color || '#888888',
        })
      );
      setIndicators(formattedIndicators);
    } catch (err) {
      console.error('Erreur lors du chargement des indicateurs:', err);
    }
  }, [get, symbol, timeframe, selectedIndicators]);

  // Initialiser le graphique
  const initChart = useCallback(async () => {
    if (!chartContainerRef.current || !data.length) return;

    // Nettoyer le graphique existant
    if (chartRef.current) {
      chartRef.current.destroy();
      chartRef.current = null;
    }

    // Importer Lightweight Charts dynamiquement
    const { createChart } = await import('lightweight-charts');

    const container = chartContainerRef.current;
    const containerWidth = container.clientWidth || 800;

    // Créer le graphique
    const chart = createChart(container, {
      width: containerWidth,
      height: height,
      layout: {
        background: { color: 'transparent' },
        textColor: '#333',
        fontSize: 12,
      },
      grid: {
        vertLines: { color: 'rgba(197, 203, 206, 0.3)' },
        horzLines: { color: 'rgba(197, 203, 206, 0.3)' },
      },
      crosshair: {
        mode: 0,
        vertLine: {
          color: '#6C6C6C',
          width: 1,
          style: 2,
        },
        horzLine: {
          color: '#6C6C6C',
          width: 1,
          style: 2,
        },
      },
      timeScale: {
        borderColor: 'rgba(197, 203, 206, 0.3)',
        timeVisible: true,
        secondsVisible: timeframe === '1m' || timeframe === '5m',
      },
      localization: {
        locale: 'fr-FR',
        priceFormatter: (price: number) => formatPrice(price),
      },
    });

    // Ajouter le graphique en chandeliers
    const candleSeries = chart.addCandlestickSeries({
      upColor: '#26a69a',
      downColor: '#ef5350',
      borderDownColor: '#ef5350',
      borderUpColor: '#26a69a',
      wickDownColor: '#ef5350',
      wickUpColor: '#26a69a',
      priceLineColor: '#2962FF',
      priceLineWidth: 1,
      priceLineStyle: 2,
      lastValueVisible: true,
    });

    candleSeries.setData(data);

    // Ajouter le volume si activé
    if (showVolume) {
      const volumeSeries = chart.addHistogramSeries({
        priceFormat: {
          type: 'volume',
        },
        priceScaleId: 'volume',
        color: '#26a69a',
        lineWidth: 1,
        lastValueVisible: true,
        title: 'Volume',
      });

      const volumeData = data.map((item) => ({
        time: item.time,
        value: item.volume || 0,
        color: item.close > item.open ? '#26a69a' : '#ef5350',
      }));

      volumeSeries.setData(volumeData);

      // Ajuster l'échelle de prix pour le volume
      chart.priceScale('volume').applyOptions({
        scaleMargins: {
          top: 0.8,
          bottom: 0,
        },
        borderVisible: false,
      });
    }

    // Ajouter les indicateurs
    indicators.forEach((indicator) => {
      if (indicator.name === 'bollinger') {
        // Bollinger Bands
        const upperBand = chart.addLineSeries({
          color: indicator.color,
          lineWidth: 1,
          lineStyle: 2,
          title: 'BB Upper',
        });
        const middleBand = chart.addLineSeries({
          color: indicator.color,
          lineWidth: 1,
          title: 'BB Middle',
        });
        const lowerBand = chart.addLineSeries({
          color: indicator.color,
          lineWidth: 1,
          lineStyle: 2,
          title: 'BB Lower',
        });

        const bandsData = indicator.data as any;
        upperBand.setData(
          data.map((d, i) => ({
            time: d.time,
            value: bandsData[i]?.upper || 0,
          }))
        );
        middleBand.setData(
          data.map((d, i) => ({
            time: d.time,
            value: bandsData[i]?.middle || 0,
          }))
        );
        lowerBand.setData(
          data.map((d, i) => ({
            time: d.time,
            value: bandsData[i]?.lower || 0,
          }))
        );
      } else if (indicator.name === 'rsi') {
        // RSI - affiché dans un paneau séparé
        const rsiSeries = chart.addLineSeries({
          color: indicator.color,
          lineWidth: 2,
          title: 'RSI',
          priceScaleId: 'rsi',
        });

        const rsiData = data.map((d, i) => ({
          time: d.time,
          value: indicator.data[i] || 50,
        }));

        rsiSeries.setData(rsiData);

        // Ajouter les niveaux RSI
        const rsiLevel70 = chart.addLineSeries({
          color: '#ef5350',
          lineWidth: 1,
          lineStyle: 2,
          priceScaleId: 'rsi',
          title: 'RSI 70',
        });
        const rsiLevel30 = chart.addLineSeries({
          color: '#26a69a',
          lineWidth: 1,
          lineStyle: 2,
          priceScaleId: 'rsi',
          title: 'RSI 30',
        });

        rsiLevel70.setData(
          data.map((d) => ({
            time: d.time,
            value: 70,
          }))
        );
        rsiLevel30.setData(
          data.map((d) => ({
            time: d.time,
            value: 30,
          }))
        );

        chart.priceScale('rsi').applyOptions({
          scaleMargins: {
            top: 0.5,
            bottom: 0,
          },
          borderVisible: false,
        });
      } else if (indicator.name === 'macd') {
        // MACD - affiché dans un paneau séparé
        const macdSeries = chart.addLineSeries({
          color: indicator.color,
          lineWidth: 2,
          title: 'MACD',
          priceScaleId: 'macd',
        });

        const signalSeries = chart.addLineSeries({
          color: '#FF6B6B',
          lineWidth: 1,
          title: 'Signal',
          priceScaleId: 'macd',
        });

        const histogramSeries = chart.addHistogramSeries({
          priceScaleId: 'macd',
          title: 'Histogram',
        });

        const macdData = indicator.data as any;
        macdSeries.setData(
          data.map((d, i) => ({
            time: d.time,
            value: macdData[i]?.macd || 0,
          }))
        );
        signalSeries.setData(
          data.map((d, i) => ({
            time: d.time,
            value: macdData[i]?.signal || 0,
          }))
        );
        histogramSeries.setData(
          data.map((d, i) => ({
            time: d.time,
            value: macdData[i]?.histogram || 0,
            color: (macdData[i]?.histogram || 0) > 0 ? '#26a69a' : '#ef5350',
          }))
        );

        chart.priceScale('macd').applyOptions({
          scaleMargins: {
            top: 0.7,
            bottom: 0,
          },
          borderVisible: false,
        });
      } else {
        // Indicateur standard (SMA, EMA)
        const series = chart.addLineSeries({
          color: indicator.color,
          lineWidth: 2,
          title: indicator.name.toUpperCase(),
        });

        const indicatorData = data.map((d, i) => ({
          time: d.time,
          value: indicator.data[i] || 0,
        }));

        series.setData(indicatorData);
      }
    });

    // Ajouter la ligne de prix actuelle
    if (lastPrice) {
      const currentPriceLine = chart.addLineSeries({
        color: '#2962FF',
        lineWidth: 1,
        lineStyle: 2,
        title: 'Prix actuel',
      });

      currentPriceLine.setData([
        { time: data[0]?.time || 0, value: lastPrice },
        { time: data[data.length - 1]?.time || 0, value: lastPrice },
      ]);
    }

    // Ajuster le temps
    chart.timeScale().fitContent();

    // Gérer le redimensionnement
    const handleResize = () => {
      if (chartContainerRef.current) {
        const newWidth = chartContainerRef.current.clientWidth;
        chart.applyOptions({ width: newWidth });
        chart.timeScale().fitContent();
      }
    };

    const resizeObserver = new ResizeObserver(handleResize);
    resizeObserver.observe(container);
    resizeObserverRef.current = resizeObserver;

    chartRef.current = chart;
  }, [data, height, indicators, lastPrice, showVolume, timeframe]);

  // ============================================
  // EFFETS
  // ============================================

  // Charger les données au montage
  useEffect(() => {
    loadData();
  }, [loadData]);

  // Charger les indicateurs
  useEffect(() => {
    if (showIndicators) {
      loadIndicators();
    }
  }, [loadIndicators, showIndicators]);

  // Initialiser le graphique
  useEffect(() => {
    if (data.length > 0) {
      initChart();
    }

    return () => {
      if (chartRef.current) {
        chartRef.current.destroy();
        chartRef.current = null;
      }
      if (resizeObserverRef.current) {
        resizeObserverRef.current.disconnect();
        resizeObserverRef.current = null;
      }
    };
  }, [data, initChart]);

  // Mettre à jour le graphique en temps réel
  useEffect(() => {
    if (lastMessage && chartRef.current) {
      try {
        const message = JSON.parse(lastMessage);
        if (message.type === 'trade' && message.symbol === symbol) {
          const newCandle = message.data;
          const candleSeries = chartRef.current.series()[0];
          if (candleSeries) {
            candleSeries.update({
              time: newCandle.time,
              open: newCandle.open,
              high: newCandle.high,
              low: newCandle.low,
              close: newCandle.close,
            });
          }
        }
      } catch (err) {
        console.error('Erreur de mise à jour en temps réel:', err);
      }
    }
  }, [lastMessage, symbol]);

  // ============================================
  // GESTIONNAIRES D'ÉVÉNEMENTS
  // ============================================

  const handleTimeframeChange = (newTimeframe: Timeframe) => {
    setTimeframe(newTimeframe);
    onTimeframeChange?.(newTimeframe);
  };

  const handleSymbolChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newSymbol = e.target.value.toUpperCase();
    setSymbol(newSymbol);
    onSymbolChange?.(newSymbol);
  };

  const handleIndicatorToggle = (indicatorId: string) => {
    setSelectedIndicators((prev) =>
      prev.includes(indicatorId)
        ? prev.filter((id) => id !== indicatorId)
        : [...prev, indicatorId]
    );
  };

  const toggleFullscreen = () => {
    setIsFullscreen(!isFullscreen);
  };

  // ============================================
  // RENDU
  // ============================================

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
          <CardTitle className="flex items-center gap-2">
            <span>{symbol}</span>
            {lastPrice !== null && (
              <span className="text-sm font-normal text-gray-500">
                {formatPrice(lastPrice)}
              </span>
            )}
            {priceChange !== null && (
              <span
                className={cn(
                  'text-sm font-medium',
                  priceChange > 0 ? 'text-green-600' : 'text-red-600'
                )}
              >
                {priceChange > 0 ? '+' : ''}
                {formatPrice(priceChange)} ({priceChangePercent?.toFixed(2)}%)
              </span>
            )}
          </CardTitle>
          <CardDescription>
            Graphique en chandeliers - {timeframe}
          </CardDescription>
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
        </div>
      </CardHeader>

      <CardContent>
        {/* Contrôles */}
        <div className="flex flex-wrap items-center gap-2 mb-4">
          <div className="flex flex-wrap gap-1">
            {timeframes.map((tf) => (
              <Button
                key={tf.value}
                variant={timeframe === tf.value ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleTimeframeChange(tf.value)}
                className="text-xs"
              >
                {tf.label}
              </Button>
            ))}
          </div>

          <div className="ml-auto flex items-center gap-2">
            <input
              type="text"
              value={symbol}
              onChange={handleSymbolChange}
              className="px-2 py-1 text-sm border rounded-md dark:bg-gray-800 dark:border-gray-700"
              placeholder="Symbole"
            />
            <Button
              variant="default"
              size="sm"
              onClick={loadData}
              disabled={isLoading}
            >
              {isLoading ? <Spinner className="h-4 w-4" /> : 'Charger'}
            </Button>
          </div>
        </div>

        {/* Indicateurs */}
        {showIndicators && (
          <div className="flex flex-wrap items-center gap-2 mb-4">
            <span className="text-sm font-medium text-gray-600 dark:text-gray-400">
              Indicateurs:
            </span>
            {availableIndicators.map((indicator) => (
              <Button
                key={indicator.id}
                variant={selectedIndicators.includes(indicator.id) ? 'default' : 'outline'}
                size="sm"
                onClick={() => handleIndicatorToggle(indicator.id)}
                className="text-xs"
                style={{
                  borderColor: selectedIndicators.includes(indicator.id)
                    ? indicator.color
                    : undefined,
                }}
              >
                <span
                  className="w-2 h-2 rounded-full inline-block mr-1"
                  style={{
                    backgroundColor: selectedIndicators.includes(indicator.id)
                      ? indicator.color
                      : 'transparent',
                  }}
                />
                {indicator.name}
              </Button>
            ))}
          </div>
        )}

        {/* Graphique */}
        <div className="relative">
          {isLoading && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/50 dark:bg-gray-900/50 z-10">
              <Spinner className="h-8 w-8" />
              <span className="ml-2 text-gray-600 dark:text-gray-400">
                Chargement des données...
              </span>
            </div>
          )}
          {error && (
            <div className="absolute inset-0 flex items-center justify-center bg-white/50 dark:bg-gray-900/50 z-10">
              <div className="text-center text-red-600">
                <p className="text-lg font-semibold">⚠️ {error}</p>
                <Button
                  variant="default"
                  size="sm"
                  onClick={loadData}
                  className="mt-2"
                >
                  Réessayer
                </Button>
              </div>
            </div>
          )}
          <div
            ref={chartContainerRef}
            className={cn(
              'w-full transition-all',
              isFullscreen ? 'h-[calc(100vh-200px)]' : 'h-[500px]'
            )}
            style={{ height: isFullscreen ? 'calc(100vh - 200px)' : height }}
          />
        </div>

        {/* Informations */}
        <div className="flex flex-wrap justify-between items-center mt-4 text-sm text-gray-500 dark:text-gray-400">
          <div>
            Dernière mise à jour:{' '}
            {data.length > 0
              ? formatDate(data[data.length - 1].time * 1000)
              : 'En attente...'}
          </div>
          <div className="flex items-center gap-4">
            <span>
              Bougies: {data.length}
            </span>
            {isConnected && (
              <span className="flex items-center gap-1">
                <span className="w-2 h-2 rounded-full bg-green-500" />
                Connecté en temps réel
              </span>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

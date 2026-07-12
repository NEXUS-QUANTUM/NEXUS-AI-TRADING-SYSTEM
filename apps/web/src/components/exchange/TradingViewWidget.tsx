// apps/web/src/components/exchange/TradingViewWidget.tsx
'use client';

import React, {
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
  forwardRef,
  Ref,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ArrowsUpDownIcon,
  ArrowPathIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  EllipsisHorizontalIcon,
  PlusIcon,
  MinusIcon,
  AdjustmentsHorizontalIcon,
  DocumentTextIcon,
  ShareIcon,
  LinkIcon,
  BookmarkIcon,
  HeartIcon,
  StarIcon,
  FlagIcon,
  PrinterIcon,
  EnvelopeIcon,
  ClipboardIcon,
  ClockIcon,
  CalendarIcon,
  ChartBarIcon,
  ChartPieIcon,
  Cog6ToothIcon,
  XMarkIcon,
  CheckIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  RectangleGroupIcon,
  Squares2X2Icon,
  ListBulletIcon,
  EyeIcon,
  EyeSlashIcon,
  PlayIcon,
  PauseIcon,
  StopIcon,
  ArrowRightIcon,
  ArrowLeftIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
} from '@heroicons/react/24/outline';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Select } from '@/components/common/Select';
import { Input } from '@/components/common/Input';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/common/Tabs';
import { Tooltip } from '@/components/common/Tooltip';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type TradingViewTheme = 'light' | 'dark' | 'system';
export type TradingViewChartType = 'candlestick' | 'line' | 'area' | 'bars' | 'hollow_candlestick' | 'heikin_ashi' | 'renko' | 'kagi' | 'point_and_figure';
export type TradingViewInterval = '1' | '3' | '5' | '15' | '30' | '60' | '120' | '240' | '360' | '720' | 'D' | 'W' | 'M';
export type TradingViewTimezone = 'Etc/UTC' | 'Europe/London' | 'Europe/Paris' | 'America/New_York' | 'America/Chicago' | 'America/Los_Angeles' | 'Asia/Tokyo' | 'Asia/Singapore' | 'Australia/Sydney';
export type TradingViewRange = '1D' | '5D' | '1M' | '3M' | '6M' | 'YTD' | '1Y' | '2Y' | '5Y' | 'ALL';

export interface TradingViewWidgetProps {
  // --- Configuration ---
  /** Symbole à afficher */
  symbol?: string;
  /** Intervalle de temps */
  interval?: TradingViewInterval;
  /** Thème */
  theme?: TradingViewTheme;
  /** Type de graphique */
  chartType?: TradingViewChartType;
  /** Timezone */
  timezone?: TradingViewTimezone;
  /** Période affichée */
  range?: TradingViewRange;

  // --- Apparence ---
  /** Titre */
  title?: string;
  /** Hauteur */
  height?: number | string;
  /** Largeur */
  width?: number | string;
  /** Classes additionnelles */
  className?: string;
  /** Afficher le header */
  showHeader?: boolean;
  /** Afficher la toolbar */
  showToolbar?: boolean;
  /** Afficher les indicateurs par défaut */
  showIndicators?: boolean;
  /** Afficher le volume */
  showVolume?: boolean;
  /** Afficher la légende */
  showLegend?: boolean;
  /** Afficher les échelles */
  showScales?: boolean;
  /** Afficher le timer */
  showTimer?: boolean;

  // --- Indicateurs ---
  /** Indicateurs à afficher par défaut */
  defaultIndicators?: string[];
  /** Indicateurs disponibles */
  availableIndicators?: string[];
  /** Autoriser l'ajout d'indicateurs */
  allowIndicators?: boolean;

  // --- Actions ---
  /** Callback lors du changement de symbole */
  onSymbolChange?: (symbol: string) => void;
  /** Callback lors du changement d'intervalle */
  onIntervalChange?: (interval: TradingViewInterval) => void;
  /** Callback lors du changement de période */
  onRangeChange?: (range: TradingViewRange) => void;
  /** Callback lors du clic sur un point */
  onChartClick?: (data: any) => void;
  /** Callback lors du chargement */
  onLoad?: () => void;
  /** Callback lors d'une erreur */
  onError?: (error: string) => void;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ID */
  id?: string;

  // --- Avancé ---
  /** Clé API (optionnelle) */
  apiKey?: string;
  /** URL de l'iframe */
  widgetUrl?: string;
  /** Désactiver le chargement automatique */
  disableAutoLoad?: boolean;
  /** Délai de chargement (ms) */
  loadDelay?: number;
  /** Couleurs personnalisées */
  customColors?: {
    background?: string;
    text?: string;
    up?: string;
    down?: string;
    grid?: string;
    border?: string;
  };
  /** Langue */
  language?: 'fr' | 'en' | 'es' | 'de' | 'it' | 'pt' | 'ru' | 'ja' | 'zh' | 'ko';
}

// ============================================================================
// CONSTANTES
// ============================================================================

const INTERVAL_LABELS: Record<TradingViewInterval, string> = {
  '1': '1m',
  '3': '3m',
  '5': '5m',
  '15': '15m',
  '30': '30m',
  '60': '1h',
  '120': '2h',
  '240': '4h',
  '360': '6h',
  '720': '12h',
  'D': '1j',
  'W': '1s',
  'M': '1m',
};

const RANGE_LABELS: Record<TradingViewRange, string> = {
  '1D': '1j',
  '5D': '5j',
  '1M': '1m',
  '3M': '3m',
  '6M': '6m',
  'YTD': 'YTD',
  '1Y': '1a',
  '2Y': '2a',
  '5Y': '5a',
  'ALL': 'Tout',
};

const CHART_TYPE_LABELS: Record<TradingViewChartType, string> = {
  candlestick: 'Chandeliers',
  line: 'Ligne',
  area: 'Zone',
  bars: 'Barres',
  hollow_candlestick: 'Chandeliers creux',
  heikin_ashi: 'Heikin Ashi',
  renko: 'Renko',
  kagi: 'Kagi',
  point_and_figure: 'Points & Figures',
};

const TIMEZONE_LABELS: Record<TradingViewTimezone, string> = {
  'Etc/UTC': 'UTC',
  'Europe/London': 'Londres',
  'Europe/Paris': 'Paris',
  'America/New_York': 'New York',
  'America/Chicago': 'Chicago',
  'America/Los_Angeles': 'Los Angeles',
  'Asia/Tokyo': 'Tokyo',
  'Asia/Singapore': 'Singapour',
  'Australia/Sydney': 'Sydney',
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const TradingViewWidget = forwardRef<HTMLDivElement, TradingViewWidgetProps>(
  (props, ref) => {
    const {
      // Configuration
      symbol = 'BTCUSD',
      interval = 'D',
      theme = 'dark',
      chartType = 'candlestick',
      timezone = 'Europe/Paris',
      range = '1M',

      // Apparence
      title = 'Graphique TradingView',
      height = 500,
      width = '100%',
      className,
      showHeader = true,
      showToolbar = true,
      showIndicators = true,
      showVolume = true,
      showLegend = true,
      showScales = true,
      showTimer = true,

      // Indicateurs
      defaultIndicators = [],
      availableIndicators = ['MA', 'EMA', 'MACD', 'RSI', 'BB', 'SAR', 'ICHIMOKU'],
      allowIndicators = true,

      // Actions
      onSymbolChange,
      onIntervalChange,
      onRangeChange,
      onChartClick,
      onLoad,
      onError,

      // Accessibilité
      ariaLabel = 'Graphique TradingView',
      id,

      // Avancé
      apiKey,
      widgetUrl = 'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.html',
      disableAutoLoad = false,
      loadDelay = 500,
      customColors,
      language = 'fr',
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const containerRef = useRef<HTMLDivElement>(null);
    const widgetRef = useRef<HTMLIFrameElement>(null);
    const timerRef = useRef<NodeJS.Timeout | null>(null);
    const messageListenerRef = useRef<((event: MessageEvent) => void) | null>(null);

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [currentSymbol, setCurrentSymbol] = useState(symbol);
    const [currentInterval, setCurrentInterval] = useState(interval);
    const [currentRange, setCurrentRange] = useState(range);
    const [currentTheme, setCurrentTheme] = useState(theme);
    const [currentChartType, setCurrentChartType] = useState(chartType);
    const [isLoading, setIsLoading] = useState(true);
    const [isFullscreen, setIsFullscreen] = useState(false);
    const [isReady, setIsReady] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [searchSymbol, setSearchSymbol] = useState('');
    const [showSearch, setShowSearch] = useState(false);
    const [suggestions, setSuggestions] = useState<string[]>([]);

    // ========================================================================
    // WIDGET CONFIG
    // ========================================================================

    const widgetConfig = useMemo(() => {
      const colors = customColors || {};
      
      return {
        symbol: currentSymbol,
        interval: currentInterval,
        theme: currentTheme,
        chartType: currentChartType,
        timezone: timezone,
        range: currentRange,
        language: language,
        container_id: 'tradingview-widget-container',
        width: typeof width === 'number' ? `${width}px` : width,
        height: typeof height === 'number' ? `${height}px` : height,
        hide_side_toolbar: !showToolbar,
        allow_symbol_change: true,
        save_image: true,
        details: true,
        news: ['headlines'],
        studies: defaultIndicators,
        show_volume: showVolume,
        show_legend: showLegend,
        show_scales: showScales,
        show_timer: showTimer,
        backgroundColor: colors.background || '#1e222d',
        textColor: colors.text || '#d1d4dc',
        upColor: colors.up || '#26a69a',
        downColor: colors.down || '#ef5350',
        gridColor: colors.grid || '#2a2e39',
        borderColor: colors.border || '#2a2e39',
      };
    }, [
      currentSymbol,
      currentInterval,
      currentTheme,
      currentChartType,
      timezone,
      currentRange,
      language,
      width,
      height,
      showToolbar,
      defaultIndicators,
      showVolume,
      showLegend,
      showScales,
      showTimer,
      customColors,
    ]);

    // ========================================================================
    // GÉNÉRATION DE L'URL DU WIDGET
    // ========================================================================

    const generateWidgetUrl = useCallback(() => {
      const params = new URLSearchParams({
        symbol: currentSymbol,
        interval: currentInterval,
        theme: currentTheme,
        style: String(Object.values(TradingViewChartType).indexOf(currentChartType)),
        timezone: timezone,
        range: currentRange,
        lang: language,
        allow_symbol_change: 'true',
        save_image: 'true',
        details: 'true',
        news: '["headlines"]',
        studies: JSON.stringify(defaultIndicators),
        show_volume: String(showVolume),
        show_legend: String(showLegend),
        show_scales: String(showScales),
        show_timer: String(showTimer),
        hide_side_toolbar: String(!showToolbar),
        backgroundColor: customColors?.background || '',
        textColor: customColors?.text || '',
        upColor: customColors?.up || '',
        downColor: customColors?.down || '',
        gridColor: customColors?.grid || '',
        borderColor: customColors?.border || '',
      });

      return `${widgetUrl}?${params.toString()}`;
    }, [
      currentSymbol,
      currentInterval,
      currentTheme,
      currentChartType,
      timezone,
      currentRange,
      language,
      defaultIndicators,
      showVolume,
      showLegend,
      showScales,
      showTimer,
      showToolbar,
      customColors,
      widgetUrl,
    ]);

    // ========================================================================
    // CHARGEMENT DU WIDGET
    // ========================================================================

    const loadWidget = useCallback(() => {
      if (disableAutoLoad) return;

      setIsLoading(true);
      setError(null);

      if (timerRef.current) {
        clearTimeout(timerRef.current);
      }

      timerRef.current = setTimeout(() => {
        try {
          const url = generateWidgetUrl();
          
          // Créer l'iframe
          const iframe = document.createElement('iframe');
          iframe.src = url;
          iframe.style.width = '100%';
          iframe.style.height = '100%';
          iframe.style.border = 'none';
          iframe.allow = 'autoplay; encrypted-media; fullscreen';
          iframe.setAttribute('allowfullscreen', 'true');
          iframe.setAttribute('loading', 'lazy');
          iframe.setAttribute('aria-label', ariaLabel);
          iframe.id = `tradingview-widget-${id || 'main'}`;

          // Nettoyer le conteneur
          if (containerRef.current) {
            containerRef.current.innerHTML = '';
            containerRef.current.appendChild(iframe);
            widgetRef.current = iframe;
          }

          setIsLoading(false);
          setIsReady(true);
          if (onLoad) onLoad();

          toast({
            title: 'Graphique chargé',
            description: `Graphique ${currentSymbol} chargé avec succès`,
            duration: 3000,
          });
        } catch (err) {
          const errorMessage = err instanceof Error ? err.message : 'Erreur de chargement';
          setError(errorMessage);
          if (onError) onError(errorMessage);
          
          toast({
            title: 'Erreur de chargement',
            description: errorMessage,
            variant: 'destructive',
          });
        }
      }, loadDelay);

      return () => {
        if (timerRef.current) {
          clearTimeout(timerRef.current);
        }
      };
    }, [
      disableAutoLoad,
      generateWidgetUrl,
      loadDelay,
      ariaLabel,
      id,
      onLoad,
      onError,
      toast,
      currentSymbol,
    ]);

    // ========================================================================
    // GESTION DES MESSAGES POST-MESSAGE
    // ========================================================================

    useEffect(() => {
      const handleMessage = (event: MessageEvent) => {
        // Vérifier l'origine (à configurer selon vos besoins)
        if (!event.origin.includes('tradingview.com')) return;

        try {
          const data = JSON.parse(event.data);
          
          switch (data.name) {
            case 'onChartClick':
              if (onChartClick) onChartClick(data.data);
              break;
            case 'onSymbolChange':
              if (data.data && data.data.symbol) {
                setCurrentSymbol(data.data.symbol);
                if (onSymbolChange) onSymbolChange(data.data.symbol);
              }
              break;
            case 'onIntervalChange':
              if (data.data && data.data.interval) {
                setCurrentInterval(data.data.interval);
                if (onIntervalChange) onIntervalChange(data.data.interval);
              }
              break;
            case 'onRangeChange':
              if (data.data && data.data.range) {
                setCurrentRange(data.data.range);
                if (onRangeChange) onRangeChange(data.data.range);
              }
              break;
            default:
              break;
          }
        } catch (e) {
          // Ignorer les messages non-JSON
        }
      };

      messageListenerRef.current = handleMessage;
      window.addEventListener('message', handleMessage);

      return () => {
        if (messageListenerRef.current) {
          window.removeEventListener('message', messageListenerRef.current);
        }
      };
    }, [onChartClick, onSymbolChange, onIntervalChange, onRangeChange]);

    // ========================================================================
    // RECHERCHE DE SYMBOLES
    // ========================================================================

    const searchSymbols = useCallback((query: string) => {
      // Simuler une recherche de symboles (à remplacer par une vraie API)
      const mockSymbols = [
        'BTCUSD', 'ETHUSD', 'BNBUSD', 'XRPUSD', 'ADAUSD',
        'SOLUSD', 'DOTUSD', 'DOGEUSD', 'MATICUSD', 'LINKUSD',
        'AAPL', 'GOOGL', 'MSFT', 'AMZN', 'TSLA',
        'EURUSD', 'GBPUSD', 'USDJPY', 'AUDUSD', 'USDCAD',
      ];

      if (!query) return mockSymbols.slice(0, 10);
      
      const lowerQuery = query.toLowerCase();
      return mockSymbols
        .filter((s) => s.toLowerCase().includes(lowerQuery))
        .slice(0, 10);
    }, []);

    const handleSearchChange = useCallback((value: string) => {
      setSearchSymbol(value);
      if (value.length > 0) {
        const results = searchSymbols(value);
        setSuggestions(results);
      } else {
        setSuggestions([]);
      }
    }, [searchSymbols]);

    const handleSymbolSelect = useCallback((selectedSymbol: string) => {
      setCurrentSymbol(selectedSymbol);
      setSearchSymbol('');
      setSuggestions([]);
      setShowSearch(false);
      if (onSymbolChange) onSymbolChange(selectedSymbol);
      
      // Recharger le widget avec le nouveau symbole
      loadWidget();
      
      toast({
        title: 'Symbole changé',
        description: `Graphique ${selectedSymbol} chargé`,
        duration: 2000,
      });
    }, [onSymbolChange, loadWidget, toast]);

    // ========================================================================
    // PLEIN ÉCRAN
    // ========================================================================

    const toggleFullscreen = useCallback(() => {
      const element = containerRef.current;
      if (!element) return;

      if (!document.fullscreenElement) {
        element.requestFullscreen?.();
        setIsFullscreen(true);
      } else {
        document.exitFullscreen?.();
        setIsFullscreen(false);
      }
    }, []);

    useEffect(() => {
      const handleFullscreenChange = () => {
        setIsFullscreen(!!document.fullscreenElement);
      };

      document.addEventListener('fullscreenchange', handleFullscreenChange);
      return () => document.removeEventListener('fullscreenchange', handleFullscreenChange);
    }, []);

    // ========================================================================
    // CHARGEMENT INITIAL
    // ========================================================================

    useEffect(() => {
      loadWidget();
      
      return () => {
        if (timerRef.current) {
          clearTimeout(timerRef.current);
        }
        if (widgetRef.current && containerRef.current) {
          containerRef.current.innerHTML = '';
        }
      };
    }, [loadWidget]);

    // ========================================================================
    // RENDU DES INDICATEURS
    // ========================================================================

    const renderIndicators = useCallback(() => {
      if (!showIndicators || !allowIndicators) return null;

      return (
        <div className="flex flex-wrap gap-1 p-2 border-t border-gray-200 dark:border-gray-700">
          {availableIndicators.map((indicator) => (
            <Badge
              key={indicator}
              variant={defaultIndicators.includes(indicator) ? 'primary' : 'outline'}
              className="cursor-pointer transition-colors hover:opacity-80"
              onClick={() => {
                // Ajouter/supprimer l'indicateur
                // À implémenter avec l'API TradingView
                toast({
                  title: indicator,
                  description: defaultIndicators.includes(indicator) 
                    ? 'Indicateur retiré' 
                    : 'Indicateur ajouté',
                  duration: 2000,
                });
              }}
            >
              {indicator}
            </Badge>
          ))}
        </div>
      );
    }, [showIndicators, allowIndicators, availableIndicators, defaultIndicators, toast]);

    // ========================================================================
    // RENDU DE LA TOOLBAR
    // ========================================================================

    const renderToolbar = useCallback(() => {
      if (!showToolbar) return null;

      const intervals: TradingViewInterval[] = ['1', '5', '15', '30', '60', '240', 'D', 'W', 'M'];
      const ranges: TradingViewRange[] = ['1D', '5D', '1M', '3M', '6M', 'YTD', '1Y', '2Y', '5Y', 'ALL'];

      return (
        <div className="flex flex-wrap items-center gap-1 p-2 border-b border-gray-200 dark:border-gray-700 bg-gray-50 dark:bg-gray-800/50">
          {/* Symbole */}
          <div className="relative flex items-center">
            <Button
              variant="ghost"
              size="sm"
              className="font-mono font-semibold"
              onClick={() => setShowSearch(!showSearch)}
            >
              {currentSymbol}
              <ChevronDownIcon className="ml-1 h-3 w-3" />
            </Button>

            {showSearch && (
              <div className="absolute left-0 top-full mt-1 z-50 w-64 rounded-lg border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-lg p-2">
                <Input
                  type="text"
                  placeholder="Rechercher un symbole..."
                  value={searchSymbol}
                  onChange={(e) => handleSearchChange(e.target.value)}
                  autoFocus
                  className="h-8 text-sm"
                />
                {suggestions.length > 0 && (
                  <div className="mt-1 max-h-48 overflow-y-auto">
                    {suggestions.map((s) => (
                      <button
                        key={s}
                        className="w-full px-2 py-1 text-left text-sm hover:bg-gray-100 dark:hover:bg-gray-800 rounded transition-colors"
                        onClick={() => handleSymbolSelect(s)}
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <Separator orientation="vertical" className="h-6" />

          {/* Intervalles */}
          {intervals.map((i) => (
            <Button
              key={i}
              variant={currentInterval === i ? 'primary' : 'ghost'}
              size="xs"
              className="h-6 px-2 text-xs font-mono"
              onClick={() => {
                setCurrentInterval(i);
                if (onIntervalChange) onIntervalChange(i);
                loadWidget();
              }}
            >
              {INTERVAL_LABELS[i]}
            </Button>
          ))}

          <Separator orientation="vertical" className="h-6" />

          {/* Périodes */}
          {ranges.map((r) => (
            <Button
              key={r}
              variant={currentRange === r ? 'primary' : 'ghost'}
              size="xs"
              className="h-6 px-2 text-xs"
              onClick={() => {
                setCurrentRange(r);
                if (onRangeChange) onRangeChange(r);
                loadWidget();
              }}
            >
              {RANGE_LABELS[r]}
            </Button>
          ))}

          <div className="flex-1" />

          {/* Type de graphique */}
          <Select
            options={Object.entries(CHART_TYPE_LABELS).map(([value, label]) => ({
              value,
              label,
            }))}
            value={currentChartType}
            onChange={(value) => {
              setCurrentChartType(value as TradingViewChartType);
              loadWidget();
            }}
            size="xs"
            className="w-36"
          />

          {/* Thème */}
          <Button
            variant="ghost"
            size="xs"
            onClick={() => {
              setCurrentTheme(currentTheme === 'dark' ? 'light' : 'dark');
              loadWidget();
            }}
          >
            {currentTheme === 'dark' ? '☀️' : '🌙'}
          </Button>

          {/* Plein écran */}
          <Button
            variant="ghost"
            size="xs"
            onClick={toggleFullscreen}
          >
            {isFullscreen ? (
              <ArrowsPointingInIcon className="h-4 w-4" />
            ) : (
              <ArrowsPointingOutIcon className="h-4 w-4" />
            )}
          </Button>

          {/* Rafraîchir */}
          <Button
            variant="ghost"
            size="xs"
            onClick={loadWidget}
            disabled={isLoading}
          >
            <ArrowPathIcon className={cn('h-4 w-4', isLoading && 'animate-spin')} />
          </Button>
        </div>
      );
    }, [
      showToolbar,
      currentSymbol,
      currentInterval,
      currentRange,
      currentChartType,
      currentTheme,
      isLoading,
      isFullscreen,
      showSearch,
      searchSymbol,
      suggestions,
      onIntervalChange,
      onRangeChange,
      loadWidget,
      toggleFullscreen,
      handleSearchChange,
      handleSymbolSelect,
    ]);

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    return (
      <Card
        ref={ref}
        id={id}
        className={cn(
          'overflow-hidden',
          isFullscreen && 'fixed inset-0 z-[9999] rounded-none',
          className
        )}
        aria-label={ariaLabel}
      >
        {/* Header */}
        {showHeader && (
          <CardHeader className="flex flex-row items-center justify-between border-b border-gray-200 dark:border-gray-700">
            <CardTitle className="flex items-center gap-2">
              {title}
              <Badge variant="outline" className="font-mono">
                {currentSymbol}
              </Badge>
              {isReady && (
                <Badge variant="success" size="sm" className="flex items-center gap-1">
                  <span className="inline-block h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                  Live
                </Badge>
              )}
            </CardTitle>
            <div className="flex items-center gap-2">
              <span className="text-xs text-gray-500 dark:text-gray-400">
                {INTERVAL_LABELS[currentInterval]} • {RANGE_LABELS[currentRange]}
              </span>
            </div>
          </CardHeader>
        )}

        {/* Toolbar */}
        {renderToolbar()}

        {/* Graphique */}
        <div
          className="relative"
          style={{
            height: typeof height === 'number' ? `${height}px` : height,
            width: typeof width === 'number' ? `${width}px` : width,
          }}
        >
          {isLoading && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-100 dark:bg-gray-800">
              <div className="h-12 w-12 animate-spin rounded-full border-4 border-brand-500 border-t-transparent" />
              <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
                Chargement du graphique...
              </p>
            </div>
          )}

          {error && (
            <div className="absolute inset-0 flex flex-col items-center justify-center bg-gray-100 dark:bg-gray-800">
              <ExclamationTriangleIcon className="h-12 w-12 text-red-500" />
              <p className="mt-3 text-sm text-red-600 dark:text-red-400">{error}</p>
              <Button
                variant="outline"
                size="sm"
                className="mt-3"
                onClick={loadWidget}
              >
                Réessayer
              </Button>
            </div>
          )}

          <div
            ref={containerRef}
            className="h-full w-full"
            style={{ display: isLoading || error ? 'none' : 'block' }}
          />
        </div>

        {/* Indicateurs */}
        {renderIndicators()}

        {/* Footer */}
        {showHeader && (
          <CardFooter className="border-t border-gray-200 dark:border-gray-700 px-4 py-2 text-xs text-gray-400">
            <div className="flex items-center justify-between w-full">
              <span>
                Données en temps réel fournies par TradingView
              </span>
              <span>
                {currentSymbol} • {new Date().toLocaleTimeString()}
              </span>
            </div>
          </CardFooter>
        )}
      </Card>
    );
  }
);

TradingViewWidget.displayName = 'TradingViewWidget';

// ============================================================================
// EXPORTS
// ============================================================================

export default TradingViewWidget;

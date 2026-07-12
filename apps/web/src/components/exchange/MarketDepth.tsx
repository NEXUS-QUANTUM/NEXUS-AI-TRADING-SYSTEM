// apps/web/src/components/exchange/MarketDepth.tsx
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
  ArrowUpIcon,
  ArrowDownIcon,
  ArrowTrendingUpIcon,
  ArrowTrendingDownIcon,
  ClockIcon,
  CheckCircleIcon,
  XCircleIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ArrowsUpDownIcon,
  ArrowPathIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  EllipsisHorizontalIcon,
  PlusIcon,
  MinusIcon,
  EyeIcon,
  EyeSlashIcon,
  AdjustmentsHorizontalIcon,
  DocumentTextIcon,
  ShareIcon,
  LinkIcon,
  BookmarkIcon,
  HeartIcon,
  StarIcon,
  FlagIcon,
} from '@heroicons/react/24/outline';
import {
  ArrowUpIcon as ArrowUpSolid,
  ArrowDownIcon as ArrowDownSolid,
} from '@heroicons/react/24/solid';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Progress } from '@/components/common/Progress';
import { Separator } from '@/components/common/Separator';
import { Skeleton } from '@/components/common/Skeleton';
import { Tooltip } from '@/components/common/Tooltip';
import { ScrollArea } from '@/components/common/ScrollArea';
import { Input } from '@/components/common/Input';
import { Select } from '@/components/common/Select';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/common/Tabs';
import { useWebSocket } from '@/hooks/useWebSocket';

// ============================================================================
// TYPES
// ============================================================================

export interface OrderBookLevel {
  /** Prix */
  price: number;
  /** Quantité */
  quantity: number;
  /** Nombre d'ordres */
  count?: number;
  /** Cumulative */
  cumulative?: number;
  /** Pourcentage */
  percentage?: number;
}

export interface OrderBookData {
  /** Offres (ventes) */
  asks: OrderBookLevel[];
  /** Demandes (achats) */
  bids: OrderBookLevel[];
  /** Dernier prix */
  lastPrice?: number;
  /** Variation */
  change?: number;
  /** Variation en pourcentage */
  changePercent?: number;
  /** Volume */
  volume?: number;
  /** Spread */
  spread?: number;
  /** Timestamp */
  timestamp?: Date;
}

export interface MarketDepthProps {
  // --- Données ---
  /** Données du carnet d'ordres */
  data?: OrderBookData;
  /** Symbole */
  symbol?: string;
  /** Chargement en cours */
  isLoading?: boolean;
  /** Erreur */
  error?: string | null;

  // --- WebSocket ---
  /** URL du WebSocket */
  wsUrl?: string;
  /** Activer le WebSocket */
  enableWebSocket?: boolean;
  /** Callback de mise à jour */
  onUpdate?: (data: OrderBookData) => void;

  // --- Apparence ---
  /** Titre */
  title?: string;
  /** Nombre de niveaux à afficher */
  depth?: number;
  /** Afficher les cumulés */
  showCumulative?: boolean;
  /** Afficher les pourcentages */
  showPercentages?: boolean;
  /** Afficher le spread */
  showSpread?: boolean;
  /** Afficher les contrôles */
  showControls?: boolean;
  /** Afficher le résumé */
  showSummary?: boolean;
  /** Afficher le graphique de profondeur */
  showDepthChart?: boolean;
  /** Classes additionnelles */
  className?: string;
  /** Couleur des offres */
  askColor?: string;
  /** Couleur des demandes */
  bidColor?: string;

  // --- Filtres ---
  /** Regrouper par prix */
  groupBy?: number;
  /** Trier par */
  sortBy?: 'price' | 'quantity' | 'cumulative';
  /** Ordre de tri */
  sortOrder?: 'asc' | 'desc';

  // --- Actions ---
  /** Callback lors du clic sur un niveau */
  onLevelClick?: (level: OrderBookLevel, side: 'bid' | 'ask') => void;
  /** Callback pour rafraîchir */
  onRefresh?: () => void;
  /** Callback pour afficher plus */
  onShowMore?: () => void;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ID */
  id?: string;

  // --- Avancé ---
  /** Formater le prix */
  formatPrice?: (price: number) => string;
  /** Formater la quantité */
  formatQuantity?: (quantity: number) => string;
  /** Intervalle de rafraîchissement (ms) */
  refreshInterval?: number;
  /** Désactiver le rafraîchissement automatique */
  disableAutoRefresh?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const DEFAULT_DEPTH = 15;
const DEFAULT_GROUP = 0.01;

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const MarketDepth = forwardRef<HTMLDivElement, MarketDepthProps>(
  (props, ref) => {
    const {
      // Données
      data: externalData,
      symbol = 'BTC/USD',
      isLoading: externalLoading = false,
      error: externalError = null,

      // WebSocket
      wsUrl,
      enableWebSocket = false,
      onUpdate,

      // Apparence
      title = 'Carnet d\'ordres',
      depth = DEFAULT_DEPTH,
      showCumulative = true,
      showPercentages = true,
      showSpread = true,
      showControls = true,
      showSummary = true,
      showDepthChart = false,
      className,
      askColor = 'text-red-500 dark:text-red-400',
      bidColor = 'text-green-500 dark:text-green-400',

      // Filtres
      groupBy = DEFAULT_GROUP,
      sortBy = 'price',
      sortOrder = 'asc',

      // Actions
      onLevelClick,
      onRefresh,
      onShowMore,

      // Accessibilité
      ariaLabel = 'Carnet d\'ordres',
      id,

      // Avancé
      formatPrice,
      formatQuantity,
      refreshInterval = 5000,
      disableAutoRefresh = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const containerRef = useRef<HTMLDivElement>(null);
    const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);
    const previousDataRef = useRef<OrderBookData | null>(null);

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [data, setData] = useState<OrderBookData | null>(externalData || null);
    const [isLoading, setIsLoading] = useState(externalLoading);
    const [error, setError] = useState<string | null>(externalError);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [viewMode, setViewMode] = useState<'levels' | 'chart'>('levels');
    const [groupValue, setGroupValue] = useState(groupBy);
    const [showAll, setShowAll] = useState(false);

    // ========================================================================
    // WEBSOCKET
    // ========================================================================

    const ws = useWebSocket({
      url: wsUrl || '',
      enabled: enableWebSocket,
      onMessage: (message) => {
        try {
          const parsed = JSON.parse(message);
          if (parsed.type === 'depth' && parsed.data) {
            const newData = parsed.data as OrderBookData;
            setData(newData);
            if (onUpdate) onUpdate(newData);
          }
        } catch (e) {
          console.error('Erreur WebSocket:', e);
        }
      },
    });

    // ========================================================================
    // SYNC AVEC LES PROPS EXTERNES
    // ========================================================================

    useEffect(() => {
      setData(externalData || null);
    }, [externalData]);

    useEffect(() => {
      setIsLoading(externalLoading);
    }, [externalLoading]);

    useEffect(() => {
      setError(externalError);
    }, [externalError]);

    // ========================================================================
    // TRAITEMENT DES DONNÉES
    // ========================================================================

    const processedData = useMemo(() => {
      if (!data) return null;

      // Copier les données
      const asks = [...data.asks];
      const bids = [...data.bids];

      // Regrouper par prix
      if (groupValue > 0) {
        const groupAsks: Map<number, OrderBookLevel> = new Map();
        const groupBids: Map<number, OrderBookLevel> = new Map();

        const groupPrice = (price: number) => {
          return Math.round(price / groupValue) * groupValue;
        };

        asks.forEach((level) => {
          const key = groupPrice(level.price);
          const existing = groupAsks.get(key);
          if (existing) {
            existing.quantity += level.quantity;
            existing.count = (existing.count || 0) + (level.count || 1);
          } else {
            groupAsks.set(key, { ...level, price: key });
          }
        });

        bids.forEach((level) => {
          const key = groupPrice(level.price);
          const existing = groupBids.get(key);
          if (existing) {
            existing.quantity += level.quantity;
            existing.count = (existing.count || 0) + (level.count || 1);
          } else {
            groupBids.set(key, { ...level, price: key });
          }
        });

        const groupedAsks = Array.from(groupAsks.values());
        const groupedBids = Array.from(groupBids.values());

        // Trier
        groupedAsks.sort((a, b) => a.price - b.price);
        groupedBids.sort((a, b) => b.price - a.price);

        // Calculer les cumulés
        let cumAsk = 0;
        let cumBid = 0;
        const totalAsk = groupedAsks.reduce((sum, l) => sum + l.quantity, 0);
        const totalBid = groupedBids.reduce((sum, l) => sum + l.quantity, 0);

        groupedAsks.forEach((level) => {
          cumAsk += level.quantity;
          level.cumulative = cumAsk;
          level.percentage = totalAsk > 0 ? (cumAsk / totalAsk) * 100 : 0;
        });

        groupedBids.forEach((level) => {
          cumBid += level.quantity;
          level.cumulative = cumBid;
          level.percentage = totalBid > 0 ? (cumBid / totalBid) * 100 : 0;
        });

        return {
          ...data,
          asks: groupedAsks,
          bids: groupedBids,
        };
      }

      // Calculer les cumulés
      let cumAsk = 0;
      let cumBid = 0;
      const totalAsk = asks.reduce((sum, l) => sum + l.quantity, 0);
      const totalBid = bids.reduce((sum, l) => sum + l.quantity, 0);

      asks.forEach((level) => {
        cumAsk += level.quantity;
        level.cumulative = cumAsk;
        level.percentage = totalAsk > 0 ? (cumAsk / totalAsk) * 100 : 0;
      });

      bids.forEach((level) => {
        cumBid += level.quantity;
        level.cumulative = cumBid;
        level.percentage = totalBid > 0 ? (cumBid / totalBid) * 100 : 0;
      });

      return {
        ...data,
        asks: asks.sort((a, b) => a.price - b.price),
        bids: bids.sort((a, b) => b.price - a.price),
      };
    }, [data, groupValue]);

    // ========================================================================
    // LIMITER LE NOMBRE DE NIVEAUX
    // ========================================================================

    const displayData = useMemo(() => {
      if (!processedData) return null;

      const displayDepth = showAll ? Infinity : depth;
      return {
        ...processedData,
        asks: processedData.asks.slice(0, displayDepth),
        bids: processedData.bids.slice(0, displayDepth),
      };
    }, [processedData, depth, showAll]);

    // ========================================================================
    // STATISTIQUES
    // ========================================================================

    const stats = useMemo(() => {
      if (!displayData) return null;

      const { asks, bids, lastPrice, change, changePercent, volume, spread } = displayData;

      const totalAsk = asks.reduce((sum, l) => sum + l.quantity, 0);
      const totalBid = bids.reduce((sum, l) => sum + l.quantity, 0);
      const totalVolume = totalAsk + totalBid;

      const maxAsk = asks.length > 0 ? asks[asks.length - 1]?.price : 0;
      const minBid = bids.length > 0 ? bids[bids.length - 1]?.price : 0;
      const bestAsk = asks.length > 0 ? asks[0]?.price : 0;
      const bestBid = bids.length > 0 ? bids[0]?.price : 0;

      const currentSpread = spread || (bestAsk > 0 && bestBid > 0 ? bestAsk - bestBid : 0);
      const midPrice = (bestAsk + bestBid) / 2;

      return {
        totalAsk,
        totalBid,
        totalVolume,
        maxAsk,
        minBid,
        bestAsk,
        bestBid,
        spread: currentSpread,
        midPrice,
        lastPrice: lastPrice || midPrice,
        change: change || 0,
        changePercent: changePercent || 0,
        volume: volume || 0,
      };
    }, [displayData]);

    // ========================================================================
    // FORMATAGE
    // ========================================================================

    const defaultFormatPrice = useCallback((price: number): string => {
      return new Intl.NumberFormat('fr-FR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 8,
      }).format(price);
    }, []);

    const defaultFormatQuantity = useCallback((quantity: number): string => {
      return new Intl.NumberFormat('fr-FR', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 4,
      }).format(quantity);
    }, []);

    const formatPriceFn = formatPrice || defaultFormatPrice;
    const formatQuantityFn = formatQuantity || defaultFormatQuantity;

    // ========================================================================
    // RAFRAÎCHISSEMENT
    // ========================================================================

    const handleRefresh = useCallback(async () => {
      if (isRefreshing) return;

      setIsRefreshing(true);
      if (onRefresh) {
        await onRefresh();
      }
      setIsRefreshing(false);
    }, [onRefresh, isRefreshing]);

    // ========================================================================
    // AUTO-REFRESH
    // ========================================================================

    useEffect(() => {
      if (disableAutoRefresh || enableWebSocket) return;

      if (refreshTimerRef.current) {
        clearInterval(refreshTimerRef.current);
      }

      refreshTimerRef.current = setInterval(() => {
        handleRefresh();
      }, refreshInterval);

      return () => {
        if (refreshTimerRef.current) {
          clearInterval(refreshTimerRef.current);
        }
      };
    }, [refreshInterval, disableAutoRefresh, enableWebSocket, handleRefresh]);

    // ========================================================================
    // RENDU
    // ========================================================================

    // --- Rendu du spread ---
    const renderSpread = useCallback(() => {
      if (!showSpread || !stats) return null;

      return (
        <div className="flex items-center justify-between px-4 py-2 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
          <div className="text-sm text-gray-500 dark:text-gray-400">
            Spread
          </div>
          <div className="flex items-center gap-3">
            <span className="font-mono font-medium">
              {formatPriceFn(stats.spread)}
            </span>
            <span className="text-xs text-gray-400">
              ({stats.bestBid > 0 && stats.bestAsk > 0 
                ? ((stats.spread / stats.bestBid) * 100).toFixed(2) 
                : 0}%)
            </span>
          </div>
        </div>
      );
    }, [showSpread, stats, formatPriceFn]);

    // --- Rendu d'un niveau ---
    const renderLevel = useCallback((
      level: OrderBookLevel,
      side: 'bid' | 'ask',
      index: number,
      maxQuantity: number
    ) => {
      const isBid = side === 'bid';
      const color = isBid ? bidColor : askColor;
      const bgColor = isBid 
        ? 'hover:bg-green-50 dark:hover:bg-green-900/10'
        : 'hover:bg-red-50 dark:hover:bg-red-900/10';

      const percentage = maxQuantity > 0 ? (level.quantity / maxQuantity) * 100 : 0;

      return (
        <div
          key={`${side}-${level.price}`}
          className={cn(
            'group relative flex cursor-pointer items-center gap-2 rounded px-3 py-1.5 text-sm transition-colors',
            bgColor
          )}
          onClick={() => onLevelClick?.(level, side)}
        >
          {/* Barre de profondeur */}
          <div
            className={cn(
              'absolute inset-y-0 rounded',
              isBid ? 'right-0 bg-green-100/50 dark:bg-green-900/20' : 'left-0 bg-red-100/50 dark:bg-red-900/20'
            )}
            style={{
              [isBid ? 'width' : 'width']: `${percentage}%`,
              [isBid ? 'right' : 'left']: 0,
            }}
          />

          {/* Contenu */}
          <div className="relative z-10 flex w-full items-center gap-2">
            {/* Prix */}
            <span className={cn('flex-1 font-mono', color)}>
              {formatPriceFn(level.price)}
            </span>

            {/* Quantité */}
            <span className="flex-1 text-right font-mono text-gray-700 dark:text-gray-300">
              {formatQuantityFn(level.quantity)}
            </span>

            {/* Cumulé */}
            {showCumulative && level.cumulative !== undefined && (
              <span className="flex-1 text-right font-mono text-gray-500 dark:text-gray-400">
                {formatQuantityFn(level.cumulative)}
              </span>
            )}

            {/* Pourcentage */}
            {showPercentages && level.percentage !== undefined && (
              <span className="w-12 text-right font-mono text-xs text-gray-400">
                {level.percentage.toFixed(1)}%
              </span>
            )}

            {/* Nombre d'ordres */}
            {level.count && level.count > 1 && (
              <Badge variant="outline" size="xs" className="ml-1">
                {level.count}
              </Badge>
            )}
          </div>
        </div>
      );
    }, [
      bidColor,
      askColor,
      showCumulative,
      showPercentages,
      formatPriceFn,
      formatQuantityFn,
      onLevelClick,
    ]);

    // --- Rendu du carnet ---
    const renderOrderBook = useCallback(() => {
      if (!displayData) return null;

      const { asks, bids } = displayData;
      const maxQuantity = Math.max(
        ...asks.map((l) => l.quantity),
        ...bids.map((l) => l.quantity),
        0
      );

      return (
        <div className="flex flex-col">
          {/* En-tête */}
          <div className="flex items-center gap-2 px-3 py-2 text-xs font-medium text-gray-500 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
            <span className="flex-1">Prix</span>
            <span className="flex-1 text-right">Quantité</span>
            {showCumulative && (
              <span className="flex-1 text-right">Cumulé</span>
            )}
            {showPercentages && (
              <span className="w-12 text-right">%</span>
            )}
          </div>

          {/* Offres (Ventes) */}
          <div className="border-b border-gray-200 dark:border-gray-700">
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 px-3 py-1 bg-gray-50 dark:bg-gray-800/50">
              Ventes ({asks.length})
            </div>
            {asks.map((level, index) => renderLevel(level, 'ask', index, maxQuantity))}
          </div>

          {/* Spread */}
          <div className="py-2 px-3 bg-gray-50 dark:bg-gray-800/50 text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">
              Spread: {formatPriceFn(stats?.spread || 0)}
            </div>
          </div>

          {/* Demandes (Achats) */}
          <div>
            <div className="text-xs font-medium text-gray-500 dark:text-gray-400 px-3 py-1 bg-gray-50 dark:bg-gray-800/50">
              Achats ({bids.length})
            </div>
            {bids.map((level, index) => renderLevel(level, 'bid', index, maxQuantity))}
          </div>
        </div>
      );
    }, [
      displayData,
      showCumulative,
      showPercentages,
      stats,
      renderLevel,
      formatPriceFn,
    ]);

    // --- Rendu du résumé ---
    const renderSummary = useCallback(() => {
      if (!showSummary || !stats) return null;

      const isPositive = stats.change >= 0;

      return (
        <div className="grid grid-cols-2 gap-2 p-4 sm:grid-cols-4">
          <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-3 text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">Dernier prix</div>
            <div className="mt-1 font-mono text-lg font-semibold">
              {formatPriceFn(stats.lastPrice)}
            </div>
          </div>
          <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-3 text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">Variation</div>
            <div className={cn(
              'mt-1 font-mono text-lg font-semibold',
              isPositive ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
            )}>
              {isPositive ? '+' : ''}{stats.changePercent.toFixed(2)}%
            </div>
          </div>
          <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-3 text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">Volume</div>
            <div className="mt-1 font-mono text-lg font-semibold">
              {formatQuantityFn(stats.volume)}
            </div>
          </div>
          <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-3 text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">Spread</div>
            <div className="mt-1 font-mono text-lg font-semibold">
              {formatPriceFn(stats.spread)}
            </div>
          </div>
        </div>
      );
    }, [showSummary, stats, formatPriceFn, formatQuantityFn]);

    // --- Rendu des contrôles ---
    const renderControls = useCallback(() => {
      if (!showControls) return null;

      return (
        <div className="flex flex-wrap items-center gap-2 p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center gap-1">
            <Tooltip content="Group by">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setGroupValue(groupValue === 0 ? 0.01 : 0)}
              >
                <AdjustmentsHorizontalIcon className="h-4 w-4" />
              </Button>
            </Tooltip>
            {groupValue > 0 && (
              <Badge variant="outline" size="sm">
                {groupValue}
              </Badge>
            )}
          </div>

          <Button
            variant="ghost"
            size="sm"
            onClick={() => setShowAll(!showAll)}
          >
            {showAll ? (
              <>
                <MinusIcon className="h-4 w-4" />
                <span className="ml-1">Réduire</span>
              </>
            ) : (
              <>
                <PlusIcon className="h-4 w-4" />
                <span className="ml-1">Plus</span>
              </>
            )}
          </Button>

          <div className="flex-1" />

          <Button
            variant="ghost"
            size="sm"
            onClick={handleRefresh}
            disabled={isRefreshing}
          >
            <ArrowPathIcon className={cn('h-4 w-4', isRefreshing && 'animate-spin')} />
          </Button>

          {ws.isConnected && (
            <Badge variant="success" size="sm" className="flex items-center gap-1">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
              Live
            </Badge>
          )}
        </div>
      );
    }, [showControls, groupValue, showAll, isRefreshing, handleRefresh, ws.isConnected]);

    // --- Rendu du graphique de profondeur ---
    const renderDepthChart = useCallback(() => {
      if (!showDepthChart || !displayData) return null;

      const { asks, bids } = displayData;
      const allPrices = [...bids.map((l) => l.price), ...asks.map((l) => l.price)];
      const allQuantities = [...bids.map((l) => l.cumulative || 0), ...asks.map((l) => l.cumulative || 0)];
      const maxQuantity = Math.max(...allQuantities, 1);
      const minPrice = Math.min(...allPrices);
      const maxPrice = Math.max(...allPrices);
      const range = maxPrice - minPrice || 1;

      // Points pour le graphique
      const bidPoints = bids.map((l) => ({
        x: ((l.price - minPrice) / range) * 100,
        y: ((l.cumulative || 0) / maxQuantity) * 100,
        price: l.price,
        quantity: l.cumulative || 0,
      }));

      const askPoints = asks.map((l) => ({
        x: ((l.price - minPrice) / range) * 100,
        y: ((l.cumulative || 0) / maxQuantity) * 100,
        price: l.price,
        quantity: l.cumulative || 0,
      }));

      return (
        <div className="p-4 border-t border-gray-200 dark:border-gray-700">
          <div className="relative h-32 rounded-lg overflow-hidden bg-gray-50 dark:bg-gray-800/50">
            {/* Axes */}
            <div className="absolute bottom-0 left-0 w-full h-px bg-gray-300 dark:bg-gray-600" />
            <div className="absolute top-0 left-0 w-px h-full bg-gray-300 dark:bg-gray-600" />

            {/* Grille */}
            <div className="absolute inset-0 grid grid-cols-4 grid-rows-4">
              {Array.from({ length: 3 }).map((_, i) => (
                <React.Fragment key={i}>
                  <div 
                    className="border-r border-gray-200/50 dark:border-gray-700/50"
                    style={{ gridColumn: i + 2 }}
                  />
                  <div 
                    className="border-b border-gray-200/50 dark:border-gray-700/50"
                    style={{ gridRow: i + 2 }}
                  />
                </React.Fragment>
              ))}
            </div>

            {/* Courbes */}
            <svg className="absolute inset-0 h-full w-full">
              {/* Bids (verts) */}
              <polyline
                points={bidPoints.map((p) => `${p.x},${100 - p.y}`).join(' ')}
                fill="none"
                stroke="#22c55e"
                strokeWidth="2"
                className="stroke-green-500"
              />
              <polygon
                points={[
                  ...bidPoints.map((p) => `${p.x},${100 - p.y}`),
                  `${bidPoints[bidPoints.length - 1]?.x || 0},100`,
                  `${bidPoints[0]?.x || 0},100`,
                ].join(' ')}
                fill="rgba(34, 197, 94, 0.1)"
              />

              {/* Asks (rouges) */}
              <polyline
                points={askPoints.map((p) => `${p.x},${100 - p.y}`).join(' ')}
                fill="none"
                stroke="#ef4444"
                strokeWidth="2"
                className="stroke-red-500"
              />
              <polygon
                points={[
                  ...askPoints.map((p) => `${p.x},${100 - p.y}`),
                  `${askPoints[0]?.x || 0},100`,
                  `${askPoints[askPoints.length - 1]?.x || 0},100`,
                ].join(' ')}
                fill="rgba(239, 68, 68, 0.1)"
              />

              {/* Point médian */}
              {stats && (
                <circle
                  cx={50}
                  cy={50}
                  r="4"
                  fill="#6366f1"
                  className="stroke-brand-500"
                />
              )}
            </svg>

            {/* Labels */}
            <div className="absolute bottom-1 left-2 text-[10px] text-gray-400">
              {formatPriceFn(minPrice)}
            </div>
            <div className="absolute bottom-1 right-2 text-[10px] text-gray-400">
              {formatPriceFn(maxPrice)}
            </div>
            <div className="absolute top-1 left-2 text-[10px] text-gray-400">
              {formatQuantityFn(maxQuantity)}
            </div>
          </div>

          <div className="mt-2 flex justify-between text-xs text-gray-500 dark:text-gray-400">
            <div className="flex items-center gap-2">
              <span className="inline-block h-2 w-4 rounded bg-green-500" />
              <span>Demandes</span>
            </div>
            <div className="flex items-center gap-2">
              <span className="inline-block h-2 w-4 rounded bg-red-500" />
              <span>Offres</span>
            </div>
          </div>
        </div>
      );
    }, [showDepthChart, displayData, stats, formatPriceFn, formatQuantityFn]);

    // --- Rendu des squelettes ---
    const renderSkeletons = useCallback(() => {
      return (
        <div className="p-4 space-y-2">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-8 w-full" />
          ))}
        </div>
      );
    }, []);

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    return (
      <Card
        ref={ref}
        id={id}
        className={cn('overflow-hidden', className)}
        aria-label={ariaLabel}
      >
        {/* Header */}
        <CardHeader className="flex flex-row items-center justify-between border-b border-gray-200 dark:border-gray-700">
          <div>
            <CardTitle className="flex items-center gap-2">
              {title}
              <Badge variant="outline" className="font-mono">
                {symbol}
              </Badge>
            </CardTitle>
          </div>
          <div className="flex items-center gap-2">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setViewMode(viewMode === 'levels' ? 'chart' : 'levels')}
            >
              {viewMode === 'levels' ? (
                <AdjustmentsHorizontalIcon className="h-4 w-4" />
              ) : (
                <DocumentTextIcon className="h-4 w-4" />
              )}
            </Button>
          </div>
        </CardHeader>

        {/* Résumé */}
        {renderSummary()}

        {/* Contrôles */}
        {renderControls()}

        {/* Spread */}
        {renderSpread()}

        {/* Contenu */}
        {error ? (
          <div className="flex flex-col items-center justify-center py-12 text-center text-red-600 dark:text-red-400">
            <ExclamationTriangleIcon className="h-12 w-12" />
            <p className="mt-3 text-sm">{error}</p>
            <Button
              variant="outline"
              size="sm"
              className="mt-3"
              onClick={handleRefresh}
            >
              Réessayer
            </Button>
          </div>
        ) : isLoading ? (
          renderSkeletons()
        ) : displayData ? (
          <>
            {viewMode === 'levels' ? (
              <ScrollArea className="max-h-[500px]">
                {renderOrderBook()}
              </ScrollArea>
            ) : (
              renderDepthChart()
            )}
          </>
        ) : (
          <div className="flex flex-col items-center justify-center py-12 text-center text-gray-500 dark:text-gray-400">
            <InformationCircleIcon className="h-12 w-12" />
            <p className="mt-3 text-sm">Aucune donnée disponible</p>
          </div>
        )}

        {/* Footer */}
        <CardFooter className="border-t border-gray-200 dark:border-gray-700 px-4 py-2 text-xs text-gray-400">
          <div className="flex items-center justify-between w-full">
            <span>
              {displayData ? `${displayData.bids.length} achats • ${displayData.asks.length} ventes` : 'En attente de données'}
            </span>
            <span>
              {data?.timestamp ? new Date(data.timestamp).toLocaleTimeString() : ''}
            </span>
          </div>
        </CardFooter>
      </Card>
    );
  }
);

MarketDepth.displayName = 'MarketDepth';

// ============================================================================
// EXPORTS
// ============================================================================

export default MarketDepth;

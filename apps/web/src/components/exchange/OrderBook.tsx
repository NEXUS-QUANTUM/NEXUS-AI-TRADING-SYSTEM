// apps/web/src/components/exchange/OrderBook.tsx
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
  PrinterIcon,
  EnvelopeIcon,
  ClipboardIcon,
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
import { useToast } from '@/hooks/useToast';

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
  /** Changement depuis la dernière mise à jour */
  change?: 'new' | 'update' | 'delete' | 'none';
  /** ID de l'ordre */
  orderId?: string;
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
  /** Volume en 24h */
  volume24h?: number;
  /** Plus haut */
  high?: number;
  /** Plus bas */
  low?: number;
  /** Spread */
  spread?: number;
  /** Spread en pourcentage */
  spreadPercent?: number;
  /** Timestamp */
  timestamp?: Date;
  /** Séquence */
  sequence?: number;
}

export type OrderBookView = 'depth' | 'levels' | 'heatmap' | 'both';
export type OrderBookSide = 'asks' | 'bids' | 'both';
export type OrderBookGrouping = number | 'auto' | 'none';

export interface OrderBookProps {
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
  /** Vue par défaut */
  defaultView?: OrderBookView;
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
  /** Afficher la heatmap */
  showHeatmap?: boolean;
  /** Classes additionnelles */
  className?: string;
  /** Couleur des offres */
  askColor?: string;
  /** Couleur des demandes */
  bidColor?: string;
  /** Couleur de la heatmap */
  heatmapColor?: string;

  // --- Filtres ---
  /** Regrouper par prix */
  grouping?: OrderBookGrouping;
  /** Afficher le côté */
  side?: OrderBookSide;
  /** Niveau minimum de quantité */
  minQuantity?: number;

  // --- Actions ---
  /** Callback lors du clic sur un niveau */
  onLevelClick?: (level: OrderBookLevel, side: 'bid' | 'ask') => void;
  /** Callback pour rafraîchir */
  onRefresh?: () => void;
  /** Callback pour placer un ordre */
  onPlaceOrder?: (side: 'buy' | 'sell', price: number, quantity: number) => void;

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
  /** Nombre de décimales pour le prix */
  priceDecimals?: number;
  /** Nombre de décimales pour la quantité */
  quantityDecimals?: number;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const DEFAULT_DEPTH = 20;
const DEFAULT_GROUPING: OrderBookGrouping = 'auto';

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const OrderBook = forwardRef<HTMLDivElement, OrderBookProps>(
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
      defaultView = 'both',
      showCumulative = true,
      showPercentages = true,
      showSpread = true,
      showControls = true,
      showSummary = true,
      showHeatmap = true,
      className,
      askColor = 'text-red-500 dark:text-red-400',
      bidColor = 'text-green-500 dark:text-green-400',
      heatmapColor = 'from-red-500 to-green-500',

      // Filtres
      grouping = DEFAULT_GROUPING,
      side = 'both',
      minQuantity = 0,

      // Actions
      onLevelClick,
      onRefresh,
      onPlaceOrder,

      // Accessibilité
      ariaLabel = 'Carnet d\'ordres',
      id,

      // Avancé
      formatPrice,
      formatQuantity,
      refreshInterval = 3000,
      disableAutoRefresh = false,
      priceDecimals = 2,
      quantityDecimals = 4,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const containerRef = useRef<HTMLDivElement>(null);
    const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);
    const previousDataRef = useRef<OrderBookData | null>(null);
    const flashTimerRef = useRef<NodeJS.Timeout | null>(null);

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [data, setData] = useState<OrderBookData | null>(externalData || null);
    const [isLoading, setIsLoading] = useState(externalLoading);
    const [error, setError] = useState<string | null>(externalError);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [view, setView] = useState<OrderBookView>(defaultView);
    const [groupValue, setGroupValue] = useState<number>(0);
    const [showAll, setShowAll] = useState(false);
    const [selectedSide, setSelectedSide] = useState<OrderBookSide>(side);
    const [flashingLevels, setFlashingLevels] = useState<Set<string>>(new Set());

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // WEBSOCKET
    // ========================================================================

    const ws = useWebSocket({
      url: wsUrl || '',
      enabled: enableWebSocket,
      onMessage: (message) => {
        try {
          const parsed = JSON.parse(message);
          if (parsed.type === 'orderbook' && parsed.data) {
            const newData = parsed.data as OrderBookData;
            updateOrderBook(newData);
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
      if (externalData) {
        updateOrderBook(externalData);
      }
    }, [externalData]);

    useEffect(() => {
      setIsLoading(externalLoading);
    }, [externalLoading]);

    useEffect(() => {
      setError(externalError);
    }, [externalError]);

    // ========================================================================
    // MISE À JOUR DU CARNET
    // ========================================================================

    const updateOrderBook = useCallback((newData: OrderBookData) => {
      // Détecter les changements pour les flashs
      if (previousDataRef.current) {
        const prev = previousDataRef.current;
        const newFlashLevels = new Set<string>();

        // Vérifier les offres
        newData.asks.forEach((level) => {
          const prevLevel = prev.asks.find((l) => l.price === level.price);
          if (prevLevel) {
            if (prevLevel.quantity !== level.quantity) {
              newFlashLevels.add(`ask-${level.price}`);
            }
          } else {
            newFlashLevels.add(`ask-${level.price}`);
          }
        });

        // Vérifier les demandes
        newData.bids.forEach((level) => {
          const prevLevel = prev.bids.find((l) => l.price === level.price);
          if (prevLevel) {
            if (prevLevel.quantity !== level.quantity) {
              newFlashLevels.add(`bid-${level.price}`);
            }
          } else {
            newFlashLevels.add(`bid-${level.price}`);
          }
        });

        setFlashingLevels(newFlashLevels);

        // Effacer les flashs après un délai
        if (flashTimerRef.current) {
          clearTimeout(flashTimerRef.current);
        }
        flashTimerRef.current = setTimeout(() => {
          setFlashingLevels(new Set());
        }, 300);
      }

      previousDataRef.current = newData;
      setData(newData);
    }, []);

    // ========================================================================
    // TRAITEMENT DES DONNÉES
    // ========================================================================

    const processedData = useMemo(() => {
      if (!data) return null;

      // Filtrer par quantité minimale
      let asks = data.asks.filter((l) => l.quantity >= minQuantity);
      let bids = data.bids.filter((l) => l.quantity >= minQuantity);

      // Regrouper par prix
      const groupSize = groupValue > 0 ? groupValue : getAutoGroupSize(data);
      
      if (groupSize > 0) {
        const groupAsks = groupLevels(asks, groupSize);
        const groupBids = groupLevels(bids, groupSize);
        asks = groupAsks;
        bids = groupBids;
      }

      // Trier
      asks.sort((a, b) => a.price - b.price);
      bids.sort((a, b) => b.price - a.price);

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
        asks,
        bids,
      };
    }, [data, groupValue, minQuantity]);

    // ========================================================================
    // GROUPEMENT AUTOMATIQUE
    // ========================================================================

    const getAutoGroupSize = useCallback((data: OrderBookData): number => {
      const allPrices = [...data.asks.map((l) => l.price), ...data.bids.map((l) => l.price)];
      if (allPrices.length === 0) return 0;

      const sorted = allPrices.sort((a, b) => a - b);
      const diffs = [];
      for (let i = 1; i < sorted.length; i++) {
        diffs.push(sorted[i] - sorted[i - 1]);
      }
      if (diffs.length === 0) return 0;

      const avgDiff = diffs.reduce((a, b) => a + b, 0) / diffs.length;
      const minDiff = Math.min(...diffs);
      
      // Trouver un multiple de la plus petite différence
      const precision = Math.pow(10, -Math.floor(Math.log10(minDiff)));
      return Math.max(minDiff, Math.round(avgDiff / precision) * precision);
    }, []);

    const groupLevels = useCallback((levels: OrderBookLevel[], groupSize: number): OrderBookLevel[] => {
      const grouped = new Map<number, OrderBookLevel>();

      levels.forEach((level) => {
        const key = Math.round(level.price / groupSize) * groupSize;
        const existing = grouped.get(key);
        if (existing) {
          existing.quantity += level.quantity;
          existing.count = (existing.count || 0) + (level.count || 1);
        } else {
          grouped.set(key, { ...level, price: key });
        }
      });

      return Array.from(grouped.values());
    }, []);

    // ========================================================================
    // LIMITER LE NOMBRE DE NIVEAUX
    // ========================================================================

    const displayData = useMemo(() => {
      if (!processedData) return null;

      const displayDepth = showAll ? Infinity : depth;
      const result: OrderBookData = {
        ...processedData,
        asks: processedData.asks.slice(0, displayDepth),
        bids: processedData.bids.slice(0, displayDepth),
      };

      // Filtrer par côté
      if (selectedSide === 'asks') {
        result.bids = [];
      } else if (selectedSide === 'bids') {
        result.asks = [];
      }

      return result;
    }, [processedData, depth, showAll, selectedSide]);

    // ========================================================================
    // STATISTIQUES
    // ========================================================================

    const stats = useMemo(() => {
      if (!displayData) return null;

      const { asks, bids, lastPrice, change, changePercent, volume, spread } = displayData;

      const totalAsk = asks.reduce((sum, l) => sum + l.quantity, 0);
      const totalBid = bids.reduce((sum, l) => sum + l.quantity, 0);

      const bestAsk = asks.length > 0 ? asks[0]?.price : 0;
      const bestBid = bids.length > 0 ? bids[0]?.price : 0;
      const worstAsk = asks.length > 0 ? asks[asks.length - 1]?.price : 0;
      const worstBid = bids.length > 0 ? bids[bids.length - 1]?.price : 0;

      const currentSpread = spread || (bestAsk > 0 && bestBid > 0 ? bestAsk - bestBid : 0);
      const spreadPercent = bestBid > 0 ? (currentSpread / bestBid) * 100 : 0;
      const midPrice = (bestAsk + bestBid) / 2;

      const imbalance = totalBid > 0 && totalAsk > 0 ? (totalBid - totalAsk) / (totalBid + totalAsk) : 0;

      return {
        totalAsk,
        totalBid,
        bestAsk,
        bestBid,
        worstAsk,
        worstBid,
        spread: currentSpread,
        spreadPercent,
        midPrice,
        lastPrice: lastPrice || midPrice,
        change: change || 0,
        changePercent: changePercent || 0,
        volume: volume || 0,
        imbalance,
        total: totalAsk + totalBid,
      };
    }, [displayData]);

    // ========================================================================
    // FORMATAGE
    // ========================================================================

    const defaultFormatPrice = useCallback((price: number): string => {
      return new Intl.NumberFormat('fr-FR', {
        minimumFractionDigits: priceDecimals,
        maximumFractionDigits: priceDecimals,
      }).format(price);
    }, [priceDecimals]);

    const defaultFormatQuantity = useCallback((quantity: number): string => {
      return new Intl.NumberFormat('fr-FR', {
        minimumFractionDigits: quantityDecimals,
        maximumFractionDigits: quantityDecimals,
      }).format(quantity);
    }, [quantityDecimals]);

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
    // CLEANUP
    // ========================================================================

    useEffect(() => {
      return () => {
        if (flashTimerRef.current) {
          clearTimeout(flashTimerRef.current);
        }
      };
    }, []);

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
              ({stats.spreadPercent.toFixed(2)}%)
            </span>
            <Badge 
              variant={stats.imbalance > 0.1 ? 'success' : stats.imbalance < -0.1 ? 'danger' : 'default'}
              size="sm"
            >
              {stats.imbalance > 0 ? '🟢' : stats.imbalance < 0 ? '🔴' : '⚪'} 
              {Math.abs(stats.imbalance * 100).toFixed(1)}%
            </Badge>
          </div>
        </div>
      );
    }, [showSpread, stats, formatPriceFn]);

    // --- Rendu d'un niveau avec heatmap ---
    const renderLevel = useCallback((
      level: OrderBookLevel,
      side: 'bid' | 'ask',
      index: number,
      maxQuantity: number,
      maxCumulative: number
    ) => {
      const isBid = side === 'bid';
      const color = isBid ? bidColor : askColor;
      const bgColor = isBid 
        ? 'hover:bg-green-50 dark:hover:bg-green-900/10'
        : 'hover:bg-red-50 dark:hover:bg-red-900/10';
      
      const isFlashing = flashingLevels.has(`${side}-${level.price}`);
      const percentage = maxQuantity > 0 ? (level.quantity / maxQuantity) * 100 : 0;
      const cumulativePercent = maxCumulative > 0 ? ((level.cumulative || 0) / maxCumulative) * 100 : 0;

      // Heatmap intensity
      const heatmapIntensity = showHeatmap ? cumulativePercent : 0;

      return (
        <motion.div
          key={`${side}-${level.price}`}
          initial={isFlashing ? { backgroundColor: isBid ? 'rgba(34,197,94,0.3)' : 'rgba(239,68,68,0.3)' } : {}}
          animate={isFlashing ? { backgroundColor: 'rgba(0,0,0,0)' } : {}}
          transition={{ duration: 0.3 }}
          className={cn(
            'group relative flex cursor-pointer items-center gap-2 rounded px-3 py-1.5 text-sm transition-colors',
            bgColor,
            isFlashing && 'animate-pulse'
          )}
          onClick={() => onLevelClick?.(level, side)}
          onDoubleClick={() => {
            if (onPlaceOrder) {
              const orderSide = isBid ? 'buy' : 'sell';
              onPlaceOrder(orderSide, level.price, level.quantity);
            }
          }}
        >
          {/* Barre de profondeur */}
          <div
            className={cn(
              'absolute inset-y-0 rounded transition-all duration-300',
              isBid ? 'right-0' : 'left-0',
              isBid ? 'bg-green-100/50 dark:bg-green-900/20' : 'bg-red-100/50 dark:bg-red-900/20'
            )}
            style={{
              width: `${percentage}%`,
              [isBid ? 'right' : 'left']: 0,
            }}
          />

          {/* Heatmap */}
          {showHeatmap && (
            <div
              className={cn(
                'absolute inset-y-0 transition-all duration-300 opacity-20',
                isBid ? 'right-0' : 'left-0',
                isBid ? 'bg-green-500' : 'bg-red-500'
              )}
              style={{
                width: `${heatmapIntensity}%`,
                [isBid ? 'right' : 'left']: 0,
              }}
            />
          )}

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
        </motion.div>
      );
    }, [
      bidColor,
      askColor,
      showCumulative,
      showPercentages,
      showHeatmap,
      flashingLevels,
      formatPriceFn,
      formatQuantityFn,
      onLevelClick,
      onPlaceOrder,
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
      const maxCumulative = Math.max(
        ...asks.map((l) => l.cumulative || 0),
        ...bids.map((l) => l.cumulative || 0),
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
          {(selectedSide === 'both' || selectedSide === 'asks') && asks.length > 0 && (
            <div className="border-b border-gray-200 dark:border-gray-700">
              <div className="flex items-center justify-between px-3 py-1 bg-gray-50 dark:bg-gray-800/50">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                  Ventes ({asks.length})
                </span>
                <span className="text-xs text-gray-400">
                  Total: {formatQuantityFn(asks.reduce((sum, l) => sum + l.quantity, 0))}
                </span>
              </div>
              {asks.map((level, index) => renderLevel(level, 'ask', index, maxQuantity, maxCumulative))}
            </div>
          )}

          {/* Spread / Prix courant */}
          <div className="py-2 px-3 bg-gray-50 dark:bg-gray-800/50 text-center border-b border-gray-200 dark:border-gray-700">
            <div className="flex items-center justify-center gap-4">
              <span className="text-xs text-gray-500 dark:text-gray-400">
                Spread: {formatPriceFn(stats?.spread || 0)}
              </span>
              {stats?.lastPrice && (
                <span className={cn(
                  'font-mono font-semibold',
                  stats.change >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
                )}>
                  {formatPriceFn(stats.lastPrice)}
                  <span className="ml-1 text-xs">
                    {stats.change >= 0 ? '+' : ''}{stats.changePercent?.toFixed(2)}%
                  </span>
                </span>
              )}
            </div>
          </div>

          {/* Demandes (Achats) */}
          {(selectedSide === 'both' || selectedSide === 'bids') && bids.length > 0 && (
            <div>
              <div className="flex items-center justify-between px-3 py-1 bg-gray-50 dark:bg-gray-800/50">
                <span className="text-xs font-medium text-gray-500 dark:text-gray-400">
                  Achats ({bids.length})
                </span>
                <span className="text-xs text-gray-400">
                  Total: {formatQuantityFn(bids.reduce((sum, l) => sum + l.quantity, 0))}
                </span>
              </div>
              {bids.map((level, index) => renderLevel(level, 'bid', index, maxQuantity, maxCumulative))}
            </div>
          )}
        </div>
      );
    }, [
      displayData,
      showCumulative,
      showPercentages,
      selectedSide,
      stats,
      renderLevel,
      formatPriceFn,
      formatQuantityFn,
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
              {formatQuantityFn(stats.volume || 0)}
            </div>
          </div>
          <div className="rounded-lg bg-gray-50 dark:bg-gray-800/50 p-3 text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">Imbalance</div>
            <div className="mt-1 font-mono text-lg font-semibold">
              {(stats.imbalance * 100).toFixed(1)}%
            </div>
          </div>
        </div>
      );
    }, [showSummary, stats, formatPriceFn, formatQuantityFn]);

    // --- Rendu des contrôles ---
    const renderControls = useCallback(() => {
      if (!showControls) return null;

      const groupOptions = [
        { value: 'none', label: 'Aucun' },
        { value: 'auto', label: 'Auto' },
        { value: '0.001', label: '0.001' },
        { value: '0.01', label: '0.01' },
        { value: '0.1', label: '0.1' },
        { value: '1', label: '1' },
        { value: '10', label: '10' },
      ];

      const viewOptions = [
        { value: 'both', label: 'Les deux' },
        { value: 'asks', label: 'Ventes' },
        { value: 'bids', label: 'Achats' },
      ];

      return (
        <div className="flex flex-wrap items-center gap-2 p-4 border-b border-gray-200 dark:border-gray-700">
          <Select
            options={viewOptions}
            value={selectedSide}
            onChange={(value) => setSelectedSide(value as OrderBookSide)}
            size="sm"
            className="w-28"
          />

          <Select
            options={groupOptions}
            value={typeof grouping === 'number' ? String(grouping) : grouping}
            onChange={(value) => {
              if (value === 'none') setGroupValue(0);
              else if (value === 'auto') setGroupValue(0);
              else setGroupValue(parseFloat(value));
            }}
            size="sm"
            className="w-24"
          />

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
            onClick={() => setView(view === 'depth' ? 'levels' : 'depth')}
          >
            {view === 'depth' ? (
              <DocumentTextIcon className="h-4 w-4" />
            ) : (
              <AdjustmentsHorizontalIcon className="h-4 w-4" />
            )}
          </Button>

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
    }, [
      showControls,
      selectedSide,
      grouping,
      showAll,
      view,
      isRefreshing,
      handleRefresh,
      ws.isConnected,
    ]);

    // --- Rendu du graphique de profondeur ---
    const renderDepthChart = useCallback(() => {
      if (view !== 'depth' || !displayData) return null;

      const { asks, bids } = displayData;
      const allPrices = [...bids.map((l) => l.price), ...asks.map((l) => l.price)];
      const allCumulative = [...bids.map((l) => l.cumulative || 0), ...asks.map((l) => l.cumulative || 0)];
      const maxCumulative = Math.max(...allCumulative, 1);
      const minPrice = Math.min(...allPrices);
      const maxPrice = Math.max(...allPrices);
      const range = maxPrice - minPrice || 1;

      // Points pour le graphique
      const bidPoints = bids.map((l) => ({
        x: ((l.price - minPrice) / range) * 100,
        y: ((l.cumulative || 0) / maxCumulative) * 100,
        price: l.price,
        quantity: l.cumulative || 0,
      }));

      const askPoints = asks.map((l) => ({
        x: ((l.price - minPrice) / range) * 100,
        y: ((l.cumulative || 0) / maxCumulative) * 100,
        price: l.price,
        quantity: l.cumulative || 0,
      }));

      return (
        <div className="p-4 border-t border-gray-200 dark:border-gray-700">
          <div className="relative h-40 rounded-lg overflow-hidden bg-gray-50 dark:bg-gray-800/50">
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
              {formatQuantityFn(maxCumulative)}
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
    }, [view, displayData, stats, formatPriceFn, formatQuantityFn]);

    // --- Rendu des squelettes ---
    const renderSkeletons = useCallback(() => {
      return (
        <div className="p-4 space-y-2">
          {Array.from({ length: 10 }).map((_, i) => (
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
              onClick={() => setView(view === 'both' ? 'depth' : view === 'depth' ? 'levels' : 'both')}
            >
              {view === 'both' ? '📊' : view === 'depth' ? '📋' : '📈'}
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
            {view === 'depth' ? renderDepthChart() : null}
            {view === 'levels' ? renderOrderBook() : null}
            {view === 'both' ? (
              <>
                {renderDepthChart()}
                <Separator />
                <ScrollArea className="max-h-[400px]">
                  {renderOrderBook()}
                </ScrollArea>
              </>
            ) : null}
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
              {displayData 
                ? `${displayData.bids.length} achats • ${displayData.asks.length} ventes` 
                : 'En attente de données'}
            </span>
            <span className="flex items-center gap-2">
              {data?.sequence && (
                <span>Seq: {data.sequence}</span>
              )}
              {data?.timestamp && (
                <span>{new Date(data.timestamp).toLocaleTimeString()}</span>
              )}
            </span>
          </div>
        </CardFooter>
      </Card>
    );
  }
);

OrderBook.displayName = 'OrderBook';

// ============================================================================
// EXPORTS
// ============================================================================

export default OrderBook;

// apps/web/src/components/dashboard/RecentTrades.tsx
'use client';

import React, {
  useState,
  useEffect,
  useCallback,
  useMemo,
  forwardRef,
  Ref,
  useRef,
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
  MagnifyingGlassIcon,
  FunnelIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ArrowsUpDownIcon,
  ArrowPathIcon,
  DocumentArrowDownIcon,
  DocumentDuplicateIcon,
  EyeIcon,
  EyeSlashIcon,
  CheckIcon,
  XMarkIcon,
  EllipsisHorizontalIcon,
  ShareIcon,
  LinkIcon,
  BookmarkIcon,
  HeartIcon,
  StarIcon,
  FlagIcon,
  PrinterIcon,
  EnvelopeIcon,
} from '@heroicons/react/24/outline';
import {
  ArrowUpIcon as ArrowUpSolid,
  ArrowDownIcon as ArrowDownSolid,
  CheckCircleIcon as CheckCircleSolid,
  XCircleIcon as XCircleSolid,
  ExclamationTriangleIcon as ExclamationTriangleSolid,
} from '@heroicons/react/24/solid';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Select } from '@/components/common/Select';
import { Table, TableHeader, TableBody, TableRow, TableCell, TableHead } from '@/components/common/Table';
import { ScrollArea } from '@/components/common/ScrollArea';
import { Separator } from '@/components/common/Separator';
import { Skeleton } from '@/components/common/Skeleton';
import { Tooltip } from '@/components/common/Tooltip';
import { Popover } from '@/components/common/Popover';
import { DropdownMenu } from '@/components/common/DropdownMenu';
import { Pagination } from '@/components/common/Pagination';
import { Progress } from '@/components/common/Progress';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type TradeType = 'BUY' | 'SELL' | 'LONG' | 'SHORT' | 'CLOSE';
export type TradeStatus = 'OPEN' | 'CLOSED' | 'PENDING' | 'CANCELLED' | 'REJECTED' | 'PARTIAL';
export type TradeOrderType = 'MARKET' | 'LIMIT' | 'STOP' | 'STOP_LIMIT' | 'TRAILING_STOP';
export type TradeTimeFrame = '1m' | '5m' | '15m' | '30m' | '1h' | '4h' | '1d' | '1w' | '1M';

export interface Trade {
  /** Identifiant unique du trade */
  id: string;
  /** Symbole de l'actif (ex: BTC/USD) */
  symbol: string;
  /** Type de trade */
  type: TradeType;
  /** Statut du trade */
  status: TradeStatus;
  /** Prix d'entrée */
  entryPrice: number;
  /** Prix de sortie */
  exitPrice?: number;
  /** Quantité */
  quantity: number;
  /** Valeur totale */
  value: number;
  /** P/L en pourcentage */
  pnl: number;
  /** P/L en valeur absolue */
  pnlValue: number;
  /** Date d'entrée */
  entryDate: Date;
  /** Date de sortie */
  exitDate?: Date;
  /** Type d'ordre */
  orderType: TradeOrderType;
  /** Take Profit */
  takeProfit?: number;
  /** Stop Loss */
  stopLoss?: number;
  /** Frais */
  fees?: number;
  /** Notes */
  notes?: string;
  /** Tags */
  tags?: string[];
  /** Stratégie utilisée */
  strategy?: string;
  /** Signal ID */
  signalId?: string;
  /** Plateforme d'exécution */
  exchange?: string;
  /** Devise de la paire */
  currency?: string;
  /** Volume */
  volume?: number;
  /** Liquidité */
  liquidity?: number;
  /** Slippage */
  slippage?: number;
  /** Spread */
  spread?: number;
  /** Temps d'exécution (ms) */
  executionTime?: number;
  /** Erreur éventuelle */
  error?: string;
  /** Données personnalisées */
  metadata?: Record<string, any>;
}

export interface TradeFilter {
  /** Symbole */
  symbol?: string;
  /** Type */
  types?: TradeType[];
  /** Statut */
  statuses?: TradeStatus[];
  /** Plage de P/L */
  pnlRange?: { min: number; max: number };
  /** Date de début */
  startDate?: Date;
  /** Date de fin */
  endDate?: Date;
  /** Recherche textuelle */
  search?: string;
  /** Trier par */
  sortBy?: keyof Trade;
  /** Ordre de tri */
  sortOrder?: 'asc' | 'desc';
  /** Limite */
  limit?: number;
  /** Offset */
  offset?: number;
}

export interface RecentTradesProps {
  // --- Données ---
  /** Liste des trades */
  trades?: Trade[];
  /** Chargement en cours */
  isLoading?: boolean;
  /** Erreur */
  error?: string | null;

  // --- Filtres ---
  /** Filtres par défaut */
  defaultFilters?: TradeFilter;
  /** Callback lors du changement de filtres */
  onFilterChange?: (filters: TradeFilter) => void;

  // --- Apparence ---
  /** Titre de la carte */
  title?: string;
  /** Sous-titre */
  subtitle?: string;
  /** Classes additionnelles */
  className?: string;
  /** Nombre d'éléments à afficher par défaut */
  defaultLimit?: number;
  /** Afficher le header */
  showHeader?: boolean;
  /** Afficher les filtres */
  showFilters?: boolean;
  /** Afficher les actions */
  showActions?: boolean;
  /** Afficher la pagination */
  showPagination?: boolean;
  /** Afficher les statuts en couleur */
  showStatusColors?: boolean;
  /** Afficher les badges de type */
  showTypeBadges?: boolean;

  // --- Actions ---
  /** Callback lors du clic sur un trade */
  onTradeClick?: (trade: Trade) => void;
  /** Callback pour exporter */
  onExport?: (trades: Trade[]) => void;
  /** Callback pour rafraîchir */
  onRefresh?: () => void;
  /** Callback pour voir tous les trades */
  onViewAll?: () => void;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ID */
  id?: string;

  // --- Avancé ---
  /** Nombre maximum de trades */
  maxTrades?: number;
  /** Intervalle de rafraîchissement (ms) */
  refreshInterval?: number;
  /** Désactiver le rafraîchissement automatique */
  disableAutoRefresh?: boolean;
  /** Format de date */
  dateFormat?: string;
  /** Format des nombres */
  numberFormat?: Intl.NumberFormatOptions;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const STATUS_CONFIG: Record<TradeStatus, { label: string; color: string; icon: React.ReactNode }> = {
  OPEN: {
    label: 'Ouvert',
    color: 'bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400',
    icon: <CheckCircleIcon className="h-3.5 w-3.5" />,
  },
  CLOSED: {
    label: 'Fermé',
    color: 'bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-400',
    icon: <InformationCircleIcon className="h-3.5 w-3.5" />,
  },
  PENDING: {
    label: 'En attente',
    color: 'bg-yellow-100 text-yellow-700 dark:bg-yellow-900/30 dark:text-yellow-400',
    icon: <ClockIcon className="h-3.5 w-3.5" />,
  },
  CANCELLED: {
    label: 'Annulé',
    color: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    icon: <XCircleIcon className="h-3.5 w-3.5" />,
  },
  REJECTED: {
    label: 'Rejeté',
    color: 'bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400',
    icon: <ExclamationTriangleIcon className="h-3.5 w-3.5" />,
  },
  PARTIAL: {
    label: 'Partiel',
    color: 'bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400',
    icon: <InformationCircleIcon className="h-3.5 w-3.5" />,
  },
};

const TYPE_CONFIG: Record<TradeType, { label: string; color: string; bg: string }> = {
  BUY: {
    label: 'Achat',
    color: 'text-green-600 dark:text-green-400',
    bg: 'bg-green-100 dark:bg-green-900/30',
  },
  SELL: {
    label: 'Vente',
    color: 'text-red-600 dark:text-red-400',
    bg: 'bg-red-100 dark:bg-red-900/30',
  },
  LONG: {
    label: 'Long',
    color: 'text-green-600 dark:text-green-400',
    bg: 'bg-green-100 dark:bg-green-900/30',
  },
  SHORT: {
    label: 'Short',
    color: 'text-red-600 dark:text-red-400',
    bg: 'bg-red-100 dark:bg-red-900/30',
  },
  CLOSE: {
    label: 'Fermeture',
    color: 'text-gray-600 dark:text-gray-400',
    bg: 'bg-gray-100 dark:bg-gray-800',
  },
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const RecentTrades = forwardRef<HTMLDivElement, RecentTradesProps>(
  (props, ref) => {
    const {
      // Données
      trades: externalTrades = [],
      isLoading: externalLoading = false,
      error: externalError = null,

      // Filtres
      defaultFilters,
      onFilterChange,

      // Apparence
      title = 'Trades Récents',
      subtitle = 'Activité de trading en temps réel',
      className,
      defaultLimit = 10,
      showHeader = true,
      showFilters = true,
      showActions = true,
      showPagination = true,
      showStatusColors = true,
      showTypeBadges = true,

      // Actions
      onTradeClick,
      onExport,
      onRefresh,
      onViewAll,

      // Accessibilité
      ariaLabel = 'Trades récents',
      id,

      // Avancé
      maxTrades = 100,
      refreshInterval = 30000,
      disableAutoRefresh = false,
      dateFormat = 'dd/MM/yyyy HH:mm',
      numberFormat = { minimumFractionDigits: 2, maximumFractionDigits: 2 },
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const containerRef = useRef<HTMLDivElement>(null);
    const refreshTimerRef = useRef<NodeJS.Timeout | null>(null);

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [trades, setTrades] = useState<Trade[]>(externalTrades);
    const [filteredTrades, setFilteredTrades] = useState<Trade[]>([]);
    const [isLoading, setIsLoading] = useState(externalLoading);
    const [error, setError] = useState<string | null>(externalError);

    const [filters, setFilters] = useState<TradeFilter>({
      limit: defaultLimit,
      offset: 0,
      sortBy: 'entryDate',
      sortOrder: 'desc',
      ...defaultFilters,
    });

    const [selectedTrades, setSelectedTrades] = useState<string[]>([]);
    const [isRefreshing, setIsRefreshing] = useState(false);
    const [view, setView] = useState<'table' | 'cards'>('table');

    // ========================================================================
    // SYNC AVEC LES PROPS EXTERNES
    // ========================================================================

    useEffect(() => {
      setTrades(externalTrades);
    }, [externalTrades]);

    useEffect(() => {
      setIsLoading(externalLoading);
    }, [externalLoading]);

    useEffect(() => {
      setError(externalError);
    }, [externalError]);

    // ========================================================================
    // FILTRAGE ET TRI
    // ========================================================================

    const applyFilters = useCallback(() => {
      let result = [...trades];

      // Filtre par recherche textuelle
      if (filters.search) {
        const searchLower = filters.search.toLowerCase();
        result = result.filter(
          (trade) =>
            trade.symbol.toLowerCase().includes(searchLower) ||
            trade.id.toLowerCase().includes(searchLower) ||
            trade.strategy?.toLowerCase().includes(searchLower) ||
            trade.notes?.toLowerCase().includes(searchLower)
        );
      }

      // Filtre par symbole
      if (filters.symbol) {
        result = result.filter((trade) =>
          trade.symbol.toLowerCase().includes(filters.symbol!.toLowerCase())
        );
      }

      // Filtre par type
      if (filters.types && filters.types.length > 0) {
        result = result.filter((trade) =>
          filters.types!.includes(trade.type)
        );
      }

      // Filtre par statut
      if (filters.statuses && filters.statuses.length > 0) {
        result = result.filter((trade) =>
          filters.statuses!.includes(trade.status)
        );
      }

      // Filtre par P/L
      if (filters.pnlRange) {
        result = result.filter(
          (trade) =>
            trade.pnl >= filters.pnlRange!.min &&
            trade.pnl <= filters.pnlRange!.max
        );
      }

      // Filtre par date
      if (filters.startDate) {
        result = result.filter(
          (trade) => new Date(trade.entryDate) >= filters.startDate!
        );
      }
      if (filters.endDate) {
        result = result.filter(
          (trade) => new Date(trade.entryDate) <= filters.endDate!
        );
      }

      // Tri
      if (filters.sortBy) {
        const sortKey = filters.sortBy;
        const sortOrder = filters.sortOrder === 'desc' ? -1 : 1;

        result.sort((a, b) => {
          const aVal = a[sortKey];
          const bVal = b[sortKey];

          if (aVal === undefined && bVal === undefined) return 0;
          if (aVal === undefined) return 1;
          if (bVal === undefined) return -1;

          if (typeof aVal === 'number' && typeof bVal === 'number') {
            return (aVal - bVal) * sortOrder;
          }

          if (aVal instanceof Date && bVal instanceof Date) {
            return (aVal.getTime() - bVal.getTime()) * sortOrder;
          }

          return String(aVal).localeCompare(String(bVal)) * sortOrder;
        });
      }

      // Limite et offset
      const start = filters.offset || 0;
      const end = filters.limit ? start + filters.limit : result.length;
      result = result.slice(start, end);

      // Limiter le nombre total
      if (result.length > maxTrades) {
        result = result.slice(0, maxTrades);
      }

      setFilteredTrades(result);
    }, [trades, filters, maxTrades]);

    useEffect(() => {
      applyFilters();
    }, [applyFilters]);

    // ========================================================================
    // CHANGEMENT DE FILTRES
    // ========================================================================

    const handleFilterChange = useCallback((newFilters: Partial<TradeFilter>) => {
      setFilters((prev) => {
        const updated = { ...prev, ...newFilters };
        if (onFilterChange) {
          onFilterChange(updated);
        }
        return updated;
      });
    }, [onFilterChange]);

    const handlePageChange = useCallback((page: number) => {
      const newOffset = (page - 1) * (filters.limit || defaultLimit);
      handleFilterChange({ offset: newOffset });
    }, [filters.limit, defaultLimit, handleFilterChange]);

    const handlePageSizeChange = useCallback((size: number) => {
      handleFilterChange({ limit: size, offset: 0 });
    }, [handleFilterChange]);

    // ========================================================================
    // SÉLECTION
    // ========================================================================

    const toggleSelectAll = useCallback(() => {
      if (selectedTrades.length === filteredTrades.length) {
        setSelectedTrades([]);
      } else {
        setSelectedTrades(filteredTrades.map((t) => t.id));
      }
    }, [selectedTrades, filteredTrades]);

    const toggleSelectTrade = useCallback((tradeId: string) => {
      setSelectedTrades((prev) =>
        prev.includes(tradeId)
          ? prev.filter((id) => id !== tradeId)
          : [...prev, tradeId]
      );
    }, []);

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
    // EXPORT
    // ========================================================================

    const handleExport = useCallback(() => {
      const dataToExport = selectedTrades.length > 0
        ? trades.filter((t) => selectedTrades.includes(t.id))
        : filteredTrades;

      if (onExport) {
        onExport(dataToExport);
      } else {
        // Export par défaut en CSV
        const headers = ['ID', 'Symbole', 'Type', 'Statut', 'Prix Entrée', 'Prix Sortie', 'Quantité', 'P&L', 'Date'];
        const csvData = dataToExport.map((trade) => [
          trade.id,
          trade.symbol,
          trade.type,
          trade.status,
          trade.entryPrice,
          trade.exitPrice || '',
          trade.quantity,
          trade.pnl,
          trade.entryDate.toISOString(),
        ]);

        const csv = [headers.join(','), ...csvData.map((row) => row.join(','))].join('\n');
        const blob = new Blob([csv], { type: 'text/csv' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `trades_${new Date().toISOString()}.csv`;
        a.click();
        URL.revokeObjectURL(url);
      }
    }, [trades, filteredTrades, selectedTrades, onExport]);

    // ========================================================================
    // AUTO-REFRESH
    // ========================================================================

    useEffect(() => {
      if (disableAutoRefresh) return;

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
    }, [refreshInterval, disableAutoRefresh, handleRefresh]);

    // ========================================================================
    // FORMATAGE
    // ========================================================================

    const formatNumber = useCallback((value: number): string => {
      return new Intl.NumberFormat('fr-FR', numberFormat).format(value);
    }, [numberFormat]);

    const formatDate = useCallback((date: Date): string => {
      return new Intl.DateTimeFormat('fr-FR', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      }).format(date);
    }, []);

    const formatCurrency = useCallback((value: number): string => {
      return new Intl.NumberFormat('fr-FR', {
        ...numberFormat,
        style: 'currency',
        currency: 'USD',
      }).format(value);
    }, [numberFormat]);

    // ========================================================================
    // RENDU
    // ========================================================================

    // --- Rendu du statut ---
    const renderStatus = useCallback((status: TradeStatus) => {
      const config = STATUS_CONFIG[status] || STATUS_CONFIG.OPEN;

      return (
        <Badge
          variant="outline"
          className={cn(
            'flex items-center gap-1.5 border-0 font-medium',
            config.color,
            showStatusColors && 'border'
          )}
        >
          {config.icon}
          {config.label}
        </Badge>
      );
    }, [showStatusColors]);

    // --- Rendu du type ---
    const renderType = useCallback((type: TradeType) => {
      const config = TYPE_CONFIG[type] || TYPE_CONFIG.BUY;

      if (!showTypeBadges) {
        return <span className={config.color}>{config.label}</span>;
      }

      return (
        <Badge variant="outline" className={cn('border-0 font-medium', config.bg, config.color)}>
          {config.label}
        </Badge>
      );
    }, [showTypeBadges]);

    // --- Rendu du P&L ---
    const renderPnL = useCallback((pnl: number, pnlValue: number) => {
      const isPositive = pnl >= 0;
      const Icon = isPositive ? ArrowUpIcon : ArrowDownIcon;

      return (
        <div className={cn(
          'flex items-center gap-1 font-semibold',
          isPositive ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
        )}>
          <Icon className="h-3.5 w-3.5" />
          <span>{formatNumber(pnl)}%</span>
          <span className="text-xs opacity-70">({formatCurrency(pnlValue)})</span>
        </div>
      );
    }, [formatNumber, formatCurrency]);

    // --- Rendu des squelettes ---
    const renderSkeletons = useCallback(() => {
      return Array.from({ length: 5 }).map((_, i) => (
        <TableRow key={i}>
          <TableCell><Skeleton className="h-4 w-20" /></TableCell>
          <TableCell><Skeleton className="h-4 w-16" /></TableCell>
          <TableCell><Skeleton className="h-4 w-24" /></TableCell>
          <TableCell><Skeleton className="h-4 w-20" /></TableCell>
          <TableCell><Skeleton className="h-4 w-16" /></TableCell>
          <TableCell><Skeleton className="h-4 w-16" /></TableCell>
          <TableCell><Skeleton className="h-4 w-16" /></TableCell>
        </TableRow>
      ));
    }, []);

    // --- Rendu du tableau ---
    const renderTable = useCallback(() => {
      if (isLoading) return renderSkeletons();

      if (filteredTrades.length === 0) {
        return (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <InformationCircleIcon className="h-12 w-12 text-gray-300 dark:text-gray-600" />
            <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
              Aucun trade trouvé
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              Essayez de modifier vos filtres
            </p>
          </div>
        );
      }

      return (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">
                <input
                  type="checkbox"
                  checked={selectedTrades.length === filteredTrades.length && filteredTrades.length > 0}
                  onChange={toggleSelectAll}
                  className="rounded border-gray-300 dark:border-gray-600"
                />
              </TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Symbole</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Statut</TableHead>
              <TableHead className="text-right">Prix</TableHead>
              <TableHead className="text-right">Quantité</TableHead>
              <TableHead className="text-right">P&L</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {filteredTrades.map((trade) => (
              <TableRow
                key={trade.id}
                className={cn(
                  'cursor-pointer transition-colors hover:bg-gray-50 dark:hover:bg-gray-800/50',
                  selectedTrades.includes(trade.id) && 'bg-brand-50 dark:bg-brand-900/20'
                )}
                onClick={() => onTradeClick?.(trade)}
              >
                <TableCell onClick={(e) => e.stopPropagation()}>
                  <input
                    type="checkbox"
                    checked={selectedTrades.includes(trade.id)}
                    onChange={() => toggleSelectTrade(trade.id)}
                    className="rounded border-gray-300 dark:border-gray-600"
                  />
                </TableCell>
                <TableCell className="text-sm">
                  {formatDate(trade.entryDate)}
                </TableCell>
                <TableCell>
                  <span className="font-medium">{trade.symbol}</span>
                </TableCell>
                <TableCell>{renderType(trade.type)}</TableCell>
                <TableCell>{renderStatus(trade.status)}</TableCell>
                <TableCell className="text-right font-mono text-sm">
                  {formatNumber(trade.entryPrice)}
                </TableCell>
                <TableCell className="text-right font-mono text-sm">
                  {formatNumber(trade.quantity)}
                </TableCell>
                <TableCell className="text-right">
                  {renderPnL(trade.pnl, trade.pnlValue)}
                </TableCell>
                <TableCell className="text-right" onClick={(e) => e.stopPropagation()}>
                  <DropdownMenu
                    trigger={<Button variant="ghost" size="sm"><EllipsisHorizontalIcon className="h-4 w-4" /></Button>}
                    items={[
                      { label: 'Voir détails', onClick: () => onTradeClick?.(trade) },
                      { label: 'Dupliquer', onClick: () => {} },
                      { label: 'Exporter', onClick: () => {} },
                      { type: 'separator' },
                      { label: 'Annuler', onClick: () => {}, variant: 'danger' },
                    ]}
                  />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      );
    }, [
      isLoading,
      filteredTrades,
      selectedTrades,
      formatDate,
      renderType,
      renderStatus,
      formatNumber,
      renderPnL,
      onTradeClick,
      toggleSelectAll,
      toggleSelectTrade,
      renderSkeletons,
    ]);

    // --- Rendu des cartes (mobile) ---
    const renderCards = useCallback(() => {
      if (isLoading) {
        return (
          <div className="grid gap-4 sm:grid-cols-2">
            {Array.from({ length: 4 }).map((_, i) => (
              <Skeleton key={i} className="h-48 w-full" />
            ))}
          </div>
        );
      }

      if (filteredTrades.length === 0) {
        return (
          <div className="flex flex-col items-center justify-center py-12 text-center">
            <InformationCircleIcon className="h-12 w-12 text-gray-300 dark:text-gray-600" />
            <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
              Aucun trade trouvé
            </p>
          </div>
        );
      }

      return (
        <div className="grid gap-4 sm:grid-cols-2">
          {filteredTrades.map((trade) => (
            <Card
              key={trade.id}
              className={cn(
                'cursor-pointer transition-all hover:shadow-md',
                selectedTrades.includes(trade.id) && 'ring-2 ring-brand-500'
              )}
              onClick={() => onTradeClick?.(trade)}
            >
              <CardContent className="p-4">
                <div className="flex items-start justify-between">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold">{trade.symbol}</span>
                      {renderType(trade.type)}
                      {renderStatus(trade.status)}
                    </div>
                    <div className="mt-1 text-sm text-gray-500 dark:text-gray-400">
                      {formatDate(trade.entryDate)}
                    </div>
                  </div>
                  <input
                    type="checkbox"
                    checked={selectedTrades.includes(trade.id)}
                    onChange={() => toggleSelectTrade(trade.id)}
                    className="rounded border-gray-300 dark:border-gray-600"
                    onClick={(e) => e.stopPropagation()}
                  />
                </div>

                <Separator className="my-3" />

                <div className="grid grid-cols-2 gap-2 text-sm">
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Prix entrée</span>
                    <div className="font-mono font-medium">{formatNumber(trade.entryPrice)}</div>
                  </div>
                  <div>
                    <span className="text-gray-500 dark:text-gray-400">Quantité</span>
                    <div className="font-mono font-medium">{formatNumber(trade.quantity)}</div>
                  </div>
                  <div className="col-span-2">
                    <span className="text-gray-500 dark:text-gray-400">P&L</span>
                    <div>{renderPnL(trade.pnl, trade.pnlValue)}</div>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      );
    }, [
      isLoading,
      filteredTrades,
      selectedTrades,
      formatDate,
      renderType,
      renderStatus,
      formatNumber,
      renderPnL,
      onTradeClick,
      toggleSelectTrade,
    ]);

    // --- Rendu des filtres ---
    const renderFilters = () => {
      if (!showFilters) return null;

      const symbolOptions = Array.from(new Set(trades.map((t) => t.symbol))).map((symbol) => ({
        value: symbol,
        label: symbol,
      }));

      const typeOptions: { value: TradeType; label: string }[] = [
        { value: 'BUY', label: 'Achat' },
        { value: 'SELL', label: 'Vente' },
        { value: 'LONG', label: 'Long' },
        { value: 'SHORT', label: 'Short' },
        { value: 'CLOSE', label: 'Fermeture' },
      ];

      const statusOptions: { value: TradeStatus; label: string }[] = [
        { value: 'OPEN', label: 'Ouvert' },
        { value: 'CLOSED', label: 'Fermé' },
        { value: 'PENDING', label: 'En attente' },
        { value: 'CANCELLED', label: 'Annulé' },
        { value: 'REJECTED', label: 'Rejeté' },
        { value: 'PARTIAL', label: 'Partiel' },
      ];

      return (
        <div className="flex flex-wrap items-center gap-2 p-4 border-b border-gray-200 dark:border-gray-700">
          <div className="flex-1 min-w-[200px]">
            <Input
              type="text"
              placeholder="Rechercher..."
              value={filters.search || ''}
              onChange={(e) => handleFilterChange({ search: e.target.value })}
              className="h-9"
              prefix={<MagnifyingGlassIcon className="h-4 w-4 text-gray-400" />}
            />
          </div>

          <Select
            options={[
              { value: '', label: 'Tous les symboles' },
              ...symbolOptions,
            ]}
            value={filters.symbol || ''}
            onChange={(value) => handleFilterChange({ symbol: value || undefined })}
            size="sm"
            className="w-32"
            placeholder="Symbole"
          />

          <Select
            options={[
              { value: '', label: 'Tous les types' },
              ...typeOptions,
            ]}
            value={filters.types?.[0] || ''}
            onChange={(value) => handleFilterChange({ types: value ? [value as TradeType] : [] })}
            size="sm"
            className="w-32"
            placeholder="Type"
          />

          <Select
            options={[
              { value: '', label: 'Tous les statuts' },
              ...statusOptions,
            ]}
            value={filters.statuses?.[0] || ''}
            onChange={(value) => handleFilterChange({ statuses: value ? [value as TradeStatus] : [] })}
            size="sm"
            className="w-32"
            placeholder="Statut"
          />

          <Button
            variant="ghost"
            size="sm"
            onClick={() => handleFilterChange({
              search: '',
              symbol: undefined,
              types: [],
              statuses: [],
              pnlRange: undefined,
              startDate: undefined,
              endDate: undefined,
            })}
          >
            Réinitialiser
          </Button>
        </div>
      );
    };

    // --- Rendu des actions ---
    const renderActions = () => {
      if (!showActions) return null;

      return (
        <div className="flex items-center gap-2 p-4 border-t border-gray-200 dark:border-gray-700">
          <div className="flex-1 text-sm text-gray-500 dark:text-gray-400">
            {selectedTrades.length > 0
              ? `${selectedTrades.length} trade${selectedTrades.length > 1 ? 's' : ''} sélectionné${selectedTrades.length > 1 ? 's' : ''}`
              : `${filteredTrades.length} trade${filteredTrades.length > 1 ? 's' : ''} affiché${filteredTrades.length > 1 ? 's' : ''}`
            }
          </div>

          <div className="flex items-center gap-1">
            <Tooltip content="Rafraîchir">
              <Button
                variant="ghost"
                size="sm"
                onClick={handleRefresh}
                disabled={isRefreshing}
              >
                <ArrowPathIcon className={cn('h-4 w-4', isRefreshing && 'animate-spin')} />
              </Button>
            </Tooltip>

            <Tooltip content="Exporter">
              <Button variant="ghost" size="sm" onClick={handleExport}>
                <DocumentArrowDownIcon className="h-4 w-4" />
              </Button>
            </Tooltip>

            <Tooltip content={view === 'table' ? 'Vue cartes' : 'Vue tableau'}>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setView((v) => v === 'table' ? 'cards' : 'table')}
              >
                {view === 'table' ? (
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <rect x="3" y="3" width="7" height="7" rx="1" strokeWidth="2" />
                    <rect x="14" y="3" width="7" height="7" rx="1" strokeWidth="2" />
                    <rect x="3" y="14" width="7" height="7" rx="1" strokeWidth="2" />
                    <rect x="14" y="14" width="7" height="7" rx="1" strokeWidth="2" />
                  </svg>
                ) : (
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <rect x="3" y="3" width="18" height="4" rx="1" strokeWidth="2" />
                    <rect x="3" y="10" width="18" height="4" rx="1" strokeWidth="2" />
                    <rect x="3" y="17" width="18" height="4" rx="1" strokeWidth="2" />
                  </svg>
                )}
              </Button>
            </Tooltip>

            {onViewAll && (
              <Button variant="ghost" size="sm" onClick={onViewAll}>
                Voir tout
              </Button>
            )}
          </div>
        </div>
      );
    };

    // --- Rendu de la pagination ---
    const renderPagination = () => {
      if (!showPagination) return null;

      const totalPages = Math.ceil(trades.length / (filters.limit || defaultLimit));

      if (totalPages <= 1) return null;

      return (
        <div className="p-4 border-t border-gray-200 dark:border-gray-700">
          <Pagination
            totalItems={trades.length}
            currentPage={(filters.offset || 0) / (filters.limit || defaultLimit) + 1}
            pageSize={filters.limit || defaultLimit}
            onPageChange={handlePageChange}
            onPageSizeChange={handlePageSizeChange}
            pageSizeOptions={[5, 10, 25, 50]}
            showInfo
            showPageSizeSelector
            size="sm"
          />
        </div>
      );
    };

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
        {showHeader && (
          <CardHeader className="flex flex-row items-center justify-between border-b border-gray-200 dark:border-gray-700">
            <div>
              <CardTitle>{title}</CardTitle>
              {subtitle && (
                <p className="text-sm text-gray-500 dark:text-gray-400">{subtitle}</p>
              )}
            </div>
            {!isLoading && (
              <div className="flex items-center gap-2">
                {!disableAutoRefresh && (
                  <span className="text-xs text-gray-400">
                    Live
                    <span className="inline-block ml-1 h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
                  </span>
                )}
              </div>
            )}
          </CardHeader>
        )}

        {/* Filtres */}
        {renderFilters()}

        {/* Contenu */}
        <div className="p-0">
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
          ) : (
            <ScrollArea className="max-h-[600px]">
              {view === 'table' ? renderTable() : renderCards()}
            </ScrollArea>
          )}
        </div>

        {/* Actions */}
        {renderActions()}

        {/* Pagination */}
        {renderPagination()}
      </Card>
    );
  }
);

RecentTrades.displayName = 'RecentTrades';

// ============================================================================
// EXPORTS
// ============================================================================

export default RecentTrades;

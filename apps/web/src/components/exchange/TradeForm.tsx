// apps/web/src/components/exchange/TradeForm.tsx
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
  CalculatorIcon,
  PercentIcon,
  CurrencyDollarIcon,
  WalletIcon,
  BanknotesIcon,
  CreditCardIcon,
  ChartBarIcon,
  ChartPieIcon,
  Cog6ToothIcon,
  AdjustmentsHorizontalIcon,
  DocumentTextIcon,
  ClipboardIcon,
  CheckIcon,
  XMarkIcon,
  ShieldCheckIcon,
  ExclamationCircleIcon,
} from '@heroicons/react/24/outline';
import {
  ArrowUpIcon as ArrowUpSolid,
  ArrowDownIcon as ArrowDownSolid,
} from '@heroicons/react/24/solid';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Select } from '@/components/common/Select';
import { Slider } from '@/components/common/Slider';
import { Switch } from '@/components/common/Switch';
import { Label } from '@/components/common/Label';
import { Separator } from '@/components/common/Separator';
import { Tooltip } from '@/components/common/Tooltip';
import { Progress } from '@/components/common/Progress';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/common/Tabs';
import { useToast } from '@/hooks/useToast';
import { useWallet } from '@/hooks/useWallet';
import { useMarketData } from '@/hooks/useMarketData';

// ============================================================================
// TYPES
// ============================================================================

export type OrderType = 'market' | 'limit' | 'stop' | 'stop_limit' | 'trailing_stop' | 'take_profit';
export type OrderSide = 'buy' | 'sell';
export type OrderTimeInForce = 'GTC' | 'IOC' | 'FOK' | 'DAY' | 'GTT';
export type OrderStatus = 'pending' | 'submitted' | 'filled' | 'partially_filled' | 'cancelled' | 'rejected';

export interface TradeFormData {
  /** Symbole */
  symbol: string;
  /** Type d'ordre */
  orderType: OrderType;
  /** Côté (achat/vente) */
  side: OrderSide;
  /** Quantité */
  quantity: number;
  /** Prix (pour limit/stop) */
  price?: number;
  /** Prix stop (pour stop/stop_limit) */
  stopPrice?: number;
  /** Take profit */
  takeProfit?: number;
  /** Stop loss */
  stopLoss?: number;
  /** Temps en vigueur */
  timeInForce?: OrderTimeInForce;
  /** Date d'expiration (pour GTT) */
  expireDate?: Date;
  /** Réduire uniquement */
  reduceOnly?: boolean;
  /** Ordre post-only */
  postOnly?: boolean;
  /** Marge utilisée */
  leverage?: number;
  /** Notes */
  notes?: string;
}

export interface TradeFormProps {
  // --- Contrôle ---
  /** Symbole par défaut */
  defaultSymbol?: string;
  /** Données initiales */
  initialData?: Partial<TradeFormData>;
  /** Callback lors de la soumission */
  onSubmit?: (data: TradeFormData) => void | Promise<void>;
  /** Callback lors de l'annulation */
  onCancel?: () => void;
  /** Callback lors du changement */
  onChange?: (data: TradeFormData) => void;

  // --- Données ---
  /** Prix courant */
  currentPrice?: number;
  /** Prix d'ouverture */
  openPrice?: number;
  /** Prix de clôture */
  closePrice?: number;
  /** Volume 24h */
  volume24h?: number;
  /** Balance disponible */
  availableBalance?: number;
  /** Devise */
  currency?: string;
  /** Leverage maximum */
  maxLeverage?: number;

  // --- Apparence ---
  /** Titre */
  title?: string;
  /** Classes additionnelles */
  className?: string;
  /** Afficher les détails avancés */
  showAdvanced?: boolean;
  /** Afficher les options de marge */
  showLeverage?: boolean;
  /** Afficher les stop-loss/take-profit */
  showSLTP?: boolean;
  /** Afficher les statistiques */
  showStats?: boolean;
  /** Variante */
  variant?: 'default' | 'compact' | 'minimal';

  // --- États ---
  /** Chargement en cours */
  isLoading?: boolean;
  /** Erreur */
  error?: string | null;
  /** Désactiver le formulaire */
  disabled?: boolean;

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
  /** Décimales pour le prix */
  priceDecimals?: number;
  /** Décimales pour la quantité */
  quantityDecimals?: number;
  /** Quantité minimale */
  minQuantity?: number;
  /** Quantité maximale */
  maxQuantity?: number;
  /** Pas de quantité */
  quantityStep?: number;
  /** Pas de prix */
  priceStep?: number;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const ORDER_TYPE_LABELS: Record<OrderType, string> = {
  market: 'Marché',
  limit: 'Limite',
  stop: 'Stop',
  stop_limit: 'Stop Limite',
  trailing_stop: 'Trailing Stop',
  take_profit: 'Take Profit',
};

const ORDER_TYPE_DESCRIPTIONS: Record<OrderType, string> = {
  market: 'Exécuté immédiatement au meilleur prix disponible',
  limit: 'Exécuté uniquement à un prix spécifique ou meilleur',
  stop: 'Déclenché lorsque le prix atteint le niveau stop',
  stop_limit: 'Ordre limite déclenché par un prix stop',
  trailing_stop: 'Stop qui suit le prix du marché',
  take_profit: 'Fermeture automatique à un niveau de profit',
};

const TIME_IN_FORCE_LABELS: Record<OrderTimeInForce, string> = {
  GTC: 'Good Till Canceled',
  IOC: 'Immediate or Cancel',
  FOK: 'Fill or Kill',
  DAY: 'Day',
  GTT: 'Good Till Time',
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const TradeForm = forwardRef<HTMLDivElement, TradeFormProps>(
  (props, ref) => {
    const {
      // Contrôle
      defaultSymbol = 'BTC/USD',
      initialData,
      onSubmit,
      onCancel,
      onChange,

      // Données
      currentPrice = 0,
      openPrice = 0,
      closePrice = 0,
      volume24h = 0,
      availableBalance = 0,
      currency = 'USD',
      maxLeverage = 10,

      // Apparence
      title = 'Passer un ordre',
      className,
      showAdvanced = false,
      showLeverage = true,
      showSLTP = true,
      showStats = true,
      variant = 'default',

      // États
      isLoading = false,
      error = null,
      disabled = false,

      // Accessibilité
      ariaLabel = 'Formulaire de trading',
      id,

      // Avancé
      formatPrice,
      formatQuantity,
      priceDecimals = 2,
      quantityDecimals = 4,
      minQuantity = 0.001,
      maxQuantity = 1000,
      quantityStep = 0.001,
      priceStep = 0.01,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const formRef = useRef<HTMLFormElement>(null);
    const submitButtonRef = useRef<HTMLButtonElement>(null);

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [formData, setFormData] = useState<TradeFormData>({
      symbol: defaultSymbol,
      orderType: 'market',
      side: 'buy',
      quantity: minQuantity,
      timeInForce: 'GTC',
      reduceOnly: false,
      postOnly: false,
      leverage: 1,
      ...initialData,
    });

    const [activeTab, setActiveTab] = useState<'buy' | 'sell'>('buy');
    const [showAdvancedSettings, setShowAdvancedSettings] = useState(showAdvanced);
    const [calculatedValue, setCalculatedValue] = useState(0);
    const [fee, setFee] = useState(0);
    const [totalCost, setTotalCost] = useState(0);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const isBuy = formData.side === 'buy';
    const isSell = formData.side === 'sell';
    const isMarket = formData.orderType === 'market';
    const isLimit = formData.orderType === 'limit';
    const isStop = formData.orderType === 'stop';
    const isStopLimit = formData.orderType === 'stop_limit';
    const isTrailingStop = formData.orderType === 'trailing_stop';
    const isTakeProfit = formData.orderType === 'take_profit';

    const price = formData.price || currentPrice;
    const quantity = formData.quantity;
    const value = quantity * price;
    const feeRate = isBuy ? 0.001 : 0.001; // 0.1% fee
    const calculatedFee = value * feeRate;
    const total = value + (isBuy ? calculatedFee : 0);

    // ========================================================================
    // MISES À JOUR
    // ========================================================================

    useEffect(() => {
      setCalculatedValue(value);
      setFee(calculatedFee);
      setTotalCost(total);
    }, [value, calculatedFee, total]);

    useEffect(() => {
      if (onChange) {
        onChange(formData);
      }
    }, [formData, onChange]);

    // ========================================================================
    // GESTIONNAIRES
    // ========================================================================

    const handleFieldChange = useCallback(<K extends keyof TradeFormData>(
      field: K,
      value: TradeFormData[K]
    ) => {
      setFormData((prev) => ({ ...prev, [field]: value }));
    }, []);

    const handleQuantityChange = useCallback((value: number) => {
      const clamped = Math.max(minQuantity, Math.min(maxQuantity, value));
      handleFieldChange('quantity', clamped);
    }, [minQuantity, maxQuantity, handleFieldChange]);

    const handlePriceChange = useCallback((value: number) => {
      handleFieldChange('price', value);
    }, [handleFieldChange]);

    const handleSideChange = useCallback((side: OrderSide) => {
      handleFieldChange('side', side);
      setActiveTab(side);
    }, [handleFieldChange]);

    const handleOrderTypeChange = useCallback((type: OrderType) => {
      handleFieldChange('orderType', type);
    }, [handleFieldChange]);

    // ========================================================================
    // PRESETS DE QUANTITÉ
    // ========================================================================

    const quantityPresets = useMemo(() => {
      return [0.25, 0.5, 0.75, 1].map((p) => ({
        label: `${p * 100}%`,
        value: p * maxQuantity,
      }));
    }, [maxQuantity]);

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validate = useCallback((): { valid: boolean; errors: Record<string, string> } => {
      const errors: Record<string, string> = {};

      if (formData.quantity <= 0) {
        errors.quantity = 'La quantité doit être supérieure à 0';
      }

      if (formData.quantity > maxQuantity) {
        errors.quantity = `Quantité maximale: ${maxQuantity}`;
      }

      if (formData.quantity < minQuantity) {
        errors.quantity = `Quantité minimale: ${minQuantity}`;
      }

      if (formData.price !== undefined && formData.price <= 0) {
        errors.price = 'Le prix doit être supérieur à 0';
      }

      if (formData.stopPrice !== undefined && formData.stopPrice <= 0) {
        errors.stopPrice = 'Le prix stop doit être supérieur à 0';
      }

      if (formData.takeProfit !== undefined && formData.takeProfit <= 0) {
        errors.takeProfit = 'Le take profit doit être supérieur à 0';
      }

      if (formData.stopLoss !== undefined && formData.stopLoss <= 0) {
        errors.stopLoss = 'Le stop loss doit être supérieur à 0';
      }

      if (isBuy && totalCost > availableBalance) {
        errors.quantity = 'Fonds insuffisants';
      }

      return {
        valid: Object.keys(errors).length === 0,
        errors,
      };
    }, [formData, maxQuantity, minQuantity, isBuy, totalCost, availableBalance]);

    // ========================================================================
    // SOUMISSION
    // ========================================================================

    const handleSubmit = useCallback(async (e: React.FormEvent) => {
      e.preventDefault();

      const { valid, errors } = validate();

      if (!valid) {
        toast({
          title: 'Erreur de validation',
          description: Object.values(errors).join('\n'),
          variant: 'destructive',
        });
        return;
      }

      if (isLoading) return;

      try {
        if (onSubmit) {
          await onSubmit(formData);
        }
      } catch (err) {
        toast({
          title: 'Erreur',
          description: err instanceof Error ? err.message : 'Une erreur est survenue',
          variant: 'destructive',
        });
      }
    }, [formData, validate, isLoading, onSubmit, toast]);

    // ========================================================================
    // RENDU DES STATISTIQUES
    // ========================================================================

    const renderStats = useCallback(() => {
      if (!showStats) return null;

      return (
        <div className="grid grid-cols-3 gap-2 p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
          <div className="text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">Prix</div>
            <div className="mt-1 font-mono text-sm font-semibold">
              {formatPrice ? formatPrice(currentPrice) : currentPrice.toFixed(priceDecimals)}
            </div>
          </div>
          <div className="text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">Volume 24h</div>
            <div className="mt-1 font-mono text-sm font-semibold">
              {formatQuantity ? formatQuantity(volume24h) : volume24h.toFixed(quantityDecimals)}
            </div>
          </div>
          <div className="text-center">
            <div className="text-xs text-gray-500 dark:text-gray-400">Balance</div>
            <div className="mt-1 font-mono text-sm font-semibold">
              {formatQuantity ? formatQuantity(availableBalance) : availableBalance.toFixed(2)} {currency}
            </div>
          </div>
        </div>
      );
    }, [showStats, currentPrice, volume24h, availableBalance, currency, formatPrice, formatQuantity, priceDecimals, quantityDecimals]);

    // ========================================================================
    // RENDU DU RÉSUMÉ
    // ========================================================================

    const renderSummary = useCallback(() => {
      const isPositive = isBuy;

      return (
        <div className="space-y-2 p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg">
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500 dark:text-gray-400">Quantité</span>
            <span className="font-mono font-medium">
              {formatQuantity ? formatQuantity(quantity) : quantity.toFixed(quantityDecimals)}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500 dark:text-gray-400">Prix</span>
            <span className="font-mono font-medium">
              {formatPrice ? formatPrice(price) : price.toFixed(priceDecimals)}
            </span>
          </div>
          <Separator />
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500 dark:text-gray-400">Valeur</span>
            <span className="font-mono font-medium">
              {formatPrice ? formatPrice(value) : value.toFixed(priceDecimals)}
            </span>
          </div>
          <div className="flex items-center justify-between text-sm">
            <span className="text-gray-500 dark:text-gray-400">Frais</span>
            <span className="font-mono font-medium text-gray-500">
              {formatPrice ? formatPrice(fee) : fee.toFixed(priceDecimals)}
            </span>
          </div>
          <Separator />
          <div className="flex items-center justify-between text-sm font-semibold">
            <span className="text-gray-700 dark:text-gray-300">Total</span>
            <span className={cn(
              'font-mono',
              isPositive ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'
            )}>
              {formatPrice ? formatPrice(totalCost) : totalCost.toFixed(priceDecimals)} {currency}
            </span>
          </div>
          {isBuy && (
            <div className="mt-2">
              <Progress
                value={(totalCost / availableBalance) * 100}
                className="h-1"
                variant={totalCost > availableBalance ? 'error' : 'default'}
              />
              <div className="mt-1 flex justify-between text-xs text-gray-500 dark:text-gray-400">
                <span>Disponible</span>
                <span>{((1 - totalCost / availableBalance) * 100).toFixed(1)}%</span>
              </div>
            </div>
          )}
        </div>
      );
    }, [
      isBuy,
      quantity,
      price,
      value,
      fee,
      totalCost,
      availableBalance,
      currency,
      formatPrice,
      formatQuantity,
      priceDecimals,
      quantityDecimals,
    ]);

    // ========================================================================
    // RENDU DES OPTIONS AVANCÉES
    // ========================================================================

    const renderAdvancedOptions = useCallback(() => {
      if (!showAdvancedSettings) return null;

      return (
        <motion.div
          initial={{ opacity: 0, height: 0 }}
          animate={{ opacity: 1, height: 'auto' }}
          exit={{ opacity: 0, height: 0 }}
          className="space-y-3 overflow-hidden"
        >
          <Separator />
          
          {/* Time in Force */}
          <div className="space-y-1">
            <Label htmlFor="timeInForce" className="text-sm">Temps en vigueur</Label>
            <Select
              id="timeInForce"
              options={Object.entries(TIME_IN_FORCE_LABELS).map(([value, label]) => ({
                value,
                label,
              }))}
              value={formData.timeInForce || 'GTC'}
              onChange={(value) => handleFieldChange('timeInForce', value as OrderTimeInForce)}
              disabled={disabled}
              size="sm"
            />
          </div>

          {/* Reduce Only */}
          <div className="flex items-center justify-between">
            <Label htmlFor="reduceOnly" className="text-sm">Réduire uniquement</Label>
            <Switch
              id="reduceOnly"
              checked={formData.reduceOnly || false}
              onCheckedChange={(checked) => handleFieldChange('reduceOnly', checked)}
              disabled={disabled}
            />
          </div>

          {/* Post Only */}
          <div className="flex items-center justify-between">
            <Label htmlFor="postOnly" className="text-sm">Post Only</Label>
            <Switch
              id="postOnly"
              checked={formData.postOnly || false}
              onCheckedChange={(checked) => handleFieldChange('postOnly', checked)}
              disabled={disabled}
            />
          </div>

          {/* Notes */}
          <div className="space-y-1">
            <Label htmlFor="notes" className="text-sm">Notes</Label>
            <Input
              id="notes"
              type="text"
              placeholder="Notes sur l'ordre..."
              value={formData.notes || ''}
              onChange={(e) => handleFieldChange('notes', e.target.value)}
              disabled={disabled}
              size="sm"
            />
          </div>
        </motion.div>
      );
    }, [showAdvancedSettings, formData, disabled, handleFieldChange]);

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const isCompact = variant === 'compact';
    const isMinimal = variant === 'minimal';

    return (
      <Card
        ref={ref}
        id={id}
        className={cn('overflow-hidden', className)}
        aria-label={ariaLabel}
      >
        {/* Header */}
        {!isMinimal && (
          <CardHeader className="flex flex-row items-center justify-between border-b border-gray-200 dark:border-gray-700">
            <CardTitle className="flex items-center gap-2">
              {title}
              <Badge variant="outline" className="font-mono">
                {formData.symbol}
              </Badge>
            </CardTitle>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowAdvancedSettings(!showAdvancedSettings)}
              >
                <Cog6ToothIcon className="h-4 w-4" />
              </Button>
              {onCancel && (
                <Button variant="ghost" size="sm" onClick={onCancel}>
                  Annuler
                </Button>
              )}
            </div>
          </CardHeader>
        )}

        {/* Corps */}
        <CardContent className={cn('p-4 space-y-4', isCompact && 'p-3 space-y-3')}>
          {/* Onglets Achat/Vente */}
          <Tabs
            value={activeTab}
            onValueChange={(value) => handleSideChange(value as OrderSide)}
            className="w-full"
          >
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger
                value="buy"
                className="data-[state=active]:bg-green-500 data-[state=active]:text-white"
              >
                <ArrowUpIcon className="mr-2 h-4 w-4" />
                Acheter
              </TabsTrigger>
              <TabsTrigger
                value="sell"
                className="data-[state=active]:bg-red-500 data-[state=active]:text-white"
              >
                <ArrowDownIcon className="mr-2 h-4 w-4" />
                Vendre
              </TabsTrigger>
            </TabsList>
          </Tabs>

          {/* Statistiques */}
          {!isCompact && renderStats()}

          {/* Type d'ordre */}
          <div className="space-y-1">
            <Label htmlFor="orderType" className="text-sm">Type d'ordre</Label>
            <Select
              id="orderType"
              options={Object.entries(ORDER_TYPE_LABELS).map(([value, label]) => ({
                value,
                label,
                description: ORDER_TYPE_DESCRIPTIONS[value as OrderType],
              }))}
              value={formData.orderType}
              onChange={(value) => handleOrderTypeChange(value as OrderType)}
              disabled={disabled}
              size={isCompact ? 'sm' : 'md'}
            />
          </div>

          {/* Prix (pour limit/stop) */}
          {(isLimit || isStopLimit || isTakeProfit) && (
            <div className="space-y-1">
              <Label htmlFor="price" className="text-sm">Prix</Label>
              <Input
                id="price"
                type="number"
                step={priceStep}
                min={0}
                value={formData.price || currentPrice}
                onChange={(e) => handlePriceChange(parseFloat(e.target.value) || 0)}
                disabled={disabled}
                size={isCompact ? 'sm' : 'md'}
                prefix={<CurrencyDollarIcon className="h-4 w-4 text-gray-400" />}
              />
              {!isCompact && (
                <div className="flex gap-1">
                  {[0.9, 0.95, 1, 1.05, 1.1].map((p) => (
                    <Button
                      key={p}
                      variant="ghost"
                      size="xs"
                      className="h-6 text-xs"
                      onClick={() => handlePriceChange(currentPrice * p)}
                      disabled={disabled}
                    >
                      {p === 1 ? 'Spot' : `${(p * 100).toFixed(0)}%`}
                    </Button>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* Prix stop (pour stop/stop_limit) */}
          {(isStop || isStopLimit || isTrailingStop) && (
            <div className="space-y-1">
              <Label htmlFor="stopPrice" className="text-sm">Prix stop</Label>
              <Input
                id="stopPrice"
                type="number"
                step={priceStep}
                min={0}
                value={formData.stopPrice || currentPrice * 0.95}
                onChange={(e) => handleFieldChange('stopPrice', parseFloat(e.target.value) || 0)}
                disabled={disabled}
                size={isCompact ? 'sm' : 'md'}
                prefix={<ExclamationCircleIcon className="h-4 w-4 text-gray-400" />}
              />
            </div>
          )}

          {/* Quantité */}
          <div className="space-y-1">
            <Label htmlFor="quantity" className="text-sm">Quantité</Label>
            <Input
              id="quantity"
              type="number"
              step={quantityStep}
              min={minQuantity}
              max={maxQuantity}
              value={formData.quantity}
              onChange={(e) => handleQuantityChange(parseFloat(e.target.value) || 0)}
              disabled={disabled}
              size={isCompact ? 'sm' : 'md'}
              suffix={formData.symbol.split('/')[0]}
            />
            {!isCompact && (
              <div className="flex gap-1">
                {quantityPresets.map((preset) => (
                  <Button
                    key={preset.label}
                    variant="ghost"
                    size="xs"
                    className="h-6 text-xs"
                    onClick={() => handleQuantityChange(preset.value)}
                    disabled={disabled}
                  >
                    {preset.label}
                  </Button>
                ))}
                <Button
                  variant="ghost"
                  size="xs"
                  className="h-6 text-xs"
                  onClick={() => handleQuantityChange(maxQuantity)}
                  disabled={disabled}
                >
                  Max
                </Button>
              </div>
            )}
          </div>

          {/* SL/TP */}
          {showSLTP && !isMarket && !isCompact && (
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <Label htmlFor="stopLoss" className="text-sm">Stop Loss</Label>
                <Input
                  id="stopLoss"
                  type="number"
                  step={priceStep}
                  min={0}
                  value={formData.stopLoss || ''}
                  onChange={(e) => handleFieldChange('stopLoss', parseFloat(e.target.value) || undefined)}
                  disabled={disabled}
                  size="sm"
                  placeholder="Auto"
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="takeProfit" className="text-sm">Take Profit</Label>
                <Input
                  id="takeProfit"
                  type="number"
                  step={priceStep}
                  min={0}
                  value={formData.takeProfit || ''}
                  onChange={(e) => handleFieldChange('takeProfit', parseFloat(e.target.value) || undefined)}
                  disabled={disabled}
                  size="sm"
                  placeholder="Auto"
                />
              </div>
            </div>
          )}

          {/* Leverage */}
          {showLeverage && !isCompact && (
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <Label htmlFor="leverage" className="text-sm">Leverage</Label>
                <span className="text-sm font-mono text-gray-500">
                  {formData.leverage}x
                </span>
              </div>
              <Slider
                id="leverage"
                min={1}
                max={maxLeverage}
                step={0.5}
                value={[formData.leverage || 1]}
                onValueChange={(value) => handleFieldChange('leverage', value[0])}
                disabled={disabled}
              />
            </div>
          )}

          {/* Options avancées */}
          {renderAdvancedOptions()}

          {/* Résumé */}
          {!isMinimal && renderSummary()}

          {/* Erreur */}
          {error && (
            <div className="flex items-center gap-2 text-sm text-red-600 dark:text-red-400">
              <ExclamationTriangleIcon className="h-5 w-5" />
              <span>{error}</span>
            </div>
          )}

          {/* Boutons d'action */}
          <div className={cn('flex gap-2', isCompact && 'flex-col')}>
            {onCancel && (
              <Button
                type="button"
                variant="ghost"
                className={cn(isCompact ? 'w-full' : 'flex-1')}
                onClick={onCancel}
                disabled={isLoading}
              >
                Annuler
              </Button>
            )}
            <Button
              ref={submitButtonRef}
              type="submit"
              className={cn(
                'flex-1',
                isBuy 
                  ? 'bg-green-500 hover:bg-green-600 dark:bg-green-600 dark:hover:bg-green-700' 
                  : 'bg-red-500 hover:bg-red-600 dark:bg-red-600 dark:hover:bg-red-700',
                isCompact && 'w-full'
              )}
              onClick={handleSubmit}
              disabled={disabled || isLoading}
              isLoading={isLoading}
            >
              {isBuy ? 'Acheter' : 'Vendre'} {formData.symbol.split('/')[0]}
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }
);

TradeForm.displayName = 'TradeForm';

// ============================================================================
// EXPORTS
// ============================================================================

export default TradeForm;

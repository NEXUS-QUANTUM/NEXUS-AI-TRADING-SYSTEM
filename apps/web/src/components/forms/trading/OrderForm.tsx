// apps/web/src/components/forms/trading/OrderForm.tsx
/**
 * NEXUS AI TRADING SYSTEM - Order Form Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * Ce composant gère la création, la modification et l'annulation
 * des ordres de trading sur différentes plateformes.
 */

'use client';

import React, { useState, useEffect, useCallback, useMemo, useRef } from 'react';
import { useForm, Controller } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import {
  Loader2,
  Send,
  X,
  Plus,
  Minus,
  TrendingUp,
  TrendingDown,
  Clock,
  Calendar,
  AlertCircle,
  CheckCircle,
  Shield,
  Zap,
  Edit2,
  Copy,
  RefreshCw,
  ArrowUp,
  ArrowDown,
  DollarSign,
  Percentage,
  Wallet,
  Ban,
} from 'lucide-react';

// NEXUS Internal Components
import { Button } from '@/components/ui/button';
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from '@/components/ui/card';
import {
  Form,
  FormControl,
  FormDescription,
  FormField,
  FormItem,
  FormLabel,
  FormMessage,
} from '@/components/ui/form';
import { Input } from '@/components/ui/input';
import { InputGroup } from '@/components/ui/input-group';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Tabs,
  TabsContent,
  TabsList,
  TabsTrigger,
} from '@/components/ui/tabs';
import { Switch } from '@/components/ui/switch';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip';
import { Slider } from '@/components/ui/slider';
import { Separator } from '@/components/ui/separator';
import { Progress } from '@/components/ui/progress';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover';
import { Calendar as CalendarComponent } from '@/components/ui/calendar';

// NEXUS Hooks & Services
import { useOrder } from '@/hooks/trading/useOrder';
import { useMarketData } from '@/hooks/market/useMarketData';
import { usePortfolio } from '@/hooks/portfolio/usePortfolio';
import { useWebSocket } from '@/hooks/websocket/useWebSocket';
import { useDebounce } from '@/hooks/utils/useDebounce';

// NEXUS Types
import type {
  OrderRequest,
  OrderResponse,
  OrderType,
  OrderSide,
  OrderStatus,
  TimeInForce,
  MarketSymbol,
  OrderBookLevel,
  Position,
} from '@/types/trading';

// NEXUS Constants
import {
  ORDER_TYPES,
  ORDER_SIDES,
  TIME_IN_FORCE,
  ORDER_VALIDITY,
  DEFAULT_ORDER_CONFIG,
  MAX_ORDER_SIZE,
  MIN_ORDER_SIZE,
} from '@/constants/trading';

// Styles
import '@/styles/forms/trading/order-form.css';

/**
 * SCHÉMA DE VALIDATION
 * Zod schema pour la validation du formulaire d'ordre
 */
const orderSchema = z
  .object({
    // Informations de base
    symbol: z.string().min(1, 'Symbole requis'),
    side: z.enum(['BUY', 'SELL']),
    orderType: z.enum(['MARKET', 'LIMIT', 'STOP', 'STOP_LIMIT', 'TRAILING_STOP']),

    // Quantité
    quantity: z.number()
      .positive('La quantité doit être positive')
      .min(MIN_ORDER_SIZE, `Quantité minimum: ${MIN_ORDER_SIZE}`)
      .max(MAX_ORDER_SIZE, `Quantité maximum: ${MAX_ORDER_SIZE}`),

    // Prix (pour LIMIT, STOP_LIMIT)
    price: z.number()
      .positive('Le prix doit être positif')
      .optional()
      .or(z.literal(''))
      .refine((val) => val === '' || val !== undefined, {
        message: 'Prix requis pour les ordres LIMIT et STOP_LIMIT',
      }),

    // Prix de déclenchement (pour STOP, STOP_LIMIT, TRAILING_STOP)
    stopPrice: z.number()
      .positive('Le prix de stop doit être positif')
      .optional()
      .or(z.literal('')),

    // Trailing stop (pour TRAILING_STOP)
    trailValue: z.number()
      .positive('La valeur de trailing doit être positive')
      .optional()
      .or(z.literal('')),

    trailType: z.enum(['PERCENTAGE', 'ABSOLUTE']).default('PERCENTAGE'),

    // Time in Force
    timeInForce: z.enum(['GTC', 'IOC', 'FOK', 'GTD', 'DAY']),

    // Validité (pour GTD)
    expireDate: z.date().optional(),

    // Ordres avancés
    reduceOnly: z.boolean().default(false),
    postOnly: z.boolean().default(false),
    iceberg: z.boolean().default(false),
    icebergSize: z.number()
      .positive('La taille d\'iceberg doit être positive')
      .optional(),

    // Paramètres de risque
    useStopLoss: z.boolean().default(false),
    stopLossPrice: z.number()
      .positive('Le prix de stop-loss doit être positif')
      .optional(),

    useTakeProfit: z.boolean().default(false),
    takeProfitPrice: z.number()
      .positive('Le prix de take-profit doit être positif')
      .optional(),

    // Tags et métadonnées
    clientOrderId: z.string()
      .max(50, 'L\'ID client ne peut pas dépasser 50 caractères')
      .optional(),
    tag: z.string()
      .max(30, 'Le tag ne peut pas dépasser 30 caractères')
      .optional(),
    notes: z.string()
      .max(200, 'Les notes ne peuvent pas dépasser 200 caractères')
      .optional(),
  })
  .refine(
    (data) => {
      // Validation : LIMIT nécessite un prix
      if (data.orderType === 'LIMIT' || data.orderType === 'STOP_LIMIT') {
        return data.price && data.price > 0;
      }
      return true;
    },
    {
      message: 'Le prix est requis pour les ordres LIMIT et STOP_LIMIT',
      path: ['price'],
    }
  )
  .refine(
    (data) => {
      // Validation : STOP et STOP_LIMIT nécessitent un stopPrice
      if (data.orderType === 'STOP' || data.orderType === 'STOP_LIMIT') {
        return data.stopPrice && data.stopPrice > 0;
      }
      return true;
    },
    {
      message: 'Le prix de stop est requis pour les ordres STOP et STOP_LIMIT',
      path: ['stopPrice'],
    }
  )
  .refine(
    (data) => {
      // Validation : TRAILING_STOP nécessite une valeur de trailing
      if (data.orderType === 'TRAILING_STOP') {
        return data.trailValue && data.trailValue > 0;
      }
      return true;
    },
    {
      message: 'La valeur de trailing est requise pour les ordres TRAILING_STOP',
      path: ['trailValue'],
    }
  )
  .refine(
    (data) => {
      // Validation : Si useStopLoss est activé, stopLossPrice est requis
      if (data.useStopLoss) {
        return data.stopLossPrice && data.stopLossPrice > 0;
      }
      return true;
    },
    {
      message: 'Le prix de stop-loss est requis',
      path: ['stopLossPrice'],
    }
  )
  .refine(
    (data) => {
      // Validation : Si useTakeProfit est activé, takeProfitPrice est requis
      if (data.useTakeProfit) {
        return data.takeProfitPrice && data.takeProfitPrice > 0;
      }
      return true;
    },
    {
      message: 'Le prix de take-profit est requis',
      path: ['takeProfitPrice'],
    }
  );

type OrderFormValues = z.infer<typeof orderSchema>;

/**
 * PROPS DU COMPOSANT
 */
interface OrderFormProps {
  /** ID de l'ordre à éditer (null pour un nouveau) */
  orderId?: string | null;
  /** Symbole par défaut */
  defaultSymbol?: string;
  /** Side par défaut (BUY/SELL) */
  defaultSide?: OrderSide;
  /** Type d'ordre par défaut */
  defaultOrderType?: OrderType;
  /** Mode de visualisation (lecture seule) */
  readOnly?: boolean;
  /** Fonction de callback après soumission */
  onSubmitOrder?: (data: OrderResponse) => void;
  /** Fonction de callback après annulation */
  onCancel?: () => void;
  /** Fonction de callback après modification */
  onModify?: (data: OrderResponse) => void;
  /** Classe CSS additionnelle */
  className?: string;
}

/**
 * COMPOSANT PRINCIPAL
 */
export function OrderForm({
  orderId = null,
  defaultSymbol = 'BTC-USD',
  defaultSide = 'BUY',
  defaultOrderType = 'LIMIT',
  readOnly = false,
  onSubmitOrder,
  onCancel,
  onModify,
  className = '',
}: OrderFormProps) {
  // ============================================================
  // ÉTATS & HOOKS
  // ============================================================

  const [isLoading, setIsLoading] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isModifying, setIsModifying] = useState(false);
  const [activeTab, setActiveTab] = useState('basic');
  const [estimatedTotal, setEstimatedTotal] = useState(0);
  const [estimatedFees, setEstimatedFees] = useState(0);
  const [isDirty, setIsDirty] = useState(false);
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [orderStatus, setOrderStatus] = useState<OrderStatus | null>(null);
  const [lastPrice, setLastPrice] = useState<number | null>(null);
  const [orderBook, setOrderBook] = useState<OrderBookLevel[]>([]);
  const [balance, setBalance] = useState<number | null>(null);
  const [availableBalance, setAvailableBalance] = useState<number | null>(null);

  // Hooks personnalisés
  const {
    createOrder,
    modifyOrder,
    cancelOrder,
    getOrder,
    previewOrder,
  } = useOrder();

  const { 
    getSymbolData, 
    getOrderBook, 
    getLastPrice,
    subscribeToSymbol,
    unsubscribeFromSymbol,
  } = useMarketData();

  const { getBalance, getAvailableBalance } = usePortfolio();
  const { sendMessage, lastMessage, isConnected } = useWebSocket('/ws/trading/order');

  // Refs
  const priceInputRef = useRef<HTMLInputElement>(null);
  const quantityInputRef = useRef<HTMLInputElement>(null);
  const subscriptionRef = useRef<(() => void) | null>(null);

  // Debounce pour les calculs de prix
  const debouncedPrice = useDebounce(useWatch('price'), 300);
  const debouncedQuantity = useDebounce(useWatch('quantity'), 300);

  // ============================================================
  // FORMULAIRE REACT-HOOK-FORM
  // ============================================================

  const form = useForm<OrderFormValues>({
    resolver: zodResolver(orderSchema),
    defaultValues: {
      symbol: defaultSymbol,
      side: defaultSide,
      orderType: defaultOrderType,
      quantity: 0,
      price: '',
      stopPrice: '',
      trailValue: '',
      trailType: 'PERCENTAGE',
      timeInForce: 'GTC',
      reduceOnly: false,
      postOnly: false,
      iceberg: false,
      icebergSize: 0,
      useStopLoss: false,
      stopLossPrice: '',
      useTakeProfit: false,
      takeProfitPrice: '',
      clientOrderId: '',
      tag: '',
      notes: '',
    },
    mode: 'onChange',
  });

  const { 
    control, 
    handleSubmit, 
    watch, 
    setValue, 
    getValues, 
    reset, 
    formState,
    setError,
    clearErrors,
  } = form;

  const { errors, isValid } = formState;

  // ============================================================
  // EFFETS
  // ============================================================

  // Chargement des données si édition
  useEffect(() => {
    if (orderId) {
      loadOrderData(orderId);
    }
  }, [orderId]);

  // Chargement des données de marché
  useEffect(() => {
    const symbol = watch('symbol');
    if (symbol) {
      loadMarketData(symbol);
      subscribeToSymbolUpdates(symbol);
    }
    return () => {
      if (subscriptionRef.current) {
        subscriptionRef.current();
      }
    };
  }, [watch('symbol')]);

  // Calcul du total estimé
  useEffect(() => {
    const quantity = debouncedQuantity || 0;
    const price = debouncedPrice || 0;
    const fees = calculateFees(quantity, price);
    setEstimatedTotal(quantity * price);
    setEstimatedFees(fees);
  }, [debouncedQuantity, debouncedPrice]);

  // Mise à jour du statut de l'ordre via WebSocket
  useEffect(() => {
    if (lastMessage && orderId) {
      try {
        const data = JSON.parse(lastMessage);
        if (data.type === 'ORDER_UPDATE' && data.orderId === orderId) {
          setOrderStatus(data.status);
          toast.info(`Ordre ${data.status}`, {
            description: `L'ordre #${orderId} est maintenant ${data.status}`,
          });
        }
        if (data.type === 'ORDER_FILLED' && data.orderId === orderId) {
          toast.success('Ordre exécuté !', {
            description: `L'ordre #${orderId} a été rempli`,
          });
        }
        if (data.type === 'ORDER_CANCELLED' && data.orderId === orderId) {
          toast.warning('Ordre annulé');
          if (onCancel) onCancel();
        }
      } catch (error) {
        console.error('Erreur de parsing WebSocket:', error);
      }
    }
  }, [lastMessage]);

  // ============================================================
  // FONCTIONS MÉTIER
  // ============================================================

  /**
   * Calcule les frais estimés
   */
  const calculateFees = useCallback((quantity: number, price: number): number => {
    // Taux de frais moyen (0.1%)
    const feeRate = 0.001;
    return quantity * price * feeRate;
  }, []);

  /**
   * Charge les données d'un ordre existant
   */
  const loadOrderData = useCallback(
    async (id: string) => {
      setIsLoading(true);
      try {
        const data = await getOrder(id);
        if (data) {
          // Transformation des données pour le formulaire
          const formData: OrderFormValues = {
            symbol: data.symbol,
            side: data.side,
            orderType: data.orderType,
            quantity: data.quantity,
            price: data.price || '',
            stopPrice: data.stopPrice || '',
            trailValue: data.trailValue || '',
            trailType: data.trailType || 'PERCENTAGE',
            timeInForce: data.timeInForce || 'GTC',
            reduceOnly: data.reduceOnly || false,
            postOnly: data.postOnly || false,
            iceberg: data.iceberg || false,
            icebergSize: data.icebergSize || 0,
            useStopLoss: data.useStopLoss || false,
            stopLossPrice: data.stopLossPrice || '',
            useTakeProfit: data.useTakeProfit || false,
            takeProfitPrice: data.takeProfitPrice || '',
            clientOrderId: data.clientOrderId || '',
            tag: data.tag || '',
            notes: data.notes || '',
          };
          reset(formData);
          setIsDirty(false);
          setOrderStatus(data.status);
        }
      } catch (error) {
        console.error('Erreur de chargement:', error);
        toast.error('Erreur de chargement', {
          description: 'Impossible de charger les données de l\'ordre',
        });
      } finally {
        setIsLoading(false);
      }
    },
    [getOrder, reset]
  );

  /**
   * Charge les données de marché
   */
  const loadMarketData = useCallback(
    async (symbol: string) => {
      try {
        const [price, book, bal, avail] = await Promise.all([
          getLastPrice(symbol),
          getOrderBook(symbol),
          getBalance(symbol.split('-')[0]),
          getAvailableBalance(symbol.split('-')[0]),
        ]);
        setLastPrice(price);
        setOrderBook(book);
        setBalance(bal);
        setAvailableBalance(avail);

        // Mise à jour automatique du prix pour les ordres LIMIT
        const orderType = watch('orderType');
        if (orderType === 'LIMIT' && !watch('price')) {
          const defaultPrice = watch('side') === 'BUY' 
            ? price * 0.9995 
            : price * 1.0005;
          setValue('price', defaultPrice);
        }
      } catch (error) {
        console.error('Erreur de chargement des données de marché:', error);
      }
    },
    [getLastPrice, getOrderBook, getBalance, getAvailableBalance, watch, setValue]
  );

  /**
   * S'abonne aux mises à jour du symbole
   */
  const subscribeToSymbolUpdates = useCallback(
    (symbol: string) => {
      if (subscriptionRef.current) {
        subscriptionRef.current();
      }
      subscriptionRef.current = subscribeToSymbol(symbol, (data) => {
        if (data.type === 'PRICE') {
          setLastPrice(data.price);
        }
        if (data.type === 'ORDER_BOOK') {
          setOrderBook(data.levels);
        }
        if (data.type === 'BALANCE') {
          setBalance(data.balance);
          setAvailableBalance(data.available);
        }
      });
    },
    [subscribeToSymbol]
  );

  /**
   * Prépare la soumission de l'ordre
   */
  const onSubmit = useCallback(
    async (data: OrderFormValues) => {
      // Vérification du solde
      if (data.side === 'BUY') {
        const total = data.quantity * (data.price || 0);
        if (availableBalance !== null && total > availableBalance) {
          setError('quantity', {
            type: 'manual',
            message: `Solde insuffisant. Disponible: $${availableBalance.toFixed(2)}`,
          });
          return;
        }
      }

      // Vérification des positions (pour SELL)
      if (data.side === 'SELL' && data.reduceOnly) {
        // Vérification de la position existante
        // ... logique de vérification des positions
      }

      // Prévisualisation
      try {
        const preview = await previewOrder(data);
        if (!preview.valid) {
          toast.error('Ordre invalide', {
            description: preview.message,
          });
          return;
        }

        setShowConfirmDialog(true);
      } catch (error) {
        console.error('Erreur de prévisualisation:', error);
        toast.error('Erreur de prévisualisation');
      }
    },
    [availableBalance, previewOrder, setError]
  );

  /**
   * Confirme la soumission de l'ordre
   */
  const confirmSubmit = useCallback(
    async (data: OrderFormValues) => {
      setShowConfirmDialog(false);
      setIsSubmitting(true);

      try {
        const response = await createOrder(data);
        toast.success('Ordre envoyé !', {
          description: `Ordre #${response.id} placé avec succès`,
        });

        // Envoi via WebSocket
        sendMessage(
          JSON.stringify({
            type: 'ORDER_SUBMITTED',
            orderId: response.id,
            data: response,
          })
        );

        setIsDirty(false);
        if (onSubmitOrder) {
          onSubmitOrder(response);
        }

        // Reset du formulaire pour un nouvel ordre
        if (!orderId) {
          reset({
            ...data,
            quantity: 0,
            price: '',
            stopPrice: '',
            trailValue: '',
          });
        }
      } catch (error) {
        console.error('Erreur de soumission:', error);
        toast.error('Erreur de soumission', {
          description: error instanceof Error ? error.message : 'Une erreur est survenue',
        });
      } finally {
        setIsSubmitting(false);
      }
    },
    [createOrder, onSubmitOrder, reset, sendMessage]
  );

  /**
   * Modifie un ordre existant
   */
  const handleModifyOrder = useCallback(
    async (data: OrderFormValues) => {
      if (!orderId) return;

      setIsModifying(true);
      try {
        const response = await modifyOrder(orderId, data);
        toast.success('Ordre modifié', {
          description: `Ordre #${orderId} mis à jour`,
        });

        sendMessage(
          JSON.stringify({
            type: 'ORDER_MODIFIED',
            orderId: response.id,
            data: response,
          })
        );

        if (onModify) {
          onModify(response);
        }
      } catch (error) {
        console.error('Erreur de modification:', error);
        toast.error('Erreur de modification');
      } finally {
        setIsModifying(false);
      }
    },
    [orderId, modifyOrder, onModify, sendMessage]
  );

  /**
   * Annule un ordre
   */
  const handleCancelOrder = useCallback(async () => {
    if (!orderId) return;

    try {
      await cancelOrder(orderId);
      toast.success('Ordre annulé');
      if (onCancel) onCancel();
    } catch (error) {
      console.error('Erreur d\'annulation:', error);
      toast.error('Erreur d\'annulation');
    }
  }, [orderId, cancelOrder, onCancel]);

  /**
   * Quick fill (50%, 75%, 100%)
   */
  const quickFill = useCallback(
    (percentage: number) => {
      if (!availableBalance || !lastPrice) return;

      const maxQuantity = availableBalance / (lastPrice || 1);
      const quantity = Math.floor((maxQuantity * percentage) / 100 * 100000) / 100000;
      setValue('quantity', quantity);
      setIsDirty(true);
    },
    [availableBalance, lastPrice, setValue]
  );

  /**
   * Met à jour le prix avec le marché
   */
  const updatePriceFromMarket = useCallback(() => {
    if (!lastPrice) return;
    const side = watch('side');
    const orderType = watch('orderType');
    
    if (orderType === 'LIMIT') {
      const price = side === 'BUY' 
        ? lastPrice * 0.9995 
        : lastPrice * 1.0005;
      setValue('price', price);
    }
    if (orderType === 'STOP' || orderType === 'STOP_LIMIT') {
      const price = side === 'BUY' 
        ? lastPrice * 1.005 
        : lastPrice * 0.995;
      setValue('stopPrice', price);
    }
    setIsDirty(true);
  }, [lastPrice, watch, setValue]);

  // ============================================================
  // RENDU
  // ============================================================

  const selectedSymbol = watch('symbol');
  const selectedSide = watch('side');
  const selectedOrderType = watch('orderType');
  const quantity = watch('quantity') || 0;
  const price = watch('price') || 0;

  if (isLoading && orderId) {
    return (
      <div className="flex flex-col items-center justify-center p-12 space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <p className="text-muted-foreground">Chargement de l'ordre...</p>
      </div>
    );
  }

  const isMarketOrder = selectedOrderType === 'MARKET';
  const isLimitOrder = selectedOrderType === 'LIMIT' || selectedOrderType === 'STOP_LIMIT';
  const isStopOrder = selectedOrderType === 'STOP' || selectedOrderType === 'STOP_LIMIT';
  const isTrailingOrder = selectedOrderType === 'TRAILING_STOP';

  return (
    <>
      <Form {...form}>
        <form
          onSubmit={handleSubmit(onSubmit)}
          className={`order-form space-y-4 ${className}`}
          noValidate
        >
          {/* ============================================================
              EN-TÊTE
          ============================================================ */}
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    {orderId ? (
                      <>
                        <Edit2 className="w-5 h-5" />
                        Modifier l'ordre
                        <Badge variant="outline" className="ml-2">
                          #{orderId.slice(0, 8)}
                        </Badge>
                      </>
                    ) : (
                      <>
                        <Send className="w-5 h-5" />
                        Nouvel ordre
                      </>
                    )}
                    {orderStatus && (
                      <Badge 
                        variant={
                          orderStatus === 'FILLED' ? 'success' :
                          orderStatus === 'CANCELLED' ? 'destructive' :
                          orderStatus === 'PARTIALLY_FILLED' ? 'warning' :
                          'secondary'
                        }
                      >
                        {orderStatus}
                      </Badge>
                    )}
                    {isDirty && (
                      <Badge variant="outline" className="text-yellow-500 border-yellow-500">
                        Modifié
                      </Badge>
                    )}
                  </CardTitle>
                  <CardDescription>
                    {orderId 
                      ? 'Modifiez ou annulez votre ordre'
                      : 'Placez un ordre de trading'}
                  </CardDescription>
                </div>
                <div className="flex items-center gap-2">
                  {lastPrice && (
                    <div className="text-right">
                      <p className="text-xs text-muted-foreground">Dernier prix</p>
                      <p className="text-lg font-mono font-bold">
                        ${lastPrice.toFixed(2)}
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </CardHeader>
          </Card>

          {/* ============================================================
              ONGLETS
          ============================================================ */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full grid-cols-3">
              <TabsTrigger value="basic" className="gap-2">
                <Zap className="w-4 h-4" />
                Ordre
              </TabsTrigger>
              <TabsTrigger value="advanced" className="gap-2">
                <Shield className="w-4 h-4" />
                Avancé
              </TabsTrigger>
              <TabsTrigger value="risk" className="gap-2">
                <AlertCircle className="w-4 h-4" />
                Risque
              </TabsTrigger>
            </TabsList>

            {/* ============================================================
                ONGLET 1 : ORDRE
            ============================================================ */}
            <TabsContent value="basic" className="space-y-4">
              <Card>
                <CardContent className="pt-6 space-y-4">
                  {/* Symbole et Side */}
                  <div className="grid grid-cols-2 gap-4">
                    <FormField
                      control={control}
                      name="symbol"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Symbole</FormLabel>
                          <Select
                            disabled={readOnly || !!orderId}
                            onValueChange={field.onChange}
                            defaultValue={field.value}
                            value={field.value}
                          >
                            <FormControl>
                              <SelectTrigger>
                                <SelectValue placeholder="Sélectionnez" />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              <SelectItem value="BTC-USD">BTC-USD</SelectItem>
                              <SelectItem value="ETH-USD">ETH-USD</SelectItem>
                              <SelectItem value="SOL-USD">SOL-USD</SelectItem>
                              <SelectItem value="ADA-USD">ADA-USD</SelectItem>
                              <SelectItem value="DOT-USD">DOT-USD</SelectItem>
                            </SelectContent>
                          </Select>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={control}
                      name="side"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Direction</FormLabel>
                          <div className="grid grid-cols-2 gap-2">
                            <Button
                              type="button"
                              variant={field.value === 'BUY' ? 'default' : 'outline'}
                              className={`gap-2 ${
                                field.value === 'BUY' 
                                  ? 'bg-green-500 hover:bg-green-600 text-white' 
                                  : ''
                              }`}
                              onClick={() => {
                                field.onChange('BUY');
                                setIsDirty(true);
                              }}
                              disabled={readOnly}
                            >
                              <TrendingUp className="w-4 h-4" />
                              ACHAT
                            </Button>
                            <Button
                              type="button"
                              variant={field.value === 'SELL' ? 'default' : 'outline'}
                              className={`gap-2 ${
                                field.value === 'SELL' 
                                  ? 'bg-red-500 hover:bg-red-600 text-white' 
                                  : ''
                              }`}
                              onClick={() => {
                                field.onChange('SELL');
                                setIsDirty(true);
                              }}
                              disabled={readOnly}
                            >
                              <TrendingDown className="w-4 h-4" />
                              VENTE
                            </Button>
                          </div>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>

                  {/* Type d'ordre */}
                  <FormField
                    control={control}
                    name="orderType"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Type d'ordre</FormLabel>
                        <div className="grid grid-cols-3 md:grid-cols-5 gap-2">
                          {ORDER_TYPES.map((type) => (
                            <Button
                              key={type.value}
                              type="button"
                              variant={field.value === type.value ? 'default' : 'outline'}
                              size="sm"
                              onClick={() => {
                                field.onChange(type.value);
                                setIsDirty(true);
                              }}
                              disabled={readOnly}
                              className="text-xs"
                            >
                              {type.icon} {type.label}
                            </Button>
                          ))}
                        </div>
                        <FormMessage />
                      </FormItem>
                    )}
                  />

                  <Separator />

                  {/* Quantité */}
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <FormLabel>Quantité</FormLabel>
                      {availableBalance !== null && (
                        <span className="text-xs text-muted-foreground">
                          Disponible: {availableBalance.toFixed(4)} {selectedSymbol.split('-')[0]}
                        </span>
                      )}
                    </div>
                    <div className="flex gap-2">
                      <FormField
                        control={control}
                        name="quantity"
                        render={({ field }) => (
                          <FormItem className="flex-1">
                            <FormControl>
                              <Input
                                {...field}
                                type="number"
                                step="0.0001"
                                min="0"
                                ref={quantityInputRef}
                                disabled={readOnly}
                                onChange={(e) => {
                                  field.onChange(parseFloat(e.target.value) || 0);
                                  setIsDirty(true);
                                }}
                                className="font-mono text-lg"
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => quickFill(25)}
                        disabled={readOnly || !availableBalance}
                      >
                        25%
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => quickFill(50)}
                        disabled={readOnly || !availableBalance}
                      >
                        50%
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => quickFill(75)}
                        disabled={readOnly || !availableBalance}
                      >
                        75%
                      </Button>
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        onClick={() => quickFill(100)}
                        disabled={readOnly || !availableBalance}
                      >
                        100%
                      </Button>
                    </div>
                  </div>

                  {/* Prix (pour LIMIT et STOP_LIMIT) */}
                  {isLimitOrder && (
                    <FormField
                      control={control}
                      name="price"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Prix limite</FormLabel>
                          <FormControl>
                            <div className="relative">
                              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                                $
                              </span>
                              <Input
                                {...field}
                                type="number"
                                step="0.01"
                                min="0"
                                ref={priceInputRef}
                                disabled={readOnly}
                                onChange={(e) => {
                                  field.onChange(parseFloat(e.target.value) || '');
                                  setIsDirty(true);
                                }}
                                className="pl-7 font-mono"
                              />
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="absolute right-2 top-1/2 -translate-y-1/2"
                                onClick={updatePriceFromMarket}
                                disabled={readOnly || !lastPrice}
                              >
                                <RefreshCw className="w-4 h-4" />
                              </Button>
                            </div>
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  )}

                  {/* Prix de stop (pour STOP et STOP_LIMIT) */}
                  {isStopOrder && (
                    <FormField
                      control={control}
                      name="stopPrice"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Prix de stop</FormLabel>
                          <FormControl>
                            <div className="relative">
                              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                                $
                              </span>
                              <Input
                                {...field}
                                type="number"
                                step="0.01"
                                min="0"
                                disabled={readOnly}
                                onChange={(e) => {
                                  field.onChange(parseFloat(e.target.value) || '');
                                  setIsDirty(true);
                                }}
                                className="pl-7 font-mono"
                              />
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                className="absolute right-2 top-1/2 -translate-y-1/2"
                                onClick={updatePriceFromMarket}
                                disabled={readOnly || !lastPrice}
                              >
                                <RefreshCw className="w-4 h-4" />
                              </Button>
                            </div>
                          </FormControl>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  )}

                  {/* Trailing Stop */}
                  {isTrailingOrder && (
                    <div className="grid grid-cols-2 gap-4">
                      <FormField
                        control={control}
                        name="trailValue"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Valeur de trailing</FormLabel>
                            <FormControl>
                              <Input
                                {...field}
                                type="number"
                                step="0.01"
                                min="0"
                                disabled={readOnly}
                                onChange={(e) => {
                                  field.onChange(parseFloat(e.target.value) || '');
                                  setIsDirty(true);
                                }}
                                className="font-mono"
                              />
                            </FormControl>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={control}
                        name="trailType"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Type de trailing</FormLabel>
                            <Select
                              disabled={readOnly}
                              onValueChange={field.onChange}
                              defaultValue={field.value}
                              value={field.value}
                            >
                              <FormControl>
                                <SelectTrigger>
                                  <SelectValue placeholder="Type" />
                                </SelectTrigger>
                              </FormControl>
                              <SelectContent>
                                <SelectItem value="PERCENTAGE">Pourcentage</SelectItem>
                                <SelectItem value="ABSOLUTE">Absolu</SelectItem>
                              </SelectContent>
                            </Select>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                  )}

                  <Separator />

                  {/* Time in Force */}
                  <div className="grid grid-cols-2 gap-4">
                    <FormField
                      control={control}
                      name="timeInForce"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Durée de validité</FormLabel>
                          <Select
                            disabled={readOnly || isMarketOrder}
                            onValueChange={field.onChange}
                            defaultValue={field.value}
                            value={field.value}
                          >
                            <FormControl>
                              <SelectTrigger>
                                <SelectValue placeholder="Sélectionnez" />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              {TIME_IN_FORCE.map((tif) => (
                                <SelectItem key={tif.value} value={tif.value}>
                                  <div className="flex items-center gap-2">
                                    <span>{tif.icon}</span>
                                    <span>{tif.label}</span>
                                    <span className="text-xs text-muted-foreground">
                                      - {tif.description}
                                    </span>
                                  </div>
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    {watch('timeInForce') === 'GTD' && (
                      <FormField
                        control={control}
                        name="expireDate"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Date d'expiration</FormLabel>
                            <Popover>
                              <PopoverTrigger asChild>
                                <FormControl>
                                  <Button
                                    variant="outline"
                                    className="w-full justify-start text-left font-normal"
                                    disabled={readOnly}
                                  >
                                    <Calendar className="mr-2 h-4 w-4" />
                                    {field.value ? (
                                      field.value.toLocaleDateString('fr-FR')
                                    ) : (
                                      <span>Sélectionnez une date</span>
                                    )}
                                  </Button>
                                </FormControl>
                              </PopoverTrigger>
                              <PopoverContent className="w-auto p-0">
                                <CalendarComponent
                                  mode="single"
                                  selected={field.value}
                                  onSelect={field.onChange}
                                  disabled={(date) => date < new Date()}
                                  initialFocus
                                />
                              </PopoverContent>
                            </Popover>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    )}
                  </div>

                  {/* Résumé de l'ordre */}
                  {(quantity > 0 && (price > 0 || isMarketOrder)) && (
                    <Alert>
                      <DollarSign className="w-4 h-4" />
                      <AlertTitle>Résumé de l'ordre</AlertTitle>
                      <AlertDescription className="space-y-1">
                        <div className="flex justify-between">
                          <span>Total:</span>
                          <span className="font-mono font-bold">
                            ${estimatedTotal.toFixed(2)}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>Frais estimés:</span>
                          <span className="font-mono text-yellow-500">
                            ${estimatedFees.toFixed(2)}
                          </span>
                        </div>
                        <div className="flex justify-between border-t pt-1">
                          <span>Total avec frais:</span>
                          <span className="font-mono font-bold">
                            ${(estimatedTotal + estimatedFees).toFixed(2)}
                          </span>
                        </div>
                      </AlertDescription>
                    </Alert>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {/* ============================================================
                ONGLET 2 : AVANCÉ
            ============================================================ */}
            <TabsContent value="advanced" className="space-y-4">
              <Card>
                <CardContent className="pt-6 space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <FormField
                      control={control}
                      name="reduceOnly"
                      render={({ field }) => (
                        <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                          <div>
                            <FormLabel>Réduction seulement</FormLabel>
                            <FormDescription>
                              Réduire uniquement la position
                            </FormDescription>
                          </div>
                          <FormControl>
                            <Switch
                              checked={field.value}
                              onCheckedChange={(checked) => {
                                field.onChange(checked);
                                setIsDirty(true);
                              }}
                              disabled={readOnly}
                            />
                          </FormControl>
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={control}
                      name="postOnly"
                      render={({ field }) => (
                        <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                          <div>
                            <FormLabel>Post Only</FormLabel>
                            <FormDescription>
                              Ordre limité au carnet
                            </FormDescription>
                          </div>
                          <FormControl>
                            <Switch
                              checked={field.value}
                              onCheckedChange={(checked) => {
                                field.onChange(checked);
                                setIsDirty(true);
                              }}
                              disabled={readOnly || !isLimitOrder}
                            />
                          </FormControl>
                        </FormItem>
                      )}
                    />
                  </div>

                  <FormField
                    control={control}
                    name="iceberg"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                        <div>
                          <FormLabel>Ordre Iceberg</FormLabel>
                          <FormDescription>
                            Masquer la taille totale
                          </FormDescription>
                        </div>
                        <FormControl>
                          <Switch
                            checked={field.value}
                            onCheckedChange={(checked) => {
                              field.onChange(checked);
                              setIsDirty(true);
                              if (!checked) setValue('icebergSize', 0);
                            }}
                            disabled={readOnly || !isLimitOrder}
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />

                  {watch('iceberg') && (
                    <FormField
                      control={control}
                      name="icebergSize"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Taille de l'iceberg</FormLabel>
                          <FormControl>
                            <Input
                              {...field}
                              type="number"
                              step="0.0001"
                              min="0"
                              disabled={readOnly}
                              onChange={(e) => {
                                field.onChange(parseFloat(e.target.value) || 0);
                                setIsDirty(true);
                              }}
                              className="font-mono"
                            />
                          </FormControl>
                          <FormDescription>
                            Taille de chaque tranche de l'iceberg
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  )}

                  <Separator />

                  {/* Métadonnées */}
                  <div className="grid grid-cols-2 gap-4">
                    <FormField
                      control={control}
                      name="clientOrderId"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>ID Client</FormLabel>
                          <FormControl>
                            <Input
                              {...field}
                              placeholder="ID personnalisé"
                              disabled={readOnly}
                            />
                          </FormControl>
                          <FormDescription>
                            Identifiant personnalisé
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={control}
                      name="tag"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Tag</FormLabel>
                          <FormControl>
                            <Input
                              {...field}
                              placeholder="Ex: scalping, swing"
                              disabled={readOnly}
                            />
                          </FormControl>
                          <FormDescription>
                            Tag pour catégoriser l'ordre
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>

                  <FormField
                    control={control}
                    name="notes"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Notes</FormLabel>
                        <FormControl>
                          <Input
                            {...field}
                            placeholder="Notes personnelles"
                            disabled={readOnly}
                          />
                        </FormControl>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            {/* ============================================================
                ONGLET 3 : RISQUE
            ============================================================ */}
            <TabsContent value="risk" className="space-y-4">
              <Card>
                <CardContent className="pt-6 space-y-4">
                  {/* Stop Loss */}
                  <FormField
                    control={control}
                    name="useStopLoss"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                        <div>
                          <FormLabel>Stop Loss</FormLabel>
                          <FormDescription>
                            Protection contre les pertes
                          </FormDescription>
                        </div>
                        <FormControl>
                          <Switch
                            checked={field.value}
                            onCheckedChange={(checked) => {
                              field.onChange(checked);
                              setIsDirty(true);
                              if (!checked) setValue('stopLossPrice', '');
                            }}
                            disabled={readOnly}
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />

                  {watch('useStopLoss') && (
                    <FormField
                      control={control}
                      name="stopLossPrice"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Prix de Stop Loss</FormLabel>
                          <FormControl>
                            <div className="relative">
                              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                                $
                              </span>
                              <Input
                                {...field}
                                type="number"
                                step="0.01"
                                min="0"
                                disabled={readOnly}
                                onChange={(e) => {
                                  field.onChange(parseFloat(e.target.value) || '');
                                  setIsDirty(true);
                                }}
                                className="pl-7 font-mono"
                              />
                            </div>
                          </FormControl>
                          <FormDescription>
                            Prix de déclenchement du stop loss
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  )}

                  <Separator />

                  {/* Take Profit */}
                  <FormField
                    control={control}
                    name="useTakeProfit"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                        <div>
                          <FormLabel>Take Profit</FormLabel>
                          <FormDescription>
                            Prendre les bénéfices
                          </FormDescription>
                        </div>
                        <FormControl>
                          <Switch
                            checked={field.value}
                            onCheckedChange={(checked) => {
                              field.onChange(checked);
                              setIsDirty(true);
                              if (!checked) setValue('takeProfitPrice', '');
                            }}
                            disabled={readOnly}
                          />
                        </FormControl>
                      </FormItem>
                    )}
                  />

                  {watch('useTakeProfit') && (
                    <FormField
                      control={control}
                      name="takeProfitPrice"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Prix de Take Profit</FormLabel>
                          <FormControl>
                            <div className="relative">
                              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                                $
                              </span>
                              <Input
                                {...field}
                                type="number"
                                step="0.01"
                                min="0"
                                disabled={readOnly}
                                onChange={(e) => {
                                  field.onChange(parseFloat(e.target.value) || '');
                                  setIsDirty(true);
                                }}
                                className="pl-7 font-mono"
                              />
                            </div>
                          </FormControl>
                          <FormDescription>
                            Prix de déclenchement du take profit
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  )}

                  <Separator />

                  {/* Visualisation du risque */}
                  {watch('useStopLoss') && watch('stopLossPrice') && (
                    <Alert>
                      <AlertCircle className="w-4 h-4" />
                      <AlertTitle>Risque estimé</AlertTitle>
                      <AlertDescription>
                        Perte potentielle: 
                        <span className="font-mono font-bold text-red-500 ml-2">
                          -{((1 - (watch('stopLossPrice') || 0) / (price || 1)) * 100).toFixed(2)}%
                        </span>
                      </AlertDescription>
                    </Alert>
                  )}

                  {watch('useTakeProfit') && watch('takeProfitPrice') && (
                    <Alert variant="success">
                      <CheckCircle className="w-4 h-4" />
                      <AlertTitle>Gain potentiel</AlertTitle>
                      <AlertDescription>
                        Profit potentiel:
                        <span className="font-mono font-bold text-green-500 ml-2">
                          +{((watch('takeProfitPrice') || 0) / (price || 1) * 100 - 100).toFixed(2)}%
                        </span>
                      </AlertDescription>
                    </Alert>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>

          {/* ============================================================
              PIED DE PAGE
          ============================================================ */}
          <Card>
            <CardFooter className="flex justify-between py-4">
              <div className="flex items-center gap-2">
                {isDirty && (
                  <span className="text-sm text-yellow-500">
                    <Edit2 className="w-3 h-3 inline mr-1" />
                    Modifications non sauvegardées
                  </span>
                )}
                {isConnected ? (
                  <Badge variant="success" className="text-xs">
                    <CheckCircle className="w-3 h-3 mr-1" />
                    Connecté
                  </Badge>
                ) : (
                  <Badge variant="destructive" className="text-xs">
                    <Ban className="w-3 h-3 mr-1" />
                    Déconnecté
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => {
                    if (isDirty) {
                      setShowConfirmDialog(true);
                    } else {
                      reset();
                      if (onCancel) onCancel();
                    }
                  }}
                  disabled={isSubmitting || isModifying}
                >
                  Annuler
                </Button>
                {orderId && (
                  <Button
                    type="button"
                    variant="destructive"
                    onClick={handleCancelOrder}
                    disabled={isSubmitting || isModifying || readOnly}
                  >
                    Annuler l'ordre
                  </Button>
                )}
                {!readOnly && (
                  <Button
                    type="submit"
                    disabled={!isValid || isSubmitting || isModifying}
                  >
                    {isSubmitting || isModifying ? (
                      <>
                        <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                        {orderId ? 'Modification...' : 'Envoi...'}
                      </>
                    ) : (
                      <>
                        {orderId ? (
                          <>
                            <Edit2 className="w-4 h-4 mr-2" />
                            Modifier
                          </>
                        ) : (
                          <>
                            <Send className="w-4 h-4 mr-2" />
                            Envoyer
                          </>
                        )}
                      </>
                    )}
                  </Button>
                )}
              </div>
            </CardFooter>
          </Card>
        </form>
      </Form>

      {/* ============================================================
          DIALOGUE DE CONFIRMATION
      ============================================================ */}
      <Dialog open={showConfirmDialog} onOpenChange={setShowConfirmDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Confirmer l'ordre</DialogTitle>
            <DialogDescription>
              Vérifiez les détails de votre ordre avant de le soumettre.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span>Symbole:</span>
              <span className="font-mono font-bold">{watch('symbol')}</span>
            </div>
            <div className="flex justify-between">
              <span>Direction:</span>
              <span className={`font-mono font-bold ${
                watch('side') === 'BUY' ? 'text-green-500' : 'text-red-500'
              }`}>
                {watch('side')}
              </span>
            </div>
            <div className="flex justify-between">
              <span>Quantité:</span>
              <span className="font-mono font-bold">{watch('quantity')}</span>
            </div>
            {watch('price') && (
              <div className="flex justify-between">
                <span>Prix:</span>
                <span className="font-mono font-bold">${watch('price')}</span>
              </div>
            )}
            <div className="flex justify-between border-t pt-2">
              <span>Total:</span>
              <span className="font-mono font-bold">${estimatedTotal.toFixed(2)}</span>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConfirmDialog(false)}>
              Retour
            </Button>
            <Button onClick={handleSubmit(confirmSubmit)} disabled={isSubmitting}>
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Envoi...
                </>
              ) : (
                'Confirmer'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}

// ============================================================
// EXPORT PAR DÉFAUT
// ============================================================
export default OrderForm;

// ============================================================
// TYPES & UTILITAIRES (exportés pour réutilisation)
// ============================================================
export type { OrderFormProps, OrderFormValues };
export { orderSchema };

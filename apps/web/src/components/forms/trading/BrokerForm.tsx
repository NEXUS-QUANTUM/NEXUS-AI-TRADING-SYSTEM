// apps/web/src/components/forms/trading/BrokerForm.tsx
/**
 * NEXUS AI TRADING SYSTEM - Broker Configuration Form Component
 * Copyright © 2026 NEXUS QUANTUM LTD
 * 
 * Ce composant gère la configuration et la gestion des connexions
 * aux courtiers (brokers) pour l'exécution des trades.
 */

'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import { z } from 'zod';
import { toast } from 'sonner';
import {
  Loader2,
  Link2,
  Unlink,
  Shield,
  Key,
  Building2,
  Globe,
  AlertCircle,
  CheckCircle,
  XCircle,
  Eye,
  EyeOff,
  RefreshCw,
  ExternalLink,
  HelpCircle,
  Server,
  Database,
  Lock,
  User,
  Mail,
  Phone,
  MapPin,
  Calendar,
  CreditCard,
  Wallet,
  Plus,
  Trash2,
  Edit2,
  Copy,
  Check,
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
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from '@/components/ui/accordion';
import { Separator } from '@/components/ui/separator';
import { Progress } from '@/components/ui/progress';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';

// NEXUS Hooks & Services
import { useBroker } from '@/hooks/trading/useBroker';
import { useAuth } from '@/hooks/useAuth';
import { useWebSocket } from '@/hooks/websocket/useWebSocket';
import { useEncryption } from '@/hooks/security/useEncryption';

// NEXUS Types
import type {
  BrokerConfig,
  BrokerType,
  BrokerStatus,
  BrokerCredentials,
  BrokerAccount,
  BrokerConfigRequest,
  BrokerConnectionStatus,
} from '@/types/trading';

// NEXUS Constants
import {
  SUPPORTED_BROKERS,
  BROKER_CATEGORIES,
  BROKER_CONFIG_FIELDS,
  DEFAULT_BROKER_CONFIG,
  BROKER_ICONS,
} from '@/constants/trading';

// Styles
import '@/styles/forms/trading/broker-form.css';

/**
 * SCHÉMA DE VALIDATION
 * Zod schema pour la validation du formulaire de configuration broker
 */
const brokerSchema = z
  .object({
    // Informations générales
    name: z.string()
      .min(3, 'Le nom doit contenir au moins 3 caractères')
      .max(50, 'Le nom ne peut pas dépasser 50 caractères')
      .regex(/^[a-zA-Z0-9\s\-_]+$/, 'Caractères invalides détectés'),

    brokerType: z.enum([
      'BINANCE',
      'COINBASE',
      'KRAKEN',
      'BYBIT',
      'ALPACA',
      'OANDA',
      'INTERACTIVE_BROKERS',
      'FXCM',
      'TRADESTATION',
      'ETRADE',
    ]),

    description: z.string()
      .max(200, 'La description ne peut pas dépasser 200 caractères')
      .optional(),

    // Credentials
    apiKey: z.string()
      .min(1, 'La clé API est requise')
      .max(100, 'La clé API est trop longue'),

    apiSecret: z.string()
      .min(1, 'La clé secrète API est requise')
      .max(200, 'La clé secrète API est trop longue'),

    // Configuration avancée
    environment: z.enum(['SANDBOX', 'LIVE']),
    accountType: z.enum(['SPOT', 'MARGIN', 'FUTURES', 'OPTIONS']),

    // Paramètres optionnels
    passphrase: z.string()
      .max(50, 'Le passphrase est trop long')
      .optional(),

    clientId: z.string()
      .max(50, 'L\'ID client est trop long')
      .optional(),

    accountId: z.string()
      .max(50, 'L\'ID du compte est trop long')
      .optional(),

    // Paramètres de connexion
    baseUrl: z.string()
      .url('URL invalide')
      .optional()
      .or(z.literal('')),

    websocketUrl: z.string()
      .url('URL invalide')
      .optional()
      .or(z.literal('')),

    // Paramètres de sécurité
    enableIpWhitelist: z.boolean().default(false),
    ipWhitelist: z.string()
      .optional()
      .or(z.literal('')),

    enableReadOnly: z.boolean().default(false),

    // Configuration des permissions
    permissions: z.object({
      trading: z.boolean().default(true),
      deposits: z.boolean().default(false),
      withdrawals: z.boolean().default(false),
      transfers: z.boolean().default(false),
      history: z.boolean().default(true),
    }),

    // Paramètres de monitoring
    enableMonitoring: z.boolean().default(true),
    alertOnError: z.boolean().default(true),
    alertThreshold: z.number()
      .min(0.1, 'Le seuil minimum est de 0.1%')
      .max(10, 'Le seuil maximum est de 10%')
      .default(1),

    // Paramètres de cache
    enableCache: z.boolean().default(true),
    cacheTTL: z.number()
      .int('Doit être un nombre entier')
      .min(1, 'Le TTL minimum est de 1 seconde')
      .max(3600, 'Le TTL maximum est de 3600 secondes')
      .default(60),

    // Paramètres de retry
    maxRetries: z.number()
      .int('Doit être un nombre entier')
      .min(0, 'Le nombre minimum de retries est 0')
      .max(10, 'Le nombre maximum de retries est 10')
      .default(3),

    retryDelay: z.number()
      .int('Doit être un nombre entier')
      .min(100, 'Le délai minimum est de 100ms')
      .max(10000, 'Le délai maximum est de 10000ms')
      .default(1000),

    // Paramètres de taux limite
    rateLimit: z.number()
      .int('Doit être un nombre entier')
      .min(0, 'La limite de taux minimum est 0')
      .max(1000, 'La limite de taux maximum est 1000')
      .optional(),

    // Paramètres de balance
    minimumBalance: z.number()
      .min(0, 'Le solde minimum ne peut pas être négatif')
      .optional(),

    maximumBalance: z.number()
      .min(0, 'Le solde maximum ne peut pas être négatif')
      .optional(),
  })
  .refine(
    (data) => {
      // Validation : Si IP Whitelist est activé, une liste doit être fournie
      if (data.enableIpWhitelist && !data.ipWhitelist) {
        return false;
      }
      return true;
    },
    {
      message: 'Veuillez spécifier une liste d\'IPs pour la whitelist',
      path: ['ipWhitelist'],
    }
  )
  .refine(
    (data) => {
      // Validation : Le solde minimum doit être inférieur au solde maximum
      if (
        data.minimumBalance !== undefined &&
        data.maximumBalance !== undefined &&
        data.minimumBalance > data.maximumBalance
      ) {
        return false;
      }
      return true;
    },
    {
      message: 'Le solde minimum ne peut pas être supérieur au solde maximum',
      path: ['minimumBalance'],
    }
  );

type BrokerFormValues = z.infer<typeof brokerSchema>;

/**
 * PROPS DU COMPOSANT
 */
interface BrokerFormProps {
  /** ID du broker à éditer (null pour un nouveau) */
  brokerId?: string | null;
  /** Mode de visualisation (lecture seule) */
  readOnly?: boolean;
  /** Type de broker par défaut */
  defaultBrokerType?: BrokerType;
  /** Fonction de callback après sauvegarde */
  onSave?: (data: BrokerConfig) => void;
  /** Fonction de callback après annulation */
  onCancel?: () => void;
  /** Fonction de callback après test de connexion */
  onTest?: (status: BrokerConnectionStatus) => void;
  /** Classe CSS additionnelle */
  className?: string;
}

/**
 * COMPOSANT PRINCIPAL
 */
export function BrokerForm({
  brokerId = null,
  readOnly = false,
  defaultBrokerType = 'BINANCE',
  onSave,
  onCancel,
  onTest,
  className = '',
}: BrokerFormProps) {
  // ============================================================
  // ÉTATS & HOOKS
  // ============================================================

  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isTesting, setIsTesting] = useState(false);
  const [testStatus, setTestStatus] = useState<BrokerConnectionStatus | null>(null);
  const [showSecret, setShowSecret] = useState(false);
  const [activeTab, setActiveTab] = useState('basic');
  const [isDirty, setIsDirty] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'idle' | 'connecting' | 'connected' | 'error'>('idle');
  const [showConfirmDialog, setShowConfirmDialog] = useState(false);
  const [copiedField, setCopiedField] = useState<string | null>(null);

  // Hooks personnalisés
  const {
    getBroker,
    createBroker,
    updateBroker,
    deleteBroker,
    testConnection,
    getBrokerStatus,
    syncBroker,
  } = useBroker();

  const { user } = useAuth();
  const { encryptData, decryptData } = useEncryption();
  const { sendMessage, lastMessage } = useWebSocket('/ws/trading/broker');

  // ============================================================
  // FORMULAIRE REACT-HOOK-FORM
  // ============================================================

  const form = useForm<BrokerFormValues>({
    resolver: zodResolver(brokerSchema),
    defaultValues: {
      name: '',
      brokerType: defaultBrokerType,
      description: '',
      apiKey: '',
      apiSecret: '',
      environment: 'SANDBOX',
      accountType: 'SPOT',
      passphrase: '',
      clientId: '',
      accountId: '',
      baseUrl: '',
      websocketUrl: '',
      enableIpWhitelist: false,
      ipWhitelist: '',
      enableReadOnly: false,
      permissions: {
        trading: true,
        deposits: false,
        withdrawals: false,
        transfers: false,
        history: true,
      },
      enableMonitoring: true,
      alertOnError: true,
      alertThreshold: 1,
      enableCache: true,
      cacheTTL: 60,
      maxRetries: 3,
      retryDelay: 1000,
      rateLimit: undefined,
      minimumBalance: undefined,
      maximumBalance: undefined,
    },
    mode: 'onChange',
  });

  const { control, handleSubmit, watch, setValue, getValues, reset, formState } = form;
  const { errors, isValid } = formState;

  const selectedBrokerType = watch('brokerType');
  const selectedEnvironment = watch('environment');
  const selectedAccountType = watch('accountType');

  // ============================================================
  // EFFETS
  // ============================================================

  // Chargement des données si édition
  useEffect(() => {
    if (brokerId) {
      loadBrokerData(brokerId);
    }
  }, [brokerId]);

  // Mise à jour des URLs par défaut selon le broker sélectionné
  useEffect(() => {
    const brokerInfo = SUPPORTED_BROKERS.find(b => b.value === selectedBrokerType);
    if (brokerInfo) {
      if (selectedEnvironment === 'SANDBOX' && brokerInfo.sandboxUrl) {
        setValue('baseUrl', brokerInfo.sandboxUrl);
        setValue('websocketUrl', brokerInfo.sandboxWsUrl || '');
      } else if (selectedEnvironment === 'LIVE' && brokerInfo.liveUrl) {
        setValue('baseUrl', brokerInfo.liveUrl);
        setValue('websocketUrl', brokerInfo.liveWsUrl || '');
      }
    }
  }, [selectedBrokerType, selectedEnvironment, setValue]);

  // Monitoring WebSocket
  useEffect(() => {
    if (lastMessage) {
      try {
        const data = JSON.parse(lastMessage);
        if (data.type === 'BROKER_STATUS_UPDATE' && data.brokerId === brokerId) {
          setConnectionStatus(data.status);
          toast.info(`Statut du broker: ${data.status}`, {
            description: data.message,
          });
        }
        if (data.type === 'BROKER_ERROR' && data.brokerId === brokerId) {
          setConnectionStatus('error');
          toast.error('Erreur broker', {
            description: data.message,
          });
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
   * Charge les données d'un broker existant
   */
  const loadBrokerData = useCallback(
    async (id: string) => {
      setIsLoading(true);
      try {
        const data = await getBroker(id);
        if (data) {
          // Décryptage des données sensibles
          const decryptedSecret = await decryptData(data.apiSecret);
          
          // Transformation des données pour le formulaire
          const formData: BrokerFormValues = {
            name: data.name,
            brokerType: data.brokerType,
            description: data.description || '',
            apiKey: data.apiKey,
            apiSecret: decryptedSecret,
            environment: data.environment || 'SANDBOX',
            accountType: data.accountType || 'SPOT',
            passphrase: data.passphrase || '',
            clientId: data.clientId || '',
            accountId: data.accountId || '',
            baseUrl: data.baseUrl || '',
            websocketUrl: data.websocketUrl || '',
            enableIpWhitelist: data.enableIpWhitelist || false,
            ipWhitelist: data.ipWhitelist || '',
            enableReadOnly: data.enableReadOnly || false,
            permissions: data.permissions || {
              trading: true,
              deposits: false,
              withdrawals: false,
              transfers: false,
              history: true,
            },
            enableMonitoring: data.enableMonitoring !== false,
            alertOnError: data.alertOnError !== false,
            alertThreshold: data.alertThreshold || 1,
            enableCache: data.enableCache !== false,
            cacheTTL: data.cacheTTL || 60,
            maxRetries: data.maxRetries || 3,
            retryDelay: data.retryDelay || 1000,
            rateLimit: data.rateLimit,
            minimumBalance: data.minimumBalance,
            maximumBalance: data.maximumBalance,
          };
          reset(formData);
          setIsDirty(false);

          // Récupérer le statut de connexion
          const status = await getBrokerStatus(id);
          if (status) {
            setConnectionStatus(status.connected ? 'connected' : 'error');
          }
        }
      } catch (error) {
        console.error('Erreur de chargement:', error);
        toast.error('Erreur de chargement', {
          description: 'Impossible de charger les données du broker',
        });
      } finally {
        setIsLoading(false);
      }
    },
    [getBroker, getBrokerStatus, decryptData, reset]
  );

  /**
   * Sauvegarde le broker
   */
  const onSubmit = useCallback(
    async (data: BrokerFormValues) => {
      setIsSaving(true);
      try {
        // Chiffrement des données sensibles
        const encryptedSecret = await encryptData(data.apiSecret);
        
        const payload: BrokerConfigRequest = {
          ...data,
          apiSecret: encryptedSecret,
        };

        let response: BrokerConfig;
        if (brokerId) {
          response = await updateBroker(brokerId, payload);
          toast.success('Broker mis à jour', {
            description: 'Les modifications ont été sauvegardées',
          });
        } else {
          response = await createBroker(payload);
          toast.success('Broker ajouté', {
            description: 'Le broker a été enregistré avec succès',
          });
        }

        // Envoi via WebSocket pour mise à jour en temps réel
        sendMessage(
          JSON.stringify({
            type: 'BROKER_UPDATED',
            brokerId: response.id,
            userId: user?.id,
            action: brokerId ? 'UPDATE' : 'CREATE',
          })
        );

        setIsDirty(false);
        if (onSave) {
          onSave(response);
        }
      } catch (error) {
        console.error('Erreur de sauvegarde:', error);
        toast.error('Erreur de sauvegarde', {
          description: error instanceof Error ? error.message : 'Une erreur est survenue',
        });
      } finally {
        setIsSaving(false);
      }
    },
    [brokerId, createBroker, updateBroker, encryptData, onSave, sendMessage, user]
  );

  /**
   * Teste la connexion au broker
   */
  const handleTestConnection = useCallback(async () => {
    const data = getValues();
    
    // Valider le formulaire
    const isValid = await form.trigger();
    if (!isValid) {
      toast.error('Formulaire invalide', {
        description: 'Veuillez corriger les erreurs avant de tester la connexion',
      });
      return;
    }

    setIsTesting(true);
    setConnectionStatus('connecting');
    setTestStatus(null);

    try {
      const encryptedSecret = await encryptData(data.apiSecret);
      const testData = {
        ...data,
        apiSecret: encryptedSecret,
      };

      const result = await testConnection(testData);
      setTestStatus(result);
      setConnectionStatus(result.success ? 'connected' : 'error');

      if (result.success) {
        toast.success('Connexion réussie', {
          description: 'Le broker est accessible et les credentials sont valides',
        });
      } else {
        toast.error('Échec de la connexion', {
          description: result.message || 'Erreur de connexion au broker',
        });
      }

      if (onTest) {
        onTest(result);
      }
    } catch (error) {
      console.error('Erreur de test:', error);
      setConnectionStatus('error');
      toast.error('Erreur de test', {
        description: error instanceof Error ? error.message : 'Une erreur est survenue',
      });
    } finally {
      setIsTesting(false);
    }
  }, [form, getValues, testConnection, encryptData, onTest]);

  /**
   * Synchronise le broker
   */
  const handleSync = useCallback(async () => {
    if (!brokerId) {
      toast.error('Aucun broker sélectionné');
      return;
    }

    setIsLoading(true);
    try {
      const result = await syncBroker(brokerId);
      toast.success('Synchronisation réussie', {
        description: 'Les données du broker ont été synchronisées',
      });
    } catch (error) {
      console.error('Erreur de synchronisation:', error);
      toast.error('Erreur de synchronisation');
    } finally {
      setIsLoading(false);
    }
  }, [brokerId, syncBroker]);

  /**
   * Annulation
   */
  const handleCancel = useCallback(() => {
    if (isDirty) {
      setShowConfirmDialog(true);
      return;
    }
    reset();
    if (onCancel) {
      onCancel();
    }
  }, [isDirty, reset, onCancel]);

  /**
   * Copie d'un champ
   */
  const copyToClipboard = useCallback((text: string, field: string) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
    toast.success('Copié !');
  }, []);

  // ============================================================
  // RENDU DES CHAMPS SPÉCIFIQUES PAR BROKER
  // ============================================================

  const renderBrokerFields = useCallback(() => {
    const brokerInfo = SUPPORTED_BROKERS.find(b => b.value === selectedBrokerType);
    if (!brokerInfo) return null;

    const fields = BROKER_CONFIG_FIELDS[selectedBrokerType] || [];

    return (
      <div className="space-y-4">
        {fields.map((field) => {
          switch (field.type) {
            case 'text':
            case 'password':
              return (
                <FormField
                  key={field.name}
                  control={control}
                  name={field.name as any}
                  render={({ field: formField }) => (
                    <FormItem>
                      <FormLabel>
                        {field.label}
                        {field.required && <span className="text-destructive ml-1">*</span>}
                      </FormLabel>
                      <FormControl>
                        <div className="relative">
                          <Input
                            {...formField}
                            type={field.type === 'password' && !showSecret ? 'password' : 'text'}
                            placeholder={field.placeholder}
                            disabled={readOnly}
                            className="font-mono"
                          />
                          {field.type === 'password' && (
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="absolute right-2 top-1/2 -translate-y-1/2"
                              onClick={() => setShowSecret(!showSecret)}
                            >
                              {showSecret ? (
                                <EyeOff className="w-4 h-4" />
                              ) : (
                                <Eye className="w-4 h-4" />
                              )}
                            </Button>
                          )}
                          {field.type === 'password' && (
                            <Button
                              type="button"
                              variant="ghost"
                              size="sm"
                              className="absolute right-10 top-1/2 -translate-y-1/2"
                              onClick={() => copyToClipboard(formField.value || '', field.name)}
                            >
                              {copiedField === field.name ? (
                                <Check className="w-4 h-4 text-green-500" />
                              ) : (
                                <Copy className="w-4 h-4" />
                              )}
                            </Button>
                          )}
                        </div>
                      </FormControl>
                      {field.description && (
                        <FormDescription>{field.description}</FormDescription>
                      )}
                      <FormMessage />
                    </FormItem>
                  )}
                />
              );
            case 'select':
              return (
                <FormField
                  key={field.name}
                  control={control}
                  name={field.name as any}
                  render={({ field: formField }) => (
                    <FormItem>
                      <FormLabel>
                        {field.label}
                        {field.required && <span className="text-destructive ml-1">*</span>}
                      </FormLabel>
                      <Select
                        disabled={readOnly}
                        onValueChange={formField.onChange}
                        defaultValue={formField.value}
                        value={formField.value}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder={`Sélectionnez ${field.label}`} />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {field.options?.map((option) => (
                            <SelectItem key={option.value} value={option.value}>
                              {option.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                      {field.description && (
                        <FormDescription>{field.description}</FormDescription>
                      )}
                      <FormMessage />
                    </FormItem>
                  )}
                />
              );
            case 'checkbox':
              return (
                <FormField
                  key={field.name}
                  control={control}
                  name={field.name as any}
                  render={({ field: formField }) => (
                    <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                      <div className="space-y-0.5">
                        <FormLabel>{field.label}</FormLabel>
                        {field.description && (
                          <FormDescription>{field.description}</FormDescription>
                        )}
                      </div>
                      <FormControl>
                        <Switch
                          checked={formField.value}
                          onCheckedChange={formField.onChange}
                          disabled={readOnly}
                        />
                      </FormControl>
                    </FormItem>
                  )}
                />
              );
            default:
              return null;
          }
        })}
      </div>
    );
  }, [selectedBrokerType, control, readOnly, showSecret, copiedField]);

  // ============================================================
  // RENDU PRINCIPAL
  // ============================================================

  if (isLoading && brokerId) {
    return (
      <div className="flex flex-col items-center justify-center p-12 space-y-4">
        <Loader2 className="w-8 h-8 animate-spin text-primary" />
        <p className="text-muted-foreground">Chargement du broker...</p>
      </div>
    );
  }

  const selectedBrokerInfo = SUPPORTED_BROKERS.find(b => b.value === selectedBrokerType);

  return (
    <>
      <Form {...form}>
        <form
          onSubmit={handleSubmit(onSubmit)}
          className={`broker-form space-y-6 ${className}`}
          noValidate
        >
          {/* ============================================================
              EN-TÊTE
          ============================================================ */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2">
                    <Building2 className="w-5 h-5" />
                    {brokerId ? 'Modifier le broker' : 'Ajouter un broker'}
                    {isDirty && (
                      <Badge variant="outline" className="text-yellow-500 border-yellow-500">
                        <Edit2 className="w-3 h-3 mr-1" />
                        Modifié
                      </Badge>
                    )}
                    {connectionStatus === 'connected' && (
                      <Badge variant="success">
                        <CheckCircle className="w-3 h-3 mr-1" />
                        Connecté
                      </Badge>
                    )}
                    {connectionStatus === 'error' && (
                      <Badge variant="destructive">
                        <XCircle className="w-3 h-3 mr-1" />
                        Erreur
                      </Badge>
                    )}
                    {connectionStatus === 'connecting' && (
                      <Badge variant="warning" className="animate-pulse">
                        <Loader2 className="w-3 h-3 mr-1 animate-spin" />
                        Test...
                      </Badge>
                    )}
                  </CardTitle>
                  <CardDescription>
                    {brokerId
                      ? 'Modifiez la configuration de votre broker'
                      : 'Configurez un nouveau broker pour l\'exécution des trades'}
                  </CardDescription>
                </div>
                {brokerId && (
                  <div className="flex items-center gap-2">
                    <TooltipProvider>
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={handleSync}
                            disabled={isLoading || connectionStatus === 'connecting'}
                          >
                            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
                          </Button>
                        </TooltipTrigger>
                        <TooltipContent>Synchroniser le broker</TooltipContent>
                      </Tooltip>
                    </TooltipProvider>
                    <Button
                      type="button"
                      variant="default"
                      size="sm"
                      onClick={handleTestConnection}
                      disabled={isTesting || connectionStatus === 'connecting'}
                      className="gap-2"
                    >
                      {isTesting ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Test...
                        </>
                      ) : (
                        <>
                          <Link2 className="w-4 h-4" />
                          Tester
                        </>
                      )}
                    </Button>
                  </div>
                )}
              </div>
            </CardHeader>

            <CardContent>
              {/* Message d'alerte si connexion impossible */}
              {connectionStatus === 'error' && testStatus && (
                <Alert variant="destructive" className="mb-4">
                  <AlertCircle className="w-4 h-4" />
                  <AlertTitle>Échec de connexion</AlertTitle>
                  <AlertDescription>
                    {testStatus.message || 'Impossible de se connecter au broker. Vérifiez vos credentials.'}
                  </AlertDescription>
                </Alert>
              )}

              {/* Sélection du broker */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <FormField
                  control={control}
                  name="brokerType"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Type de broker</FormLabel>
                      <Select
                        disabled={readOnly || !!brokerId}
                        onValueChange={field.onChange}
                        defaultValue={field.value}
                        value={field.value}
                      >
                        <FormControl>
                          <SelectTrigger>
                            <SelectValue placeholder="Sélectionnez un broker" />
                          </SelectTrigger>
                        </FormControl>
                        <SelectContent>
                          {SUPPORTED_BROKERS.map((broker) => {
                            const Icon = BROKER_ICONS[broker.value] || Building2;
                            return (
                              <SelectItem key={broker.value} value={broker.value}>
                                <div className="flex items-center gap-2">
                                  <Icon className="w-4 h-4" />
                                  <span>{broker.label}</span>
                                  <Badge variant="secondary" className="text-xs">
                                    {broker.category}
                                  </Badge>
                                </div>
                              </SelectItem>
                            );
                          })}
                        </SelectContent>
                      </Select>
                      <FormDescription>
                        Le type de broker détermine les paramètres de connexion
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />

                <FormField
                  control={control}
                  name="name"
                  render={({ field }) => (
                    <FormItem>
                      <FormLabel>Nom du broker</FormLabel>
                      <FormControl>
                        <Input
                          {...field}
                          placeholder="Ex: Binance Principal"
                          disabled={readOnly}
                          className="font-mono"
                        />
                      </FormControl>
                      <FormDescription>
                        Nom pour identifier ce broker
                      </FormDescription>
                      <FormMessage />
                    </FormItem>
                  )}
                />
              </div>

              <FormField
                control={control}
                name="description"
                render={({ field }) => (
                  <FormItem className="mt-4">
                    <FormLabel>Description</FormLabel>
                    <FormControl>
                      <Input
                        {...field}
                        placeholder="Description du broker..."
                        disabled={readOnly}
                      />
                    </FormControl>
                    <FormMessage />
                  </FormItem>
                )}
              />
            </CardContent>
          </Card>

          {/* ============================================================
              ONGLETS DE CONFIGURATION
          ============================================================ */}
          <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
            <TabsList className="grid w-full grid-cols-4">
              <TabsTrigger value="basic" className="gap-2">
                <Key className="w-4 h-4" />
                Credentials
              </TabsTrigger>
              <TabsTrigger value="advanced" className="gap-2">
                <Server className="w-4 h-4" />
                Avancé
              </TabsTrigger>
              <TabsTrigger value="security" className="gap-2">
                <Shield className="w-4 h-4" />
                Sécurité
              </TabsTrigger>
              <TabsTrigger value="monitoring" className="gap-2">
                <Database className="w-4 h-4" />
                Monitoring
              </TabsTrigger>
            </TabsList>

            {/* ============================================================
                ONGLET 1 : CREDENTIALS
            ============================================================ */}
            <TabsContent value="basic" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Credentials d'accès</CardTitle>
                  <CardDescription>
                    Configurez les clés API pour accéder au broker
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Champs spécifiques au broker */}
                  {renderBrokerFields()}

                  <Separator />

                  {/* Configuration de l'environnement */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <FormField
                      control={control}
                      name="environment"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Environnement</FormLabel>
                          <Select
                            disabled={readOnly}
                            onValueChange={field.onChange}
                            defaultValue={field.value}
                            value={field.value}
                          >
                            <FormControl>
                              <SelectTrigger>
                                <SelectValue placeholder="Sélectionnez un environnement" />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              <SelectItem value="SANDBOX">
                                <div className="flex items-center gap-2">
                                  <span>🧪</span>
                                  <span>Sandbox (Test)</span>
                                </div>
                              </SelectItem>
                              <SelectItem value="LIVE">
                                <div className="flex items-center gap-2">
                                  <span>🚀</span>
                                  <span>Live (Production)</span>
                                </div>
                              </SelectItem>
                            </SelectContent>
                          </Select>
                          <FormDescription>
                            Environnement de trading (test ou réel)
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={control}
                      name="accountType"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Type de compte</FormLabel>
                          <Select
                            disabled={readOnly}
                            onValueChange={field.onChange}
                            defaultValue={field.value}
                            value={field.value}
                          >
                            <FormControl>
                              <SelectTrigger>
                                <SelectValue placeholder="Sélectionnez un type" />
                              </SelectTrigger>
                            </FormControl>
                            <SelectContent>
                              <SelectItem value="SPOT">
                                <div className="flex items-center gap-2">
                                  <span>💱</span>
                                  <span>Spot</span>
                                </div>
                              </SelectItem>
                              <SelectItem value="MARGIN">
                                <div className="flex items-center gap-2">
                                  <span>📊</span>
                                  <span>Margin</span>
                                </div>
                              </SelectItem>
                              <SelectItem value="FUTURES">
                                <div className="flex items-center gap-2">
                                  <span>📈</span>
                                  <span>Futures</span>
                                </div>
                              </SelectItem>
                              <SelectItem value="OPTIONS">
                                <div className="flex items-center gap-2">
                                  <span>🎯</span>
                                  <span>Options</span>
                                </div>
                              </SelectItem>
                            </SelectContent>
                          </Select>
                          <FormDescription>
                            Type de compte à utiliser
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>

                  {/* URLs */}
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <FormField
                      control={control}
                      name="baseUrl"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>URL de base</FormLabel>
                          <FormControl>
                            <Input
                              {...field}
                              placeholder="https://api.broker.com"
                              disabled={readOnly}
                              className="font-mono text-sm"
                            />
                          </FormControl>
                          <FormDescription>
                            URL de l'API REST
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />

                    <FormField
                      control={control}
                      name="websocketUrl"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>URL WebSocket</FormLabel>
                          <FormControl>
                            <Input
                              {...field}
                              placeholder="wss://stream.broker.com"
                              disabled={readOnly}
                              className="font-mono text-sm"
                            />
                          </FormControl>
                          <FormDescription>
                            URL pour les données en temps réel
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* ============================================================
                ONGLET 2 : PARAMÈTRES AVANCÉS
            ============================================================ */}
            <TabsContent value="advanced" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Paramètres avancés</CardTitle>
                  <CardDescription>
                    Configuration avancée pour les cas d'usage spécifiques
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* Paramètres de retry */}
                  <div className="space-y-4">
                    <h4 className="text-sm font-medium">Politique de reprise</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <FormField
                        control={control}
                        name="maxRetries"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Nombre maximum de retries</FormLabel>
                            <FormControl>
                              <Input
                                {...field}
                                type="number"
                                min="0"
                                max="10"
                                disabled={readOnly}
                                onChange={(e) => {
                                  field.onChange(parseInt(e.target.value) || 0);
                                  setIsDirty(true);
                                }}
                              />
                            </FormControl>
                            <FormDescription>
                              Tentatives en cas d'échec
                            </FormDescription>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={control}
                        name="retryDelay"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Délai entre les retries (ms)</FormLabel>
                            <FormControl>
                              <Input
                                {...field}
                                type="number"
                                min="100"
                                max="10000"
                                step="100"
                                disabled={readOnly}
                                onChange={(e) => {
                                  field.onChange(parseInt(e.target.value) || 0);
                                  setIsDirty(true);
                                }}
                              />
                            </FormControl>
                            <FormDescription>
                              Temps d'attente entre deux tentatives
                            </FormDescription>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                  </div>

                  <Separator />

                  {/* Gestion des balances */}
                  <div className="space-y-4">
                    <h4 className="text-sm font-medium">Limites de balance</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <FormField
                        control={control}
                        name="minimumBalance"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Solde minimum</FormLabel>
                            <FormControl>
                              <div className="relative">
                                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                                  $
                                </span>
                                <Input
                                  {...field}
                                  type="number"
                                  step="1"
                                  min="0"
                                  className="pl-7"
                                  disabled={readOnly}
                                  onChange={(e) => {
                                    field.onChange(
                                      e.target.value ? parseFloat(e.target.value) : undefined
                                    );
                                    setIsDirty(true);
                                  }}
                                />
                              </div>
                            </FormControl>
                            <FormDescription>
                              Alerte si le solde descend en dessous
                            </FormDescription>
                            <FormMessage />
                          </FormItem>
                        )}
                      />

                      <FormField
                        control={control}
                        name="maximumBalance"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>Solde maximum</FormLabel>
                            <FormControl>
                              <div className="relative">
                                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground">
                                  $
                                </span>
                                <Input
                                  {...field}
                                  type="number"
                                  step="1"
                                  min="0"
                                  className="pl-7"
                                  disabled={readOnly}
                                  onChange={(e) => {
                                    field.onChange(
                                      e.target.value ? parseFloat(e.target.value) : undefined
                                    );
                                    setIsDirty(true);
                                  }}
                                />
                              </div>
                            </FormControl>
                            <FormDescription>
                              Alerte si le solde dépasse le seuil
                            </FormDescription>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </div>
                  </div>

                  <Separator />

                  {/* Cache */}
                  <div className="space-y-4">
                    <h4 className="text-sm font-medium">Cache</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <FormField
                        control={control}
                        name="enableCache"
                        render={({ field }) => (
                          <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                            <div className="space-y-0.5">
                              <FormLabel>Activer le cache</FormLabel>
                              <FormDescription>
                                Mettre en cache les données fréquentes
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

                      {watch('enableCache') && (
                        <FormField
                          control={control}
                          name="cacheTTL"
                          render={({ field }) => (
                            <FormItem>
                              <FormLabel>TTL du cache (secondes)</FormLabel>
                              <FormControl>
                                <Input
                                  {...field}
                                  type="number"
                                  min="1"
                                  max="3600"
                                  disabled={readOnly}
                                  onChange={(e) => {
                                    field.onChange(parseInt(e.target.value) || 0);
                                    setIsDirty(true);
                                  }}
                                />
                              </FormControl>
                              <FormDescription>
                                Durée de vie des données en cache
                              </FormDescription>
                              <FormMessage />
                            </FormItem>
                          )}
                        />
                      )}
                    </div>
                  </div>

                  <FormField
                    control={control}
                    name="rateLimit"
                    render={({ field }) => (
                      <FormItem>
                        <FormLabel>Limite de taux (requêtes/sec)</FormLabel>
                        <FormControl>
                          <Input
                            {...field}
                            type="number"
                            min="0"
                            max="1000"
                            placeholder="Auto"
                            disabled={readOnly}
                            onChange={(e) => {
                              field.onChange(
                                e.target.value ? parseInt(e.target.value) : undefined
                              );
                              setIsDirty(true);
                            }}
                          />
                        </FormControl>
                        <FormDescription>
                          Limiter le nombre de requêtes par seconde
                        </FormDescription>
                        <FormMessage />
                      </FormItem>
                    )}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            {/* ============================================================
                ONGLET 3 : SÉCURITÉ
            ============================================================ */}
            <TabsContent value="security" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Paramètres de sécurité</CardTitle>
                  <CardDescription>
                    Configurez les options de sécurité pour protéger votre compte
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {/* IP Whitelist */}
                  <FormField
                    control={control}
                    name="enableIpWhitelist"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel>Whitelist IP</FormLabel>
                          <FormDescription>
                            Restreindre l'accès à des IP spécifiques
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

                  {watch('enableIpWhitelist') && (
                    <FormField
                      control={control}
                      name="ipWhitelist"
                      render={({ field }) => (
                        <FormItem>
                          <FormLabel>Liste des IPs autorisées</FormLabel>
                          <FormControl>
                            <Input
                              {...field}
                              placeholder="192.168.1.1, 10.0.0.1/24"
                              disabled={readOnly}
                              className="font-mono text-sm"
                            />
                          </FormControl>
                          <FormDescription>
                            Séparées par des virgules ou espaces
                          </FormDescription>
                          <FormMessage />
                        </FormItem>
                      )}
                    />
                  )}

                  <Separator />

                  {/* Mode lecture seule */}
                  <FormField
                    control={control}
                    name="enableReadOnly"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel>Mode lecture seule</FormLabel>
                          <FormDescription>
                            Empêcher les modifications via ce broker
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

                  <Separator />

                  {/* Permissions */}
                  <div className="space-y-4">
                    <h4 className="text-sm font-medium">Permissions</h4>
                    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                      <FormField
                        control={control}
                        name="permissions.trading"
                        render={({ field }) => (
                          <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                            <div>
                              <FormLabel>Trading</FormLabel>
                              <FormDescription>Exécuter des trades</FormDescription>
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
                        name="permissions.deposits"
                        render={({ field }) => (
                          <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                            <div>
                              <FormLabel>Dépôts</FormLabel>
                              <FormDescription>Effectuer des dépôts</FormDescription>
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
                        name="permissions.withdrawals"
                        render={({ field }) => (
                          <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                            <div>
                              <FormLabel>Retraits</FormLabel>
                              <FormDescription>Effectuer des retraits</FormDescription>
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
                        name="permissions.history"
                        render={({ field }) => (
                          <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                            <div>
                              <FormLabel>Historique</FormLabel>
                              <FormDescription>Consulter l'historique</FormDescription>
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
                    </div>
                  </div>
                </CardContent>
              </Card>
            </TabsContent>

            {/* ============================================================
                ONGLET 4 : MONITORING
            ============================================================ */}
            <TabsContent value="monitoring" className="space-y-4">
              <Card>
                <CardHeader>
                  <CardTitle>Monitoring et alertes</CardTitle>
                  <CardDescription>
                    Configurez la surveillance du broker et les alertes
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <FormField
                    control={control}
                    name="enableMonitoring"
                    render={({ field }) => (
                      <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                        <div className="space-y-0.5">
                          <FormLabel>Activer le monitoring</FormLabel>
                          <FormDescription>
                            Surveiller l'état du broker en temps réel
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

                  {watch('enableMonitoring') && (
                    <>
                      <FormField
                        control={control}
                        name="alertOnError"
                        render={({ field }) => (
                          <FormItem className="flex flex-row items-center justify-between rounded-lg border p-3">
                            <div className="space-y-0.5">
                              <FormLabel>Alertes d'erreur</FormLabel>
                              <FormDescription>
                                Notifier en cas d'erreur critique
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
                        name="alertThreshold"
                        render={({ field }) => (
                          <FormItem>
                            <FormLabel>
                              Seuil d'alerte : {field.value}%
                            </FormLabel>
                            <FormControl>
                              <Slider
                                min={0.1}
                                max={10}
                                step={0.1}
                                value={[field.value]}
                                onValueChange={(value) => {
                                  field.onChange(value[0]);
                                  setIsDirty(true);
                                }}
                                disabled={readOnly}
                              />
                            </FormControl>
                            <FormDescription>
                              Pourcentage de variation déclenchant une alerte
                            </FormDescription>
                            <FormMessage />
                          </FormItem>
                        )}
                      />
                    </>
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
                {selectedBrokerInfo && (
                  <Badge variant="outline" className="text-xs">
                    <Globe className="w-3 h-3 mr-1" />
                    {selectedBrokerInfo.category}
                  </Badge>
                )}
              </div>
              <div className="flex items-center gap-2">
                {!brokerId && (
                  <Button
                    type="button"
                    variant="outline"
                    onClick={handleCancel}
                    disabled={isSaving}
                  >
                    Annuler
                  </Button>
                )}
                {!readOnly && (
                  <>
                    {brokerId && (
                      <Button
                        type="button"
                        variant="destructive"
                        size="sm"
                        onClick={async () => {
                          if (confirm('Supprimer ce broker ?')) {
                            try {
                              await deleteBroker(brokerId);
                              toast.success('Broker supprimé');
                              if (onCancel) onCancel();
                            } catch (error) {
                              toast.error('Erreur de suppression');
                            }
                          }
                        }}
                        disabled={isSaving}
                      >
                        <Trash2 className="w-4 h-4 mr-2" />
                        Supprimer
                      </Button>
                    )}
                    <Button
                      type="submit"
                      disabled={!isValid || isSaving}
                    >
                      {isSaving ? (
                        <>
                          <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                          Sauvegarde...
                        </>
                      ) : (
                        <>
                          <Save className="w-4 h-4 mr-2" />
                          {brokerId ? 'Mettre à jour' : 'Ajouter'}
                        </>
                      )}
                    </Button>
                  </>
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
            <DialogTitle>Modifications non sauvegardées</DialogTitle>
            <DialogDescription>
              Vous avez des modifications non sauvegardées. Voulez-vous vraiment quitter ?
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowConfirmDialog(false)}>
              Continuer l'édition
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                setShowConfirmDialog(false);
                reset();
                if (onCancel) onCancel();
              }}
            >
              Quitter sans sauvegarder
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
export default BrokerForm;

// ============================================================
// TYPES & UTILITAIRES (exportés pour réutilisation)
// ============================================================
export type { BrokerFormProps, BrokerFormValues };
export { brokerSchema };

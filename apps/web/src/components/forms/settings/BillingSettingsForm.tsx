// apps/web/src/components/forms/settings/BillingSettingsForm.tsx
'use client';

import React, {
  useState,
  useCallback,
  useRef,
  useEffect,
  forwardRef,
  Ref,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CreditCardIcon,
  BanknotesIcon,
  WalletIcon,
  CurrencyDollarIcon,
  PlusIcon,
  MinusIcon,
  CheckIcon,
  XMarkIcon,
  ArrowPathIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  EyeIcon,
  EyeSlashIcon,
  PencilIcon,
  TrashIcon,
  DocumentDuplicateIcon,
  ShareIcon,
  LinkIcon,
  BookmarkIcon,
  HeartIcon,
  StarIcon,
  FlagIcon,
  PrinterIcon,
  EnvelopeIcon,
  ClipboardIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  GlobeAltIcon,
  SparklesIcon,
  RocketLaunchIcon,
  ShieldCheckIcon,
  Cog6ToothIcon,
  CalendarIcon,
  ClockIcon,
  DocumentTextIcon,
  ReceiptPercentIcon,
  BuildingOfficeIcon,
  UserIcon,
  PhoneIcon,
  MapPinIcon,
} from '@heroicons/react/24/outline';
import {
  CheckCircleIcon as CheckCircleSolid,
  ExclamationCircleIcon as ExclamationCircleSolid,
} from '@heroicons/react/24/solid';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Select } from '@/components/common/Select';
import { Switch } from '@/components/common/Switch';
import { Tabs, TabsList, TabsTrigger, TabsContent } from '@/components/common/Tabs';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '@/components/common/Card';
import { Badge } from '@/components/common/Badge';
import { Separator } from '@/components/common/Separator';
import { Progress } from '@/components/common/Progress';
import { Tooltip } from '@/components/common/Tooltip';
import { ScrollArea } from '@/components/common/ScrollArea';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type BillingPlan = 'free' | 'basic' | 'pro' | 'enterprise' | 'custom';
export type BillingPeriod = 'monthly' | 'yearly' | 'lifetime';
export type PaymentMethod = 'card' | 'paypal' | 'crypto' | 'bank_transfer' | 'invoice';
export type InvoiceStatus = 'paid' | 'pending' | 'overdue' | 'cancelled' | 'refunded';
export type BillingStatus = 'active' | 'inactive' | 'past_due' | 'cancelled' | 'trialing';

export interface BillingAddress {
  /** Ligne d'adresse 1 */
  line1: string;
  /** Ligne d'adresse 2 */
  line2?: string;
  /** Ville */
  city: string;
  /** État/Région */
  state?: string;
  /** Code postal */
  postalCode: string;
  /** Pays */
  country: string;
}

export interface PaymentMethodConfig {
  /** Identifiant */
  id: string;
  /** Type de méthode */
  type: PaymentMethod;
  /** Nom de la méthode */
  name: string;
  /** Derniers chiffres */
  last4?: string;
  /** Date d'expiration */
  expiryDate?: string;
  /** Marque de la carte */
  brand?: string;
  /** Est-ce que la méthode est par défaut */
  isDefault: boolean;
  /** Est-ce que la méthode est active */
  isActive: boolean;
}

export interface Invoice {
  /** Numéro de facture */
  number: string;
  /** Date de la facture */
  date: Date;
  /** Date d'échéance */
  dueDate: Date;
  /** Montant */
  amount: number;
  /** Devise */
  currency: string;
  /** Statut */
  status: InvoiceStatus;
  /** Description */
  description: string;
  /** URL de la facture */
  url?: string;
}

export interface BillingSettingsData {
  /** Plan actuel */
  plan: BillingPlan;
  /** Période de facturation */
  period: BillingPeriod;
  /** Statut de facturation */
  status: BillingStatus;
  /** Prochaine facturation */
  nextBillingDate?: Date;
  /** Date de début du plan */
  startDate?: Date;
  /** Date de fin du plan */
  endDate?: Date;
  /** Méthodes de paiement */
  paymentMethods: PaymentMethodConfig[];
  /** Adresse de facturation */
  billingAddress: BillingAddress;
  /** Factures */
  invoices: Invoice[];
  /** Devise par défaut */
  defaultCurrency: string;
  /** Email de facturation */
  billingEmail: string;
  /** Nom de la société */
  companyName?: string;
  /** Numéro de TVA */
  vatNumber?: string;
  /** SIRET */
  siret?: string;
  /** Réduction (pourcentage) */
  discount?: number;
  /** Code promo */
  promoCode?: string;
  /** Est-ce que l'auto-renouvellement est activé */
  autoRenew: boolean;
  /** Est-ce que les emails de facturation sont activés */
  billingEmailsEnabled: boolean;
  /** Est-ce que le mode test est activé */
  testMode: boolean;
}

export interface BillingSettingsFormProps {
  // --- Contrôle ---
  /** Données initiales */
  initialData?: Partial<BillingSettingsData>;
  /** Callback de soumission */
  onSubmit?: (data: BillingSettingsData) => void | Promise<void>;
  /** Callback de succès */
  onSuccess?: (data: BillingSettingsData) => void;
  /** Callback d'erreur */
  onError?: (error: string) => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de changement */
  onChange?: (data: BillingSettingsData) => void;

  // --- Apparence ---
  /** Titre du formulaire */
  title?: string;
  /** Sous-titre */
  subtitle?: string;
  /** Classes additionnelles */
  className?: string;
  /** Variante de la carte */
  variant?: 'default' | 'glass' | 'solid' | 'outlined';

  // --- États ---
  /** État de chargement */
  isLoading?: boolean;
  /** État d'erreur */
  error?: string | null;
  /** Message de succès */
  success?: string | null;
  /** Désactiver le formulaire */
  disabled?: boolean;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ID */
  id?: string;

  // --- Avancé ---
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const PLANS: Record<BillingPlan, { label: string; price: number; currency: string; features: string[]; color: string }> = {
  free: {
    label: 'Gratuit',
    price: 0,
    currency: '€',
    features: ['1 projet', '10 requêtes/jour', 'Support communautaire'],
    color: 'text-gray-500',
  },
  basic: {
    label: 'Basique',
    price: 29,
    currency: '€',
    features: ['5 projets', '100 requêtes/jour', 'Support email', 'API de base'],
    color: 'text-blue-500',
  },
  pro: {
    label: 'Pro',
    price: 99,
    currency: '€',
    features: ['Projets illimités', '1000 requêtes/jour', 'Support prioritaire', 'API complète', 'Analytique avancée'],
    color: 'text-purple-500',
  },
  enterprise: {
    label: 'Entreprise',
    price: 299,
    currency: '€',
    features: ['Projets illimités', 'Requêtes illimitées', 'Support dédié', 'API complète', 'Analytique avancée', 'SLA 99.9%'],
    color: 'text-brand-500',
  },
  custom: {
    label: 'Personnalisé',
    price: 0,
    currency: '€',
    features: ['Sur mesure', 'Contactez-nous'],
    color: 'text-gray-500',
  },
};

const PERIODS: { value: BillingPeriod; label: string; discount: number }[] = [
  { value: 'monthly', label: 'Mensuel', discount: 0 },
  { value: 'yearly', label: 'Annuel', discount: 20 },
  { value: 'lifetime', label: 'À vie', discount: 40 },
];

const PAYMENT_METHOD_TYPES: { value: PaymentMethod; label: string; icon: React.ReactNode }[] = [
  { value: 'card', label: 'Carte bancaire', icon: <CreditCardIcon className="h-4 w-4" /> },
  { value: 'paypal', label: 'PayPal', icon: <BanknotesIcon className="h-4 w-4" /> },
  { value: 'crypto', label: 'Crypto-monnaie', icon: <CurrencyDollarIcon className="h-4 w-4" /> },
  { value: 'bank_transfer', label: 'Virement bancaire', icon: <BuildingOfficeIcon className="h-4 w-4" /> },
  { value: 'invoice', label: 'Facture', icon: <DocumentTextIcon className="h-4 w-4" /> },
];

const INVOICE_STATUS_MAP: Record<InvoiceStatus, { color: string; label: string; icon: React.ReactNode }> = {
  paid: {
    color: 'text-green-500',
    label: 'Payée',
    icon: <CheckCircleIcon className="h-4 w-4" />,
  },
  pending: {
    color: 'text-yellow-500',
    label: 'En attente',
    icon: <ClockIcon className="h-4 w-4" />,
  },
  overdue: {
    color: 'text-red-500',
    label: 'En retard',
    icon: <ExclamationCircleIcon className="h-4 w-4" />,
  },
  cancelled: {
    color: 'text-gray-400',
    label: 'Annulée',
    icon: <XMarkIcon className="h-4 w-4" />,
  },
  refunded: {
    color: 'text-blue-500',
    label: 'Remboursée',
    icon: <ArrowPathIcon className="h-4 w-4" />,
  },
};

const CURRENCIES = [
  { value: 'EUR', label: '€ Euro' },
  { value: 'USD', label: '$ Dollar US' },
  { value: 'GBP', label: '£ Livre Sterling' },
  { value: 'CHF', label: 'Fr Franc Suisse' },
  { value: 'CAD', label: 'C$ Dollar Canadien' },
  { value: 'JPY', label: '¥ Yen Japonais' },
];

const COUNTRIES = [
  { value: 'FR', label: 'France' },
  { value: 'BE', label: 'Belgique' },
  { value: 'CH', label: 'Suisse' },
  { value: 'CA', label: 'Canada' },
  { value: 'US', label: 'États-Unis' },
  { value: 'GB', label: 'Royaume-Uni' },
  { value: 'DE', label: 'Allemagne' },
  { value: 'ES', label: 'Espagne' },
  { value: 'IT', label: 'Italie' },
  { value: 'NL', label: 'Pays-Bas' },
  { value: 'LU', label: 'Luxembourg' },
  { value: 'PT', label: 'Portugal' },
];

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const BillingSettingsForm = forwardRef<HTMLDivElement, BillingSettingsFormProps>(
  (props, ref) => {
    const {
      // Contrôle
      initialData = {},
      onSubmit,
      onSuccess,
      onError,
      onCancel,
      onChange,

      // Apparence
      title = 'Facturation',
      subtitle = 'Gérez vos informations de facturation et vos paiements',
      className,
      variant = 'default',

      // États
      isLoading = false,
      error = null,
      success = null,
      disabled = false,

      // Accessibilité
      ariaLabel = 'Paramètres de facturation',
      id,

      // Avancé
      debug = false,
    } = props;

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const formRef = useRef<HTMLFormElement>(null);

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [formData, setFormData] = useState<BillingSettingsData>({
      plan: 'free',
      period: 'monthly',
      status: 'active',
      paymentMethods: [],
      billingAddress: {
        line1: '',
        city: '',
        postalCode: '',
        country: 'FR',
      },
      invoices: [],
      defaultCurrency: 'EUR',
      billingEmail: '',
      autoRenew: true,
      billingEmailsEnabled: true,
      testMode: false,
      ...initialData,
    });

    const [isSubmitting, setIsSubmitting] = useState(false);
    const [formErrors, setFormErrors] = useState<Record<string, string>>({});
    const [activeTab, setActiveTab] = useState<'overview' | 'payment' | 'address' | 'invoices'>('overview');
    const [isAddingPayment, setIsAddingPayment] = useState(false);
    const [newPaymentMethod, setNewPaymentMethod] = useState<Partial<PaymentMethodConfig>>({
      type: 'card',
      isDefault: false,
      isActive: true,
    });
    const [selectedPlan, setSelectedPlan] = useState<BillingPlan>(formData.plan);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const currentPlan = PLANS[formData.plan] || PLANS.free;
    const currentPeriod = PERIODS.find(p => p.value === formData.period) || PERIODS[0];
    const monthlyPrice = currentPlan.price;
    const yearlyPrice = monthlyPrice * 12 * (1 - (currentPeriod.discount / 100));
    const totalPrice = formData.period === 'yearly' ? yearlyPrice : monthlyPrice;
    const discountAmount = formData.period === 'yearly' ? monthlyPrice * 12 - yearlyPrice : 0;

    // ========================================================================
    // VALIDATION
    // ========================================================================

    const validate = useCallback((): boolean => {
      const errors: Record<string, string> = {};

      if (!formData.billingEmail) {
        errors.billingEmail = 'L\'email de facturation est requis';
      }

      if (!formData.billingAddress.line1) {
        errors.billingAddressLine1 = 'L\'adresse est requise';
      }

      if (!formData.billingAddress.city) {
        errors.billingAddressCity = 'La ville est requise';
      }

      if (!formData.billingAddress.postalCode) {
        errors.billingAddressPostalCode = 'Le code postal est requis';
      }

      setFormErrors(errors);
      return Object.keys(errors).length === 0;
    }, [formData]);

    // ========================================================================
    // GESTIONNAIRES DE CHAMPS
    // ========================================================================

    const handleFieldChange = useCallback(<K extends keyof BillingSettingsData>(
      field: K,
      value: BillingSettingsData[K]
    ) => {
      setFormData(prev => ({ ...prev, [field]: value }));
      setFormErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[field];
        return newErrors;
      });
    }, []);

    const handleAddressChange = useCallback(<K extends keyof BillingAddress>(
      field: K,
      value: BillingAddress[K]
    ) => {
      setFormData(prev => ({
        ...prev,
        billingAddress: { ...prev.billingAddress, [field]: value },
      }));
      setFormErrors(prev => {
        const newErrors = { ...prev };
        delete newErrors[`billingAddress${field.charAt(0).toUpperCase() + field.slice(1)}`];
        return newErrors;
      });
    }, []);

    // ========================================================================
    // GESTION DES MÉTHODES DE PAIEMENT
    // ========================================================================

    const handleAddPaymentMethod = useCallback(() => {
      if (!newPaymentMethod.type) {
        toast({
          title: 'Erreur',
          description: 'Veuillez sélectionner un type de paiement',
          variant: 'destructive',
        });
        return;
      }

      const newMethod: PaymentMethodConfig = {
        id: `pm_${Date.now()}`,
        type: newPaymentMethod.type,
        name: PAYMENT_METHOD_TYPES.find(p => p.value === newPaymentMethod.type)?.label || 'Carte',
        isDefault: newPaymentMethod.isDefault || false,
        isActive: true,
        last4: newPaymentMethod.last4,
        expiryDate: newPaymentMethod.expiryDate,
        brand: newPaymentMethod.brand,
      };

      setFormData(prev => ({
        ...prev,
        paymentMethods: [...prev.paymentMethods, newMethod],
      }));

      setNewPaymentMethod({ type: 'card', isDefault: false, isActive: true });
      setIsAddingPayment(false);

      toast({
        title: 'Méthode ajoutée',
        description: 'La méthode de paiement a été ajoutée avec succès',
        duration: 2000,
      });
    }, [newPaymentMethod, toast]);

    const handleRemovePaymentMethod = useCallback((id: string) => {
      setFormData(prev => ({
        ...prev,
        paymentMethods: prev.paymentMethods.filter(m => m.id !== id),
      }));

      toast({
        title: 'Méthode supprimée',
        description: 'La méthode de paiement a été supprimée',
        duration: 2000,
      });
    }, [toast]);

    const handleSetDefaultPayment = useCallback((id: string) => {
      setFormData(prev => ({
        ...prev,
        paymentMethods: prev.paymentMethods.map(m => ({
          ...m,
          isDefault: m.id === id,
        })),
      }));

      toast({
        title: 'Méthode par défaut',
        description: 'La méthode de paiement par défaut a été mise à jour',
        duration: 2000,
      });
    }, [toast]);

    // ========================================================================
    // GESTION DES ABONNEMENTS
    // ========================================================================

    const handleChangePlan = useCallback((plan: BillingPlan) => {
      setSelectedPlan(plan);
      handleFieldChange('plan', plan);

      toast({
        title: 'Plan changé',
        description: `Vous êtes maintenant sur le plan ${PLANS[plan].label}`,
        duration: 3000,
      });
    }, [handleFieldChange, toast]);

    const handleChangePeriod = useCallback((period: BillingPeriod) => {
      handleFieldChange('period', period);
    }, [handleFieldChange]);

    const handleCancelSubscription = useCallback(() => {
      if (confirm('Êtes-vous sûr de vouloir annuler votre abonnement ?')) {
        handleFieldChange('status', 'cancelled');
        handleFieldChange('autoRenew', false);

        toast({
          title: 'Abonnement annulé',
          description: 'Votre abonnement a été annulé avec succès',
          duration: 3000,
        });
      }
    }, [handleFieldChange, toast]);

    // ========================================================================
    // SOUMISSION
    // ========================================================================

    const handleSubmit = useCallback(async (e: React.FormEvent) => {
      e.preventDefault();

      if (isSubmitting || isLoading || disabled) return;

      if (!validate()) {
        toast({
          title: 'Erreur de validation',
          description: 'Veuillez corriger les erreurs du formulaire',
          variant: 'destructive',
        });
        return;
      }

      setIsSubmitting(true);

      try {
        if (onSubmit) {
          await onSubmit(formData);
        }

        if (onSuccess) onSuccess(formData);

        toast({
          title: 'Configuration sauvegardée',
          description: 'Les paramètres de facturation ont été mis à jour',
          variant: 'success',
        });

        if (debug) {
          console.log('Billing settings saved:', formData);
        }

      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Erreur de sauvegarde';
        if (onError) onError(errorMessage);
        toast({
          title: 'Erreur',
          description: errorMessage,
          variant: 'destructive',
        });
        if (debug) console.error('Erreur de sauvegarde:', err);
      } finally {
        setIsSubmitting(false);
      }
    }, [isSubmitting, isLoading, disabled, formData, validate, onSubmit, onSuccess, onError, toast, debug]);

    // ========================================================================
    // NOTIFICATION DES CHANGEMENTS
    // ========================================================================

    useEffect(() => {
      if (onChange) {
        onChange(formData);
      }
    }, [formData, onChange]);

    // ========================================================================
    // RENDU DE L'APERÇU DU PLAN
    // ========================================================================

    const renderPlanOverview = () => (
      <div className="space-y-6">
        {/* Plan actuel */}
        <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4">
          <div className="flex items-center justify-between">
            <div>
              <h3 className="font-semibold text-gray-900 dark:text-white">
                Plan {currentPlan.label}
              </h3>
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {formData.period === 'yearly' ? 'Facturation annuelle' : 'Facturation mensuelle'}
              </p>
            </div>
            <div className="text-right">
              <span className="text-2xl font-bold text-gray-900 dark:text-white">
                {currentPlan.price > 0 ? `${currentPlan.currency}${currentPlan.price}` : 'Gratuit'}
              </span>
              {currentPlan.price > 0 && (
                <span className="text-sm text-gray-500 dark:text-gray-400">
                  /{formData.period === 'yearly' ? 'an' : 'mois'}
                </span>
              )}
            </div>
          </div>

          {formData.period === 'yearly' && currentPlan.price > 0 && (
            <div className="mt-2 text-sm text-green-600 dark:text-green-400">
              Économisez {discountAmount.toFixed(2)}€ avec la facturation annuelle
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            {currentPlan.features.map((feature, index) => (
              <Badge key={index} variant="outline" size="sm" className="flex items-center gap-1">
                <CheckIcon className="h-3 w-3 text-green-500" />
                {feature}
              </Badge>
            ))}
          </div>

          <div className="mt-4 flex items-center gap-3">
            <Badge
              variant={
                formData.status === 'active' ? 'success' :
                formData.status === 'past_due' ? 'warning' :
                formData.status === 'cancelled' ? 'danger' :
                formData.status === 'trialing' ? 'info' :
                'default'
              }
              className="capitalize"
            >
              {formData.status === 'active' ? 'Actif' :
               formData.status === 'past_due' ? 'En retard' :
               formData.status === 'cancelled' ? 'Annulé' :
               formData.status === 'trialing' ? 'Période d\'essai' :
               'Inactif'}
            </Badge>
            {formData.nextBillingDate && (
              <span className="text-sm text-gray-500 dark:text-gray-400">
                Prochaine facturation: {formData.nextBillingDate.toLocaleDateString()}
              </span>
            )}
          </div>
        </div>

        {/* Changer de plan */}
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Changer de plan
          </h4>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {Object.entries(PLANS).map(([key, plan]) => {
              const isActive = formData.plan === key;
              return (
                <button
                  key={key}
                  type="button"
                  className={cn(
                    'rounded-lg border-2 p-4 text-left transition-all',
                    isActive
                      ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                      : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                  )}
                  onClick={() => handleChangePlan(key as BillingPlan)}
                  disabled={disabled || isSubmitting || isLoading}
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{plan.label}</span>
                    {isActive && (
                      <Badge variant="success" size="xs">Actuel</Badge>
                    )}
                  </div>
                  <p className="text-sm text-gray-500 dark:text-gray-400">
                    {plan.price > 0 ? `${plan.currency}${plan.price}` : 'Gratuit'}
                    {formData.period === 'yearly' && plan.price > 0 && ' / an'}
                  </p>
                  <div className="mt-1 text-xs text-gray-400">
                    {plan.features.slice(0, 2).join(' • ')}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Période de facturation */}
        <div className="space-y-2">
          <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
            Période de facturation
          </label>
          <div className="flex gap-2">
            {PERIODS.map((period) => (
              <button
                key={period.value}
                type="button"
                className={cn(
                  'flex-1 rounded-lg border-2 p-3 text-center transition-all',
                  formData.period === period.value
                    ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                    : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                )}
                onClick={() => handleChangePeriod(period.value)}
                disabled={disabled || isSubmitting || isLoading}
              >
                <span className="font-medium">{period.label}</span>
                {period.discount > 0 && (
                  <Badge variant="success" size="xs" className="ml-1">
                    -{period.discount}%
                  </Badge>
                )}
              </button>
            ))}
          </div>
        </div>

        {/* Actions */}
        <div className="flex flex-wrap gap-3">
          {formData.status !== 'cancelled' && (
            <Button
              type="button"
              variant="danger"
              size="sm"
              onClick={handleCancelSubscription}
              disabled={disabled || isSubmitting || isLoading}
            >
              Annuler l'abonnement
            </Button>
          )}
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              handleFieldChange('testMode', !formData.testMode);
              toast({
                title: formData.testMode ? 'Mode test désactivé' : 'Mode test activé',
                description: formData.testMode 
                  ? 'Les transactions seront désormais réelles' 
                  : 'Les transactions seront simulées pour les tests',
                duration: 3000,
              });
            }}
            disabled={disabled || isSubmitting || isLoading}
          >
            {formData.testMode ? 'Désactiver le mode test' : 'Activer le mode test'}
          </Button>
        </div>
      </div>
    );

    // ========================================================================
    // RENDU DES MÉTHODES DE PAIEMENT
    // ========================================================================

    const renderPaymentMethods = () => (
      <div className="space-y-6">
        {/* Méthodes existantes */}
        {formData.paymentMethods.length > 0 && (
          <div className="space-y-2">
            {formData.paymentMethods.map((method) => (
              <div
                key={method.id}
                className={cn(
                  'flex items-center gap-3 rounded-lg border p-3',
                  method.isDefault ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20' : 'border-gray-200 dark:border-gray-700'
                )}
              >
                <div className="flex-shrink-0">
                  {PAYMENT_METHOD_TYPES.find(p => p.value === method.type)?.icon || <CreditCardIcon className="h-5 w-5" />}
                </div>
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium">{method.name}</span>
                    {method.isDefault && (
                      <Badge variant="primary" size="xs">Par défaut</Badge>
                    )}
                    {!method.isActive && (
                      <Badge variant="outline" size="xs">Inactif</Badge>
                    )}
                  </div>
                  {method.last4 && (
                    <p className="text-sm text-gray-500 dark:text-gray-400">
                      •••• {method.last4}
                      {method.expiryDate && ` • Expire ${method.expiryDate}`}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-1">
                  {!method.isDefault && method.isActive && (
                    <Tooltip content="Définir par défaut">
                      <button
                        type="button"
                        className="rounded p-1 text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                        onClick={() => handleSetDefaultPayment(method.id)}
                      >
                        <CheckIcon className="h-4 w-4" />
                      </button>
                    </Tooltip>
                  )}
                  <Tooltip content="Supprimer">
                    <button
                      type="button"
                      className="rounded p-1 text-gray-400 hover:text-red-600 hover:bg-red-50 dark:hover:bg-red-900/20 transition-colors"
                      onClick={() => handleRemovePaymentMethod(method.id)}
                    >
                      <TrashIcon className="h-4 w-4" />
                    </button>
                  </Tooltip>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Ajouter une méthode */}
        {isAddingPayment ? (
          <div className="rounded-lg border border-gray-200 dark:border-gray-700 p-4 space-y-4">
            <div className="flex items-center justify-between">
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300">
                Ajouter une méthode de paiement
              </h4>
              <button
                type="button"
                className="text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                onClick={() => {
                  setIsAddingPayment(false);
                  setNewPaymentMethod({ type: 'card', isDefault: false, isActive: true });
                }}
              >
                <XMarkIcon className="h-4 w-4" />
              </button>
            </div>

            <div className="space-y-3">
              <div className="space-y-2">
                <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                  Type de paiement
                </label>
                <div className="flex flex-wrap gap-2">
                  {PAYMENT_METHOD_TYPES.map((type) => (
                    <button
                      key={type.value}
                      type="button"
                      className={cn(
                        'flex items-center gap-2 rounded-lg border-2 px-3 py-2 transition-all',
                        newPaymentMethod.type === type.value
                          ? 'border-brand-500 bg-brand-50 dark:bg-brand-900/20'
                          : 'border-gray-200 dark:border-gray-700 hover:border-gray-300 dark:hover:border-gray-600'
                      )}
                      onClick={() => setNewPaymentMethod({ ...newPaymentMethod, type: type.value })}
                    >
                      {type.icon}
                      <span className="text-sm">{type.label}</span>
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Nom
                  </label>
                  <Input
                    type="text"
                    placeholder="Ma carte"
                    value={newPaymentMethod.name || ''}
                    onChange={(e) => setNewPaymentMethod({ ...newPaymentMethod, name: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                    Définir par défaut
                  </label>
                  <div className="pt-2">
                    <Switch
                      checked={newPaymentMethod.isDefault || false}
                      onCheckedChange={(checked) => setNewPaymentMethod({ ...newPaymentMethod, isDefault: checked })}
                    />
                  </div>
                </div>
              </div>

              {(newPaymentMethod.type === 'card') && (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Derniers chiffres
                    </label>
                    <Input
                      type="text"
                      placeholder="4242"
                      maxLength={4}
                      value={newPaymentMethod.last4 || ''}
                      onChange={(e) => setNewPaymentMethod({ ...newPaymentMethod, last4: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
                      Date d'expiration
                    </label>
                    <Input
                      type="text"
                      placeholder="MM/YY"
                      value={newPaymentMethod.expiryDate || ''}
                      onChange={(e) => setNewPaymentMethod({ ...newPaymentMethod, expiryDate: e.target.value })}
                    />
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2">
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={() => {
                  setIsAddingPayment(false);
                  setNewPaymentMethod({ type: 'card', isDefault: false, isActive: true });
                }}
              >
                Annuler
              </Button>
              <Button
                type="button"
                variant="primary"
                size="sm"
                onClick={handleAddPaymentMethod}
              >
                Ajouter
              </Button>
            </div>
          </div>
        ) : (
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => setIsAddingPayment(true)}
            disabled={disabled || isSubmitting || isLoading}
          >
            <PlusIcon className="h-4 w-4 mr-2" />
            Ajouter une méthode de paiement
          </Button>
        )}
      </div>
    );

    // ========================================================================
    // RENDU DE L'ADRESSE DE FACTURATION
    // ========================================================================

    const renderBillingAddress = () => (
      <div className="space-y-4">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Adresse ligne 1
            </label>
            <Input
              type="text"
              placeholder="123 Rue de la Paix"
              value={formData.billingAddress.line1}
              onChange={(e) => handleAddressChange('line1', e.target.value)}
              error={formErrors.billingAddressLine1}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Adresse ligne 2
            </label>
            <Input
              type="text"
              placeholder="Appartement 4B"
              value={formData.billingAddress.line2 || ''}
              onChange={(e) => handleAddressChange('line2', e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Ville
            </label>
            <Input
              type="text"
              placeholder="Paris"
              value={formData.billingAddress.city}
              onChange={(e) => handleAddressChange('city', e.target.value)}
              error={formErrors.billingAddressCity}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              État/Région
            </label>
            <Input
              type="text"
              placeholder="Île-de-France"
              value={formData.billingAddress.state || ''}
              onChange={(e) => handleAddressChange('state', e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Code postal
            </label>
            <Input
              type="text"
              placeholder="75001"
              value={formData.billingAddress.postalCode}
              onChange={(e) => handleAddressChange('postalCode', e.target.value)}
              error={formErrors.billingAddressPostalCode}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Pays
            </label>
            <Select
              options={COUNTRIES}
              value={formData.billingAddress.country}
              onChange={(value) => handleAddressChange('country', value)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <Separator />

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Email de facturation
            </label>
            <Input
              type="email"
              placeholder="facturation@exemple.com"
              value={formData.billingEmail}
              onChange={(e) => handleFieldChange('billingEmail', e.target.value)}
              error={formErrors.billingEmail}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Devise par défaut
            </label>
            <Select
              options={CURRENCIES}
              value={formData.defaultCurrency}
              onChange={(value) => handleFieldChange('defaultCurrency', value)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Société
            </label>
            <Input
              type="text"
              placeholder="Nexus Trading IA"
              value={formData.companyName || ''}
              onChange={(e) => handleFieldChange('companyName', e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
          <div className="space-y-2">
            <label className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Numéro de TVA
            </label>
            <Input
              type="text"
              placeholder="FR123456789"
              value={formData.vatNumber || ''}
              onChange={(e) => handleFieldChange('vatNumber', e.target.value)}
              disabled={disabled || isSubmitting || isLoading}
            />
          </div>
        </div>

        <div className="flex items-center justify-between">
          <div>
            <p className="text-sm font-medium text-gray-700 dark:text-gray-300">
              Emails de facturation
            </p>
            <p className="text-xs text-gray-500 dark:text-gray-400">
              Recevoir les factures par email
            </p>
          </div>
          <Switch
            checked={formData.billingEmailsEnabled}
            onCheckedChange={(checked) => handleFieldChange('billingEmailsEnabled', checked)}
            disabled={disabled || isSubmitting || isLoading}
          />
        </div>
      </div>
    );

    // ========================================================================
    // RENDU DES FACTURES
    // ========================================================================

    const renderInvoices = () => (
      <div className="space-y-4">
        {formData.invoices.length === 0 ? (
          <div className="rounded-lg border-2 border-dashed border-gray-300 dark:border-gray-600 p-8 text-center">
            <DocumentTextIcon className="mx-auto h-12 w-12 text-gray-400" />
            <p className="mt-2 text-sm text-gray-500 dark:text-gray-400">
              Aucune facture disponible
            </p>
            <p className="text-xs text-gray-400 dark:text-gray-500">
              Les factures apparaîtront ici après vos premiers paiements
            </p>
          </div>
        ) : (
          <ScrollArea className="max-h-96">
            <div className="space-y-2">
              {formData.invoices.map((invoice) => {
                const statusInfo = INVOICE_STATUS_MAP[invoice.status] || INVOICE_STATUS_MAP.paid;
                return (
                  <div
                    key={invoice.number}
                    className="flex items-center gap-3 rounded-lg border border-gray-200 dark:border-gray-700 p-3"
                  >
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-mono font-medium">{invoice.number}</span>
                        <span className={cn('flex items-center gap-1 text-xs', statusInfo.color)}>
                          {statusInfo.icon}
                          {statusInfo.label}
                        </span>
                      </div>
                      <p className="text-sm text-gray-500 dark:text-gray-400">
                        {invoice.description}
                      </p>
                      <div className="flex items-center gap-3 text-xs text-gray-400">
                        <span>{invoice.date.toLocaleDateString()}</span>
                        <span>Échéance: {invoice.dueDate.toLocaleDateString()}</span>
                      </div>
                    </div>
                    <div className="text-right">
                      <p className="font-semibold text-gray-900 dark:text-white">
                        {invoice.currency} {invoice.amount.toFixed(2)}
                      </p>
                      {invoice.url && (
                        <button
                          type="button"
                          className="text-xs text-brand-600 hover:text-brand-700 dark:text-brand-400 dark:hover:text-brand-300"
                          onClick={() => window.open(invoice.url, '_blank')}
                        >
                          Voir la facture
                        </button>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        )}

        <div className="flex justify-end">
          <Button
            type="button"
            variant="outline"
            size="sm"
            onClick={() => {
              toast({
                title: 'Export en cours',
                description: 'Le téléchargement des factures va commencer',
                duration: 3000,
              });
            }}
            disabled={disabled || isSubmitting || isLoading}
          >
            <DocumentDuplicateIcon className="h-4 w-4 mr-2" />
            Exporter toutes les factures
          </Button>
        </div>
      </div>
    );

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const hasError = !!error || Object.keys(formErrors).length > 0;

    return (
      <Card
        ref={ref}
        id={id}
        className={cn(
          'w-full max-w-4xl mx-auto overflow-hidden',
          variant === 'glass' && 'bg-white/80 backdrop-blur-xl dark:bg-gray-900/80',
          variant === 'solid' && 'bg-white dark:bg-gray-900',
          variant === 'outlined' && 'border-2 border-gray-200 dark:border-gray-700 bg-transparent',
          className
        )}
        aria-label={ariaLabel}
      >
        {/* Header */}
        <CardHeader className="border-b border-gray-200 dark:border-gray-700">
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="flex items-center gap-2">
                {title}
                <Badge variant="outline" size="sm" className="flex items-center gap-1">
                  <CurrencyDollarIcon className="h-3 w-3" />
                  {formData.status === 'active' ? 'Actif' : 'Inactif'}
                </Badge>
              </CardTitle>
              {subtitle && (
                <p className="text-sm text-gray-500 dark:text-gray-400">{subtitle}</p>
              )}
            </div>
            {onCancel && (
              <Button
                type="button"
                variant="ghost"
                size="sm"
                onClick={onCancel}
                disabled={isSubmitting || isLoading}
              >
                Annuler
              </Button>
            )}
          </div>
        </CardHeader>

        {/* Tabs */}
        <div className="border-b border-gray-200 dark:border-gray-700">
          <div className="flex overflow-x-auto">
            {[
              { id: 'overview', label: '📊 Aperçu' },
              { id: 'payment', label: '💳 Paiement' },
              { id: 'address', label: '📍 Adresse' },
              { id: 'invoices', label: '📄 Factures' },
            ].map((tab) => (
              <button
                key={tab.id}
                type="button"
                className={cn(
                  'px-4 py-2.5 text-sm font-medium transition-colors whitespace-nowrap border-b-2',
                  activeTab === tab.id
                    ? 'border-brand-500 text-brand-600 dark:text-brand-400'
                    : 'border-transparent text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                )}
                onClick={() => setActiveTab(tab.id as any)}
                disabled={disabled || isSubmitting || isLoading}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>

        {/* Contenu */}
        <CardContent className="p-6">
          <form ref={formRef} onSubmit={handleSubmit} noValidate>
            {/* Erreur globale */}
            {hasError && error && (
              <div className="mb-4 flex items-start gap-2 rounded-lg bg-red-50 dark:bg-red-900/20 p-3 text-sm text-red-600 dark:text-red-400">
                <ExclamationCircleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />
                <span>{error}</span>
              </div>
            )}

            {/* Succès */}
            {success && (
              <div className="mb-4 flex items-start gap-2 rounded-lg bg-green-50 dark:bg-green-900/20 p-3 text-sm text-green-600 dark:text-green-400">
                <CheckCircleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />
                <span>{success}</span>
              </div>
            )}

            {/* Contenu de l'onglet */}
            <AnimatePresence mode="wait">
              <motion.div
                key={activeTab}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                transition={{ duration: 0.2 }}
              >
                {activeTab === 'overview' && renderPlanOverview()}
                {activeTab === 'payment' && renderPaymentMethods()}
                {activeTab === 'address' && renderBillingAddress()}
                {activeTab === 'invoices' && renderInvoices()}
              </motion.div>
            </AnimatePresence>

            {/* Actions */}
            <div className="mt-6 flex items-center justify-end gap-3 pt-6 border-t border-gray-200 dark:border-gray-700">
              <Button
                type="submit"
                variant="primary"
                onClick={handleSubmit}
                disabled={disabled || isSubmitting || isLoading}
                isLoading={isSubmitting || isLoading}
              >
                {isSubmitting ? 'Sauvegarde...' : 'Sauvegarder'}
              </Button>
            </div>
          </form>
        </CardContent>

        {/* Footer */}
        <CardFooter className="border-t border-gray-200 dark:border-gray-700 px-4 py-2 text-xs text-gray-400">
          <div className="flex items-center justify-between w-full">
            <span>
              Plan: {currentPlan.label} • {formData.period === 'yearly' ? 'Annuel' : 'Mensuel'}
            </span>
            <span>
              {formData.paymentMethods.length} méthodes de paiement
            </span>
          </div>
        </CardFooter>
      </Card>
    );
  }
);

BillingSettingsForm.displayName = 'BillingSettingsForm';

// ============================================================================
// EXPORTS
// ============================================================================

export default BillingSettingsForm;

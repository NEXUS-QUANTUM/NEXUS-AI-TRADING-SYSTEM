// apps/web/src/components/forms/layouts/FormTabsLayout.tsx
'use client';

import React, {
  ReactNode,
  forwardRef,
  Ref,
  useState,
  useCallback,
  useEffect,
  useRef,
  Children,
  isValidElement,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  ChevronDownIcon,
  ChevronUpIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  CheckIcon,
  ExclamationTriangleIcon,
  InformationCircleIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
  Cog6ToothIcon,
  AdjustmentsHorizontalIcon,
  Squares2X2Icon,
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
  PlusIcon,
  MinusIcon,
  ArrowLeftIcon,
  ArrowRightIcon,
} from '@heroicons/react/24/outline';
import { Button } from '@/components/common/Button';
import { Badge } from '@/components/common/Badge';
import { Separator } from '@/components/common/Separator';
import { Progress } from '@/components/common/Progress';
import { Tooltip } from '@/components/common/Tooltip';
import { ScrollArea } from '@/components/common/ScrollArea';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type FormTab = {
  /** Identifiant de l'onglet */
  id: string;
  /** Libellé de l'onglet */
  label: string;
  /** Icône de l'onglet */
  icon?: React.ReactNode;
  /** Contenu de l'onglet */
  content: ReactNode;
  /** Badge de l'onglet */
  badge?: string | number;
  /** Statut de l'onglet */
  status?: 'idle' | 'valid' | 'invalid' | 'warning' | 'info';
  /** Désactiver l'onglet */
  disabled?: boolean;
  /** Afficher l'onglet */
  visible?: boolean;
  /** Classe additionnelle */
  className?: string;
};

export type FormTabsVariant = 'default' | 'pills' | 'underlined' | 'outlined' | 'minimal' | 'cards';
export type FormTabsSize = 'sm' | 'md' | 'lg' | 'xl';
export type FormTabsAlignment = 'left' | 'center' | 'right' | 'between';
export type FormTabsPosition = 'top' | 'bottom' | 'left' | 'right';
export type FormTabsStatus = 'idle' | 'loading' | 'success' | 'error' | 'warning' | 'info';
export type FormTabsAnimation = 'fade' | 'slide' | 'scale' | 'none';

export interface FormTabsLayoutProps {
  // --- Contrôle ---
  /** Onglets du formulaire */
  tabs: FormTab[];
  /** Onglet actif (contrôlé) */
  activeTab?: string;
  /** Onglet actif par défaut */
  defaultActiveTab?: string;
  /** Callback de changement d'onglet */
  onTabChange?: (tabId: string) => void;

  // --- Apparence ---
  /** Variante des onglets */
  variant?: FormTabsVariant;
  /** Taille des onglets */
  size?: FormTabsSize;
  /** Alignement des onglets */
  alignment?: FormTabsAlignment;
  /** Position des onglets */
  position?: FormTabsPosition;
  /** Statut des onglets */
  status?: FormTabsStatus;
  /** Animation de transition */
  animation?: FormTabsAnimation;
  /** Afficher les badges de statut */
  showStatusBadges?: boolean;
  /** Afficher les icônes */
  showIcons?: boolean;
  /** Afficher la barre de progression */
  showProgress?: boolean;
  /** Afficher les séparateurs */
  showSeparators?: boolean;
  /** Afficher le compteur d'onglets */
  showTabCount?: boolean;
  /** Classes additionnelles */
  className?: string;
  /** Classe pour la liste des onglets */
  tabsClassName?: string;
  /** Classe pour le contenu */
  contentClassName?: string;
  /** Classe pour les onglets individuels */
  tabClassName?: string;
  /** Classe pour l'onglet actif */
  activeTabClassName?: string;

  // --- Comportement ---
  /** Désactiver les onglets */
  disabled?: boolean;
  /** État de chargement */
  isLoading?: boolean;
  /** Message d'erreur */
  error?: string | null;
  /** Message de succès */
  success?: string | null;
  /** Message d'information */
  info?: string | null;
  /** Message d'avertissement */
  warning?: string | null;
  /** Progression (0-100) */
  progress?: number;
  /** Désactiver la fermeture des onglets */
  disableClose?: boolean;
  /** Désactiver l'ajout d'onglets */
  disableAdd?: boolean;
  /** Désactiver la réorganisation */
  disableReorder?: boolean;
  /** Nombre maximal d'onglets */
  maxTabs?: number;

  // --- Actions ---
  /** Callback de soumission */
  onSubmit?: () => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de réinitialisation */
  onReset?: () => void;
  /** Callback de validation d'onglet */
  onTabValidate?: (tabId: string) => boolean | Promise<boolean>;
  /** Callback d'ajout d'onglet */
  onTabAdd?: () => void;
  /** Callback de fermeture d'onglet */
  onTabClose?: (tabId: string) => void;
  /** Callback de réorganisation */
  onTabReorder?: (tabs: FormTab[]) => void;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ID */
  id?: string;

  // --- Avancé ---
  /** Désactiver les animations */
  disableAnimations?: boolean;
  /** Mode débogage */
  debug?: boolean;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const VARIANT_MAP: Record<FormTabsVariant, string> = {
  default: 'border-b border-gray-200 dark:border-gray-700',
  pills: 'space-x-1',
  underlined: 'border-b-2 border-gray-200 dark:border-gray-700',
  outlined: 'border border-gray-200 dark:border-gray-700 rounded-lg p-1',
  minimal: 'border-b border-gray-200 dark:border-gray-700',
  cards: 'space-x-2',
};

const TAB_VARIANT_MAP: Record<FormTabsVariant, string> = {
  default: 'border-b-2 border-transparent rounded-t-lg px-4 py-2',
  pills: 'rounded-full px-4 py-2',
  underlined: 'border-b-2 border-transparent px-4 py-2',
  outlined: 'rounded-md px-4 py-2',
  minimal: 'border-b-2 border-transparent px-3 py-1.5',
  cards: 'rounded-lg px-4 py-2 shadow-sm',
};

const ACTIVE_TAB_VARIANT_MAP: Record<FormTabsVariant, string> = {
  default: 'border-brand-500 text-brand-600 dark:text-brand-400',
  pills: 'bg-brand-500 text-white dark:bg-brand-600',
  underlined: 'border-brand-500 text-brand-600 dark:text-brand-400',
  outlined: 'bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-400 border-brand-500',
  minimal: 'border-brand-500 text-brand-600 dark:text-brand-400',
  cards: 'bg-brand-500 text-white dark:bg-brand-600 shadow-md',
};

const SIZE_MAP: Record<FormTabsSize, { padding: string; fontSize: string; gap: string }> = {
  sm: { padding: 'px-3 py-1.5', fontSize: 'text-xs', gap: 'gap-1' },
  md: { padding: 'px-4 py-2', fontSize: 'text-sm', gap: 'gap-2' },
  lg: { padding: 'px-6 py-2.5', fontSize: 'text-base', gap: 'gap-3' },
  xl: { padding: 'px-8 py-3', fontSize: 'text-lg', gap: 'gap-4' },
};

const ALIGNMENT_MAP: Record<FormTabsAlignment, string> = {
  left: 'justify-start',
  center: 'justify-center',
  right: 'justify-end',
  between: 'justify-between',
};

const STATUS_MAP: Record<FormTabsStatus, { color: string; icon: React.ReactNode }> = {
  idle: {
    color: 'text-gray-500 dark:text-gray-400',
    icon: <InformationCircleIcon className="h-5 w-5" />,
  },
  loading: {
    color: 'text-brand-500',
    icon: <ArrowPathIcon className="h-5 w-5 animate-spin" />,
  },
  success: {
    color: 'text-green-500',
    icon: <CheckCircleIcon className="h-5 w-5" />,
  },
  error: {
    color: 'text-red-500',
    icon: <ExclamationCircleIcon className="h-5 w-5" />,
  },
  warning: {
    color: 'text-yellow-500',
    icon: <ExclamationTriangleIcon className="h-5 w-5" />,
  },
  info: {
    color: 'text-blue-500',
    icon: <InformationCircleIcon className="h-5 w-5" />,
  },
};

const STATUS_TAB_MAP: Record<NonNullable<FormTab['status']>, { color: string; icon: React.ReactNode }> = {
  idle: {
    color: 'text-gray-400 dark:text-gray-500',
    icon: <InformationCircleIcon className="h-4 w-4" />,
  },
  valid: {
    color: 'text-green-500',
    icon: <CheckCircleIcon className="h-4 w-4" />,
  },
  invalid: {
    color: 'text-red-500',
    icon: <ExclamationCircleIcon className="h-4 w-4" />,
  },
  warning: {
    color: 'text-yellow-500',
    icon: <ExclamationTriangleIcon className="h-4 w-4" />,
  },
  info: {
    color: 'text-blue-500',
    icon: <InformationCircleIcon className="h-4 w-4" />,
  },
};

const ANIMATION_MAP: Record<FormTabsAnimation, {
  initial: { opacity?: number; x?: string | number; y?: string | number; scale?: number };
  animate: { opacity?: number; x?: string | number; y?: string | number; scale?: number };
  exit: { opacity?: number; x?: string | number; y?: string | number; scale?: number };
}> = {
  fade: {
    initial: { opacity: 0 },
    animate: { opacity: 1 },
    exit: { opacity: 0 },
  },
  slide: {
    initial: { opacity: 0, x: 20 },
    animate: { opacity: 1, x: 0 },
    exit: { opacity: 0, x: -20 },
  },
  scale: {
    initial: { opacity: 0, scale: 0.95 },
    animate: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.95 },
  },
  none: {
    initial: { opacity: 1 },
    animate: { opacity: 1 },
    exit: { opacity: 1 },
  },
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const FormTabsLayout = forwardRef<HTMLDivElement, FormTabsLayoutProps>(
  (props, ref) => {
    const {
      // Contrôle
      tabs,
      activeTab: externalActiveTab,
      defaultActiveTab,
      onTabChange,

      // Apparence
      variant = 'default',
      size = 'md',
      alignment = 'left',
      position = 'top',
      status = 'idle',
      animation = 'fade',
      showStatusBadges = true,
      showIcons = true,
      showProgress = false,
      showSeparators = true,
      showTabCount = true,
      className,
      tabsClassName,
      contentClassName,
      tabClassName,
      activeTabClassName,

      // Comportement
      disabled = false,
      isLoading = false,
      error = null,
      success = null,
      info = null,
      warning = null,
      progress = 0,
      disableClose = false,
      disableAdd = false,
      disableReorder = false,
      maxTabs,

      // Actions
      onSubmit,
      onCancel,
      onReset,
      onTabValidate,
      onTabAdd,
      onTabClose,
      onTabReorder,

      // Accessibilité
      ariaLabel = 'Onglets du formulaire',
      id,

      // Avancé
      disableAnimations = false,
      debug = false,
    } = props;

    // ========================================================================
    // TOAST
    // ========================================================================

    const { toast } = useToast();

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const containerRef = useRef<HTMLDivElement>(null);
    const tabsRef = useRef<HTMLDivElement>(null);
    const dragRef = useRef<{ startX: number; index: number } | null>(null);

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalActiveTab, setInternalActiveTab] = useState<string>(
      defaultActiveTab || (tabs.length > 0 ? tabs[0].id : '')
    );
    const [localTabs, setLocalTabs] = useState<FormTab[]>(tabs);
    const [isDragging, setIsDragging] = useState(false);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const activeTab = externalActiveTab !== undefined ? externalActiveTab : internalActiveTab;
    const isControlled = externalActiveTab !== undefined;

    const activeTabIndex = localTabs.findIndex(t => t.id === activeTab);
    const currentTab = localTabs[activeTabIndex];
    const visibleTabs = localTabs.filter(t => t.visible !== false);

    const sizeStyles = SIZE_MAP[size] || SIZE_MAP.md;
    const variantStyles = VARIANT_MAP[variant] || VARIANT_MAP.default;
    const tabVariantStyles = TAB_VARIANT_MAP[variant] || TAB_VARIANT_MAP.default;
    const activeVariantStyles = ACTIVE_TAB_VARIANT_MAP[variant] || ACTIVE_TAB_VARIANT_MAP.default;
    const alignmentStyles = ALIGNMENT_MAP[alignment] || ALIGNMENT_MAP.left;
    const statusMap = STATUS_MAP[status] || STATUS_MAP.idle;
    const animationStyles = ANIMATION_MAP[animation] || ANIMATION_MAP.fade;

    const hasStatusMessage = error || success || info || warning;
    const statusMessage = error || success || info || warning;
    const statusType = error ? 'error' : success ? 'success' : warning ? 'warning' : info ? 'info' : null;
    const statusColor = statusType ? STATUS_MAP[statusType as FormTabsStatus]?.color : statusMap.color;

    const hasTabs = localTabs.length > 0;
    const isVertical = position === 'left' || position === 'right';

    // ========================================================================
    // GESTION DE L'ONGLET ACTIF
    // ========================================================================

    const setActiveTab = useCallback((tabId: string) => {
      if (isControlled) {
        if (onTabChange) onTabChange(tabId);
      } else {
        setInternalActiveTab(tabId);
        if (onTabChange) onTabChange(tabId);
      }
    }, [isControlled, onTabChange]);

    const handleTabClick = useCallback((tabId: string) => {
      const tab = localTabs.find(t => t.id === tabId);
      if (tab?.disabled || disabled) return;
      setActiveTab(tabId);
    }, [localTabs, disabled, setActiveTab]);

    // ========================================================================
    // VALIDATION D'ONGLET
    // ========================================================================

    const validateCurrentTab = useCallback(async (): Promise<boolean> => {
      if (!onTabValidate || !currentTab) return true;

      try {
        const result = await onTabValidate(currentTab.id);
        if (!result) {
          toast({
            title: 'Erreur de validation',
            description: `L'onglet "${currentTab.label}" contient des erreurs`,
            variant: 'destructive',
          });
        }
        return result;
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : 'Erreur de validation';
        toast({
          title: 'Erreur',
          description: errorMessage,
          variant: 'destructive',
        });
        return false;
      }
    }, [currentTab, onTabValidate, toast]);

    // ========================================================================
    // NAVIGATION ENTRE ONGLETS
    // ========================================================================

    const goToPreviousTab = useCallback(async () => {
      if (activeTabIndex <= 0) return;

      // Valider l'onglet courant avant de changer
      const isValid = await validateCurrentTab();
      if (!isValid) return;

      const prevTab = localTabs[activeTabIndex - 1];
      if (prevTab && !prevTab.disabled) {
        setActiveTab(prevTab.id);
      }
    }, [activeTabIndex, localTabs, validateCurrentTab, setActiveTab]);

    const goToNextTab = useCallback(async () => {
      if (activeTabIndex >= localTabs.length - 1) return;

      // Valider l'onglet courant avant de changer
      const isValid = await validateCurrentTab();
      if (!isValid) return;

      const nextTab = localTabs[activeTabIndex + 1];
      if (nextTab && !nextTab.disabled) {
        setActiveTab(nextTab.id);
      }
    }, [activeTabIndex, localTabs, validateCurrentTab, setActiveTab]);

    // ========================================================================
    // GESTION DES ONGLETS
    // ========================================================================

    const handleAddTab = useCallback(() => {
      if (disableAdd) return;
      if (maxTabs && localTabs.length >= maxTabs) {
        toast({
          title: 'Limite atteinte',
          description: `Nombre maximal d'onglets: ${maxTabs}`,
          variant: 'destructive',
        });
        return;
      }
      if (onTabAdd) onTabAdd();
    }, [disableAdd, maxTabs, localTabs.length, onTabAdd, toast]);

    const handleCloseTab = useCallback((tabId: string) => {
      if (disableClose) return;
      if (onTabClose) onTabClose(tabId);

      // Si l'onglet fermé est l'onglet actif, passer au suivant ou précédent
      if (tabId === activeTab) {
        const tabIndex = localTabs.findIndex(t => t.id === tabId);
        const nextTab = localTabs[tabIndex + 1] || localTabs[tabIndex - 1];
        if (nextTab) setActiveTab(nextTab.id);
      }

      setLocalTabs(prev => prev.filter(t => t.id !== tabId));
    }, [disableClose, onTabClose, activeTab, localTabs, setActiveTab]);

    // ========================================================================
    // DRAG & DROP (réorganisation)
    // ========================================================================

    const handleDragStart = useCallback((e: React.MouseEvent, index: number) => {
      if (disableReorder) return;
      dragRef.current = { startX: e.clientX, index };
      setIsDragging(true);
    }, [disableReorder]);

    const handleDragMove = useCallback((e: React.MouseEvent) => {
      if (!dragRef.current || !isDragging) return;

      const { startX, index } = dragRef.current;
      const deltaX = e.clientX - startX;
      const threshold = 50;

      if (Math.abs(deltaX) > threshold) {
        const direction = deltaX > 0 ? 1 : -1;
        const newIndex = Math.max(0, Math.min(localTabs.length - 1, index + direction));

        if (newIndex !== index) {
          const newTabs = [...localTabs];
          const [removed] = newTabs.splice(index, 1);
          newTabs.splice(newIndex, 0, removed);
          setLocalTabs(newTabs);
          if (onTabReorder) onTabReorder(newTabs);
          dragRef.current = { startX: e.clientX, index: newIndex };
        }
      }
    }, [isDragging, localTabs, onTabReorder]);

    const handleDragEnd = useCallback(() => {
      dragRef.current = null;
      setIsDragging(false);
    }, []);

    // ========================================================================
    // SYNCHRONISATION AVEC LES PROPS
    // ========================================================================

    useEffect(() => {
      setLocalTabs(tabs);
    }, [tabs]);

    // ========================================================================
    // GESTIONNAIRES
    // ========================================================================

    const handleSubmit = useCallback(() => {
      if (disabled || isLoading) return;
      if (onSubmit) onSubmit();
    }, [disabled, isLoading, onSubmit]);

    const handleCancel = useCallback(() => {
      if (disabled || isLoading) return;
      if (onCancel) onCancel();
    }, [disabled, isLoading, onCancel]);

    const handleReset = useCallback(() => {
      if (disabled || isLoading) return;
      if (onReset) onReset();
    }, [disabled, isLoading, onReset]);

    // ========================================================================
    // RENDU DU STATUT GLOBAL
    // ========================================================================

    const renderStatus = () => {
      if (!hasStatusMessage) return null;

      return (
        <div
          className={cn(
            'flex items-start gap-2 rounded-lg p-3 text-sm',
            error && 'bg-red-50 dark:bg-red-900/20 text-red-600 dark:text-red-400',
            success && 'bg-green-50 dark:bg-green-900/20 text-green-600 dark:text-green-400',
            warning && 'bg-yellow-50 dark:bg-yellow-900/20 text-yellow-600 dark:text-yellow-400',
            info && 'bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400'
          )}
        >
          {error && <ExclamationCircleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />}
          {success && <CheckCircleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />}
          {warning && <ExclamationTriangleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />}
          {info && <InformationCircleIcon className="h-5 w-5 flex-shrink-0 mt-0.5" />}
          <span>{statusMessage}</span>
        </div>
      );
    };

    // ========================================================================
    // RENDU DE LA BARRE DE PROGRESSION
    // ========================================================================

    const renderProgress = () => {
      if (!showProgress) return null;

      return (
        <div className="mb-4">
          <Progress
            value={progress}
            className="h-1.5"
            variant={
              progress >= 100 ? 'success' :
              progress >= 70 ? 'info' :
              progress >= 30 ? 'warning' :
              'default'
            }
          />
          <div className="mt-1 flex justify-between text-xs text-gray-500 dark:text-gray-400">
            <span>Progression</span>
            <span>{Math.round(progress)}%</span>
          </div>
        </div>
      );
    };

    // ========================================================================
    // RENDU DE LA NAVIGATION
    // ========================================================================

    const renderNavigation = () => {
      const isHorizontal = position === 'top' || position === 'bottom';

      return (
        <div
          ref={tabsRef}
          className={cn(
            'relative',
            variantStyles,
            isHorizontal ? 'flex' : 'flex-col',
            alignmentStyles,
            showSeparators && 'border-gray-200 dark:border-gray-700',
            tabsClassName
          )}
          role="tablist"
          aria-label={ariaLabel}
        >
          {visibleTabs.map((tab, index) => {
            const isActive = tab.id === activeTab;
            const isDisabled = tab.disabled || disabled;
            const tabStatus = tab.status || 'idle';
            const statusStyles = STATUS_TAB_MAP[tabStatus];

            return (
              <button
                key={tab.id}
                type="button"
                className={cn(
                  'relative flex items-center gap-2 transition-all',
                  tabVariantStyles,
                  sizeStyles.padding,
                  sizeStyles.fontSize,
                  isActive ? activeVariantStyles : 'text-gray-600 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-200',
                  isDisabled && 'opacity-50 cursor-not-allowed',
                  variant === 'pills' && !isActive && 'hover:bg-gray-100 dark:hover:bg-gray-800',
                  variant === 'cards' && !isActive && 'border border-gray-200 dark:border-gray-700 hover:bg-gray-50 dark:hover:bg-gray-800',
                  isActive && activeTabClassName,
                  tabClassName
                )}
                onClick={() => handleTabClick(tab.id)}
                onMouseDown={(e) => {
                  if (disableReorder) return;
                  const target = e.currentTarget;
                  const rect = target.getBoundingClientRect();
                  handleDragStart(e, index);
                }}
                onMouseMove={handleDragMove}
                onMouseUp={handleDragEnd}
                onMouseLeave={handleDragEnd}
                disabled={isDisabled}
                role="tab"
                aria-selected={isActive}
                aria-controls={`tab-panel-${tab.id}`}
                id={`tab-${tab.id}`}
                tabIndex={isActive ? 0 : -1}
              >
                {/* Icône */}
                {showIcons && tab.icon && (
                  <span className={cn(
                    'flex-shrink-0',
                    isActive ? 'text-brand-500' : 'text-gray-400'
                  )}>
                    {tab.icon}
                  </span>
                )}

                {/* Label */}
                <span>{tab.label}</span>

                {/* Badge */}
                {tab.badge && (
                  <Badge variant="outline" size="xs" className="ml-1">
                    {tab.badge}
                  </Badge>
                )}

                {/* Statut d'onglet */}
                {showStatusBadges && tab.status && tab.status !== 'idle' && (
                  <span className={cn('flex-shrink-0', statusStyles.color)}>
                    {statusStyles.icon}
                  </span>
                )}

                {/* Bouton de fermeture */}
                {!disableClose && !isDisabled && (
                  <button
                    type="button"
                    className="ml-1 rounded-full p-0.5 hover:bg-gray-200 dark:hover:bg-gray-700 transition-colors"
                    onClick={(e) => {
                      e.stopPropagation();
                      handleCloseTab(tab.id);
                    }}
                    aria-label={`Fermer l'onglet ${tab.label}`}
                  >
                    <XMarkIcon className="h-3 w-3" />
                  </button>
                )}
              </button>
            );
          })}

          {/* Bouton d'ajout */}
          {!disableAdd && !disabled && (
            <button
              type="button"
              className={cn(
                'flex items-center justify-center rounded-lg transition-colors',
                sizeStyles.padding,
                sizeStyles.fontSize,
                'text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800'
              )}
              onClick={handleAddTab}
              aria-label="Ajouter un onglet"
            >
              <PlusIcon className="h-4 w-4" />
            </button>
          )}

          {/* Compteur */}
          {showTabCount && (
            <span className="ml-auto text-xs text-gray-400">
              {visibleTabs.length} {visibleTabs.length > 1 ? 'onglets' : 'onglet'}
            </span>
          )}
        </div>
      );
    };

    // ========================================================================
    // RENDU DU CONTENU
    // ========================================================================

    const renderContent = () => {
      if (isLoading) {
        return (
          <div className="flex flex-col items-center justify-center py-12">
            <ArrowPathIcon className="h-8 w-8 animate-spin text-brand-500" />
            <p className="mt-3 text-sm text-gray-500 dark:text-gray-400">
              Chargement...
            </p>
          </div>
        );
      }

      if (!hasTabs) {
        return (
          <div className="flex flex-col items-center justify-center py-12 text-gray-400">
            <InformationCircleIcon className="h-12 w-12" />
            <p className="mt-3 text-sm">Aucun onglet disponible</p>
          </div>
        );
      }

      if (!currentTab) {
        return (
          <div className="flex flex-col items-center justify-center py-12 text-gray-400">
            <ExclamationTriangleIcon className="h-12 w-12" />
            <p className="mt-3 text-sm">Onglet sélectionné non trouvé</p>
          </div>
        );
      }

      return (
        <AnimatePresence mode="wait">
          <motion.div
            key={activeTab}
            initial={!disableAnimations ? animationStyles.initial : {}}
            animate={!disableAnimations ? animationStyles.animate : {}}
            exit={!disableAnimations ? animationStyles.exit : {}}
            transition={{ duration: 0.2 }}
            className="flex-1"
          >
            {currentTab.content}
          </motion.div>
        </AnimatePresence>
      );
    };

    // ========================================================================
    // RENDU DES ACTIONS
    // ========================================================================

    const renderActions = () => {
      const showActions = onSubmit || onCancel || onReset;

      if (!showActions) return null;

      return (
        <div className="flex flex-wrap items-center justify-end gap-3 pt-4">
          {onReset && (
            <Button
              type="button"
              variant="ghost"
              size="sm"
              onClick={handleReset}
              disabled={disabled || isLoading}
            >
              Réinitialiser
            </Button>
          )}
          {onCancel && (
            <Button
              type="button"
              variant="ghost"
              onClick={handleCancel}
              disabled={disabled || isLoading}
            >
              Annuler
            </Button>
          )}
          {onSubmit && (
            <Button
              type="submit"
              variant="primary"
              onClick={handleSubmit}
              disabled={disabled || isLoading}
              isLoading={isLoading}
            >
              {isLoading ? 'Envoi...' : 'Soumettre'}
            </Button>
          )}
        </div>
      );
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    const isTop = position === 'top';
    const isBottom = position === 'bottom';
    const isLeft = position === 'left';
    const isRight = position === 'right';

    const layoutClasses = cn(
      'flex',
      isVertical ? 'flex-row' : 'flex-col',
      isVertical && 'gap-4',
      !isVertical && 'gap-4',
      className
    );

    const navClasses = cn(
      isVertical ? 'flex-shrink-0' : 'w-full',
      isLeft && 'order-1',
      isRight && 'order-3',
      isTop && 'order-1',
      isBottom && 'order-3'
    );

    const contentClasses = cn(
      'flex-1 min-w-0',
      isVertical ? 'order-2' : 'order-2',
      contentClassName
    );

    return (
      <div
        ref={ref}
        id={id}
        className={cn(
          'relative rounded-xl border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 p-4',
          className
        )}
        aria-label={ariaLabel}
      >
        {/* Progression */}
        {renderProgress()}

        {/* Statut */}
        {renderStatus()}

        <div className={layoutClasses}>
          {/* Navigation */}
          <div className={navClasses}>
            {renderNavigation()}
          </div>

          {/* Contenu */}
          <div className={contentClasses}>
            {renderContent()}
          </div>
        </div>

        {/* Actions */}
        {renderActions()}
      </div>
    );
  }
);

FormTabsLayout.displayName = 'FormTabsLayout';

// ============================================================================
// SOUS-COMPOSANTS
// ============================================================================

// --- FormTabsLayout.Tab ---
interface FormTabProps extends FormTab {
  children?: ReactNode;
}

export const FormTab: React.FC<FormTabProps> = ({
  id,
  label,
  icon,
  content,
  badge,
  status,
  disabled,
  visible,
  className,
  children,
}) => {
  return (
    <div
      className={cn('hidden', className)}
      role="tabpanel"
      id={`tab-panel-${id}`}
      aria-labelledby={`tab-${id}`}
    >
      {content || children}
    </div>
  );
};

// --- FormTabsLayout.Panel ---
interface FormTabPanelProps {
  children: ReactNode;
  className?: string;
}

export const FormTabPanel: React.FC<FormTabPanelProps> = ({
  children,
  className,
}) => {
  return (
    <div className={cn('p-4', className)}>
      {children}
    </div>
  );
};

// ============================================================================
// EXPORTS
// ============================================================================

export default Object.assign(FormTabsLayout, {
  Tab: FormTab,
  Panel: FormTabPanel,
});

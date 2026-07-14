// apps/web/src/components/forms/layouts/FormSidebarLayout.tsx
'use client';

import React, {
  ReactNode,
  forwardRef,
  Ref,
  useState,
  useCallback,
  useEffect,
  useRef,
} from 'react';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import {
  XMarkIcon,
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
  MaximizeIcon,
  MinimizeIcon,
  PanelLeftIcon,
  PanelRightIcon,
  PanelTopIcon,
  PanelBottomIcon,
  HomeIcon,
  UserIcon,
  SettingsIcon,
  ChartBarIcon,
  ChartPieIcon,
  DocumentTextIcon,
  FolderIcon,
  FolderOpenIcon,
  ArchiveIcon,
  TagIcon,
  HashtagIcon,
} from '@heroicons/react/24/outline';
import { Button } from '@/components/common/Button';
import { Badge } from '@/components/common/Badge';
import { Separator } from '@/components/common/Separator';
import { Progress } from '@/components/common/Progress';
import { Tooltip } from '@/components/common/Tooltip';
import { ScrollArea } from '@/components/common/ScrollArea';
import { Portal } from '@/components/common/Portal';
import { useToast } from '@/hooks/useToast';

// ============================================================================
// TYPES
// ============================================================================

export type FormSidebarSize = 'sm' | 'md' | 'lg' | 'xl' | 'full' | 'auto';
export type FormSidebarVariant = 'default' | 'glass' | 'solid' | 'outlined';
export type FormSidebarStatus = 'idle' | 'loading' | 'success' | 'error' | 'warning' | 'info';
export type FormSidebarAnimation = 'slide' | 'fade' | 'scale' | 'bounce' | 'none';
export type FormSidebarBackdrop = 'none' | 'blur' | 'dark' | 'blur-dark' | 'transparent';
export type FormSidebarMode = 'overlay' | 'push' | 'inline' | 'float';
export type FormSidebarPosition = 'left' | 'right';
export type FormSidebarItem = {
  /** Identifiant de l'élément */
  id: string;
  /** Libellé de l'élément */
  label: string;
  /** Icône de l'élément */
  icon?: React.ReactNode;
  /** Contenu de l'élément */
  content: ReactNode;
  /** Badge de l'élément */
  badge?: string | number;
  /** Statut de l'élément */
  status?: FormSidebarStatus;
  /** Désactiver l'élément */
  disabled?: boolean;
  /** Sous-éléments */
  items?: FormSidebarItem[];
  /** Classe additionnelle */
  className?: string;
};

export interface FormSidebarSection {
  /** Identifiant de la section */
  id: string;
  /** Titre de la section */
  title?: string;
  /** Éléments de la section */
  items: FormSidebarItem[];
  /** Classe additionnelle */
  className?: string;
}

export interface FormSidebarLayoutProps {
  // --- Contrôle ---
  /** Ouverture du sidebar */
  open?: boolean;
  /** Ouverture par défaut */
  defaultOpen?: boolean;
  /** Callback de changement d'état */
  onOpenChange?: (open: boolean) => void;

  // --- Contenu ---
  /** Titre du sidebar */
  title?: ReactNode;
  /** Sous-titre du sidebar */
  subtitle?: ReactNode;
  /** Icône du sidebar */
  icon?: ReactNode;
  /** Sections du sidebar */
  sections?: FormSidebarSection[];
  /** En-tête personnalisé */
  header?: ReactNode;
  /** Pied de page personnalisé */
  footer?: ReactNode;
  /** Enfant (contenu principal) */
  children?: ReactNode;
  /** Actions du formulaire */
  actions?: ReactNode;
  /** Élément déclencheur */
  trigger?: ReactNode;
  /** Contenu en dehors du sidebar */
  outsideContent?: ReactNode;

  // --- Apparence ---
  /** Position du sidebar */
  position?: FormSidebarPosition;
  /** Taille du sidebar */
  size?: FormSidebarSize;
  /** Variante du sidebar */
  variant?: FormSidebarVariant;
  /** Statut du sidebar */
  status?: FormSidebarStatus;
  /** Animation d'ouverture */
  animation?: FormSidebarAnimation;
  /** Fond d'écran */
  backdrop?: FormSidebarBackdrop;
  /** Mode d'affichage */
  mode?: FormSidebarMode;
  /** Afficher le bouton de fermeture */
  showCloseButton?: boolean;
  /** Afficher le séparateur entre les sections */
  showSectionSeparator?: boolean;
  /** Afficher les badges de statut */
  showStatusBadges?: boolean;
  /** Afficher les icônes */
  showIcons?: boolean;
  /** Afficher la barre de progression */
  showProgress?: boolean;
  /** Afficher l'ombre */
  showShadow?: boolean;
  /** Afficher la bordure */
  showBorder?: boolean;
  /** Afficher le bouton de réduction */
  showCollapseButton?: boolean;
  /** Afficher le compteur d'éléments */
  showItemCount?: boolean;
  /** Classes additionnelles */
  className?: string;
  /** Classe pour l'en-tête */
  headerClassName?: string;
  /** Classe pour le contenu */
  contentClassName?: string;
  /** Classe pour le pied de page */
  footerClassName?: string;
  /** Classe pour les sections */
  sectionClassName?: string;
  /** Classe pour les éléments */
  itemClassName?: string;
  /** Classe pour l'overlay */
  overlayClassName?: string;
  /** Classe pour le contenu extérieur */
  outsideClassName?: string;

  // --- Comportement ---
  /** Désactiver le sidebar */
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
  /** Désactiver le clic en dehors */
  disableOutsideClick?: boolean;
  /** Désactiver la touche Escape */
  disableEscape?: boolean;
  /** Désactiver le scroll du body */
  lockScroll?: boolean;
  /** Désactiver le focus trap */
  disableFocusTrap?: boolean;
  /** Largeur personnalisée */
  width?: string | number;
  /** Padding personnalisé */
  padding?: string | number;
  /** Élément sélectionné par défaut */
  defaultSelected?: string;
  /** Élément sélectionné (contrôlé) */
  selected?: string;
  /** Callback de sélection */
  onSelect?: (itemId: string) => void;

  // --- Callbacks ---
  /** Callback de soumission */
  onSubmit?: () => void;
  /** Callback d'annulation */
  onCancel?: () => void;
  /** Callback de réinitialisation */
  onReset?: () => void;
  /** Callback à l'ouverture */
  onOpen?: () => void;
  /** Callback à la fermeture */
  onClose?: () => void;

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

const SIZE_MAP: Record<FormSidebarSize, { width: string; padding: string; title: string }> = {
  sm: { width: 'w-64', padding: 'p-3', title: 'text-base' },
  md: { width: 'w-80', padding: 'p-4', title: 'text-lg' },
  lg: { width: 'w-96', padding: 'p-6', title: 'text-xl' },
  xl: { width: 'w-[32rem]', padding: 'p-6', title: 'text-2xl' },
  full: { width: 'w-full', padding: 'p-6', title: 'text-2xl' },
  auto: { width: 'w-auto', padding: 'p-4', title: 'text-lg' },
};

const STATUS_MAP: Record<FormSidebarStatus, { color: string; icon: React.ReactNode; border: string }> = {
  idle: {
    color: 'text-gray-500 dark:text-gray-400',
    icon: <InformationCircleIcon className="h-5 w-5" />,
    border: 'border-gray-200 dark:border-gray-700',
  },
  loading: {
    color: 'text-brand-500',
    icon: <ArrowPathIcon className="h-5 w-5 animate-spin" />,
    border: 'border-brand-200 dark:border-brand-800',
  },
  success: {
    color: 'text-green-500',
    icon: <CheckCircleIcon className="h-5 w-5" />,
    border: 'border-green-200 dark:border-green-800',
  },
  error: {
    color: 'text-red-500',
    icon: <ExclamationCircleIcon className="h-5 w-5" />,
    border: 'border-red-200 dark:border-red-800',
  },
  warning: {
    color: 'text-yellow-500',
    icon: <ExclamationTriangleIcon className="h-5 w-5" />,
    border: 'border-yellow-200 dark:border-yellow-800',
  },
  info: {
    color: 'text-blue-500',
    icon: <InformationCircleIcon className="h-5 w-5" />,
    border: 'border-blue-200 dark:border-blue-800',
  },
};

const BACKDROP_MAP: Record<FormSidebarBackdrop, string> = {
  none: 'bg-transparent',
  blur: 'backdrop-blur-sm bg-black/20',
  dark: 'bg-black/50',
  'blur-dark': 'backdrop-blur-md bg-black/60',
  transparent: 'bg-transparent',
};

const ANIMATION_MAP: Record<FormSidebarAnimation, {
  hidden: { opacity?: number; x?: string; y?: string; scale?: number };
  visible: { opacity?: number; x?: string; y?: string; scale?: number };
  exit: { opacity?: number; x?: string; y?: string; scale?: number };
}> = {
  slide: {
    hidden: { opacity: 0, x: '100%' },
    visible: { opacity: 1, x: '0%' },
    exit: { opacity: 0, x: '100%' },
  },
  fade: {
    hidden: { opacity: 0 },
    visible: { opacity: 1 },
    exit: { opacity: 0 },
  },
  scale: {
    hidden: { opacity: 0, scale: 0.95 },
    visible: { opacity: 1, scale: 1 },
    exit: { opacity: 0, scale: 0.95 },
  },
  bounce: {
    hidden: { opacity: 0, x: '120%', scale: 0.8 },
    visible: { opacity: 1, x: '0%', scale: 1 },
    exit: { opacity: 0, x: '100%', scale: 0.8 },
  },
  none: {
    hidden: { opacity: 0 },
    visible: { opacity: 1 },
    exit: { opacity: 0 },
  },
};

// ============================================================================
// SOUS-COMPOSANT: SidebarItem
// ============================================================================

interface SidebarItemProps {
  item: FormSidebarItem;
  isSelected: boolean;
  onSelect: (id: string) => void;
  depth?: number;
  showIcons: boolean;
  showStatusBadges: boolean;
  className?: string;
  disabled?: boolean;
}

const SidebarItem: React.FC<SidebarItemProps> = ({
  item,
  isSelected,
  onSelect,
  depth = 0,
  showIcons,
  showStatusBadges,
  className,
  disabled,
}) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const hasChildren = item.items && item.items.length > 0;
  const status = item.status || 'idle';
  const statusMap = STATUS_MAP[status];

  const handleClick = useCallback(() => {
    if (item.disabled || disabled) return;
    if (hasChildren) {
      setIsExpanded(!isExpanded);
    } else {
      onSelect(item.id);
    }
  }, [item.disabled, disabled, hasChildren, isExpanded, onSelect, item.id]);

  return (
    <div className={className}>
      <button
        type="button"
        className={cn(
          'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition-all',
          isSelected && 'bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-400',
          !isSelected && 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800',
          (item.disabled || disabled) && 'opacity-50 cursor-not-allowed',
          depth > 0 && 'ml-4'
        )}
        onClick={handleClick}
        disabled={item.disabled || disabled}
      >
        {showIcons && item.icon && (
          <span className="flex-shrink-0">
            {item.icon}
          </span>
        )}
        <span className="flex-1 text-left">{item.label}</span>
        {showStatusBadges && status !== 'idle' && (
          <span className={statusMap.color}>
            {statusMap.icon}
          </span>
        )}
        {item.badge && (
          <Badge variant="outline" size="xs">
            {item.badge}
          </Badge>
        )}
        {hasChildren && (
          <span className="text-gray-400">
            {isExpanded ? (
              <ChevronDownIcon className="h-4 w-4" />
            ) : (
              <ChevronRightIcon className="h-4 w-4" />
            )}
          </span>
        )}
      </button>

      {hasChildren && isExpanded && (
        <div className="mt-1 space-y-0.5">
          {item.items?.map((child) => (
            <SidebarItem
              key={child.id}
              item={child}
              isSelected={isSelected}
              onSelect={onSelect}
              depth={depth + 1}
              showIcons={showIcons}
              showStatusBadges={showStatusBadges}
              disabled={disabled}
            />
          ))}
        </div>
      )}
    </div>
  );
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const FormSidebarLayout = forwardRef<HTMLDivElement, FormSidebarLayoutProps>(
  (props, ref) => {
    const {
      // Contrôle
      open: externalOpen,
      defaultOpen = false,
      onOpenChange,

      // Contenu
      title,
      subtitle,
      icon,
      sections = [],
      header,
      footer,
      children,
      actions,
      trigger,
      outsideContent,

      // Apparence
      position = 'right',
      size = 'md',
      variant = 'default',
      status = 'idle',
      animation = 'slide',
      backdrop = 'blur-dark',
      mode = 'overlay',
      showCloseButton = true,
      showSectionSeparator = true,
      showStatusBadges = true,
      showIcons = true,
      showProgress = false,
      showShadow = true,
      showBorder = true,
      showCollapseButton = false,
      showItemCount = true,
      className,
      headerClassName,
      contentClassName,
      footerClassName,
      sectionClassName,
      itemClassName,
      overlayClassName,
      outsideClassName,

      // Comportement
      disabled = false,
      isLoading = false,
      error = null,
      success = null,
      info = null,
      warning = null,
      progress = 0,
      disableOutsideClick = false,
      disableEscape = false,
      lockScroll = true,
      disableFocusTrap = false,
      width,
      padding,
      defaultSelected,
      selected: externalSelected,
      onSelect: externalOnSelect,

      // Callbacks
      onSubmit,
      onCancel,
      onReset,
      onOpen,
      onClose,

      // Accessibilité
      ariaLabel,
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

    const sidebarRef = useRef<HTMLDivElement>(null);
    const triggerRef = useRef<HTMLElement>(null);
    const previousFocusRef = useRef<HTMLElement | null>(null);

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalOpen, setInternalOpen] = useState(defaultOpen);
    const [internalSelected, setInternalSelected] = useState<string | undefined>(defaultSelected);
    const [isMounted, setIsMounted] = useState(false);
    const [isCollapsed, setIsCollapsed] = useState(false);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const open = externalOpen !== undefined ? externalOpen : internalOpen;
    const isControlled = externalOpen !== undefined;

    const selected = externalSelected !== undefined ? externalSelected : internalSelected;
    const isSelectedControlled = externalSelected !== undefined;

    const sizeStyles = SIZE_MAP[size] || SIZE_MAP.md;
    const statusMap = STATUS_MAP[status] || STATUS_MAP.idle;
    const backdropStyles = BACKDROP_MAP[backdrop] || BACKDROP_MAP['blur-dark'];
    const animationStyles = ANIMATION_MAP[animation] || ANIMATION_MAP.slide;

    const hasStatus = status !== 'idle';
    const hasStatusMessage = error || success || info || warning;
    const statusMessage = error || success || info || warning;
    const statusType = error ? 'error' : success ? 'success' : warning ? 'warning' : info ? 'info' : null;
    const statusColor = statusType ? STATUS_MAP[statusType as FormSidebarStatus]?.color : statusMap.color;

    const hasHeader = title || subtitle || icon || header;
    const hasFooter = footer || actions;
    const hasContent = children || sections.length > 0;

    const totalItems = sections.reduce((acc, section) => acc + section.items.length, 0);

    // ========================================================================
    // GESTION DE L'OUVERTURE/FERMETURE
    // ========================================================================

    const setOpen = useCallback((value: boolean) => {
      if (isControlled) {
        if (onOpenChange) onOpenChange(value);
      } else {
        setInternalOpen(value);
      }
      if (value && onOpen) onOpen();
      if (!value && onClose) onClose();
    }, [isControlled, onOpenChange, onOpen, onClose]);

    const handleOpen = useCallback(() => {
      if (disabled) return;
      setOpen(true);
    }, [disabled, setOpen]);

    const handleClose = useCallback(() => {
      if (disabled) return;
      setOpen(false);
    }, [disabled, setOpen]);

    const toggleCollapse = useCallback(() => {
      setIsCollapsed(!isCollapsed);
    }, [isCollapsed]);

    // ========================================================================
    // GESTION DE LA SÉLECTION
    // ========================================================================

    const handleSelect = useCallback((itemId: string) => {
      if (isSelectedControlled) {
        if (externalOnSelect) externalOnSelect(itemId);
      } else {
        setInternalSelected(itemId);
        if (externalOnSelect) externalOnSelect(itemId);
      }
    }, [isSelectedControlled, externalOnSelect]);

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
      handleClose();
    }, [disabled, isLoading, onCancel, handleClose]);

    const handleReset = useCallback(() => {
      if (disabled || isLoading) return;
      if (onReset) onReset();
    }, [disabled, isLoading, onReset]);

    // ========================================================================
    // FOCUS TRAP
    // ========================================================================

    useEffect(() => {
      if (!open || disableFocusTrap) return;

      const activeElement = document.activeElement as HTMLElement;
      if (activeElement) {
        previousFocusRef.current = activeElement;
      }

      setTimeout(() => {
        const focusable = sidebarRef.current?.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable && focusable.length > 0) {
          (focusable[0] as HTMLElement).focus();
        } else if (sidebarRef.current) {
          sidebarRef.current.focus();
        }
      }, 100);

      return () => {
        if (previousFocusRef.current) {
          setTimeout(() => {
            previousFocusRef.current?.focus();
          }, 100);
        }
      };
    }, [open, disableFocusTrap]);

    // ========================================================================
    // SCROLL LOCK
    // ========================================================================

    useEffect(() => {
      if (!lockScroll || mode === 'inline') return;

      const body = document.body;
      const scrollY = window.scrollY;

      if (open) {
        body.style.overflow = 'hidden';
        body.style.position = 'fixed';
        body.style.top = `-${scrollY}px`;
        body.style.width = '100%';
      } else {
        body.style.overflow = '';
        body.style.position = '';
        body.style.top = '';
        body.style.width = '';
        window.scrollTo(0, scrollY);
      }

      return () => {
        body.style.overflow = '';
        body.style.position = '';
        body.style.top = '';
        body.style.width = '';
      };
    }, [open, lockScroll, mode]);

    // ========================================================================
    // ESCAPE KEY
    // ========================================================================

    useEffect(() => {
      if (disableEscape || mode === 'inline') return;

      const handleEscape = (e: KeyboardEvent) => {
        if (e.key === 'Escape' && open) {
          e.preventDefault();
          handleClose();
        }
      };

      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }, [open, disableEscape, handleClose, mode]);

    // ========================================================================
    // MOUNT
    // ========================================================================

    useEffect(() => {
      setIsMounted(true);
      return () => setIsMounted(false);
    }, []);

    // ========================================================================
    // RENDU DE L'EN-TÊTE
    // ========================================================================

    const renderHeader = () => {
      if (header) {
        return (
          <div className={cn('flex items-center justify-between', headerClassName)}>
            {header}
            <div className="flex items-center gap-1">
              {showCollapseButton && (
                <button
                  type="button"
                  onClick={toggleCollapse}
                  className="rounded-lg p-1.5 text-gray-400 hover:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                  aria-label={isCollapsed ? 'Développer' : 'Réduire'}
                >
                  {isCollapsed ? (
                    <MaximizeIcon className="h-5 w-5" />
                  ) : (
                    <MinimizeIcon className="h-5 w-5" />
                  )}
                </button>
              )}
              {showCloseButton && (
                <button
                  type="button"
                  onClick={handleClose}
                  className="rounded-lg p-1.5 text-gray-400 hover:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                  aria-label="Fermer"
                >
                  <XMarkIcon className="h-5 w-5" />
                </button>
              )}
            </div>
          </div>
        );
      }

      if (!hasHeader) return null;

      return (
        <div className={cn('flex items-start gap-4', headerClassName)}>
          {icon && (
            <div className="flex-shrink-0">
              <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-brand-50 dark:bg-brand-900/20 text-brand-500">
                {icon}
              </div>
            </div>
          )}
          <div className="flex-1 min-w-0">
            {title && (
              <h2 className={cn('font-semibold text-gray-900 dark:text-white', sizeStyles.title)}>
                {title}
              </h2>
            )}
            {subtitle && (
              <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                {subtitle}
              </p>
            )}
          </div>
          <div className="flex items-center gap-1">
            {showCollapseButton && (
              <button
                type="button"
                onClick={toggleCollapse}
                className="rounded-lg p-1.5 text-gray-400 hover:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                aria-label={isCollapsed ? 'Développer' : 'Réduire'}
              >
                {isCollapsed ? (
                  <MaximizeIcon className="h-5 w-5" />
                ) : (
                  <MinimizeIcon className="h-5 w-5" />
                )}
              </button>
            )}
            {showCloseButton && (
              <button
                type="button"
                onClick={handleClose}
                className="rounded-lg p-1.5 text-gray-400 hover:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                aria-label="Fermer"
              >
                <XMarkIcon className="h-5 w-5" />
              </button>
            )}
          </div>
        </div>
      );
    };

    // ========================================================================
    // RENDU DU STATUT
    // ========================================================================

    const renderStatus = () => {
      if (!hasStatusMessage && !hasStatus) return null;

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

      if (isCollapsed) {
        return (
          <div className="flex flex-col items-center justify-center py-12 text-gray-400">
            <PanelLeftIcon className="h-12 w-12" />
            <p className="mt-3 text-sm">Sidebar réduit</p>
          </div>
        );
      }

      // Navigation des sections
      if (sections.length > 0) {
        return (
          <div className="space-y-4">
            {sections.map((section, index) => (
              <div
                key={section.id}
                className={cn(
                  'space-y-1',
                  !(index === sections.length - 1) && showSectionSeparator && 'border-b border-gray-200 dark:border-gray-700 pb-4',
                  section.className,
                  sectionClassName
                )}
              >
                {section.title && (
                  <div className="flex items-center justify-between px-3 py-1">
                    <span className="text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
                      {section.title}
                    </span>
                    {showItemCount && (
                      <span className="text-xs text-gray-400">
                        {section.items.length}
                      </span>
                    )}
                  </div>
                )}
                {section.items.map((item) => (
                  <SidebarItem
                    key={item.id}
                    item={item}
                    isSelected={selected === item.id}
                    onSelect={handleSelect}
                    showIcons={showIcons}
                    showStatusBadges={showStatusBadges}
                    className={itemClassName}
                    disabled={disabled}
                  />
                ))}
              </div>
            ))}
          </div>
        );
      }

      return children;
    };

    // ========================================================================
    // RENDU DU PIED DE PAGE
    // ========================================================================

    const renderFooter = () => {
      if (footer) {
        return (
          <div className={footerClassName}>
            {footer}
          </div>
        );
      }

      if (isCollapsed) return null;

      const showActions = actions || onSubmit || onCancel || onReset;

      if (!showActions) return null;

      return (
        <div className={cn(
          'flex flex-wrap items-center justify-end gap-3',
          footerClassName
        )}>
          {actions && (
            <div className="flex items-center gap-2">
              {actions}
            </div>
          )}
          <div className="flex items-center gap-2">
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
        </div>
      );
    };

    // ========================================================================
    // RENDU DU CONTENU EXTÉRIEUR
    // ========================================================================

    const renderOutsideContent = () => {
      if (!outsideContent) return null;

      return (
        <div className={outsideClassName}>
          {outsideContent}
        </div>
      );
    };

    // ========================================================================
    // RENDU DU SIDEBAR
    // ========================================================================

    const renderSidebar = () => {
      const sidebarContent = (
        <div
          ref={sidebarRef}
          className={cn(
            'relative flex h-full flex-col',
            sizeStyles.width,
            variant === 'glass' && 'bg-white/80 backdrop-blur-xl dark:bg-gray-900/80',
            variant === 'solid' && 'bg-white dark:bg-gray-900',
            variant === 'outlined' && 'border-2 border-gray-200 dark:border-gray-700 bg-transparent',
            showShadow && 'shadow-2xl',
            showBorder && 'border border-gray-200 dark:border-gray-700',
            hasStatus && statusMap.border,
            className
          )}
          style={{
            width: width,
            padding: padding,
          }}
        >
          {/* Progression */}
          {showProgress && !isCollapsed && (
            <div className="px-6 pt-6">
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
          )}

          {/* En-tête */}
          {hasHeader && (
            <div className={cn(
              'border-b border-gray-200 dark:border-gray-700',
              sizeStyles.padding,
              headerClassName
            )}>
              {renderHeader()}
            </div>
          )}

          {/* Statut */}
          {!isCollapsed && (
            <div className={sizeStyles.padding}>
              {renderStatus()}
            </div>
          )}

          {/* Contenu */}
          {hasContent && !isCollapsed && (
            <ScrollArea className="flex-1">
              <div className={cn(
                sizeStyles.padding,
                contentClassName
              )}>
                {renderContent()}
              </div>
            </ScrollArea>
          )}

          {/* Pied de page */}
          {hasFooter && !isCollapsed && (
            <div className={cn(
              'border-t border-gray-200 dark:border-gray-700',
              sizeStyles.padding,
              footerClassName
            )}>
              {renderFooter()}
            </div>
          )}
        </div>
      );

      if (mode === 'inline') {
        return (
          <div className="relative flex h-full">
            {renderOutsideContent()}
            {sidebarContent}
          </div>
        );
      }

      const overlay = backdrop !== 'none' && (
        <motion.div
          className={cn('fixed inset-0', backdropStyles, overlayClassName)}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.3 }}
          onClick={disableOutsideClick ? undefined : handleClose}
        />
      );

      const positionClasses = {
        left: 'left-0 top-0 h-full',
        right: 'right-0 top-0 h-full',
      };

      const positionStyle = {
        left: { left: 0, top: 0, height: '100%' },
        right: { right: 0, top: 0, height: '100%' },
      };

      return (
        <>
          {overlay}
          <motion.div
            className={cn(
              'fixed z-50',
              positionClasses[position]
            )}
            initial={animationStyles.hidden}
            animate={animationStyles.visible}
            exit={animationStyles.exit}
            transition={{ duration: 0.3 }}
            style={positionStyle[position]}
          >
            {renderOutsideContent()}
            {sidebarContent}
          </motion.div>
        </>
      );
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    return (
      <>
        {/* Trigger */}
        {trigger && (
          <div
            ref={triggerRef as any}
            onClick={handleOpen}
            className="inline-block cursor-pointer"
          >
            {trigger}
          </div>
        )}

        {/* Sidebar */}
        {isMounted && (mode === 'inline' || open) && renderSidebar()}
      </>
    );
  }
);

FormSidebarLayout.displayName = 'FormSidebarLayout';

// ============================================================================
// SOUS-COMPOSANTS
// ============================================================================

// --- FormSidebarLayout.Section ---
interface FormSidebarSectionProps extends FormSidebarSection {
  children?: ReactNode;
}

export const FormSidebarSection: React.FC<FormSidebarSectionProps> = ({
  id,
  title,
  items,
  className,
  children,
}) => {
  return (
    <div className={cn('space-y-1', className)}>
      {title && (
        <div className="px-3 py-1 text-xs font-medium uppercase text-gray-500 dark:text-gray-400">
          {title}
        </div>
      )}
      {children || items?.map((item) => (
        <div key={item.id} className="px-3 py-2 text-sm text-gray-700 dark:text-gray-300">
          {item.label}
        </div>
      ))}
    </div>
  );
};

// --- FormSidebarLayout.Item ---
interface FormSidebarItemProps extends FormSidebarItem {
  onSelect?: (id: string) => void;
  isSelected?: boolean;
}

export const FormSidebarItem: React.FC<FormSidebarItemProps> = ({
  id,
  label,
  icon,
  content,
  badge,
  status,
  disabled,
  items,
  className,
  onSelect,
  isSelected = false,
}) => {
  return (
    <button
      type="button"
      className={cn(
        'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm transition-all',
        isSelected && 'bg-brand-50 dark:bg-brand-900/20 text-brand-700 dark:text-brand-400',
        !isSelected && 'text-gray-700 hover:bg-gray-100 dark:text-gray-300 dark:hover:bg-gray-800',
        disabled && 'opacity-50 cursor-not-allowed',
        className
      )}
      onClick={() => onSelect?.(id)}
      disabled={disabled}
    >
      {icon && <span className="flex-shrink-0">{icon}</span>}
      <span className="flex-1 text-left">{label}</span>
      {badge && <Badge variant="outline" size="xs">{badge}</Badge>}
    </button>
  );
};

// ============================================================================
// EXPORTS
// ============================================================================

export default Object.assign(FormSidebarLayout, {
  Section: FormSidebarSection,
  Item: FormSidebarItem,
});

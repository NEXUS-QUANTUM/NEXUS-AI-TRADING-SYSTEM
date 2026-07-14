// apps/web/src/components/forms/layouts/FormPanelLayout.tsx
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

export type FormPanelSide = 'left' | 'right' | 'top' | 'bottom';
export type FormPanelSize = 'sm' | 'md' | 'lg' | 'xl' | 'full' | 'auto';
export type FormPanelVariant = 'default' | 'glass' | 'solid' | 'outlined';
export type FormPanelStatus = 'idle' | 'loading' | 'success' | 'error' | 'warning' | 'info';
export type FormPanelAnimation = 'slide' | 'fade' | 'scale' | 'bounce' | 'none';
export type FormPanelBackdrop = 'none' | 'blur' | 'dark' | 'blur-dark' | 'transparent';
export type FormPanelMode = 'overlay' | 'push' | 'inline' | 'float';

export interface FormPanelSection {
  /** Identifiant de la section */
  id: string;
  /** Titre de la section */
  title?: ReactNode;
  /** Description de la section */
  description?: ReactNode;
  /** Contenu de la section */
  content: ReactNode;
  /** Icône de la section */
  icon?: ReactNode;
  /** Statut de la section */
  status?: FormPanelStatus;
  /** Est-ce que la section est collapsible */
  collapsible?: boolean;
  /** Est-ce que la section est initialement ouverte */
  defaultOpen?: boolean;
  /** Classe additionnelle */
  className?: string;
}

export interface FormPanelLayoutProps {
  // --- Contrôle ---
  /** Ouverture du panneau */
  open?: boolean;
  /** Ouverture par défaut */
  defaultOpen?: boolean;
  /** Callback de changement d'état */
  onOpenChange?: (open: boolean) => void;

  // --- Contenu ---
  /** Titre du panneau */
  title?: ReactNode;
  /** Sous-titre du panneau */
  subtitle?: ReactNode;
  /** Icône du panneau */
  icon?: ReactNode;
  /** Sections du formulaire */
  sections?: FormPanelSection[];
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
  /** Contenu en dehors du panneau */
  outsideContent?: ReactNode;

  // --- Apparence ---
  /** Côté du panneau */
  side?: FormPanelSide;
  /** Taille du panneau */
  size?: FormPanelSize;
  /** Variante du panneau */
  variant?: FormPanelVariant;
  /** Statut du panneau */
  status?: FormPanelStatus;
  /** Animation d'ouverture */
  animation?: FormPanelAnimation;
  /** Fond d'écran */
  backdrop?: FormPanelBackdrop;
  /** Mode d'affichage */
  mode?: FormPanelMode;
  /** Afficher le bouton de fermeture */
  showCloseButton?: boolean;
  /** Afficher le séparateur entre les sections */
  showSectionSeparator?: boolean;
  /** Afficher les badges de statut */
  showStatusBadges?: boolean;
  /** Afficher les icônes de section */
  showSectionIcons?: boolean;
  /** Afficher la barre de progression */
  showProgress?: boolean;
  /** Afficher l'ombre */
  showShadow?: boolean;
  /** Afficher la bordure */
  showBorder?: boolean;
  /** Afficher le bouton de réduction */
  showCollapseButton?: boolean;
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
  /** Classe pour l'overlay */
  overlayClassName?: string;
  /** Classe pour le contenu extérieur */
  outsideClassName?: string;

  // --- Comportement ---
  /** Désactiver le panneau */
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
  /** Largeur personnalisée (pour left/right) */
  width?: string | number;
  /** Hauteur personnalisée (pour top/bottom) */
  height?: string | number;
  /** Padding personnalisé */
  padding?: string | number;
  /** Seuil de swipe pour fermer (px) */
  swipeThreshold?: number;

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
  /** Callback de swipe */
  onSwipe?: (direction: 'left' | 'right' | 'up' | 'down') => void;

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

const SIZE_MAP: Record<FormPanelSize, { width: string; height: string; padding: string; title: string }> = {
  sm: { width: 'w-72', height: 'h-72', padding: 'p-4', title: 'text-base' },
  md: { width: 'w-96', height: 'h-96', padding: 'p-6', title: 'text-lg' },
  lg: { width: 'w-[32rem]', height: 'h-[32rem]', padding: 'p-6', title: 'text-xl' },
  xl: { width: 'w-[40rem]', height: 'h-[40rem]', padding: 'p-8', title: 'text-2xl' },
  full: { width: 'w-full', height: 'h-full', padding: 'p-8', title: 'text-2xl' },
  auto: { width: 'w-auto', height: 'h-auto', padding: 'p-6', title: 'text-lg' },
};

const STATUS_MAP: Record<FormPanelStatus, { color: string; icon: React.ReactNode; border: string }> = {
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

const BACKDROP_MAP: Record<FormPanelBackdrop, string> = {
  none: 'bg-transparent',
  blur: 'backdrop-blur-sm bg-black/20',
  dark: 'bg-black/50',
  'blur-dark': 'backdrop-blur-md bg-black/60',
  transparent: 'bg-transparent',
};

const ANIMATION_MAP: Record<FormPanelAnimation, {
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
// SOUS-COMPOSANT: Section
// ============================================================================

interface SectionProps {
  section: FormPanelSection;
  index: number;
  isLast: boolean;
  showSeparator: boolean;
  showIcons: boolean;
  showStatusBadges: boolean;
  className?: string;
  disableAnimations?: boolean;
}

const Section: React.FC<SectionProps> = ({
  section,
  index,
  isLast,
  showSeparator,
  showIcons,
  showStatusBadges,
  className,
  disableAnimations,
}) => {
  const [isOpen, setIsOpen] = useState(section.defaultOpen !== undefined ? section.defaultOpen : true);
  const status = section.status || 'idle';
  const statusMap = STATUS_MAP[status];

  const toggleOpen = useCallback(() => {
    if (section.collapsible) {
      setIsOpen(!isOpen);
    }
  }, [section.collapsible, isOpen]);

  return (
    <div
      className={cn(
        'relative',
        !isLast && showSeparator && 'border-b border-gray-200 dark:border-gray-700 pb-4',
        !isLast && !showSeparator && 'mb-4',
        section.className,
        className
      )}
    >
      {/* En-tête de la section */}
      {(section.title || section.description || section.icon) && (
        <div
          className={cn(
            'flex items-start gap-3',
            section.collapsible && 'cursor-pointer'
          )}
          onClick={toggleOpen}
        >
          {/* Icône */}
          {showIcons && section.icon && (
            <div className="flex-shrink-0 mt-0.5">
              {section.icon}
            </div>
          )}

          {/* Titre et description */}
          <div className="flex-1 min-w-0">
            {section.title && (
              <div className="flex items-center gap-2">
                <h3 className="font-medium text-gray-900 dark:text-white">
                  {section.title}
                </h3>
                {showStatusBadges && status !== 'idle' && (
                  <Badge
                    variant={
                      status === 'success' ? 'success' :
                      status === 'error' ? 'danger' :
                      status === 'warning' ? 'warning' :
                      status === 'info' ? 'info' :
                      'default'
                    }
                    size="xs"
                  >
                    {status}
                  </Badge>
                )}
                {section.collapsible && (
                  <button
                    type="button"
                    className="ml-auto text-gray-400 hover:text-gray-600 dark:hover:text-gray-300"
                    onClick={(e) => {
                      e.stopPropagation();
                      toggleOpen();
                    }}
                  >
                    {isOpen ? (
                      <ChevronUpIcon className="h-4 w-4" />
                    ) : (
                      <ChevronDownIcon className="h-4 w-4" />
                    )}
                  </button>
                )}
              </div>
            )}
            {section.description && (
              <p className="text-sm text-gray-500 dark:text-gray-400">
                {section.description}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Contenu de la section */}
      <AnimatePresence>
        {(!section.collapsible || isOpen) && (
          <motion.div
            initial={!disableAnimations ? { opacity: 0, height: 0 } : {}}
            animate={!disableAnimations ? { opacity: 1, height: 'auto' } : {}}
            exit={!disableAnimations ? { opacity: 0, height: 0 } : {}}
            transition={{ duration: 0.2 }}
            className="overflow-hidden"
          >
            <div className={cn('mt-3', section.title && 'mt-3')}>
              {section.content}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const FormPanelLayout = forwardRef<HTMLDivElement, FormPanelLayoutProps>(
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
      side = 'right',
      size = 'md',
      variant = 'default',
      status = 'idle',
      animation = 'slide',
      backdrop = 'blur-dark',
      mode = 'overlay',
      showCloseButton = true,
      showSectionSeparator = true,
      showStatusBadges = true,
      showSectionIcons = true,
      showProgress = false,
      showShadow = true,
      showBorder = true,
      showCollapseButton = false,
      className,
      headerClassName,
      contentClassName,
      footerClassName,
      sectionClassName,
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
      height,
      padding,
      swipeThreshold = 50,

      // Callbacks
      onSubmit,
      onCancel,
      onReset,
      onOpen,
      onClose,
      onSwipe,

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

    const panelRef = useRef<HTMLDivElement>(null);
    const triggerRef = useRef<HTMLElement>(null);
    const previousFocusRef = useRef<HTMLElement | null>(null);
    const dragStartRef = useRef<{ x: number; y: number } | null>(null);

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalOpen, setInternalOpen] = useState(defaultOpen);
    const [isMounted, setIsMounted] = useState(false);
    const [isDragging, setIsDragging] = useState(false);
    const [dragOffset, setDragOffset] = useState(0);
    const [isCollapsed, setIsCollapsed] = useState(false);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const open = externalOpen !== undefined ? externalOpen : internalOpen;
    const isControlled = externalOpen !== undefined;

    const isLeft = side === 'left';
    const isRight = side === 'right';
    const isTop = side === 'top';
    const isBottom = side === 'bottom';

    const sizeStyles = SIZE_MAP[size] || SIZE_MAP.md;
    const statusMap = STATUS_MAP[status] || STATUS_MAP.idle;
    const backdropStyles = BACKDROP_MAP[backdrop] || BACKDROP_MAP['blur-dark'];
    const animationStyles = ANIMATION_MAP[animation] || ANIMATION_MAP.slide;

    const hasStatus = status !== 'idle';
    const hasStatusMessage = error || success || info || warning;
    const statusMessage = error || success || info || warning;
    const statusType = error ? 'error' : success ? 'success' : warning ? 'warning' : info ? 'info' : null;
    const statusColor = statusType ? STATUS_MAP[statusType as FormPanelStatus]?.color : statusMap.color;

    const hasHeader = title || subtitle || icon || header;
    const hasFooter = footer || actions;
    const hasContent = children || sections.length > 0;

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
    // SWIPE GESTURES
    // ========================================================================

    const handleDragStart = useCallback((e: React.MouseEvent | React.TouchEvent) => {
      const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
      const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
      dragStartRef.current = { x: clientX, y: clientY };
      setIsDragging(true);
    }, []);

    const handleDragMove = useCallback((e: React.MouseEvent | React.TouchEvent) => {
      if (!dragStartRef.current) return;

      const clientX = 'touches' in e ? e.touches[0].clientX : e.clientX;
      const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;

      const deltaX = clientX - dragStartRef.current.x;
      const deltaY = clientY - dragStartRef.current.y;

      let offset = 0;
      let direction: 'left' | 'right' | 'up' | 'down' | null = null;

      if (isLeft || isRight) {
        offset = isRight ? -deltaX : deltaX;
        direction = deltaX > 0 ? 'right' : 'left';
      } else if (isTop || isBottom) {
        offset = isBottom ? -deltaY : deltaY;
        direction = deltaY > 0 ? 'down' : 'up';
      }

      setDragOffset(Math.max(0, offset));

      if (offset > swipeThreshold) {
        if (onSwipe && direction) {
          onSwipe(direction);
        }
        handleClose();
        setIsDragging(false);
        dragStartRef.current = null;
      }
    }, [isLeft, isRight, isTop, isBottom, swipeThreshold, onSwipe, handleClose]);

    const handleDragEnd = useCallback(() => {
      setIsDragging(false);
      dragStartRef.current = null;
      setDragOffset(0);
    }, []);

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
        const focusable = panelRef.current?.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable && focusable.length > 0) {
          (focusable[0] as HTMLElement).focus();
        } else if (panelRef.current) {
          panelRef.current.focus();
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
            <p className="mt-3 text-sm">Panneau réduit</p>
          </div>
        );
      }

      if (sections.length > 0) {
        return (
          <div className="space-y-4">
            {sections.map((section, index) => (
              <Section
                key={section.id}
                section={section}
                index={index}
                isLast={index === sections.length - 1}
                showSeparator={showSectionSeparator}
                showIcons={showSectionIcons}
                showStatusBadges={showStatusBadges}
                className={sectionClassName}
                disableAnimations={disableAnimations}
              />
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
    // RENDU DU PANNEAU
    // ========================================================================

    const renderPanel = () => {
      const panelContent = (
        <div
          ref={panelRef}
          className={cn(
            'relative flex flex-col',
            isLeft || isRight ? sizeStyles.width : 'w-full',
            isTop || isBottom ? sizeStyles.height : 'h-full',
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
            height: height,
            padding: padding,
            transform: isDragging ? `translateX(${isRight ? dragOffset : -dragOffset}px)` : undefined,
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
          <div className="relative">
            {renderOutsideContent()}
            {panelContent}
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
        top: 'top-0 left-0 w-full',
        bottom: 'bottom-0 left-0 w-full',
      };

      const positionStyle = {
        left: isLeft ? { left: 0, top: 0, height: '100%' } : {},
        right: isRight ? { right: 0, top: 0, height: '100%' } : {},
        top: isTop ? { top: 0, left: 0, width: '100%' } : {},
        bottom: isBottom ? { bottom: 0, left: 0, width: '100%' } : {},
      };

      return (
        <>
          {overlay}
          <motion.div
            className={cn(
              'fixed z-50',
              positionClasses[side]
            )}
            initial={animationStyles.hidden}
            animate={animationStyles.visible}
            exit={animationStyles.exit}
            transition={{ duration: 0.3 }}
            style={positionStyle[side]}
            onMouseDown={handleDragStart}
            onMouseMove={handleDragMove}
            onMouseUp={handleDragEnd}
            onMouseLeave={handleDragEnd}
            onTouchStart={handleDragStart}
            onTouchMove={handleDragMove}
            onTouchEnd={handleDragEnd}
          >
            {renderOutsideContent()}
            {panelContent}
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

        {/* Panel */}
        {isMounted && (mode === 'inline' || open) && renderPanel()}
      </>
    );
  }
);

FormPanelLayout.displayName = 'FormPanelLayout';

// ============================================================================
// SOUS-COMPOSANTS
// ============================================================================

// --- FormPanelLayout.Section ---
interface FormPanelSectionProps extends FormPanelSection {
  children?: ReactNode;
}

export const FormPanelSection: React.FC<FormPanelSectionProps> = ({
  id,
  title,
  description,
  content,
  icon,
  status,
  collapsible,
  defaultOpen,
  className,
  children,
}) => {
  return (
    <div className={className}>
      {(title || description || icon) && (
        <div className="flex items-start gap-3 mb-3">
          {icon && <div className="flex-shrink-0 mt-0.5">{icon}</div>}
          <div className="flex-1 min-w-0">
            {title && <h4 className="font-medium text-gray-900 dark:text-white">{title}</h4>}
            {description && <p className="text-sm text-gray-500 dark:text-gray-400">{description}</p>}
          </div>
        </div>
      )}
      <div>{content || children}</div>
    </div>
  );
};

// ============================================================================
// EXPORTS
// ============================================================================

export default Object.assign(FormPanelLayout, {
  Section: FormPanelSection,
});

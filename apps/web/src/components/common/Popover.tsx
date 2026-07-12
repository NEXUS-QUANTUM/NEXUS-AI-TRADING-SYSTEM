// apps/web/src/components/common/Popover.tsx
'use client';

import React, {
  ReactNode,
  useState,
  useEffect,
  useRef,
  useCallback,
  useMemo,
  forwardRef,
  Ref,
  createContext,
  useContext,
  Children,
  isValidElement,
  cloneElement,
  useId,
} from 'react';
import {
  createPortal,
  flushSync,
} from 'react-dom';
import {
  Transition,
  TransitionChild,
} from '@headlessui/react';
import {
  XMarkIcon,
  ChevronDownIcon,
  ChevronUpIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  CheckIcon,
  InformationCircleIcon,
  ExclamationTriangleIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  QuestionMarkCircleIcon,
  AdjustmentsHorizontalIcon,
  FunnelIcon,
  MagnifyingGlassIcon,
  PlusCircleIcon,
  MinusCircleIcon,
  PencilIcon,
  TrashIcon,
  DuplicateIcon,
  ArchiveIcon,
  ArrowPathIcon,
  ShareIcon,
  LinkIcon,
  BookmarkIcon,
  HeartIcon,
  StarIcon,
  FlagIcon,
  EyeIcon,
  EyeSlashIcon,
  LockClosedIcon,
  LockOpenIcon,
  CloudArrowUpIcon,
  CloudArrowDownIcon,
  ArrowDownTrayIcon,
  ArrowUpTrayIcon,
  DocumentTextIcon,
  FolderIcon,
  FolderOpenIcon,
  UserIcon,
  UserGroupIcon,
  Cog6ToothIcon,
  ClipboardIcon,
  ListBulletIcon,
  Squares2X2Icon,
  TableCellsIcon,
  CodeBracketIcon,
  PhotoIcon,
  VideoCameraIcon,
  MusicalNoteIcon,
} from '@heroicons/react/24/outline';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';
import { useClickAway } from '@/hooks/useClickAway';
import { useKeyPress } from '@/hooks/useKeyPress';
import { useScrollLock } from '@/hooks/useScrollLock';
import { useMediaQuery } from '@/hooks/useMediaQuery';
import { Button } from '@/components/common/Button';
import { Input } from '@/components/common/Input';
import { Separator } from '@/components/common/Separator';
import { Badge } from '@/components/common/Badge';
import { Avatar, AvatarFallback, AvatarImage } from '@/components/common/Avatar';
import { ScrollArea } from '@/components/common/ScrollArea';
import { Tooltip } from '@/components/common/Tooltip';
import { Checkbox } from '@/components/common/Checkbox';
import { RadioGroup } from '@/components/common/RadioGroup';
import { Switch } from '@/components/common/Switch';
import { Label } from '@/components/common/Label';
import { Skeleton } from '@/components/common/Skeleton';

// ============================================================================
// TYPES
// ============================================================================

export type PopoverVariant = 'default' | 'outlined' | 'ghost' | 'solid' | 'card' | 'dropdown' | 'tooltip';

export type PopoverSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'full';

export type PopoverPlacement = 
  | 'top'
  | 'top-start'
  | 'top-end'
  | 'bottom'
  | 'bottom-start'
  | 'bottom-end'
  | 'left'
  | 'left-start'
  | 'left-end'
  | 'right'
  | 'right-start'
  | 'right-end';

export type PopoverAnimation = 'fade' | 'slide' | 'scale' | 'bounce' | 'none';

export type PopoverTrigger = 'click' | 'hover' | 'focus' | 'contextmenu' | 'manual';

export interface PopoverProps {
  // --- Contrôle ---
  /** Ouverture contrôlée */
  open?: boolean;
  /** Ouverture par défaut */
  defaultOpen?: boolean;
  /** Callback lors du changement d'état */
  onOpenChange?: (open: boolean) => void;

  // --- Contenu ---
  /** Élément déclencheur */
  trigger: ReactNode;
  /** Contenu du popover */
  children: ReactNode;
  /** Titre du popover */
  title?: ReactNode;
  /** Sous-titre du popover */
  subtitle?: ReactNode;
  /** Pied de page du popover */
  footer?: ReactNode;
  /** Icône du popover */
  icon?: ReactNode;

  // --- Apparence ---
  /** Variante d'affichage */
  variant?: PopoverVariant;
  /** Taille du popover */
  size?: PopoverSize;
  /** Position du popover */
  placement?: PopoverPlacement;
  /** Animation du popover */
  animation?: PopoverAnimation;
  /** Classe CSS additionnelle */
  className?: string;
  /** Classe CSS pour le conteneur */
  containerClassName?: string;
  /** Classe CSS pour le trigger */
  triggerClassName?: string;
  /** Classe CSS pour le contenu */
  contentClassName?: string;
  /** Classe CSS pour le header */
  headerClassName?: string;
  /** Classe CSS pour le footer */
  footerClassName?: string;
  /** Classe CSS pour le corps */
  bodyClassName?: string;
  /** Classe CSS pour le titre */
  titleClassName?: string;
  /** Classe CSS pour le sous-titre */
  subtitleClassName?: string;
  /** Classe CSS pour la flèche */
  arrowClassName?: string;

  /** Largeur maximale */
  maxWidth?: string | number;
  /** Hauteur maximale */
  maxHeight?: string | number;
  /** Largeur minimale */
  minWidth?: string | number;
  /** Padding interne */
  padding?: string | number;
  /** Ombre portée */
  shadow?: 'none' | 'sm' | 'md' | 'lg' | 'xl' | '2xl';
  /** Rayon de bordure */
  radius?: 'none' | 'sm' | 'md' | 'lg' | 'xl' | 'full';

  // --- Comportement ---
  /** Type de déclenchement */
  triggerType?: PopoverTrigger;
  /** Délai d'ouverture (ms) */
  openDelay?: number;
  /** Délai de fermeture (ms) */
  closeDelay?: number;
  /** Fermer au clic en dehors */
  closeOnClickOutside?: boolean;
  /** Fermer au clic sur le trigger */
  closeOnTriggerClick?: boolean;
  /** Fermer à l'appui de la touche Escape */
  closeOnEscape?: boolean;
  /** Fermer automatiquement après un délai */
  autoClose?: number;
  /** Désactiver le popover */
  disabled?: boolean;
  /** Mode portable (render dans un portal) */
  portal?: boolean;
  /** Élément parent pour le portal */
  portalContainer?: HTMLElement | null;
  /** Mode flottant */
  floating?: boolean;
  /** Afficher la flèche */
  showArrow?: boolean;
  /** Afficher le bouton de fermeture */
  showCloseButton?: boolean;
  /** Garder le focus à l'intérieur */
  trapFocus?: boolean;
  /** Restaurer le focus à la fermeture */
  restoreFocus?: boolean;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ARIA describedby */
  ariaDescribedby?: string;
  /** Rôle ARIA */
  role?: 'dialog' | 'menu' | 'listbox' | 'tooltip' | 'alertdialog';
  /** ID */
  id?: string;

  // --- États ---
  /** État de chargement */
  isLoading?: boolean;
  /** État d'erreur */
  error?: string | null;

  // --- Callbacks ---
  /** Callback à l'ouverture */
  onOpen?: () => void;
  /** Callback à la fermeture */
  onClose?: () => void;
  /** Callback avant l'ouverture */
  onBeforeOpen?: () => boolean | void;
  /** Callback avant la fermeture */
  onBeforeClose?: () => boolean | void;

  // --- Avancé ---
  /** Stratégie de positionnement */
  positionStrategy?: 'absolute' | 'fixed';
  /** Offset du popover */
  offset?: number;
  /** S'aligner sur le trigger */
  align?: 'start' | 'center' | 'end';
  /** Gestion du débordement */
  overflow?: 'auto' | 'hidden' | 'visible' | 'scroll';
  /** Autoriser le scroll dans le popover */
  scrollable?: boolean;
  /** Largeur du popover adaptée au trigger */
  matchTriggerWidth?: boolean;
}

// ============================================================================
// CONTEXT
// ============================================================================

interface PopoverContextType {
  open: boolean;
  setOpen: (open: boolean) => void;
  toggle: () => void;
  close: () => void;
  variant: PopoverVariant;
  size: PopoverSize;
  triggerRef: React.RefObject<HTMLElement>;
  contentRef: React.RefObject<HTMLDivElement>;
  placement: PopoverPlacement;
  isLoading: boolean;
  disabled: boolean;
}

const PopoverContext = createContext<PopoverContextType | null>(null);

export const usePopoverContext = () => {
  const context = useContext(PopoverContext);
  if (!context) {
    throw new Error('Popover components must be used within a Popover');
  }
  return context;
};

// ============================================================================
// COMPOSANTS INTERNES
// ============================================================================

// --- Flèche du popover ---
interface PopoverArrowProps {
  placement: PopoverPlacement;
  className?: string;
  size?: number;
}

const PopoverArrow: React.FC<PopoverArrowProps> = ({
  placement,
  className,
  size = 8,
}) => {
  const isTop = placement.startsWith('top');
  const isBottom = placement.startsWith('bottom');
  const isLeft = placement.startsWith('left');
  const isRight = placement.startsWith('right');

  const arrowPosition = {
    top: 'bottom-0 translate-y-1/2',
    bottom: 'top-0 -translate-y-1/2',
    left: 'right-0 translate-x-1/2',
    right: 'left-0 -translate-x-1/2',
  };

  const borderColor = 'border-gray-200 dark:border-gray-700';

  if (isTop || isBottom) {
    return (
      <div
        className={cn(
          'absolute left-1/2 -translate-x-1/2 w-0 h-0',
          arrowPosition[isTop ? 'top' : 'bottom'],
          className
        )}
      >
        <div
          className={cn(
            'w-0 h-0 border-x-[8px] border-x-transparent',
            isTop
              ? `border-t-[8px] ${borderColor}`
              : `border-b-[8px] ${borderColor}`
          )}
        />
        <div
          className={cn(
            'absolute left-1/2 -translate-x-1/2 w-0 h-0 border-x-[7px] border-x-transparent',
            isTop
              ? `-top-[9px] border-t-[7px] border-t-white dark:border-t-gray-900`
              : `-bottom-[9px] border-b-[7px] border-b-white dark:border-b-gray-900`
          )}
        />
      </div>
    );
  }

  if (isLeft || isRight) {
    return (
      <div
        className={cn(
          'absolute top-1/2 -translate-y-1/2 w-0 h-0',
          arrowPosition[isLeft ? 'left' : 'right'],
          className
        )}
      >
        <div
          className={cn(
            'w-0 h-0 border-y-[8px] border-y-transparent',
            isLeft
              ? `border-l-[8px] ${borderColor}`
              : `border-r-[8px] ${borderColor}`
          )}
        />
        <div
          className={cn(
            'absolute top-1/2 -translate-y-1/2 w-0 h-0 border-y-[7px] border-y-transparent',
            isLeft
              ? `-left-[9px] border-l-[7px] border-l-white dark:border-l-gray-900`
              : `-right-[9px] border-r-[7px] border-r-white dark:border-r-gray-900`
          )}
        />
      </div>
    );
  }

  return null;
};

// ============================================================================
// HOOKS INTERNES
// ============================================================================

// --- Hook de positionnement ---
interface Position {
  top: number;
  left: number;
  width: number;
  height: number;
  placement: PopoverPlacement;
}

const usePopoverPosition = (
  triggerRef: React.RefObject<HTMLElement>,
  contentRef: React.RefObject<HTMLElement>,
  placement: PopoverPlacement,
  offset: number,
  matchWidth: boolean,
  portal: boolean,
  floating: boolean
): Position | null => {
  const [position, setPosition] = useState<Position | null>(null);

  useEffect(() => {
    const updatePosition = () => {
      const trigger = triggerRef.current;
      const content = contentRef.current;

      if (!trigger || !content) return;

      const triggerRect = trigger.getBoundingClientRect();
      const contentRect = content.getBoundingClientRect();

      const gap = offset || 8;
      const scrollX = window.scrollX;
      const scrollY = window.scrollY;

      let top = 0;
      let left = 0;
      let finalPlacement = placement;

      // Calcul de la position de base
      const place = placement;
      const isTop = place.startsWith('top');
      const isBottom = place.startsWith('bottom');
      const isLeft = place.startsWith('left');
      const isRight = place.startsWith('right');
      const isStart = place.endsWith('start');
      const isEnd = place.endsWith('end');
      const isCenter = !isStart && !isEnd;

      // Position verticale
      if (isTop) {
        top = triggerRect.top + scrollY - contentRect.height - gap;
      } else if (isBottom) {
        top = triggerRect.bottom + scrollY + gap;
      } else if (isLeft) {
        top = triggerRect.top + scrollY + (triggerRect.height - contentRect.height) / 2;
      } else if (isRight) {
        top = triggerRect.top + scrollY + (triggerRect.height - contentRect.height) / 2;
      }

      // Position horizontale
      if (isLeft) {
        left = triggerRect.left + scrollX - contentRect.width - gap;
      } else if (isRight) {
        left = triggerRect.right + scrollX + gap;
      } else if (isTop || isBottom) {
        if (isStart) {
          left = triggerRect.left + scrollX;
        } else if (isEnd) {
          left = triggerRect.right + scrollX - contentRect.width;
        } else {
          left = triggerRect.left + scrollX + (triggerRect.width - contentRect.width) / 2;
        }
      }

      // Largeur adaptée
      if (matchWidth) {
        content.style.width = `${triggerRect.width}px`;
      }

      // Ajustements pour éviter les débordements
      const viewportWidth = window.innerWidth;
      const viewportHeight = window.innerHeight;

      // Ajustement horizontal
      if (left + contentRect.width > viewportWidth - 16) {
        left = viewportWidth - contentRect.width - 16;
      }
      if (left < 16) {
        left = 16;
      }

      // Ajustement vertical
      if (top + contentRect.height > viewportHeight + scrollY - 16) {
        top = viewportHeight + scrollY - contentRect.height - 16;
      }
      if (top < scrollY + 16) {
        top = scrollY + 16;
      }

      // Vérifier si le placement doit être inversé
      if (isTop && top < scrollY + 16) {
        finalPlacement = placement.replace('top', 'bottom') as PopoverPlacement;
        top = triggerRect.bottom + scrollY + gap;
      }
      if (isBottom && top + contentRect.height > viewportHeight + scrollY - 16) {
        finalPlacement = placement.replace('bottom', 'top') as PopoverPlacement;
        top = triggerRect.top + scrollY - contentRect.height - gap;
      }
      if (isLeft && left < 16) {
        finalPlacement = placement.replace('left', 'right') as PopoverPlacement;
        left = triggerRect.right + scrollX + gap;
      }
      if (isRight && left + contentRect.width > viewportWidth - 16) {
        finalPlacement = placement.replace('right', 'left') as PopoverPlacement;
        left = triggerRect.left + scrollX - contentRect.width - gap;
      }

      // Position fixe pour le mode floating
      if (floating) {
        top = top - scrollY;
        left = left - scrollX;
      }

      const pos = {
        top: portal || floating ? top : top - (document.documentElement.scrollTop || 0),
        left: portal || floating ? left : left - (document.documentElement.scrollLeft || 0),
        width: matchWidth ? triggerRect.width : contentRect.width,
        height: contentRect.height,
        placement: finalPlacement,
      };

      setPosition(pos);
    };

    updatePosition();

    // Mise à jour au redimensionnement
    const handleResize = () => updatePosition();
    window.addEventListener('resize', handleResize);
    window.addEventListener('scroll', handleResize);

    // Utiliser ResizeObserver pour détecter les changements de taille
    const content = contentRef.current;
    if (content && typeof ResizeObserver !== 'undefined') {
      const observer = new ResizeObserver(updatePosition);
      observer.observe(content);
      return () => {
        window.removeEventListener('resize', handleResize);
        window.removeEventListener('scroll', handleResize);
        observer.disconnect();
      };
    }

    return () => {
      window.removeEventListener('resize', handleResize);
      window.removeEventListener('scroll', handleResize);
    };
  }, [triggerRef, contentRef, placement, offset, matchWidth, portal, floating]);

  return position;
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const Popover = forwardRef<HTMLDivElement, PopoverProps>(
  (props, ref) => {
    const {
      // Contrôle
      open: externalOpen,
      defaultOpen = false,
      onOpenChange,

      // Contenu
      trigger,
      children,
      title,
      subtitle,
      footer,
      icon,

      // Apparence
      variant = 'default',
      size = 'md',
      placement = 'bottom',
      animation = 'scale',
      className,
      containerClassName,
      triggerClassName,
      contentClassName,
      headerClassName,
      footerClassName,
      bodyClassName,
      titleClassName,
      subtitleClassName,
      arrowClassName,

      maxWidth,
      maxHeight,
      minWidth,
      minHeight,
      padding = 16,
      shadow = 'lg',
      radius = 'lg',

      // Comportement
      triggerType = 'click',
      openDelay = 0,
      closeDelay = 0,
      closeOnClickOutside = true,
      closeOnTriggerClick = true,
      closeOnEscape = true,
      autoClose = 0,
      disabled = false,
      portal = true,
      portalContainer = null,
      floating = false,
      showArrow = true,
      showCloseButton = false,
      trapFocus = false,
      restoreFocus = true,

      // Accessibilité
      ariaLabel,
      ariaDescribedby,
      role = 'dialog',
      id,

      // États
      isLoading = false,
      error = null,

      // Callbacks
      onOpen,
      onClose,
      onBeforeOpen,
      onBeforeClose,

      // Avancé
      positionStrategy = 'absolute',
      offset = 8,
      align = 'center',
      overflow = 'visible',
      scrollable = true,
      matchTriggerWidth = false,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const triggerRef = useRef<HTMLElement>(null);
    const contentRef = useRef<HTMLDivElement>(null);
    const closeButtonRef = useRef<HTMLButtonElement>(null);
    const triggerElement = useRef<HTMLElement | null>(null);
    const uniqueId = useId();
    const popoverId = id || `nexus-popover-${uniqueId}`;

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalOpen, setInternalOpen] = useState(defaultOpen);
    const [isMounted, setIsMounted] = useState(false);
    const [isAnimating, setIsAnimating] = useState(false);
    const [hasBeenOpened, setHasBeenOpened] = useState(false);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const open = externalOpen ?? internalOpen;
    const isControlled = externalOpen !== undefined;

    // ========================================================================
    // DÉTECTION DU PÉRIPHÉRIQUE
    // ========================================================================

    const isMobile = useMediaQuery('(max-width: 768px)');

    // ========================================================================
    // FERMETURE
    // ========================================================================

    const close = useCallback(() => {
      if (isControlled) {
        onOpenChange?.(false);
      } else {
        setInternalOpen(false);
      }
      onClose?.();
    }, [isControlled, onOpenChange, onClose]);

    // ========================================================================
    // OUVERTURE
    // ========================================================================

    const openPopover = useCallback(() => {
      if (disabled || isLoading) return;

      if (onBeforeOpen) {
        const shouldOpen = onBeforeOpen();
        if (shouldOpen === false) return;
      }

      if (isControlled) {
        onOpenChange?.(true);
      } else {
        setInternalOpen(true);
      }
      onOpen?.();
      setHasBeenOpened(true);
    }, [disabled, isLoading, onBeforeOpen, isControlled, onOpenChange, onOpen]);

    // ========================================================================
    // BASCULE
    // ========================================================================

    const toggle = useCallback(() => {
      if (open) {
        close();
      } else {
        openPopover();
      }
    }, [open, close, openPopover]);

    // ========================================================================
    // TIMEOUTS
    // ========================================================================

    useEffect(() => {
      if (open && autoClose > 0) {
        const timer = setTimeout(close, autoClose);
        return () => clearTimeout(timer);
      }
    }, [open, autoClose, close]);

    // ========================================================================
    // ÉCHAPPEMENT
    // ========================================================================

    const escapePressed = useKeyPress('Escape');

    useEffect(() => {
      if (escapePressed && open && closeOnEscape) {
        close();
      }
    }, [escapePressed, open, closeOnEscape, close]);

    // ========================================================================
    // CLIC EXTÉRIEUR
    // ========================================================================

    useClickAway(
      contentRef,
      (event) => {
        if (
          open &&
          closeOnClickOutside &&
          triggerRef.current &&
          !triggerRef.current.contains(event.target as Node)
        ) {
          close();
        }
      },
      [open, closeOnClickOutside, close]
    );

    // ========================================================================
    // MONTAGE
    // ========================================================================

    useEffect(() => {
      setIsMounted(true);
      return () => setIsMounted(false);
    }, []);

    // ========================================================================
    // FOCUS
    // ========================================================================

    useEffect(() => {
      if (open && trapFocus && contentRef.current) {
        const focusableElements = contentRef.current.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusableElements.length > 0) {
          (focusableElements[0] as HTMLElement).focus();
        }
      }
    }, [open, trapFocus]);

    // ========================================================================
    // CONTEXT
    // ========================================================================

    const contextValue = useMemo<PopoverContextType>(
      () => ({
        open,
        setOpen: isControlled ? (value: boolean) => onOpenChange?.(value) : setInternalOpen,
        toggle,
        close,
        variant,
        size,
        triggerRef,
        contentRef,
        placement,
        isLoading,
        disabled,
      }),
      [open, isControlled, onOpenChange, toggle, close, variant, size, placement, isLoading, disabled]
    );

    // ========================================================================
    // POSITION
    // ========================================================================

    const position = usePopoverPosition(
      triggerRef,
      contentRef,
      placement,
      offset,
      matchTriggerWidth,
      portal,
      floating
    );

    // ========================================================================
    // RENDU DU POPOVER
    // ========================================================================

    const renderPopover = () => {
      // Animation classes
      const animationClasses = {
        fade: {
          enter: 'transition-opacity duration-200',
          enterFrom: 'opacity-0',
          enterTo: 'opacity-100',
          leave: 'transition-opacity duration-150',
          leaveFrom: 'opacity-100',
          leaveTo: 'opacity-0',
        },
        slide: {
          enter: 'transition-all duration-200',
          enterFrom: 'opacity-0 -translate-y-2',
          enterTo: 'opacity-100 translate-y-0',
          leave: 'transition-all duration-150',
          leaveFrom: 'opacity-100 translate-y-0',
          leaveTo: 'opacity-0 -translate-y-2',
        },
        scale: {
          enter: 'transition-all duration-200',
          enterFrom: 'opacity-0 scale-95',
          enterTo: 'opacity-100 scale-100',
          leave: 'transition-all duration-150',
          leaveFrom: 'opacity-100 scale-100',
          leaveTo: 'opacity-0 scale-95',
        },
        bounce: {
          enter: 'transition-all duration-300',
          enterFrom: 'opacity-0 scale-50 -translate-y-4',
          enterTo: 'opacity-100 scale-100 translate-y-0',
          leave: 'transition-all duration-200',
          leaveFrom: 'opacity-100 scale-100 translate-y-0',
          leaveTo: 'opacity-0 scale-50 -translate-y-4',
        },
        none: {
          enter: 'duration-0',
          enterFrom: '',
          enterTo: '',
          leave: 'duration-0',
          leaveFrom: '',
          leaveTo: '',
        },
      };

      const anim = animationClasses[animation] || animationClasses.scale;

      // Styles de taille
      const sizeClasses = {
        xs: 'w-40',
        sm: 'w-56',
        md: 'w-64',
        lg: 'w-80',
        xl: 'w-96',
        full: 'w-full',
      };

      // Variantes
      const variantClasses = {
        default: 'bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700',
        outlined: 'bg-white dark:bg-gray-900 border-2 border-gray-300 dark:border-gray-600',
        ghost: 'bg-transparent border border-gray-200 dark:border-gray-700 shadow-none',
        solid: 'bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 border-0',
        card: 'bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 shadow-xl',
        dropdown: 'bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-700 shadow-lg',
        tooltip: 'bg-gray-900 dark:bg-gray-100 text-white dark:text-gray-900 border-0',
      };

      // Rayon
      const radiusClasses = {
        none: 'rounded-none',
        sm: 'rounded-sm',
        md: 'rounded-md',
        lg: 'rounded-lg',
        xl: 'rounded-xl',
        full: 'rounded-full',
      };

      // Ombre
      const shadowClasses = {
        none: 'shadow-none',
        sm: 'shadow-sm',
        md: 'shadow-md',
        lg: 'shadow-lg',
        xl: 'shadow-xl',
        '2xl': 'shadow-2xl',
      };

      // Contenu
      const contentElement = (
        <Transition
          show={open}
          enter={anim.enter}
          enterFrom={anim.enterFrom}
          enterTo={anim.enterTo}
          leave={anim.leave}
          leaveFrom={anim.leaveFrom}
          leaveTo={anim.leaveTo}
          afterLeave={() => {
            if (restoreFocus && triggerRef.current) {
              triggerRef.current.focus();
            }
          }}
        >
          <div
            ref={contentRef}
            className={cn(
              'relative z-50',
              variantClasses[variant],
              shadowClasses[shadow],
              radiusClasses[radius],
              sizeClasses[size],
              !matchTriggerWidth && size !== 'full' && 'min-w-[200px]',
              contentClassName
            )}
            style={{
              maxWidth: maxWidth,
              maxHeight: maxHeight,
              minWidth: minWidth,
              minHeight: minHeight,
              padding: padding,
              overflow: overflow,
              ...(position && {
                position: positionStrategy,
                top: position.top,
                left: position.left,
                width: position.width,
              }),
            }}
            role={role}
            aria-label={ariaLabel}
            aria-describedby={ariaDescribedby}
            id={popoverId}
          >
            {/* Flèche */}
            {showArrow && position && (
              <PopoverArrow
                placement={position.placement}
                className={arrowClassName}
              />
            )}

            {/* Contenu avec contexte */}
            <PopoverContext.Provider value={contextValue}>
              {/* Header */}
              {(title || subtitle || icon || showCloseButton) && (
                <div
                  className={cn(
                    'flex items-start gap-2 border-b border-gray-200 dark:border-gray-700',
                    headerClassName
                  )}
                  style={{ padding: typeof padding === 'number' ? padding : undefined }}
                >
                  {icon && (
                    <span className="flex-shrink-0 mt-1 text-gray-500 dark:text-gray-400">
                      {icon}
                    </span>
                  )}
                  <div className="flex-1 min-w-0">
                    {title && (
                      <div className={cn('font-semibold text-gray-900 dark:text-white', titleClassName)}>
                        {title}
                      </div>
                    )}
                    {subtitle && (
                      <div className={cn('text-sm text-gray-500 dark:text-gray-400', subtitleClassName)}>
                        {subtitle}
                      </div>
                    )}
                  </div>
                  {showCloseButton && (
                    <button
                      ref={closeButtonRef}
                      type="button"
                      className="flex-shrink-0 rounded p-1 text-gray-400 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
                      onClick={close}
                      aria-label="Fermer"
                    >
                      <XMarkIcon className="h-4 w-4" />
                    </button>
                  )}
                </div>
              )}

              {/* Corps */}
              <div
                className={cn(
                  'flex-1',
                  scrollable && 'overflow-y-auto',
                  bodyClassName
                )}
                style={{
                  maxHeight: scrollable ? maxHeight || '300px' : undefined,
                }}
              >
                {isLoading ? (
                  <div className="flex flex-col items-center justify-center gap-3 py-8">
                    <ArrowPathIcon className="h-6 w-6 animate-spin text-brand-500" />
                    <span className="text-sm text-gray-500 dark:text-gray-400">
                      Chargement...
                    </span>
                  </div>
                ) : error ? (
                  <div className="flex items-center gap-2 p-4 text-sm text-red-600 dark:text-red-400">
                    <ExclamationCircleIcon className="h-5 w-5 flex-shrink-0" />
                    <span>{error}</span>
                  </div>
                ) : (
                  children
                )}
              </div>

              {/* Footer */}
              {footer && (
                <div
                  className={cn(
                    'border-t border-gray-200 dark:border-gray-700',
                    footerClassName
                  )}
                  style={{ padding: typeof padding === 'number' ? padding : undefined }}
                >
                  {footer}
                </div>
              )}
            </PopoverContext.Provider>
          </div>
        </Transition>
      );

      if (portal && isMounted) {
        const container = portalContainer || document.body;
        return createPortal(contentElement, container);
      }

      return contentElement;
    };

    // ========================================================================
    // RENDU DU TRIGGER
    // ========================================================================

    const renderTrigger = () => {
      // Si le trigger est un élément React valide, on le clone avec les props
      if (isValidElement(trigger)) {
        const triggerProps: any = {
          ref: (node: HTMLElement) => {
            triggerRef.current = node;
            triggerElement.current = node;
            // Si le trigger a déjà une ref, on l'appelle
            if (typeof (trigger as any).ref === 'function') {
              (trigger as any).ref(node);
            } else if ((trigger as any).ref) {
              (trigger as any).ref.current = node;
            }
          },
          className: cn(
            triggerProps?.className,
            triggerClassName,
            disabled && 'opacity-50 cursor-not-allowed',
            open && 'ring-2 ring-brand-500 ring-offset-2'
          ),
          'aria-expanded': open,
          'aria-haspopup': true,
          'aria-controls': popoverId,
          onClick: (e: React.MouseEvent) => {
            if (disabled) return;
            if (triggerType === 'click' || triggerType === 'contextmenu') {
              e.preventDefault();
              if (closeOnTriggerClick && open) {
                close();
              } else {
                toggle();
              }
            }
            if ((trigger as any).props?.onClick) {
              (trigger as any).props.onClick(e);
            }
          },
          onMouseEnter: (e: React.MouseEvent) => {
            if (disabled) return;
            if (triggerType === 'hover') {
              setTimeout(openPopover, openDelay);
            }
            if ((trigger as any).props?.onMouseEnter) {
              (trigger as any).props.onMouseEnter(e);
            }
          },
          onMouseLeave: (e: React.MouseEvent) => {
            if (disabled) return;
            if (triggerType === 'hover') {
              setTimeout(close, closeDelay);
            }
            if ((trigger as any).props?.onMouseLeave) {
              (trigger as any).props.onMouseLeave(e);
            }
          },
          onFocus: (e: React.FocusEvent) => {
            if (disabled) return;
            if (triggerType === 'focus') {
              openPopover();
            }
            if ((trigger as any).props?.onFocus) {
              (trigger as any).props.onFocus(e);
            }
          },
          onBlur: (e: React.FocusEvent) => {
            if (disabled) return;
            if (triggerType === 'focus') {
              setTimeout(close, closeDelay);
            }
            if ((trigger as any).props?.onBlur) {
              (trigger as any).props.onBlur(e);
            }
          },
          onContextMenu: (e: React.MouseEvent) => {
            if (disabled) return;
            if (triggerType === 'contextmenu') {
              e.preventDefault();
              toggle();
            }
            if ((trigger as any).props?.onContextMenu) {
              (trigger as any).props.onContextMenu(e);
            }
          },
        };

        return cloneElement(trigger, triggerProps);
      }

      // Si le trigger est un élément HTML, on le wrapper
      if (typeof trigger === 'string') {
        return (
          <button
            ref={triggerRef as any}
            className={cn(
              'cursor-pointer',
              triggerClassName,
              disabled && 'opacity-50 cursor-not-allowed',
              open && 'ring-2 ring-brand-500 ring-offset-2'
            )}
            aria-expanded={open}
            aria-haspopup={true}
            aria-controls={popoverId}
            disabled={disabled}
            onClick={() => {
              if (disabled) return;
              if (triggerType === 'click' || triggerType === 'contextmenu') {
                if (closeOnTriggerClick && open) {
                  close();
                } else {
                  toggle();
                }
              }
            }}
            onMouseEnter={() => {
              if (disabled) return;
              if (triggerType === 'hover') {
                setTimeout(openPopover, openDelay);
              }
            }}
            onMouseLeave={() => {
              if (disabled) return;
              if (triggerType === 'hover') {
                setTimeout(close, closeDelay);
              }
            }}
            onFocus={() => {
              if (disabled) return;
              if (triggerType === 'focus') {
                openPopover();
              }
            }}
            onBlur={() => {
              if (disabled) return;
              if (triggerType === 'focus') {
                setTimeout(close, closeDelay);
              }
            }}
          >
            {trigger}
          </button>
        );
      }

      // Fallback: wrapper avec un div
      return (
        <div
          ref={triggerRef as any}
          className={cn(
            'cursor-pointer inline-block',
            triggerClassName,
            disabled && 'opacity-50 cursor-not-allowed'
          )}
          aria-expanded={open}
          aria-haspopup={true}
          aria-controls={popoverId}
          onClick={() => {
            if (disabled) return;
            if (triggerType === 'click' || triggerType === 'contextmenu') {
              if (closeOnTriggerClick && open) {
                close();
              } else {
                toggle();
              }
            }
          }}
          onMouseEnter={() => {
            if (disabled) return;
            if (triggerType === 'hover') {
              setTimeout(openPopover, openDelay);
            }
          }}
          onMouseLeave={() => {
            if (disabled) return;
            if (triggerType === 'hover') {
              setTimeout(close, closeDelay);
            }
          }}
          onFocus={() => {
            if (disabled) return;
            if (triggerType === 'focus') {
              openPopover();
            }
          }}
          onBlur={() => {
            if (disabled) return;
            if (triggerType === 'focus') {
              setTimeout(close, closeDelay);
            }
          }}
        >
          {trigger}
        </div>
      );
    };

    // ========================================================================
    // RENDU PRINCIPAL
    // ========================================================================

    return (
      <div
        ref={ref}
        className={cn('relative inline-block', containerClassName)}
        style={{ position: floating ? 'static' : 'relative' }}
      >
        {renderTrigger()}
        {renderPopover()}
      </div>
    );
  }
);

Popover.displayName = 'Popover';

// ============================================================================
// SOUS-COMPOSANTS
// ============================================================================

// --- Popover.Item ---
interface PopoverItemProps {
  children: ReactNode;
  onClick?: () => void;
  icon?: ReactNode;
  iconPosition?: 'left' | 'right';
  description?: string;
  disabled?: boolean;
  active?: boolean;
  variant?: 'default' | 'danger' | 'success' | 'warning';
  className?: string;
}

export const PopoverItem: React.FC<PopoverItemProps> = ({
  children,
  onClick,
  icon,
  iconPosition = 'left',
  description,
  disabled = false,
  active = false,
  variant = 'default',
  className,
}) => {
  const context = usePopoverContext();

  const variantClasses = {
    default: 'text-gray-700 dark:text-gray-300 hover:bg-gray-100 dark:hover:bg-gray-800',
    danger: 'text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-900/30',
    success: 'text-green-600 dark:text-green-400 hover:bg-green-50 dark:hover:bg-green-900/30',
    warning: 'text-yellow-600 dark:text-yellow-400 hover:bg-yellow-50 dark:hover:bg-yellow-900/30',
  };

  const handleClick = () => {
    if (disabled) return;
    if (onClick) onClick();
    if (context) context.close();
  };

  return (
    <button
      className={cn(
        'flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm transition-colors',
        variantClasses[variant],
        active && 'bg-brand-50 text-brand-700 dark:bg-brand-900/30 dark:text-brand-400',
        disabled && 'opacity-50 cursor-not-allowed',
        className
      )}
      onClick={handleClick}
      disabled={disabled}
      role="menuitem"
    >
      {icon && iconPosition === 'left' && (
        <span className="flex-shrink-0 text-gray-400">{icon}</span>
      )}
      <div className="flex-1 text-left">
        <div>{children}</div>
        {description && (
          <div className="text-xs text-gray-500 dark:text-gray-400">{description}</div>
        )}
      </div>
      {active && <CheckIcon className="h-4 w-4 text-brand-500" />}
      {icon && iconPosition === 'right' && (
        <span className="flex-shrink-0 text-gray-400">{icon}</span>
      )}
    </button>
  );
};

// --- Popover.Separator ---
export const PopoverSeparator: React.FC<{ className?: string }> = ({ className }) => {
  return <Separator className={cn('my-1', className)} />;
};

// --- Popover.Header ---
export const PopoverHeader: React.FC<{ children: ReactNode; className?: string }> = ({
  children,
  className,
}) => {
  return (
    <div className={cn('px-3 py-2 font-medium text-gray-900 dark:text-white', className)}>
      {children}
    </div>
  );
};

// --- Popover.Footer ---
export const PopoverFooter: React.FC<{ children: ReactNode; className?: string }> = ({
  children,
  className,
}) => {
  return (
    <div className={cn('border-t border-gray-200 dark:border-gray-700 px-3 py-2', className)}>
      {children}
    </div>
  );
};

// ============================================================================
// HOOKS
// ============================================================================

export const usePopover = (defaultOpen = false) => {
  const [open, setOpen] = useState(defaultOpen);

  const openPopover = useCallback(() => setOpen(true), []);
  const closePopover = useCallback(() => setOpen(false), []);
  const togglePopover = useCallback(() => setOpen((prev) => !prev), []);

  return {
    open,
    setOpen,
    open: openPopover,
    close: closePopover,
    toggle: togglePopover,
  };
};

export const usePopoverHover = (delay = 200) => {
  const [open, setOpen] = useState(false);
  const timerRef = useRef<NodeJS.Timeout>();

  const openPopover = useCallback(() => {
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setOpen(true), delay);
  }, [delay]);

  const closePopover = useCallback(() => {
    clearTimeout(timerRef.current);
    timerRef.current = setTimeout(() => setOpen(false), delay);
  }, [delay]);

  const clearTimer = useCallback(() => {
    clearTimeout(timerRef.current);
  }, []);

  useEffect(() => {
    return () => clearTimer();
  }, [clearTimer]);

  return {
    open,
    setOpen,
    open: openPopover,
    close: closePopover,
    clearTimer,
  };
};

// ============================================================================
// EXPORTS
// ============================================================================

export default Object.assign(Popover, {
  Item: PopoverItem,
  Separator: PopoverSeparator,
  Header: PopoverHeader,
  Footer: PopoverFooter,
});

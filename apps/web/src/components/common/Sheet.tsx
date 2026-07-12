// apps/web/src/components/common/Sheet.tsx
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
  useId,
  Children,
  isValidElement,
  cloneElement,
} from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence, MotionConfig, PanInfo } from 'framer-motion';
import {
  XMarkIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  ChevronUpIcon,
  ChevronDownIcon,
  Maximize2Icon,
  Minimize2Icon,
  ArrowsPointingOutIcon,
  ArrowsPointingInIcon,
} from '@heroicons/react/24/outline';
import { Button } from '@/components/common/Button';
import { ScrollArea } from '@/components/common/ScrollArea';
import { Separator } from '@/components/common/Separator';

// ============================================================================
// TYPES
// ============================================================================

export type SheetSide = 'left' | 'right' | 'top' | 'bottom';
export type SheetSize = 'xs' | 'sm' | 'md' | 'lg' | 'xl' | 'full' | 'auto';
export type SheetVariant = 'default' | 'glass' | 'solid' | 'outlined' | 'gradient';
export type SheetAnimation = 'slide' | 'fade' | 'scale' | 'bounce' | 'none';
export type SheetBackdrop = 'none' | 'blur' | 'dark' | 'blur-dark' | 'transparent';

export interface SheetProps {
  // --- Contrôle ---
  /** Ouverture du sheet */
  open?: boolean;
  /** Ouverture par défaut */
  defaultOpen?: boolean;
  /** Callback lors du changement d'état */
  onOpenChange?: (open: boolean) => void;

  // --- Contenu ---
  /** Contenu du sheet */
  children: ReactNode;
  /** Élément déclencheur */
  trigger?: ReactNode;
  /** Titre du sheet */
  title?: ReactNode;
  /** Sous-titre du sheet */
  subtitle?: ReactNode;
  /** Footer du sheet */
  footer?: ReactNode;
  /** Icône du sheet */
  icon?: ReactNode;

  // --- Apparence ---
  /** Côté d'où le sheet glisse */
  side?: SheetSide;
  /** Taille du sheet */
  size?: SheetSize;
  /** Variante visuelle */
  variant?: SheetVariant;
  /** Animation d'ouverture */
  animation?: SheetAnimation;
  /** Fond d'écran */
  backdrop?: SheetBackdrop;
  /** Rayon de bordure */
  radius?: 'none' | 'sm' | 'md' | 'lg' | 'xl' | 'full';
  /** Classe CSS additionnelle */
  className?: string;
  /** Classe CSS pour le conteneur */
  containerClassName?: string;
  /** Classe CSS pour le contenu */
  contentClassName?: string;
  /** Classe CSS pour le header */
  headerClassName?: string;
  /** Classe CSS pour le footer */
  footerClassName?: string;
  /** Classe CSS pour le body */
  bodyClassName?: string;
  /** Classe CSS pour le titre */
  titleClassName?: string;
  /** Classe CSS pour le sous-titre */
  subtitleClassName?: string;

  // --- Comportement ---
  /** Désactiver le swipe pour fermer */
  disableSwipe?: boolean;
  /** Désactiver le clic en dehors */
  disableOutsideClick?: boolean;
  /** Désactiver la touche Escape */
  disableEscape?: boolean;
  /** Désactiver le scroll du body */
  lockScroll?: boolean;
  /** Désactiver le focus trap */
  disableFocusTrap?: boolean;
  /** Désactiver le sheet */
  disabled?: boolean;
  /** Mode portable (render dans un portal) */
  portal?: boolean;
  /** État de chargement */
  isLoading?: boolean;
  /** État d'erreur */
  error?: string | null;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ARIA describedby */
  ariaDescribedby?: string;
  /** ID */
  id?: string;
  /** Rôle ARIA */
  role?: 'dialog' | 'menu' | 'navigation' | 'region';

  // --- Callbacks ---
  /** Callback à l'ouverture */
  onOpen?: () => void;
  /** Callback à la fermeture */
  onClose?: () => void;
  /** Callback avant l'ouverture */
  onBeforeOpen?: () => boolean | void;
  /** Callback avant la fermeture */
  onBeforeClose?: () => boolean | void;
  /** Callback lors du swipe */
  onSwipe?: (direction: 'up' | 'down' | 'left' | 'right') => void;

  // --- Avancé ---
  /** Z-index */
  zIndex?: number;
  /** Durée de l'animation (ms) */
  animationDuration?: number;
  /** Seuil de swipe pour fermer */
  swipeThreshold?: number;
  /** Largeur personnalisée (pour left/right) */
  width?: string | number;
  /** Hauteur personnalisée (pour top/bottom) */
  height?: string | number;
  /** Padding personnalisé */
  padding?: string | number;
  /** Désactiver le resize */
  disableResize?: boolean;
  /** Taille minimale */
  minSize?: string | number;
  /** Taille maximale */
  maxSize?: string | number;
}

// ============================================================================
// CONTEXT
// ============================================================================

interface SheetContextType {
  open: boolean;
  setOpen: (open: boolean) => void;
  close: () => void;
  side: SheetSide;
  size: SheetSize;
  variant: SheetVariant;
  animation: SheetAnimation;
  disabled: boolean;
  isLoading: boolean;
  isDragging: boolean;
  setIsDragging: (dragging: boolean) => void;
  sheetId: string;
}

const SheetContext = createContext<SheetContextType | null>(null);

export const useSheetContext = () => {
  const context = useContext(SheetContext);
  if (!context) {
    throw new Error('useSheetContext must be used within a Sheet');
  }
  return context;
};

// ============================================================================
// COMPOSANTS INTERNES
// ============================================================================

// --- Sheet Header ---
interface SheetHeaderProps {
  className?: string;
  children?: ReactNode;
  showCloseButton?: boolean;
  onClose?: () => void;
}

export const SheetHeader: React.FC<SheetHeaderProps> = ({
  className,
  children,
  showCloseButton = true,
  onClose,
}) => {
  const context = useSheetContext();
  const { close, side, title, subtitle, icon } = context;

  const handleClose = () => {
    if (onClose) onClose();
    close();
  };

  // Si un children est fourni, on l'utilise
  if (children) {
    return (
      <div className={cn('flex items-center justify-between', className)}>
        {children}
        {showCloseButton && (
          <button
            onClick={handleClose}
            className="flex-shrink-0 rounded-lg p-1.5 text-gray-400 hover:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
            aria-label="Fermer"
          >
            <XMarkIcon className="h-5 w-5" />
          </button>
        )}
      </div>
    );
  }

  // Sinon on utilise les props du contexte
  return (
    <div className={cn('flex items-start justify-between gap-4', className)}>
      <div className="flex-1 min-w-0">
        {icon && <span className="mr-2">{icon}</span>}
        {title && (
          <h2 className={cn('text-lg font-semibold text-gray-900 dark:text-white')}>
            {title}
          </h2>
        )}
        {subtitle && (
          <p className="text-sm text-gray-500 dark:text-gray-400">
            {subtitle}
          </p>
        )}
      </div>
      {showCloseButton && (
        <button
          onClick={handleClose}
          className="flex-shrink-0 rounded-lg p-1.5 text-gray-400 hover:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors"
          aria-label="Fermer"
        >
          <XMarkIcon className="h-5 w-5" />
        </button>
      )}
    </div>
  );
};

// --- Sheet Body ---
interface SheetBodyProps {
  className?: string;
  children: ReactNode;
  scrollable?: boolean;
  maxHeight?: string | number;
}

export const SheetBody: React.FC<SheetBodyProps> = ({
  className,
  children,
  scrollable = true,
  maxHeight,
}) => {
  if (scrollable) {
    return (
      <ScrollArea
        className={cn('flex-1', className)}
        maxHeight={maxHeight || '100%'}
      >
        {children}
      </ScrollArea>
    );
  }

  return (
    <div className={cn('flex-1 overflow-hidden', className)}>
      {children}
    </div>
  );
};

// --- Sheet Footer ---
interface SheetFooterProps {
  className?: string;
  children: ReactNode;
}

export const SheetFooter: React.FC<SheetFooterProps> = ({
  className,
  children,
}) => {
  return (
    <div className={cn('border-t border-gray-200 dark:border-gray-700 p-4', className)}>
      {children}
    </div>
  );
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const Sheet = forwardRef<HTMLDivElement, SheetProps>(
  (props, ref) => {
    const {
      // Contrôle
      open: externalOpen,
      defaultOpen = false,
      onOpenChange,

      // Contenu
      children,
      trigger,
      title,
      subtitle,
      footer,
      icon,

      // Apparence
      side = 'right',
      size = 'md',
      variant = 'default',
      animation = 'slide',
      backdrop = 'blur-dark',
      radius = 'lg',
      className,
      containerClassName,
      contentClassName,
      headerClassName,
      footerClassName,
      bodyClassName,
      titleClassName,
      subtitleClassName,

      // Comportement
      disableSwipe = false,
      disableOutsideClick = false,
      disableEscape = false,
      lockScroll = true,
      disableFocusTrap = false,
      disabled = false,
      portal = true,
      isLoading = false,
      error = null,

      // Accessibilité
      ariaLabel,
      ariaDescribedby,
      id,
      role = 'dialog',

      // Callbacks
      onOpen,
      onClose,
      onBeforeOpen,
      onBeforeClose,
      onSwipe,

      // Avancé
      zIndex = 1000,
      animationDuration = 300,
      swipeThreshold = 50,
      width,
      height,
      padding,
      disableResize = false,
      minSize,
      maxSize,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const sheetRef = useRef<HTMLDivElement>(null);
    const triggerRef = useRef<HTMLElement>(null);
    const previousFocusRef = useRef<HTMLElement | null>(null);
    const uniqueId = useId();
    const sheetId = id || `nexus-sheet-${uniqueId}`;

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalOpen, setInternalOpen] = useState(defaultOpen);
    const [isMounted, setIsMounted] = useState(false);
    const [isDragging, setIsDragging] = useState(false);
    const [dragOffset, setDragOffset] = useState(0);
    const [isAnimating, setIsAnimating] = useState(false);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const open = externalOpen !== undefined ? externalOpen : internalOpen;
    const isControlled = externalOpen !== undefined;
    const isLeft = side === 'left';
    const isRight = side === 'right';
    const isTop = side === 'top';
    const isBottom = side === 'bottom';

    // ========================================================================
    // TAILLES
    // ========================================================================

    const getSizeClasses = useCallback(() => {
      const sizeMap: Record<SheetSize, string> = {
        xs: isLeft || isRight ? 'w-72' : 'h-72',
        sm: isLeft || isRight ? 'w-80' : 'h-80',
        md: isLeft || isRight ? 'w-96' : 'h-96',
        lg: isLeft || isRight ? 'w-[32rem]' : 'h-[32rem]',
        xl: isLeft || isRight ? 'w-[40rem]' : 'h-[40rem]',
        full: isLeft || isRight ? 'w-full' : 'h-full',
        auto: isLeft || isRight ? 'w-auto' : 'h-auto',
      };
      return sizeMap[size] || sizeMap.md;
    }, [size, isLeft, isRight]);

    const getPositionClasses = useCallback(() => {
      const base = 'fixed bg-white dark:bg-gray-900 shadow-2xl';
      
      if (isLeft) return cn(base, 'left-0 top-0 h-full', getSizeClasses());
      if (isRight) return cn(base, 'right-0 top-0 h-full', getSizeClasses());
      if (isTop) return cn(base, 'top-0 left-0 w-full', getSizeClasses());
      if (isBottom) return cn(base, 'bottom-0 left-0 w-full', getSizeClasses());
      
      return base;
    }, [isLeft, isRight, isTop, isBottom, getSizeClasses]);

    // ========================================================================
    // STYLES PERSONNALISÉS
    // ========================================================================

    const getCustomStyles = useCallback((): React.CSSProperties => {
      const styles: React.CSSProperties = {};

      // Largeur/hauteur personnalisée
      if (width && (isLeft || isRight)) {
        styles.width = typeof width === 'number' ? `${width}px` : width;
      }
      if (height && (isTop || isBottom)) {
        styles.height = typeof height === 'number' ? `${height}px` : height;
      }

      // Taille minimale/maximale
      if (minSize) {
        styles.minWidth = typeof minSize === 'number' ? `${minSize}px` : minSize;
        styles.minHeight = typeof minSize === 'number' ? `${minSize}px` : minSize;
      }
      if (maxSize) {
        styles.maxWidth = typeof maxSize === 'number' ? `${maxSize}px` : maxSize;
        styles.maxHeight = typeof maxSize === 'number' ? `${maxSize}px` : maxSize;
      }

      // Padding
      if (padding) {
        styles.padding = typeof padding === 'number' ? `${padding}px` : padding;
      }

      // Z-index
      styles.zIndex = zIndex;

      return styles;
    }, [width, height, isLeft, isRight, isTop, isBottom, minSize, maxSize, padding, zIndex]);

    // ========================================================================
    // VARIANTES
    // ========================================================================

    const getVariantClasses = useCallback(() => {
      const base = 'border';
      
      switch (variant) {
        case 'glass':
          return cn(
            base,
            'border-white/20 bg-white/80 backdrop-blur-xl dark:bg-gray-900/80 dark:border-gray-700/50'
          );
        case 'solid':
          return cn(
            base,
            'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900'
          );
        case 'outlined':
          return cn(
            base,
            'border-2 border-gray-300 dark:border-gray-600 bg-transparent'
          );
        case 'gradient':
          return cn(
            base,
            'border-transparent bg-gradient-to-br from-white to-gray-50 dark:from-gray-900 dark:to-gray-800'
          );
        default:
          return cn(
            base,
            'border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900'
          );
      }
    }, [variant]);

    // ========================================================================
    // ANIMATIONS
    // ========================================================================

    const getAnimationVariants = useCallback(() => {
      const hidden = {
        opacity: 0,
        x: isLeft ? '-100%' : isRight ? '100%' : 0,
        y: isTop ? '-100%' : isBottom ? '100%' : 0,
        scale: animation === 'scale' ? 0.9 : 1,
        transition: { duration: animationDuration / 1000 },
      };
      
      const visible = {
        opacity: 1,
        x: 0,
        y: 0,
        scale: 1,
        transition: { duration: animationDuration / 1000, ease: 'easeOut' },
      };

      const exit = {
        opacity: 0,
        x: isLeft ? '-100%' : isRight ? '100%' : 0,
        y: isTop ? '-100%' : isBottom ? '100%' : 0,
        scale: animation === 'scale' ? 0.9 : 1,
        transition: { duration: animationDuration / 1000, ease: 'easeIn' },
      };

      if (animation === 'none') {
        return {
          hidden: { opacity: 0 },
          visible: { opacity: 1 },
          exit: { opacity: 0 },
        };
      }

      if (animation === 'fade') {
        return {
          hidden: { opacity: 0 },
          visible: { opacity: 1 },
          exit: { opacity: 0 },
        };
      }

      if (animation === 'bounce') {
        return {
          hidden: { 
            opacity: 0,
            x: isLeft ? '-120%' : isRight ? '120%' : 0,
            y: isTop ? '-120%' : isBottom ? '120%' : 0,
            scale: 0.8,
          },
          visible: {
            opacity: 1,
            x: 0,
            y: 0,
            scale: 1,
            transition: { 
              duration: animationDuration / 1000,
              type: 'spring',
              stiffness: 300,
              damping: 25,
            },
          },
          exit: {
            opacity: 0,
            x: isLeft ? '-100%' : isRight ? '100%' : 0,
            y: isTop ? '-100%' : isBottom ? '100%' : 0,
            scale: 0.8,
            transition: { duration: animationDuration / 1000, ease: 'easeIn' },
          },
        };
      }

      return { hidden, visible, exit };
    }, [isLeft, isRight, isTop, isBottom, animation, animationDuration]);

    // ========================================================================
    // BACKDROP
    // ========================================================================

    const getBackdropClasses = useCallback(() => {
      switch (backdrop) {
        case 'none':
          return 'bg-transparent';
        case 'blur':
          return 'backdrop-blur-sm bg-black/20';
        case 'dark':
          return 'bg-black/50';
        case 'blur-dark':
          return 'backdrop-blur-md bg-black/60';
        case 'transparent':
          return 'bg-transparent';
        default:
          return 'backdrop-blur-md bg-black/60';
      }
    }, [backdrop]);

    // ========================================================================
    // RAYON
    // ========================================================================

    const getRadiusClasses = useCallback(() => {
      const radiusMap = {
        none: 'rounded-none',
        sm: 'rounded-sm',
        md: 'rounded-md',
        lg: 'rounded-lg',
        xl: 'rounded-xl',
        full: 'rounded-full',
      };

      const radiusClass = radiusMap[radius] || radiusMap.lg;

      // Appliquer le rayon en fonction du côté
      if (isLeft) return cn(radiusClass, 'rounded-r-none');
      if (isRight) return cn(radiusClass, 'rounded-l-none');
      if (isTop) return cn(radiusClass, 'rounded-b-none');
      if (isBottom) return cn(radiusClass, 'rounded-t-none');
      
      return radiusClass;
    }, [radius, isLeft, isRight, isTop, isBottom]);

    // ========================================================================
    // GESTION DE L'OUVERTURE/FERMETURE
    // ========================================================================

    const openSheet = useCallback(() => {
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
    }, [disabled, isLoading, onBeforeOpen, isControlled, onOpenChange, onOpen]);

    const closeSheet = useCallback(() => {
      if (onBeforeClose) {
        const shouldClose = onBeforeClose();
        if (shouldClose === false) return;
      }

      if (isControlled) {
        onOpenChange?.(false);
      } else {
        setInternalOpen(false);
      }
      onClose?.();
    }, [onBeforeClose, isControlled, onOpenChange, onClose]);

    // ========================================================================
    // SWIPE
    // ========================================================================

    const handleDrag = useCallback((_event: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
      if (disableSwipe || disabled) return;

      const offset = isLeft ? info.offset.x : 
                     isRight ? -info.offset.x :
                     isTop ? info.offset.y :
                     -info.offset.y;

      setDragOffset(Math.max(0, offset));
      setIsDragging(true);
    }, [disableSwipe, disabled, isLeft, isRight, isTop, isBottom]);

    const handleDragEnd = useCallback((_event: MouseEvent | TouchEvent | PointerEvent, info: PanInfo) => {
      if (disableSwipe || disabled) return;

      setIsDragging(false);

      const offset = isLeft ? info.offset.x : 
                     isRight ? -info.offset.x :
                     isTop ? info.offset.y :
                     -info.offset.y;

      if (offset > swipeThreshold) {
        closeSheet();
        onSwipe?.(side);
      }

      setDragOffset(0);
    }, [disableSwipe, disabled, isLeft, isRight, isTop, isBottom, swipeThreshold, closeSheet, onSwipe, side]);

    // ========================================================================
    // FOCUS TRAP
    // ========================================================================

    useEffect(() => {
      if (!open || disableFocusTrap) return;

      // Sauvegarder l'élément actuellement focusé
      const activeElement = document.activeElement as HTMLElement;
      if (activeElement) {
        previousFocusRef.current = activeElement;
      }

      // Focus sur le sheet
      setTimeout(() => {
        const focusable = sheetRef.current?.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable && focusable.length > 0) {
          (focusable[0] as HTMLElement).focus();
        } else if (sheetRef.current) {
          sheetRef.current.focus();
        }
      }, 100);

      return () => {
        // Restaurer le focus
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
      if (!lockScroll) return;

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
    }, [open, lockScroll]);

    // ========================================================================
    // ESCAPE KEY
    // ========================================================================

    useEffect(() => {
      if (disableEscape) return;

      const handleEscape = (e: KeyboardEvent) => {
        if (e.key === 'Escape' && open) {
          e.preventDefault();
          closeSheet();
        }
      };

      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }, [open, disableEscape, closeSheet]);

    // ========================================================================
    // MOUNT
    // ========================================================================

    useEffect(() => {
      setIsMounted(true);
      return () => setIsMounted(false);
    }, []);

    // ========================================================================
    // CONTEXT
    // ========================================================================

    const contextValue = useMemo<SheetContextType>(
      () => ({
        open,
        setOpen: isControlled ? (value: boolean) => onOpenChange?.(value) : setInternalOpen,
        close: closeSheet,
        side,
        size,
        variant,
        animation,
        disabled,
        isLoading,
        isDragging,
        setIsDragging,
        sheetId,
      }),
      [
        open,
        isControlled,
        onOpenChange,
        closeSheet,
        side,
        size,
        variant,
        animation,
        disabled,
        isLoading,
        isDragging,
        setIsDragging,
        sheetId,
      ]
    );

    // ========================================================================
    // RENDU DU SHEET
    // ========================================================================

    const renderSheet = () => {
      const variants = getAnimationVariants();
      const sheetContent = (
        <SheetContext.Provider value={contextValue}>
          <motion.div
            ref={(node) => {
              if (typeof ref === 'function') ref(node);
              else if (ref) ref.current = node;
              sheetRef.current = node;
            }}
            id={sheetId}
            className={cn(
              'flex flex-col outline-none',
              getPositionClasses(),
              getVariantClasses(),
              getRadiusClasses(),
              className
            )}
            style={getCustomStyles()}
            initial="hidden"
            animate="visible"
            exit="exit"
            variants={variants}
            drag={!disableSwipe && !disabled ? (isLeft || isRight ? 'x' : 'y') : false}
            dragConstraints={{ left: 0, right: 0, top: 0, bottom: 0 }}
            dragElastic={0.1}
            dragMomentum={false}
            onDrag={handleDrag}
            onDragEnd={handleDragEnd}
            role={role}
            aria-label={ariaLabel}
            aria-describedby={ariaDescribedby}
            aria-modal="true"
            tabIndex={-1}
          >
            {/* Header par défaut */}
            {(title || subtitle || icon) && (
              <div className={cn('p-4 border-b border-gray-200 dark:border-gray-700', headerClassName)}>
                <SheetHeader
                  className="w-full"
                  showCloseButton
                  onClose={closeSheet}
                />
              </div>
            )}

            {/* Contenu personnalisé */}
            <div className={cn('flex-1 overflow-hidden', bodyClassName)}>
              {isLoading ? (
                <div className="flex flex-col items-center justify-center h-full gap-4 p-8">
                  <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-500 border-t-transparent" />
                  <p className="text-sm text-gray-500 dark:text-gray-400">Chargement...</p>
                </div>
              ) : error ? (
                <div className="flex flex-col items-center justify-center h-full gap-4 p-8 text-red-600 dark:text-red-400">
                  <ExclamationTriangleIcon className="h-12 w-12" />
                  <p className="text-center">{error}</p>
                </div>
              ) : (
                children
              )}
            </div>

            {/* Footer */}
            {footer && (
              <div className={cn('border-t border-gray-200 dark:border-gray-700 p-4', footerClassName)}>
                {footer}
              </div>
            )}
          </motion.div>
        </SheetContext.Provider>
      );

      // Overlay
      const overlay = backdrop !== 'none' && (
        <motion.div
          className={cn('fixed inset-0', getBackdropClasses())}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: animationDuration / 1000 }}
          onClick={disableOutsideClick ? undefined : closeSheet}
          style={{ zIndex: zIndex - 1 }}
        />
      );

      return (
        <>
          {overlay}
          {sheetContent}
        </>
      );
    };

    // ========================================================================
    // RENDU FINAL
    // ========================================================================

    return (
      <>
        {/* Trigger */}
        {trigger && (
          <div
            ref={triggerRef as any}
            onClick={openSheet}
            className="inline-block cursor-pointer"
          >
            {trigger}
          </div>
        )}

        {/* Sheet */}
        {portal && isMounted ? (
          createPortal(
            <AnimatePresence mode="wait">
              {open && renderSheet()}
            </AnimatePresence>,
            document.body
          )
        ) : (
          <AnimatePresence mode="wait">
            {open && renderSheet()}
          </AnimatePresence>
        )}
      </>
    );
  }
);

Sheet.displayName = 'Sheet';

// ============================================================================
// SOUS-COMPOSANTS
// ============================================================================

// --- Sheet.Trigger ---
interface SheetTriggerProps {
  children: ReactNode;
  className?: string;
  asChild?: boolean;
}

export const SheetTrigger: React.FC<SheetTriggerProps> = ({
  children,
  className,
  asChild = false,
}) => {
  const context = useSheetContext();

  const handleClick = () => {
    if (context) context.setOpen(true);
  };

  if (asChild) {
    return cloneElement(children as React.ReactElement, {
      onClick: handleClick,
      className: cn((children as any).props?.className, className),
    });
  }

  return (
    <div className={cn('cursor-pointer inline-block', className)} onClick={handleClick}>
      {children}
    </div>
  );
};

// --- Sheet.Close ---
interface SheetCloseProps {
  children?: ReactNode;
  className?: string;
  asChild?: boolean;
}

export const SheetClose: React.FC<SheetCloseProps> = ({
  children,
  className,
  asChild = false,
}) => {
  const context = useSheetContext();

  const handleClick = () => {
    if (context) context.close();
  };

  if (asChild && children) {
    return cloneElement(children as React.ReactElement, {
      onClick: handleClick,
      className: cn((children as any).props?.className, className),
    });
  }

  if (children) {
    return (
      <div className={cn('cursor-pointer', className)} onClick={handleClick}>
        {children}
      </div>
    );
  }

  return (
    <button
      className={cn(
        'flex-shrink-0 rounded-lg p-1.5 text-gray-400 hover:text-gray-500 hover:bg-gray-100 dark:hover:bg-gray-800 transition-colors',
        className
      )}
      onClick={handleClick}
      aria-label="Fermer"
    >
      <XMarkIcon className="h-5 w-5" />
    </button>
  );
};

// ============================================================================
// HOOKS
// ============================================================================

export const useSheet = (defaultOpen = false) => {
  const [open, setOpen] = useState(defaultOpen);

  const openSheet = useCallback(() => setOpen(true), []);
  const closeSheet = useCallback(() => setOpen(false), []);
  const toggleSheet = useCallback(() => setOpen((prev) => !prev), []);

  return {
    open,
    setOpen,
    open: openSheet,
    close: closeSheet,
    toggle: toggleSheet,
  };
};

// ============================================================================
// EXPORTS
// ============================================================================

export default Object.assign(Sheet, {
  Header: SheetHeader,
  Body: SheetBody,
  Footer: SheetFooter,
  Trigger: SheetTrigger,
  Close: SheetClose,
});

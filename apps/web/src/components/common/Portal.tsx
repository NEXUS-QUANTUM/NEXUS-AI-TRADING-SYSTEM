// apps/web/src/components/common/Portal.tsx
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
  useLayoutEffect,
} from 'react';
import { createPortal } from 'react-dom';
import { cn } from '@/lib/utils';
import { motion, AnimatePresence } from 'framer-motion';

// ============================================================================
// TYPES
// ============================================================================

export type PortalVariant = 'default' | 'modal' | 'popover' | 'tooltip' | 'notification' | 'dropdown' | 'sidebar' | 'fullscreen';

export type PortalAnimation = 'fade' | 'slide-up' | 'slide-down' | 'slide-left' | 'slide-right' | 'scale' | 'bounce' | 'none';

export type PortalPlacement = 'center' | 'top' | 'bottom' | 'left' | 'right' | 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';

export type PortalZIndex = 'auto' | 'base' | 'modal' | 'popover' | 'tooltip' | 'notification' | 'dropdown' | 'sidebar' | 'max';

export interface PortalProps {
  // --- Contrôle ---
  /** Ouverture du portal */
  open?: boolean;
  /** Ouverture par défaut */
  defaultOpen?: boolean;
  /** Callback lors du changement d'état */
  onOpenChange?: (open: boolean) => void;

  // --- Contenu ---
  /** Contenu à porter */
  children: ReactNode;
  /** Fallback à afficher quand le portal est fermé */
  fallback?: ReactNode;
  /** Élément déclencheur (optionnel) */
  trigger?: ReactNode;

  // --- Apparence ---
  /** Variante du portal */
  variant?: PortalVariant;
  /** Animation à l'ouverture/fermeture */
  animation?: PortalAnimation;
  /** Position du portal */
  placement?: PortalPlacement;
  /** Classe CSS additionnelle */
  className?: string;
  /** Classe CSS pour le conteneur */
  containerClassName?: string;
  /** Classe CSS pour l'overlay */
  overlayClassName?: string;
  /** Classe CSS pour le contenu */
  contentClassName?: string;

  // --- Overlay ---
  /** Afficher l'overlay */
  showOverlay?: boolean;
  /** Cliquer sur l'overlay ferme le portal */
  closeOnOverlayClick?: boolean;
  /** Classe CSS de l'overlay */
  overlayClass?: string;
  /** Opacité de l'overlay */
  overlayOpacity?: number;
  /** Couleur de l'overlay */
  overlayColor?: string;
  /** Flou de l'overlay */
  overlayBlur?: 'none' | 'sm' | 'md' | 'lg' | 'xl';

  // --- Comportement ---
  /** ID du conteneur parent */
  containerId?: string;
  /** Élément parent pour le portal */
  parentElement?: HTMLElement | null;
  /** Élément parent par sélecteur */
  parentSelector?: string;
  /** Fermer à l'appui de la touche Escape */
  closeOnEscape?: boolean;
  /** Fermer automatiquement après un délai */
  autoClose?: number;
  /** Désactiver le portal */
  disabled?: boolean;
  /** Garder le focus à l'intérieur */
  trapFocus?: boolean;
  /** Restaurer le focus à la fermeture */
  restoreFocus?: boolean;
  /** Désactiver le scroll du body */
  lockScroll?: boolean;
  /** Désactiver le scroll du body avec prévention du scroll */
  preventScroll?: boolean;
  /** Délai d'ouverture (ms) */
  openDelay?: number;
  /** Délai de fermeture (ms) */
  closeDelay?: number;
  /** Conserver le DOM après la fermeture */
  keepMounted?: boolean;

  // --- Accessibilité ---
  /** ARIA label */
  ariaLabel?: string;
  /** ARIA describedby */
  ariaDescribedby?: string;
  /** ARIA labelledby */
  ariaLabelledby?: string;
  /** Rôle ARIA */
  role?: 'dialog' | 'alertdialog' | 'menu' | 'tooltip' | 'presentation' | 'none';
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
  /** Callback après le rendu */
  onMounted?: () => void;
  /** Callback après le démontage */
  onUnmounted?: () => void;

  // --- Avancé ---
  /** Niveau z-index */
  zIndex?: PortalZIndex | number;
  /** Désactiver le portal (rendu en ligne) */
  disablePortal?: boolean;
  /** Mode debug */
  debug?: boolean;
  /** Test ID pour les tests */
  dataTestId?: string;
}

// ============================================================================
// CONSTANTES
// ============================================================================

const Z_INDEX_MAP: Record<PortalZIndex, number> = {
  auto: 0,
  base: 100,
  popover: 1000,
  dropdown: 1100,
  tooltip: 1200,
  modal: 1300,
  notification: 1400,
  sidebar: 1500,
  max: 9999,
};

const ANIMATION_MAP: Record<PortalAnimation, {
  enter: string;
  enterFrom: string;
  enterTo: string;
  leave: string;
  leaveFrom: string;
  leaveTo: string;
}> = {
  'fade': {
    enter: 'transition-opacity duration-300 ease-out',
    enterFrom: 'opacity-0',
    enterTo: 'opacity-100',
    leave: 'transition-opacity duration-200 ease-in',
    leaveFrom: 'opacity-100',
    leaveTo: 'opacity-0',
  },
  'slide-up': {
    enter: 'transition-all duration-300 ease-out',
    enterFrom: 'opacity-0 translate-y-8',
    enterTo: 'opacity-100 translate-y-0',
    leave: 'transition-all duration-200 ease-in',
    leaveFrom: 'opacity-100 translate-y-0',
    leaveTo: 'opacity-0 translate-y-8',
  },
  'slide-down': {
    enter: 'transition-all duration-300 ease-out',
    enterFrom: 'opacity-0 -translate-y-8',
    enterTo: 'opacity-100 translate-y-0',
    leave: 'transition-all duration-200 ease-in',
    leaveFrom: 'opacity-100 translate-y-0',
    leaveTo: 'opacity-0 -translate-y-8',
  },
  'slide-left': {
    enter: 'transition-all duration-300 ease-out',
    enterFrom: 'opacity-0 translate-x-8',
    enterTo: 'opacity-100 translate-x-0',
    leave: 'transition-all duration-200 ease-in',
    leaveFrom: 'opacity-100 translate-x-0',
    leaveTo: 'opacity-0 translate-x-8',
  },
  'slide-right': {
    enter: 'transition-all duration-300 ease-out',
    enterFrom: 'opacity-0 -translate-x-8',
    enterTo: 'opacity-100 translate-x-0',
    leave: 'transition-all duration-200 ease-in',
    leaveFrom: 'opacity-100 translate-x-0',
    leaveTo: 'opacity-0 -translate-x-8',
  },
  'scale': {
    enter: 'transition-all duration-300 ease-out',
    enterFrom: 'opacity-0 scale-95',
    enterTo: 'opacity-100 scale-100',
    leave: 'transition-all duration-200 ease-in',
    leaveFrom: 'opacity-100 scale-100',
    leaveTo: 'opacity-0 scale-95',
  },
  'bounce': {
    enter: 'transition-all duration-500 ease-out',
    enterFrom: 'opacity-0 scale-50 -translate-y-4',
    enterTo: 'opacity-100 scale-100 translate-y-0',
    leave: 'transition-all duration-300 ease-in',
    leaveFrom: 'opacity-100 scale-100 translate-y-0',
    leaveTo: 'opacity-0 scale-50 -translate-y-4',
  },
  'none': {
    enter: 'duration-0',
    enterFrom: '',
    enterTo: '',
    leave: 'duration-0',
    leaveFrom: '',
    leaveTo: '',
  },
};

const PLACEMENT_MAP: Record<PortalPlacement, string> = {
  center: 'items-center justify-center',
  top: 'items-start justify-center pt-8',
  bottom: 'items-end justify-center pb-8',
  left: 'items-center justify-start pl-8',
  right: 'items-center justify-end pr-8',
  'top-left': 'items-start justify-start pt-8 pl-8',
  'top-right': 'items-start justify-end pt-8 pr-8',
  'bottom-left': 'items-end justify-start pb-8 pl-8',
  'bottom-right': 'items-end justify-end pb-8 pr-8',
};

const OVERLAY_BLUR_MAP: Record<NonNullable<PortalProps['overlayBlur']>, string> = {
  none: '',
  sm: 'backdrop-blur-sm',
  md: 'backdrop-blur-md',
  lg: 'backdrop-blur-lg',
  xl: 'backdrop-blur-xl',
};

// ============================================================================
// CONTEXT
// ============================================================================

interface PortalContextType {
  open: boolean;
  setOpen: (open: boolean) => void;
  close: () => void;
  variant: PortalVariant;
  animation: PortalAnimation;
  placement: PortalPlacement;
  isLoading: boolean;
  disabled: boolean;
  zIndex: number;
  portalId: string;
}

const PortalContext = createContext<PortalContextType | null>(null);

export const usePortalContext = () => {
  const context = useContext(PortalContext);
  if (!context) {
    throw new Error('usePortalContext must be used within a Portal');
  }
  return context;
};

// ============================================================================
// COMPOSANT PRINCIPAL
// ============================================================================

export const Portal = forwardRef<HTMLDivElement, PortalProps>(
  (props, ref) => {
    const {
      // Contrôle
      open: externalOpen,
      defaultOpen = false,
      onOpenChange,

      // Contenu
      children,
      fallback,
      trigger,

      // Apparence
      variant = 'default',
      animation = 'fade',
      placement = 'center',
      className,
      containerClassName,
      overlayClassName,
      contentClassName,

      // Overlay
      showOverlay = false,
      closeOnOverlayClick = true,
      overlayClass,
      overlayOpacity = 0.5,
      overlayColor = '#000000',
      overlayBlur = 'none',

      // Comportement
      containerId,
      parentElement: externalParentElement,
      parentSelector,
      closeOnEscape = true,
      autoClose = 0,
      disabled = false,
      trapFocus = false,
      restoreFocus = true,
      lockScroll = true,
      preventScroll = false,
      openDelay = 0,
      closeDelay = 0,
      keepMounted = false,

      // Accessibilité
      ariaLabel,
      ariaDescribedby,
      ariaLabelledby,
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
      onMounted,
      onUnmounted,

      // Avancé
      zIndex = 'modal',
      disablePortal = false,
      debug = false,
      dataTestId,
    } = props;

    // ========================================================================
    // RÉFÉRENCES
    // ========================================================================

    const portalRef = useRef<HTMLDivElement>(null);
    const triggerRef = useRef<HTMLElement>(null);
    const focusTargetRef = useRef<HTMLElement | null>(null);
    const previousFocusRef = useRef<HTMLElement | null>(null);
    const timerRef = useRef<NodeJS.Timeout | null>(null);
    const uniqueId = useId();
    const portalId = id || `nexus-portal-${uniqueId}`;

    // ========================================================================
    // ÉTATS
    // ========================================================================

    const [internalOpen, setInternalOpen] = useState(defaultOpen);
    const [isMounted, setIsMounted] = useState(false);
    const [isAnimating, setIsAnimating] = useState(false);
    const [parentElement, setParentElement] = useState<HTMLElement | null>(null);
    const [hasBeenOpened, setHasBeenOpened] = useState(false);
    const [isVisible, setIsVisible] = useState(false);

    // ========================================================================
    // DÉRIVÉS
    // ========================================================================

    const open = externalOpen ?? internalOpen;
    const isControlled = externalOpen !== undefined;
    const zIndexValue = typeof zIndex === 'number' ? zIndex : Z_INDEX_MAP[zIndex];
    const shouldRender = open || (keepMounted && hasBeenOpened);

    // ========================================================================
    // GESTION DE L'OUVERTURE/FERMETURE
    // ========================================================================

    const openPortal = useCallback(() => {
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

    const closePortal = useCallback(() => {
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

    const togglePortal = useCallback(() => {
      if (open) {
        closePortal();
      } else {
        openPortal();
      }
    }, [open, closePortal, openPortal]);

    // ========================================================================
    // TIMEOUTS
    // ========================================================================

    useEffect(() => {
      if (open && autoClose > 0) {
        const timer = setTimeout(closePortal, autoClose);
        return () => clearTimeout(timer);
      }
    }, [open, autoClose, closePortal]);

    // ========================================================================
    // FERMETURE PAR ESCAPE
    // ========================================================================

    useEffect(() => {
      if (!closeOnEscape) return;

      const handleEscape = (e: KeyboardEvent) => {
        if (e.key === 'Escape' && open) {
          e.preventDefault();
          closePortal();
        }
      };

      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }, [open, closeOnEscape, closePortal]);

    // ========================================================================
    // FERMETURE PAR CLIC SUR L'OVERLAY
    // ========================================================================

    const handleOverlayClick = useCallback((e: React.MouseEvent) => {
      if (closeOnOverlayClick && e.target === e.currentTarget) {
        closePortal();
      }
    }, [closeOnOverlayClick, closePortal]);

    // ========================================================================
    // FOCUS
    // ========================================================================

    useEffect(() => {
      if (!open) {
        if (restoreFocus && previousFocusRef.current) {
          previousFocusRef.current.focus();
        }
        return;
      }

      // Sauvegarder l'élément actuellement focusé
      const activeElement = document.activeElement as HTMLElement;
      if (activeElement) {
        previousFocusRef.current = activeElement;
      }

      // Focus sur le premier élément focusable du portal
      if (trapFocus && portalRef.current) {
        const focusable = portalRef.current.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
        );
        if (focusable.length > 0) {
          (focusable[0] as HTMLElement).focus();
        }
      }
    }, [open, trapFocus, restoreFocus]);

    // ========================================================================
    // TRAP FOCUS
    // ========================================================================

    useEffect(() => {
      if (!trapFocus || !open) return;

      const handleFocus = (e: FocusEvent) => {
        if (!portalRef.current) return;
        const target = e.target as HTMLElement;
        if (!portalRef.current.contains(target)) {
          const focusable = portalRef.current.querySelectorAll(
            'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
          );
          if (focusable.length > 0) {
            (focusable[0] as HTMLElement).focus();
          }
        }
      };

      document.addEventListener('focus', handleFocus, true);
      return () => document.removeEventListener('focus', handleFocus, true);
    }, [open, trapFocus]);

    // ========================================================================
    // SCROLL LOCK
    // ========================================================================

    useEffect(() => {
      if (!lockScroll || preventScroll) return;

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
    }, [open, lockScroll, preventScroll]);

    // ========================================================================
    // PARENT ELEMENT
    // ========================================================================

    useEffect(() => {
      const findParent = (): HTMLElement | null => {
        if (externalParentElement) {
          return externalParentElement;
        }

        if (parentSelector) {
          return document.querySelector(parentSelector) as HTMLElement | null;
        }

        if (containerId) {
          return document.getElementById(containerId);
        }

        return document.body;
      };

      const parent = findParent();
      setParentElement(parent);
    }, [externalParentElement, parentSelector, containerId]);

    // ========================================================================
    // MOUNT / UNMOUNT
    // ========================================================================

    useLayoutEffect(() => {
      setIsMounted(true);
      onMounted?.();

      return () => {
        setIsMounted(false);
        onUnmounted?.();
      };
    }, [onMounted, onUnmounted]);

    // ========================================================================
    // ANIMATION
    // ========================================================================

    useEffect(() => {
      if (open) {
        setTimeout(() => {
          setIsAnimating(true);
        }, 50);
      } else {
        setIsAnimating(false);
      }
    }, [open]);

    // ========================================================================
    // CONTEXT
    // ========================================================================

    const contextValue = useMemo<PortalContextType>(
      () => ({
        open,
        setOpen: isControlled ? (value: boolean) => onOpenChange?.(value) : setInternalOpen,
        close: closePortal,
        variant,
        animation,
        placement,
        isLoading,
        disabled,
        zIndex: zIndexValue,
        portalId,
      }),
      [
        open,
        isControlled,
        onOpenChange,
        closePortal,
        variant,
        animation,
        placement,
        isLoading,
        disabled,
        zIndexValue,
        portalId,
      ]
    );

    // ========================================================================
    // RENDU DU CONTENU
    // ========================================================================

    const renderContent = () => {
      if (!shouldRender && !isAnimating) {
        return fallback || null;
      }

      const animationClasses = ANIMATION_MAP[animation];

      return (
        <PortalContext.Provider value={contextValue}>
          <div
            ref={(node) => {
              if (typeof ref === 'function') ref(node);
              else if (ref) ref.current = node;
              portalRef.current = node;
            }}
            id={portalId}
            className={cn(
              'fixed inset-0 z-[var(--portal-z-index)]',
              containerClassName
            )}
            style={{
              '--portal-z-index': zIndexValue,
            } as React.CSSProperties}
            role={role}
            aria-label={ariaLabel}
            aria-describedby={ariaDescribedby}
            aria-labelledby={ariaLabelledby}
            data-testid={dataTestId}
          >
            {/* Overlay */}
            {showOverlay && (
              <motion.div
                className={cn(
                  'absolute inset-0',
                  OVERLAY_BLUR_MAP[overlayBlur],
                  overlayClass,
                  overlayClassName
                )}
                style={{
                  backgroundColor: overlayColor,
                  opacity: overlayOpacity,
                }}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.3 }}
                onClick={handleOverlayClick}
              />
            )}

            {/* Contenu */}
            <div
              className={cn(
                'relative flex min-h-full',
                PLACEMENT_MAP[placement],
                className
              )}
            >
              <motion.div
                className={cn(
                  'relative',
                  contentClassName
                )}
                initial={{
                  opacity: 0,
                  scale: 0.95,
                  y: 20,
                }}
                animate={{
                  opacity: 1,
                  scale: 1,
                  y: 0,
                }}
                exit={{
                  opacity: 0,
                  scale: 0.95,
                  y: 20,
                }}
                transition={{
                  duration: 0.3,
                  ease: 'easeOut',
                }}
              >
                {isLoading ? (
                  <div className="flex flex-col items-center justify-center gap-3 p-8">
                    <div className="h-8 w-8 animate-spin rounded-full border-4 border-brand-500 border-t-transparent" />
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
              </motion.div>
            </div>
          </div>
        </PortalContext.Provider>
      );
    };

    // ========================================================================
    // RENDU FINAL
    // ========================================================================

    // Si le portal est désactivé, rendre en ligne
    if (disablePortal || !isMounted) {
      return (
        <>
          {trigger && (
            <div ref={triggerRef as any} onClick={openPortal}>
              {trigger}
            </div>
          )}
          {open && renderContent()}
        </>
      );
    }

    // Rendu avec portal
    return (
      <>
        {trigger && (
          <div
            ref={triggerRef as any}
            onClick={openPortal}
            className="inline-block"
          >
            {trigger}
          </div>
        )}
        {parentElement && createPortal(renderContent(), parentElement)}
      </>
    );
  }
);

Portal.displayName = 'Portal';

// ============================================================================
// SOUS-COMPOSANTS
// ============================================================================

// --- Portal.Header ---
interface PortalHeaderProps {
  children: ReactNode;
  className?: string;
  showCloseButton?: boolean;
  onClose?: () => void;
}

export const PortalHeader: React.FC<PortalHeaderProps> = ({
  children,
  className,
  showCloseButton = true,
  onClose,
}) => {
  const context = usePortalContext();

  const handleClose = () => {
    if (onClose) onClose();
    if (context) context.close();
  };

  return (
    <div className={cn('flex items-center justify-between border-b border-gray-200 dark:border-gray-700 p-4', className)}>
      <div className="flex-1 min-w-0">{children}</div>
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

// --- Portal.Body ---
interface PortalBodyProps {
  children: ReactNode;
  className?: string;
  scrollable?: boolean;
  maxHeight?: string | number;
}

export const PortalBody: React.FC<PortalBodyProps> = ({
  children,
  className,
  scrollable = true,
  maxHeight = '70vh',
}) => {
  return (
    <div
      className={cn(
        'flex-1 p-4',
        scrollable && 'overflow-y-auto',
        className
      )}
      style={{ maxHeight: scrollable ? maxHeight : undefined }}
    >
      {children}
    </div>
  );
};

// --- Portal.Footer ---
interface PortalFooterProps {
  children: ReactNode;
  className?: string;
  alignment?: 'left' | 'center' | 'right' | 'between';
}

export const PortalFooter: React.FC<PortalFooterProps> = ({
  children,
  className,
  alignment = 'right',
}) => {
  const alignmentClasses = {
    left: 'justify-start',
    center: 'justify-center',
    right: 'justify-end',
    between: 'justify-between',
  };

  return (
    <div
      className={cn(
        'flex items-center gap-3 border-t border-gray-200 dark:border-gray-700 p-4',
        alignmentClasses[alignment],
        className
      )}
    >
      {children}
    </div>
  );
};

// --- Portal.Trigger ---
interface PortalTriggerProps {
  children: ReactNode;
  className?: string;
}

export const PortalTrigger: React.FC<PortalTriggerProps> = ({
  children,
  className,
}) => {
  const context = usePortalContext();

  const handleClick = () => {
    if (context) context.setOpen(true);
  };

  return (
    <div className={cn('cursor-pointer inline-block', className)} onClick={handleClick}>
      {children}
    </div>
  );
};

// --- Portal.Close ---
interface PortalCloseProps {
  children: ReactNode;
  className?: string;
}

export const PortalClose: React.FC<PortalCloseProps> = ({
  children,
  className,
}) => {
  const context = usePortalContext();

  const handleClick = () => {
    if (context) context.close();
  };

  return (
    <div className={cn('cursor-pointer inline-block', className)} onClick={handleClick}>
      {children}
    </div>
  );
};

// ============================================================================
// HOOKS
// ============================================================================

export const usePortal = (defaultOpen = false) => {
  const [open, setOpen] = useState(defaultOpen);

  const openPortal = useCallback(() => setOpen(true), []);
  const closePortal = useCallback(() => setOpen(false), []);
  const togglePortal = useCallback(() => setOpen((prev) => !prev), []);

  return {
    open,
    setOpen,
    open: openPortal,
    close: closePortal,
    toggle: togglePortal,
  };
};

export const usePortalManager = () => {
  const [portals, setPortals] = useState<Array<{ id: string; open: boolean }>>([]);

  const registerPortal = useCallback((id: string) => {
    setPortals((prev) => [...prev, { id, open: false }]);
  }, []);

  const unregisterPortal = useCallback((id: string) => {
    setPortals((prev) => prev.filter((p) => p.id !== id));
  }, []);

  const openPortal = useCallback((id: string) => {
    setPortals((prev) =>
      prev.map((p) => (p.id === id ? { ...p, open: true } : p))
    );
  }, []);

  const closePortal = useCallback((id: string) => {
    setPortals((prev) =>
      prev.map((p) => (p.id === id ? { ...p, open: false } : p))
    );
  }, []);

  const closeAll = useCallback(() => {
    setPortals((prev) => prev.map((p) => ({ ...p, open: false })));
  }, []);

  const getOpenCount = useCallback(() => {
    return portals.filter((p) => p.open).length;
  }, [portals]);

  return {
    portals,
    registerPortal,
    unregisterPortal,
    openPortal,
    closePortal,
    closeAll,
    getOpenCount,
  };
};

// ============================================================================
// EXPORTS
// ============================================================================

export default Object.assign(Portal, {
  Header: PortalHeader,
  Body: PortalBody,
  Footer: PortalFooter,
  Trigger: PortalTrigger,
  Close: PortalClose,
});

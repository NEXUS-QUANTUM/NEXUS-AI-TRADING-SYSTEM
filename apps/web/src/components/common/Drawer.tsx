/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import { cn } from '@/utils/helpers';
import { X } from 'lucide-react';

// ============================================
// TYPES
// ============================================

export interface DrawerProps {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  children?: React.ReactNode;
  modal?: boolean;
}

export interface DrawerTriggerProps {
  asChild?: boolean;
  children?: React.ReactNode;
  onClick?: (event: React.MouseEvent) => void;
}

export interface DrawerPortalProps {
  container?: HTMLElement | null;
  children?: React.ReactNode;
}

export interface DrawerOverlayProps {
  className?: string;
  onClick?: (event: React.MouseEvent) => void;
}

export interface DrawerContentProps {
  className?: string;
  children?: React.ReactNode;
  side?: 'left' | 'right' | 'top' | 'bottom';
  size?: 'sm' | 'md' | 'lg' | 'xl' | 'full';
  hideClose?: boolean;
  closeOnOverlayClick?: boolean;
  closeOnEscape?: boolean;
  onClose?: () => void;
  onOpen?: () => void;
  onAnimationEnd?: () => void;
  overlayClassName?: string;
}

export interface DrawerHeaderProps {
  className?: string;
  children?: React.ReactNode;
}

export interface DrawerFooterProps {
  className?: string;
  children?: React.ReactNode;
}

export interface DrawerTitleProps {
  className?: string;
  children?: React.ReactNode;
}

export interface DrawerDescriptionProps {
  className?: string;
  children?: React.ReactNode;
}

export interface DrawerCloseProps {
  className?: string;
  children?: React.ReactNode;
  onClick?: (event: React.MouseEvent) => void;
}

// ============================================
// CONTEXTE
// ============================================

interface DrawerContextType {
  open: boolean;
  setOpen: (open: boolean) => void;
  isOpen: boolean;
  side: 'left' | 'right' | 'top' | 'bottom';
  size: 'sm' | 'md' | 'lg' | 'xl' | 'full';
}

const DrawerContext = React.createContext<DrawerContextType | undefined>(
  undefined
);

const useDrawer = () => {
  const context = React.useContext(DrawerContext);
  if (!context) {
    throw new Error('useDrawer must be used within a Drawer');
  }
  return context;
};

// ============================================
// COMPOSANT PRINCIPAL
// ============================================

const Drawer = React.forwardRef<HTMLDivElement, DrawerProps>(
  ({ open, defaultOpen = false, onOpenChange, children, modal = true }, ref) => {
    const [isOpen, setIsOpen] = React.useState(defaultOpen);

    React.useEffect(() => {
      if (open !== undefined) {
        setIsOpen(open);
      }
    }, [open]);

    const setOpen = React.useCallback(
      (newOpen: boolean) => {
        setIsOpen(newOpen);
        onOpenChange?.(newOpen);
      },
      [onOpenChange]
    );

    // Gestion des touches clavier
    React.useEffect(() => {
      if (!isOpen) return;

      const handleEscape = (e: KeyboardEvent) => {
        if (e.key === 'Escape') {
          setOpen(false);
        }
      };

      document.addEventListener('keydown', handleEscape);
      return () => document.removeEventListener('keydown', handleEscape);
    }, [isOpen, setOpen]);

    // Empêcher le scroll du body
    React.useEffect(() => {
      if (isOpen && modal) {
        document.body.style.overflow = 'hidden';
        return () => {
          document.body.style.overflow = '';
        };
      }
    }, [isOpen, modal]);

    const contextValue = React.useMemo(
      () => ({
        open: isOpen,
        setOpen,
        isOpen,
        side: 'right' as const,
        size: 'md' as const,
      }),
      [isOpen, setOpen]
    );

    if (!isOpen) return null;

    return (
      <DrawerContext.Provider value={contextValue}>
        <div ref={ref} className="fixed inset-0 z-50">
          {children}
        </div>
      </DrawerContext.Provider>
    );
  }
);
Drawer.displayName = 'Drawer';

// ============================================
// TRIGGER
// ============================================

const DrawerTrigger = React.forwardRef<HTMLButtonElement, DrawerTriggerProps>(
  ({ asChild, children, onClick, ...props }, ref) => {
    const { setOpen } = useDrawer();

    const handleClick = (e: React.MouseEvent) => {
      setOpen(true);
      onClick?.(e);
    };

    if (asChild && React.isValidElement(children)) {
      return React.cloneElement(children as React.ReactElement, {
        onClick: handleClick,
        ...props,
      });
    }

    return (
      <button
        ref={ref}
        onClick={handleClick}
        className="inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors hover:bg-gray-100 dark:hover:bg-gray-800"
        {...props}
      >
        {children}
      </button>
    );
  }
);
DrawerTrigger.displayName = 'DrawerTrigger';

// ============================================
// OVERLAY
// ============================================

const DrawerOverlay = React.forwardRef<HTMLDivElement, DrawerOverlayProps>(
  ({ className, onClick }, ref) => {
    const { setOpen } = useDrawer();

    const handleClick = (e: React.MouseEvent) => {
      onClick?.(e);
      setOpen(false);
    };

    return (
      <div
        ref={ref}
        className={cn(
          'fixed inset-0 bg-black/80 backdrop-blur-sm transition-opacity',
          'animate-in fade-in-0 duration-300',
          className
        )}
        onClick={handleClick}
      />
    );
  }
);
DrawerOverlay.displayName = 'DrawerOverlay';

// ============================================
// CONTENT
// ============================================

const DrawerContent = React.forwardRef<HTMLDivElement, DrawerContentProps>(
  (
    {
      className,
      children,
      side = 'right',
      size = 'md',
      hideClose = false,
      closeOnOverlayClick = true,
      closeOnEscape = true,
      onClose,
      onOpen,
      onAnimationEnd,
      overlayClassName,
      ...props
    },
    ref
  ) => {
    const { setOpen } = useDrawer();

    // ============================================
    // TAILLES
    // ============================================
    const sizeClasses = {
      left: {
        sm: 'w-72',
        md: 'w-96',
        lg: 'w-[480px]',
        xl: 'w-[560px]',
        full: 'w-full',
      },
      right: {
        sm: 'w-72',
        md: 'w-96',
        lg: 'w-[480px]',
        xl: 'w-[560px]',
        full: 'w-full',
      },
      top: {
        sm: 'h-48',
        md: 'h-64',
        lg: 'h-96',
        xl: 'h-[480px]',
        full: 'h-full',
      },
      bottom: {
        sm: 'h-48',
        md: 'h-64',
        lg: 'h-96',
        xl: 'h-[480px]',
        full: 'h-full',
      },
    };

    // ============================================
    // POSITIONS & ANIMATIONS
    // ============================================
    const positionClasses = {
      left: 'left-0 top-0 h-full',
      right: 'right-0 top-0 h-full',
      top: 'top-0 left-0 w-full',
      bottom: 'bottom-0 left-0 w-full',
    };

    const animationClasses = {
      left: 'slide-in-from-left animate-in duration-300',
      right: 'slide-in-from-right animate-in duration-300',
      top: 'slide-in-from-top animate-in duration-300',
      bottom: 'slide-in-from-bottom animate-in duration-300',
    };

    const handleClose = () => {
      setOpen(false);
      onClose?.();
    };

    const handleOpen = () => {
      onOpen?.();
    };

    React.useEffect(() => {
      handleOpen();
    }, []);

    return (
      <div className="fixed inset-0 z-50 flex">
        {/* Overlay */}
        <DrawerOverlay
          className={overlayClassName}
          onClick={closeOnOverlayClick ? handleClose : undefined}
        />

        {/* Contenu du drawer */}
        <div
          ref={ref}
          className={cn(
            'fixed bg-white dark:bg-gray-900 shadow-2xl',
            positionClasses[side],
            sizeClasses[side][size],
            animationClasses[side],
            className
          )}
          onAnimationEnd={onAnimationEnd}
          {...props}
        >
          {/* Bouton de fermeture */}
          {!hideClose && (
            <button
              onClick={handleClose}
              className={cn(
                'absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity',
                'hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
                'disabled:pointer-events-none',
                'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100'
              )}
            >
              <X className="h-4 w-4" />
              <span className="sr-only">Fermer</span>
            </button>
          )}

          {/* Contenu */}
          <div className="flex h-full flex-col overflow-auto p-6">{children}</div>
        </div>
      </div>
    );
  }
);
DrawerContent.displayName = 'DrawerContent';

// ============================================
// HEADER
// ============================================

const DrawerHeader = React.forwardRef<HTMLDivElement, DrawerHeaderProps>(
  ({ className, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('flex flex-col space-y-1.5 pb-4', className)}
      {...props}
    >
      {children}
    </div>
  )
);
DrawerHeader.displayName = 'DrawerHeader';

// ============================================
// FOOTER
// ============================================

const DrawerFooter = React.forwardRef<HTMLDivElement, DrawerFooterProps>(
  ({ className, children, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('mt-auto flex flex-col-reverse gap-2 pt-4 sm:flex-row sm:justify-end', className)}
      {...props}
    >
      {children}
    </div>
  )
);
DrawerFooter.displayName = 'DrawerFooter';

// ============================================
// TITLE
// ============================================

const DrawerTitle = React.forwardRef<HTMLHeadingElement, DrawerTitleProps>(
  ({ className, children, ...props }, ref) => (
    <h2
      ref={ref}
      className={cn('text-lg font-semibold leading-none tracking-tight text-gray-900 dark:text-white', className)}
      {...props}
    >
      {children}
    </h2>
  )
);
DrawerTitle.displayName = 'DrawerTitle';

// ============================================
// DESCRIPTION
// ============================================

const DrawerDescription = React.forwardRef<
  HTMLParagraphElement,
  DrawerDescriptionProps
>(({ className, children, ...props }, ref) => (
  <p
    ref={ref}
    className={cn('text-sm text-gray-500 dark:text-gray-400', className)}
    {...props}
  >
    {children}
  </p>
));
DrawerDescription.displayName = 'DrawerDescription';

// ============================================
// CLOSE
// ============================================

const DrawerClose = React.forwardRef<HTMLButtonElement, DrawerCloseProps>(
  ({ className, children, onClick, ...props }, ref) => {
    const { setOpen } = useDrawer();

    const handleClick = (e: React.MouseEvent) => {
      setOpen(false);
      onClick?.(e);
    };

    return (
      <button
        ref={ref}
        onClick={handleClick}
        className={cn(
          'inline-flex items-center justify-center rounded-md text-sm font-medium transition-colors',
          'hover:bg-gray-100 dark:hover:bg-gray-800',
          className
        )}
        {...props}
      >
        {children || <X className="h-4 w-4" />}
      </button>
    );
  }
);
DrawerClose.displayName = 'DrawerClose';

// ============================================
// EXPORTATIONS
// ============================================

export {
  Drawer,
  DrawerTrigger,
  DrawerContent,
  DrawerHeader,
  DrawerFooter,
  DrawerTitle,
  DrawerDescription,
  DrawerClose,
  DrawerOverlay,
};

export default Drawer;

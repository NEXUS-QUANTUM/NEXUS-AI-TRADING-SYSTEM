/**
 * NEXUS AI TRADING SYSTEM
 * Copyright © 2026 NEXUS QUANTUM LTD
 * CEO: Dr X... - Majority Shareholder
 */

'use client';

import * as React from 'react';
import * as DialogPrimitive from '@radix-ui/react-dialog';
import { cn } from '@/utils/helpers';
import { X } from 'lucide-react';

// ============================================
// TYPES
// ============================================

export interface DialogProps
  extends React.ComponentPropsWithoutRef<typeof DialogPrimitive.Root> {
  open?: boolean;
  defaultOpen?: boolean;
  onOpenChange?: (open: boolean) => void;
  modal?: boolean;
}

export interface DialogTriggerProps
  extends React.ComponentPropsWithoutRef<typeof DialogPrimitive.Trigger> {
  asChild?: boolean;
}

export interface DialogPortalProps
  extends React.ComponentPropsWithoutRef<typeof DialogPrimitive.Portal> {
  container?: HTMLElement | null;
}

export interface DialogOverlayProps
  extends React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay> {
  className?: string;
}

export interface DialogContentProps
  extends React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content> {
  className?: string;
  onInteractOutside?: (event: Event) => void;
  onEscapeKeyDown?: (event: KeyboardEvent) => void;
  onPointerDownOutside?: (event: Event) => void;
  hideClose?: boolean;
  closeOnInteractOutside?: boolean;
  size?: 'sm' | 'md' | 'lg' | 'xl' | '2xl' | 'full' | 'auto';
  position?: 'center' | 'top' | 'bottom' | 'left' | 'right';
}

export interface DialogHeaderProps
  extends React.HTMLAttributes<HTMLDivElement> {
  className?: string;
}

export interface DialogFooterProps
  extends React.HTMLAttributes<HTMLDivElement> {
  className?: string;
}

export interface DialogTitleProps
  extends React.ComponentPropsWithoutRef<typeof DialogPrimitive.Title> {
  className?: string;
}

export interface DialogDescriptionProps
  extends React.ComponentPropsWithoutRef<typeof DialogPrimitive.Description> {
  className?: string;
}

export interface DialogCloseProps
  extends React.ComponentPropsWithoutRef<typeof DialogPrimitive.Close> {
  className?: string;
}

// ============================================
// COMPOSANTS
// ============================================

const Dialog = DialogPrimitive.Root;

const DialogTrigger = DialogPrimitive.Trigger;

const DialogPortal = DialogPrimitive.Portal;

const DialogClose = DialogPrimitive.Close;

const DialogOverlay = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  DialogOverlayProps
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      'fixed inset-0 z-50 bg-black/80 backdrop-blur-sm',
      'data-[state=open]:animate-in data-[state=closed]:animate-out',
      'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
      className
    )}
    {...props}
  />
));
DialogOverlay.displayName = DialogPrimitive.Overlay.displayName;

const DialogContent = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  DialogContentProps
>(
  (
    {
      className,
      children,
      hideClose = false,
      closeOnInteractOutside = true,
      size = 'md',
      position = 'center',
      onInteractOutside,
      ...props
    },
    ref
  ) => {
    // ============================================
    // TAILLES
    // ============================================
    const sizeClasses = {
      sm: 'max-w-sm',
      md: 'max-w-md',
      lg: 'max-w-lg',
      xl: 'max-w-xl',
      '2xl': 'max-w-2xl',
      full: 'max-w-[95vw]',
      auto: 'max-w-fit',
    };

    // ============================================
    // POSITIONS
    // ============================================
    const positionClasses = {
      center: 'fixed left-[50%] top-[50%] translate-x-[-50%] translate-y-[-50%]',
      top: 'fixed left-[50%] top-4 translate-x-[-50%]',
      bottom: 'fixed left-[50%] bottom-4 translate-x-[-50%]',
      left: 'fixed left-4 top-[50%] translate-y-[-50%]',
      right: 'fixed right-4 top-[50%] translate-y-[-50%]',
    };

    // ============================================
    // GESTIONNAIRES
    // ============================================
    const handleInteractOutside = (event: Event) => {
      if (!closeOnInteractOutside) {
        event.preventDefault();
      }
      onInteractOutside?.(event);
    };

    return (
      <DialogPortal>
        <DialogOverlay />
        <DialogPrimitive.Content
          ref={ref}
          className={cn(
            'z-50 grid w-full gap-4 border bg-white p-6 shadow-lg dark:bg-gray-900',
            'duration-200 data-[state=open]:animate-in data-[state=closed]:animate-out',
            'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
            'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
            'data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%]',
            'data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%]',
            'sm:rounded-lg',
            sizeClasses[size],
            positionClasses[position],
            className
          )}
          onInteractOutside={handleInteractOutside}
          {...props}
        >
          {children}
          {!hideClose && (
            <DialogPrimitive.Close
              className={cn(
                'absolute right-4 top-4 rounded-sm opacity-70 ring-offset-background transition-opacity',
                'hover:opacity-100 focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2',
                'disabled:pointer-events-none',
                'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-gray-100'
              )}
            >
              <X className="h-4 w-4" />
              <span className="sr-only">Fermer</span>
            </DialogPrimitive.Close>
          )}
        </DialogPrimitive.Content>
      </DialogPortal>
    );
  }
);
DialogContent.displayName = DialogPrimitive.Content.displayName;

const DialogHeader = React.forwardRef<HTMLDivElement, DialogHeaderProps>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'flex flex-col space-y-1.5 text-center sm:text-left',
        className
      )}
      {...props}
    />
  )
);
DialogHeader.displayName = 'DialogHeader';

const DialogFooter = React.forwardRef<HTMLDivElement, DialogFooterProps>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'flex flex-col-reverse sm:flex-row sm:justify-end sm:space-x-2',
        className
      )}
      {...props}
    />
  )
);
DialogFooter.displayName = 'DialogFooter';

const DialogTitle = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Title>,
  DialogTitleProps
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Title
    ref={ref}
    className={cn(
      'text-lg font-semibold leading-none tracking-tight text-gray-900 dark:text-white',
      className
    )}
    {...props}
  />
));
DialogTitle.displayName = DialogPrimitive.Title.displayName;

const DialogDescription = React.forwardRef<
  React.ElementRef<typeof DialogPrimitive.Description>,
  DialogDescriptionProps
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Description
    ref={ref}
    className={cn('text-sm text-gray-500 dark:text-gray-400', className)}
    {...props}
  />
));
DialogDescription.displayName = DialogPrimitive.Description.displayName;

// ============================================
// SOUS-COMPOSANTS
// ============================================

export interface DialogConfirmProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onConfirm: () => void;
  onCancel?: () => void;
  title: string;
  description: string;
  confirmLabel?: string;
  cancelLabel?: string;
  confirmVariant?: 'default' | 'destructive' | 'success' | 'warning' | 'outline';
  isLoading?: boolean;
  size?: 'sm' | 'md' | 'lg';
}

const DialogConfirm = React.forwardRef<HTMLDivElement, DialogConfirmProps>(
  (
    {
      open,
      onOpenChange,
      onConfirm,
      onCancel,
      title,
      description,
      confirmLabel = 'Confirmer',
      cancelLabel = 'Annuler',
      confirmVariant = 'default',
      isLoading = false,
      size = 'md',
      ...props
    },
    ref
  ) => {
    const variantClasses = {
      default: 'bg-blue-600 text-white hover:bg-blue-700 dark:bg-blue-600 dark:hover:bg-blue-700',
      destructive: 'bg-red-600 text-white hover:bg-red-700 dark:bg-red-600 dark:hover:bg-red-700',
      success: 'bg-green-600 text-white hover:bg-green-700 dark:bg-green-600 dark:hover:bg-green-700',
      warning: 'bg-yellow-600 text-white hover:bg-yellow-700 dark:bg-yellow-600 dark:hover:bg-yellow-700',
      outline: 'border border-gray-300 bg-transparent hover:bg-gray-100 dark:border-gray-700 dark:hover:bg-gray-800',
    };

    return (
      <Dialog open={open} onOpenChange={onOpenChange}>
        <DialogContent
          ref={ref as any}
          size={size}
          className="sm:max-w-[425px]"
          {...props}
        >
          <DialogHeader>
            <DialogTitle>{title}</DialogTitle>
            <DialogDescription>{description}</DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2 sm:gap-0">
            <DialogPrimitive.Close asChild>
              <button
                className={cn(
                  'inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium',
                  'border border-gray-300 bg-white text-gray-700',
                  'hover:bg-gray-50 dark:border-gray-700 dark:bg-gray-800 dark:text-gray-300 dark:hover:bg-gray-700',
                  'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
                  'disabled:pointer-events-none disabled:opacity-50'
                )}
                onClick={onCancel}
                disabled={isLoading}
              >
                {cancelLabel}
              </button>
            </DialogPrimitive.Close>
            <button
              className={cn(
                'inline-flex items-center justify-center rounded-md px-4 py-2 text-sm font-medium',
                'focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2',
                'disabled:pointer-events-none disabled:opacity-50',
                variantClasses[confirmVariant]
              )}
              onClick={onConfirm}
              disabled={isLoading}
            >
              {isLoading ? (
                <>
                  <span className="mr-2 h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  Chargement...
                </>
              ) : (
                confirmLabel
              )}
            </button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    );
  }
);
DialogConfirm.displayName = 'DialogConfirm';

// ============================================
// EXPORTATIONS
// ============================================

export {
  Dialog,
  DialogPortal,
  DialogOverlay,
  DialogClose,
  DialogTrigger,
  DialogContent,
  DialogHeader,
  DialogFooter,
  DialogTitle,
  DialogDescription,
  DialogConfirm,
};

export default Dialog;
